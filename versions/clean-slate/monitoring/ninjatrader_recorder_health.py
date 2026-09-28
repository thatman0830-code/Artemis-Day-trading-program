"""Read-only health evidence for the active NinjaTrader MES/MNQ recorder."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from execution.ninjatrader_closed_bar_recorder_v1 import _chain
from futures_data.sessions import IntervalClassification, SessionCalendar


def evaluate(*, archive_root: Path, bridge_root: Path, as_of: datetime) -> dict:
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("UTC as_of required")
    rows, hashes = [], []
    for market, bridge_name in (("ES", "MES.bar.json"), ("NQ", "MNQ.bar.json")):
        manifest_path = archive_root / market / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        chain_path = archive_root / market / manifest["archive_file"]
        head, last, count, gaps, scheduled = _chain(chain_path)
        bridge_path = bridge_root / bridge_name
        bridge = json.loads(bridge_path.read_text(encoding="utf-8-sig"))
        close = datetime.fromisoformat(bridge["close_time_utc"].replace("Z", "+00:00"))
        classification = SessionCalendar().classify(as_of - timedelta(minutes=1))
        age = (as_of - close).total_seconds()
        if (manifest.get("state") != "RECORDING" or manifest.get("trading_authority") is not False
                or bridge.get("trading_authority") is not False or bridge.get("is_closed") is not True
                or head != manifest.get("head_record_sha256") or count != manifest.get("record_count")
                or gaps != manifest.get("unresolved_gap_count")
                or scheduled != manifest.get("scheduled_non_trading_minute_count")
                or last is None or last != close):
            raise ValueError(f"{market} recorder integrity rejected")
        if classification is IntervalClassification.OPEN and (age < 0 or age > 120):
            raise ValueError(f"{market} live bridge is stale during open session")
        for path in (manifest_path, chain_path, bridge_path):
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        rows.append({"market": market, "latest_close_utc": close.isoformat(),
                     "age_seconds": round(age, 3), "record_count": count,
                     "unresolved_gap_count": gaps,
                     "scheduled_non_trading_minute_count": scheduled})
    if rows[0]["latest_close_utc"] != rows[1]["latest_close_utc"]:
        raise ValueError("MES/MNQ bridges are not synchronized")
    classification = SessionCalendar().classify(as_of - timedelta(minutes=1))
    return {"schema_version": "ninjatrader-recorder-health-v1", "state": "HEALTHY",
            "observed_at": as_of.isoformat(), "session_classification": classification.value,
            "operational_heartbeat_at": as_of.isoformat(), "markets": rows,
            "source_file_sha256": sorted(set(hashes)),
            "unresolved_gap_count": max(row["unresolved_gap_count"] for row in rows),
            "trading_authority": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--bridge-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(archive_root=args.archive_root, bridge_root=args.bridge_root,
                              as_of=datetime.now(timezone.utc)), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
