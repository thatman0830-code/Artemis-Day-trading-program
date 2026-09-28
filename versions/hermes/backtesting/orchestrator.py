from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256

from backtesting.adapter import TradingBrainMarketDataAdapter
from backtesting.manifests import BacktestRunManifest
from backtesting.market_data import CanonicalTimeframe, HistoricalDataset
from backtesting.replay import DeterministicReplay, ReplayCheckpoint, ReplayPublication
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION, PUBLIC_ENGINE_ENTRY_POINTS
from strategy.trading_brain.p11_cisd_confirmation import (
    CISDEngine, CISDProcess, CISDState, DeliveryLeg, ReversalConfirmationSequence,
)
from strategy.trading_brain.p11_delivery_leg_producer import (
    DeliveryFormationOutcome, ReversalDeliveryFormation,
    ReversalDeliveryLedger, ReversalDeliveryLegProducer, ReversalDeliverySource,
)
from strategy.trading_brain.p13_stop_loss_selection import StopLossSelectionEngine
from strategy.trading_brain.p19_mechanical_swings import (
    MechanicalSwingEngine, MechanicalSwingResult,
)
from strategy.trading_brain.p16_conflict_resolution import ConflictResolver
from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakQualifier, StructuralEventType, StructuralRegime,
    StructuralStateSnapshot,
)
from strategy.trading_brain.p20_displacement import (
    DisplacementCandle, DisplacementLedger, DisplacementOutcome,
    DisplacementQualificationProducer, MechanicalDisplacementPolicy,
)
from strategy.trading_brain.p20_structural_state_producer import (
    StructuralIngestionLedger, StructuralStateProducer,
)
from strategy.trading_brain.p20_state_commit import StructuralStateCommitter
from strategy.trading_brain.p21_active_dealing_range import (
    ActiveDealingRangeEngine, StructuralRange,
)
from strategy.trading_brain.p22_ote import OTE, OTEEngine
from strategy.trading_brain.p23_liquidity import (
    LiquidityInteractionEngine, LiquidityPoolEngine, LiquidityReference,
    LiquiditySweep,
)
from strategy.trading_brain.p23_liquidity_reference_producer import (
    StructuralLiquidityReferenceLedger, StructuralLiquidityReferenceProducer,
)
from strategy.trading_brain.p23_prior_period_references import (
    POLICY_ID as PRIOR_PERIOD_POLICY_ID, PriorPeriodCandle,
    PriorPeriodLiquidityReferenceProducer, PriorPeriodReferenceLedger,
    PriorPeriodReferenceType,
)
from strategy.trading_brain.p24_lrl_selection import LRL, LRLRole, LRLSelectionEngine
from strategy.trading_brain.p25_fvg_ifvg import FVG, IFVG, FVGEngine
from strategy.trading_brain.p26_confluence import Confluence, ConfluenceEngine
from strategy.trading_brain.p27_setup_qualification import (
    ContinuationSetupState, ReversalSetupState, SetupModel,
    SetupQualificationEngine,
)
from strategy.trading_brain.owner_policies import CANONICAL_MIN_RR_V1, MinimumRiskRewardPolicy
from strategy.trading_brain.p28_entry_zone_selection import EntryZoneSelectionEngine


class EvaluationOutcome(str, Enum):
    NO_SETUP = "NO_SETUP"
    WAITING_MISSING_PREREQUISITE = "WAITING_MISSING_PREREQUISITE"
    CANDIDATE = "CANDIDATE"
    MSS_CISD_CONFIRMED = "MSS_CISD_CONFIRMED"
    ARMED_CONTINUATION = "ARMED_CONTINUATION"
    ENTRY_ZONE_ARMED_REVERSAL = "ENTRY_ZONE_ARMED_REVERSAL"
    REJECTED = "REJECTED"
    INVALID_FAIL_CLOSED = "INVALID_FAIL_CLOSED"


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a UTC timezone-aware datetime.")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _record_id(value: object) -> str:
    if value is None:
        return "NONE"
    direct = getattr(value, "id", None)
    if direct is not None:
        return str(direct)
    for name in ("qualification", "setup", "stop", "active_lrl", "active_range", "active_ote", "confluence"):
        nested = getattr(value, name, None)
        if nested is not None and getattr(nested, "id", None) is not None:
            return str(nested.id)
    error = getattr(value, "error", None)
    if error is not None and getattr(error, "id", None) is not None:
        return str(error.id)
    return _hash(("canonical-result", type(value).__module__, type(value).__name__, repr(value)))


@dataclass(frozen=True)
class EvaluationContext:
    id: str
    dataset_id: str
    dataset_fingerprint: str
    run_id: str
    replay_batch_id: str
    replay_batch_sequence: int
    evaluation_time: datetime
    symbol: str
    timeframes: tuple[CanonicalTimeframe, ...]
    strategy_configuration_version: str
    model_configuration_version: str
    trading_brain_contract_version: str
    calculation_version: str


@dataclass(frozen=True)
class PrimitiveResultReference:
    id: str
    owner: str
    entry_point: str
    evaluation_time: datetime
    input_ids: tuple[str, ...]
    output_id: str
    canonical_state: str | None
    canonical_reason: str | None
    result: object


@dataclass(frozen=True)
class MissingPrerequisite:
    id: str
    owner: str
    prerequisite: str
    evaluation_time: datetime
    reason: str


@dataclass(frozen=True)
class EvaluationTrace:
    id: str
    context_id: str
    primitive_results: tuple[PrimitiveResultReference, ...]
    missing_prerequisites: tuple[MissingPrerequisite, ...]


@dataclass(frozen=True)
class ContinuationEvaluationRequest:
    id: str
    setup_candidate_id: str
    direction: StructuralRegime
    structural_state: StructuralStateSnapshot
    active_range: StructuralRange | None
    liquidity_references: tuple[LiquidityReference, ...]
    invalidation_event_id: str | None = None
    accepted_structural_event_id: str | None = None


@dataclass(frozen=True)
class ReversalEvaluationRequest:
    id: str
    setup_candidate_id: str
    direction: StructuralRegime
    structural_state: StructuralStateSnapshot
    active_range: StructuralRange | None
    liquidity_references: tuple[LiquidityReference, ...]
    confirmation_sequence: ReversalConfirmationSequence
    delivery_legs: tuple[DeliveryLeg, ...]
    qualifying_sweep: LiquiditySweep
    invalidation_event_id: str | None = None
    delivery_source: ReversalDeliverySource | None = None
    accepted_structural_event_id: str | None = None


SetupRequest = ContinuationEvaluationRequest | ReversalEvaluationRequest


@dataclass(frozen=True)
class RequestEvaluationState:
    request_id: str
    active_range: StructuralRange | None = None
    active_ote: OTE | None = None
    active_lrl: LRL | None = None
    cisd_process: CISDProcess | None = None
    historical_facts: tuple[object, ...] = ()


@dataclass(frozen=True)
class SetupStateFact:
    id: str
    request_id: str | None
    model: SetupModel | None
    outcome: EvaluationOutcome
    canonical_state: object | None
    canonical_reason: str | None
    setup: object | None
    entry_zone: object | None
    stop: object | None
    target: LRL | None
    final_qualification: object | None
    evaluation_time: datetime


@dataclass(frozen=True)
class BatchEvaluationResult:
    id: str
    context: EvaluationContext
    outcome: EvaluationOutcome
    trace: EvaluationTrace
    setup_fact: SetupStateFact
    source_candle_ids: tuple[str, ...]
    request_fingerprint: str


