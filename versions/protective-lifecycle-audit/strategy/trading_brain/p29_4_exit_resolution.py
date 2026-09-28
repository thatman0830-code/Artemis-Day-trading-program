from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p29_1_entry_execution import OrderState
from strategy.trading_brain.p29_3_protective_orders import ProtectiveOrder, ProtectiveOrderHistory, ProtectiveOrderSet
from strategy.trading_brain.position_state_contract import PositionState


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TARGET = "TARGET"
    STOP_LOSS_GAP = "STOP_LOSS_GAP"
    OHLC_AMBIGUOUS_STOP_PRIORITY = "OHLC_AMBIGUOUS_STOP_PRIORITY"


class ExitResolutionErrorCode(str, Enum):
    EXIT_RESOLUTION_INVALID = "EXIT_RESOLUTION_INVALID"


@dataclass(frozen=True)
class OpenPositionBoundary:
    id: str
    setup_id: str
    entry_fill_id: str
    protective_set_id: str
    symbol: str
    timeframe: str
    input_version: str
    state: object
    opened_time: int
    confirmed: bool = True
    immutable: bool = True


@dataclass(frozen=True)
class PriceObservation:
    id: str
    price: Decimal
    timestamp: int
    immutable: bool = True


@dataclass(frozen=True)
class ExitMarketData:
    id: str
    symbol: str
    timeframe: str
    opened_time: int
    closed_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    input_version: str
    chronological_prices: tuple[PriceObservation, ...] = ()
    immutable: bool = True


@dataclass(frozen=True)
class ExitCandleEvaluation:
    id: str
    protective_set_id: str
    market_data_id: str
    stop_touched: bool
    target_touched: bool
    first_observable_price: Decimal
    evaluated_time: int
    resolution_id: str | None
    immutable: bool = True


@dataclass(frozen=True)
class ExecutionRecord:
    id: str
    setup_id: str
    protective_set_id: str
    oco_group_id: str
    market_data_id: str
    winning_order_id: str
    cancelled_order_id: str
    exit_reason: ExitReason
    exit_price: Decimal
    exit_time: int
    first_observable_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    symbol: str
    timeframe: str
    input_version: str
    immutable: bool = True


@dataclass(frozen=True)
class ExitResolutionError:
    id: str
    code: ExitResolutionErrorCode
    reason: str
    protective_set_id: str | None
    event_time: int
    immutable: bool = True


@dataclass(frozen=True)
class ExitResolutionHistory:
    evaluations: tuple[ExitCandleEvaluation, ...] = ()
    resolutions: tuple[ExecutionRecord, ...] = ()
    protective_transitions: tuple[ProtectiveOrder, ...] = ()


@dataclass(frozen=True)
class ExitResolutionResult:
    evaluation: ExitCandleEvaluation | None
    resolution: ExecutionRecord | None
    stop_order: ProtectiveOrder | None
    target_order: ProtectiveOrder | None
    error: ExitResolutionError | None
    history: ExitResolutionHistory

    @property
    def exited(self) -> bool:
        return self.resolution is not None and self.error is None


