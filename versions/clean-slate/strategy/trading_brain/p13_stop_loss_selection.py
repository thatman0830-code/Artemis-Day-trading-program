from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralRegime, StructuralSwing,
)
from strategy.trading_brain.p23_liquidity import (
    LiquiditySide, LiquidityState, LiquiditySweep,
)
from strategy.trading_brain.p27_setup_qualification import Setup, SetupModel
from strategy.trading_brain.p28_entry_zone_selection import (
    EntryZoneSelection, EntryZoneSelectionState,
)


class StopSelectionErrorCode(str, Enum):
    STOP_SELECTION_INVALID = "STOP_SELECTION_INVALID"


@dataclass(frozen=True)
class StopSelectionError:
    id: str
    code: StopSelectionErrorCode
    setup_id: str
    reason: str
    selection_time: int
    immutable: bool = True


@dataclass(frozen=True)
class StopSelection:
    id: str
    setup_id: str
    entry_zone_selection_id: str
    model: SetupModel
    direction: StructuralRegime
    reference_type: str
    reference_id: str
    reference_price: Decimal
    minimum_tick: Decimal
    frozen_entry_price: Decimal
    stop_price: Decimal
    selection_time: int
    immutable: bool = True


@dataclass(frozen=True)
class StopSelectionResult:
    stop: StopSelection | None
    error: StopSelectionError | None

    @property
    def valid(self) -> bool:
        return self.stop is not None and self.error is None


