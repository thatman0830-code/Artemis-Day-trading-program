"""Resolve archived experimental signals without touching canonical trade history."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import os
import uuid

from backtesting.databento_research_dataset_v1 import read_databento_research_days
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe
from backtesting.ninjatrader_canonical_smoke_v1 import NinjaTraderCanonicalSmokeV1
from backtesting.ninjatrader_signal_lifecycle_v1 import resolve_signal_lifecycle
from backtesting.ninjatrader_three_profile_shadow_ledger_v1 import build_three_profile_shadow_ledgers

DAYS = ("2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10")


def clean(value):
    if isinstance(value, Decimal): return format(value, "f")
    if isinstance(value, Enum): return value.value
    if hasattr(value, "isoformat"): return value.isoformat()
    if isinstance(value, tuple): return [clean(x) for x in value]
    if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
    return value


def report(market, evidence, signal, now):
    body = json.dumps(signal, sort_keys=True, separators=(",", ":")).encode()
    identity = sha256(body).hexdigest()
    return NinjaTraderCanonicalSmokeV1(identity, market, evidence.instrument, now,
        evidence.dataset.dataset_id, evidence.dataset.fingerprint,
        evidence.chain_head_sha256, "0" * 64, Decimal("0.25"), "0" * 64,
        "1" * 64, "2" * 64, evidence.record_count, evidence.record_count, (),
        "EXPERIMENTAL_SHADOW_SIGNAL", identity, True, signal["signal_id"],
        signal["side"], datetime.fromisoformat(signal["signal_time"]),
        Decimal(signal["entry_price"]), Decimal(signal["stop_price"]),
        Decimal(signal["target_price"]))


def atomic_write(target, document):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x") as stream:
            json.dump(document, stream, sort_keys=True, separators=(",", ":"))
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    now = datetime.now(timezone.utc)
    evaluation = json.loads((ROOT / "outputs/experimental_target_five_day/latest.json").read_text())
    if (evaluation.get("schema_version") != "experimental-target-five-day-evaluation-v1"
            or evaluation.get("trading_authority") is not False):
        raise ValueError("verified non-authoritative target evaluation required")
    outcomes = Counter(); completed = []; market_results = {}
    for market in FuturesCanonicalMarket:
        evidence = read_databento_research_days(ROOT / "data/databento_recovery_staging",
            market=market, days=DAYS, as_of=now)
        bars = tuple(x for x in evidence.dataset.candles if x.timeframe is CanonicalTimeframe.M1)
        signals = evaluation["markets"][market.value]["experimental_major_single"]["signals"]
        rows = []
        for signal in signals:
            result = resolve_signal_lifecycle(report=report(market, evidence, signal, now),
                                              bars=bars, max_holding_bars=30)
            outcomes[result.outcome.value] += 1
            if result.completed_trade is not None:
                completed.append(result.completed_trade)
            rows.append({"signal_id": signal["signal_id"], "outcome": result.outcome.value,
                         "bars_examined": result.bars_examined,
                         "ambiguous_bar_resolved_stop_first": result.ambiguous_bar_resolved_stop_first})
        market_results[market.value] = rows
    trades = tuple(sorted(completed, key=lambda x: (x.exit_time, x.signal_id)))
    ledgers = build_three_profile_shadow_ledgers(trades=trades, evaluated_at=now)
    document = {"schema_version": "experimental-target-five-day-lifecycle-v1",
        "state": "COMPLETE", "evaluated_at": now.isoformat(),
        "input_signal_count": sum(len(x) for x in market_results.values()),
        "completed_trade_count": len(trades), "outcome_counts": dict(sorted(outcomes.items())),
        "markets": market_results, "ledgers": [clean(asdict(x)) for x in ledgers],
        "canonical_history_modified": False, "comparison_only": True,
        "paper_execution_permitted": False, "live_trading_permitted": False,
        "trading_authority": False}
    atomic_write(ROOT / "outputs/experimental_target_five_day/lifecycle.json", document)
    print(json.dumps({k: document[k] for k in ("schema_version", "input_signal_count",
        "completed_trade_count", "outcome_counts", "paper_execution_permitted",
        "trading_authority")}, sort_keys=True))


if __name__ == "__main__":
    main()
