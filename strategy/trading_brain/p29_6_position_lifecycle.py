from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_1_entry_execution import EntryFill, EntryOrder, OrderState, PositionAvailability
from strategy.trading_brain.p29_2_position_sizing import PositionSizing
from strategy.trading_brain.p29_3_protective_orders import ProtectiveOrderHistory, ProtectiveOrderSet
from strategy.trading_brain.position_state_contract import PositionState

if TYPE_CHECKING:
    from strategy.trading_brain.p29_4_exit_resolution import ExecutionRecord, ExitResolutionHistory


class PositionLifecycleErrorCode(str, Enum):
    POSITION_LIFECYCLE_INVALID = "POSITION_LIFECYCLE_INVALID"


@dataclass(frozen=True)
class Position:
    id: str
    snapshot_id: str
    previous_snapshot_id: str | None
    setup_id: str
    setup_candidate_id: str
    model: SetupModel
    direction: StructuralRegime
    symbol: str
    timeframe: str
    input_version: str
    state: PositionState
    quantity: Decimal
    entry_order_id: str
    entry_execution_id: str
    entry_price: Decimal
    opened_time: int
    sizing_id: str
    protective_set_id: str
    oco_group_id: str
    stop_order_id: str
    stop_price: Decimal
    target_order_id: str
    target_price: Decimal
    exit_execution_id: str | None = None
    winning_protective_order_id: str | None = None
    cancelled_protective_order_id: str | None = None
    exit_price: Decimal | None = None
    exit_time: int | None = None
    exit_reason: object | None = None
    state_time: int = 0
    immutable: bool = True


@dataclass(frozen=True)
class PositionLifecycleHistory:
    snapshots: tuple[Position, ...] = ()


@dataclass(frozen=True)
class PositionLifecycleError:
    id: str
    code: PositionLifecycleErrorCode
    reason: str
    position_id: str | None
    event_time: int
    immutable: bool = True


@dataclass(frozen=True)
class PositionLifecycleResult:
    position: Position | None
    error: PositionLifecycleError | None
    history: PositionLifecycleHistory

    @property
    def valid(self) -> bool:
        return self.position is not None and self.error is None


