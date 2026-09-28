from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope


@dataclass(frozen=True)
class CumulativePoint:
    id: str
    sequence: int
    trade_id: str
    accounting_id: str
    closed_time: int
    net_pnl: Decimal
    net_r: Decimal
    prior_cumulative_net_pnl: Decimal
    prior_cumulative_net_r: Decimal
    cumulative_net_pnl: Decimal
    cumulative_net_r: Decimal
    immutable: bool = True


@dataclass(frozen=True)
class CumulativeSnapshot:
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
    starting_cumulative_net_pnl: Decimal
    starting_cumulative_net_r: Decimal
    final_cumulative_net_pnl: Decimal
    final_cumulative_net_r: Decimal
    points: tuple[CumulativePoint, ...]
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class CumulativeError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class CumulativeHistory:
    snapshots: tuple[CumulativeSnapshot, ...] = ()


@dataclass(frozen=True)
class CumulativeResult:
    snapshot: CumulativeSnapshot | None
    error: CumulativeError | None
    history: CumulativeHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class CumulativePnLREngine:
    """Canonical #29.7.2.5 cumulative NetPnL and NetR trade series."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.5:" + kind + ":" + ":".join(map(str, parts))))

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
        error = CumulativeError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return CumulativeResult(None, error, history)

    def calculate(self, *, scope: TradeCountScope | None, trades: tuple[TradeAccounting, ...] | None, as_of_time: int, history: CumulativeHistory = CumulativeHistory()) -> CumulativeResult:
        as_of = int(as_of_time)
        if scope is None or trades is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_CUMULATIVE_INPUT_MISSING", scope, as_of, history)
        if not scope.immutable or as_of < 0 or not all(value.strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.calculation_version)):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "CUMULATIVE_SCOPE_INVALID", scope, as_of, history)
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
            values = tuple((trade, self._decimal(trade.net_pnl), self._decimal(trade.net_r)) for trade in eligible)
        except ValueError:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "NON_FINITE_CUMULATIVE_INPUT", scope, as_of, history)
        points = []
        cumulative_pnl = Decimal("0")
        cumulative_r = Decimal("0")
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            for sequence, (trade, net_pnl, net_r) in enumerate(values, start=1):
                prior_pnl, prior_r = cumulative_pnl, cumulative_r
                cumulative_pnl += net_pnl
                cumulative_r += net_r
                points.append(CumulativePoint(
                    self._uid("point", scope.id, as_of, sequence, trade.id), sequence,
                    trade.trade_id, trade.id, trade.closed_time, net_pnl, net_r,
                    prior_pnl, prior_r, cumulative_pnl, cumulative_r,
                ))
        source_ids = tuple(trade.id for trade in eligible)
        snapshot_id = self._uid("snapshot", scope.id, as_of, *source_ids)
        exact = next((snapshot for snapshot in history.snapshots if snapshot.id == snapshot_id), None)
        if exact:
            return CumulativeResult(exact, None, history)
        if any((snapshot.scope_id, snapshot.as_of_time) == (scope.id, as_of) for snapshot in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_CUMULATIVE_SNAPSHOT", scope, as_of, history)
        snapshot = CumulativeSnapshot(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe,
            scope.setup_model, scope.direction, scope.input_version, scope.calculation_version,
            as_of, len(eligible), Decimal("0"), Decimal("0"), cumulative_pnl,
            cumulative_r, tuple(points), tuple(trade.trade_id for trade in eligible),
            source_ids, future, "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return CumulativeResult(snapshot, None, CumulativeHistory(history.snapshots + (snapshot,)))

    @staticmethod
    def _validate_trade(scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if trade.strategy_id != scope.strategy_id or trade.symbol != scope.symbol:
            return "CUMULATIVE_SCOPE_IDENTITY_MISMATCH"
        if trade.timeframe.lower() != scope.timeframe.lower():
            return "CUMULATIVE_TIMEFRAME_MISMATCH"
        if trade.model != scope.setup_model or trade.direction != scope.direction:
            return "CUMULATIVE_MODEL_OR_DIRECTION_MISMATCH"
        if trade.input_version != scope.input_version:
            return "CUMULATIVE_INPUT_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN):
            return "TRADE_RESULT_INVALID"
        return None
