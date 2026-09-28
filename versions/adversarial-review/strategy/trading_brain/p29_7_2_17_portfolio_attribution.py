from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodType
from strategy.trading_brain.p29_7_2_16_portfolio_aggregation import PortfolioPerformance


class AttributionErrorCode(str, Enum):
    ATTRIBUTION_INVALID = "ATTRIBUTION_INVALID"


@dataclass(frozen=True)
class AttributionScope:
    id: str
    portfolio_id: str
    portfolio_version: str
    period_type: PeriodType
    account_timezone: str
    source_version: str
    portfolio_calculation_version: str
    calculation_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class StrategyAttribution:
    id: str
    sequence: int
    strategy_id: str
    symbol: str
    timeframe: str
    setup_model: object
    direction: object
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    net_pnl_contribution: Decimal
    net_r_contribution: Decimal
    source_strategy_contribution_id: str
    source_strategy_snapshot_id: str
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class AttributionPeriodReference:
    id: str
    portfolio_period_observation_id: str
    period_type: PeriodType
    period_start: int
    period_end: int
    account_timezone: str
    portfolio_net_pnl: Decimal
    portfolio_net_r: Decimal
    portfolio_trade_count: int
    contributing_strategy_ids: tuple[str, ...]
    source_strategy_period_observation_ids: tuple[str, ...]
    finalized_time: int
    immutable: bool = True


@dataclass(frozen=True)
class PortfolioAttribution:
    id: str
    scope_id: str
    portfolio_id: str
    portfolio_version: str
    included_strategy_ids: tuple[str, ...]
    excluded_strategy_ids: tuple[str, ...]
    effective_strategy_ids: tuple[str, ...]
    period_type: PeriodType
    account_timezone: str
    source_version: str
    portfolio_calculation_version: str
    calculation_version: str
    historical_version: str
    as_of_time: int
    strategy_count: int
    trade_count: int
    attributed_trade_count: int
    portfolio_net_pnl: Decimal
    attributed_net_pnl: Decimal
    net_pnl_conservation_delta: Decimal
    portfolio_net_r: Decimal
    attributed_net_r: Decimal
    net_r_conservation_delta: Decimal
    starting_equity: Decimal
    ending_equity: Decimal
    strategy_attributions: tuple[StrategyAttribution, ...]
    period_references: tuple[AttributionPeriodReference, ...]
    missing_period_ends: tuple[int, ...]
    zero_return_period_ids: tuple[str, ...]
    period_gap_pairs: tuple[tuple[int, int], ...]
    source_portfolio_snapshot_id: str
    source_strategy_contribution_ids: tuple[str, ...]
    source_strategy_snapshot_ids: tuple[str, ...]
    source_portfolio_period_observation_ids: tuple[str, ...]
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    calculation_timestamp: int
    immutable: bool = True


@dataclass(frozen=True)
class AttributionError:
    id: str
    code: object
    reason: str
    portfolio_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class AttributionHistory:
    snapshots: tuple[PortfolioAttribution, ...] = ()


