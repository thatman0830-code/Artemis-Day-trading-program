"""Collect pre-registered fixed-2R OOS outcomes from verified live bars only."""
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

from backtesting.experimental_major_single_orchestrator_v1 import ExperimentalMajorSingleTargetOrchestratorV1
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe
from backtesting.ninjatrader_canonical_smoke_v1 import NinjaTraderCanonicalSmokeV1, _evaluate_once
from backtesting.ninjatrader_oos_shadow_dataset_v1 import read_ninjatrader_oos_shadow_days
from backtesting.ninjatrader_signal_lifecycle_v1 import resolve_signal_lifecycle
from backtesting.ninjatrader_three_profile_shadow_ledger_v1 import build_three_profile_shadow_ledgers


def clean(value):
    if isinstance(value, Decimal): return format(value, "f")
    if isinstance(value, Enum): return value.value
    if hasattr(value, "isoformat"): return value.isoformat()
    if isinstance(value, tuple): return [clean(x) for x in value]
    if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
    return value


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


def source_days(root, market, current_day):
    available = sorted(x.stem for x in (Path(root) / market.value).glob("????-??-??.jsonl")
                       if x.stem <= current_day and x.is_file() and not x.is_symlink())
    selected = tuple(available[-5:])
    if not selected or selected[-1] != current_day:
        raise ValueError(f"current {market.value} archive unavailable")
    return selected


def signal_rows(state, market, oos_days):
    rows = []
    for batch in state.batch_results:
        fact = batch.setup_fact; qualification = fact.final_qualification
        if qualification is None or fact.evaluation_time.date().isoformat() not in oos_days:
            continue
        risk = abs(qualification.entry - qualification.stop)
        target = (qualification.entry + risk * Decimal("2")
                  if qualification.direction.value == "BULLISH"
                  else qualification.entry - risk * Decimal("2"))
        rows.append({"signal_id": sha256(("fixed-2r-oos-v1" + qualification.id).encode()).hexdigest(),
            "source_qualification_id": qualification.id, "market": market.value,
            "side": "LONG" if qualification.direction.value == "BULLISH" else "SHORT",
            "signal_time": fact.evaluation_time.isoformat(),
            "entry_price": format(qualification.entry, "f"),
            "stop_price": format(qualification.stop, "f"),
            "target_price": format(target, "f")})
    unique = {x["signal_id"]: x for x in rows}
    return tuple(unique[key] for key in sorted(unique))


def report(signal, evidence, now):
    identity = sha256(json.dumps(signal, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    market = FuturesCanonicalMarket(signal["market"])
    return NinjaTraderCanonicalSmokeV1(identity, market, evidence.instrument, now,
        evidence.dataset.dataset_id, evidence.dataset.fingerprint, evidence.chain_head_sha256,
        "0" * 64, Decimal("0.25"), "0" * 64, "1" * 64, "2" * 64,
        evidence.record_count, evidence.record_count, (), "FIXED_2R_OOS_SHADOW",
        identity, True, signal["signal_id"], signal["side"],
        datetime.fromisoformat(signal["signal_time"]), Decimal(signal["entry_price"]),
        Decimal(signal["stop_price"]), Decimal(signal["target_price"]))


def main():
    now = datetime.now(timezone.utc); current_day = now.date().isoformat()
    protocol = json.loads((ROOT / "outputs/experimental_target_five_day/fixed-2r-oos-protocol.json").read_text())
    oos_days = tuple(protocol["untouched_oos_days"])
    if (protocol.get("schema_version") != "fixed-2r-shadow-oos-protocol-v1"
            or protocol.get("approved") is not False
            or protocol.get("trading_authority") is not False
            or current_day not in oos_days):
        raise ValueError("active non-authoritative OOS protocol required")
    completed = []; outcomes = Counter(); market_documents = {}
    blocked = False
    for market in FuturesCanonicalMarket:
        try:
            days = source_days(ROOT / "data/ninjatrader_closed_bars", market, current_day)
            evidence = read_ninjatrader_oos_shadow_days(ROOT / "data/ninjatrader_closed_bars",
                market=market, days=days, as_of=now)
        except ValueError as error:
            blocked = True
            market_documents[market.value] = {"state": "WAITING_COMPLETE_SESSION",
                "reason": str(error), "signals": []}
            continue
        _, state = _evaluate_once(evidence=evidence, minimum_tick=Decimal("0.25"),
            specification_id="0" * 64, as_of=now, return_state=True,
            orchestrator_class=ExperimentalMajorSingleTargetOrchestratorV1)
        signals = signal_rows(state, market, set(oos_days)); rows = []
        bars = tuple(x for x in evidence.dataset.candles if x.timeframe is CanonicalTimeframe.M1)
        for signal in signals:
            resolution = resolve_signal_lifecycle(report=report(signal, evidence, now),
                bars=bars, max_holding_bars=30)
            outcomes[resolution.outcome.value] += 1
            if resolution.completed_trade is not None:
                completed.append(resolution.completed_trade)
            rows.append({"signal": signal, "outcome": resolution.outcome.value,
                         "resolution_id": resolution.resolution_id,
                         "ambiguous_bar_resolved_stop_first": resolution.ambiguous_bar_resolved_stop_first})
        market_documents[market.value] = {"source_days": list(days),
            "dataset_fingerprint": evidence.dataset.fingerprint,
            "latest_close_utc": bars[-1].close_time.isoformat(), "signals": rows}
    trades = tuple(sorted(completed, key=lambda x: (x.exit_time, x.signal_id)))
    ledgers = build_three_profile_shadow_ledgers(trades=trades, evaluated_at=now)
    document = {"schema_version": "fixed-2r-oos-shadow-cycle-v1",
        "state": "WAITING_COMPLETE_SESSION" if blocked else "COLLECTING",
        "observed_at": now.isoformat(), "oos_days": list(oos_days),
        "signal_count": sum(len(x["signals"]) for x in market_documents.values()),
        "completed_trade_count": len(trades), "outcome_counts": dict(sorted(outcomes.items())),
        "markets": market_documents, "ledgers": [clean(asdict(x)) for x in ledgers],
        "canonical_history_modified": False, "comparison_only": True,
        "paper_execution_permitted": False, "live_trading_permitted": False,
        "trading_authority": False}
    atomic_write(ROOT / "outputs/fixed_2r_oos_shadow/latest.json", document)
    print(json.dumps({"schema_version": document["schema_version"], "state": document["state"],
        "signal_count": document["signal_count"], "completed_trade_count": len(trades),
        "outcome_counts": document["outcome_counts"], "paper_execution_permitted": False,
        "trading_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
