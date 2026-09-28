"""Descriptive failure attribution for the five-day major-single target lane."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import statistics
import uuid
from zoneinfo import ZoneInfo

from backtesting.databento_research_dataset_v1 import read_databento_research_days
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe

DAYS = ("2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10")
WINDOWS = (30, 60, 120)


def decimal_median(values):
    return Decimal(str(statistics.median(values))) if values else Decimal("0")


def outcome(side, stop, target, bars):
    for index, bar in enumerate(bars, 1):
        stop_hit = bar.low <= stop if side == "LONG" else bar.high >= stop
        target_hit = bar.high >= target if side == "LONG" else bar.low <= target
        if stop_hit:
            return "STOP", index, target_hit
        if target_hit:
            return "TARGET", index, False
    return "UNRESOLVED", len(bars), False


def analyze_signal(signal, bars):
    side = signal["side"]
    at = datetime.fromisoformat(signal["signal_time"])
    entry = Decimal(signal["entry_price"]); stop = Decimal(signal["stop_price"])
    target = Decimal(signal["target_price"])
    relevant = tuple(x for x in bars if x.open_time >= at)
    entry_index = next((i for i, bar in enumerate(relevant)
                        if bar.low <= entry <= bar.high), None)
    risk = abs(entry - stop); reward = abs(target - entry)
    row = {"signal_id": signal["signal_id"], "signal_time": at.isoformat(),
        "chicago_hour": at.astimezone(ZoneInfo("America/Chicago")).hour,
        "side": side, "risk_points": format(risk, "f"),
        "reward_points": format(reward, "f"),
        "target_r_multiple": format(reward / risk, "f"), "entered": entry_index is not None}
    bounded_target = entry + risk * Decimal("2") if side == "LONG" else entry - risk * Decimal("2")
    row["fixed_2r_target_price"] = format(bounded_target, "f")
    if entry_index is None:
        row.update({"mfe_r_30": None, "mae_r_30": None,
                    "window_outcomes": {str(x): "WAITING_ENTRY" for x in WINDOWS},
                    "fixed_2r_window_outcomes": {str(x): "WAITING_ENTRY" for x in WINDOWS},
                    "eventual_first_outcome": "WAITING_ENTRY"})
        return row
    after = relevant[entry_index:]
    first30 = after[:30]
    favorable = (max((x.high for x in first30), default=entry) - entry
                  if side == "LONG" else entry - min((x.low for x in first30), default=entry))
    adverse = (entry - min((x.low for x in first30), default=entry)
               if side == "LONG" else max((x.high for x in first30), default=entry) - entry)
    row["mfe_r_30"] = format(max(Decimal("0"), favorable) / risk, "f")
    row["mae_r_30"] = format(max(Decimal("0"), adverse) / risk, "f")
    row["window_outcomes"] = {str(window): outcome(side, stop, target, after[:window])[0]
                              for window in WINDOWS}
    row["fixed_2r_window_outcomes"] = {
        str(window): outcome(side, stop, bounded_target, after[:window])[0]
        for window in WINDOWS}
    eventual, bars_to_event, ambiguous = outcome(side, stop, target, after)
    row.update({"eventual_first_outcome": eventual, "bars_to_event": bars_to_event,
                "ambiguous_stop_first": ambiguous})
    return row


def summarize(rows):
    entered = [x for x in rows if x["entered"]]
    target_r = [Decimal(x["target_r_multiple"]) for x in entered]
    mfe = [Decimal(x["mfe_r_30"]) for x in entered]
    mae = [Decimal(x["mae_r_30"]) for x in entered]
    return {"signal_count": len(rows), "entered_count": len(entered),
        "median_target_r": format(decimal_median(target_r), "f"),
        "median_mfe_r_30": format(decimal_median(mfe), "f"),
        "median_mae_r_30": format(decimal_median(mae), "f"),
        "mfe_at_least_1r_count": sum(x >= 1 for x in mfe),
        "mfe_reached_target_r_count": sum(m >= t for m, t in zip(mfe, target_r)),
        "eventual_first_outcomes": dict(sorted(Counter(
            x["eventual_first_outcome"] for x in rows).items())),
        "window_outcomes": {str(window): dict(sorted(Counter(
            x["window_outcomes"][str(window)] for x in rows).items())) for window in WINDOWS},
        "fixed_2r_window_outcomes": {str(window): dict(sorted(Counter(
            x["fixed_2r_window_outcomes"][str(window)] for x in rows).items()))
            for window in WINDOWS}}


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
    source = json.loads((ROOT / "outputs/experimental_target_five_day/latest.json").read_text())
    rows = []; markets = {}
    for market in FuturesCanonicalMarket:
        evidence = read_databento_research_days(ROOT / "data/databento_recovery_staging",
            market=market, days=DAYS, as_of=now)
        bars = tuple(x for x in evidence.dataset.candles if x.timeframe is CanonicalTimeframe.M1)
        signals = source["markets"][market.value]["experimental_major_single"]["signals"]
        market_rows = [analyze_signal(signal, bars) for signal in signals]
        rows.extend(market_rows); markets[market.value] = {"summary": summarize(market_rows),
                                                           "signals": market_rows}
    overall = summarize(rows)
    document = {"schema_version": "experimental-target-negative-evidence-diagnostic-v1",
        "state": "COMPLETE", "evaluated_at": now.isoformat(), "markets": markets,
        "overall": overall, "interpretation_constraints": [
            "DESCRIPTIVE_ONLY", "NO_THRESHOLD_OPTIMIZATION", "NO_DIRECTION_INFERENCE",
            "REQUIRES_UNTOUCHED_OUT_OF_SAMPLE_CONFIRMATION"],
        "canonical_policy_changed": False, "comparison_only": True,
        "paper_execution_permitted": False, "live_trading_permitted": False,
        "trading_authority": False}
    atomic_write(ROOT / "outputs/experimental_target_five_day/negative-evidence-diagnostic.json",
                 document)
    print(json.dumps({"schema_version": document["schema_version"], "overall": overall,
        "paper_execution_permitted": False, "trading_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
