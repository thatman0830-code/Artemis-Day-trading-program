from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope


class PeriodType(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    FULL_HISTORY = "FULL_HISTORY"


@dataclass(frozen=True)
class PeriodDefinition:
    period_type: PeriodType
    account_timezone: str
    period_start: int
    period_end: int
    source_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class PeriodStatisticsSnapshot:
    id: str
    period_id: str
    scope_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    input_version: str
    calculation_version: str
    source_version: str
    historical_version: str
    period_type: PeriodType
    account_timezone: str
    period_start: int
    period_end: int
    finalized_time: int
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    total_net_pnl: Decimal
    total_net_r: Decimal
    win_rate: Decimal | None
    average_net_pnl: Decimal | None
    average_net_r: Decimal | None
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    excluded_other_period_trade_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class PeriodStatisticsError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    finalized_time: int
    immutable: bool = True


@dataclass(frozen=True)
class PeriodStatisticsHistory:
    snapshots: tuple[PeriodStatisticsSnapshot, ...] = ()


@dataclass(frozen=True)
class PeriodStatisticsResult:
    snapshot: PeriodStatisticsSnapshot | None
    error: PeriodStatisticsError | None
    history: PeriodStatisticsHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class PeriodStatisticsEngine:
    """Canonical #29.7.2.9 finalized period aggregation in AccountTimezone."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.9:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, scope, now, history):
        scope_id = scope.id if scope else None
        error = PeriodStatisticsError(self._uid("error", scope_id or "NONE", code.value, reason, now), code, reason, scope_id, int(now))
        return PeriodStatisticsResult(None, error, history)

    def calculate(self, *, scope: TradeCountScope | None, period: PeriodDefinition | None, trades: tuple[TradeAccounting, ...] | None, as_of_time: int, history: PeriodStatisticsHistory = PeriodStatisticsHistory()) -> PeriodStatisticsResult:
        now = int(as_of_time)
        if scope is None or period is None or trades is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_PERIOD_INPUT_MISSING", scope, now, history)
        if not scope.immutable or now < 0 or not all(value.strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.calculation_version)):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "PERIOD_SCOPE_INVALID", scope, now, history)
        reason = self._validate_period(period, now)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, now, history)
        trade_ids = [trade.trade_id for trade in trades]
        record_ids = [trade.id for trade in trades]
        if len(trade_ids) != len(set(trade_ids)) or len(record_ids) != len(set(record_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CANONICAL_TRADE_KEY", scope, now, history)
        for trade in trades:
            reason = self._validate_trade(scope, trade)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, now, history)
        eligible = tuple(sorted((trade for trade in trades if period.period_start <= trade.closed_time < period.period_end), key=lambda trade: (trade.closed_time, trade.trade_id)))
        future = tuple(sorted(trade.trade_id for trade in trades if trade.closed_time > now))
        other = tuple(sorted(trade.trade_id for trade in trades if trade.closed_time <= now and not (period.period_start <= trade.closed_time < period.period_end)))
        try:
            pnl = tuple(self._decimal(trade.net_pnl) for trade in eligible)
            net_r = tuple(self._decimal(trade.net_r) for trade in eligible)
        except ValueError:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "NON_FINITE_PERIOD_INPUT", scope, now, history)
        count = len(eligible)
        wins = sum(trade.trade_result == TradeResult.WIN for trade in eligible)
        losses = sum(trade.trade_result == TradeResult.LOSS for trade in eligible)
        breakevens = sum(trade.trade_result == TradeResult.BREAKEVEN for trade in eligible)
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            total_pnl = sum(pnl, Decimal("0"))
            total_r = sum(net_r, Decimal("0"))
            win_rate = Decimal(wins) / Decimal(count) if count else None
            average_pnl = total_pnl / Decimal(count) if count else None
            average_r = total_r / Decimal(count) if count else None
        period_id = self._uid("period", scope.id, period.period_type.value, period.account_timezone, period.period_start, period.period_end, period.source_version, period.historical_version, scope.calculation_version)
        source_ids = tuple(trade.id for trade in eligible)
        snapshot_id = self._uid("snapshot", period_id, now, *source_ids)
        exact = next((snapshot for snapshot in history.snapshots if snapshot.id == snapshot_id), None)
        if exact:
            return PeriodStatisticsResult(exact, None, history)
        if any(snapshot.period_id == period_id for snapshot in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_PERIOD_SNAPSHOT", scope, now, history)
        snapshot = PeriodStatisticsSnapshot(
            snapshot_id, period_id, scope.id, scope.strategy_id, scope.symbol,
            scope.timeframe, scope.setup_model, scope.direction, scope.input_version,
            scope.calculation_version, period.source_version, period.historical_version,
            period.period_type, period.account_timezone, period.period_start,
            period.period_end, now, count, wins, losses, breakevens, total_pnl,
            total_r, win_rate, average_pnl, average_r,
            tuple(trade.trade_id for trade in eligible), source_ids, other, future,
            "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return PeriodStatisticsResult(snapshot, None, PeriodStatisticsHistory(history.snapshots + (snapshot,)))

    @staticmethod
    def _validate_period(period, now):
        if not period.immutable or not period.account_timezone.strip() or not period.source_version.strip() or not period.historical_version.strip():
            return "PERIOD_DEFINITION_INVALID"
        if period.period_type not in tuple(PeriodType):
            return "PERIOD_TYPE_INVALID"
        if period.period_start < 0 or period.period_end <= period.period_start:
            return "PERIOD_BOUNDARY_INVALID"
        if period.period_end > now:
            return "PERIOD_NOT_FINAL"
        try:
            timezone = ZoneInfo(period.account_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            return "ACCOUNT_TIMEZONE_INVALID"
        if period.period_type == PeriodType.FULL_HISTORY:
            return None
        start = datetime.fromtimestamp(period.period_start, timezone)
        end = datetime.fromtimestamp(period.period_end, timezone)
        if any((start.hour, start.minute, start.second, start.microsecond, end.hour, end.minute, end.second, end.microsecond)):
            return "PERIOD_BOUNDARY_INVALID"
        if period.period_type == PeriodType.DAILY:
            expected_end = start + timedelta(days=1)
        elif period.period_type == PeriodType.WEEKLY:
            if start.weekday() != 0:
                return "PERIOD_BOUNDARY_INVALID"
            expected_end = start + timedelta(days=7)
        else:
            expected_end = start.replace(year=start.year + (start.month == 12), month=1 if start.month == 12 else start.month + 1)
        if int(expected_end.timestamp()) != period.period_end:
            return "PERIOD_BOUNDARY_INVALID"
        return None

    def _validate_trade(self, scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if trade.strategy_id != scope.strategy_id or trade.symbol != scope.symbol:
            return "PERIOD_SCOPE_IDENTITY_MISMATCH"
        if trade.timeframe.lower() != scope.timeframe.lower():
            return "PERIOD_TIMEFRAME_MISMATCH"
        if trade.model != scope.setup_model or trade.direction != scope.direction:
            return "PERIOD_MODEL_OR_DIRECTION_MISMATCH"
        if trade.input_version != scope.input_version:
            return "PERIOD_INPUT_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN):
            return "TRADE_RESULT_INVALID"
        try:
            self._decimal(trade.net_pnl)
            self._decimal(trade.net_r)
        except ValueError:
            return "NON_FINITE_PERIOD_INPUT"
        return None
