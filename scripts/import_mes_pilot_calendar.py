"""Import Forex Factory weekly calendar snapshots for the MES paper pilot.

Converts raw Forex Factory weekly JSON snapshots (lists of
``{title, country, date, impact, forecast, previous}``) into normalized
``mes-pilot-calendar-v1`` files, one per Sunday..Saturday (America/New_York)
week, in ``data/mes_pilot/calendar/``:

    data/mes_pilot/calendar/ff-week-<sunday>.json

Each weekly file keeps every distinct snapshot of that week (deduplicated by
source sha256) with its ``retrieved_at`` so the engine can use the calendar
point-in-time: a decision may only use a snapshot retrieved at or before it.
The top-level ``events`` / ``source_sha256`` / ``retrieved_at`` mirror the most
recently retrieved snapshot. Re-running on the same inputs rewrites
byte-identical files (idempotent).

retrieved_at
    Existing raw snapshots: the file modification time (UTC). Identical content
    seen in several files keeps the earliest time. Fetched snapshots: the clock
    at fetch time.

Staleness rule (live)
    A LIVE session requires a snapshot that covers the session date and was
    retrieved within the last 7 days (``EventCalendar.load_for_live``). Check
    with ``--check-live YYYY-MM-DD``.

Usage
    # import the existing shadow-trial raw snapshots (default inputs)
    .venv/Scripts/python.exe scripts/import_mes_pilot_calendar.py

    # import extra raw files
    .venv/Scripts/python.exe scripts/import_mes_pilot_calendar.py --input path/to/ff_week.json

    # Frank, live use only: fetch this week's feed, archive the raw bytes under
    # data/mes_pilot/calendar/raw/, then import. Run once on Sunday evening or
    # before 09:00 ET on the first session of the week, and again any morning
    # you want a refresh. Do not poll: Forex Factory rate-limits this feed
    # (keep to at most one request per hour).
    .venv/Scripts/python.exe scripts/import_mes_pilot_calendar.py --fetch --check-live 2026-10-05

The fetch is the only network access in this script and runs only when
``--fetch`` is passed. No API keys are used.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import argparse
import glob
import hashlib
import json
import os
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mes_pilot.events import (EventCalendar, LIVE_MAX_SNAPSHOT_AGE, SCHEMA_VERSION,  # noqa: E402
                              normalize_forex_factory)

UTC = timezone.utc
DEFAULT_RAW_GLOB = ROOT / "outputs" / "forex_factory_shadow_trial" / "raw" / "*.json"
DEFAULT_OUT = ROOT / "data" / "mes_pilot" / "calendar"
FF_THIS_WEEK_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
GENERATOR = "scripts/import_mes_pilot_calendar.py v1"


def _atomic_write(path: Path, text: str) -> bool:
    """Write only when content changed. Returns True when the file changed."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return True


def load_raw_snapshot(path: Path, retrieved_at: datetime | None = None) -> dict:
    raw = Path(path).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    when = retrieved_at or datetime.fromtimestamp(Path(path).stat().st_mtime, UTC)
    doc = normalize_forex_factory(json.loads(raw.decode("utf-8")), retrieved_at=when, source_sha256=sha)
    doc["retrieved_at_basis"] = "FETCH_CLOCK" if retrieved_at else "FILE_MTIME"
    doc["source_file"] = Path(path).name
    return doc


def _snapshot_entry(doc: dict) -> dict:
    return {"source_sha256": doc["source_sha256"], "retrieved_at": doc["retrieved_at"],
            "retrieved_at_basis": doc.get("retrieved_at_basis", "UNKNOWN"),
            "source_file": doc.get("source_file", ""), "event_count": len(doc["events"]),
            "high_impact_usd_count": sum(e["currency"] == "USD" and e["impact"] == "High" for e in doc["events"]),
            "events": doc["events"]}


def _ts(text: str) -> datetime:
    return datetime.fromisoformat(text)


def week_document(coverage: list[str], entries: list[dict]) -> dict:
    by_sha: dict[str, dict] = {}
    for entry in entries:
        prev = by_sha.get(entry["source_sha256"])
        if prev is None or _ts(entry["retrieved_at"]) < _ts(prev["retrieved_at"]):
            by_sha[entry["source_sha256"]] = entry  # identical content: keep earliest observation
    snapshots = sorted(by_sha.values(), key=lambda e: (_ts(e["retrieved_at"]), e["source_sha256"]))
    latest = snapshots[-1]
    return {"schema_version": SCHEMA_VERSION, "source": "FOREX_FACTORY_WEEKLY", "generator": GENERATOR,
            "coverage": coverage, "coverage_basis": "SUNDAY_TO_SATURDAY_AMERICA_NEW_YORK",
            "source_sha256": latest["source_sha256"], "retrieved_at": latest["retrieved_at"],
            "first_retrieved_at": snapshots[0]["retrieved_at"], "snapshot_count": len(snapshots),
            "events": latest["events"], "snapshots": snapshots}


