"""Publish a deterministic five-session coverage gate for the owned simulator."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import json, os, sys, uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe
from backtesting.provider_neutral_coverage_v1 import audit_coverage, coverage_document
from backtesting.provider_neutral_market_feed_v1 import read_provider_neutral_replay

DAYS = ("2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10")


def atomic_write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    now = datetime.now(timezone.utc)
    evaluation = json.loads((ROOT / "outputs/experimental_target_five_day/latest.json").read_text(encoding="utf-8"))
    snapshot = json.loads((ROOT / "outputs/provider_neutral_paper_trial/latest.json").read_text(encoding="utf-8"))
    feed_bars = {day: {} for day in DAYS}
    for market in FuturesCanonicalMarket:
        feed = read_provider_neutral_replay(ROOT / "data/databento_recovery_staging", market=market, days=DAYS, as_of=now)
        for day in DAYS:
            feed_bars[day][market.value] = sum(1 for bar in feed.bars if bar.timeframe is CanonicalTimeframe.M1 and bar.open_time.isoformat()[:10] == day)
    signal_counts = {day: Counter() for day in DAYS}
    for market in FuturesCanonicalMarket:
        for signal in evaluation["markets"][market.value]["experimental_major_single"]["signals"]:
            day = signal["signal_time"][:10]
            if day in signal_counts:
                signal_counts[day][market.value] += 1
    completed_by_day = Counter(row["entry_time"][:10] for row in snapshot.get("journal_rows", []))
    signal_dates = {signal["signal_id"]: signal["signal_time"][:10]
                    for market in FuturesCanonicalMarket
                    for signal in evaluation["markets"][market.value]["experimental_major_single"]["signals"]}
    completed_by_signal_day = Counter(signal_dates[row["signal_id"]]
                                      for row in snapshot.get("journal_rows", []) if row["signal_id"] in signal_dates)
    rows = audit_coverage(configured_days=DAYS, feed_bars=feed_bars,
                          signal_counts={day: dict(counts) for day, counts in signal_counts.items()},
                          completed_by_day=dict(completed_by_day),
                          completed_by_signal_day=dict(completed_by_signal_day))
    document = coverage_document(evaluated_at=now.isoformat(), configured_days=DAYS, rows=rows)
    document["market_data_provider"] = "DATABENTO_HISTORICAL_REPLAY"
    document["market_data_live_connected"] = False
    atomic_write(ROOT / "outputs/provider_neutral_paper_trial/coverage.json", document)
    print(json.dumps({"schema_version": document["schema_version"], "covered_days": document["covered_days"],
                      "missing_or_unqualified_days": document["missing_or_unqualified_days"],
                      "trading_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
