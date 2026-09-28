"""Resolve retained canonical signals and refresh the three-profile comparison."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import os
import uuid

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_history_v1 import read_ninjatrader_canonical_smoke_history
from backtesting.ninjatrader_canonical_smoke_v1 import NinjaTraderCanonicalSmokeV1
from backtesting.ninjatrader_closed_bar_dataset_v1 import read_closed_bar_dataset
from backtesting.ninjatrader_completed_trade_history_v1 import append_completed_shadow_trade, read_completed_shadow_trade_history
from backtesting.ninjatrader_shadow_profile_comparison_v1 import compare_shadow_profiles
from backtesting.ninjatrader_signal_lifecycle_v1 import LifecycleOutcome, resolve_signal_lifecycle


def _report(value):
    fields = NinjaTraderCanonicalSmokeV1.__dataclass_fields__
    data = {key: value[key] for key in fields if key in value}
    data["market"] = FuturesCanonicalMarket(data["market"])
    data["evaluated_at"] = datetime.fromisoformat(data["evaluated_at"].replace("Z", "+00:00"))
    data["minimum_tick"] = Decimal(data["minimum_tick"])
    data["outcome_counts"] = tuple(tuple(item) for item in data["outcome_counts"])
    if data.get("signal_time") is not None:
        data["signal_time"] = datetime.fromisoformat(data["signal_time"].replace("Z", "+00:00"))
    for name in ("entry_price", "stop_price", "target_price"):
        if data.get(name) is not None:
            data[name] = Decimal(data[name])
    return NinjaTraderCanonicalSmokeV1(**data)


def _clean(value):
    if isinstance(value, Decimal): return format(value, "f")
    if isinstance(value, Enum): return value.value
    if hasattr(value, "isoformat"): return value.isoformat()
    if isinstance(value, tuple): return [_clean(item) for item in value]
    if isinstance(value, dict): return {key: _clean(item) for key, item in value.items()}
    return value


def _write(target, document):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x") as stream:
            json.dump(document, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    now = datetime.now(timezone.utc)
    history_root = ROOT / "outputs/ninjatrader_canonical_smoke_history"
    trade_root = ROOT / "outputs/ninjatrader_completed_shadow_trades"
    outcome_counts = {outcome.value: 0 for outcome in LifecycleOutcome}
    qualified_signal_count = 0
    evidence_rejections = []
    for market in FuturesCanonicalMarket:
        events = read_ninjatrader_canonical_smoke_history(history_root, market=market)
        for event in events:
            report = _report(event.report)
            if report.qualified_signal_id is None:
                continue
            qualified_signal_count += 1
            try:
                evidence = read_closed_bar_dataset(ROOT / "data/ninjatrader_closed_bars", market=market, day=report.signal_time.date().isoformat(), as_of=now)
                result = resolve_signal_lifecycle(report=report, bars=evidence.dataset.candles)
            except ValueError as exc:
                evidence_rejections.append({"market": market.value, "report_id": report.report_id, "failure_type": type(exc).__name__})
                continue
            outcome_counts[result.outcome.value] += 1
            if result.completed_trade is not None:
                append_completed_shadow_trade(trade_root, trade=result.completed_trade)
    trades = read_completed_shadow_trade_history(trade_root)
    comparison = compare_shadow_profiles(trades=trades, evaluated_at=now)
    _write(ROOT / "outputs/ninjatrader_shadow_profile_comparison/latest.json", _clean(asdict(comparison)))
    state = "EVIDENCE_REJECTED" if evidence_rejections else "COMPLETE"
    cycle = {
        "schema_version": "ninjatrader-completed-lifecycle-cycle-v1", "state": state,
        "observed_at": now.isoformat(), "qualified_signal_count": qualified_signal_count,
        "outcome_counts": outcome_counts, "evidence_rejection_count": len(evidence_rejections),
        "evidence_rejections": evidence_rejections, "retained_completed_trades": len(trades),
        "selection_state": comparison.selection_state.value,
        "candidate_profile": None if comparison.candidate_profile is None else comparison.candidate_profile.value,
        "paper_execution_permitted": False, "trading_authority": False,
    }
    _write(ROOT / "outputs/operational_health/ninjatrader-signal-lifecycle-status.json", cycle)
    print(json.dumps(cycle, sort_keys=True, separators=(",", ":")))
    return 2 if evidence_rejections else 0


if __name__ == "__main__":
    raise SystemExit(main())
