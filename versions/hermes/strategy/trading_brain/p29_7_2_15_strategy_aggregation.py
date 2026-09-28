from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodStatisticsSnapshot, PeriodType


@dataclass(frozen=True)
class StrategyAggregationScope:
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
    period_type: PeriodType
    account_timezone: str
    immutable: bool = True


@dataclass(frozen=True)
class StrategyStartingEquity:
    id: str
    strategy_id: str
    equity: Decimal
    source_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class StrategyEquityPoint:
    id: str
    sequence: int
    trade_id: str
    accounting_id: str
    closed_time: int
    net_pnl: Decimal
    prior_equity: Decimal
    equity: Decimal
    immutable: bool = True


@dataclass(frozen=True)
class StrategyPeriodReturnObservation:
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    period_type: PeriodType
    period_id: str
    period_start: int
    period_end: int
    account_timezone: str
    net_pnl: Decimal
    net_r: Decimal
    trade_count: int
    finalized: bool
    finalized_time: int
    source_version: str
    calculation_version: str
    historical_version: str
    source_period_snapshot_id: str
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class StrategyPerformance:
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
    period_type: PeriodType
    account_timezone: str
    as_of_time: int
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    strategy_gross_pnl: Decimal
    strategy_net_pnl: Decimal
    strategy_gross_r: Decimal
    strategy_net_r: Decimal
    win_rate: Decimal | None
    expectancy_net_pnl: Decimal | None
    expectancy_net_r: Decimal | None
    total_winning_net_pnl: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    starting_equity: Decimal
    ending_equity: Decimal
    equity_points: tuple[StrategyEquityPoint, ...]
    period_observations: tuple[StrategyPeriodReturnObservation, ...]
    period_count: int
    zero_trade_period_ids: tuple[str, ...]
    period_gap_pairs: tuple[tuple[str, str], ...]
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    source_period_snapshot_ids: tuple[str, ...]
    future_excluded_trade_ids: tuple[str, ...]
    future_excluded_period_ids: tuple[str, ...]
    starting_equity_fact_id: str
    calculation_timestamp: int
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class StrategyAggregationError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class StrategyAggregationHistory:
    snapshots: tuple[StrategyPerformance, ...] = ()


