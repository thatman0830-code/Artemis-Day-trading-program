"""Bounded, read-only historical context bridge for the MES paper runner (repair 2026-10-02).

Layers, oldest first, each kept separately labelled (provenance never erased):

1. ``ES_ARCHIVE_PROXY``  local ES 1-minute archive (deep warmup, 60-session volatility
   history). ES and MES track the same index; over 210 overlapping minutes on
   2026-10-01 the close differed by median 0 and at most 2 ticks. Missing archive
   minutes count as known zero-volume ONLY where the file manifest's declared
   ``missing_aggregate_minutes`` exactly equals the minutes missing from that file.
2. ``MES_HISTORICAL``    native MES (``MES.c.0`` -> raw contract) from the Databento
   Historical API for the most recent ``native_sessions`` trading sessions through the
   provider's available end. Downloaded ONLY after ``metadata.get_cost`` returns
   exactly 0.0; otherwise the layer is skipped with ``HISTORICAL_COST_NONZERO`` and the
   resulting hole stays visible. Missing minutes inside a historical response are NOT
   certified (an empty response is not proof of zero trades).
3. live intraday replay from the last context bar end (``live_feed``), which joins
   the moving live edge in the same ordered stream.

All three are fed to the engine before any decision. Layers 1-2 run in engine
warmup (no decisions, no session records, no persisted risk roll). Nothing beyond
the fetch time is accepted; identical overlaps are dropped and conflicting
duplicates rejected and reported.
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from mes_pilot.bars import Bar, load_archive_sessions, session_date_for
from mes_pilot.coverage import open_minute_starts, previous_trading_date, session_bounds

UTC = timezone.utc
ONE_MIN = timedelta(minutes=1)
DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1m"
SYMBOL = "MES.c.0"
STYPE_IN = "continuous"
KEY_ENV = "DATABENTO_API_KEY"
_ENTITLEMENT = re.compile(r"entitle|license|licence|permission|not authori|subscription|403|401|auth", re.I)
_KEY = re.compile(r"db-[A-Za-z0-9]{6,}")


def _redact(text: str) -> str:
    return _KEY.sub("db-***", text)


@dataclass
class HistoryFetch:
    status: str                      # OK | EMPTY | HISTORICAL_COST_NONZERO | ENTITLEMENT_DENIED | ERROR | SKIPPED
    bars: list = field(default_factory=list)
    requested_start: datetime | None = None
    requested_end: datetime | None = None
    effective_start: datetime | None = None
    effective_end: datetime | None = None
    received_first: datetime | None = None
    received_last_end: datetime | None = None
    cost_usd: float | None = None
    contracts: list = field(default_factory=list)
    duplicates_dropped: int = 0
    conflicts: list = field(default_factory=list)
    future_bars_dropped: int = 0
    clamps: list = field(default_factory=list)
    message: str | None = None
    provenance: dict = field(default_factory=dict)

    def summary(self) -> dict:
        iso = lambda t: t.isoformat() if isinstance(t, datetime) else t  # noqa: E731
        return {"status": self.status, "bars": len(self.bars), "requested": [iso(self.requested_start), iso(self.requested_end)],
                "effective": [iso(self.effective_start), iso(self.effective_end)],
                "received": [iso(self.received_first), iso(self.received_last_end)], "cost_usd": self.cost_usd,
                "contracts": self.contracts, "duplicates_dropped": self.duplicates_dropped,
                "conflicts": self.conflicts[:20], "conflict_count": len(self.conflicts),
                "future_bars_dropped": self.future_bars_dropped, "clamps": self.clamps,
                "message": self.message, "provenance": self.provenance}


def _px(v) -> float:
    return float(v) / 1e9 if isinstance(v, int) else float(v)


def _historical_client(key: str):
    import databento as db  # lazy
    return db.Historical(key=key)


def _available_end(client) -> datetime | None:
    rng = client.metadata.get_dataset_range(dataset=DATASET)
    try:
        raw = rng["schema"][SCHEMA]["end"]
    except (KeyError, TypeError):
        raw = rng.get("end") if isinstance(rng, dict) else None
    return _parse_ts(raw) if raw is not None else None


def _parse_ts(raw) -> datetime:
    s = str(raw).strip().replace("Z", "")
    if "+" in s[10:]:
        s = s[:s.index("+", 10)]
    if "." in s:
        head, frac = s.split(".", 1)
        s = head + "." + frac[:6]
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def fetch_mes_history(start: datetime, end: datetime, *, client_factory: Callable[[str], object] | None = None,
                      key_provider: Callable[[], str | None] | None = None,
                      clock: Callable[[], datetime] | None = None,
                      max_span: timedelta = timedelta(days=9)) -> HistoryFetch:
    """Read-only Historical fetch of MES.c.0 ohlcv-1m in [start, end), guarded by a zero-cost check."""
    clock = clock or (lambda: datetime.now(UTC))
    key_provider = key_provider or (lambda: os.environ.get(KEY_ENV))
    client_factory = client_factory or _historical_client
    out = HistoryFetch("ERROR", requested_start=start, requested_end=end)
    now = clock()
    out.provenance = {"dataset": DATASET, "schema": SCHEMA, "symbol": SYMBOL, "stype_in": STYPE_IN,
                      "fetched_at_utc": now.isoformat(), "source": "MES_HISTORICAL"}
    try:
        import databento as _db  # noqa: F401
        out.provenance["databento_version"] = getattr(_db, "__version__", None)
    except ImportError:
        out.provenance["databento_version"] = None
    if end - start > max_span:
        out.clamps.append({"kind": "MAX_SPAN", "from": start.isoformat(), "to": (end - max_span).isoformat()})
        start = end - max_span
    key = key_provider()
    if not key:
        out.status, out.message = "ERROR", f"{KEY_ENV} is not configured"
        return out
    try:
        client = client_factory(key)
    finally:
        del key
    try:
        avail = _available_end(client)
        eff_end = min(t for t in (end, avail, now) if t is not None)
        if eff_end < end:
            out.clamps.append({"kind": "AVAILABLE_OR_CLOCK_END", "requested_end": end.isoformat(),
                               "effective_end": eff_end.isoformat(),
                               "provider_available_end": avail.isoformat() if avail else None})
        eff_end = eff_end.replace(second=0, microsecond=0)
        out.effective_start, out.effective_end = start, eff_end
        if eff_end <= start:
            out.status, out.message = "EMPTY", "nothing available in range"
            return out
        cost = client.metadata.get_cost(dataset=DATASET, symbols=[SYMBOL], stype_in=STYPE_IN, schema=SCHEMA,
                                        start=start.isoformat(), end=eff_end.isoformat())
        out.cost_usd = float(cost)
        if out.cost_usd != 0.0:
            out.status, out.message = "HISTORICAL_COST_NONZERO", f"provider quoted ${out.cost_usd}; not downloaded"
            return out
        # Provider symbology (free): continuous -> instrument_id -> raw contract. Never fabricated; an
        # unresolved id keeps the continuous label, which the engine treats as a different series (reset).
        iid_to_raw: dict = {}
        try:
            d0, d1 = start.date().isoformat(), (eff_end.date() + timedelta(days=1)).isoformat()
            r1 = client.symbology.resolve(dataset=DATASET, symbols=[SYMBOL], stype_in=STYPE_IN,
                                          stype_out="instrument_id", start_date=d0, end_date=d1)
            ids = sorted({str(m.get("s")) for m in (r1 or {}).get("result", {}).get(SYMBOL, []) if m.get("s")})
            if ids:
                r2 = client.symbology.resolve(dataset=DATASET, symbols=ids, stype_in="instrument_id",
                                              stype_out="raw_symbol", start_date=d0, end_date=d1)
                for iid, rows in (r2 or {}).get("result", {}).items():
                    raws = {str(m.get("s")) for m in rows if m.get("s")}
                    if len(raws) == 1:
                        iid_to_raw[int(iid)] = raws.pop()
            out.provenance["symbology"] = {"continuous_to_instrument_ids": ids,
                                           "instrument_id_to_raw": {str(k): v for k, v in iid_to_raw.items()}}
        except Exception as exc:
            out.provenance["symbology_error"] = _redact(f"{type(exc).__name__}: {exc}")
        out.contracts = sorted(set(iid_to_raw.values()))
        store = client.timeseries.get_range(dataset=DATASET, schema=SCHEMA, symbols=[SYMBOL], stype_in=STYPE_IN,
                                            start=start.isoformat(), end=eff_end.isoformat())
        unmapped = 0
        seen: dict = {}
        for rec in store:
            if type(rec).__name__ != "OHLCVMsg":
                continue
            ts = datetime.fromtimestamp(int(rec.ts_event) / 1e9, UTC)
            b = Bar(ts, ts + ONE_MIN, _px(rec.open), _px(rec.high), _px(rec.low), _px(rec.close),
                    float(getattr(rec, "volume", 0)), iid_to_raw.get(int(getattr(rec, "instrument_id", -1)), SYMBOL), 1)
            if b.contract == SYMBOL:
                unmapped += 1
            if b.end > eff_end or b.end > now:
                out.future_bars_dropped += 1
                continue
            key_v = (b.open, b.high, b.low, b.close, b.volume)
            if b.start in seen:
                if seen[b.start][0] == key_v:
                    out.duplicates_dropped += 1
                else:
                    out.conflicts.append({"start": b.start.isoformat(), "kept": list(seen[b.start][0]),
                                          "rejected": list(key_v)})
                continue
            seen[b.start] = (key_v, b)
        out.bars = [seen[k][1] for k in sorted(seen)]
        out.provenance["unmapped_bars"] = unmapped
        if out.bars:
            out.received_first, out.received_last_end = out.bars[0].start, out.bars[-1].end
            out.status = "OK"
        else:
            out.status = "EMPTY"
        return out
    except Exception as exc:
        text = _redact(f"{type(exc).__name__}: {exc}")
        out.status = "ENTITLEMENT_DENIED" if _ENTITLEMENT.search(text) else "ERROR"
        out.message = text[:500]
        return out


# --------------------------------------------------------------------------- archive layer
def archive_zero_volume_evidence(roots: list[Path], session_dates: set) -> dict:
    """Minute starts certified zero-volume by archive manifests (exact-count rule) + per-file audit."""
    evidence: dict = {}
    audit = []
    for root in roots:
        for mpath in sorted(glob.glob(str(Path(root) / "manifests" / "*.json"))):
            try:
                man = json.loads(Path(mpath).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rel = man.get("normalized_relative_path")
            if not rel or man.get("http_status") != 200:
                continue
            npath = Path(root) / rel
            if not npath.exists():
                continue
            starts, days = set(), set()
            for line in npath.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                days.add(row["session_date"])
                starts.add(datetime.fromtimestamp(int(row["window_start_ns"]) / 1e9, UTC))
            if not (days & session_dates):
                continue
            missing = []
            for d in sorted(days):
                s, e = session_bounds(date.fromisoformat(d))
                missing.extend(m for m in open_minute_starts(s, e) if m not in starts)
            declared = man.get("missing_aggregate_minutes")
            ok = declared is not None and int(declared) == len(missing) and \
                str(man.get("missing_semantics", "")).startswith("ZERO_OBSERVED")
            audit.append({"manifest": Path(mpath).name, "sessions": sorted(days), "declared_missing": declared,
                          "computed_missing": len(missing), "accepted": ok})
            if ok:
                for m in missing:
                    evidence[m] = "ARCHIVE_MANIFEST_ZERO_VOLUME"
    return {"minutes": evidence, "audit": audit}


def trading_date_n_back(day: date, n: int) -> date:
    d = day
    for _ in range(n):
        d = previous_trading_date(d)
    return d


def build_context(target, *, cfg, archives: list[Path], now: datetime, native_sessions: int = 5,
                  fetch: Callable[..., HistoryFetch] = fetch_mes_history, log: Callable[[str], None] = print) -> dict:
    """Warm ``target`` (engine or PortfolioGroup) from archive + native MES history; return provenance.

    The caller then runs the live feed with ``replay_start = result['last_context_bar_end']``.
    """
    sp = cfg.splits
    today = session_date_for(now)
    native_from_day = trading_date_n_back(today, native_sessions)
    native_start = session_bounds(native_from_day)[0]          # 18:00 ET before that trade date
    all_sessions = [s for s in load_archive_sessions(archives, start=today - timedelta(days=400))
                    if not (sp.protected_oos[0] <= s.session_date <= sp.protected_oos[1])
                    and s.bars and s.bars[-1].end <= now]      # never future-dated archive input
    deep = [s for s in all_sessions if s.session_date < native_from_day]
    # +2 margin: the volatility band needs volatility_sessions COMPLETED sessions before today.
    deep = deep[-max(1, cfg.strategy.volatility_sessions - native_sessions + 2):]
    fetched = fetch(native_start, now)
    fallback = None
    if fetched.status != "OK":
        # Native layer unavailable: fall back to every archive session (ES proxy) up to the archive end.
        fallback = [s for s in all_sessions if s.session_date >= native_from_day]
        log(f"[bridge] MES historical layer {fetched.status}: {fetched.message}; falling back to ES archive")
    used = deep + (fallback or [])
    ev = archive_zero_volume_evidence(archives, {s.session_date.isoformat() for s in used})
    attest = getattr(target, "attest_zero_trade", None)
    target.start_warmup() if hasattr(target, "start_warmup") else setattr(target, "warmup", True)
    for s in used:
        if callable(attest):
            for m in sorted(m for m in ev["minutes"] if session_date_for(m) == s.session_date):
                attest(m, ev["minutes"][m])
        for bar in s.bars:
            target.process_bar(bar, None, continuity="ARCHIVE_SESSION", source="ES_ARCHIVE_PROXY")
    if fetched.status == "OK":
        for bar in fetched.bars:
            target.process_bar(bar, None, continuity="HISTORICAL_RANGE", source="MES_HISTORICAL")
    last_end = _last_bar_end(target)
    coverage = _coverage_dict(target)
    target.end_warmup()
    return {"schema": "mes-context-bridge-v1", "now": now.isoformat(), "session_day": today.isoformat(),
            "archive_sessions_used": [s.session_date.isoformat() for s in used],
            "archive_contracts": sorted({s.contract for s in used}),
            "archive_last_bar_end": used[-1].bars[-1].end.isoformat() if used else None,
            "archive_manifest_audit": ev["audit"][-20:],
            "archive_zero_volume_minutes_certified": len(ev["minutes"]),
            "native_from_trade_date": native_from_day.isoformat(), "native_start": native_start.isoformat(),
            "mes_historical": fetched.summary(), "fallback_to_archive": fallback is not None,
            "last_context_bar_end": last_end.isoformat() if last_end else None,
            "coverage_at_warmup_end": coverage}


def _last_bar_end(target):
    engines = getattr(target, "engines", None)
    eng = next(iter(engines.values())) if engines else target
    return eng.last_bar.end if eng.last_bar else None


def _coverage_dict(target):
    engines = getattr(target, "engines", None)
    eng = next(iter(engines.values())) if engines else target
    cov = getattr(eng, "coverage", None)
    return cov.to_dict() if cov is not None else None
