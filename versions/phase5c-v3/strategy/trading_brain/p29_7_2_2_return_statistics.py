from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope


@dataclass(frozen=True)
class ReturnStatistics:
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
    sample_size: int
    total_net_pnl: Decimal
    total_net_r: Decimal
    total_gross_pnl: Decimal
    total_gross_r: Decimal
    average_net_pnl: Decimal | None
    average_net_r: Decimal | None
    average_gross_pnl: Decimal | None
    average_gross_r: Decimal | None
    minimum_net_pnl: Decimal | None
    maximum_net_pnl: Decimal | None
    minimum_net_r: Decimal | None
    maximum_net_r: Decimal | None
    minimum_gross_pnl: Decimal | None
    maximum_gross_pnl: Decimal | None
    minimum_gross_r: Decimal | None
    maximum_gross_r: Decimal | None
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class ReturnStatisticsError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class ReturnStatisticsHistory:
    snapshots: tuple[ReturnStatistics, ...] = ()


@dataclass(frozen=True)
class ReturnStatisticsResult:
    snapshot: ReturnStatistics | None
    error: ReturnStatisticsError | None
    history: ReturnStatisticsHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class ReturnStatisticsEngine:
    """Canonical #29.7.2.2 finalized-trade population return statistics."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.2:" + kind + ":" + ":".join(map(str, parts))))

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
        sid = scope.id if scope else None
        error = ReturnStatisticsError(self._uid("error", sid or "NONE", code.value, reason, as_of), code, reason, sid, int(as_of))
        return ReturnStatisticsResult(None, error, history)

    def calculate(self, *, scope: TradeCountScope | None, trades: tuple[TradeAccounting, ...] | None, as_of_time: int, history: ReturnStatisticsHistory = ReturnStatisticsHistory()) -> ReturnStatisticsResult:
        as_of = int(as_of_time)
        if scope is None or trades is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_RETURN_INPUT_MISSING", scope, as_of, history)
        if not scope.immutable or as_of < 0 or not all(x.strip() for x in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.calculation_version)):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "RETURN_SCOPE_INVALID", scope, as_of, history)
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
            net_pnl = tuple(self._decimal(x.net_pnl) for x in eligible)
            net_r = tuple(self._decimal(x.net_r) for x in eligible)
            gross_pnl = tuple(self._decimal(x.gross_pnl) for x in eligible)
            gross_r = tuple(self._decimal(x.gross_r) for x in eligible)
        except ValueError:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "NON_FINITE_RETURN_INPUT", scope, as_of, history)
        n = len(eligible)
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            totals = tuple(sum(values, Decimal("0")) for values in (net_pnl, net_r, gross_pnl, gross_r))
            averages = tuple(total / Decimal(n) if n else None for total in totals)
        extrema = tuple((min(values), max(values)) if values else (None, None) for values in (net_pnl, net_r, gross_pnl, gross_r))
        source_ids = tuple(x.id for x in eligible)
        snapshot_id = self._uid("snapshot", scope.id, as_of, *source_ids)
        exact = next((x for x in history.snapshots if x.id == snapshot_id), None)
        if exact:
            return ReturnStatisticsResult(exact, None, history)
        if any((x.scope_id, x.as_of_time) == (scope.id, as_of) for x in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_RETURN_STATISTICS_SNAPSHOT", scope, as_of, history)
        snapshot = ReturnStatistics(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe,
            scope.setup_model, scope.direction, scope.input_version,
            scope.calculation_version, as_of, n, *totals, *averages,
            extrema[0][0], extrema[0][1], extrema[1][0], extrema[1][1],
            extrema[2][0], extrema[2][1], extrema[3][0], extrema[3][1],
            tuple(x.trade_id for x in eligible), source_ids, future,
            "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        updated = ReturnStatisticsHistory(history.snapshots + (snapshot,))
        return ReturnStatisticsResult(snapshot, None, updated)

    @staticmethod
    def _validate_trade(scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if trade.strategy_id != scope.strategy_id or trade.symbol != scope.symbol:
            return "RETURN_SCOPE_IDENTITY_MISMATCH"
        if trade.timeframe.lower() != scope.timeframe.lower():
            return "RETURN_TIMEFRAME_MISMATCH"
        if trade.model != scope.setup_model or trade.direction != scope.direction:
            return "RETURN_MODEL_OR_DIRECTION_MISMATCH"
        if trade.input_version != scope.input_version:
            return "RETURN_INPUT_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN):
            return "TRADE_RESULT_INVALID"
        return None