@dataclass(frozen=True)
class OrchestrationState:
    id: str
    dataset_id: str
    dataset_fingerprint: str
    run_id: str
    trading_brain_contract_version: str
    calculation_version: str
    last_batch_sequence: int | None = None
    last_evaluation_time: datetime | None = None
    structural_ledgers: tuple[StructuralIngestionLedger, ...] = ()
    displacement_ledger: DisplacementLedger = DisplacementLedger()
    liquidity_reference_ledger: StructuralLiquidityReferenceLedger = (
        StructuralLiquidityReferenceLedger()
    )
    reversal_delivery_ledger: ReversalDeliveryLedger = ReversalDeliveryLedger()
    prior_period_reference_ledger: PriorPeriodReferenceLedger = PriorPeriodReferenceLedger()
    request_states: tuple[RequestEvaluationState, ...] = ()
    batch_results: tuple[BatchEvaluationResult, ...] = ()
    active_requests: tuple[SetupRequest, ...] = ()


@dataclass(frozen=True)
class OrchestrationCommit:
    state: OrchestrationState
    result: BatchEvaluationResult


@dataclass(frozen=True)
class OrchestrationCheckpoint:
    id: str
    checkpoint_version: str
    state_id: str
    dataset_id: str
    dataset_fingerprint: str
    run_id: str
    trading_brain_contract_version: str
    calculation_version: str
    last_batch_sequence: int | None
    replay_checkpoint: ReplayCheckpoint


