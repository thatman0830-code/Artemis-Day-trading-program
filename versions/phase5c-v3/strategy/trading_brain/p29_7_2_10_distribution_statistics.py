from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode


@dataclass(frozen=True)
class DistributionScope:
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    input_version: str
    source_version: str
    calculation_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class DistributionObservation:
    sequence: int
    trade_id: str
    accounting_id: str
    closed_time: int
    trade_result: TradeResult
    net_pnl: Decimal
    net_r: Decimal
    immutable: bool = True


@dataclass(frozen=True)
class DistributionSnapshot:
    id: str
    scope_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    input_version: str
    source_version: str
    calculation_version: str
    historical_version: str
    as_of_time: int
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    observations: tuple[DistributionObservation, ...]
    net_pnl_distribution: tuple[Decimal, ...]
    net_r_distribution: tuple[Decimal, ...]
    winning_net_pnl_distribution: tuple[Decimal, ...]
    winning_net_r_distribution: tuple[Decimal, ...]
    losing_net_pnl_distribution: tuple[Decimal, ...]
    losing_net_r_distribution: tuple[Decimal, ...]
    breakeven_net_pnl_distribution: tuple[Decimal, ...]
    breakeven_net_r_distribution: tuple[Decimal, ...]
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class DistributionError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class DistributionHistory:
    snapshots: tuple[DistributionSnapshot, ...] = ()


@dataclass(frozen=True)
class DistributionResult:
    snapshot: DistributionSnapshot | None
    error: DistributionError | None
    history: DistributionHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class DistributionStatisticsEngine:
    """Canonical #29.7.2.10 raw finalized-trade distribution facts."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.10:" + kind + ":" + ":".join(map(str, parts))))

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
        error = DistributionError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return DistributionResult(None, error, history)

    def calculate(self, *, scope: DistributionScope | None, trades: tuple[TradeAccounting, ...] | None, as_of_time: int, history: DistributionHistory = DistributionHistory()) -> DistributionResult:
        as_of = int(as_of_time)
        if scope is None or trades is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_DISTRIBUTION_INPUT_MISSING", scope, as_of, history)
        if not scope.immutable or as_of < 0 or not all(value.strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.source_version, scope.calculation_version, scope.historical_version)):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "DISTRIBUTION_SCOPE_INVALID", scope, as_of, history)
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
        observations = []
        try:
            for sequence, trade in enumerate(eligible, start=1):
                observations.append(DistributionObservation(sequence, trade.trade_id, trade.id, trade.closed_time, trade.trade_result, self._decimal(trade.net_pnl), self._decimal(trade.net_r)))
        except ValueError:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "NON_FINITE_DISTRIBUTION_INPUT", scope, as_of, history)
        observations = tuple(observations)
        wins = tuple(item for item in observations if item.trade_result == TradeResult.WIN)
        losses = tuple(item for item in observations if item.trade_result == TradeResult.LOSS)
        breakevens = tuple(item for item in observations if item.trade_result == TradeResult.BREAKEVEN)
        sorted_values = lambda rows, field: tuple(sorted(getattr(row, field) for row in rows))
        distributions = (
            sorted_values(observations, "net_pnl"), sorted_values(observations, "net_r"),
            sorted_values(wins, "net_pnl"), sorted_values(wins, "net_r"),
            sorted_values(losses, "net_pnl"), sorted_values(losses, "net_r"),
            sorted_values(breakevens, "net_pnl"), sorted_values(breakevens, "net_r"),
        )
        source_ids = tuple(trade.id for trade in eligible)
        snapshot_id = self._uid("snapshot", scope.id, scope.source_version, scope.historical_version, scope.calculation_version, as_of, *source_ids)
        exact = next((snapshot for snapshot in history.snapshots if snapshot.id == snapshot_id), None)
        if exact:
            return DistributionResult(exact, None, history)
        if any((snapshot.scope_id, snapshot.as_of_time, snapshot.source_version, snapshot.historical_version, snapshot.calculation_version) == (scope.id, as_of, scope.source_version, scope.historical_version, scope.calculation_version) for snapshot in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_DISTRIBUTION_SNAPSHOT", scope, as_of, history)
        snapshot = DistributionSnapshot(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe,
            scope.setup_model, scope.direction, scope.input_version,
            scope.source_version, scope.calculation_version, scope.historical_version,
            as_of, len(observations), len(wins), len(losses), len(breakevens),
            observations, *distributions, tuple(trade.trade_id for trade in eligible),
            source_ids, future,
        )
        return DistributionResult(snapshot, None, DistributionHistory(history.snapshots + (snapshot,)))

    def _validate_trade(self, scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if trade.strategy_id != scope.strategy_id or trade.symbol != scope.symbol:
            return "DISTRIBUTION_SCOPE_IDENTITY_MISMATCH"
        if trade.timeframe.lower() != scope.timeframe.lower():
            return "DISTRIBUTION_TIMEFRAME_MISMATCH"
        if trade.model != scope.setup_model or trade.direction != scope.direction:
            return "DISTRIBUTION_MODEL_OR_DIRECTION_MISMATCH"
        if trade.input_version != scope.input_version:
            return "DISTRIBUTION_INPUT_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN):
            return "TRADE_RESULT_INVALID"
        try:
            self._decimal(trade.net_pnl)
            self._decimal(trade.net_r)
        except ValueError:
            return "NON_FINITE_DISTRIBUTION_INPUT"
        return None
