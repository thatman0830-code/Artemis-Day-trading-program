from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralRegime, StructuralStateSnapshot, StructuralSwing,
)


@dataclass(frozen=True)
class StructuralRange:
    id: str
    timeframe: str
    upper_boundary: Decimal
    lower_boundary: Decimal
    defining_high_swing_id: str
    defining_low_swing_id: str
    defining_high_price: Decimal
    defining_low_price: Decimal
    regime: StructuralRegime
    creation_time: int
    confirmation_time: int
    active: bool
    historical: bool
    created_by_event_id: str
    termination_time: int | None = None
    terminated_by_event_id: str | None = None
    predecessor_range_id: str | None = None
    successor_range_id: str | None = None


@dataclass(frozen=True)
class ActiveRangeError:
    id: str
    error_code: str
    owning_module: str
    severity: str
    timeframe: str
    processing_timestamp: int
    state_id: str
    message: str
    immutable: bool = True


@dataclass(frozen=True)
class RangeUpdateResult:
    active_range: StructuralRange | None
    terminated_range: StructuralRange | None
    preserved_previous_range: StructuralRange | None
    error: ActiveRangeError | None


class ActiveDealingRangeEngine:
    """Canonical #21 range construction/lifecycle only."""

    @staticmethod
    def _boundaries(
        state: StructuralStateSnapshot,
    ) -> tuple[StructuralSwing | None, StructuralSwing | None]:
        if state.regime == StructuralRegime.BULLISH:
            return state.governing_high, state.protected_low
        if state.regime == StructuralRegime.BEARISH:
            return state.protected_high, state.governing_low
        return None, None

    @staticmethod
    def _validate_references(
        state: StructuralStateSnapshot,
        high: StructuralSwing,
        low: StructuralSwing,
    ) -> None:
        if high.type != MechanicalSwingType.H or low.type != MechanicalSwingType.L:
            raise ValueError("#21 boundaries must use structural high and low wick extremes.")
        if high.timeframe != state.timeframe or low.timeframe != state.timeframe:
            raise ValueError("Active dealing ranges are timeframe-isolated.")

    @staticmethod
    def _range_id(
        *, state: StructuralStateSnapshot, high: StructuralSwing,
        low: StructuralSwing, event_id: str,
    ) -> str:
        key = f"trading-brain:#21:{state.timeframe}:{state.regime.value}:{high.id}:{low.id}:{event_id}"
        return str(uuid5(NAMESPACE_URL, key))

    @staticmethod
    def _error(
        *, state: StructuralStateSnapshot, processing_timestamp: int,
        high: StructuralSwing, low: StructuralSwing,
    ) -> ActiveRangeError:
        key = f"trading-brain:#21-error:{state.id}:{processing_timestamp}:{high.id}:{low.id}"
        return ActiveRangeError(
            id=str(uuid5(NAMESPACE_URL, key)),
            error_code="ACTIVE_RANGE_INVALID",
            owning_module="#21",
            severity="BLOCKING",
            timeframe=state.timeframe,
            processing_timestamp=processing_timestamp,
            state_id=state.id,
            message="UpperBoundary must be strictly greater than LowerBoundary.",
        )

    @staticmethod
    def _terminate(
        previous: StructuralRange, *, timestamp: int,
        event_id: str, successor_id: str | None,
    ) -> StructuralRange:
        return replace(
            previous,
            active=False,
            historical=True,
            termination_time=timestamp,
            terminated_by_event_id=event_id,
            successor_range_id=successor_id,
        )

    def update(
        self,
        *,
        state_after: StructuralStateSnapshot,
        accepted_structural_event_id: str | None,
        processing_timestamp: int,
        previous_active_range: StructuralRange | None = None,
    ) -> RangeUpdateResult:
        if previous_active_range is not None:
            if not previous_active_range.active or previous_active_range.historical:
                raise ValueError("previous_active_range must be the active lifecycle record.")
            if previous_active_range.timeframe != state_after.timeframe:
                raise ValueError("Previous range and structural state must share one timeframe.")

        # Event-driven invariant: ordinary candles and unresolved candidates do nothing.
        if accepted_structural_event_id is None:
            return RangeUpdateResult(
                active_range=previous_active_range,
                terminated_range=None,
                preserved_previous_range=previous_active_range,
                error=None,
            )

        if state_after.regime in {
            StructuralRegime.INITIALIZING,
            StructuralRegime.TRANSITION,
        }:
            terminated = None
            if previous_active_range is not None:
                terminated = self._terminate(
                    previous_active_range,
                    timestamp=processing_timestamp,
                    event_id=accepted_structural_event_id,
                    successor_id=None,
                )
            return RangeUpdateResult(
                active_range=None,
                terminated_range=terminated,
                preserved_previous_range=None if terminated else previous_active_range,
                error=None,
            )

        high, low = self._boundaries(state_after)
        if high is None or low is None:
            # Missing structural information is not an error and cannot invent a replacement.
            return RangeUpdateResult(
                active_range=None if previous_active_range is None else previous_active_range,
                terminated_range=None,
                preserved_previous_range=previous_active_range,
                error=None,
            )

        self._validate_references(state_after, high, low)
        if high.price <= low.price:
            return RangeUpdateResult(
                active_range=None,
                terminated_range=None,
                preserved_previous_range=previous_active_range,
                error=self._error(
                    state=state_after,
                    processing_timestamp=processing_timestamp,
                    high=high,
                    low=low,
                ),
            )

        if (
            previous_active_range is not None
            and previous_active_range.regime == state_after.regime
            and previous_active_range.defining_high_swing_id == high.id
            and previous_active_range.defining_low_swing_id == low.id
        ):
            return RangeUpdateResult(
                active_range=previous_active_range,
                terminated_range=None,
                preserved_previous_range=previous_active_range,
                error=None,
            )

        range_id = self._range_id(
            state=state_after, high=high, low=low,
            event_id=accepted_structural_event_id,
        )
        new_range = StructuralRange(
            id=range_id,
            timeframe=state_after.timeframe,
            upper_boundary=high.price,
            lower_boundary=low.price,
            defining_high_swing_id=high.id,
            defining_low_swing_id=low.id,
            defining_high_price=high.price,
            defining_low_price=low.price,
            regime=state_after.regime,
            creation_time=processing_timestamp,
            confirmation_time=(
                state_after.as_of_timestamp
                if state_after.as_of_timestamp is not None
                else processing_timestamp
            ),
            active=True,
            historical=False,
            created_by_event_id=accepted_structural_event_id,
            predecessor_range_id=(
                previous_active_range.id if previous_active_range is not None else None
            ),
        )
        terminated = None
        if previous_active_range is not None:
            terminated = self._terminate(
                previous_active_range,
                timestamp=processing_timestamp,
                event_id=accepted_structural_event_id,
                successor_id=new_range.id,
            )
        return RangeUpdateResult(
            active_range=new_range,
            terminated_range=terminated,
            preserved_previous_range=None,
            error=None,
        )
