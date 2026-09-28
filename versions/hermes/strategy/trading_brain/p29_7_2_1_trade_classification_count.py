from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult


class AnalyticsErrorCode(str, Enum):
    DATA_INTEGRITY_ERROR = "DATA_INTEGRITY_ERROR"
    PERFORMANCE_DATA_INVALID = "PERFORMANCE_DATA_INVALID"


@dataclass(frozen=True)
class TradeCountScope:
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: SetupModel
    direction: StructuralRegime
    input_version: str
    calculation_version: str
    immutable: bool = True


@dataclass(frozen=True)
class TradeClassificationCount:
    id: str
    scope_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: SetupModel
    direction: StructuralRegime
    input_version: str
    calculation_version: str
    as_of_time: int
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class TradeCountError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class TradeCountHistory:
    snapshots: tuple[TradeClassificationCount, ...] = ()


@dataclass(frozen=True)
class TradeCountResult:
    snapshot: TradeClassificationCount | None
    error: TradeCountError | None
    history: TradeCountHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class TradeClassificationCountEngine:
    """Canonical #29.7.2.1 read-only classification consumption and count."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.1:" + kind + ":" + ":".join(map(str, parts))))

    def _invalid(self, code, reason, scope, as_of, history):
        scope_id = scope.id if scope else None
        error = TradeCountError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return TradeCountResult(None, error, history)

    def calculate(
        self, *, scope: TradeCountScope | None,
        trades: tuple[TradeAccounting, ...] | None,
        as_of_time: int,
        history: TradeCountHistory = TradeCountHistory(),
    ) -> TradeCountResult:
        as_of = int(as_of_time)
        if scope is None or trades is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_ANALYTICS_INPUT_MISSING", scope, as_of, history)
        reason = self._validate_scope(scope, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        trade_ids = [trade.trade_id for trade in trades]
        accounting_ids = [trade.id for trade in trades]
        if len(trade_ids) != len(set(trade_ids)) or len(accounting_ids) != len(set(accounting_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CANONICAL_TRADE_KEY", scope, as_of, history)
        for trade in trades:
            reason = self._validate_trade(scope, trade)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        eligible = tuple(sorted(
            (trade for trade in trades if trade.closed_time <= as_of),
            key=lambda trade: (trade.closed_time, trade.trade_id),
        ))
        future = tuple(sorted(trade.trade_id for trade in trades if trade.closed_time > as_of))
        wins = sum(trade.trade_result == TradeResult.WIN for trade in eligible)
        losses = sum(trade.trade_result == TradeResult.LOSS for trade in eligible)
        breakevens = sum(trade.trade_result == TradeResult.BREAKEVEN for trade in eligible)
        count = len(eligible)
        if count != wins + losses + breakevens:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "TRADE_CLASSIFICATION_COUNT_INVARIANT_FAILED", scope, as_of, history)
        source_trade_ids = tuple(trade.trade_id for trade in eligible)
        source_accounting_ids = tuple(trade.id for trade in eligible)
        snapshot_id = self._uid("snapshot", scope.id, as_of, *source_accounting_ids)
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return TradeCountResult(exact, None, history)
        canonical_key = (scope.id, as_of)
        if any((item.scope_id, item.as_of_time) == canonical_key for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_ANALYTICS_SNAPSHOT", scope, as_of, history)
        snapshot = TradeClassificationCount(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol,
            scope.timeframe, scope.setup_model, scope.direction,
            scope.input_version, scope.calculation_version, as_of,
            count, wins, losses, breakevens, source_trade_ids,
            source_accounting_ids, future,
        )
        updated = TradeCountHistory(history.snapshots + (snapshot,))
        return TradeCountResult(snapshot, None, updated)

    @staticmethod
    def _validate_scope(scope, as_of):
        if not all(value.strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.calculation_version)):
            return "ANALYTICS_SCOPE_IDENTITY_MISSING"
        if not scope.immutable or as_of < 0:
            return "ANALYTICS_SCOPE_INVALID"
        if scope.direction not in (StructuralRegime.BULLISH, StructuralRegime.BEARISH):
            return "ANALYTICS_SCOPE_DIRECTION_INVALID"
        return None

    @staticmethod
    def _validate_trade(scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if trade.strategy_id != scope.strategy_id or trade.symbol != scope.symbol:
            return "ANALYTICS_SCOPE_IDENTITY_MISMATCH"
        if trade.timeframe.lower() != scope.timeframe.lower():
            return "ANALYTICS_TIMEFRAME_MISMATCH"
        if trade.model != scope.setup_model or trade.direction != scope.direction:
            return "ANALYTICS_MODEL_OR_DIRECTION_MISMATCH"
        if trade.input_version != scope.input_version:
            return "ANALYTICS_INPUT_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN):
            return "TRADE_RESULT_INVALID"
        return None
