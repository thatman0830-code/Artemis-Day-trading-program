from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodType
from strategy.trading_brain.p29_7_2_15_strategy_aggregation import StrategyPerformance


class PortfolioAggregationErrorCode(str, Enum):
    PORTFOLIO_STARTING_EQUITY_MISSING = "PORTFOLIO_STARTING_EQUITY_MISSING"


@dataclass(frozen=True)
class PortfolioDefinition:
    portfolio_id: str
    portfolio_version: str
    included_strategy_ids: tuple[str, ...]
    excluded_strategy_ids: tuple[str, ...]
    creation_time: int
    period_type: PeriodType
    account_timezone: str
    source_version: str
    strategy_calculation_version: str
    calculation_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class PortfolioStartingEquity:
    id: str
    portfolio_id: str
    portfolio_version: str
    equity: Decimal
    source_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class PortfolioEquityPoint:
    id: str
    sequence: int
    strategy_id: str
    trade_id: str
    accounting_id: str
    closed_time: int
    net_pnl: Decimal
    prior_equity: Decimal
    equity: Decimal
    peak_equity: Decimal
    drawdown_abs: Decimal
    drawdown_pct: Decimal | None
    source_strategy_snapshot_id: str
    source_strategy_equity_point_id: str
    immutable: bool = True


@dataclass(frozen=True)
class StrategyContribution:
    id: str
    strategy_id: str
    strategy_snapshot_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    gross_pnl: Decimal
    net_pnl: Decimal
    gross_r: Decimal
    net_r: Decimal
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class PortfolioPeriodObservation:
    id: str
    portfolio_id: str
    portfolio_version: str
    period_type: PeriodType
    period_start: int
    period_end: int
    account_timezone: str
    trade_count: int
    net_pnl: Decimal
    net_r: Decimal
    contributing_strategy_ids: tuple[str, ...]
    source_strategy_period_observation_ids: tuple[str, ...]
    source_period_ids: tuple[str, ...]
    finalized_time: int
    source_version: str
    calculation_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class PortfolioPerformance:
    id: str
    portfolio_id: str
    portfolio_version: str
    effective_strategy_ids: tuple[str, ...]
    included_strategy_ids: tuple[str, ...]
    excluded_strategy_ids: tuple[str, ...]
    period_type: PeriodType
    account_timezone: str
    source_version: str
    strategy_calculation_version: str
    calculation_version: str
    historical_version: str
    as_of_time: int
    population_start_time: int | None
    population_end_time: int | None
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    portfolio_gross_pnl: Decimal
    portfolio_net_pnl: Decimal
    portfolio_gross_r: Decimal
    portfolio_net_r: Decimal
    average_gross_pnl: Decimal | None
    average_net_pnl: Decimal | None
    average_gross_r: Decimal | None
    average_net_r: Decimal | None
    win_rate: Decimal | None
    expectancy_net_pnl: Decimal | None
    expectancy_net_r: Decimal | None
    total_winning_net_pnl: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    starting_equity: Decimal
    ending_equity: Decimal
    maximum_drawdown_abs: Decimal
    maximum_drawdown_pct: Decimal | None
    maximum_drawdown_equity_point_ids: tuple[str, ...]
    equity_points: tuple[PortfolioEquityPoint, ...]
    strategy_contributions: tuple[StrategyContribution, ...]
    period_observations: tuple[PortfolioPeriodObservation, ...]
    aligned_period_count: int
    zero_return_period_ids: tuple[str, ...]
    missing_period_ends: tuple[int, ...]
    period_gap_pairs: tuple[tuple[int, int], ...]
    source_strategy_snapshot_ids: tuple[str, ...]
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    starting_equity_fact_id: str
    calculation_timestamp: int
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class PortfolioAggregationError:
    id: str
    code: object
    reason: str
    portfolio_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class PortfolioAggregationHistory:
    snapshots: tuple[PortfolioPerformance, ...] = ()


