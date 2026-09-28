from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p23_liquidity import LiquiditySide
from strategy.trading_brain.p25_fvg_ifvg import FVG, IFVG, FVGDirection


class CISDState(str, Enum):
    WAITING_FOR_1M_CONFIRMATION = "WAITING_FOR_1M_CONFIRMATION"
    CISD_REFERENCE_IDENTIFIED = "CISD_REFERENCE_IDENTIFIED"
    WAITING_FOR_BODY_CLOSE = "WAITING_FOR_BODY_CLOSE"
    CISD_CONFIRMED = "CISD_CONFIRMED"
    CONFIRMATION_TERMINATED = "CONFIRMATION_TERMINATED"


class CISDDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class CISDNonConfirmationOutcome(str, Enum):
    NOT_CONFIRMABLE = "NOT_CONFIRMABLE"
    INVALID_CISD_REFERENCE = "INVALID_CISD_REFERENCE"


@dataclass(frozen=True)
class DeliveryCandle:
    id: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    close_time: int
    is_closed: bool = True


@dataclass(frozen=True)
class DeliveryLeg:
    id: str
    setup_candidate_id: str
    timeframe: str
    direction: CISDDirection
    candles: tuple[DeliveryCandle, ...]
    directly_precedes_reversal_delivery: bool
    confirmed: bool = True

    @property
    def initiating_candle(self) -> DeliveryCandle | None:
        return min(self.candles, key=lambda candle: candle.close_time) if self.candles else None

    @property
    def end_time(self) -> int | None:
        return max((candle.close_time for candle in self.candles), default=None)


@dataclass(frozen=True)
class ReversalConfirmationSequence:
    setup_candidate_id: str
    intended_direction: CISDDirection
    prior_regime: StructuralRegime
    sweep_id: str
    sweep_side: LiquiditySide
    sweep_time: int
    mss_id: str
    mss_confirmation_time: int
    mss_accepted: bool


@dataclass(frozen=True)
class CISDReference:
    delivery_leg_id: str
    delivery_candle_id: str
    delivery_candle_direction: CISDDirection
    reference_price: Decimal
    reference_known_time: int


@dataclass(frozen=True)
class CISDConfirmation:
    id: str
    setup_candidate_id: str
    timeframe: str
    direction: CISDDirection
    delivery_leg_id: str
    delivery_candle_id: str
    delivery_candle_direction: CISDDirection
    reference_price: Decimal
    confirmation_candle_id: str
    confirmation_close: Decimal
    confirmation_time: int
    body_close_confirmed: bool
    associated_mss_id: str
    associated_sweep_id: str
    same_candle_as_mss: bool
    valid: bool
    active_for_setup: bool
    invalidation_time: int | None
    invalidation_reason: str | None
    historical: bool
    immutable: bool = True


@dataclass(frozen=True)
class CISDProcess:
    sequence: ReversalConfirmationSequence
    state: CISDState
    reference: CISDReference | None = None
    confirmation: CISDConfirmation | None = None
    non_confirmation_outcome: CISDNonConfirmationOutcome | None = None
    last_evaluated_time: int | None = None


@dataclass(frozen=True)
class CISDEvaluation:
    process: CISDProcess
    body_close_observed: bool
    chronology_eligible: bool
    confirmed: bool


