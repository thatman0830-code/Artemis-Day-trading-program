"""Validate exported recovery bars without modifying the immutable live archive."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))

import argparse, hashlib, json, os, uuid
from datetime import datetime, timezone
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_historical_export_v1 import read_ninjatrader_historical_export


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x") as stream: json.dump(value, stream, sort_keys=True, separators=(",", ":")); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally: temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--mes", required=True); parser.add_argument("--mnq", required=True)
    parser.add_argument("--start", default="2026-09-08T13:34:00+00:00"); parser.add_argument("--end", default="2026-09-08T14:23:00+00:00"); args = parser.parse_args()
    now = datetime.now(timezone.utc); results = []
    start = datetime.fromisoformat(args.start); end = datetime.fromisoformat(args.end)
    if start.utcoffset() != timezone.utc.utcoffset(start) or end.utcoffset() != timezone.utc.utcoffset(end) or start > end:
        raise ValueError("ordered UTC recovery interval required")
    expected_count = int((end - start).total_seconds() // 60) + 1
    required = {start.timestamp() + 60 * index for index in range(expected_count)}
    for market, source in ((FuturesCanonicalMarket.ES, args.mes), (FuturesCanonicalMarket.NQ, args.mnq)):
        export = read_ninjatrader_historical_export(source, market=market, as_of=now, start_at=start, end_at=end)
        closes = {bar.close_time.timestamp() for bar in export.dataset.candles}
        if not required.issubset(closes): raise ValueError(f"{market.value} export does not cover exact recovery interval")
        results.append({"market": market.value, "source_sha256": export.source_sha256, "record_count": export.record_count, "earliest_close_utc": export.earliest_close_utc.isoformat(), "latest_close_utc": export.latest_close_utc.isoformat(), "missing_interval_bars_present": expected_count, "historical_replay_eligible": True, "immutable_archive_repair_eligible": False})
    report = {"schema_version": "ninjatrader-gap-recovery-export-validation-v1", "state": "INDEPENDENT_REPLAY_ELIGIBLE", "reason": "export overlap differs from immutable live recorder; direct splice prohibited", "exports": results, "paper_execution_permitted": False, "trading_authority": False}
    report["report_id"] = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    atomic_write(ROOT / "outputs/ninjatrader_gap_recovery/latest.json", report); print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__": raise SystemExit(main())
