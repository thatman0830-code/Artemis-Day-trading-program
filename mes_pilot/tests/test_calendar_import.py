"""scripts/import_mes_pilot_calendar.py: normalization, dedupe, idempotency,
fetch path with a fake opener (no network), live staleness check."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from mes_pilot.events import ET, EventCalendar

UTC = timezone.utc
REPO = Path(__file__).resolve().parents[2]
CAL_DIR = REPO / "data" / "mes_pilot" / "calendar"


def _load_script():
    spec = importlib.util.spec_from_file_location("import_mes_pilot_calendar",
                                                  REPO / "scripts" / "import_mes_pilot_calendar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


imp = _load_script()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import urllib.request

    def refuse(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def row(title, y, m, d, hh, mm=0, currency="USD", impact="High"):
    return {"title": title, "country": currency, "date": datetime(y, m, d, hh, mm, tzinfo=ET).isoformat(),
            "impact": impact, "forecast": "", "previous": ""}


def write_raw(path: Path, rows, mtime: datetime) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    os.utime(path, (mtime.timestamp(), mtime.timestamp()))
    return path


WEEK_A = [row("CPI m/m", 2026, 9, 11, 8, 30), row("Bank thing", 2026, 9, 6, 21, 30, "JPY", "Low")]
WEEK_A2 = WEEK_A + [row("Fed Chair Speaks", 2026, 9, 10, 14)]
WEEK_B = [row("FOMC Statement", 2026, 9, 16, 14), row("FOMC Statement", 2026, 9, 16, 14)]  # dup row


def test_import_groups_by_week_dedupes_and_is_idempotent(tmp_path):
    raw = tmp_path / "raw_in"
    t1 = datetime(2026, 9, 8, 23, 32, tzinfo=UTC)
    files = [write_raw(raw / "a1.json", WEEK_A, t1),
             write_raw(raw / "a1_copy.json", WEEK_A, t1 + timedelta(days=1)),   # identical bytes, later mtime
             write_raw(raw / "a2.json", WEEK_A2, t1 + timedelta(days=2)),
             write_raw(raw / "b.json", WEEK_B, datetime(2026, 9, 13, 16, 32, tzinfo=UTC))]
    out = tmp_path / "cal"
    report = imp.import_snapshots(files, out)
    assert report["errors"] == []
    assert sorted(report["weeks_written"]) == ["ff-week-2026-09-06.json", "ff-week-2026-09-13.json"]
    a = json.loads((out / "ff-week-2026-09-06.json").read_text(encoding="utf-8"))
    assert a["coverage"] == ["2026-09-06", "2026-09-12"] and a["snapshot_count"] == 2
    assert a["snapshots"][0]["retrieved_at"] == t1.isoformat()           # earliest observation kept
    assert a["snapshots"][0]["source_sha256"] == hashlib.sha256((raw / "a1.json").read_bytes()).hexdigest()
    assert a["source_sha256"] == a["snapshots"][-1]["source_sha256"]     # top level mirrors the latest
    assert {e["title"] for e in a["events"]} == {"CPI m/m", "Bank thing", "Fed Chair Speaks"}
    assert a["snapshots"][0]["retrieved_at_basis"] == "FILE_MTIME"
    b = json.loads((out / "ff-week-2026-09-13.json").read_text(encoding="utf-8"))
    assert len(b["events"]) == 1                                         # duplicate row removed
    before = {p.name: p.read_bytes() for p in out.glob("*.json")}
    again = imp.import_snapshots(files, out)
    assert again["weeks_written"] == [] and len(again["weeks_unchanged"]) == 2
    assert {p.name: p.read_bytes() for p in out.glob("*.json")} == before
    # importing only one file later keeps the previously merged snapshots
    imp.import_snapshots([files[0]], out)
    assert json.loads((out / "ff-week-2026-09-06.json").read_text(encoding="utf-8"))["snapshot_count"] == 2
    cal = EventCalendar.load_dir(out)
    assert date(2026, 9, 9) in cal.covered_days and date(2026, 9, 19) in cal.covered_days


def test_import_reports_invalid_inputs(tmp_path):
    bad = write_raw(tmp_path / "bad.json", {"not": "a list"}, datetime(2026, 9, 8, tzinfo=UTC))
    multi = write_raw(tmp_path / "multi.json", WEEK_A + WEEK_B, datetime(2026, 9, 8, tzinfo=UTC))
    report = imp.import_snapshots([bad, multi], tmp_path / "cal")
    assert len(report["errors"]) == 2 and report["weeks_written"] == []
    assert imp.main(["--no-default-inputs", "--input", str(bad), "--out-dir", str(tmp_path / "cal")]) == 2


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_uses_injected_opener_and_records_fetch_clock(tmp_path):
    out = tmp_path / "cal"
    seen = []
    fetched_at = datetime(2026, 9, 27, 22, 0, tzinfo=UTC)

    def opener(request):
        seen.append(request.full_url)
        return FakeResponse(json.dumps(WEEK_A2).encode())

    path = imp.fetch_this_week(out, opener=opener, clock=lambda: fetched_at)
    assert seen == [imp.FF_THIS_WEEK_URL]
    assert path.parent == out / "raw" and path.with_suffix(".retrieved_at").exists()
    os.utime(path, (0, 0))  # mtime must not be used for fetched files
    assert imp.main(["--no-default-inputs", "--out-dir", str(out)]) == 0
    doc = json.loads((out / "ff-week-2026-09-06.json").read_text(encoding="utf-8"))
    assert doc["retrieved_at"] == fetched_at.isoformat()
    assert doc["snapshots"][0]["retrieved_at_basis"] == "FETCH_CLOCK"


def test_check_live_staleness_rule(tmp_path):
    out = tmp_path / "cal"
    write_raw(tmp_path / "w.json", WEEK_A, datetime(2026, 9, 6, 22, 0, tzinfo=UTC))
    imp.import_snapshots([tmp_path / "w.json"], out)
    ok = imp.check_live(out, date(2026, 9, 11), datetime(2026, 9, 11, 13, 0, tzinfo=UTC))
    assert ok["live_ready"] and ok["high_impact_usd"]
    stale = imp.check_live(out, date(2026, 9, 11), datetime(2026, 9, 13, 22, 0, 1, tzinfo=UTC))
    assert not stale["live_ready"] and stale["detail"] == "STALE_SNAPSHOT"
    missing = imp.check_live(out, date(2026, 9, 14), datetime(2026, 9, 14, 13, 0, tzinfo=UTC))
    assert not missing["live_ready"] and missing["detail"] == "NO_COVERAGE"
    rc = imp.main(["--no-default-inputs", "--out-dir", str(out), "--check-live", "2026-09-14",
                   "--now", "2026-09-14T13:00:00+00:00"])
    assert rc == 3


@pytest.mark.skipif(not (CAL_DIR / "_index.json").exists(), reason="imported calendar not present")
def test_generated_calendar_weeks():
    index = json.loads((CAL_DIR / "_index.json").read_text(encoding="utf-8"))
    coverage = [tuple(w["coverage"]) for w in index["weeks"]]
    assert coverage[:4] == [("2026-09-06", "2026-09-12"), ("2026-09-13", "2026-09-19"),
                            ("2026-09-20", "2026-09-26"), ("2026-09-27", "2026-10-03")]
