from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p29_1_entry_execution import EntryFill
from strategy.trading_brain.p29_2_position_sizing import PositionSizing
from strategy.trading_brain.p29_4_exit_resolution import ExecutionRecord


class CommissionModel(str, Enum):
    PER_UNIT = "PER_UNIT"
    PER_CONTRACT = "PER_CONTRACT"
    PERCENT_NOTIONAL = "PERCENT_NOTIONAL"
    FIXED_ORDER = "FIXED_ORDER"
    FIXED_TRADE = "FIXED_TRADE"
    ZERO = "ZERO"


class SlippageModel(str, Enum):
    NONE = "NONE"
    FIXED_TICKS = "FIXED_TICKS"
    FIXED_PRICE = "FIXED_PRICE"
    PERCENTAGE = "PERCENTAGE"
    INSTRUMENT_SPECIFIC = "INSTRUMENT_SPECIFIC"
    VOLATILITY_DEPENDENT = "VOLATILITY_DEPENDENT"


class ExecutionCostErrorCode(str, Enum):
    EXECUTION_COST_INVALID = "EXECUTION_COST_INVALID"


@dataclass(frozen=True)
class ExecutionCostSpecification:
    id: str
    symbol: str
    input_version: str
    effective_time: int
    minimum_tick: Decimal
    contract_multiplier: Decimal
    commission_model: CommissionModel
    commission_rate: Decimal
    transaction_fee_model: CommissionModel
    transaction_fee_rate: Decimal
    spread_model: SlippageModel
    spread_value: Decimal
    slippage_model: SlippageModel
    slippage_value: Decimal
    immutable: bool = True


@dataclass(frozen=True)
class ExecutionCostRecord:
    id: str
    setup_id: str
    model: object
    direction: StructuralRegime
    symbol: str
    timeframe: str
    entry_fill_id: str
    position_sizing_id: str
    exit_execution_id: str
    cost_specification_id: str
    input_version: str
    quantity: Decimal
    contract_multiplier: Decimal
    mechanical_entry_price: Decimal
    mechanical_exit_price: Decimal
    entry_notional: Decimal
    exit_notional: Decimal
    entry_spread: Decimal
    exit_spread: Decimal
    entry_slippage: Decimal
    exit_slippage: Decimal
    economic_entry_price: Decimal
    economic_exit_price: Decimal
    entry_commission: Decimal
    exit_commission: Decimal
    commission: Decimal
    entry_transaction_fee: Decimal
    exit_transaction_fee: Decimal
    transaction_fees: Decimal
    explicit_cash_costs: Decimal
    price_friction_cash_cost: Decimal
    rounding_mode: str
    calculated_time: int
    immutable: bool = True


@dataclass(frozen=True)
class ExecutionCostError:
    id: str
    code: ExecutionCostErrorCode
    reason: str
    setup_id: str | None
    calculated_time: int
    immutable: bool = True


@dataclass(frozen=True)
class ExecutionCostHistory:
    records: tuple[ExecutionCostRecord, ...] = ()


@dataclass(frozen=True)
class ExecutionCostResult:
    record: ExecutionCostRecord | None
    error: ExecutionCostError | None
    history: ExecutionCostHistory

    @property
    def valid(self) -> bool:
        return self.record is not None and self.error is None