class CISDEngine:
    """Canonical #11 1M delivery-state confirmation only.

    It does not detect MSS, displacement, sweeps, or FVGs and cannot select an
    entry, arm a setup, calculate risk, size, place orders, or execute.
    """

    TIMEFRAME = "1m"

    @staticmethod
    def _decimal(value: object, *, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{field} must be an exact finite number.") from error
        if not result.is_finite():
            raise ValueError(f"{field} must be an exact finite number.")
        return result

    @classmethod
    def _validate_candle(cls, candle: DeliveryCandle) -> None:
        if candle.timeframe.lower() != cls.TIMEFRAME:
            raise ValueError("#11 owns 1M candles only.")
        if not candle.is_closed:
            raise ValueError("CISD requires a completed 1M candle.")
        values = tuple(
            cls._decimal(value, field=field)
            for field, value in (
                ("open", candle.open), ("high", candle.high),
                ("low", candle.low), ("close", candle.close),
            )
        )
        open_, high, low, close = values
        if low <= 0 or high < low or not low <= open_ <= high or not low <= close <= high:
            raise ValueError("Invalid completed 1M candle OHLC geometry.")
        if not candle.id.strip():
            raise ValueError("Candle identity is required.")

    @staticmethod
    def _opposite(direction: CISDDirection) -> CISDDirection:
        return (
            CISDDirection.BEARISH
            if direction == CISDDirection.BULLISH else CISDDirection.BULLISH
        )

    @classmethod
    def _candle_direction(cls, candle: DeliveryCandle) -> CISDDirection | None:
        open_ = cls._decimal(candle.open, field="open")
        close = cls._decimal(candle.close, field="close")
        if close > open_:
            return CISDDirection.BULLISH
        if close < open_:
            return CISDDirection.BEARISH
        return None

    @staticmethod
    def _validate_sequence(sequence: ReversalConfirmationSequence) -> None:
        if not sequence.setup_candidate_id.strip() or not sequence.sweep_id.strip() or not sequence.mss_id.strip():
            raise ValueError("The reversal sequence requires immutable setup, sweep, and MSS identities.")
        if not sequence.mss_accepted:
            raise ValueError("#11 requires an accepted upstream MSS.")
        if sequence.sweep_time > sequence.mss_confirmation_time:
            raise ValueError("The qualifying LRL sweep must not follow MSS confirmation.")
        if sequence.prior_regime == StructuralRegime.BEARISH:
            valid = (
                sequence.sweep_side == LiquiditySide.LSL
                and sequence.intended_direction == CISDDirection.BULLISH
            )
        elif sequence.prior_regime == StructuralRegime.BULLISH:
            valid = (
                sequence.sweep_side == LiquiditySide.BSL
                and sequence.intended_direction == CISDDirection.BEARISH
            )
        else:
            valid = False
        if not valid:
            raise ValueError("Reversal sequence violates Amendment 005A sweep-side mapping.")

    def start(self, *, sequence: ReversalConfirmationSequence) -> CISDProcess:
        self._validate_sequence(sequence)
        return CISDProcess(sequence, CISDState.WAITING_FOR_1M_CONFIRMATION)

    def identify_reference(
        self, *, process: CISDProcess,
        delivery_legs: tuple[DeliveryLeg, ...], as_of_time: int,
    ) -> CISDProcess:
        if process.state != CISDState.WAITING_FOR_1M_CONFIRMATION:
            raise ValueError("Reference selection requires WAITING_FOR_1M_CONFIRMATION.")
        ids = [leg.id for leg in delivery_legs]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate delivery-leg identity.")

        candidates: list[DeliveryLeg] = []
        for leg in delivery_legs:
            for candle in leg.candles:
                self._validate_candle(candle)
            if (
                leg.confirmed
                and leg.setup_candidate_id == process.sequence.setup_candidate_id
                and leg.timeframe.lower() == self.TIMEFRAME
                and leg.directly_precedes_reversal_delivery
                and leg.end_time is not None
                and leg.end_time <= as_of_time
            ):
                candidates.append(leg)
        if not candidates:
            return replace(
                process,
                non_confirmation_outcome=CISDNonConfirmationOutcome.NOT_CONFIRMABLE,
            )

        # The latest directly preceding associated leg governs. An invalid latest
        # leg must not be bypassed in favor of an easier older reference.
        selected = max(candidates, key=lambda leg: (leg.end_time, leg.id))
        initiating = selected.initiating_candle
        expected = self._opposite(process.sequence.intended_direction)
        if (
            initiating is None
            or selected.direction != expected
            or self._candle_direction(initiating) != expected
        ):
            return replace(
                process,
                non_confirmation_outcome=CISDNonConfirmationOutcome.INVALID_CISD_REFERENCE,
            )
        if initiating.close_time >= as_of_time:
            # Frozen pre-state: the evaluating candle cannot manufacture its own
            # reference and then break it at the same timestamp.
            return replace(
                process,
                non_confirmation_outcome=CISDNonConfirmationOutcome.NOT_CONFIRMABLE,
            )
        reference = CISDReference(
            delivery_leg_id=selected.id,
            delivery_candle_id=initiating.id,
            delivery_candle_direction=selected.direction,
            reference_price=self._decimal(initiating.open, field="open"),
            reference_known_time=initiating.close_time,
        )
        return replace(
            process, state=CISDState.CISD_REFERENCE_IDENTIFIED,
            reference=reference, non_confirmation_outcome=None,
        )

    @staticmethod
    def wait_for_body_close(*, process: CISDProcess) -> CISDProcess:
        if process.state != CISDState.CISD_REFERENCE_IDENTIFIED or process.reference is None:
            raise ValueError("A valid frozen CISD reference must be identified first.")
        return replace(process, state=CISDState.WAITING_FOR_BODY_CLOSE)

    @staticmethod
    def _confirmation_id(
        *, process: CISDProcess, candle: DeliveryCandle,
    ) -> str:
        reference = process.reference
        key = (
            f"trading-brain:#11:{process.sequence.setup_candidate_id}:"
            f"{process.sequence.intended_direction.value}:{reference.delivery_candle_id}:"
            f"{candle.id}:{candle.close_time}"
        )
        return str(uuid5(NAMESPACE_URL, key))

    def evaluate(
        self, *, process: CISDProcess, candle: DeliveryCandle,
    ) -> CISDEvaluation:
        self._validate_candle(candle)
        if process.state == CISDState.CISD_CONFIRMED:
            return CISDEvaluation(process, False, True, True)
        if process.state == CISDState.CONFIRMATION_TERMINATED:
            return CISDEvaluation(process, False, False, False)
        if process.state != CISDState.WAITING_FOR_BODY_CLOSE or process.reference is None:
            raise ValueError("CISD evaluation requires WAITING_FOR_BODY_CLOSE and a frozen reference.")
        if (
            process.last_evaluated_time is not None
            and candle.close_time <= process.last_evaluated_time
        ):
            raise ValueError("1M confirmation candles must be evaluated once in increasing close-time order.")

        sequence = process.sequence
        chronology_eligible = (
            candle.close_time >= sequence.sweep_time
            and candle.close_time >= sequence.mss_confirmation_time
            and candle.close_time > process.reference.reference_known_time
        )
        close = self._decimal(candle.close, field="close")
        reference = process.reference.reference_price
        if sequence.intended_direction == CISDDirection.BULLISH:
            crossed = close > reference
        else:
            crossed = close < reference
        body_close_observed = crossed

        if not chronology_eligible or not crossed:
            updated = replace(process, last_evaluated_time=candle.close_time)
            return CISDEvaluation(updated, body_close_observed, chronology_eligible, False)

        confirmation = CISDConfirmation(
            id=self._confirmation_id(process=process, candle=candle),
            setup_candidate_id=sequence.setup_candidate_id,
            timeframe=self.TIMEFRAME, direction=sequence.intended_direction,
            delivery_leg_id=process.reference.delivery_leg_id,
            delivery_candle_id=process.reference.delivery_candle_id,
            delivery_candle_direction=process.reference.delivery_candle_direction,
            reference_price=reference, confirmation_candle_id=candle.id,
            confirmation_close=close, confirmation_time=candle.close_time,
            body_close_confirmed=True, associated_mss_id=sequence.mss_id,
            associated_sweep_id=sequence.sweep_id,
            same_candle_as_mss=candle.close_time == sequence.mss_confirmation_time,
            valid=True, active_for_setup=True,
            invalidation_time=None, invalidation_reason=None,
            historical=False,
        )
        updated = replace(
            process, state=CISDState.CISD_CONFIRMED,
            confirmation=confirmation, last_evaluated_time=candle.close_time,
        )
        return CISDEvaluation(updated, True, True, True)

    @staticmethod
    def terminate(
        *, process: CISDProcess, invalidation_time: int,
        invalidation_reason: str,
    ) -> CISDProcess:
        if process.state == CISDState.CONFIRMATION_TERMINATED:
            return process
        if not invalidation_reason.strip():
            raise ValueError("Upstream invalidation/expiration reason is required.")
        confirmation = process.confirmation
        if confirmation is not None:
            if invalidation_time < confirmation.confirmation_time:
                raise ValueError("Confirmation cannot be invalidated before it exists.")
            confirmation = replace(
                confirmation, active_for_setup=False,
                invalidation_time=int(invalidation_time),
                invalidation_reason=invalidation_reason,
                historical=True,
            )
        return replace(
            process, state=CISDState.CONFIRMATION_TERMINATED,
            confirmation=confirmation,
        )

    @classmethod
    def zone_is_temporally_eligible(
        cls, *, process: CISDProcess, zone: FVG | IFVG,
    ) -> bool:
        confirmation = process.confirmation
        if (
            process.state != CISDState.CISD_CONFIRMED
            or confirmation is None
            or not confirmation.active_for_setup
            or zone.timeframe.lower() != cls.TIMEFRAME
        ):
            return False
        expected = (
            FVGDirection.BULLISH
            if confirmation.direction == CISDDirection.BULLISH
            else FVGDirection.BEARISH
        )
        return (
            zone.direction == expected
            and zone.confirmation_time >= confirmation.confirmation_time
        )
