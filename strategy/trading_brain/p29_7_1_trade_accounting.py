from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p29_1_entry_execution import EntryFill
from strategy.trading_brain.p29_2_position_sizing import PositionSizing
from strategy.trading_brain.p29_4_exit_resolution import ExecutionRecord
from strategy.trading_brain.p29_5_execution_costs import ExecutionCostRecord
from strategy.trading_brain.p29_6_position_lifecycle import Position, PositionState


class TradeResult(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


class AccountingErrorCode(str, Enum):
    ACCOUNTING_ERROR = "ACCOUNTING_ERROR"


@dataclass(frozen=True)
class TradeAccounting:
    id: str
    trade_id: str
    position_id: str
    setup_id: str
    setup_candidate_id: str
    strategy_id: str
    model: object
    direction: StructuralRegime
    symbol: str
    timeframe: str
    input_version: str
    entry_fill_id: str
    sizing_id: str
    exit_execution_id: str
    execution_cost_record_id: str
    position_snapshot_id: str
    opened_time: int
    closed_time: int
    quantity: Decimal
    minimum_tick: Decimal
    tick_value: Decimal
    contract_multiplier: Decimal
    mechanical_entry_price: Decimal
    mechanical_exit_price: Decimal
    economic_entry_price: Decimal
    economic_exit_price: Decimal
    direction_multiplier: Decimal
    entry_spread: Decimal
    exit_spread: Decimal
    entry_slippage: Decimal
    exit_slippage: Decimal
    commission: Decimal
    transaction_fees: Decimal
    explicit_cash_costs: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    maximum_allowed_risk: Decimal
    actual_risk_dollars: Decimal
    gross_r: Decimal
    net_r: Decimal
    pre_trade_equity: Decimal
    account_equity_change: Decimal
    post_trade_equity: Decimal
    trade_result: TradeResult
    rounding_mode: str
    accounting_time: int
    immutable: bool = True


@dataclass(frozen=True)
class AccountingError:
    id: str
    code: AccountingErrorCode
    reason: str
    position_id: str | None
    accounting_time: int
    immutable: bool = True


@dataclass(frozen=True)
class TradeAccountingHistory:
    records: tuple[TradeAccounting, ...] = ()


@dataclass(frozen=True)
class TradeAccountingResult:
    record: TradeAccounting | None
    error: AccountingError | None
    history: TradeAccountingHistory

    @property
    def valid(self) -> bool:
        return self.record is not None and self.error is None


class TradeAccountingEngine:
    """Canonical #29.7.1 finalized per-trade facts only; no persistence or analytics."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.1:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, reason, time, history, position=None):
        pid = position.id if position else None
        error = AccountingError(self._uid("error", pid or "NONE", reason, time), AccountingErrorCode.ACCOUNTING_ERROR, reason, pid, int(time))
        return TradeAccountingResult(None, error, history)

    def calculate(
        self, *, strategy_id: str,
        position: Position | None, entry_fill: EntryFill | None,
        sizing: PositionSizing | None, exit_execution: ExecutionRecord | None,
        costs: ExecutionCostRecord | None, accounting_time: int,
        history: TradeAccountingHistory = TradeAccountingHistory(),
    ) -> TradeAccountingResult:
        now = int(accounting_time)
        if not strategy_id.strip():
            return self._invalid("STRATEGY_ID_MISSING", now, history, position)
        if any(value is None for value in (position, entry_fill, sizing, exit_execution, costs)):
            return self._invalid("REQUIRED_ACCOUNTING_INPUT_MISSING", now, history, position)
        assert position and entry_fill and sizing and exit_execution and costs
        reason = self._validate(position, entry_fill, sizing, exit_execution, costs, now)
        if reason:
            return self._invalid(reason, now, history, position)
        record_id = self._uid("record", strategy_id, position.snapshot_id, entry_fill.id, sizing.id, exit_execution.id, costs.id, now)
        exact = next((row for row in history.records if row.id == record_id), None)
        if exact:
            return TradeAccountingResult(exact, None, history)
        if any(row.position_id == position.id for row in history.records):
            return self._invalid("CONFLICTING_TRADE_ACCOUNTING_RECORD", now, history, position)

        direction_multiplier = Decimal("1") if position.direction == StructuralRegime.BULLISH else Decimal("-1")
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            gross = (costs.economic_exit_price - costs.economic_entry_price) * direction_multiplier * sizing.proposed_quantity * sizing.contract_multiplier
            net = gross - costs.explicit_cash_costs
            gross_r = gross / sizing.actual_risk_dollars
            net_r = net / sizing.actual_risk_dollars
            post_equity = sizing.pre_fill_equity + net
        result = TradeResult.WIN if net > 0 else TradeResult.LOSS if net < 0 else TradeResult.BREAKEVEN
        record = TradeAccounting(
            record_id, self._uid("trade", position.id), position.id,
            position.setup_id, position.setup_candidate_id, strategy_id,
            position.model, position.direction, position.symbol, position.timeframe,
            position.input_version, entry_fill.id, sizing.id, exit_execution.id,
            costs.id, position.snapshot_id, position.opened_time,
            position.exit_time, sizing.proposed_quantity,
            sizing.stop_distance / sizing.stop_distance_ticks, sizing.tick_value,
            sizing.contract_multiplier, entry_fill.fill_price,
            exit_execution.exit_price, costs.economic_entry_price,
            costs.economic_exit_price, direction_multiplier,
            costs.entry_spread, costs.exit_spread, costs.entry_slippage,
            costs.exit_slippage, costs.commission, costs.transaction_fees,
            costs.explicit_cash_costs, gross, net, sizing.maximum_risk,
            sizing.actual_risk_dollars, gross_r, net_r,
            sizing.pre_fill_equity, net, post_equity, result,
            "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS", now,
        )
        updated = TradeAccountingHistory(history.records + (record,))
        return TradeAccountingResult(record, None, updated)

    def _validate(self, position, fill, sizing, execution, costs, now):
        if position.state != PositionState.CLOSED or position.exit_execution_id is None:
            return "POSITION_NOT_CANONICALLY_CLOSED"
        identity = (
            position.setup_id == fill.setup_id == sizing.setup_id == execution.setup_id == costs.setup_id
            and position.setup_candidate_id == sizing.setup_candidate_id
            and position.model == sizing.model == costs.model
            and position.direction == sizing.direction == costs.direction
            and position.entry_execution_id == fill.id == sizing.entry_fill_id == costs.entry_fill_id
            and position.sizing_id == sizing.id == costs.position_sizing_id
            and position.exit_execution_id == execution.id == costs.exit_execution_id
            and position.snapshot_id != position.previous_snapshot_id
        )
        if not identity:
            return "ACCOUNTING_SOURCE_IDENTITY_MISMATCH"
        if position.symbol != fill.symbol or position.symbol != sizing.symbol or position.symbol != execution.symbol or position.symbol != costs.symbol:
            return "ACCOUNTING_SYMBOL_MISMATCH"
        if any(value.lower() != position.timeframe.lower() for value in (fill.timeframe, sizing.timeframe, execution.timeframe, costs.timeframe)):
            return "ACCOUNTING_TIMEFRAME_MISMATCH"
        if sizing.input_version != position.input_version or costs.input_version != position.input_version or execution.input_version != position.input_version:
            return "ACCOUNTING_INPUT_VERSION_MISMATCH"
        try:
            numeric = tuple(map(self._decimal, (
                position.quantity, position.entry_price, position.exit_price,
                sizing.proposed_quantity, sizing.contract_multiplier,
                sizing.tick_value, sizing.stop_distance, sizing.stop_distance_ticks,
                sizing.pre_fill_equity, sizing.maximum_risk,
                sizing.actual_risk_dollars, fill.fill_price,
                execution.exit_price, costs.mechanical_entry_price,
                costs.mechanical_exit_price, costs.economic_entry_price,
                costs.economic_exit_price, costs.commission,
                costs.transaction_fees, costs.explicit_cash_costs,
            )))
        except (ValueError, TypeError):
            return "NON_FINITE_ACCOUNTING_INPUT"
        quantity, entry, exit_price, sized_quantity, multiplier, tick_value, distance, distance_ticks, equity, maximum_risk, actual_risk, fill_price, resolved_exit, mechanical_entry, mechanical_exit, economic_entry, economic_exit, commission, transaction_fees, explicit = numeric
        if any(value <= 0 for value in (quantity, entry, exit_price, sized_quantity, multiplier, tick_value, distance, distance_ticks, equity, maximum_risk, actual_risk, fill_price, resolved_exit, mechanical_entry, mechanical_exit, economic_entry, economic_exit)):
            return "NON_POSITIVE_ACCOUNTING_INPUT"
        if any(value < 0 for value in (commission, transaction_fees, explicit)):
            return "NEGATIVE_EXECUTION_COST"
        if explicit != commission + transaction_fees or costs.price_friction_cash_cost != 0:
            return "EXECUTION_COST_DOUBLE_COUNT_OR_AGGREGATION_INVALID"
        if not (quantity == sized_quantity == costs.quantity and entry == fill_price == mechanical_entry and exit_price == resolved_exit == mechanical_exit):
            return "ACCOUNTING_PRICE_OR_QUANTITY_MISMATCH"
        if multiplier != costs.contract_multiplier:
            return "ACCOUNTING_MULTIPLIER_MISMATCH"
        if position.exit_price != execution.exit_price or position.exit_reason != execution.exit_reason or position.exit_time != execution.exit_time:
            return "POSITION_EXIT_FACT_MISMATCH"
        if now < max(position.exit_time, sizing.calculated_time, execution.exit_time, costs.calculated_time) or position.opened_time != fill.fill_time or position.exit_time < position.opened_time:
            return "ACCOUNTING_CHRONOLOGY_INVALID"
        return None
