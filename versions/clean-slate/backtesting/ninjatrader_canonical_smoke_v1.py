"""Deterministic advisory-only canonical replay of verified NinjaTrader bars."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import platform
import sys

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.ninjatrader_closed_bar_dataset_v1 import NinjaTraderClosedBarDatasetV1
from backtesting.orchestrator import EvaluationOutcome, TradingBrainEvaluationOrchestrator
from backtesting.replay import DeterministicReplay
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION


VERSION = "ninjatrader-canonical-smoke-v1"
CALCULATION_VERSION = "futures-canonical-advisory-v1"


class NinjaTraderCanonicalSmokeError(RuntimeError):
    pass


def _hex_id(value: object, field: str) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        raise NinjaTraderCanonicalSmokeError(f"{field} must be a SHA-256 identity")
    return value


@dataclass(frozen=True)
class NinjaTraderCanonicalSmokeV1:
    report_id: str
    market: FuturesCanonicalMarket
    instrument: str
    evaluated_at: datetime
    dataset_id: str
    dataset_fingerprint: str
    source_chain_head_sha256: str
    instrument_specification_id: str
    minimum_tick: Decimal
    run_id: str
    replay_checkpoint_id: str
    orchestration_checkpoint_id: str
    source_bar_count: int
    evaluated_batch_count: int
    outcome_counts: tuple[tuple[str, int], ...]
    latest_outcome: str
    latest_setup_fact_id: str
    deterministic_repeat_verified: bool
    qualified_signal_id: str | None = None
    signal_side: str | None = None
    signal_time: datetime | None = None
    entry_price: Decimal | None = None
    stop_price: Decimal | None = None
    target_price: Decimal | None = None
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


def _evaluate_once(*, evidence: NinjaTraderClosedBarDatasetV1,
                   minimum_tick: Decimal, specification_id: str,
                   as_of: datetime, return_state: bool = False,
                   orchestrator_class=TradingBrainEvaluationOrchestrator) -> tuple:
    dataset = evidence.dataset
    manifest = DatasetManifest.from_dataset(dataset, symbol=evidence.market.value,
        created_at=as_of, configuration_id=evidence.chain_head_sha256)
    run = BacktestRunManifest.create(dataset=manifest,
        trading_brain_contract_version=INTERFACE_CONTRACT_VERSION,
        strategy_configuration_version="canonical-strategy-v1",
        model_configuration_version="canonical-model-v1",
        replay_start_inclusive=manifest.interval_start_inclusive,
        replay_end_exclusive=manifest.interval_end_exclusive,
        starting_equity=Decimal("50000"),
        execution_cost_configuration_id="advisory-no-execution-v1", random_seed=0,
        runtime=RuntimeFacts(f"{sys.version_info.major}.{sys.version_info.minor}",
            platform.python_implementation(), platform.system(), VERSION))
    replay = DeterministicReplay(dataset=dataset, run=run)
    if not isinstance(orchestrator_class, type) or not issubclass(
            orchestrator_class, TradingBrainEvaluationOrchestrator):
        raise NinjaTraderCanonicalSmokeError("orchestrator class is invalid")
    engine = orchestrator_class(dataset=dataset, run=run,
        minimum_tick=minimum_tick, calculation_version=CALCULATION_VERSION,
        account_timezone="America/Chicago", canonical_mode=True,
        enabled_prior_period_reference_types=("PDH", "PDL"))
    state = engine.initial_state()
    for publication in replay:
        state = engine.evaluate(publication=publication, state=state).state
    replay_checkpoint = replay.checkpoint()
    orchestration_checkpoint = engine.checkpoint(
        state=state, replay_checkpoint=replay_checkpoint)
    engine.validate_resume(state=state, checkpoint=orchestration_checkpoint,
                           replay_checkpoint=replay_checkpoint)
    latest = state.batch_results[-1]
    fact = latest.setup_fact
    armed = latest.outcome in {EvaluationOutcome.ARMED_CONTINUATION,
                               EvaluationOutcome.ENTRY_ZONE_ARMED_REVERSAL}
    signal = (None, None, None, None, None, None)
    if armed and fact.final_qualification is not None:
        direction = getattr(getattr(fact, "setup", None), "direction", None)
        direction = getattr(direction, "value", direction)
        side = "LONG" if direction == "BULLISH" else "SHORT" if direction == "BEARISH" else None
        entry = getattr(fact.entry_zone, "eq_normalized", None)
        stop = getattr(fact.stop, "stop_price", None)
        target = getattr(fact.target, "level", None)
        if side is None or any(not isinstance(value, Decimal) for value in (entry, stop, target)):
            raise NinjaTraderCanonicalSmokeError("armed setup lacks exact lifecycle facts")
        signal = (fact.final_qualification.id, side, fact.evaluation_time,
                  entry, stop, target)
    counts = tuple((outcome.value, sum(row.outcome is outcome for row in state.batch_results))
                   for outcome in EvaluationOutcome)
    result = (run.id, replay_checkpoint.event_sequence_id,
            orchestration_checkpoint.id, len(state.batch_results), counts,
            latest.outcome.value, latest.setup_fact.id, signal)
    return (result, state) if return_state else result


def evaluate_ninjatrader_canonical_smoke(*,
        evidence: NinjaTraderClosedBarDatasetV1, minimum_tick: Decimal,
        instrument_specification_id: str, as_of: datetime
) -> NinjaTraderCanonicalSmokeV1:
    """Replay twice and emit a report only when every deterministic identity agrees."""
    if not isinstance(evidence, NinjaTraderClosedBarDatasetV1):
        raise NinjaTraderCanonicalSmokeError("verified NinjaTrader dataset evidence is required")
    if (evidence.smoke_replay_eligible is not True
            or evidence.training_validation_eligible is not False
            or evidence.untouched_oos_eligible is not False
            or evidence.advisory_only is not True
            or evidence.paper_execution_permitted is not False
            or evidence.live_trading_permitted is not False
            or evidence.trading_authority is not False):
        raise NinjaTraderCanonicalSmokeError("dataset grants prohibited authority")
    if not isinstance(minimum_tick, Decimal) or not minimum_tick.is_finite() or minimum_tick <= 0:
        raise NinjaTraderCanonicalSmokeError("minimum_tick must be a positive exact Decimal")
    specification_id = _hex_id(instrument_specification_id, "instrument specification")
    if (not isinstance(as_of, datetime) or as_of.tzinfo is None
            or as_of.utcoffset() != timedelta(0)):
        raise NinjaTraderCanonicalSmokeError("as_of must be UTC")
    if as_of < evidence.dataset.candles[-1].close_time:
        raise NinjaTraderCanonicalSmokeError("evaluation cannot precede dataset coverage")

    first = _evaluate_once(evidence=evidence, minimum_tick=minimum_tick,
                           specification_id=specification_id, as_of=as_of)
    second = _evaluate_once(evidence=evidence, minimum_tick=minimum_tick,
                            specification_id=specification_id, as_of=as_of)
    if first != second:
        raise NinjaTraderCanonicalSmokeError("canonical replay was not deterministic")
    run_id, replay_id, orchestration_id, batches, counts, outcome, setup_id, signal = first
    report_id = hashlib.sha256("\x1f".join((VERSION, evidence.market.value,
        evidence.instrument, as_of.isoformat(timespec="microseconds"),
        evidence.dataset.dataset_id, evidence.dataset.fingerprint,
        evidence.chain_head_sha256, specification_id, format(minimum_tick, "f"),
        run_id, replay_id, orchestration_id, str(batches), outcome,
        setup_id, *("NONE" if value is None else str(value) for value in signal))).encode()).hexdigest()
    return NinjaTraderCanonicalSmokeV1(report_id, evidence.market,
        evidence.instrument, as_of, evidence.dataset.dataset_id,
        evidence.dataset.fingerprint, evidence.chain_head_sha256,
        specification_id, minimum_tick, run_id, replay_id, orchestration_id,
        evidence.record_count, batches, counts, outcome, setup_id, True, *signal)


def assert_distinct_ninjatrader_smokes(es: NinjaTraderCanonicalSmokeV1,
                                       nq: NinjaTraderCanonicalSmokeV1) -> None:
    if (es.market, nq.market) != (FuturesCanonicalMarket.ES, FuturesCanonicalMarket.NQ):
        raise NinjaTraderCanonicalSmokeError("expected ordered ES and NQ smoke reports")
    if (es.report_id == nq.report_id or es.dataset_id == nq.dataset_id
            or es.dataset_fingerprint == nq.dataset_fingerprint
            or es.source_chain_head_sha256 == nq.source_chain_head_sha256
            or es.run_id == nq.run_id):
        raise NinjaTraderCanonicalSmokeError("ES and NQ smoke evidence is not isolated")