@dataclass(frozen=True)
class StrategyAggregationResult:
    snapshot: StrategyPerformance | None
    error: StrategyAggregationError | None
    history: StrategyAggregationHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class StrategyAggregationEngine:
    """Canonical #29.7.2.15 strategy-level accounting and period aggregation."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.15:" + kind + ":" + ":".join(map(str, parts))))

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
        error = StrategyAggregationError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return StrategyAggregationResult(None, error, history)

    def calculate(
        self, *, scope: StrategyAggregationScope | None,
        trades: tuple[TradeAccounting, ...] | None,
        periods: tuple[PeriodStatisticsSnapshot, ...] | None,
        starting_equity: StrategyStartingEquity | None,
        as_of_time: int,
        history: StrategyAggregationHistory = StrategyAggregationHistory(),
    ) -> StrategyAggregationResult:
        as_of = int(as_of_time)
        if scope is None or trades is None or periods is None or starting_equity is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_STRATEGY_AGGREGATION_INPUT_MISSING", scope, as_of, history)
        reason = self._validate_scope_and_equity(scope, starting_equity, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        trade_ids = [trade.trade_id for trade in trades]
        accounting_ids = [trade.id for trade in trades]
        period_ids = [period.period_id for period in periods]
        period_snapshot_ids = [period.id for period in periods]
        period_ends = [period.period_end for period in periods]
        if len(trade_ids) != len(set(trade_ids)) or len(accounting_ids) != len(set(accounting_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CANONICAL_TRADE_KEY", scope, as_of, history)
        if len(period_ids) != len(set(period_ids)) or len(period_snapshot_ids) != len(set(period_snapshot_ids)) or len(period_ends) != len(set(period_ends)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CANONICAL_PERIOD_KEY", scope, as_of, history)
        for trade in trades:
            reason = self._validate_trade(scope, trade)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        if tuple(sorted(periods, key=lambda period: (period.period_start, period.period_id))) != periods:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "STRATEGY_PERIOD_ORDER_INVALID", scope, as_of, history)
        for period in periods:
            reason = self._validate_period(scope, period)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)

        eligible = tuple(sorted((trade for trade in trades if trade.closed_time <= as_of), key=lambda trade: (trade.closed_time, trade.trade_id)))
        future_trades = tuple(sorted(trade.trade_id for trade in trades if trade.closed_time > as_of))
        eligible_periods = tuple(period for period in periods if period.period_end <= as_of)
        future_periods = tuple(period.period_id for period in periods if period.period_end > as_of)
        for period in eligible_periods:
            if period.finalized_time > as_of:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "STRATEGY_PERIOD_NOT_FINAL_AT_AS_OF", scope, as_of, history)
            reason = self._validate_period_population(period, trades)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)

        try:
            values = tuple((trade, self._decimal(trade.gross_pnl), self._decimal(trade.net_pnl), self._decimal(trade.gross_r), self._decimal(trade.net_r)) for trade in eligible)
            initial_equity = self._decimal(starting_equity.equity)
        except ValueError:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "NON_FINITE_STRATEGY_AGGREGATION_INPUT", scope, as_of, history)
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            context.rounding = ROUND_HALF_UP
            gross_pnl = sum((item[1] for item in values), Decimal(0))
            net_pnl = sum((item[2] for item in values), Decimal(0))
            gross_r = sum((item[3] for item in values), Decimal(0))
            net_r = sum((item[4] for item in values), Decimal(0))
            count = len(values)
            wins = sum(trade.trade_result == TradeResult.WIN for trade in eligible)
            losses = sum(trade.trade_result == TradeResult.LOSS for trade in eligible)
            breakevens = sum(trade.trade_result == TradeResult.BREAKEVEN for trade in eligible)
            win_rate = Decimal(wins) / Decimal(count) if count else None
            expectancy_pnl = net_pnl / Decimal(count) if count else None
            expectancy_r = net_r / Decimal(count) if count else None
            winning_pnl = sum((item[2] for item in values if item[2] > 0), Decimal(0))
            losing_pnl = abs(sum((item[2] for item in values if item[2] < 0), Decimal(0)))
            profit_factor = winning_pnl / losing_pnl if losing_pnl > 0 else Decimal("Infinity") if winning_pnl > 0 else None
            equity_points = []
            equity = initial_equity
            for sequence, (trade, _gross_pnl, trade_net_pnl, _gross_r, _net_r) in enumerate(values, start=1):
                prior = equity
                equity += trade_net_pnl
                equity_points.append(StrategyEquityPoint(
                    self._uid("equity-point", scope.id, starting_equity.id, trade.id), sequence,
                    trade.trade_id, trade.id, trade.closed_time, trade_net_pnl, prior, equity,
                ))
            observations = tuple(self._period_observation(scope, period) for period in eligible_periods)

        gaps = tuple((left.period_id, right.period_id) for left, right in zip(eligible_periods, eligible_periods[1:]) if left.period_end < right.period_start)
        if any(left.period_end > right.period_start for left, right in zip(eligible_periods, eligible_periods[1:])):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "STRATEGY_PERIOD_OVERLAP_INVALID", scope, as_of, history)
        source_ids = tuple(trade.id for trade in eligible)
        snapshot_id = self._uid(
            "snapshot", scope.id, scope.source_version, scope.historical_version, scope.calculation_version,
            scope.period_type.value, as_of, starting_equity.id, starting_equity.equity,
            *((trade.id, trade.trade_result.value, trade.gross_pnl, trade.net_pnl, trade.gross_r, trade.net_r) for trade in eligible),
            *((period.id, period.total_net_pnl, period.total_net_r, period.trade_count) for period in eligible_periods),
        )
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return StrategyAggregationResult(exact, None, history)
        if any((item.scope_id, item.as_of_time, item.period_type, item.source_version, item.historical_version, item.calculation_version) == (scope.id, as_of, scope.period_type, scope.source_version, scope.historical_version, scope.calculation_version) for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_STRATEGY_AGGREGATION_SNAPSHOT", scope, as_of, history)
        snapshot = StrategyPerformance(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.setup_model,
            scope.direction, scope.input_version, scope.source_version, scope.calculation_version,
            scope.historical_version, scope.period_type, scope.account_timezone, as_of, count, wins, losses,
            breakevens, gross_pnl, net_pnl, gross_r, net_r, win_rate, expectancy_pnl, expectancy_r,
            winning_pnl, losing_pnl, profit_factor, initial_equity, equity, tuple(equity_points), observations,
            len(observations), tuple(item.period_id for item in observations if item.trade_count == 0), gaps,
            tuple(trade.trade_id for trade in eligible), source_ids, tuple(period.id for period in eligible_periods),
            future_trades, future_periods, starting_equity.id, as_of,
            "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return StrategyAggregationResult(snapshot, None, StrategyAggregationHistory(history.snapshots + (snapshot,)))

    def _period_observation(self, scope, period):
        return StrategyPeriodReturnObservation(
            self._uid("period-return", scope.id, period.id), scope.strategy_id, scope.symbol,
            scope.timeframe, scope.setup_model, scope.direction, period.period_type, period.period_id,
            period.period_start, period.period_end, period.account_timezone, self._decimal(period.total_net_pnl),
            self._decimal(period.total_net_r), period.trade_count, True, period.finalized_time,
            period.source_version, period.calculation_version, period.historical_version, period.id,
            period.source_trade_ids, period.source_accounting_ids,
        )

    def _validate_scope_and_equity(self, scope, starting, as_of):
        if not scope.immutable or as_of < 0 or scope.period_type not in tuple(PeriodType) or not all(str(value).strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.source_version, scope.calculation_version, scope.historical_version, scope.account_timezone)):
            return "STRATEGY_AGGREGATION_SCOPE_INVALID"
        if not starting.immutable or not all(str(value).strip() for value in (starting.id, starting.strategy_id, starting.source_version, starting.historical_version)):
            return "STRATEGY_STARTING_EQUITY_FACT_INVALID"
        if (starting.strategy_id, starting.source_version, starting.historical_version) != (scope.strategy_id, scope.source_version, scope.historical_version):
            return "STRATEGY_STARTING_EQUITY_VERSION_MISMATCH"
        try:
            self._decimal(starting.equity)
        except ValueError:
            return "NON_FINITE_STRATEGY_STARTING_EQUITY"
        return None

    def _validate_trade(self, scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if not all((trade.id, trade.trade_id, trade.position_id, trade.setup_id)):
            return "ACCOUNTING_IDENTITY_MISSING"
        if (trade.strategy_id, trade.symbol, trade.timeframe.lower(), trade.model, trade.direction, trade.input_version) != (scope.strategy_id, scope.symbol, scope.timeframe.lower(), scope.setup_model, scope.direction, scope.input_version):
            return "STRATEGY_ACCOUNTING_SCOPE_OR_VERSION_MISMATCH"
        if trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
        if trade.trade_result not in (TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN):
            return "TRADE_RESULT_INVALID"
        try:
            for value in (trade.gross_pnl, trade.net_pnl, trade.gross_r, trade.net_r):
                self._decimal(value)
        except ValueError:
            return "NON_FINITE_STRATEGY_AGGREGATION_INPUT"
        return None

    def _validate_period(self, scope, period):
        if not period.immutable or period.period_start >= period.period_end or period.finalized_time < period.period_end:
            return "STRATEGY_PERIOD_INVALID_OR_NON_FINAL"
        if (period.scope_id, period.strategy_id, period.symbol, period.timeframe.lower(), period.setup_model, period.direction, period.input_version) != (scope.id, scope.strategy_id, scope.symbol, scope.timeframe.lower(), scope.setup_model, scope.direction, scope.input_version):
            return "STRATEGY_PERIOD_SCOPE_MISMATCH"
        if (period.period_type, period.account_timezone, period.source_version, period.calculation_version, period.historical_version) != (scope.period_type, scope.account_timezone, scope.source_version, scope.calculation_version, scope.historical_version):
            return "STRATEGY_PERIOD_TYPE_OR_VERSION_MISMATCH"
        if len(period.source_trade_ids) != len(set(period.source_trade_ids)) or len(period.source_accounting_ids) != len(set(period.source_accounting_ids)):
            return "DUPLICATE_PERIOD_SOURCE_KEY"
        try:
            for value in (period.total_net_pnl, period.total_net_r):
                self._decimal(value)
        except ValueError:
            return "NON_FINITE_STRATEGY_PERIOD_INPUT"
        if period.trade_count != period.win_count + period.loss_count + period.breakeven_count:
            return "STRATEGY_PERIOD_COUNT_CONSERVATION_INVALID"
        return None

    def _validate_period_population(self, period, trades):
        population = tuple(sorted((trade for trade in trades if period.period_start <= trade.closed_time < period.period_end), key=lambda trade: (trade.closed_time, trade.trade_id)))
        if period.source_trade_ids != tuple(trade.trade_id for trade in population) or period.source_accounting_ids != tuple(trade.id for trade in population) or period.trade_count != len(population):
            return "STRATEGY_PERIOD_POPULATION_MISMATCH"
        try:
            if self._decimal(period.total_net_pnl) != sum((self._decimal(trade.net_pnl) for trade in population), Decimal(0)) or self._decimal(period.total_net_r) != sum((self._decimal(trade.net_r) for trade in population), Decimal(0)):
                return "STRATEGY_PERIOD_TOTAL_MISMATCH"
        except ValueError:
            return "NON_FINITE_STRATEGY_PERIOD_INPUT"
        counts = (
            sum(trade.trade_result == TradeResult.WIN for trade in population),
            sum(trade.trade_result == TradeResult.LOSS for trade in population),
            sum(trade.trade_result == TradeResult.BREAKEVEN for trade in population),
        )
        if counts != (period.win_count, period.loss_count, period.breakeven_count):
            return "STRATEGY_PERIOD_CLASSIFICATION_MISMATCH"
        return None
