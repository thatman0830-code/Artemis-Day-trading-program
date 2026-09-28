from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope


@dataclass(frozen=True)
class StreakSnapshot:
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
    maximum_winning_streak: int
    maximum_losing_streak: int
    maximum_winning_streak_trade_id_groups: tuple[tuple[str, ...], ...]
    maximum_losing_streak_trade_id_groups: tuple[tuple[str, ...], ...]
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    source_results: tuple[TradeResult, ...]
    future_excluded_trade_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class StreakError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class StreakHistory:
    snapshots: tuple[StreakSnapshot, ...] = ()


@dataclass(frozen=True)
class StreakResult:
    snapshot: StreakSnapshot | None
    error: StreakError | None
    history: StreakHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class StreakStatisticsEngine:
    """Canonical #29.7.2.8 maximum WIN/LOSS streak statistics."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.8:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _finite(value: object) -> bool:
        try:
            return Decimal(str(value)).is_finite()
        except (InvalidOperation, ValueError):
            return False

    def _invalid(self, code, reason, scope, as_of, history):
        scope_id = scope.id if scope else None
        error = StreakError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return StreakResult(None, error, history)

    def calculate(self, *, scope: TradeCountScope | None, trades: tuple[TradeAccounting, ...] | None, as_of_time: int, history: StreakHistory = StreakHistory()) -> StreakResult:
        as_of = int(as_of_time)
        if scope is None or trades is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_STREAK_INPUT_MISSING", scope, as_of, history)
        if not scope.immutable or as_of < 0 or not all(value.strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.calculation_version)):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "STREAK_SCOPE_INVALID", scope, as_of, history)
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
        win_groups = self._groups(eligible, TradeResult.WIN)
        loss_groups = self._groups(eligible, TradeResult.LOSS)
        max_wins = max(map(len, win_groups), default=0)
        max_losses = max(map(len, loss_groups), default=0)
        maximum_win_groups = tuple(group for group in win_groups if len(group) == max_wins) if max_wins else ()
        maximum_loss_groups = tuple(group for group in loss_groups if len(group) == max_losses) if max_losses else ()
        source_ids = tuple(trade.id for trade in eligible)
        snapshot_id = self._uid("snapshot", scope.id, as_of, *source_ids)
        exact = next((snapshot for snapshot in history.snapshots if snapshot.id == snapshot_id), None)
        if exact:
            return StreakResult(exact, None, history)
        if any((snapshot.scope_id, snapshot.as_of_time) == (scope.id, as_of) for snapshot in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_STREAK_SNAPSHOT", scope, as_of, history)
        snapshot = StreakSnapshot(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe,
            scope.setup_model, scope.direction, scope.input_version,
            scope.calculation_version, as_of, len(eligible), max_wins, max_losses,
            maximum_win_groups, maximum_loss_groups,
            tuple(trade.trade_id for trade in eligible), source_ids,
            tuple(trade.trade_result for trade in eligible), future,
        )
        return StreakResult(snapshot, None, StreakHistory(history.snapshots + (snapshot,)))

    @staticmethod
    def _groups(trades, result):
        groups = []
        current = []
        for trade in trades:
            if trade.trade_result == result:
                current.append(trade.trade_id)
            elif current:
                groups.append(tuple(current))
                current = []
        if current:
            groups.append(tuple(current))
        return tuple(groups)

    def _validate_trade(self, scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if trade.strategy_id != scope.strategy_id or trade.symbol != scope.symbol:
            return "STREAK_SCOPE_IDENTITY_MISMATCH"
        if trade.timeframe.lower() != scope.timeframe.lower():
            return "STREAK_TIMEFRAME_MISMATCH"
        if trade.model != scope.setup_model or trade.direction != scope.direction:
            return "STREAK_MODEL_OR_DIRECTION_MISMATCH"
        if trade.input_version != scope.input_version:
            return "STREAK_INPUT_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN):
            return "TRADE_RESULT_INVALID"
        if not self._finite(trade.net_pnl) or not self._finite(trade.net_r):
            return "NON_FINITE_ACCOUNTING_INPUT"
        return None
