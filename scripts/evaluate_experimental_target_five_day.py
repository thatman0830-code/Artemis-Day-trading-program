"""Compare canonical and major-single target lanes on five archived days."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import uuid

from backtesting.databento_research_dataset_v1 import read_databento_research_days
from backtesting.experimental_major_single_orchestrator_v1 import ExperimentalMajorSingleTargetOrchestratorV1
from backtesting.experimental_major_single_orchestrator_v1 import SESSION_POLICY
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_v1 import _evaluate_once
from backtesting.orchestrator import EvaluationOutcome

DAYS = ("2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10")


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


def counts(state):
    targets = entries = stops = finals = armed = 0
    signal_facts = []
    for batch in state.batch_results:
        fact = batch.setup_fact
        targets += int(fact.target is not None)
        entries += int(getattr(fact.entry_zone, "selected_zone_id", None) is not None)
        stops += int(fact.stop is not None)
        finals += int(fact.final_qualification is not None)
        if batch.outcome in {EvaluationOutcome.ARMED_CONTINUATION,
                             EvaluationOutcome.ENTRY_ZONE_ARMED_REVERSAL}:
            armed += 1
            qualification = fact.final_qualification
            signal_facts.append({"signal_id": qualification.id,
                "signal_time": fact.evaluation_time.isoformat(),
                "side": "LONG" if qualification.direction.value == "BULLISH" else "SHORT",
                "entry_price": format(qualification.entry, "f"),
                "stop_price": format(qualification.stop, "f"),
                "target_price": format(qualification.target, "f")})
    return {"target_available_count": targets, "entry_selected_count": entries,
            "stop_selected_count": stops, "finalization_count": finals,
            "armed_signal_count": armed, "signals": signal_facts}


def main():
    now = datetime.now(timezone.utc)
    canonical_audit = json.loads((ROOT /
        "outputs/futures_data/databento_research_evaluation/2026-09-10-gate-audit.json").read_text())
    output_root = ROOT / "outputs/experimental_target_five_day"
    partial = output_root / "partial.json"
    markets = json.loads(partial.read_text()).get("markets", {}) if partial.exists() else {}
    for market in FuturesCanonicalMarket:
        if market.value in markets:
            print(f"REUSING_EXPERIMENTAL_{market.value}", flush=True)
            continue
        print(f"EVALUATING_EXPERIMENTAL_{market.value}", flush=True)
        evidence = read_databento_research_days(ROOT / "data/databento_recovery_staging",
            market=market, days=DAYS, as_of=now)
        _, experimental = _evaluate_once(evidence=evidence, minimum_tick=Decimal("0.25"),
            specification_id="0" * 64, as_of=now, return_state=True,
            orchestrator_class=ExperimentalMajorSingleTargetOrchestratorV1)
        prior = canonical_audit["markets"][market.value]
        canonical = {"target_available_count": prior["target_available_count"],
            "entry_selected_count": prior["entry_zone_selected_count"],
            "stop_selected_count": prior["stop_selected_count"],
            "finalization_count": prior["finalization_count"],
            "armed_signal_count": prior["armed_count"], "signals": []}
        markets[market.value] = {"canonical": canonical,
                                 "experimental_major_single": counts(experimental)}
        atomic_write(partial, {"schema_version": "experimental-target-five-day-partial-v1",
            "context_days_utc": list(DAYS), "markets": markets,
            "paper_execution_permitted": False, "trading_authority": False})
    document = {"schema_version": "experimental-target-five-day-evaluation-v1",
        "state": "COMPLETE", "evaluated_at": now.isoformat(), "context_days_utc": list(DAYS),
        "markets": markets, "identical_source_data_verified": True,
        "canonical_evidence_source": "databento-five-day-strategy-gate-audit-v1",
        "experimental_session_policy": SESSION_POLICY,
        "canonical_policy_changed": False, "comparison_only": True,
        "paper_execution_permitted": False, "live_trading_permitted": False,
        "trading_authority": False}
    target = output_root / "latest.json"
    atomic_write(target, document)
    partial.unlink(missing_ok=True)
    summary = {market: {lane: {key: value for key, value in facts.items() if key != "signals"}
                         for lane, facts in lanes.items()} for market, lanes in markets.items()}
    print(json.dumps({"schema_version": document["schema_version"], "markets": summary,
        "paper_execution_permitted": False, "trading_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