def import_snapshots(paths: list[Path], out_dir: Path = DEFAULT_OUT, *,
                     retrieved_at_override: dict[str, datetime] | None = None) -> dict:
    """Normalize ``paths`` into weekly files under ``out_dir``. Returns a report."""
    out_dir = Path(out_dir)
    weeks: dict[tuple[str, str], list[dict]] = {}
    errors = []
    for path in sorted({Path(p).resolve() for p in paths}):
        try:
            override = (retrieved_at_override or {}).get(str(path))
            doc = load_raw_snapshot(path, override)
        except (ValueError, KeyError, TypeError, OSError, UnicodeDecodeError) as exc:
            errors.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        weeks.setdefault(tuple(doc["coverage"]), []).append(_snapshot_entry(doc))
    written, unchanged = [], []
    for coverage, entries in sorted(weeks.items()):
        target = out_dir / f"ff-week-{coverage[0]}.json"
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
                if existing.get("schema_version") == SCHEMA_VERSION and existing.get("coverage") == list(coverage):
                    entries = list(existing.get("snapshots", [])) + entries
            except (ValueError, OSError):
                errors.append({"file": str(target), "error": "existing weekly file unreadable; rebuilt from inputs"})
        doc = week_document(list(coverage), entries)
        text = json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=True) + "\n"
        (written if _atomic_write(target, text) else unchanged).append(target.name)
    index = build_index(out_dir)
    _atomic_write(out_dir / "_index.json", json.dumps(index, sort_keys=True, indent=1) + "\n")
    return {"inputs": len(paths), "weeks_written": written, "weeks_unchanged": unchanged,
            "errors": errors, "coverage": index["weeks"]}


def build_index(out_dir: Path) -> dict:
    weeks = []
    for path in sorted(glob.glob(str(Path(out_dir) / "ff-week-*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        weeks.append({"file": Path(path).name, "coverage": doc["coverage"],
                      "snapshot_count": doc.get("snapshot_count", 1),
                      "first_retrieved_at": doc.get("first_retrieved_at", doc["retrieved_at"]),
                      "latest_retrieved_at": doc["retrieved_at"],
                      "high_impact_usd": sorted({f'{e["scheduled_at_et"]} {e["title"]}' for e in doc["events"]
                                                 if e["currency"] == "USD" and e["impact"] == "High"})})
    return {"schema_version": "mes-pilot-calendar-index-v1", "weeks": weeks}


def fetch_this_week(out_dir: Path = DEFAULT_OUT, *, opener=None, clock=None) -> Path:
    """Download this week's Forex Factory feed (LIVE USE ONLY; network).

    Saves the raw bytes as ``<out_dir>/raw/<sha256>.json`` and returns the
    path. ``opener``/``clock`` are injectable for tests.
    """
    import urllib.request  # deferred: no network machinery unless --fetch

    clock = clock or (lambda: datetime.now(UTC))
    request = urllib.request.Request(FF_THIS_WEEK_URL, headers={"User-Agent": "mes-paper-pilot-calendar/1"})
    open_fn = opener or (lambda req: urllib.request.urlopen(req, timeout=20))
    with open_fn(request) as response:
        raw = response.read()
    fetched_at = clock()
    rows = json.loads(raw.decode("utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Forex Factory feed returned no events")
    sha = hashlib.sha256(raw).hexdigest()
    raw_dir = Path(out_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f"{sha}.json"
    if not target.exists():
        target.write_bytes(raw)
    sidecar = raw_dir / f"{sha}.retrieved_at"
    if not sidecar.exists():
        sidecar.write_text(fetched_at.astimezone(UTC).isoformat() + "\n", encoding="utf-8")
    return target


def _fetched_retrieval_times(raw_dir: Path) -> dict[str, datetime]:
    out = {}
    for side in glob.glob(str(Path(raw_dir) / "*.retrieved_at")):
        raw = Path(side).with_suffix(".json")
        if raw.exists():
            out[str(raw.resolve())] = datetime.fromisoformat(Path(side).read_text(encoding="utf-8").strip())
    return out


def check_live(out_dir: Path, session_day: date, now: datetime) -> dict:
    cal = EventCalendar.load_for_live(out_dir)
    ok, detail, events = cal.coverage(session_day, now)
    return {"session_date": session_day.isoformat(), "now": now.isoformat(), "live_ready": ok,
            "detail": detail, "max_snapshot_age_days": LIVE_MAX_SNAPSHOT_AGE.days,
            "high_impact_usd": [f"{e.scheduled_at.isoformat()} {e.title}" for e in events
                                if e.currency == "USD" and e.impact == "High"],
            "load_errors": cal.load_errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", action="append", default=[], help="extra raw Forex Factory weekly JSON file")
    parser.add_argument("--no-default-inputs", action="store_true",
                        help="skip outputs/forex_factory_shadow_trial/raw/*.json")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--fetch", action="store_true",
                        help=f"LIVE USE: download {FF_THIS_WEEK_URL} (network) before importing")
    parser.add_argument("--check-live", metavar="SESSION_DATE",
                        help="report whether the live 7-day staleness rule passes for this session date")
    parser.add_argument("--now", help="ISO timestamp for --check-live (default: current UTC time)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    paths = [Path(p) for p in args.input]
    if not args.no_default_inputs:
        paths += [Path(p) for p in sorted(glob.glob(str(DEFAULT_RAW_GLOB)))]
    if args.fetch:
        paths.append(fetch_this_week(out_dir))
    raw_dir = out_dir / "raw"
    if raw_dir.exists():
        paths += [Path(p) for p in sorted(glob.glob(str(raw_dir / "*.json")))]
    report = import_snapshots(paths, out_dir, retrieved_at_override=_fetched_retrieval_times(raw_dir))
    if args.check_live:
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(UTC)
        report["live_check"] = check_live(out_dir, date.fromisoformat(args.check_live), now)
    print(json.dumps(report, indent=1, sort_keys=True, default=str))
    if report["errors"]:
        return 2
    if args.check_live and not report["live_check"]["live_ready"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