class PositionLifecycleEngine:
    """Canonical #29.6 availability and OPEN/CLOSED facts only."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.6:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    @staticmethod
    def _latest(history: PositionLifecycleHistory) -> tuple[Position, ...]:
        latest: dict[str, Position] = {}
        for snapshot in history.snapshots:
            latest[snapshot.id] = snapshot
        return tuple(latest.values())

    def availability(self, *, symbol: str, checked_time: int, history: PositionLifecycleHistory = PositionLifecycleHistory()) -> PositionAvailability:
        latest = self._latest(history)
        newest = max((position.state_time for position in latest), default=0)
        confirmed = bool(symbol.strip()) and int(checked_time) >= newest
        count = sum(position.state == PositionState.OPEN for position in latest)
        return PositionAvailability(
            id=self._uid("availability", symbol, checked_time, count, newest),
            symbol=symbol, open_position_count=count,
            checked_time=int(checked_time), confirmed=confirmed,
        )

    @staticmethod
    def open_boundary(position: Position):
        """Expose the immutable OPEN fact consumed by canonical #29.4."""
        from strategy.trading_brain.p29_4_exit_resolution import OpenPositionBoundary
        return OpenPositionBoundary(
            id=position.snapshot_id, setup_id=position.setup_id,
            entry_fill_id=position.entry_execution_id,
            protective_set_id=position.protective_set_id,
            symbol=position.symbol, timeframe=position.timeframe,
            input_version=position.input_version, state=position.state,
            opened_time=position.opened_time, confirmed=position.state == PositionState.OPEN,
        )

    def _invalid(self, reason, time, history, position=None):
        pid = position.id if position else None
        error = PositionLifecycleError(self._uid("error", pid or "NONE", reason, time), PositionLifecycleErrorCode.POSITION_LIFECYCLE_INVALID, reason, pid, int(time))
        return PositionLifecycleResult(position, error, history)

    def open(
        self, *, entry_order: EntryOrder | None, fill: EntryFill | None,
        sizing: PositionSizing | None, protective_set: ProtectiveOrderSet | None,
        protective_history: ProtectiveOrderHistory | None,
        history: PositionLifecycleHistory = PositionLifecycleHistory(),
    ) -> PositionLifecycleResult:
        if any(value is None for value in (entry_order, fill, sizing, protective_set, protective_history)):
            return self._invalid("REQUIRED_POSITION_OPEN_INPUT_MISSING", getattr(fill, "fill_time", 0), history)
        assert entry_order and fill and sizing and protective_set and protective_history
        position_id = self._uid("position", fill.id)
        existing = next((item for item in self._latest(history) if item.id == position_id), None)
        if existing:
            same = existing.entry_execution_id == fill.id and existing.sizing_id == sizing.id and existing.protective_set_id == protective_set.id
            if same:
                return PositionLifecycleResult(existing, None, history)
            return self._invalid("CONFLICTING_POSITION_CREATION", fill.fill_time, history, existing)
        if any(item.state == PositionState.OPEN for item in self._latest(history)):
            return self._invalid("OVERLAPPING_POSITION_PROHIBITED", fill.fill_time, history)
        reason = self._validate_open(entry_order, fill, sizing, protective_set, protective_history)
        if reason:
            return self._invalid(reason, fill.fill_time, history)
        stop, target = protective_set.stop_order, protective_set.target_order
        snapshot_id = self._uid("snapshot", position_id, "OPEN", fill.fill_time)
        position = Position(
            position_id, snapshot_id, None, fill.setup_id, sizing.setup_candidate_id,
            sizing.model, sizing.direction, fill.symbol, fill.timeframe,
            sizing.input_version, PositionState.OPEN, sizing.proposed_quantity,
            entry_order.id, fill.id, fill.fill_price, fill.fill_time, sizing.id,
            protective_set.id, protective_set.oco_group.id, stop.id, stop.price,
            target.id, target.price, state_time=fill.fill_time,
        )
        updated = PositionLifecycleHistory(history.snapshots + (position,))
        return PositionLifecycleResult(position, None, updated)

    def _validate_open(self, order, fill, sizing, protective_set, protective_history):
        if order.state != OrderState.FILLED or fill.event != "ENTRY_FILL_CONFIRMED":
            return "ENTRY_FILL_NOT_CONFIRMED"
        stop, target = protective_set.stop_order, protective_set.target_order
        latest_stop = next((x for x in reversed(protective_history.transitions) if x.id == stop.id), None)
        latest_target = next((x for x in reversed(protective_history.transitions) if x.id == target.id), None)
        if latest_stop != stop or latest_target != target or stop.state != OrderState.ACTIVE or target.state != OrderState.ACTIVE:
            return "PROTECTIVE_SET_NOT_ACTIVE"
        identity = (
            order.setup_id == fill.setup_id == sizing.setup_id == protective_set.setup_id
            and order.setup_candidate_id == sizing.setup_candidate_id
            and order.model == sizing.model == stop.model == target.model
            and order.direction == sizing.direction == stop.direction == target.direction
            and order.id == fill.order_id == sizing.entry_order_id
            and fill.id == sizing.entry_fill_id == protective_set.oco_group.entry_fill_id
            and sizing.id == protective_set.oco_group.sizing_id
            and protective_set.oco_group.stop_order_id == stop.id
            and protective_set.oco_group.target_order_id == target.id
        )
        if not identity:
            return "POSITION_OPEN_IDENTITY_MISMATCH"
        if fill.order_record_id != order.record_id:
            return "ENTRY_ORDER_RECORD_MISMATCH"
        if fill.symbol != sizing.symbol or fill.symbol != stop.symbol:
            return "POSITION_SYMBOL_MISMATCH"
        if fill.timeframe.lower() != sizing.timeframe.lower() or fill.timeframe.lower() != stop.timeframe.lower():
            return "POSITION_TIMEFRAME_MISMATCH"
        if sizing.input_version != stop.input_version or sizing.input_version != target.input_version:
            return "POSITION_INPUT_VERSION_MISMATCH"
        try:
            entry, quantity, stop_price, target_price = map(self._decimal, (fill.fill_price, sizing.proposed_quantity, stop.price, target.price))
        except ValueError:
            return "NON_FINITE_POSITION_INPUT"
        if quantity <= 0 or entry != sizing.entry_price or quantity != stop.quantity or quantity != target.quantity:
            return "POSITION_PRICE_OR_QUANTITY_MISMATCH"
        if sizing.direction == StructuralRegime.BULLISH and not stop_price < entry < target_price:
            return "LONG_POSITION_GEOMETRY_INVALID"
        if sizing.direction == StructuralRegime.BEARISH and not target_price < entry < stop_price:
            return "SHORT_POSITION_GEOMETRY_INVALID"
        if min(stop.state_time, target.state_time) < fill.fill_time:
            return "PROTECTIVE_ACTIVATION_CHRONOLOGY_INVALID"
        return None

    def close(
        self, *, position: Position,
        exit_execution: "ExecutionRecord" | None,
        exit_history: "ExitResolutionHistory" | None,
        history: PositionLifecycleHistory,
    ) -> PositionLifecycleResult:
        time = getattr(exit_execution, "exit_time", position.state_time)
        latest = next((item for item in self._latest(history) if item.id == position.id), None)
        if latest != position:
            return self._invalid("POSITION_NOT_LATEST_SNAPSHOT", time, history, position)
        if position.state == PositionState.CLOSED:
            if exit_execution is not None and position.exit_execution_id == exit_execution.id:
                return PositionLifecycleResult(position, None, history)
            return self._invalid("CLOSED_POSITION_FINAL", time, history, position)
        if position.state != PositionState.OPEN:
            return self._invalid("POSITION_NOT_OPEN", time, history, position)
        if exit_execution is None or exit_history is None:
            return self._invalid("RESOLVED_EXIT_REQUIRED", time, history, position)
        if exit_execution not in exit_history.resolutions:
            return self._invalid("EXIT_NOT_IN_IMMUTABLE_HISTORY", time, history, position)
        transitions = [x for x in exit_history.protective_transitions if x.id in (position.stop_order_id, position.target_order_id)]
        if len(transitions) != 2:
            return self._invalid("TERMINAL_OCO_TRANSITIONS_MISSING", time, history, position)
        states = {x.id: x.state for x in transitions}
        if states.get(exit_execution.winning_order_id) != OrderState.FILLED or states.get(exit_execution.cancelled_order_id) != OrderState.CANCELLED:
            return self._invalid("TERMINAL_OCO_TRANSITIONS_INVALID", time, history, position)
        if (
            exit_execution.setup_id != position.setup_id
            or exit_execution.protective_set_id != position.protective_set_id
            or exit_execution.oco_group_id != position.oco_group_id
            or exit_execution.symbol != position.symbol
            or exit_execution.timeframe.lower() != position.timeframe.lower()
            or exit_execution.input_version != position.input_version
            or exit_execution.winning_order_id not in (position.stop_order_id, position.target_order_id)
            or exit_execution.cancelled_order_id not in (position.stop_order_id, position.target_order_id)
            or exit_execution.winning_order_id == exit_execution.cancelled_order_id
        ):
            return self._invalid("POSITION_EXIT_IDENTITY_MISMATCH", time, history, position)
        if exit_execution.exit_time < position.opened_time:
            return self._invalid("POSITION_CLOSE_CHRONOLOGY_INVALID", time, history, position)
        try:
            exit_price = self._decimal(exit_execution.exit_price)
        except ValueError:
            return self._invalid("NON_FINITE_EXIT_PRICE", time, history, position)
        if exit_price <= 0:
            return self._invalid("NON_POSITIVE_EXIT_PRICE", time, history, position)
        closed = replace(
            position,
            snapshot_id=self._uid("snapshot", position.id, "CLOSED", exit_execution.id),
            previous_snapshot_id=position.snapshot_id, state=PositionState.CLOSED,
            exit_execution_id=exit_execution.id,
            winning_protective_order_id=exit_execution.winning_order_id,
            cancelled_protective_order_id=exit_execution.cancelled_order_id,
            exit_price=exit_price, exit_time=exit_execution.exit_time,
            exit_reason=exit_execution.exit_reason,
            state_time=exit_execution.exit_time,
        )
        updated = PositionLifecycleHistory(history.snapshots + (closed,))
        return PositionLifecycleResult(closed, None, updated)
