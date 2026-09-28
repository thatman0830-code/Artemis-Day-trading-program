from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope


@dataclass(frozen=True)
class ProfitFactorSnapshot:
    id: str
    scope_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    input_version: str
    calculation_version: str
    as_of_time: int
    trade_count: int
    total_winning_net_pnl: Decimal
    summed_negative_net_pnl: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class ProfitFactorError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class ProfitFactorHistory:
    snapshots: tuple[ProfitFactorSnapshot, ...] = ()


@dataclass(frozen=True)
class ProfitFactorResult:
    snapshot: ProfitFactorSnapshot | None
    error: ProfitFactorError | None
    history: ProfitFactorHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class ProfitFactorEngine:
    """Canonical #29.7.2.4 profit factor over finalized trade NetPnL."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.4:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, scope, as_of, history):
        scope_id = scope.id if scope else None
        error = ProfitFactorError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return ProfitFactorResult(None, error, history)

    def calculate(self, *, scope: TradeCountScope | None, trades: tuple[TradeAccounting, ...] | None, as_of_time: int, history: ProfitFactorHistory = ProfitFactorHistory()) -> ProfitFactorResult:
        as_of = int(as_of_time)
        if scope is None or trades is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_PROFIT_FACTOR_INPUT_MISSING", scope, as_of, history)
        if not scope.immutable or as_of < 0 or not all(value.strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.calculation_version)):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "PROFIT_FACTOR_SCOPE_INVALID", scope, as_of, history)
        trade_ids = [trade.trade_id for trade in trades]
        record_ids = [trade.id for trade in trades]
        if len(trade_ids) != len(set(trade_ids)) or len(record_ids) != len(set(record_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CANONICAL_TRADE_KEY", scope, as_of, history)
        for trade in trades:
            reason = self._validate_trade(scope, trade)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        eligible = tuple(sorted((trade for trade in trades if trade.closed_time <= as_of), key=lambda trade: (trade.closed_time, trade.trade_id)))
        future = tuple(sorted(trade.trade_id for trade in trades if trade.closed_time > as_of))
        try:
            pnl = tuple(self._decimal(trade.net_pnl) for trade in eligible)
        except ValueError:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "NON_FINITE_PROFIT_FACTOR_INPUT", scope, as_of, history)
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            gross_profit = sum((value for value in pnl if value > 0), Decimal("0"))
            summed_negative = sum((value for value in pnl if value < 0), Decimal("0"))
            gross_loss = abs(summed_negative)
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss
            elif gross_profit > 0:
                profit_factor = Decimal("Infinity")
            else:
                profit_factor = None
        source_ids = tuple(trade.id for trade in eligible)
        snapshot_id = self._uid("snapshot", scope.id, as_of, *source_ids)
        exact = next((snapshot for snapshot in history.snapshots if snapshot.id == snapshot_id), None)
        if exact:
            return ProfitFactorResult(exact, None, history)
        if any((snapshot.scope_id, snapshot.as_of_time) == (scope.id, as_of) for snapshot in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_PROFIT_FACTOR_SNAPSHOT", scope, as_of, history)
        snapshot = ProfitFactorSnapshot(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe,
            scope.setup_model, scope.direction, scope.input_version, scope.calculation_version,
            as_of, len(eligible), gross_profit, summed_negative, gross_loss, profit_factor,
            tuple(trade.trade_id for trade in eligible), source_ids, future,
            "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return ProfitFactorResult(snapshot, None, ProfitFactorHistory(history.snapshots + (snapshot,)))

    @staticmethod
    def _validate_trade(scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if trade.strategy_id != scope.strategy_id or trade.symbol != scope.symbol:
            return "PROFIT_FACTOR_SCOPE_IDENTITY_MISMATCH"
        if trade.timeframe.lower() != scope.timeframe.lower():
            return "PROFIT_FACTOR_TIMEFRAME_MISMATCH"
        if trade.model != scope.setup_model or trade.direction != scope.direction:
            return "PROFIT_FACTOR_MODEL_OR_DIRECTION_MISMATCH"
        if trade.input_version != scope.input_version:
            return "PROFIT_FACTOR_INPUT_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN):
            return "TRADE_RESULT_INVALID"
        return None
