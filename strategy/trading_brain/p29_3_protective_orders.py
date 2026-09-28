from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p13_stop_loss_selection import StopSelection
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p24_lrl_selection import LRL, LRLRole
from strategy.trading_brain.p27_setup_qualification import FinalSetupQualification, SetupModel
from strategy.trading_brain.p29_1_entry_execution import EntryFill, EntryOrder, ExecutionMode, OrderSide, OrderState
from strategy.trading_brain.p29_2_position_sizing import PositionSizing


class ProtectiveOrderKind(str, Enum):
    STOP = "STOP"
    TARGET = "TARGET"


class ProtectiveOrderErrorCode(str, Enum):
    PROTECTIVE_ORDER_INVALID = "PROTECTIVE_ORDER_INVALID"
    TARGET_ORDER_INVALID = "TARGET_ORDER_INVALID"


@dataclass(frozen=True)
class ProtectiveOrder:
    id: str
    record_id: str
    previous_record_id: str | None
    oco_group_id: str
    setup_id: str
    entry_fill_id: str
    sizing_id: str
    source_price_id: str
    symbol: str
    timeframe: str
    model: SetupModel
    direction: StructuralRegime
    kind: ProtectiveOrderKind
    side: OrderSide
    price: Decimal
    quantity: Decimal
    minimum_tick: Decimal
    quantity_increment: Decimal
    input_version: str
    mode: ExecutionMode
    state: OrderState
    created_time: int
    state_time: int
    exchange_submission_authorized: bool = False
    immutable: bool = True


@dataclass(frozen=True)
class OCOGroup:
    id: str
    setup_id: str
    entry_fill_id: str
    sizing_id: str
    stop_order_id: str
    target_order_id: str
    created_time: int
    resolution_pending: bool = True
    exchange_submission_authorized: bool = False
    immutable: bool = True


@dataclass(frozen=True)
class ProtectiveOrderSet:
    id: str
    setup_id: str
    stop_order: ProtectiveOrder
    target_order: ProtectiveOrder
    oco_group: OCOGroup
    created_time: int
    immutable: bool = True


@dataclass(frozen=True)
class ProtectiveOrderHistory:
    sets: tuple[ProtectiveOrderSet, ...] = ()
    transitions: tuple[ProtectiveOrder, ...] = ()


@dataclass(frozen=True)
class ProtectiveOrderError:
    id: str
    code: ProtectiveOrderErrorCode
    reason: str
    setup_id: str | None
    event_time: int
    immutable: bool = True


@dataclass(frozen=True)
class ProtectiveOrderResult:
    protective_set: ProtectiveOrderSet | None
    error: ProtectiveOrderError | None
    history: ProtectiveOrderHistory

    @property
    def valid(self) -> bool:
        return self.protective_set is not None and self.error is None


