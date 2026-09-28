"""Deterministic canonical Trading Brain evaluation for isolated ES/NQ lanes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import platform
import sys

from backtesting.futures_canonical_lane_v1 import (
    FuturesCanonicalLaneV1,
    FuturesCanonicalMarket,
    LANE_VERSION,
)
from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.market_data import GapPolicy, normalize_historical_candle, validate_dataset
from backtesting.orchestrator import EvaluationOutcome, TradingBrainEvaluationOrchestrator
from backtesting.replay import DeterministicReplay
from backtesting.core_v1.production_adapters import PassBV3ArchiveAdapter
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION


VERSION = "futures-canonical-evaluation-v1"
CALCULATION_VERSION = "futures-canonical-advisory-v1"


class FuturesCanonicalEvaluationError(RuntimeError):
    pass


def _hex_id(value: object, field: str) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        raise FuturesCanonicalEvaluationError(f"{field} must be a SHA-256 identity")
    return value


@dataclass(frozen=True)
class FuturesCanonicalEvaluationV1:
    report_id: str
    lane_id: str
    market: FuturesCanonicalMarket
    evaluated_at: datetime
    dataset_id: str
    dataset_fingerprint: str
    instrument_specification_id: str
    minimum_tick: Decimal
    run_id: str
    replay_checkpoint_id: str
    orchestration_checkpoint_id: str
    evaluated_batch_count: int
    source_bar_count: int
    source_contract_ids: tuple[str, ...]
    data_quality_event_count: int
    outcome_counts: tuple[tuple[str, int], ...]
    latest_outcome: str
    latest_setup_fact_id: str
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION

    def __post_init__(self) -> None:
        if (self.market not in FuturesCanonicalMarket
                or self.evaluated_at.tzinfo is None
                or self.evaluated_at.utcoffset() != timedelta(0)
                or self.minimum_tick <= 0
                or not self.minimum_tick.is_finite() or self.evaluated_batch_count <= 0
                or self.source_bar_count != self.evaluated_batch_count
                or not self.source_contract_ids
                or self.advisory_only is not True
                or self.paper_execution_permitted is not False
                or self.live_trading_permitted is not False
                or self.trading_authority is not False):
            raise FuturesCanonicalEvaluationError("canonical futures evaluation is invalid")


def evaluate_futures_canonical_lane(
    *,
    lane: FuturesCanonicalLaneV1,
    adapter: PassBV3ArchiveAdapter,
    minimum_tick: Decimal,
    instrument_specification_id: str,
    as_of: datetime,
) -> FuturesCanonicalEvaluationV1:
    """Replay one verified ES/NQ lane through the canonical advisory engine."""
    if not isinstance(lane, FuturesCanonicalLaneV1) or lane.schema_version != LANE_VERSION:
        raise FuturesCanonicalEvaluationError("canonical futures lane is required")
    if (lane.advisory_only is not True or lane.paper_execution_permitted is not False
            or lane.live_trading_permitted is not False or lane.trading_authority is not False):
        raise FuturesCanonicalEvaluationError("lane grants prohibited execution authority")
    if not isinstance(adapter, PassBV3ArchiveAdapter):
        raise FuturesCanonicalEvaluationError("verified Pass B v3 adapter is required")
    if not isinstance(minimum_tick, Decimal) or not minimum_tick.is_finite() or minimum_tick <= 0:
        raise FuturesCanonicalEvaluationError("minimum_tick must be a positive exact Decimal")
    specification_id = _hex_id(instrument_specification_id, "instrument specification")
    if (not isinstance(as_of, datetime) or as_of.tzinfo is None
            or as_of.utcoffset() != timedelta(0)):
        raise FuturesCanonicalEvaluationError("as_of must be UTC")

    metadata = adapter.validate()
    if (adapter.market != lane.market.value or metadata.dataset_id != lane.dataset_id
            or metadata.dataset_fingerprint != lane.dataset_fingerprint):
        raise FuturesCanonicalEvaluationError("adapter evidence differs from admitted lane")
    if as_of < metadata.coverage_end_exclusive:
        raise FuturesCanonicalEvaluationError("evaluation cannot precede archive coverage")

    source_events = tuple(adapter.iter_events())
    if not source_events:
        raise FuturesCanonicalEvaluationError("verified lane has no source bars")
    contracts = tuple(sorted({item.bar.contract_id for item in source_events
                              if item.bar.contract_id is not None}))
    candles = tuple(normalize_historical_candle({
        "symbol": lane.market.value, "timeframe": "1m",
        "open_time": item.bar.open_time, "close_time": item.bar.close_time,
        "open": item.bar.open, "high": item.bar.high, "low": item.bar.low,
        "close": item.bar.close, "volume": item.bar.volume, "is_closed": True,
    }, dataset_id=lane.dataset_id, schema_version="historical-candle-v1",
       source="verified-pass-b-v3", exchange="XCME") for item in source_events)
    dataset = validate_dataset(candles, dataset_id=lane.dataset_id,
        schema_version="historical-candle-v1", source="verified-pass-b-v3",
        exchange="XCME", gap_policy=GapPolicy.RECORD, validation_time=as_of)
    manifest = DatasetManifest.from_dataset(dataset, symbol=lane.market.value,
        created_at=as_of, configuration_id=lane.lane_id)
    run = BacktestRunManifest.create(dataset=manifest,
        trading_brain_contract_version=INTERFACE_CONTRACT_VERSION,
        strategy_configuration_version=lane.strategy_configuration_version,
        model_configuration_version=lane.model_configuration_version,
        replay_start_inclusive=manifest.interval_start_inclusive,
        replay_end_exclusive=manifest.interval_end_exclusive,
        starting_equity=Decimal("100000"),
        execution_cost_configuration_id="advisory-no-execution-v1", random_seed=0,
        runtime=RuntimeFacts(f"{sys.version_info.major}.{sys.version_info.minor}",
            platform.python_implementation(), platform.system(), VERSION))
    replay = DeterministicReplay(dataset=dataset, run=run)
    engine = TradingBrainEvaluationOrchestrator(dataset=dataset, run=run,
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
    counts = tuple((outcome.value, sum(row.outcome is outcome for row in state.batch_results))
                   for outcome in EvaluationOutcome)
    quality_count = len(adapter.data_quality_events)
    report_id = hashlib.sha256("\x1f".join((VERSION, lane.lane_id,
        as_of.isoformat(timespec="microseconds"), dataset.fingerprint,
        specification_id, format(minimum_tick, "f"), run.id,
        replay_checkpoint.event_sequence_id, orchestration_checkpoint.id,
        str(len(source_events)), ",".join(contracts), str(quality_count),
        latest.outcome.value, latest.setup_fact.id)).encode()).hexdigest()
    return FuturesCanonicalEvaluationV1(report_id, lane.lane_id, lane.market, as_of,
        dataset.dataset_id, dataset.fingerprint, specification_id, minimum_tick,
        run.id, replay_checkpoint.event_sequence_id, orchestration_checkpoint.id,
        len(state.batch_results), len(source_events), contracts, quality_count,
        counts, latest.outcome.value, latest.setup_fact.id)


def assert_distinct_futures_evaluations(
    es: FuturesCanonicalEvaluationV1, nq: FuturesCanonicalEvaluationV1
) -> None:
    if (es.market, nq.market) != (FuturesCanonicalMarket.ES, FuturesCanonicalMarket.NQ):
        raise FuturesCanonicalEvaluationError("expected ordered ES and NQ evaluations")
    if (es.report_id == nq.report_id or es.lane_id == nq.lane_id
            or es.dataset_id == nq.dataset_id
            or es.dataset_fingerprint == nq.dataset_fingerprint
            or es.run_id == nq.run_id):
        raise FuturesCanonicalEvaluationError("ES and NQ evaluation evidence is not isolated")
