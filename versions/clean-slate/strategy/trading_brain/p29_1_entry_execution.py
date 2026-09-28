from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import ContinuationSetupState, FinalSetupQualification, ReversalSetupState, SetupModel
from strategy.trading_brain.p28_entry_zone_selection import EntryZoneSelection, EntryZoneSelectionState


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    TESTNET = "TESTNET"


class OrderType(str, Enum):
    LIMIT = "LIMIT"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderState(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class EntryExecutionErrorCode(str, Enum):
    ENTRY_INVALID = "ENTRY_INVALID"
    ENTRY_NOT_FILLED = "ENTRY_NOT_FILLED"


@dataclass(frozen=True)
class EntryExecutionContext:
    id: str; symbol: str; timeframe: str; minimum_tick: Decimal
    mode: ExecutionMode; confirmed_time: int; immutable: bool = True


@dataclass(frozen=True)
class PositionAvailability:
    """Immutable input owned by the later #29.6 position boundary."""
    id: str; symbol: str; open_position_count: int; checked_time: int
    confirmed: bool = True; immutable: bool = True


@dataclass(frozen=True)
class EntryCandle:
    id: str; symbol: str; timeframe: str; opened_time: int; closed_time: int
    open: Decimal; high: Decimal; low: Decimal; close: Decimal
    immutable: bool = True


@dataclass(frozen=True)
class EntryOrder:
    id: str; record_id: str; previous_record_id: str | None
    setup_id: str; setup_candidate_id: str; final_qualification_id: str
    entry_zone_selection_id: str; symbol: str; timeframe: str
    model: SetupModel; direction: StructuralRegime; order_type: OrderType
    side: OrderSide; limit_price: Decimal; minimum_tick: Decimal
    mode: ExecutionMode; state: OrderState; created_time: int; state_time: int
    immutable: bool = True


@dataclass(frozen=True)
class EntryFill:
    id: str; order_id: str; order_record_id: str; setup_id: str
    entry_zone_selection_id: str; candle_id: str; symbol: str; timeframe: str
    side: OrderSide; fill_price: Decimal; fill_time: int; mode: ExecutionMode
    event: str = "ENTRY_FILL_CONFIRMED"; immutable: bool = True


@dataclass(frozen=True)
class EntryExecutionError:
    id: str; code: EntryExecutionErrorCode; reason: str; event_time: int
    order_id: str | None = None; immutable: bool = True


@dataclass(frozen=True)
class EntryCandleEvaluation:
    id: str; order_id: str; candle_id: str; opened_time: int; closed_time: int
    touched: bool; immutable: bool = True


@dataclass(frozen=True)
class EntryExecutionHistory:
    orders: tuple[EntryOrder, ...] = (); fills: tuple[EntryFill, ...] = ()
    evaluations: tuple[EntryCandleEvaluation, ...] = ()


@dataclass(frozen=True)
class EntryExecutionResult:
    order: EntryOrder | None; fill: EntryFill | None
    error: EntryExecutionError | None; history: EntryExecutionHistory

    @property
    def valid(self) -> bool:
        return self.error is None


class EntryExecutionEngine:
    """Canonical #29.1 facts only; contains no exchange submission interface."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        key = "trading-brain:#29.1:" + kind + ":" + ":".join(map(str, parts))
        return str(uuid5(NAMESPACE_URL, key))

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
    def _on_grid(value: Decimal, tick: Decimal) -> bool:
        return tick > 0 and value > 0 and value % tick == 0

    @staticmethod
    def _latest(order_id: str, history: EntryExecutionHistory) -> EntryOrder | None:
        rows = [row for row in history.orders if row.id == order_id]
        return rows[-1] if rows else None

    def _error(self, code, reason, time, history, order=None):
        error = EntryExecutionError(self._uid("error", code.value, reason, time, order.id if order else "NONE"), code, reason, int(time), order.id if order else None)
        return EntryExecutionResult(order, None, error, history)

    def create_order(self, *, qualification: FinalSetupQualification | None, selection: EntryZoneSelection | None, context: EntryExecutionContext | None, position_availability: PositionAvailability | None, created_time: int, history: EntryExecutionHistory = EntryExecutionHistory()) -> EntryExecutionResult:
        now = int(created_time)
        reason = self._validate(qualification, selection, context, position_availability, now)
        if reason:
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, reason, now, history)
        assert qualification and selection and context and selection.eq_normalized is not None
        if any(row.setup_id == qualification.setup_id for row in history.orders):
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "DUPLICATE_ENTRY_ORDER", now, history)
        side = OrderSide.BUY if qualification.direction == StructuralRegime.BULLISH else OrderSide.SELL
        oid = self._uid("order", qualification.id, selection.id, context.id)
        order = EntryOrder(oid, self._uid("record", oid, "PENDING", now), None, qualification.setup_id, qualification.setup_candidate_id, qualification.id, selection.id, context.symbol, context.timeframe, qualification.model, qualification.direction, OrderType.LIMIT, side, selection.eq_normalized, context.minimum_tick, context.mode, OrderState.PENDING, now, now)
        new = EntryExecutionHistory(history.orders + (order,), history.fills, history.evaluations)
        return EntryExecutionResult(order, None, None, new)

    def _validate(self, q, s, c, availability, now):
        if q is None or s is None or c is None:
            return "REQUIRED_FROZEN_INPUT_MISSING"
        if not c.symbol.strip() or not c.timeframe.strip() or c.mode not in (ExecutionMode.PAPER, ExecutionMode.TESTNET):
            return "EXECUTION_CONTEXT_INVALID"
        armed = (q.model == SetupModel.CONTINUATION and q.final_state == ContinuationSetupState.ARMED) or (q.model == SetupModel.REVERSAL_1 and q.final_state == ReversalSetupState.ENTRY_ZONE_ARMED)
        if not q.executable or not armed:
            return "SETUP_NOT_CANONICALLY_ARMED"
        if s.state != EntryZoneSelectionState.SELECTED or s.eq_normalized is None:
            return "ENTRY_ZONE_SELECTION_INVALID"
        if (q.setup_id, q.setup_candidate_id, q.model, q.direction, q.entry_zone_selection_id, q.entry) != (s.setup_id, s.setup_candidate_id, s.model, s.direction, s.id, s.eq_normalized):
            return "FROZEN_INPUT_IDENTITY_MISMATCH"
        try:
            tick = self._decimal(c.minimum_tick)
        except ValueError:
            return "MINIMUM_TICK_INVALID"
        if tick != s.minimum_tick or not self._on_grid(s.eq_normalized, tick):
            return "FROZEN_EQ_TICK_GRID_INVALID"
        candidates = [x for x in s.frozen_candidates if x.zone_id == s.selected_zone_id]
        if len(candidates) != 1 or candidates[0].timeframe.lower() != c.timeframe.lower():
            return "TIMEFRAME_IDENTITY_MISMATCH"
        if now < max(q.finalized_time, s.selection_time or s.eligibility_time, c.confirmed_time):
            return "ORDER_PRECEDES_FROZEN_INPUT"
        if availability is None or not availability.confirmed:
            return "POSITION_AVAILABILITY_NOT_CONFIRMED"
        if availability.symbol != c.symbol or availability.checked_time > now or availability.checked_time < q.finalized_time:
            return "POSITION_AVAILABILITY_IDENTITY_OR_CHRONOLOGY_INVALID"
        if availability.open_position_count != 0:
            return "LIVE_POSITION_ALREADY_EXISTS"
        return None

    def _transition(self, order, state, time, history):
        latest = self._latest(order.id, history)
        allowed = (order.state == OrderState.PENDING and state in (OrderState.ACTIVE, OrderState.CANCELLED)) or (order.state == OrderState.ACTIVE and state in (OrderState.FILLED, OrderState.CANCELLED))
        if latest != order or not allowed or time < order.state_time:
            return None
        return replace(order, record_id=self._uid("record", order.id, state.value, time), previous_record_id=order.record_id, state=state, state_time=int(time))

    def activate_order(self, *, order, activation_time, history):
        active = self._transition(order, OrderState.ACTIVE, int(activation_time), history)
        if active is None:
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "ORDER_ACTIVATION_INVALID", activation_time, history, order)
        new = EntryExecutionHistory(history.orders + (active,), history.fills, history.evaluations)
        return EntryExecutionResult(active, None, None, new)

    def cancel_order(self, *, order, invalidation_time, history):
        cancelled = self._transition(order, OrderState.CANCELLED, int(invalidation_time), history)
        if cancelled is None:
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "ORDER_CANCELLATION_INVALID", invalidation_time, history, order)
        new = EntryExecutionHistory(history.orders + (cancelled,), history.fills, history.evaluations)
        return EntryExecutionResult(cancelled, None, None, new)

    def evaluate_candle(self, *, order: EntryOrder, candle: EntryCandle, history: EntryExecutionHistory) -> EntryExecutionResult:
        if self._latest(order.id, history) != order or order.state != OrderState.ACTIVE:
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "ORDER_NOT_ACTIVE_OR_NOT_LATEST", candle.closed_time, history, order)
        if any(fill.order_id == order.id for fill in history.fills):
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "DUPLICATE_ENTRY_FILL", candle.closed_time, history, order)
        if candle.symbol != order.symbol or candle.timeframe.lower() != order.timeframe.lower():
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "CANDLE_IDENTITY_MISMATCH", candle.closed_time, history, order)
        if candle.opened_time < order.state_time or candle.closed_time < candle.opened_time:
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "CANDLE_CHRONOLOGY_INVALID", candle.closed_time, history, order)
        prior = [row for row in history.evaluations if row.order_id == order.id]
        if any(row.candle_id == candle.id for row in prior) or any(row.closed_time > candle.opened_time for row in prior):
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "CANDLE_DUPLICATE_OR_OUT_OF_ORDER", candle.closed_time, history, order)
        try:
            o, h, l, c = map(self._decimal, (candle.open, candle.high, candle.low, candle.close))
        except ValueError:
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "CANDLE_PRICE_INVALID", candle.closed_time, history, order)
        if h < max(o, l, c) or l > min(o, h, c) or any(not self._on_grid(v, order.minimum_tick) for v in (o, h, l, c)):
            return self._error(EntryExecutionErrorCode.ENTRY_INVALID, "CANDLE_GEOMETRY_OR_TICK_GRID_INVALID", candle.closed_time, history, order)
        touched = l <= order.limit_price <= h
        evaluation = EntryCandleEvaluation(self._uid("evaluation", order.id, candle.id, candle.closed_time), order.id, candle.id, candle.opened_time, candle.closed_time, touched)
        observed = EntryExecutionHistory(history.orders, history.fills, history.evaluations + (evaluation,))
        if not touched:
            return self._error(EntryExecutionErrorCode.ENTRY_NOT_FILLED, "FROZEN_EQ_NOT_TOUCHED", candle.closed_time, observed, order)
        filled = self._transition(order, OrderState.FILLED, candle.closed_time, history)
        assert filled is not None
        fill = EntryFill(self._uid("fill", order.id, candle.id, order.limit_price, candle.closed_time), order.id, filled.record_id, order.setup_id, order.entry_zone_selection_id, candle.id, order.symbol, order.timeframe, order.side, order.limit_price, candle.closed_time, order.mode)
        new = EntryExecutionHistory(history.orders + (filled,), history.fills + (fill,), history.evaluations + (evaluation,))
        return EntryExecutionResult(filled, fill, None, new)