class ProtectiveOrderEngine:
    """Canonical #29.3 paper/testnet protective intent facts only."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.3:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, time, history, qualification=None):
        setup_id = qualification.setup_id if qualification else None
        error = ProtectiveOrderError(self._uid("error", setup_id or "NONE", code.value, reason, time), code, reason, setup_id, int(time))
        return ProtectiveOrderResult(None, error, history)

    def create(
        self, *, qualification: FinalSetupQualification | None,
        stop: StopSelection | None, target: LRL | None,
        entry_order: EntryOrder | None, fill: EntryFill | None,
        sizing: PositionSizing | None, created_time: int,
        history: ProtectiveOrderHistory = ProtectiveOrderHistory(),
    ) -> ProtectiveOrderResult:
        now = int(created_time)
        if any(value is None for value in (qualification, stop, target, entry_order, fill, sizing)):
            return self._invalid(ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID, "REQUIRED_PROTECTIVE_INPUT_MISSING", now, history, qualification)
        assert qualification and stop and target and entry_order and fill and sizing
        reason, code = self._validate(qualification, stop, target, entry_order, fill, sizing, now)
        if reason:
            return self._invalid(code, reason, now, history, qualification)

        set_id = self._uid("set", qualification.id, stop.id, target.id, fill.id, sizing.id, now)
        exact = next((item for item in history.sets if item.id == set_id), None)
        if exact is not None:
            return ProtectiveOrderResult(exact, None, history)
        if any(item.setup_id == qualification.setup_id for item in history.sets):
            return self._invalid(ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID, "CONFLICTING_PROTECTIVE_ORDER_SET", now, history, qualification)

        oco_id = self._uid("oco", set_id)
        stop_id, target_id = self._uid("stop", set_id), self._uid("target", set_id)
        exit_side = OrderSide.SELL if qualification.direction == StructuralRegime.BULLISH else OrderSide.BUY
        common = dict(
            oco_group_id=oco_id, setup_id=qualification.setup_id,
            entry_fill_id=fill.id, sizing_id=sizing.id, symbol=entry_order.symbol,
            timeframe=entry_order.timeframe, model=qualification.model,
            direction=qualification.direction,
            side=exit_side, quantity=sizing.proposed_quantity,
            minimum_tick=entry_order.minimum_tick,
            quantity_increment=sizing.quantity_increment,
            input_version=sizing.input_version, mode=entry_order.mode,
            state=OrderState.PENDING, created_time=now, state_time=now,
        )
        stop_order = ProtectiveOrder(stop_id, self._uid("record", stop_id, "PENDING", now), None, source_price_id=stop.id, kind=ProtectiveOrderKind.STOP, price=stop.stop_price, **common)
        target_order = ProtectiveOrder(target_id, self._uid("record", target_id, "PENDING", now), None, source_price_id=target.id, kind=ProtectiveOrderKind.TARGET, price=target.level, **common)
        oco = OCOGroup(oco_id, qualification.setup_id, fill.id, sizing.id, stop_id, target_id, now)
        protective_set = ProtectiveOrderSet(set_id, qualification.setup_id, stop_order, target_order, oco, now)
        updated = ProtectiveOrderHistory(history.sets + (protective_set,), history.transitions + (stop_order, target_order))
        return ProtectiveOrderResult(protective_set, None, updated)

    def _validate(self, q, stop, target, order, fill, sizing, now):
        try:
            entry, stop_price, target_price, quantity, tick, step = map(self._decimal, (
                fill.fill_price, stop.stop_price, target.level, sizing.proposed_quantity,
                order.minimum_tick, sizing.quantity_increment,
            ))
        except ValueError:
            return "NON_FINITE_PROTECTIVE_INPUT", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if order.state != OrderState.FILLED or fill.event != "ENTRY_FILL_CONFIRMED":
            return "ENTRY_FILL_NOT_CONFIRMED", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        identity = (
            q.setup_id == stop.setup_id == order.setup_id == fill.setup_id == sizing.setup_id
            and q.setup_candidate_id == order.setup_candidate_id == sizing.setup_candidate_id
            and q.model == stop.model == order.model == sizing.model
            and q.direction == stop.direction == order.direction == sizing.direction
            and q.id == order.final_qualification_id == sizing.final_qualification_id
            and q.stop_selection_id == stop.id == sizing.stop_selection_id
            and q.target_lrl_id == target.id
            and order.id == fill.order_id == sizing.entry_order_id
            and fill.id == sizing.entry_fill_id
        )
        if not identity:
            return "PROTECTIVE_INPUT_IDENTITY_MISMATCH", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if fill.order_record_id != order.record_id or fill.symbol != order.symbol or sizing.symbol != order.symbol:
            return "FILL_OR_SYMBOL_IDENTITY_MISMATCH", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if fill.timeframe.lower() != order.timeframe.lower() or sizing.timeframe.lower() != order.timeframe.lower():
            return "TIMEFRAME_IDENTITY_MISMATCH", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if sizing.authorized:
            return "SIZING_PROPOSAL_AUTHORIZATION_MUTATED", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if sizing.input_version.strip() == "":
            return "INPUT_VERSION_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if not target.active or target.historical or target.role != LRLRole.CONTINUATION_TARGET or target.regime != q.direction:
            return "FROZEN_TARGET_INVALID", ProtectiveOrderErrorCode.TARGET_ORDER_INVALID
        if not (entry == q.entry == stop.frozen_entry_price == order.limit_price == sizing.entry_price):
            return "FROZEN_ENTRY_MISMATCH", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if stop_price != q.stop or stop_price != sizing.stop_price:
            return "FROZEN_STOP_MISMATCH", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if target_price != q.target:
            return "FROZEN_TARGET_MISMATCH", ProtectiveOrderErrorCode.TARGET_ORDER_INVALID
        if tick <= 0 or step <= 0 or quantity <= 0 or any(price <= 0 or price % tick != 0 for price in (entry, stop_price, target_price)):
            return "PRICE_TICK_OR_QUANTITY_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if quantity % step != 0:
            return "QUANTITY_STEP_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if q.direction == StructuralRegime.BULLISH:
            if not stop_price < entry:
                return "LONG_STOP_GEOMETRY_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
            if not entry < target_price:
                return "LONG_TARGET_GEOMETRY_INVALID", ProtectiveOrderErrorCode.TARGET_ORDER_INVALID
        elif q.direction == StructuralRegime.BEARISH:
            if not entry < stop_price:
                return "SHORT_STOP_GEOMETRY_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
            if not target_price < entry:
                return "SHORT_TARGET_GEOMETRY_INVALID", ProtectiveOrderErrorCode.TARGET_ORDER_INVALID
        else:
            return "DIRECTION_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        if now < max(q.finalized_time, stop.selection_time, target.selected_time, order.state_time, fill.fill_time, sizing.calculated_time):
            return "PROTECTIVE_ORDER_CHRONOLOGY_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID
        return None, ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID

    def activate(self, *, protective_set: ProtectiveOrderSet, activation_time: int, history: ProtectiveOrderHistory) -> ProtectiveOrderResult:
        now = int(activation_time)
        known = next((item for item in history.sets if item.id == protective_set.id), None)
        latest_stop = next((x for x in reversed(history.transitions) if x.id == protective_set.stop_order.id), None)
        latest_target = next((x for x in reversed(history.transitions) if x.id == protective_set.target_order.id), None)
        if known != protective_set or latest_stop is None or latest_target is None:
            return self._invalid(ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID, "PROTECTIVE_SET_NOT_IN_HISTORY", now, history)
        if latest_stop.state == latest_target.state == OrderState.ACTIVE:
            return ProtectiveOrderResult(replace(protective_set, stop_order=latest_stop, target_order=latest_target), None, history)
        if latest_stop.state != OrderState.PENDING or latest_target.state != OrderState.PENDING or now < protective_set.created_time:
            return self._invalid(ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID, "PROTECTIVE_ACTIVATION_INVALID", now, history)
        stop = replace(latest_stop, record_id=self._uid("record", latest_stop.id, "ACTIVE", now), previous_record_id=latest_stop.record_id, state=OrderState.ACTIVE, state_time=now)
        target = replace(latest_target, record_id=self._uid("record", latest_target.id, "ACTIVE", now), previous_record_id=latest_target.record_id, state=OrderState.ACTIVE, state_time=now)
        active_set = replace(protective_set, stop_order=stop, target_order=target)
        updated = ProtectiveOrderHistory(history.sets, history.transitions + (stop, target))
        return ProtectiveOrderResult(active_set, None, updated)