class ExitResolutionEngine:
    """Canonical #29.4 deterministic exit facts; no costs, PnL, or lifecycle mutation."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.4:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, reason, time, history, protective_set=None):
        set_id = protective_set.id if protective_set else None
        error = ExitResolutionError(self._uid("error", set_id or "NONE", reason, time), ExitResolutionErrorCode.EXIT_RESOLUTION_INVALID, reason, set_id, int(time))
        return ExitResolutionResult(None, None, None, None, error, history)

    def evaluate(
        self, *, protective_set: ProtectiveOrderSet | None,
        protective_history: ProtectiveOrderHistory | None,
        position: OpenPositionBoundary | None,
        market: ExitMarketData | None,
        history: ExitResolutionHistory = ExitResolutionHistory(),
    ) -> ExitResolutionResult:
        if any(value is None for value in (protective_set, protective_history, position, market)):
            return self._invalid("REQUIRED_EXIT_INPUT_MISSING", getattr(market, "closed_time", 0), history, protective_set)
        assert protective_set and protective_history and position and market
        existing_eval = next((row for row in history.evaluations if row.protective_set_id == protective_set.id and row.market_data_id == market.id), None)
        if existing_eval is not None:
            resolution = next((row for row in history.resolutions if row.id == existing_eval.resolution_id), None)
            stop, target = self._terminal_orders(protective_set, history, resolution)
            return ExitResolutionResult(existing_eval, resolution, stop, target, None, history)
        if any(row.protective_set_id == protective_set.id for row in history.resolutions):
            return self._invalid("PROTECTIVE_SET_ALREADY_RESOLVED", market.closed_time, history, protective_set)
        reason = self._validate(protective_set, protective_history, position, market, history)
        if reason:
            return self._invalid(reason, market.closed_time, history, protective_set)
        stop_price, target_price = protective_set.stop_order.price, protective_set.target_order.price
        prices = market.chronological_prices
        first = prices[0].price if prices else market.open
        direction = protective_set.stop_order.direction
        gap_stop = (direction == StructuralRegime.BULLISH and first < stop_price) or (direction == StructuralRegime.BEARISH and first > stop_price)
        if gap_stop:
            outcome = (ExitReason.STOP_LOSS_GAP, first, protective_set.stop_order, protective_set.target_order, market.opened_time)
            stop_touched, target_touched = True, False
        elif prices:
            outcome, stop_touched, target_touched = self._chronological(direction, prices, stop_price, target_price, protective_set)
        else:
            stop_touched = market.low <= stop_price if direction == StructuralRegime.BULLISH else market.high >= stop_price
            target_touched = market.high >= target_price if direction == StructuralRegime.BULLISH else market.low <= target_price
            if stop_touched and target_touched:
                outcome = (ExitReason.OHLC_AMBIGUOUS_STOP_PRIORITY, stop_price, protective_set.stop_order, protective_set.target_order, market.closed_time)
            elif stop_touched:
                outcome = (ExitReason.STOP_LOSS, stop_price, protective_set.stop_order, protective_set.target_order, market.closed_time)
            elif target_touched:
                outcome = (ExitReason.TARGET, target_price, protective_set.target_order, protective_set.stop_order, market.closed_time)
            else:
                outcome = None
        resolution = None
        stop_terminal = target_terminal = None
        if outcome:
            exit_reason, exit_price, winner, sibling, exit_time = outcome
            resolution_id = self._uid("resolution", protective_set.id, market.id, exit_reason.value, exit_price, exit_time)
            resolution = ExecutionRecord(resolution_id, protective_set.setup_id, protective_set.id, protective_set.oco_group.id, market.id, winner.id, sibling.id, exit_reason, exit_price, exit_time, first, stop_price, target_price, market.symbol, market.timeframe, market.input_version)
            winner_terminal = replace(winner, record_id=self._uid("record", winner.id, "FILLED", exit_time), previous_record_id=winner.record_id, state=OrderState.FILLED, state_time=exit_time)
            sibling_terminal = replace(sibling, record_id=self._uid("record", sibling.id, "CANCELLED", exit_time), previous_record_id=sibling.record_id, state=OrderState.CANCELLED, state_time=exit_time)
            if winner.id == protective_set.stop_order.id:
                stop_terminal, target_terminal = winner_terminal, sibling_terminal
            else:
                target_terminal, stop_terminal = winner_terminal, sibling_terminal
        evaluation = ExitCandleEvaluation(self._uid("evaluation", protective_set.id, market.id, market.closed_time), protective_set.id, market.id, stop_touched, target_touched, first, market.closed_time, resolution.id if resolution else None)
        updated = ExitResolutionHistory(
            history.evaluations + (evaluation,),
            history.resolutions + ((resolution,) if resolution else ()),
            history.protective_transitions + ((stop_terminal, target_terminal) if resolution else ()),
        )
        return ExitResolutionResult(evaluation, resolution, stop_terminal, target_terminal, None, updated)

    @staticmethod
    def _chronological(direction, prices, stop, target, protective_set):
        stop_seen = target_seen = False
        for observation in prices:
            stop_hit = observation.price <= stop if direction == StructuralRegime.BULLISH else observation.price >= stop
            target_hit = observation.price >= target if direction == StructuralRegime.BULLISH else observation.price <= target
            stop_seen |= stop_hit; target_seen |= target_hit
            if stop_hit:
                return (ExitReason.STOP_LOSS, stop, protective_set.stop_order, protective_set.target_order, observation.timestamp), stop_seen, target_seen
            if target_hit:
                return (ExitReason.TARGET, target, protective_set.target_order, protective_set.stop_order, observation.timestamp), stop_seen, target_seen
        return None, stop_seen, target_seen

    def _validate(self, protective_set, protective_history, position, market, history):
        stop, target = protective_set.stop_order, protective_set.target_order
        latest_stop = next((x for x in reversed(protective_history.transitions) if x.id == stop.id), None)
        latest_target = next((x for x in reversed(protective_history.transitions) if x.id == target.id), None)
        if latest_stop != stop or latest_target != target or stop.state != OrderState.ACTIVE or target.state != OrderState.ACTIVE:
            return "PROTECTIVE_SET_NOT_ACTIVE"
        if not position.confirmed or getattr(position.state, "value", position.state) != "OPEN":
            return "OPEN_POSITION_NOT_CONFIRMED"
        if (position.setup_id != protective_set.setup_id or position.entry_fill_id != protective_set.oco_group.entry_fill_id or position.protective_set_id != protective_set.id):
            return "POSITION_PROTECTIVE_IDENTITY_MISMATCH"
        if market.symbol != stop.symbol or position.symbol != stop.symbol:
            return "SYMBOL_IDENTITY_MISMATCH"
        if market.timeframe.lower() != stop.timeframe.lower() or position.timeframe.lower() != stop.timeframe.lower():
            return "TIMEFRAME_IDENTITY_MISMATCH"
        if market.input_version != stop.input_version or position.input_version != stop.input_version:
            return "INPUT_VERSION_MISMATCH"
        if market.opened_time < max(stop.state_time, target.state_time, position.opened_time) or market.closed_time < market.opened_time:
            return "MARKET_DATA_CHRONOLOGY_INVALID"
        previous = [row for row in history.evaluations if row.protective_set_id == protective_set.id]
        if any(row.evaluated_time > market.opened_time for row in previous):
            return "MARKET_DATA_RETROACTIVE_OR_OUT_OF_ORDER"
        try:
            o, h, l, c, stop_price, target_price, grid = map(self._decimal, (market.open, market.high, market.low, market.close, stop.price, target.price, stop.minimum_tick))
        except ValueError:
            return "NON_FINITE_EXIT_INPUT"
        if grid <= 0 or h < max(o, l, c) or l > min(o, h, c) or any(value <= 0 or value % grid != 0 for value in (o, h, l, c, stop_price, target_price)):
            return "EXIT_PRICE_GEOMETRY_OR_TICK_GRID_INVALID"
        if stop.direction == StructuralRegime.BULLISH and not stop_price < target_price:
            return "PROTECTIVE_GEOMETRY_INVALID"
        if stop.direction == StructuralRegime.BEARISH and not target_price < stop_price:
            return "PROTECTIVE_GEOMETRY_INVALID"
        if market.chronological_prices:
            prior_time = market.opened_time - 1
            for observation in market.chronological_prices:
                try:
                    price = self._decimal(observation.price)
                except ValueError:
                    return "CHRONOLOGICAL_PRICE_INVALID"
                if observation.timestamp < market.opened_time or observation.timestamp > market.closed_time or observation.timestamp <= prior_time or price <= 0 or price % grid != 0:
                    return "CHRONOLOGICAL_PRICE_INVALID"
                prior_time = observation.timestamp
        return None

    @staticmethod
    def _terminal_orders(protective_set, history, resolution):
        if resolution is None:
            return None, None
        stop = next((x for x in reversed(history.protective_transitions) if x.id == protective_set.stop_order.id), None)
        target = next((x for x in reversed(history.protective_transitions) if x.id == protective_set.target_order.id), None)
        return stop, target