class TradingBrainEvaluationOrchestrator:
    """Phase 3 read-only strategy evaluator. It stops before canonical #29.1."""

    CHECKPOINT_VERSION = "backtesting-orchestration-checkpoint-v1"

    def __init__(self, *, dataset: HistoricalDataset, run: BacktestRunManifest,
                 minimum_tick: Decimal, calculation_version: str,
                 account_timezone: str = "UTC",
                 prior_period_policy_id: str = PRIOR_PERIOD_POLICY_ID,
                 risk_reward_policy: MinimumRiskRewardPolicy = CANONICAL_MIN_RR_V1,
                 canonical_mode: bool = False,
                 enabled_prior_period_reference_types: tuple[str, ...] = (
                     "PDH", "PDL", "PWH", "PWL",
                 )):
        if not isinstance(dataset, HistoricalDataset) or not isinstance(run, BacktestRunManifest):
            raise TypeError("Phase 3 requires Phase 1 dataset and run records.")
        if (dataset.dataset_id, dataset.fingerprint, dataset.symbol) != (
                run.dataset_id, run.dataset_fingerprint, run.symbol):
            raise ValueError("Dataset and run identities are incompatible.")
        if run.trading_brain_contract_version != INTERFACE_CONTRACT_VERSION:
            raise ValueError("Trading Brain contract version is incompatible.")
        if not isinstance(minimum_tick, Decimal) or not minimum_tick.is_finite() or minimum_tick <= 0:
            raise ValueError("minimum_tick must be a finite positive Decimal.")
        if not calculation_version.strip():
            raise ValueError("calculation_version is required.")
        self.dataset = dataset
        self.run = run
        self.minimum_tick = minimum_tick
        self.calculation_version = calculation_version
        if prior_period_policy_id != PRIOR_PERIOD_POLICY_ID:
            raise ValueError("Unknown prior-period policy identity.")
        self.account_timezone = account_timezone
        self.prior_period_policy_id = prior_period_policy_id
        self.risk_reward_policy = risk_reward_policy
        self.canonical_mode = bool(canonical_mode)
        try:
            self.enabled_prior_period_reference_types = tuple(
                PriorPeriodReferenceType(item) for item in enabled_prior_period_reference_types
            )
        except ValueError as error:
            raise ValueError("Unknown prior-period reference type.") from error
        if len(set(self.enabled_prior_period_reference_types)) != len(
                self.enabled_prior_period_reference_types):
            raise ValueError("Duplicate prior-period reference type.")
        self.adapter = TradingBrainMarketDataAdapter(dataset)
        self._expected_publications = tuple(DeterministicReplay(dataset=dataset, run=run))
        self._assert_strategy_manifest()

    @staticmethod
    def _assert_strategy_manifest() -> None:
        required = {"#11", "#13", "#19", "#20", "#21", "#22", "#23", "#24", "#25", "#26", "#27", "#28"}
        if not required <= set(PUBLIC_ENGINE_ENTRY_POINTS):
            raise RuntimeError("Frozen strategy entry-point manifest is incomplete.")

    def initial_state(self) -> OrchestrationState:
        identity = _hash(("orchestration-state-v1", self.dataset.dataset_id,
                          self.dataset.fingerprint, self.run.id,
                          self.run.trading_brain_contract_version,
                          self.calculation_version, "INITIAL"))
        return OrchestrationState(
            identity, self.dataset.dataset_id, self.dataset.fingerprint,
            self.run.id, self.run.trading_brain_contract_version,
            self.calculation_version,
        )

    @staticmethod
    def _milliseconds(value: datetime) -> int:
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        delta = value - epoch
        return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000

    def _validate(self, *, publication: ReplayPublication,
                  state: OrchestrationState) -> None:
        if not isinstance(publication, ReplayPublication) or not isinstance(state, OrchestrationState):
            raise TypeError("Immutable Phase 2 publication and Phase 3 state are required.")
        if (state.dataset_id, state.dataset_fingerprint, state.run_id,
            state.trading_brain_contract_version, state.calculation_version) != (
                self.dataset.dataset_id, self.dataset.fingerprint, self.run.id,
                self.run.trading_brain_contract_version, self.calculation_version):
            raise ValueError("Orchestration state identity/version mismatch.")
        batch = publication.batch
        if batch.sequence >= len(self._expected_publications) or publication != self._expected_publications[batch.sequence]:
            raise ValueError("Replay publication is not the canonical Phase 2 event at this cursor.")
        if publication.availability.published_batch_id != batch.id:
            raise ValueError("Replay publication identities are incompatible.")
        if publication.availability.run_id != self.run.id or publication.availability.dataset_id != self.dataset.dataset_id:
            raise ValueError("Replay publication run/dataset mismatch.")
        if state.last_batch_sequence is not None:
            if batch.sequence < state.last_batch_sequence:
                raise ValueError("Cannot evaluate after a later timestamp was committed.")
            if batch.sequence > state.last_batch_sequence + 1:
                raise ValueError("Cannot skip a replay batch.")
        elif batch.sequence != 0:
            raise ValueError("Initial orchestration must consume replay batch zero.")

    def _context(self, publication: ReplayPublication) -> EvaluationContext:
        batch = publication.batch
        identity = _hash(("evaluation-context-v1", self.dataset.fingerprint,
                          self.run.id, batch.id, self.calculation_version))
        return EvaluationContext(
            identity, self.dataset.dataset_id, self.dataset.fingerprint,
            self.run.id, batch.id, batch.sequence, batch.event_time,
            self.run.symbol, self.run.timeframes,
            self.run.strategy_configuration_version,
            self.run.model_configuration_version,
            self.run.trading_brain_contract_version, self.calculation_version,
        )

    @staticmethod
    def _primitive(*, owner: str, entry_point: str, time: datetime,
                   inputs: tuple[str, ...], result: object,
                   state: object | None = None, reason: str | None = None) -> PrimitiveResultReference:
        if entry_point not in PUBLIC_ENGINE_ENTRY_POINTS[owner]:
            raise RuntimeError(f"Unapproved Trading Brain entry point: {entry_point}")
        output = _record_id(result)
        canonical_state = getattr(state, "value", str(state)) if state is not None else None
        identity = _hash(("primitive-reference-v1", owner, entry_point,
                          _stamp(time), *inputs, output,
                          canonical_state or "", reason or ""))
        return PrimitiveResultReference(identity, owner, entry_point, time,
                                        inputs, output, canonical_state, reason, result)

    @staticmethod
    def _missing(*, owner: str, name: str, time: datetime, reason: str) -> MissingPrerequisite:
        identity = _hash(("missing-prerequisite-v1", owner, name, _stamp(time), reason))
        return MissingPrerequisite(identity, owner, name, time, reason)

    @staticmethod
    def _request_state(state: OrchestrationState, request: SetupRequest) -> RequestEvaluationState:
        existing = next((item for item in state.request_states if item.request_id == request.id), None)
        if existing is not None:
            return existing
        return RequestEvaluationState(request.id, active_range=request.active_range)

    def _market_facts(self, *, context: EvaluationContext,
                      state: OrchestrationState,
                      traces: list[PrimitiveResultReference],
                      missing: list[MissingPrerequisite]) -> tuple[
                          tuple[FVG | IFVG, ...],
                          tuple[StructuralIngestionLedger, ...],
                      ]:
        zones: list[FVG | IFVG] = []
        ledgers = {item.timeframe: item for item in state.structural_ledgers}
        for timeframe in self.run.timeframes:
            frame = self.adapter.to_mechanical_swing_frame(
                symbol=self.run.symbol, timeframe=timeframe, as_of=context.evaluation_time,
            )
            mechanical = MechanicalSwingEngine().detect(timeframe=timeframe.value, candles=frame)
            traces.append(self._primitive(
                owner="#19", entry_point="p19_mechanical_swings.MechanicalSwingEngine.detect",
                time=context.evaluation_time, inputs=tuple(str(value) for value in frame.get("id", ())),
                result=mechanical,
            ))
            structural_ledger = ledgers.get(timeframe.value)
            existing = {
                fact.source_swing.id
                for fact in structural_ledger.availability_facts
            } if structural_ledger is not None else set()
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            for swing in mechanical.swings:
                if swing.id in existing:
                    continue
                # #19's two right-side bars make a pivot visible only at the
                # close of the second right-side candle: pivot open + 3 bars.
                available_at = epoch + timedelta(
                    milliseconds=swing.pivot_time,
                ) + timeframe.duration * 3
                if available_at > context.evaluation_time:
                    continue
                structural_ledger = StructuralStateProducer().ingest(
                    swing_result=MechanicalSwingResult(timeframe.value, (swing,)),
                    symbol=self.run.symbol, available_at=available_at,
                    source_version=self.dataset.schema_version,
                    calculation_version=self.calculation_version,
                    ledger=structural_ledger,
                )
                existing.add(swing.id)
            if structural_ledger is None:
                structural_ledger = StructuralStateProducer().ingest(
                    swing_result=MechanicalSwingResult(timeframe.value, ()),
                    symbol=self.run.symbol, available_at=context.evaluation_time,
                    source_version=self.dataset.schema_version,
                    calculation_version=self.calculation_version,
                )
            ledgers[timeframe.value] = structural_ledger
            traces.append(self._primitive(
                owner="#20",
                entry_point="p20_structural_state_producer.StructuralStateProducer.ingest",
                time=context.evaluation_time,
                inputs=tuple(item.id for item in mechanical.swings),
                result=structural_ledger,
                state=(
                    structural_ledger.current_snapshot.regime
                    if structural_ledger.current_snapshot is not None else None
                ),
                reason=(None if structural_ledger.classification_ready else "INITIALIZING"),
            ))
            if not structural_ledger.classification_ready:
                missing.append(self._missing(
                    owner="#20", name=f"CLASSIFICATION_READY_STRUCTURE:{timeframe.value}",
                    time=context.evaluation_time,
                    reason="Both canonical governing sides are not yet available.",
                ))
            mappings = self.adapter.to_candle_mappings(
                symbol=self.run.symbol, timeframe=timeframe, as_of=context.evaluation_time,
            )
            detected = FVGEngine(minimum_tick=self.minimum_tick).detect(
                timeframe=timeframe.value, candles=mappings,
            )
            traces.append(self._primitive(
                owner="#25", entry_point="p25_fvg_ifvg.FVGEngine.detect",
                time=context.evaluation_time, inputs=tuple(str(item["id"]) for item in mappings),
                result=detected,
            ))
            zones.extend(detected)
        return (
            tuple(sorted(zones, key=lambda zone: (zone.confirmation_time, zone.timeframe, zone.id))),
            tuple(ledgers[key] for key in sorted(ledgers)),
        )

    def _displacement_facts(
        self, *, context: EvaluationContext,
        structural_ledgers: tuple[StructuralIngestionLedger, ...],
        ledger: DisplacementLedger,
        traces: list[PrimitiveResultReference],
        missing: list[MissingPrerequisite],
    ) -> DisplacementLedger:
        producer = DisplacementQualificationProducer()
        policy = MechanicalDisplacementPolicy.owner_mechanical_v1(
            calculation_version=self.calculation_version
        )
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

        def converted(item) -> DisplacementCandle:
            return DisplacementCandle(
                str(item["id"]), str(item["s"]), str(item["i"]),
                epoch + timedelta(milliseconds=int(item["t"])),
                epoch + timedelta(milliseconds=int(item["T"])),
                item["o"], item["h"], item["l"], item["c"],
                self.dataset.dataset_id, self.run.id,
                self.dataset.schema_version, self.calculation_version,
                bool(item["is_closed"]),
            )

        for structural in structural_ledgers:
            state_before = structural.current_snapshot
            if state_before is None or not structural.classification_ready:
                continue
            timeframe = next(
                item for item in self.run.timeframes if item.value == structural.timeframe
            )
            mappings = self.adapter.to_candle_mappings(
                symbol=self.run.symbol, timeframe=timeframe,
                as_of=context.evaluation_time,
            )
            if not mappings:
                continue
            evaluation = converted(mappings[-1])
            references = tuple(converted(item) for item in mappings[-21:-1])
            contexts: list[object] = []
            if state_before.regime == StructuralRegime.INITIALIZING:
                contexts.extend((
                    producer.context(
                        state=state_before, symbol=self.run.symbol,
                        direction=StructuralRegime.BULLISH,
                        event_type=StructuralEventType.BOS,
                    ),
                    producer.context(
                        state=state_before, symbol=self.run.symbol,
                        direction=StructuralRegime.BEARISH,
                        event_type=StructuralEventType.BOS,
                    ),
                ))
            elif state_before.regime == StructuralRegime.BULLISH:
                contexts.append(producer.context(
                    state=state_before, symbol=self.run.symbol,
                    direction=StructuralRegime.BULLISH,
                    event_type=StructuralEventType.BOS,
                ))
                if state_before.protected_low is not None:
                    contexts.append(producer.context(
                        state=state_before, symbol=self.run.symbol,
                        direction=StructuralRegime.BEARISH,
                        event_type=StructuralEventType.MSS,
                    ))
            elif state_before.regime == StructuralRegime.BEARISH:
                contexts.append(producer.context(
                    state=state_before, symbol=self.run.symbol,
                    direction=StructuralRegime.BEARISH,
                    event_type=StructuralEventType.BOS,
                ))
                if state_before.protected_high is not None:
                    contexts.append(producer.context(
                        state=state_before, symbol=self.run.symbol,
                        direction=StructuralRegime.BULLISH,
                        event_type=StructuralEventType.MSS,
                    ))
            for candidate_context in contexts:
                qualification, ledger = producer.evaluate(
                    policy=policy, context=candidate_context,
                    state_before=state_before, evaluation_candle=evaluation,
                    reference_candles=references,
                    minimum_tick=self.minimum_tick,
                    dataset_id=self.dataset.dataset_id, run_id=self.run.id,
                    source_version=self.dataset.schema_version,
                    calculation_version=self.calculation_version,
                    ledger=ledger,
                )
                traces.append(self._primitive(
                    owner="#20",
                    entry_point="p20_displacement.DisplacementQualificationProducer.evaluate",
                    time=context.evaluation_time,
                    inputs=(state_before.id, evaluation.id, *(item.id for item in references)),
                    result=qualification, state=qualification.outcome,
                    reason=qualification.reason,
                ))
                if qualification.outcome == DisplacementOutcome.INSUFFICIENT_REFERENCE:
                    missing.append(self._missing(
                        owner="#20", name=f"DISPLACEMENT_REFERENCE:{timeframe.value}",
                        time=context.evaluation_time, reason=qualification.reason,
                    ))
                if qualification.qualified:
                    candidates = StructuralBreakQualifier().qualify(
                        state_before=state_before, candle=dict(mappings[-1]),
                        qualifying_displacement=qualification,
                    )
                    traces.append(self._primitive(
                        owner="#20",
                        entry_point="p20_structural_classification.StructuralBreakQualifier.qualify",
                        time=context.evaluation_time,
                        inputs=(qualification.id, state_before.id, evaluation.id),
                        result=candidates,
                    ))
        return ledger

    def _canonical_continuation_request(
        self, *, context: EvaluationContext,
        structural_ledgers: tuple[StructuralIngestionLedger, ...],
        displacement_ledger: DisplacementLedger,
        liquidity_ledger: StructuralLiquidityReferenceLedger,
        traces: list[PrimitiveResultReference],
    ) -> tuple[
        ContinuationEvaluationRequest | None,
        tuple[StructuralIngestionLedger, ...],
        StructuralLiquidityReferenceLedger,
    ]:
        """Commit a genuine same-batch BOS and expose its continuation context."""
        now = self._milliseconds(context.evaluation_time)
        candidates = tuple(
            record for record in displacement_ledger.records
            if record.qualified and record.active
            and record.available_at == context.evaluation_time
            and record.event_type == StructuralEventType.BOS
        )
        if not candidates:
            return None, structural_ledgers, liquidity_ledger
        ledgers = {item.timeframe: item for item in structural_ledgers}
        request = None
        # Every timeframe may advance its own canonical structure. Only an
        # accepted 5M BOS owns a continuation setup request.
        for record in sorted(candidates, key=lambda item: (item.timeframe, item.id)):
            source = ledgers.get(record.timeframe)
            if source is None or source.current_snapshot is None:
                continue
            before = source.current_snapshot
            if before.id != record.structural_snapshot_id:
                continue
            timeframe = next(item for item in self.run.timeframes if item.value == record.timeframe)
            mappings = self.adapter.to_candle_mappings(
                symbol=self.run.symbol, timeframe=timeframe,
                as_of=context.evaluation_time,
            )
            if not mappings:
                continue
            qualified = StructuralBreakQualifier().qualify(
                state_before=before, candle=dict(mappings[-1]),
                qualifying_displacement=record,
            )
            decision = ConflictResolver().resolve(
                state_before=before, candidates=qualified, processing_timestamp=now,
            )
            traces.append(self._primitive(
                owner="#16", entry_point="p16_conflict_resolution.ConflictResolver.resolve",
                time=context.evaluation_time, inputs=tuple(item.id for item in qualified),
                result=decision, state=decision.resolution_rule,
            ))
            if not decision.accepted_events:
                continue
            after = StructuralStateCommitter().commit(
                state_before=before, decision=decision,
            )
            traces.append(self._primitive(
                owner="#20", entry_point="p20_state_commit.StructuralStateCommitter.commit",
                time=context.evaluation_time, inputs=(before.id, decision.id),
                result=after, state=after.regime,
            ))
            event_id = decision.primary_structural_event_id
            assert event_id is not None
            active_range = ActiveDealingRangeEngine().update(
                state_after=after, accepted_structural_event_id=event_id,
                processing_timestamp=now,
            ).active_range
            if active_range is None:
                continue
            liquidity_ledger = StructuralLiquidityReferenceProducer().derive(
                structural_ledger=source, state_after=after,
                accepted_structural_event_id=event_id, active_range=active_range,
                symbol=self.run.symbol, dataset_id=self.dataset.dataset_id,
                run_id=self.run.id, source_version=self.dataset.schema_version,
                calculation_version=self.calculation_version,
                evaluation_time=context.evaluation_time, ledger=liquidity_ledger,
            )
            traces.append(self._primitive(
                owner="#23",
                entry_point=("p23_liquidity_reference_producer."
                             "StructuralLiquidityReferenceProducer.derive"),
                time=context.evaluation_time,
                inputs=(source.id, after.id, active_range.id), result=liquidity_ledger,
            ))
            mechanical = MechanicalSwingEngine().detect(
                timeframe=timeframe.value,
                candles=self.adapter.to_mechanical_swing_frame(
                    symbol=self.run.symbol, timeframe=timeframe,
                    as_of=context.evaluation_time,
                ),
            )
            ledgers[record.timeframe] = StructuralStateProducer().ingest(
                swing_result=mechanical, symbol=self.run.symbol,
                available_at=context.evaluation_time,
                source_version=self.dataset.schema_version,
                calculation_version=self.calculation_version,
                ledger=source, state_before=after,
            )
            if record.timeframe.lower() == "5m":
                request_id = _hash(("canonical-continuation-request-v1", event_id, after.id))
                request = ContinuationEvaluationRequest(
                    request_id, event_id, after.regime, after, active_range, (),
                    None, event_id,
                )
        return (
            request,
            tuple(ledgers[key] for key in sorted(ledgers)),
            liquidity_ledger,
        )

    def _cisd(self, *, request: ReversalEvaluationRequest,
              request_state: RequestEvaluationState, context: EvaluationContext,
              traces: list[PrimitiveResultReference]) -> CISDProcess:
        engine = CISDEngine()
        process = request_state.cisd_process
        now = self._milliseconds(context.evaluation_time)
        if process is None:
            process = engine.start(sequence=request.confirmation_sequence)
            traces.append(self._primitive(
                owner="#11", entry_point="p11_cisd_confirmation.CISDEngine.start",
                time=context.evaluation_time, inputs=(request.setup_candidate_id,),
                result=process, state=process.state,
            ))
        if request.invalidation_event_id is not None and process.state != CISDState.CONFIRMATION_TERMINATED:
            process = engine.terminate(
                process=process, invalidation_time=now,
                invalidation_reason=request.invalidation_event_id,
            )
            traces.append(self._primitive(
                owner="#11", entry_point="p11_cisd_confirmation.CISDEngine.terminate",
                time=context.evaluation_time, inputs=(request.invalidation_event_id,),
                result=process, state=process.state,
            ))
            return process
        if process.state == CISDState.WAITING_FOR_1M_CONFIRMATION:
            visible_legs = tuple(
                leg for leg in request.delivery_legs
                if leg.end_time is not None and leg.end_time <= now
            )
            process = engine.identify_reference(
                process=process, delivery_legs=visible_legs, as_of_time=now,
            )
            traces.append(self._primitive(
                owner="#11", entry_point="p11_cisd_confirmation.CISDEngine.identify_reference",
                time=context.evaluation_time,
                inputs=tuple(leg.id for leg in visible_legs),
                result=process, state=process.state,
                reason=getattr(process.non_confirmation_outcome, "value", None),
            ))
        if process.state == CISDState.CISD_REFERENCE_IDENTIFIED:
            process = engine.wait_for_body_close(process=process)
            traces.append(self._primitive(
                owner="#11", entry_point="p11_cisd_confirmation.CISDEngine.wait_for_body_close",
                time=context.evaluation_time, inputs=(request.setup_candidate_id,),
                result=process, state=process.state,
            ))
        if process.state == CISDState.WAITING_FOR_BODY_CLOSE:
            candles = self.adapter.to_delivery_candles(symbol=self.run.symbol, as_of=context.evaluation_time)
            for candle in candles:
                if process.last_evaluated_time is not None and candle.close_time <= process.last_evaluated_time:
                    continue
                if process.reference is not None and candle.close_time <= process.reference.reference_known_time:
                    continue
                evaluation = engine.evaluate(process=process, candle=candle)
                process = evaluation.process
                traces.append(self._primitive(
                    owner="#11", entry_point="p11_cisd_confirmation.CISDEngine.evaluate",
                    time=context.evaluation_time, inputs=(candle.id,), result=evaluation,
                    state=process.state,
                ))
                if process.state == CISDState.CISD_CONFIRMED:
                    break
        return process

    def _evaluate_request(self, *, request: SetupRequest, request_state: RequestEvaluationState,
                          context: EvaluationContext, zones: tuple[FVG | IFVG, ...],
                          derived_references: tuple[LiquidityReference, ...],
                          delivery_formation: ReversalDeliveryFormation | None,
                          traces: list[PrimitiveResultReference],
                          missing: list[MissingPrerequisite]) -> tuple[SetupStateFact, RequestEvaluationState]:
        now = self._milliseconds(context.evaluation_time)
        if (request.structural_state.as_of_timestamp is not None
                and request.structural_state.as_of_timestamp > now):
            raise ValueError("Future structural state is unavailable at evaluation time.")
        prior_range = request_state.active_range or request.active_range
        if prior_range is not None and prior_range.confirmation_time > now:
            raise ValueError("Future active range is unavailable at evaluation time.")
        range_result = ActiveDealingRangeEngine().update(
            state_after=request.structural_state,
            accepted_structural_event_id=request.accepted_structural_event_id,
            processing_timestamp=now,
            previous_active_range=prior_range,
        )
        traces.append(self._primitive(
            owner="#21", entry_point="p21_active_dealing_range.ActiveDealingRangeEngine.update",
            time=context.evaluation_time, inputs=(request.structural_state.id,), result=range_result,
            reason=getattr(range_result.error, "error_code", None),
        ))
        active_range = range_result.active_range
        ote_result = OTEEngine().update(
            active_range=active_range, previous_active_ote=request_state.active_ote,
            termination_event_id=request.invalidation_event_id,
        )
        traces.append(self._primitive(
            owner="#22", entry_point="p22_ote.OTEEngine.update",
            time=context.evaluation_time,
            inputs=(active_range.id if active_range else "NONE",), result=ote_result,
        ))
        active_ote = ote_result.active_ote
        combined = {
            reference.id: reference
            for reference in (*request.liquidity_references, *derived_references)
        }
        visible_references = tuple(
            combined[key] for key in sorted(combined)
            if combined[key].confirmation_time <= now
        )
        for reference in request.liquidity_references:
            if reference.confirmation_time > now:
                missing.append(self._missing(
                    owner="#23", name=f"FUTURE_LIQUIDITY_REFERENCE:{reference.id}",
                    time=context.evaluation_time,
                    reason="Reference is excluded until its confirmation timestamp.",
                ))
        inventory = LiquidityPoolEngine(minimum_tick=self.minimum_tick).build_inventory(
            references=visible_references, active_range=active_range,
        )
        traces.append(self._primitive(
            owner="#23", entry_point="p23_liquidity.LiquidityPoolEngine.build_inventory",
            time=context.evaluation_time,
            inputs=tuple(item.id for item in visible_references), result=inventory,
        ))
        current = self.adapter.to_candle_mappings(
            symbol=self.run.symbol, timeframe=self.run.timeframes[0], as_of=context.evaluation_time,
        )
        if not current:
            missing.append(self._missing(owner="#24", name="CURRENT_PRICE", time=context.evaluation_time,
                                         reason="No published candle is available for target selection."))
            return self._setup_fact(request, context, EvaluationOutcome.WAITING_MISSING_PREREQUISITE,
                                    None, "CURRENT_PRICE_MISSING"), replace(
                                        request_state, active_range=active_range, active_ote=active_ote)
        target_result = LRLSelectionEngine().select(
            pools=inventory.pools, current_price=current[-1]["c"], active_range=active_range,
            regime=request.direction, role=LRLRole.CONTINUATION_TARGET,
            selection_time=now, previous_active_lrl=request_state.active_lrl,
            setup_invalidated=request.invalidation_event_id is not None,
        )
        traces.append(self._primitive(
            owner="#24", entry_point="p24_lrl_selection.LRLSelectionEngine.select",
            time=context.evaluation_time, inputs=tuple(pool.id for pool in inventory.pools),
            result=target_result,
        ))
        target = target_result.active_lrl
        historical = request_state.historical_facts + tuple(
            item for item in (range_result.terminated_range, ote_result.terminated_ote,
                              target_result.terminated_lrl) if item is not None
        )
        cisd_process = request_state.cisd_process
        confluences: tuple[Confluence, ...] = ()
        if isinstance(request, ContinuationEvaluationRequest):
            if active_ote is not None:
                evaluations = tuple(
                    ConfluenceEngine().evaluate_ote(
                        ote=active_ote, imbalance=zone, evaluation_time=now,
                    ) for zone in zones
                )
                for evaluation in evaluations:
                    traces.append(self._primitive(
                        owner="#26", entry_point="p26_confluence.ConfluenceEngine.evaluate_ote",
                        time=context.evaluation_time,
                        inputs=(active_ote.id, getattr(evaluation.confluence, "secondary_object_id", "NONE")),
                        result=evaluation,
                    ))
                confluences = tuple(item.confluence for item in evaluations if item.confluence is not None)
            protected = (
                request.structural_state.protected_low
                if request.direction == StructuralRegime.BULLISH
                else request.structural_state.protected_high
            )
            phase = SetupQualificationEngine().qualify_continuation(
                setup_candidate_id=request.setup_candidate_id,
                state=ContinuationSetupState.CANDIDATE, direction=request.direction,
                protected_swing=protected, active_range=active_range, ote=active_ote,
                target_lrl=target, confluences=confluences, evaluation_time=now,
            )
            cisd_for_selection = None
        else:
            cisd_process = (
                None if request.delivery_source is not None
                and (delivery_formation is None
                     or delivery_formation.outcome != DeliveryFormationOutcome.READY)
                else self._cisd(
                    request=request, request_state=request_state,
                    context=context, traces=traces,
                )
            )
            phase = SetupQualificationEngine().qualify_reversal_1(
                setup_candidate_id=request.setup_candidate_id,
                state=ReversalSetupState.MSS_CONFIRMED, direction=request.direction,
                cisd_process=cisd_process, target_lrl=target, evaluation_time=now,
            )
            cisd_for_selection = cisd_process
        traces.append(self._primitive(
            owner="#27",
            entry_point=("p27_setup_qualification.SetupQualificationEngine.qualify_continuation"
                         if isinstance(request, ContinuationEvaluationRequest)
                         else "p27_setup_qualification.SetupQualificationEngine.qualify_reversal_1"),
            time=context.evaluation_time, inputs=(request.setup_candidate_id,),
            result=phase, state=phase.setup.state,
            reason=",".join(phase.setup.missing_prerequisites) or None,
        ))
        updated = RequestEvaluationState(request.id, active_range, active_ote, target,
                                         cisd_process, historical)
        if not phase.eligible_for_entry_zone_selection:
            for name in phase.setup.missing_prerequisites:
                missing.append(self._missing(owner="#27", name=name, time=context.evaluation_time,
                                             reason="Canonical Phase A prerequisite is unavailable."))
            outcome = (EvaluationOutcome.MSS_CISD_CONFIRMED
                       if isinstance(request, ReversalEvaluationRequest)
                       and cisd_process is not None and cisd_process.state == CISDState.CISD_CONFIRMED
                       else EvaluationOutcome.CANDIDATE)
            return self._setup_fact(
                request, context, outcome, phase.setup.state,
                ",".join(phase.setup.missing_prerequisites) or None,
                setup=phase.setup, target=target,
            ), updated
        selection = EntryZoneSelectionEngine(minimum_tick=self.minimum_tick).select(
            setup=phase.setup, candidates=zones, selection_time=now,
            cisd_process=cisd_for_selection,
        )
        traces.append(self._primitive(
            owner="#28", entry_point="p28_entry_zone_selection.EntryZoneSelectionEngine.select",
            time=context.evaluation_time, inputs=tuple(zone.id for zone in zones),
            result=selection, state=selection.state,
        ))
        if selection.selected_zone_id is None:
            missing.append(self._missing(owner="#28", name="ELIGIBLE_ENTRY_ZONE",
                                         time=context.evaluation_time,
                                         reason=selection.state.value))
            outcome = (
                EvaluationOutcome.MSS_CISD_CONFIRMED
                if isinstance(request, ReversalEvaluationRequest)
                and cisd_process is not None and cisd_process.state == CISDState.CISD_CONFIRMED
                else EvaluationOutcome.WAITING_MISSING_PREREQUISITE
            )
            return self._setup_fact(
                request, context, outcome, phase.setup.state,
                selection.state.value, setup=phase.setup,
                entry_zone=selection, target=target,
            ), updated
        stop_result = StopLossSelectionEngine(minimum_tick=self.minimum_tick).select(
            setup=phase.setup, entry_zone=selection, selection_time=now,
            protected_swing=(protected if isinstance(request, ContinuationEvaluationRequest) else None),
            qualifying_sweep=(request.qualifying_sweep if isinstance(request, ReversalEvaluationRequest) else None),
        )
        traces.append(self._primitive(
            owner="#13", entry_point="p13_stop_loss_selection.StopLossSelectionEngine.select",
            time=context.evaluation_time, inputs=(phase.setup.id, selection.id), result=stop_result,
            reason=getattr(stop_result.error, "reason", None),
        ))
        final = SetupQualificationEngine().finalize(
            phase_a_setup=phase.setup, entry_zone_selection=selection,
            stop_selection=stop_result.stop, target_lrl=target, finalized_time=now,
            risk_reward_policy=self.risk_reward_policy,
            source_version=self.run.trading_brain_contract_version,
            calculation_version=self.calculation_version,
        )
        final_state = getattr(final.qualification, "final_state", None)
        reason = getattr(final.error, "reason", None)
        traces.append(self._primitive(
            owner="#27", entry_point="p27_setup_qualification.SetupQualificationEngine.finalize",
            time=context.evaluation_time,
            inputs=(phase.setup.id, selection.id, _record_id(stop_result), _record_id(target)),
            result=final, state=final_state, reason=reason,
        ))
        if final.error is not None:
            outcome = EvaluationOutcome.INVALID_FAIL_CLOSED
        elif final_state in {ContinuationSetupState.REJECTED, ReversalSetupState.REJECTED}:
            outcome = EvaluationOutcome.REJECTED
        elif final_state == ContinuationSetupState.ARMED:
            outcome = EvaluationOutcome.ARMED_CONTINUATION
        elif final_state == ReversalSetupState.ENTRY_ZONE_ARMED:
            outcome = EvaluationOutcome.ENTRY_ZONE_ARMED_REVERSAL
        else:
            outcome = EvaluationOutcome.INVALID_FAIL_CLOSED
        return self._setup_fact(
            request, context, outcome, final_state, reason, setup=phase.setup,
            entry_zone=selection, stop=stop_result.stop, target=target,
            final_qualification=final.qualification,
        ), updated

    def _structural_liquidity_references(
        self, *, request: SetupRequest, context: EvaluationContext,
        structural_ledgers: tuple[StructuralIngestionLedger, ...],
        ledger: StructuralLiquidityReferenceLedger,
        traces: list[PrimitiveResultReference],
    ) -> StructuralLiquidityReferenceLedger:
        """Derive #23 inputs only for a provably compatible accepted #20/#21 handoff."""
        active_range = request.active_range
        source = next(
            (item for item in structural_ledgers
             if item.timeframe == request.structural_state.timeframe), None,
        )
        if (
            active_range is None or source is None or source.current_snapshot is None
            or request.structural_state.predecessor_state_id != source.current_snapshot.id
        ):
            return ledger
        result = StructuralLiquidityReferenceProducer().derive(
            structural_ledger=source, state_after=request.structural_state,
            accepted_structural_event_id=active_range.created_by_event_id,
            active_range=active_range, symbol=self.run.symbol,
            dataset_id=self.dataset.dataset_id, run_id=self.run.id,
            source_version=self.dataset.schema_version,
            calculation_version=self.calculation_version,
            evaluation_time=context.evaluation_time, ledger=ledger,
        )
        traces.append(self._primitive(
            owner="#23",
            entry_point=("p23_liquidity_reference_producer."
                         "StructuralLiquidityReferenceProducer.derive"),
            time=context.evaluation_time,
            inputs=(source.current_snapshot.id, request.structural_state.id,
                    active_range.id), result=result,
        ))
        return result

    def _prior_period_references(
        self, *, context: EvaluationContext, ledger: PriorPeriodReferenceLedger,
        traces: list[PrimitiveResultReference],
    ) -> PriorPeriodReferenceLedger:
        mappings = self.adapter.to_candle_mappings(
            symbol=self.run.symbol, timeframe=CanonicalTimeframe.M1,
            as_of=context.evaluation_time,
        )
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        candles = tuple(PriorPeriodCandle(
            str(item["id"]), str(item["s"]), str(item["i"]),
            epoch + timedelta(milliseconds=int(item["t"])),
            epoch + timedelta(milliseconds=int(item["T"])),
            item["o"], item["h"], item["l"], item["c"],
            self.dataset.dataset_id, self.run.id, self.dataset.schema_version,
            self.calculation_version, bool(item["is_closed"]),
        ) for item in mappings)
        evaluation, result = PriorPeriodLiquidityReferenceProducer().evaluate(
            candles=candles, evaluation_time=context.evaluation_time,
            account_timezone=self.account_timezone, symbol=self.run.symbol,
            dataset_id=self.dataset.dataset_id, run_id=self.run.id,
            policy_id=self.prior_period_policy_id,
            source_version=self.dataset.schema_version,
            calculation_version=self.calculation_version, ledger=ledger,
        )
        traces.append(self._primitive(
            owner="#23",
            entry_point=("p23_prior_period_references."
                         "PriorPeriodLiquidityReferenceProducer.evaluate"),
            time=context.evaluation_time,
            inputs=tuple(item.id for item in candles), result=evaluation,
            reason=",".join(sorted({item.outcome.value for item in evaluation.statuses})),
        ))
        return result

    def _consume_visible_liquidity(
        self, *, request: SetupRequest | None, context: EvaluationContext,
        structural: StructuralLiquidityReferenceLedger,
        prior_period: PriorPeriodReferenceLedger,
        traces: list[PrimitiveResultReference],
    ) -> tuple[StructuralLiquidityReferenceLedger, PriorPeriodReferenceLedger]:
        enabled_prior = tuple(
            reference for reference in prior_period.active_references
            if PriorPeriodReferenceType(reference.source_type)
            in self.enabled_prior_period_reference_types
        )
        references = structural.active_references + enabled_prior
        inventory = LiquidityPoolEngine(minimum_tick=self.minimum_tick).build_inventory(
            references=references,
            active_range=(request.active_range if request is not None else None),
        )
        mappings = self.adapter.to_candle_mappings(
            symbol=self.run.symbol, timeframe=CanonicalTimeframe.M1,
            as_of=context.evaluation_time,
        )
        if not mappings:
            return structural, prior_period
        candle = dict(mappings[-1])
        for pool in inventory.pools:
            # The event candle must begin no earlier than pool availability;
            # a same-batch structural confirmation cannot retroactively sweep.
            if int(candle["t"]) < pool.confirmation_time:
                continue
            interaction = LiquidityInteractionEngine.evaluate(
                pool=pool, candle=candle, event_timeframe="1m",
            )
            traces.append(self._primitive(
                owner="#23",
                entry_point="p23_liquidity.LiquidityInteractionEngine.evaluate",
                time=context.evaluation_time, inputs=(pool.id, str(candle["id"])),
                result=interaction,
                state=interaction.pool.state,
                reason=(interaction.event.outcome.value if interaction.event else None),
            ))
            if interaction.event is None:
                continue
            for reference_id in pool.component_reference_ids:
                if any(item.reference.id == reference_id for item in structural.facts):
                    structural = StructuralLiquidityReferenceProducer().consume(
                        reference_id=reference_id, interaction=interaction,
                        consumption_time=context.evaluation_time, ledger=structural,
                    )
                if any(item.reference.id == reference_id for item in prior_period.facts):
                    _, prior_period = PriorPeriodLiquidityReferenceProducer().consume(
                        reference_id=reference_id, interaction=interaction,
                        consumption_time=context.evaluation_time, ledger=prior_period,
                    )
        return structural, prior_period

    def _reversal_delivery_formation(
        self, *, request: ReversalEvaluationRequest,
        context: EvaluationContext, ledger: ReversalDeliveryLedger,
        traces: list[PrimitiveResultReference],
    ) -> tuple[ReversalDeliveryFormation, ReversalDeliveryLedger]:
        source = request.delivery_source
        if source is None:
            raise ValueError("A genuine reversal delivery source is required.")
        mappings = self.adapter.to_candle_mappings(
            symbol=self.run.symbol, timeframe=CanonicalTimeframe.M1,
            as_of=context.evaluation_time,
        )
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        candles = tuple(DisplacementCandle(
            str(item["id"]), str(item["s"]), str(item["i"]),
            epoch + timedelta(milliseconds=int(item["t"])),
            epoch + timedelta(milliseconds=int(item["T"])),
            item["o"], item["h"], item["l"], item["c"],
            self.dataset.dataset_id, self.run.id, self.dataset.schema_version,
            self.calculation_version, bool(item["is_closed"]),
        ) for item in mappings)
        record, result_ledger = ReversalDeliveryLegProducer().form(
            setup_candidate_id=request.setup_candidate_id,
            structural_state=source.structural_state,
            reversal_lrl=source.reversal_lrl, sweep=source.sweep,
            mss_decision=source.mss_decision,
            displacement=source.displacement, candles=candles,
            evaluation_time=context.evaluation_time, symbol=self.run.symbol,
            dataset_id=self.dataset.dataset_id, run_id=self.run.id,
            source_version=self.dataset.schema_version,
            calculation_version=self.calculation_version,
            configuration_version=self.run.model_configuration_version,
            ledger=ledger,
        )
        traces.append(self._primitive(
            owner="#11",
            entry_point=("p11_delivery_leg_producer."
                         "ReversalDeliveryLegProducer.form"),
            time=context.evaluation_time,
            inputs=(source.reversal_lrl.id, source.mss_decision.id,
                    source.displacement.id), result=record,
            state=record.outcome, reason=record.reason,
        ))
        return record, result_ledger

    @staticmethod
    def _setup_fact(request: SetupRequest | None, context: EvaluationContext,
                    outcome: EvaluationOutcome, canonical_state: object | None,
                    reason: str | None, *, setup: object | None = None,
                    entry_zone: object | None = None, stop: object | None = None,
                    target: LRL | None = None,
                    final_qualification: object | None = None) -> SetupStateFact:
        request_id = request.id if request is not None else None
        model = (SetupModel.CONTINUATION if isinstance(request, ContinuationEvaluationRequest)
                 else SetupModel.REVERSAL_1 if isinstance(request, ReversalEvaluationRequest) else None)
        identity = _hash(("setup-state-fact-v1", context.id, request_id or "NONE",
                          outcome.value, getattr(canonical_state, "value", str(canonical_state)),
                          reason or "", _record_id(setup), _record_id(entry_zone),
                          _record_id(stop), _record_id(target), _record_id(final_qualification)))
        return SetupStateFact(identity, request_id, model, outcome, canonical_state,
                              reason, setup, entry_zone, stop, target,
                              final_qualification, context.evaluation_time)

    def evaluate(self, *, publication: ReplayPublication, state: OrchestrationState,
                 request: SetupRequest | None = None) -> OrchestrationCommit:
        self._validate(publication=publication, state=state)
        batch = publication.batch
        request_fingerprint = _hash(("setup-request-v1", repr(request)))
        if state.last_batch_sequence == batch.sequence:
            previous = next((item for item in state.batch_results
                             if item.context.replay_batch_id == batch.id), None)
            if previous is None:
                raise ValueError("Conflicting duplicate batch evaluation.")
            if previous.request_fingerprint != request_fingerprint:
                raise ValueError("Conflicting duplicate setup request evaluation.")
            return OrchestrationCommit(state, previous)
        context = self._context(publication)
        traces: list[PrimitiveResultReference] = []
        missing: list[MissingPrerequisite] = []
        zones, structural_ledgers = self._market_facts(
            context=context, state=state, traces=traces, missing=missing,
        )
        displacement_ledger = self._displacement_facts(
            context=context, structural_ledgers=structural_ledgers,
            ledger=state.displacement_ledger, traces=traces, missing=missing,
        )
        prior_period_reference_ledger = self._prior_period_references(
            context=context, ledger=state.prior_period_reference_ledger,
            traces=traces,
        )
        liquidity_reference_ledger = state.liquidity_reference_ledger
        reversal_delivery_ledger = state.reversal_delivery_ledger
        delivery_formation = None
        request_states = list(state.request_states)
        active_requests = list(state.active_requests)
        if self.canonical_mode:
            generated, structural_ledgers, liquidity_reference_ledger = (
                self._canonical_continuation_request(
                    context=context, structural_ledgers=structural_ledgers,
                    displacement_ledger=displacement_ledger,
                    liquidity_ledger=liquidity_reference_ledger,
                    traces=traces,
                )
            )
            if generated is not None:
                # A later accepted structural event owns a new immutable setup
                # context; earlier waiting contexts remain in history but are
                # no longer evaluated as active candidates.
                active_requests = [generated]
            if request is None and active_requests:
                request = sorted(active_requests, key=lambda item: item.id)[0]
                request_fingerprint = _hash(("setup-request-v1", repr(request)))
        if self.canonical_mode:
            liquidity_reference_ledger, prior_period_reference_ledger = (
                self._consume_visible_liquidity(
                    request=request, context=context,
                    structural=liquidity_reference_ledger,
                    prior_period=prior_period_reference_ledger,
                    traces=traces,
                )
            )
        if request is None:
            setup_fact = self._setup_fact(None, context, EvaluationOutcome.NO_SETUP, None, None)
        else:
            if not request.id.strip() or request.setup_candidate_id == "":
                raise ValueError("Setup request identities are required.")
            current_state = self._request_state(state, request)
            try:
                liquidity_reference_ledger = self._structural_liquidity_references(
                    request=request, context=context,
                    structural_ledgers=structural_ledgers,
                    ledger=liquidity_reference_ledger, traces=traces,
                )
                if (isinstance(request, ReversalEvaluationRequest)
                        and request.delivery_source is not None
                        and request.delivery_source.displacement.available_at
                            <= context.evaluation_time):
                    delivery_formation, reversal_delivery_ledger = self._reversal_delivery_formation(
                        request=request, context=context,
                        ledger=reversal_delivery_ledger, traces=traces,
                    )
                    if delivery_formation.outcome == DeliveryFormationOutcome.READY:
                        request = replace(
                            request,
                            confirmation_sequence=delivery_formation.sequence,
                            delivery_legs=(delivery_formation.delivery_leg,),
                        )
                setup_fact, updated_request = self._evaluate_request(
                    request=request, request_state=current_state, context=context,
                    zones=zones,
                    derived_references=(
                        liquidity_reference_ledger.active_references
                        + tuple(
                            reference
                            for reference in prior_period_reference_ledger.active_references
                            if PriorPeriodReferenceType(reference.source_type)
                            in self.enabled_prior_period_reference_types
                        )
                    ),
                    delivery_formation=delivery_formation,
                    traces=traces, missing=missing,
                )
            except (TypeError, ValueError) as error:
                missing.append(self._missing(owner="ORCHESTRATOR", name="CANONICAL_INPUT_VALIDATION",
                                             time=context.evaluation_time, reason=str(error)))
                setup_fact = self._setup_fact(
                    request, context, EvaluationOutcome.INVALID_FAIL_CLOSED,
                    None, str(error),
                )
                updated_request = current_state
            request_states = [item for item in request_states if item.request_id != request.id]
            request_states.append(updated_request)
            request_states.sort(key=lambda item: item.request_id)
            if self.canonical_mode and setup_fact.outcome in {
                EvaluationOutcome.ARMED_CONTINUATION,
                EvaluationOutcome.ENTRY_ZONE_ARMED_REVERSAL,
                EvaluationOutcome.REJECTED,
                EvaluationOutcome.INVALID_FAIL_CLOSED,
            }:
                active_requests = [item for item in active_requests if item.id != request.id]
        trace_id = _hash(("evaluation-trace-v1", context.id,
                          *(item.id for item in traces), *(item.id for item in missing)))
        trace = EvaluationTrace(trace_id, context.id, tuple(traces), tuple(missing))
        result_id = _hash(("batch-evaluation-v1", context.id, setup_fact.id, trace.id))
        result = BatchEvaluationResult(
            result_id, context, setup_fact.outcome, trace, setup_fact,
            tuple(event.candle_id for event in batch.events),
            request_fingerprint,
        )
        state_id = _hash(("orchestration-state-v1", state.id, result.id,
                          str(batch.sequence), _stamp(batch.event_time)))
        next_state = OrchestrationState(
            id=state_id, dataset_id=state.dataset_id,
            dataset_fingerprint=state.dataset_fingerprint, run_id=state.run_id,
            trading_brain_contract_version=state.trading_brain_contract_version,
            calculation_version=state.calculation_version,
            last_batch_sequence=batch.sequence,
            last_evaluation_time=batch.event_time,
            structural_ledgers=structural_ledgers,
            displacement_ledger=displacement_ledger,
            liquidity_reference_ledger=liquidity_reference_ledger,
            reversal_delivery_ledger=reversal_delivery_ledger,
            prior_period_reference_ledger=prior_period_reference_ledger,
            request_states=tuple(request_states),
            batch_results=state.batch_results + (result,),
            active_requests=tuple(sorted(active_requests, key=lambda item: item.id)),
        )
        return OrchestrationCommit(next_state, result)

    def checkpoint(self, *, state: OrchestrationState,
                   replay_checkpoint: ReplayCheckpoint) -> OrchestrationCheckpoint:
        if (state.dataset_id, state.dataset_fingerprint, state.run_id,
            state.trading_brain_contract_version) != (
                replay_checkpoint.dataset_id, replay_checkpoint.dataset_fingerprint,
                replay_checkpoint.run_id, replay_checkpoint.trading_brain_contract_version):
            raise ValueError("Replay and orchestration checkpoint identities mismatch.")
        expected_cursor = 0 if state.last_batch_sequence is None else state.last_batch_sequence + 1
        if replay_checkpoint.next_batch_sequence != expected_cursor:
            raise ValueError("Replay checkpoint cursor is incompatible with orchestration state.")
        identity = _hash(("orchestration-checkpoint-v1", state.id,
                          replay_checkpoint.event_sequence_id,
                          str(replay_checkpoint.next_batch_sequence), self.calculation_version))
        return OrchestrationCheckpoint(
            identity, self.CHECKPOINT_VERSION, state.id, state.dataset_id,
            state.dataset_fingerprint, state.run_id,
            state.trading_brain_contract_version, state.calculation_version,
            state.last_batch_sequence, replay_checkpoint,
        )

    def validate_resume(self, *, state: OrchestrationState,
                        checkpoint: OrchestrationCheckpoint,
                        replay_checkpoint: ReplayCheckpoint) -> None:
        expected = self.checkpoint(state=state, replay_checkpoint=replay_checkpoint)
        if checkpoint != expected:
            raise ValueError("Orchestration checkpoint or state is incompatible.")