@dataclass(frozen=True)
class AttributionResult:
    snapshot: PortfolioAttribution | None
    error: AttributionError | None
    history: AttributionHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class PortfolioAttributionEngine:
    """Canonical #29.7.2.17 read-only conservation decomposition."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.17:" + kind + ":" + ":".join(map(str, parts))))

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
        portfolio_id = scope.portfolio_id if scope else None
        code_value = code.value if hasattr(code, "value") else str(code)
        error = AttributionError(self._uid("error", portfolio_id or "NONE", code_value, reason, as_of), code, reason, portfolio_id, int(as_of))
        return AttributionResult(None, error, history)

    def calculate(
        self, *, scope: AttributionScope | None,
        portfolio: PortfolioPerformance | None,
        as_of_time: int,
        history: AttributionHistory = AttributionHistory(),
    ) -> AttributionResult:
        as_of = int(as_of_time)
        if scope is None or portfolio is None:
            return self._invalid(AttributionErrorCode.ATTRIBUTION_INVALID, "REQUIRED_ATTRIBUTION_INPUT_MISSING", scope, as_of, history)
        reason = self._validate_scope(scope, as_of)
        if reason:
            return self._invalid(AttributionErrorCode.ATTRIBUTION_INVALID, reason, scope, as_of, history)
        contribution_ids = [item.id for item in portfolio.strategy_contributions]
        strategy_ids = [item.strategy_id for item in portfolio.strategy_contributions]
        trade_ids = [trade_id for item in portfolio.strategy_contributions for trade_id in item.source_trade_ids]
        accounting_ids = [accounting_id for item in portfolio.strategy_contributions for accounting_id in item.source_accounting_ids]
        period_ids = [item.id for item in portfolio.period_observations]
        if len(contribution_ids) != len(set(contribution_ids)) or len(strategy_ids) != len(set(strategy_ids)) or len(trade_ids) != len(set(trade_ids)) or len(accounting_ids) != len(set(accounting_ids)) or len(period_ids) != len(set(period_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_ATTRIBUTION_SOURCE_KEY", scope, as_of, history)
        reason = self._validate_portfolio(scope, portfolio, as_of)
        if reason:
            return self._invalid(AttributionErrorCode.ATTRIBUTION_INVALID, reason, scope, as_of, history)
        try:
            rows = tuple(self._attribution(scope, item, sequence) for sequence, item in enumerate(portfolio.strategy_contributions, start=1))
            period_rows = tuple(self._period(scope, item) for item in portfolio.period_observations)
            portfolio_net_pnl = self._decimal(portfolio.portfolio_net_pnl)
            portfolio_net_r = self._decimal(portfolio.portfolio_net_r)
            attributed_net_pnl = sum((item.net_pnl_contribution for item in rows), Decimal(0))
            attributed_net_r = sum((item.net_r_contribution for item in rows), Decimal(0))
            deltas = (
                portfolio_net_pnl - attributed_net_pnl,
                portfolio_net_r - attributed_net_r,
            )
        except ValueError:
            return self._invalid(AttributionErrorCode.ATTRIBUTION_INVALID, "NON_FINITE_ATTRIBUTION_INPUT", scope, as_of, history)
        if any(delta != 0 for delta in deltas) or sum(item.trade_count for item in rows) != portfolio.trade_count:
            return self._invalid(AttributionErrorCode.ATTRIBUTION_INVALID, "ATTRIBUTION_CONSERVATION_INVALID", scope, as_of, history)
        snapshot_id = self._uid(
            "snapshot", scope.id, portfolio.id, scope.calculation_version, as_of,
            *((item.source_strategy_contribution_id, item.net_pnl_contribution, item.net_r_contribution) for item in rows),
        )
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return AttributionResult(exact, None, history)
        if any((item.scope_id, item.portfolio_id, item.portfolio_version, item.as_of_time, item.source_version, item.historical_version, item.calculation_version) == (scope.id, scope.portfolio_id, scope.portfolio_version, as_of, scope.source_version, scope.historical_version, scope.calculation_version) for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_ATTRIBUTION_SNAPSHOT", scope, as_of, history)
        snapshot = PortfolioAttribution(
            snapshot_id, scope.id, portfolio.portfolio_id, portfolio.portfolio_version,
            portfolio.included_strategy_ids, portfolio.excluded_strategy_ids, portfolio.effective_strategy_ids,
            portfolio.period_type, portfolio.account_timezone, portfolio.source_version,
            portfolio.calculation_version, scope.calculation_version, portfolio.historical_version, as_of,
            len(rows), portfolio.trade_count, sum(item.trade_count for item in rows),
            portfolio_net_pnl, attributed_net_pnl, deltas[0],
            portfolio_net_r, attributed_net_r, deltas[1], self._decimal(portfolio.starting_equity),
            self._decimal(portfolio.ending_equity), rows, period_rows, portfolio.missing_period_ends,
            portfolio.zero_return_period_ids, portfolio.period_gap_pairs, portfolio.id,
            tuple(item.id for item in portfolio.strategy_contributions), portfolio.source_strategy_snapshot_ids,
            tuple(item.id for item in portfolio.period_observations), portfolio.source_trade_ids,
            portfolio.source_accounting_ids, as_of,
        )
        return AttributionResult(snapshot, None, AttributionHistory(history.snapshots + (snapshot,)))

    def _attribution(self, scope, item, sequence):
        return StrategyAttribution(
            self._uid("strategy", scope.id, item.id), sequence, item.strategy_id, item.symbol,
            item.timeframe, item.setup_model, item.direction, item.trade_count, item.win_count,
            item.loss_count, item.breakeven_count, self._decimal(item.net_pnl), self._decimal(item.net_r),
            item.id, item.strategy_snapshot_id, item.source_trade_ids, item.source_accounting_ids,
        )

    def _period(self, scope, item):
        return AttributionPeriodReference(
            self._uid("period", scope.id, item.id), item.id, item.period_type, item.period_start,
            item.period_end, item.account_timezone, self._decimal(item.net_pnl), self._decimal(item.net_r),
            item.trade_count, item.contributing_strategy_ids, item.source_strategy_period_observation_ids,
            item.finalized_time,
        )

    def _validate_scope(self, scope, as_of):
        if not scope.immutable or as_of < 0 or scope.period_type not in tuple(PeriodType) or not all(str(value).strip() for value in (scope.id, scope.portfolio_id, scope.portfolio_version, scope.account_timezone, scope.source_version, scope.portfolio_calculation_version, scope.calculation_version, scope.historical_version)):
            return "ATTRIBUTION_SCOPE_INVALID"
        return None

    def _validate_portfolio(self, scope, portfolio, as_of):
        if not portfolio.immutable or portfolio.as_of_time != as_of or portfolio.calculation_timestamp != as_of:
            return "PORTFOLIO_ATTRIBUTION_SOURCE_NON_FINAL_OR_STALE"
        if (portfolio.portfolio_id, portfolio.portfolio_version, portfolio.period_type, portfolio.account_timezone, portfolio.source_version, portfolio.calculation_version, portfolio.historical_version) != (scope.portfolio_id, scope.portfolio_version, scope.period_type, scope.account_timezone, scope.source_version, scope.portfolio_calculation_version, scope.historical_version):
            return "PORTFOLIO_ATTRIBUTION_SCOPE_OR_VERSION_MISMATCH"
        expected_effective = tuple(strategy_id for strategy_id in portfolio.included_strategy_ids if strategy_id not in set(portfolio.excluded_strategy_ids))
        if portfolio.effective_strategy_ids != expected_effective or tuple(item.strategy_id for item in portfolio.strategy_contributions) != expected_effective:
            return "PORTFOLIO_MEMBERSHIP_OR_ORDER_MISMATCH"
        if len(portfolio.included_strategy_ids) != len(set(portfolio.included_strategy_ids)) or len(portfolio.excluded_strategy_ids) != len(set(portfolio.excluded_strategy_ids)):
            return "PORTFOLIO_MEMBERSHIP_DUPLICATE"
        if portfolio.trade_count != portfolio.win_count + portfolio.loss_count + portfolio.breakeven_count:
            return "PORTFOLIO_COUNT_CONSERVATION_INVALID"
        if portfolio.population_start_time is not None and portfolio.population_end_time is not None and portfolio.population_start_time > portfolio.population_end_time:
            return "PORTFOLIO_POPULATION_CHRONOLOGY_INVALID"
        if portfolio.population_end_time is not None and portfolio.population_end_time > as_of:
            return "PORTFOLIO_POPULATION_FUTURE"
        if tuple(point.trade_id for point in portfolio.equity_points) != portfolio.source_trade_ids or tuple(point.accounting_id for point in portfolio.equity_points) != portfolio.source_accounting_ids:
            return "PORTFOLIO_TRADE_LINEAGE_MISMATCH"
        if tuple(sorted(portfolio.equity_points, key=lambda point: (point.closed_time, point.trade_id))) != portfolio.equity_points:
            return "PORTFOLIO_EQUITY_ORDER_INVALID"
        if tuple(sorted(portfolio.period_observations, key=lambda item: (item.period_start, item.id))) != portfolio.period_observations:
            return "PORTFOLIO_PERIOD_ORDER_INVALID"
        if portfolio.aligned_period_count != len(portfolio.period_observations):
            return "PORTFOLIO_PERIOD_COUNT_MISMATCH"
        if portfolio.source_strategy_snapshot_ids != tuple(item.strategy_snapshot_id for item in portfolio.strategy_contributions):
            return "PORTFOLIO_STRATEGY_LINEAGE_MISMATCH"
        period_ids = tuple(item.id for item in portfolio.period_observations)
        if portfolio.zero_return_period_ids != tuple(item.id for item in portfolio.period_observations if item.net_r == 0):
            return "PORTFOLIO_ZERO_PERIOD_LINEAGE_MISMATCH"
        if len(portfolio.missing_period_ends) != len(set(portfolio.missing_period_ends)) or tuple(sorted(portfolio.missing_period_ends)) != portfolio.missing_period_ends:
            return "PORTFOLIO_MISSING_PERIOD_LINEAGE_INVALID"
        try:
            for value in (
                portfolio.portfolio_gross_pnl, portfolio.portfolio_net_pnl,
                portfolio.portfolio_gross_r, portfolio.portfolio_net_r,
                portfolio.starting_equity, portfolio.ending_equity,
            ):
                self._decimal(value)
            for contribution in portfolio.strategy_contributions:
                if not contribution.immutable or contribution.trade_count != contribution.win_count + contribution.loss_count + contribution.breakeven_count:
                    return "STRATEGY_CONTRIBUTION_INVALID"
                for value in (contribution.gross_pnl, contribution.net_pnl, contribution.gross_r, contribution.net_r):
                    self._decimal(value)
            for point in portfolio.equity_points:
                if not point.immutable or point.closed_time > as_of:
                    return "PORTFOLIO_EQUITY_POINT_NON_FINAL_OR_FUTURE"
                for value in (point.net_pnl, point.prior_equity, point.equity, point.peak_equity, point.drawdown_abs):
                    self._decimal(value)
            for period in portfolio.period_observations:
                if not period.immutable or period.period_end > as_of or period.finalized_time > as_of:
                    return "PORTFOLIO_PERIOD_NON_FINAL_OR_FUTURE"
                if (period.period_type, period.account_timezone, period.source_version, period.calculation_version, period.historical_version, period.contributing_strategy_ids) != (portfolio.period_type, portfolio.account_timezone, portfolio.source_version, portfolio.calculation_version, portfolio.historical_version, portfolio.effective_strategy_ids):
                    return "PORTFOLIO_PERIOD_SCOPE_OR_MEMBERSHIP_MISMATCH"
                self._decimal(period.net_pnl)
                self._decimal(period.net_r)
        except ValueError:
            return "NON_FINITE_ATTRIBUTION_INPUT"
        contribution_trade_ids = tuple(trade_id for item in portfolio.strategy_contributions for trade_id in item.source_trade_ids)
        contribution_accounting_ids = tuple(accounting_id for item in portfolio.strategy_contributions for accounting_id in item.source_accounting_ids)
        if len(contribution_trade_ids) != len(set(contribution_trade_ids)) or len(contribution_accounting_ids) != len(set(contribution_accounting_ids)):
            return "DUPLICATE_ATTRIBUTION_SOURCE_KEY"
        if set(contribution_trade_ids) != set(portfolio.source_trade_ids) or set(contribution_accounting_ids) != set(portfolio.source_accounting_ids):
            return "PORTFOLIO_CONTRIBUTION_LINEAGE_MISMATCH"
        if sum(item.trade_count for item in portfolio.strategy_contributions) != portfolio.trade_count:
            return "ATTRIBUTION_CONSERVATION_INVALID"
        return None