class StopLossSelectionEngine:
    """Canonical #13 immutable StopPrice selection only.

    StopPrice is not ExitPrice. This primitive has no R-multiple, arming, risk,
    sizing, protective-order, fill, position, or execution behavior.
    """

    def __init__(self, *, minimum_tick: Decimal):
        self.minimum_tick = self._decimal(minimum_tick, field="minimum_tick")
        if self.minimum_tick <= 0:
            raise ValueError("minimum_tick must be positive.")

    @staticmethod
    def _decimal(value: object, *, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{field} must be an exact finite number.") from error
        if not result.is_finite():
            raise ValueError(f"{field} must be an exact finite number.")
        return result

    def _on_grid(self, price: Decimal) -> bool:
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            ticks = price / self.minimum_tick
            return ticks == ticks.to_integral_value()

    @staticmethod
    def _error_id(setup_id: str, reason: str, selection_time: int) -> str:
        key = f"trading-brain:#13:error:{setup_id}:{reason}:{selection_time}"
        return str(uuid5(NAMESPACE_URL, key))

    def _invalid(
        self, *, setup: Setup, reason: str, selection_time: int,
    ) -> StopSelectionResult:
        return StopSelectionResult(
            stop=None,
            error=StopSelectionError(
                id=self._error_id(setup.id, reason, selection_time),
                code=StopSelectionErrorCode.STOP_SELECTION_INVALID,
                setup_id=setup.id, reason=reason,
                selection_time=int(selection_time),
            ),
        )

    @staticmethod
    def _validate_handoff(
        setup: Setup, entry_zone: EntryZoneSelection,
    ) -> str | None:
        if not setup.entry_zone_selection_eligible:
            return "SETUP_NOT_ENTRY_ZONE_SELECTION_ELIGIBLE"
        if entry_zone.setup_id != setup.id:
            return "ENTRY_ZONE_SETUP_MISMATCH"
        if entry_zone.model != setup.model or entry_zone.direction != setup.direction:
            return "ENTRY_ZONE_MODEL_DIRECTION_MISMATCH"
        if (
            entry_zone.state != EntryZoneSelectionState.SELECTED
            or entry_zone.selected_zone_id is None
            or entry_zone.eq_normalized is None
        ):
            return "FROZEN_ENTRY_ZONE_NOT_SELECTED"
        return None

    @staticmethod
    def _selection_id(
        *, setup: Setup, entry_zone: EntryZoneSelection,
        reference_id: str, selection_time: int,
    ) -> str:
        key = (
            f"trading-brain:#13:{setup.id}:{entry_zone.id}:"
            f"{reference_id}:{selection_time}"
        )
        return str(uuid5(NAMESPACE_URL, key))

    def select(
        self, *, setup: Setup, entry_zone: EntryZoneSelection,
        selection_time: int,
        protected_swing: StructuralSwing | None = None,
        qualifying_sweep: LiquiditySweep | None = None,
    ) -> StopSelectionResult:
        handoff_error = self._validate_handoff(setup, entry_zone)
        if handoff_error is not None:
            return self._invalid(
                setup=setup, reason=handoff_error,
                selection_time=selection_time,
            )
        if selection_time < (entry_zone.selection_time or entry_zone.eligibility_time):
            return self._invalid(
                setup=setup, reason="STOP_SELECTION_PRECEDES_FROZEN_ENTRY",
                selection_time=selection_time,
            )

        entry = self._decimal(entry_zone.eq_normalized, field="frozen_entry_price")
        if not self._on_grid(entry):
            return self._invalid(
                setup=setup, reason="FROZEN_ENTRY_OFF_TICK_GRID",
                selection_time=selection_time,
            )

        if setup.model == SetupModel.CONTINUATION:
            if protected_swing is None:
                return self._invalid(
                    setup=setup, reason="PROTECTED_STRUCTURAL_SWING_MISSING",
                    selection_time=selection_time,
                )
            expected_type = (
                MechanicalSwingType.L
                if setup.direction == StructuralRegime.BULLISH
                else MechanicalSwingType.H
            )
            if (
                not protected_swing.protected
                or protected_swing.type != expected_type
                or protected_swing.id != setup.protected_swing_id
            ):
                return self._invalid(
                    setup=setup, reason="PROTECTED_STRUCTURAL_SWING_INVALID",
                    selection_time=selection_time,
                )
            reference_id = protected_swing.id
            reference_type = "PROTECTED_STRUCTURAL_SWING"
            reference = self._decimal(protected_swing.price, field="protected_swing_price")
        elif setup.model == SetupModel.REVERSAL_1:
            if qualifying_sweep is None:
                return self._invalid(
                    setup=setup, reason="QUALIFYING_SWEEP_EXTREME_MISSING",
                    selection_time=selection_time,
                )
            expected_side = (
                LiquiditySide.LSL
                if setup.direction == StructuralRegime.BULLISH
                else LiquiditySide.BSL
            )
            if (
                qualifying_sweep.id != setup.qualifying_sweep_id
                or qualifying_sweep.side != expected_side
                or qualifying_sweep.outcome != LiquidityState.SWEPT
                or qualifying_sweep.final_state != LiquidityState.CONSUMED
            ):
                return self._invalid(
                    setup=setup, reason="QUALIFYING_SWEEP_INVALID",
                    selection_time=selection_time,
                )
            reference_id = qualifying_sweep.id
            reference_type = "QUALIFYING_SWEEP_EXTREME"
            reference = self._decimal(
                qualifying_sweep.candle_extreme, field="qualifying_sweep_extreme",
            )
            if (
                expected_side == LiquiditySide.LSL
                and reference >= qualifying_sweep.level
            ) or (
                expected_side == LiquiditySide.BSL
                and reference <= qualifying_sweep.level
            ):
                return self._invalid(
                    setup=setup, reason="QUALIFYING_SWEEP_EXTREME_INVALID",
                    selection_time=selection_time,
                )
        else:
            return self._invalid(
                setup=setup, reason="SETUP_MODEL_INVALID",
                selection_time=selection_time,
            )

        if reference <= 0 or not self._on_grid(reference):
            return self._invalid(
                setup=setup, reason="STOP_REFERENCE_OFF_TICK_GRID",
                selection_time=selection_time,
            )
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            if setup.direction == StructuralRegime.BULLISH:
                stop = reference - self.minimum_tick
                valid_geometry = stop > 0 and stop < reference and stop < entry
            else:
                stop = reference + self.minimum_tick
                valid_geometry = stop > reference and stop > entry
        if not valid_geometry:
            return self._invalid(
                setup=setup, reason="STOP_GEOMETRY_INVALID_AGAINST_FROZEN_ENTRY",
                selection_time=selection_time,
            )
        stop_selection = StopSelection(
            id=self._selection_id(
                setup=setup, entry_zone=entry_zone,
                reference_id=reference_id, selection_time=selection_time,
            ),
            setup_id=setup.id, entry_zone_selection_id=entry_zone.id,
            model=setup.model, direction=setup.direction,
            reference_type=reference_type, reference_id=reference_id,
            reference_price=reference, minimum_tick=self.minimum_tick,
            frozen_entry_price=entry, stop_price=stop,
            selection_time=int(selection_time),
        )
        return StopSelectionResult(stop_selection, None)