@dataclass(frozen=True)
class PortfolioAggregationResult:
    snapshot: PortfolioPerformance | None
    error: PortfolioAggregationError | None
    history: PortfolioAggregationHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class PortfolioAggregationEngine:
    """Canonical #29.7.2.16 read-only aggregation of #29.7.2.15 populations."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.16:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, definition, as_of, history):
        portfolio_id = definition.portfolio_id if definition else None
        code_value = code.value if hasattr(code, "value") else str(code)
        error = PortfolioAggregationError(self._uid("error", portfolio_id or "NONE", code_value, reason, as_of), code, reason, portfolio_id, int(as_of))
        return PortfolioAggregationResult(None, error, history)

    def calculate(
        self, *, definition: PortfolioDefinition | None,
        strategies: tuple[StrategyPerformance, ...] | None,
        starting_equity: PortfolioStartingEquity | None,
        as_of_time: int,
        history: PortfolioAggregationHistory = PortfolioAggregationHistory(),
    ) -> PortfolioAggregationResult:
        as_of = int(as_of_time)
        if definition is None or strategies is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_PORTFOLIO_AGGREGATION_INPUT_MISSING", definition, as_of, history)
        if starting_equity is None:
            return self._invalid(PortfolioAggregationErrorCode.PORTFOLIO_STARTING_EQUITY_MISSING, "PORTFOLIO_STARTING_EQUITY_MISSING", definition, as_of, history)
        reason = self._validate_definition(definition, starting_equity, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, definition, as_of, history)
        strategy_ids = [item.strategy_id for item in strategies]
        snapshot_ids = [item.id for item in strategies]
        if len(strategy_ids) != len(set(strategy_ids)) or len(snapshot_ids) != len(set(snapshot_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_STRATEGY_POPULATION", definition, as_of, history)
        included = tuple(strategy_id for strategy_id in definition.included_strategy_ids if strategy_id not in set(definition.excluded_strategy_ids))
        supplied_ids = set(strategy_ids)
        if any(strategy_id not in supplied_ids for strategy_id in included):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "INCLUDED_STRATEGY_POPULATION_MISSING", definition, as_of, history)
        if any(strategy_id not in set(definition.included_strategy_ids) | set(definition.excluded_strategy_ids) for strategy_id in strategy_ids):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "UNDECLARED_STRATEGY_POPULATION", definition, as_of, history)
        for strategy in strategies:
            reason = self._validate_strategy(definition, strategy, as_of)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, definition, as_of, history)
        by_id = {item.strategy_id: item for item in strategies}
        effective = tuple(by_id[strategy_id] for strategy_id in included)
        all_trade_ids = tuple(trade_id for item in effective for trade_id in item.source_trade_ids)
        all_accounting_ids = tuple(accounting_id for item in effective for accounting_id in item.source_accounting_ids)
        if len(all_trade_ids) != len(set(all_trade_ids)) or len(all_accounting_ids) != len(set(all_accounting_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_PORTFOLIO_TRADE_KEY", definition, as_of, history)

        contributions = tuple(self._contribution(definition, item) for item in effective)
        try:
            initial = self._decimal(starting_equity.equity)
            with localcontext() as context:
                context.prec = max(context.prec, 28)
                context.rounding = ROUND_HALF_UP
                count = sum(item.trade_count for item in effective)
                wins = sum(item.win_count for item in effective)
                losses = sum(item.loss_count for item in effective)
                breakevens = sum(item.breakeven_count for item in effective)
                gross_pnl = sum((self._decimal(item.strategy_gross_pnl) for item in effective), Decimal(0))
                net_pnl = sum((self._decimal(item.strategy_net_pnl) for item in effective), Decimal(0))
                gross_r = sum((self._decimal(item.strategy_gross_r) for item in effective), Decimal(0))
                net_r = sum((self._decimal(item.strategy_net_r) for item in effective), Decimal(0))
                average_gross_pnl = gross_pnl / Decimal(count) if count else None
                average_net_pnl = net_pnl / Decimal(count) if count else None
                average_gross_r = gross_r / Decimal(count) if count else None
                average_net_r = net_r / Decimal(count) if count else None
                win_rate = Decimal(wins) / Decimal(count) if count else None
                winning_pnl = sum((self._decimal(item.total_winning_net_pnl) for item in effective), Decimal(0))
                gross_loss = sum((self._decimal(item.gross_loss) for item in effective), Decimal(0))
                profit_factor = winning_pnl / gross_loss if gross_loss > 0 else Decimal("Infinity") if winning_pnl > 0 else None
                equity_points, ending, maximum_abs, maximum_pct, maximum_ids = self._equity(definition, effective, initial)
                periods, missing_ends, gaps = self._periods(definition, effective, as_of)
        except ValueError as exc:
            reason = str(exc) or "NON_FINITE_PORTFOLIO_INPUT"
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, definition, as_of, history)
        if count != wins + losses + breakevens or sum(item.trade_count for item in contributions) != count:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "PORTFOLIO_COUNT_CONSERVATION_INVALID", definition, as_of, history)
        if sum((item.net_pnl for item in contributions), Decimal(0)) != net_pnl or sum((item.net_r for item in contributions), Decimal(0)) != net_r:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "PORTFOLIO_CONTRIBUTION_CONSERVATION_INVALID", definition, as_of, history)
        population_start = equity_points[0].closed_time if equity_points else None
        population_end = equity_points[-1].closed_time if equity_points else None
        snapshot_id = self._uid(
            "snapshot", definition.portfolio_id, definition.portfolio_version, definition.source_version,
            definition.historical_version, definition.calculation_version, as_of, starting_equity.id,
            *((item.id, item.strategy_id, item.strategy_net_pnl, item.strategy_net_r) for item in effective),
        )
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return PortfolioAggregationResult(exact, None, history)
        if any((item.portfolio_id, item.portfolio_version, item.as_of_time, item.source_version, item.historical_version, item.calculation_version) == (definition.portfolio_id, definition.portfolio_version, as_of, definition.source_version, definition.historical_version, definition.calculation_version) for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_PORTFOLIO_SNAPSHOT", definition, as_of, history)
        snapshot = PortfolioPerformance(
            snapshot_id, definition.portfolio_id, definition.portfolio_version, included,
            definition.included_strategy_ids, definition.excluded_strategy_ids, definition.period_type,
            definition.account_timezone, definition.source_version, definition.strategy_calculation_version,
            definition.calculation_version, definition.historical_version, as_of, population_start, population_end,
            count, wins, losses, breakevens, gross_pnl, net_pnl, gross_r, net_r,
            average_gross_pnl, average_net_pnl, average_gross_r, average_net_r, win_rate,
            average_net_pnl, average_net_r, winning_pnl, gross_loss, profit_factor, initial, ending,
            maximum_abs, maximum_pct, maximum_ids, equity_points, contributions, periods, len(periods),
            tuple(item.id for item in periods if item.net_r == 0), missing_ends, gaps,
            tuple(item.id for item in effective), tuple(point.trade_id for point in equity_points),
            tuple(point.accounting_id for point in equity_points), starting_equity.id, as_of,
            "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS",
        )
        return PortfolioAggregationResult(snapshot, None, PortfolioAggregationHistory(history.snapshots + (snapshot,)))

    def _contribution(self, definition, strategy):
        return StrategyContribution(
            self._uid("contribution", definition.portfolio_id, definition.portfolio_version, strategy.id),
            strategy.strategy_id, strategy.id, strategy.symbol, strategy.timeframe, strategy.setup_model,
            strategy.direction, strategy.trade_count, strategy.win_count, strategy.loss_count,
            strategy.breakeven_count, self._decimal(strategy.strategy_gross_pnl), self._decimal(strategy.strategy_net_pnl),
            self._decimal(strategy.strategy_gross_r), self._decimal(strategy.strategy_net_r),
            strategy.source_trade_ids, strategy.source_accounting_ids,
        )

    def _equity(self, definition, strategies, initial):
        sources = sorted(((point.closed_time, point.trade_id, strategy.strategy_id, strategy.id, point) for strategy in strategies for point in strategy.equity_points), key=lambda row: (row[0], row[1]))
        equity = initial
        peak = initial
        points = []
        for sequence, (_time, _trade_id, strategy_id, snapshot_id, source) in enumerate(sources, start=1):
            prior = equity
            net_pnl = self._decimal(source.net_pnl)
            equity += net_pnl
            peak = max(peak, equity)
            absolute = peak - equity
            percentage = absolute / peak * Decimal(100) if peak > 0 else None
            points.append(PortfolioEquityPoint(
                self._uid("equity-point", definition.portfolio_id, definition.portfolio_version, snapshot_id, source.id),
                sequence, strategy_id, source.trade_id, source.accounting_id, source.closed_time, net_pnl,
                prior, equity, peak, absolute, percentage, snapshot_id, source.id,
            ))
        maximum_abs = max((point.drawdown_abs for point in points), default=Decimal(0))
        percentages = tuple(point.drawdown_pct for point in points if point.drawdown_pct is not None)
        maximum_pct = max(percentages) if percentages else None
        maximum_ids = tuple(point.id for point in points if point.drawdown_abs == maximum_abs)
        return tuple(points), equity, maximum_abs, maximum_pct, maximum_ids

    def _periods(self, definition, strategies, as_of):
        if not strategies:
            return (), (), ()
        maps = [{item.period_end: item for item in strategy.period_observations if item.period_end <= as_of} for strategy in strategies]
        union_ends = set().union(*(set(item) for item in maps))
        aligned_ends = sorted(set.intersection(*(set(item) for item in maps)))
        missing_ends = tuple(sorted(union_ends - set(aligned_ends)))
        observations = []
        for period_end in aligned_ends:
            rows = tuple(mapping[period_end] for mapping in maps)
            first = rows[0]
            if any((row.period_type, row.period_start, row.period_end, row.account_timezone) != (first.period_type, first.period_start, first.period_end, first.account_timezone) for row in rows[1:]):
                raise ValueError("PORTFOLIO_PERIOD_ALIGNMENT_MISMATCH")
            observations.append(PortfolioPeriodObservation(
                self._uid("period", definition.portfolio_id, definition.portfolio_version, period_end, *(row.id for row in rows)),
                definition.portfolio_id, definition.portfolio_version, first.period_type, first.period_start,
                first.period_end, first.account_timezone, sum(row.trade_count for row in rows),
                sum((self._decimal(row.net_pnl) for row in rows), Decimal(0)),
                sum((self._decimal(row.net_r) for row in rows), Decimal(0)),
                tuple(strategy.strategy_id for strategy in strategies), tuple(row.id for row in rows),
                tuple(row.period_id for row in rows), max(row.finalized_time for row in rows),
                definition.source_version, definition.calculation_version, definition.historical_version,
            ))
        gaps = tuple((left.period_end, right.period_start) for left, right in zip(observations, observations[1:]) if left.period_end < right.period_start)
        return tuple(observations), missing_ends, gaps

    def _validate_definition(self, definition, starting, as_of):
        if not definition.immutable or as_of < 0 or definition.creation_time > as_of or definition.period_type not in tuple(PeriodType) or not all(str(value).strip() for value in (definition.portfolio_id, definition.portfolio_version, definition.account_timezone, definition.source_version, definition.strategy_calculation_version, definition.calculation_version, definition.historical_version)):
            return "PORTFOLIO_DEFINITION_INVALID"
        if len(definition.included_strategy_ids) != len(set(definition.included_strategy_ids)) or len(definition.excluded_strategy_ids) != len(set(definition.excluded_strategy_ids)):
            return "PORTFOLIO_MEMBERSHIP_DUPLICATE"
        if not starting.immutable or not all(str(value).strip() for value in (starting.id, starting.portfolio_id, starting.portfolio_version, starting.source_version, starting.historical_version)):
            return "PORTFOLIO_STARTING_EQUITY_INVALID"
        if (starting.portfolio_id, starting.portfolio_version, starting.source_version, starting.historical_version) != (definition.portfolio_id, definition.portfolio_version, definition.source_version, definition.historical_version):
            return "PORTFOLIO_STARTING_EQUITY_VERSION_MISMATCH"
        try:
            self._decimal(starting.equity)
        except ValueError:
            return "NON_FINITE_PORTFOLIO_STARTING_EQUITY"
        return None

    def _validate_strategy(self, definition, strategy, as_of):
        if not strategy.immutable or strategy.as_of_time != as_of:
            return "STRATEGY_POPULATION_NON_FINAL_OR_STALE"
        if (strategy.period_type, strategy.account_timezone, strategy.source_version, strategy.calculation_version, strategy.historical_version) != (definition.period_type, definition.account_timezone, definition.source_version, definition.strategy_calculation_version, definition.historical_version):
            return "STRATEGY_POPULATION_SCOPE_OR_VERSION_MISMATCH"
        if strategy.trade_count != strategy.win_count + strategy.loss_count + strategy.breakeven_count or strategy.trade_count != len(strategy.equity_points):
            return "STRATEGY_POPULATION_COUNT_INVALID"
        equity_ids = [point.id for point in strategy.equity_points]
        trade_ids = [point.trade_id for point in strategy.equity_points]
        accounting_ids = [point.accounting_id for point in strategy.equity_points]
        period_ids = [item.id for item in strategy.period_observations]
        period_ends = [item.period_end for item in strategy.period_observations]
        if len(equity_ids) != len(set(equity_ids)) or len(trade_ids) != len(set(trade_ids)) or len(accounting_ids) != len(set(accounting_ids)) or len(period_ids) != len(set(period_ids)) or len(period_ends) != len(set(period_ends)):
            return "DUPLICATE_STRATEGY_SOURCE_KEY"
        if tuple(point.trade_id for point in strategy.equity_points) != strategy.source_trade_ids or tuple(point.accounting_id for point in strategy.equity_points) != strategy.source_accounting_ids:
            return "STRATEGY_POPULATION_LINEAGE_MISMATCH"
        if tuple(sorted(strategy.equity_points, key=lambda point: (point.closed_time, point.trade_id))) != strategy.equity_points:
            return "STRATEGY_EQUITY_ORDER_INVALID"
        if tuple(sorted(strategy.period_observations, key=lambda item: (item.period_start, item.period_id))) != strategy.period_observations:
            return "STRATEGY_PERIOD_ORDER_INVALID"
        try:
            for value in (
                strategy.strategy_gross_pnl, strategy.strategy_net_pnl,
                strategy.strategy_gross_r, strategy.strategy_net_r,
                strategy.total_winning_net_pnl, strategy.gross_loss,
                strategy.starting_equity, strategy.ending_equity,
            ):
                self._decimal(value)
            net_pnl = sum((self._decimal(point.net_pnl) for point in strategy.equity_points), Decimal(0))
            if net_pnl != self._decimal(strategy.strategy_net_pnl):
                return "STRATEGY_POPULATION_NET_PNL_MISMATCH"
            for point in strategy.equity_points:
                if not point.immutable or point.closed_time > as_of:
                    return "STRATEGY_EQUITY_POINT_NON_FINAL_OR_FUTURE"
            for observation in strategy.period_observations:
                if not observation.immutable or not observation.finalized or observation.period_end > as_of or observation.finalized_time > as_of:
                    return "STRATEGY_PERIOD_NON_FINAL_OR_FUTURE"
                if (observation.strategy_id, observation.period_type, observation.account_timezone, observation.source_version, observation.calculation_version, observation.historical_version) != (strategy.strategy_id, definition.period_type, definition.account_timezone, definition.source_version, definition.strategy_calculation_version, definition.historical_version):
                    return "STRATEGY_PERIOD_SCOPE_OR_VERSION_MISMATCH"
                self._decimal(observation.net_pnl)
                self._decimal(observation.net_r)
        except ValueError:
            return "NON_FINITE_STRATEGY_POPULATION"
        return None
