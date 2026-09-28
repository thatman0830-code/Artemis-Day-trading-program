"""Run the owned 15-session simulator on a verified replay feed."""
from pathlib import Path
import json, os, sys, uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.provider_neutral_market_feed_v1 import read_provider_neutral_replay
from backtesting.provider_neutral_paper_trial_v1 import build_provider_neutral_trial, snapshot_document
from backtesting.market_data import CanonicalTimeframe
from backtesting.ninjatrader_canonical_smoke_v1 import NinjaTraderCanonicalSmokeV1
from backtesting.ninjatrader_signal_lifecycle_v1 import resolve_signal_lifecycle

DAYS = ("2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10")


def clean(value):
    if isinstance(value, Decimal): return format(value, "f")
    if isinstance(value, Enum): return value.value
    if hasattr(value, "isoformat"): return value.isoformat()
    if isinstance(value, tuple): return [clean(item) for item in value]
    if isinstance(value, dict): return {key: clean(item) for key, item in value.items()}
    return value


def atomic_write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def as_report(market, feed, signal, now):
    identity = str(signal["signal_id"])
    return NinjaTraderCanonicalSmokeV1(identity, market, feed.market.value, now,
        feed.dataset_id, feed.fingerprint, feed.source_sha256, "0" * 64,
        Decimal("0.25"), "0" * 64, "1" * 64, "2" * 64, len(feed.bars),
        len(feed.bars), (), "PROVIDER_NEUTRAL_REPLAY", identity, True,
        signal["signal_id"], signal["side"], datetime.fromisoformat(signal["signal_time"]),
        Decimal(signal["entry_price"]), Decimal(signal["stop_price"]), Decimal(signal["target_price"]))


def main():
    now = datetime.now(timezone.utc)
    evaluation = json.loads((ROOT / "outputs/experimental_target_five_day/latest.json").read_text(encoding="utf-8"))
    if evaluation.get("trading_authority") is not False or evaluation.get("comparison_only") is not True:
        raise ValueError("non-authoritative evaluation required")
    completed = []; outcomes = Counter(); feeds = {}; resolutions = {}
    for market in FuturesCanonicalMarket:
        feed = read_provider_neutral_replay(ROOT / "data/databento_recovery_staging",
            market=market, days=DAYS, as_of=now)
        feeds[market.value] = {"days": list(DAYS), "dataset_id": feed.dataset_id,
            "fingerprint": feed.fingerprint, "source_sha256": feed.source_sha256,
            "bar_count": len(feed.bars), "live": False, "trading_authority": False}
        bars = tuple(x for x in feed.bars if x.timeframe is CanonicalTimeframe.M1)
        rows = []
        for signal in evaluation["markets"][market.value]["experimental_major_single"]["signals"]:
            result = resolve_signal_lifecycle(report=as_report(market, feed, signal, now),
                                              bars=bars, max_holding_bars=30)
            outcomes[result.outcome.value] += 1
            if result.completed_trade is not None: completed.append(result.completed_trade)
            rows.append({"signal_id": signal["signal_id"], "outcome": result.outcome.value,
                "resolution_id": result.resolution_id, "bars_examined": result.bars_examined})
        resolutions[market.value] = rows
    snapshot = build_provider_neutral_trial(trades=tuple(sorted(completed, key=lambda x: (x.exit_time, x.signal_id))), evaluated_at=now)
    document = snapshot_document(snapshot)
    document.update({"market_data_provider": "DATABENTO_HISTORICAL_REPLAY", "market_data_live_connected": False,
        "market_data_days": list(DAYS), "feeds": feeds, "lifecycle_outcomes": dict(sorted(outcomes.items())),
        "resolutions": resolutions, "completed_trade_count": len(completed),
        "paper_execution_permitted": False, "trading_authority": False})
    atomic_write(ROOT / "outputs/provider_neutral_paper_trial/latest.json", document)
    atomic_write(ROOT / "outputs/provider_neutral_paper_trial/trades.jsonl", {
        "schema_version": "provider-neutral-paper-trade-journal-v1",
        "comparison_only": True,
        "rows": document["journal_rows"],
        "market_data_provider": "DATABENTO_HISTORICAL_REPLAY",
        "trading_authority": False,
    })
    print(json.dumps({"schema_version": document["schema_version"], "completed_sessions": document["completed_sessions"],
        "completed_trade_count": len(completed), "outcome_counts": document["lifecycle_outcomes"],
        "market_data_live_connected": False, "paper_execution_permitted": False,
        "trading_authority": False}, sort_keys=True))


if __name__ == "__main__": main()
