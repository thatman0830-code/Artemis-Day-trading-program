from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256

from strategy.trading_brain.p11_cisd_confirmation import (
    CISDDirection, DeliveryCandle, DeliveryLeg, ReversalConfirmationSequence,
)
from strategy.trading_brain.p16_conflict_resolution import StructuralResolutionDecision
from strategy.trading_brain.p20_displacement import DisplacementCandle, DisplacementQualification
from strategy.trading_brain.p20_structural_classification import (
    StructuralEventType, StructuralRegime, StructuralStateSnapshot,
)
from strategy.trading_brain.p23_liquidity import (
    LiquidityInteractionResult, LiquiditySide, LiquidityState,
)
from strategy.trading_brain.p24_lrl_selection import LRL, LRLRole


class DeliveryFormationOutcome(str, Enum):
    READY = "READY"
    NOT_CONFIRMABLE = "NOT_CONFIRMABLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INVALID_INPUT = "INVALID_INPUT"
    UPSTREAM_INVALID = "UPSTREAM_INVALID"


@dataclass(frozen=True)
class ReversalDeliverySource:
    structural_state: StructuralStateSnapshot
    reversal_lrl: LRL
    sweep: LiquidityInteractionResult
    mss_decision: StructuralResolutionDecision
    displacement: DisplacementQualification


@dataclass(frozen=True)
class ReversalDeliveryFormation:
    id: str
    evaluation_key: str
    outcome: DeliveryFormationOutcome
    reason: str
    setup_candidate_id: str
    intended_direction: CISDDirection
    prior_regime: StructuralRegime
    lrl_id: str
    liquidity_pool_id: str
    sweep_id: str
    mss_decision_id: str
    mss_event_id: str
    structural_state_id: str
    displacement_id: str
    ordered_source_candle_ids: tuple[str, ...]
    source_candles: tuple[DisplacementCandle, ...]
    delivery_leg: DeliveryLeg | None
    sequence: ReversalConfirmationSequence | None
    occurrence_time: datetime
    available_at: datetime
    symbol: str
    timeframe: str
    dataset_id: str
    run_id: str
    source_version: str
    calculation_version: str
    configuration_version: str
    active: bool = True
    historical: bool = False
    invalidation_time: datetime | None = None
    invalidation_reason: str | None = None


@dataclass(frozen=True)
class ReversalDeliveryTransition:
    id: str
    formation_id: str
    predecessor_record_id: str
    successor_record_id: str
    transition_time: datetime
    reason: str


@dataclass(frozen=True)
class ReversalDeliveryLedger:
    records: tuple[ReversalDeliveryFormation, ...] = ()
    transitions: tuple[ReversalDeliveryTransition, ...] = ()


def _hash(*parts: object) -> str:
    return sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC timezone-aware.")
    return value.astimezone(timezone.utc)