class ExecutionCostEngine:
    """Canonical #29.5 economic-price and explicit-cash-cost facts only."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.5:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, reason, time, history, sizing=None):
        setup_id = sizing.setup_id if sizing else None
        error = ExecutionCostError(self._uid("error", setup_id or "NONE", reason, time), ExecutionCostErrorCode.EXECUTION_COST_INVALID, reason, setup_id, int(time))
        return ExecutionCostResult(None, error, history)

    def calculate(
        self, *, entry_fill: EntryFill | None,
        sizing: PositionSizing | None, exit_execution: ExecutionRecord | None,
        specification: ExecutionCostSpecification | None,
        calculated_time: int,
        history: ExecutionCostHistory = ExecutionCostHistory(),
    ) -> ExecutionCostResult:
        now = int(calculated_time)
        if any(value is None for value in (entry_fill, sizing, exit_execution, specification)):
            return self._invalid("REQUIRED_COST_INPUT_MISSING", now, history, sizing)
        assert entry_fill and sizing and exit_execution and specification
        reason = self._validate(entry_fill, sizing, exit_execution, specification, now)
        if reason:
            return self._invalid(reason, now, history, sizing)
        record_id = self._uid("record", entry_fill.id, sizing.id, exit_execution.id, specification.id, now)
        exact = next((row for row in history.records if row.id == record_id), None)
        if exact:
            return ExecutionCostResult(exact, None, history)
        if any(row.exit_execution_id == exit_execution.id for row in history.records):
            return self._invalid("CONFLICTING_EXECUTION_COST_RECORD", now, history, sizing)

        quantity = sizing.proposed_quantity
        multiplier = sizing.contract_multiplier
        entry = entry_fill.fill_price
        exit_price = exit_execution.exit_price
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            entry_notional = entry * quantity * multiplier
            exit_notional = exit_price * quantity * multiplier
            entry_spread = self._price_adjustment(specification.spread_model, specification.spread_value, entry, specification.minimum_tick)
            exit_spread = self._price_adjustment(specification.spread_model, specification.spread_value, exit_price, specification.minimum_tick)
            entry_slippage = self._price_adjustment(specification.slippage_model, specification.slippage_value, entry, specification.minimum_tick)
            exit_slippage = self._price_adjustment(specification.slippage_model, specification.slippage_value, exit_price, specification.minimum_tick)
            adverse_entry = entry_spread + entry_slippage
            adverse_exit = exit_spread + exit_slippage
            if sizing.direction == StructuralRegime.BULLISH:
                economic_entry, economic_exit = entry + adverse_entry, exit_price - adverse_exit
            else:
                economic_entry, economic_exit = entry - adverse_entry, exit_price + adverse_exit
            entry_commission, exit_commission = self._cash_sides(specification.commission_model, specification.commission_rate, quantity, multiplier, entry_notional, exit_notional)
            entry_fee, exit_fee = self._cash_sides(specification.transaction_fee_model, specification.transaction_fee_rate, quantity, multiplier, entry_notional, exit_notional)
            commission = entry_commission + exit_commission
            transaction_fees = entry_fee + exit_fee
            explicit = commission + transaction_fees
        if economic_entry <= 0 or economic_exit <= 0 or explicit < 0:
            return self._invalid("ECONOMIC_PRICE_OR_COST_INVALID", now, history, sizing)
        record = ExecutionCostRecord(
            record_id, sizing.setup_id, sizing.model, sizing.direction,
            sizing.symbol, sizing.timeframe, entry_fill.id, sizing.id,
            exit_execution.id, specification.id, sizing.input_version,
            quantity, multiplier, entry, exit_price, entry_notional, exit_notional,
            entry_spread, exit_spread, entry_slippage, exit_slippage,
            economic_entry, economic_exit, entry_commission, exit_commission,
            commission, entry_fee, exit_fee, transaction_fees, explicit,
            Decimal("0"), "NONE_CANONICAL_EXACT", now,
        )
        updated = ExecutionCostHistory(history.records + (record,))
        return ExecutionCostResult(record, None, updated)

    def _validate(self, fill, sizing, execution, spec, now):
        try:
            values = tuple(map(self._decimal, (fill.fill_price, sizing.proposed_quantity,
                sizing.contract_multiplier, execution.exit_price, spec.minimum_tick,
                spec.contract_multiplier, spec.commission_rate,
                spec.transaction_fee_rate, spec.spread_value, spec.slippage_value)))
        except ValueError:
            return "NON_FINITE_COST_INPUT"
        entry, quantity, multiplier, exit_price, tick, configured_multiplier, commission_rate, fee_rate, spread, slippage = values
        if any(value <= 0 for value in (entry, quantity, multiplier, exit_price, tick, configured_multiplier)):
            return "NON_POSITIVE_PRICE_QUANTITY_OR_INSTRUMENT"
        if any(value < 0 for value in (commission_rate, fee_rate, spread, slippage)):
            return "NEGATIVE_COST_CONFIGURATION"
        if commission_rate > Decimal("100") and spec.commission_model == CommissionModel.PERCENT_NOTIONAL:
            return "PERCENTAGE_RATE_OUT_OF_RANGE"
        if fee_rate > Decimal("100") and spec.transaction_fee_model == CommissionModel.PERCENT_NOTIONAL:
            return "PERCENTAGE_RATE_OUT_OF_RANGE"
        if (spec.spread_model == SlippageModel.PERCENTAGE and spread > Decimal("100")) or (spec.slippage_model == SlippageModel.PERCENTAGE and slippage > Decimal("100")):
            return "PERCENTAGE_RATE_OUT_OF_RANGE"
        if spec.spread_model in (SlippageModel.INSTRUMENT_SPECIFIC, SlippageModel.VOLATILITY_DEPENDENT) or spec.slippage_model in (SlippageModel.INSTRUMENT_SPECIFIC, SlippageModel.VOLATILITY_DEPENDENT):
            return "UNDEFINED_DYNAMIC_PRICE_FRICTION_MODEL"
        if spec.symbol != fill.symbol or sizing.symbol != fill.symbol or execution.symbol != fill.symbol:
            return "SYMBOL_IDENTITY_MISMATCH"
        if sizing.timeframe.lower() != fill.timeframe.lower() or execution.timeframe.lower() != fill.timeframe.lower():
            return "TIMEFRAME_IDENTITY_MISMATCH"
        if spec.input_version != sizing.input_version or execution.input_version != sizing.input_version:
            return "INPUT_VERSION_MISMATCH"
        if configured_multiplier != multiplier:
            return "CONTRACT_MULTIPLIER_MISMATCH"
        if not (sizing.setup_id == fill.setup_id == execution.setup_id and sizing.entry_fill_id == fill.id):
            return "COST_SOURCE_IDENTITY_MISMATCH"
        if entry != sizing.entry_price or exit_price != execution.exit_price:
            return "MECHANICAL_PRICE_MISMATCH"
        if entry % tick != 0 or exit_price % tick != 0 or tick != sizing.stop_distance / sizing.stop_distance_ticks:
            return "PRICE_TICK_GRID_MISMATCH"
        if now < max(fill.fill_time, sizing.calculated_time, execution.exit_time, spec.effective_time) or execution.exit_time < fill.fill_time:
            return "COST_INPUT_CHRONOLOGY_INVALID"
        return None

    @staticmethod
    def _price_adjustment(model, value, price, tick):
        if model == SlippageModel.NONE:
            return Decimal("0")
        if model == SlippageModel.FIXED_TICKS:
            return value * tick
        if model == SlippageModel.FIXED_PRICE:
            return value
        if model == SlippageModel.PERCENTAGE:
            if value > Decimal("100"):
                raise ValueError("percentage out of range")
            return price * value / Decimal("100")
        raise ValueError("undefined dynamic model")

    @staticmethod
    def _cash_sides(model, rate, quantity, multiplier, entry_notional, exit_notional):
        zero = Decimal("0")
        if model == CommissionModel.ZERO:
            return zero, zero
        if model == CommissionModel.PER_UNIT:
            each = rate * quantity
            return each, each
        if model == CommissionModel.PER_CONTRACT:
            each = rate * quantity * multiplier
            return each, each
        if model == CommissionModel.PERCENT_NOTIONAL:
            return entry_notional * rate / Decimal("100"), exit_notional * rate / Decimal("100")
        if model == CommissionModel.FIXED_ORDER:
            return rate, rate
        if model == CommissionModel.FIXED_TRADE:
            return rate, zero
        raise ValueError("invalid cash model")