def _ms(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = value - epoch
    return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000


def _from_ms(value: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=value)


class ReversalDeliveryLegProducer:
    """Owner-approved mechanical Reversal #1 delivery formation for #11 only."""

    TIMEFRAME = "1m"

    @staticmethod
    def _direction(candle: DisplacementCandle) -> CISDDirection | None:
        if candle.close > candle.open:
            return CISDDirection.BULLISH
        if candle.close < candle.open:
            return CISDDirection.BEARISH
        return None

    @staticmethod
    def _expected(state: StructuralStateSnapshot) -> tuple[CISDDirection, LiquiditySide]:
        if state.regime == StructuralRegime.BEARISH:
            return CISDDirection.BULLISH, LiquiditySide.LSL
        if state.regime == StructuralRegime.BULLISH:
            return CISDDirection.BEARISH, LiquiditySide.BSL
        raise ValueError("Reversal #1 requires a directional prior structural regime.")

    @staticmethod
    def _valid_candle(candle: DisplacementCandle, lineage: tuple[str, ...]) -> bool:
        values = (candle.open, candle.high, candle.low, candle.close)
        try:
            _utc(candle.open_time, "open_time")
            _utc(candle.close_time, "close_time")
        except ValueError:
            return False
        return bool(
            candle.id and candle.is_closed and candle.timeframe.lower() == "1m"
            and (candle.symbol, candle.dataset_id, candle.run_id,
                 candle.source_version, candle.calculation_version) == lineage
            and candle.open_time < candle.close_time
            and candle.close_time - candle.open_time == timedelta(minutes=1)
            and all(isinstance(value, Decimal) and value.is_finite() for value in values)
            and candle.low > 0 and candle.high >= candle.low
            and candle.low <= candle.open <= candle.high
            and candle.low <= candle.close <= candle.high
        )

    @staticmethod
    def _accepted_mss(decision: StructuralResolutionDecision):
        accepted = decision.accepted_events
        if len(accepted) != 1:
            return None
        event = accepted[0]
        if event.id != decision.primary_structural_event_id:
            return None
        return event if event.source_candidate.event_type == StructuralEventType.MSS else None

    def form(
        self, *, setup_candidate_id: str, structural_state: StructuralStateSnapshot,
        reversal_lrl: LRL, sweep: LiquidityInteractionResult,
        mss_decision: StructuralResolutionDecision,
        displacement: DisplacementQualification,
        candles: tuple[DisplacementCandle, ...], evaluation_time: datetime,
        symbol: str, dataset_id: str, run_id: str, source_version: str,
        calculation_version: str, configuration_version: str,
        ledger: ReversalDeliveryLedger | None = None,
    ) -> tuple[ReversalDeliveryFormation, ReversalDeliveryLedger]:
        ledger = ledger or ReversalDeliveryLedger()
        evaluation_time = _utc(evaluation_time, "evaluation_time")
        if not all(isinstance(item, str) and item.strip() for item in (
            setup_candidate_id, symbol, dataset_id, run_id, source_version,
            calculation_version, configuration_version,
        )):
            raise ValueError("Complete delivery-formation identity/version lineage is required.")
        intended, required_side = self._expected(structural_state)
        event = sweep.event
        accepted = self._accepted_mss(mss_decision)
        event_id = event.id if event is not None else "NONE"
        accepted_id = accepted.id if accepted is not None else "NONE"
        key = _hash(
            "#11-delivery-evaluation-v1", setup_candidate_id, reversal_lrl.id,
            event_id, mss_decision.id, accepted_id, structural_state.id,
            displacement.id, symbol, dataset_id, run_id, source_version,
            calculation_version, configuration_version,
        )
        latest = next((item for item in reversed(ledger.records)
                       if item.evaluation_key == key), None)
        lineage = (symbol, dataset_id, run_id, source_version, calculation_version)
        ordered = tuple(candles)
        record_ordered = ordered
        outcome, reason = DeliveryFormationOutcome.INVALID_INPUT, "INPUT_VALIDATION_FAILED"
        leg = None
        sequence = None
        occurrence = evaluation_time
        available = evaluation_time

        upstream_compatible = bool(
            event is not None and accepted is not None
            and reversal_lrl.role == LRLRole.REVERSAL_SWEEP_REFERENCE
            and reversal_lrl.pool_id == sweep.pool.id == event.pool_id
            and reversal_lrl.side == sweep.pool.side == event.side == required_side
            and event.outcome == LiquidityState.SWEPT
            and event.final_state == LiquidityState.CONSUMED
            and sweep.pool.state == LiquidityState.CONSUMED
            and mss_decision.pre_state_id == structural_state.id
            and mss_decision.timeframe.lower() == self.TIMEFRAME
            and accepted.source_candidate.state_before_id == structural_state.id
            and accepted.source_candidate.direction.value == intended.value
            and displacement.qualified and displacement.active
            and displacement.event_type == StructuralEventType.MSS
            and displacement.direction.value == intended.value
            and displacement.structural_snapshot_id == structural_state.id
            and displacement.structural_candidate_id == accepted.source_candidate.id
            and displacement.symbol == symbol
            and displacement.timeframe.lower() == self.TIMEFRAME
            and (displacement.dataset_id, displacement.run_id,
                 displacement.source_version, displacement.calculation_version)
                == (dataset_id, run_id, source_version, calculation_version)
            and event.event_timeframe.lower() == self.TIMEFRAME
            and event.event_time <= mss_decision.processing_timestamp
        )
        if not upstream_compatible:
            outcome, reason = DeliveryFormationOutcome.UPSTREAM_INVALID, "LRL_SWEEP_MSS_DISPLACEMENT_LINEAGE_INVALID"
        elif not ordered:
            outcome, reason = DeliveryFormationOutcome.INSUFFICIENT_HISTORY, "NO_PUBLISHED_1M_HISTORY"
        elif any(not self._valid_candle(item, lineage) for item in ordered):
            outcome, reason = DeliveryFormationOutcome.INVALID_INPUT, "CANDLE_IDENTITY_VERSION_TIMEFRAME_OR_GEOMETRY_INVALID"
        elif len({item.id for item in ordered}) != len(ordered):
            outcome, reason = DeliveryFormationOutcome.INVALID_INPUT, "DUPLICATE_CANDLE_IDENTITY"
        elif ordered != tuple(sorted(ordered, key=lambda item: (item.open_time, item.id))):
            outcome, reason = DeliveryFormationOutcome.INVALID_INPUT, "CANDLES_NOT_CANONICALLY_ORDERED"
        elif any(item.close_time > evaluation_time for item in ordered):
            outcome, reason = DeliveryFormationOutcome.INVALID_INPUT, "FUTURE_OR_UNAVAILABLE_CANDLE"
        else:
            by_open = {_ms(item.open_time): index for index, item in enumerate(ordered)}
            mss_index = by_open.get(mss_decision.processing_timestamp)
            sweep_index = by_open.get(event.event_time)
            if mss_index is None or sweep_index is None:
                outcome, reason = DeliveryFormationOutcome.INSUFFICIENT_HISTORY, "SWEEP_OR_MSS_1M_CANDLE_UNAVAILABLE"
            elif ordered[mss_index].id != displacement.evaluation_candle_id:
                outcome, reason = DeliveryFormationOutcome.UPSTREAM_INVALID, "MSS_CANDLE_IDENTITY_MISMATCH"
            elif sweep_index > mss_index:
                outcome, reason = DeliveryFormationOutcome.UPSTREAM_INVALID, "MSS_PRECEDES_QUALIFYING_SWEEP"
            elif self._direction(ordered[mss_index]) != intended:
                outcome, reason = DeliveryFormationOutcome.UPSTREAM_INVALID, "MSS_CANDLE_DIRECTION_MISMATCH"
            elif mss_index == 0:
                outcome, reason = DeliveryFormationOutcome.INSUFFICIENT_HISTORY, "OPPOSING_DELIVERY_HISTORY_UNAVAILABLE"
            else:
                opposing = (CISDDirection.BEARISH if intended == CISDDirection.BULLISH
                            else CISDDirection.BULLISH)
                end = mss_index - 1
                if ordered[end].close_time != ordered[mss_index].open_time:
                    outcome, reason = DeliveryFormationOutcome.INSUFFICIENT_HISTORY, "GAP_BEFORE_REVERSAL_DELIVERY"
                elif self._direction(ordered[end]) != opposing:
                    outcome, reason = DeliveryFormationOutcome.NOT_CONFIRMABLE, "IMMEDIATELY_PRECEDING_DELIVERY_NOT_OPPOSING"
                else:
                    start = end
                    while start > 0:
                        prior, current = ordered[start - 1], ordered[start]
                        if prior.close_time != current.open_time:
                            outcome, reason = DeliveryFormationOutcome.INSUFFICIENT_HISTORY, "GAP_INSIDE_REQUIRED_DELIVERY_CONTEXT"
                            break
                        if self._direction(prior) != opposing:
                            break
                        start -= 1
                    else:
                        outcome, reason = DeliveryFormationOutcome.INSUFFICIENT_HISTORY, "DELIVERY_START_OUTSIDE_DATASET"
                    if outcome not in {DeliveryFormationOutcome.INSUFFICIENT_HISTORY} or reason == "INPUT_VALIDATION_FAILED":
                        boundary = ordered[start - 1] if start > 0 else None
                        if boundary is None:
                            outcome, reason = DeliveryFormationOutcome.INSUFFICIENT_HISTORY, "DELIVERY_START_OUTSIDE_DATASET"
                        elif boundary.close_time != ordered[start].open_time:
                            outcome, reason = DeliveryFormationOutcome.INSUFFICIENT_HISTORY, "GAP_AT_DELIVERY_START_BOUNDARY"
                        elif self._direction(boundary) == opposing:
                            outcome, reason = DeliveryFormationOutcome.INVALID_INPUT, "DELIVERY_START_NOT_MAXIMAL"
                        else:
                            source = ordered[start:mss_index]
                            record_ordered = ordered[start - 1:mss_index + 1]
                            delivery = tuple(DeliveryCandle(
                                item.id, self.TIMEFRAME, item.open, item.high,
                                item.low, item.close, _ms(item.close_time), True,
                            ) for item in source)
                            leg_id = _hash(
                                "#11-delivery-leg-v1", setup_candidate_id,
                                reversal_lrl.id, event.id, mss_decision.id,
                                accepted.id, displacement.id, *(item.id for item in source),
                                symbol, dataset_id, run_id, source_version,
                                calculation_version, configuration_version,
                            )
                            leg = DeliveryLeg(
                                leg_id, setup_candidate_id, self.TIMEFRAME,
                                opposing, delivery, True, True,
                            )
                            sweep_close = ordered[sweep_index].close_time
                            mss_close = ordered[mss_index].close_time
                            sequence = ReversalConfirmationSequence(
                                setup_candidate_id, intended,
                                structural_state.regime, event.id, event.side,
                                _ms(sweep_close), accepted.id, _ms(mss_close), True,
                            )
                            occurrence = mss_close
                            available = max(
                                displacement.available_at,
                                mss_close, sweep_close,
                                _from_ms(reversal_lrl.selected_time),
                                *(item.close_time for item in source),
                            )
                            if available > evaluation_time:
                                outcome, reason = DeliveryFormationOutcome.INVALID_INPUT, "UPSTREAM_FACT_NOT_YET_AVAILABLE"
                                leg = sequence = None
                            else:
                                outcome, reason = DeliveryFormationOutcome.READY, "CONTIGUOUS_OPPOSING_DELIVERY_FROZEN"

        record_id = _hash(key, outcome.value, reason,
                          *(item.id for item in record_ordered), getattr(leg, "id", "NONE"))
        record = ReversalDeliveryFormation(
            record_id, key, outcome, reason, setup_candidate_id, intended,
            structural_state.regime, reversal_lrl.id, reversal_lrl.pool_id,
            event_id, mss_decision.id, accepted_id, structural_state.id,
            displacement.id, tuple(item.id for item in record_ordered), record_ordered, leg, sequence,
            occurrence, available, symbol, self.TIMEFRAME, dataset_id, run_id,
            source_version, calculation_version, configuration_version,
        )
        if latest is not None:
            if not latest.active:
                return latest, ledger
            if latest != record:
                raise ValueError("Conflicting delivery-formation identity.")
            return latest, ledger
        return record, ReversalDeliveryLedger(ledger.records + (record,), ledger.transitions)

    @staticmethod
    def invalidate(
        *, record: ReversalDeliveryFormation, invalidation_time: datetime,
        reason: str, ledger: ReversalDeliveryLedger,
    ) -> tuple[ReversalDeliveryFormation, ReversalDeliveryLedger]:
        invalidation_time = _utc(invalidation_time, "invalidation_time")
        if record not in ledger.records or not reason.strip():
            raise ValueError("Active ledger record and invalidation reason are required.")
        latest = next(item for item in reversed(ledger.records)
                      if item.evaluation_key == record.evaluation_key)
        if not latest.active:
            return latest, ledger
        if invalidation_time < latest.available_at:
            raise ValueError("A delivery leg cannot be invalidated before availability.")
        historical = replace(
            latest, id=_hash(latest.id, "historical", reason,
                             invalidation_time.isoformat()), active=False,
            historical=True, invalidation_time=invalidation_time,
            invalidation_reason=reason,
        )
        transition = ReversalDeliveryTransition(
            _hash("#11-delivery-transition-v1", latest.id, historical.id, reason),
            latest.id, latest.id, historical.id, invalidation_time, reason,
        )
        return historical, ReversalDeliveryLedger(
            ledger.records + (historical,), ledger.transitions + (transition,),
        )
