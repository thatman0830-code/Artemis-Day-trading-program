from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_7_drawdown import DrawdownSnapshot
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodStatisticsSnapshot, PeriodType


@dataclass(frozen=True)
class RiskAdjustedScope:
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
    account_timezone: str
    immutable: bool = True


@dataclass(frozen=True)
class RiskAdjustedConfiguration:
    id: str
    annualization_periods: Decimal
    risk_free_rate: Decimal
    version: str
    immutable: bool = True


@dataclass(frozen=True)
class DailyEquityObservation:
    id: str
    period_snapshot_id: str
    period_id: str
    period_start: int
    period_end: int
    finalized_time: int
    equity: Decimal
    source_equity_snapshot_id: str
    source_equity_point_id: str | None
    source_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class DailyReturnObservation:
    id: str
    sequence: int
    previous_equity_observation_id: str
    current_equity_observation_id: str
    previous_period_id: str
    current_period_id: str
    previous_equity: Decimal
    current_equity: Decimal
    return_value: Decimal
    immutable: bool = True


@dataclass(frozen=True)
class RiskAdjustedSnapshot:
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
    account_timezone: str
    as_of_time: int
    configuration_id: str
    configuration_version: str
    annualization_periods: Decimal
    risk_free_rate: Decimal
    period_count: int
    equity_observation_count: int
    return_count: int
    mean_daily_return: Decimal | None
    annualized_return: Decimal | None
    daily_volatility: Decimal | None
    annualized_volatility: Decimal | None
    daily_downside_deviation: Decimal | None
    annualized_downside_deviation: Decimal | None
    sharpe_ratio: Decimal | None
    sortino_ratio: Decimal | None
    maximum_drawdown_percentage: Decimal | None
    maximum_drawdown_fraction: Decimal | None
    calmar_ratio: Decimal | None
    returns: tuple[DailyReturnObservation, ...]
    source_period_snapshot_ids: tuple[str, ...]
    source_period_ids: tuple[str, ...]
    source_equity_observation_ids: tuple[str, ...]
    source_equity_snapshot_ids: tuple[str, ...]
    source_equity_point_ids: tuple[str, ...]
    source_trade_ids: tuple[str, ...]
    source_accounting_ids: tuple[str, ...]
    source_drawdown_snapshot_id: str
    missing_equity_period_ids: tuple[str, ...]
    gap_period_pairs: tuple[tuple[str, str], ...]
    nonpositive_equity_cutoff_observation_id: str | None
    future_excluded_period_ids: tuple[str, ...]
    rounding_mode: str
    immutable: bool = True


@dataclass(frozen=True)
class RiskAdjustedError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class RiskAdjustedHistory:
    snapshots: tuple[RiskAdjustedSnapshot, ...] = ()


@dataclass(frozen=True)
class RiskAdjustedResult:
    snapshot: RiskAdjustedSnapshot | None
    error: RiskAdjustedError | None
    history: RiskAdjustedHistory

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.error is None


class RiskAdjustedStatisticsEngine:
    """Canonical #29.7.2.11 daily-equity risk-adjusted statistics."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.11:" + kind + ":" + ":".join(map(str, parts))))

    @staticmethod
    def _decimal(value: object, *, finite: bool = True) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError from exc
        if finite and not result.is_finite():
            raise ValueError
        return result

    def _invalid(self, code, reason, scope, as_of, history):
        scope_id = scope.id if scope else None
        error = RiskAdjustedError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, int(as_of))
        return RiskAdjustedResult(None, error, history)

    def calculate(
        self, *, scope: RiskAdjustedScope | None,
        configuration: RiskAdjustedConfiguration | None,
        trades: tuple[TradeAccounting, ...] | None,
        periods: tuple[PeriodStatisticsSnapshot, ...] | None,
        equity_observations: tuple[DailyEquityObservation, ...] | None,
        drawdown: DrawdownSnapshot | None,
        as_of_time: int,
        history: RiskAdjustedHistory = RiskAdjustedHistory(),
    ) -> RiskAdjustedResult:
        as_of = int(as_of_time)
        if None in (scope, configuration, trades, periods, equity_observations, drawdown):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_RISK_ADJUSTED_INPUT_MISSING", scope, as_of, history)
        reason = self._validate_scope_and_config(scope, configuration, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        for values, reason in ((trades, "DUPLICATE_CANONICAL_TRADE_KEY"), (periods, "DUPLICATE_PERIOD"), (equity_observations, "DUPLICATE_EQUITY_OBSERVATION")):
            ids = [item.id for item in values]
            if len(ids) != len(set(ids)):
                return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, reason, scope, as_of, history)
        trade_ids = [trade.trade_id for trade in trades]
        if len(trade_ids) != len(set(trade_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_CANONICAL_TRADE_KEY", scope, as_of, history)
        period_ids = [period.period_id for period in periods]
        period_ends = [period.period_end for period in periods]
        if len(period_ids) != len(set(period_ids)) or len(period_ends) != len(set(period_ends)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_PERIOD", scope, as_of, history)
        observation_period_ids = [item.period_id for item in equity_observations]
        if len(observation_period_ids) != len(set(observation_period_ids)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_EQUITY_PERIOD", scope, as_of, history)
        for trade in trades:
            reason = self._validate_trade(scope, trade)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        for period in periods:
            reason = self._validate_period(scope, period)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        reason = self._validate_drawdown(scope, drawdown, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)

        eligible_periods = tuple(sorted((period for period in periods if period.period_end <= as_of), key=lambda item: (item.period_start, item.period_id)))
        future_periods = tuple(sorted(period.period_id for period in periods if period.period_end > as_of))
        accounting_by_id = {trade.id: trade for trade in trades}
        for period in eligible_periods:
            if period.finalized_time > as_of:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "PERIOD_NOT_FINAL_AT_AS_OF", scope, as_of, history)
            if any(accounting_id not in accounting_by_id for accounting_id in period.source_accounting_ids):
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "PERIOD_ACCOUNTING_LINEAGE_MISSING", scope, as_of, history)
        eligible_ids = {period.id for period in eligible_periods}
        observation_by_snapshot = {}
        try:
            for observation in equity_observations:
                if not observation.immutable or not all((observation.id, observation.period_snapshot_id, observation.period_id, observation.source_equity_snapshot_id, observation.source_version, observation.historical_version)):
                    raise ValueError("EQUITY_OBSERVATION_INVALID")
                if observation.period_snapshot_id not in {period.id for period in periods}:
                    raise ValueError("EQUITY_PERIOD_LINEAGE_MISSING")
                period = next(period for period in periods if period.id == observation.period_snapshot_id)
                if (observation.period_id, observation.period_start, observation.period_end, observation.source_version, observation.historical_version) != (period.period_id, period.period_start, period.period_end, period.source_version, period.historical_version):
                    raise ValueError("EQUITY_PERIOD_IDENTITY_MISMATCH")
                if observation.finalized_time < observation.period_end:
                    raise ValueError("EQUITY_OBSERVATION_NOT_FINAL")
                try:
                    self._decimal(observation.equity)
                except ValueError:
                    raise ValueError("EQUITY_OBSERVATION_NON_FINITE")
                if observation.period_snapshot_id in eligible_ids:
                    if observation.finalized_time > as_of:
                        raise ValueError("EQUITY_OBSERVATION_NOT_FINAL_AT_AS_OF")
                    observation_by_snapshot[observation.period_snapshot_id] = observation
        except ValueError as exc:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, str(exc), scope, as_of, history)

        ordered_observations = tuple(observation_by_snapshot[period.id] for period in eligible_periods if period.id in observation_by_snapshot)
        missing = tuple(period.period_id for period in eligible_periods if period.id not in observation_by_snapshot)
        gap_pairs = []
        returns = []
        cutoff = None
        with localcontext() as context:
            context.prec = max(context.prec, 34)
            context.rounding = ROUND_HALF_UP
            for previous, current in zip(ordered_observations, ordered_observations[1:]):
                if previous.period_end != current.period_start:
                    gap_pairs.append((previous.period_id, current.period_id))
                    continue
                previous_equity = self._decimal(previous.equity)
                current_equity = self._decimal(current.equity)
                if cutoff is not None:
                    continue
                if previous_equity <= 0:
                    cutoff = previous.id
                    continue
                value = current_equity / previous_equity - Decimal(1)
                returns.append(DailyReturnObservation(
                    self._uid("return", scope.id, previous.id, current.id), len(returns) + 1,
                    previous.id, current.id, previous.period_id, current.period_id,
                    previous_equity, current_equity, value,
                ))
                if current_equity <= 0:
                    cutoff = current.id

            values = tuple(item.return_value for item in returns)
            count = len(values)
            mean = sum(values, Decimal(0)) / Decimal(count) if count else None
            annualized_return = mean * configuration.annualization_periods if mean is not None else None
            daily_volatility = None
            if count >= 2:
                variance = sum((value - mean) ** 2 for value in values) / Decimal(count - 1)
                daily_volatility = variance.sqrt()
            root_periods = configuration.annualization_periods.sqrt()
            annualized_volatility = daily_volatility * root_periods if daily_volatility is not None else None
            downside = None
            if count:
                downside = (sum(min(value, Decimal(0)) ** 2 for value in values) / Decimal(count)).sqrt()
            annualized_downside = downside * root_periods if downside is not None else None
            sharpe = self._ratio(mean, daily_volatility, root_periods, count, require_two=True)
            sortino = self._ratio(mean, downside, root_periods, count, require_two=True)
            max_dd_pct = self._decimal(drawdown.maximum_drawdown_pct) if drawdown.maximum_drawdown_pct is not None else None
            max_dd_fraction = max_dd_pct / Decimal(100) if max_dd_pct is not None else None
            calmar = self._calmar(annualized_return, max_dd_fraction, count)

        source_period_snapshot_ids = tuple(period.id for period in eligible_periods)
        source_accounting_ids = tuple(accounting_id for period in eligible_periods for accounting_id in period.source_accounting_ids)
        source_trade_ids = tuple(trade_id for period in eligible_periods for trade_id in period.source_trade_ids)
        source_equity_ids = tuple(item.id for item in ordered_observations)
        identity_parts = (
            *source_period_snapshot_ids,
            *((item.id, item.equity, item.finalized_time) for item in ordered_observations),
            drawdown.id, drawdown.maximum_drawdown_pct, configuration.id,
        )
        snapshot_id = self._uid("snapshot", scope.id, scope.source_version, scope.historical_version, scope.calculation_version, as_of, *identity_parts)
        exact = next((item for item in history.snapshots if item.id == snapshot_id), None)
        if exact:
            return RiskAdjustedResult(exact, None, history)
        if any((item.scope_id, item.as_of_time, item.source_version, item.historical_version, item.calculation_version) == (scope.id, as_of, scope.source_version, scope.historical_version, scope.calculation_version) for item in history.snapshots):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_RISK_ADJUSTED_SNAPSHOT", scope, as_of, history)
        snapshot = RiskAdjustedSnapshot(
            snapshot_id, scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.setup_model, scope.direction,
            scope.input_version, scope.source_version, scope.calculation_version, scope.historical_version, scope.account_timezone,
            as_of, configuration.id, configuration.version, configuration.annualization_periods, configuration.risk_free_rate,
            len(eligible_periods), len(ordered_observations), len(returns), mean, annualized_return,
            daily_volatility, annualized_volatility, downside, annualized_downside, sharpe, sortino,
            max_dd_pct, max_dd_fraction, calmar, tuple(returns), source_period_snapshot_ids,
            tuple(period.period_id for period in eligible_periods), source_equity_ids,
            tuple(item.source_equity_snapshot_id for item in ordered_observations),
            tuple(item.source_equity_point_id for item in ordered_observations if item.source_equity_point_id is not None),
            source_trade_ids, source_accounting_ids, drawdown.id, missing, tuple(gap_pairs), cutoff,
            future_periods, ROUND_HALF_UP, True,
        )
        return RiskAdjustedResult(snapshot, None, RiskAdjustedHistory(history.snapshots + (snapshot,)))

    @staticmethod
    def _ratio(mean, deviation, root_periods, count, *, require_two):
        if mean is None or (require_two and count < 2) or deviation is None:
            return None
        if deviation != 0:
            return mean / deviation * root_periods
        if mean > 0:
            return Decimal("Infinity")
        if mean < 0:
            return Decimal("-Infinity")
        return None

    @staticmethod
    def _calmar(annualized_return, maximum_drawdown_fraction, count):
        if not count or annualized_return is None or maximum_drawdown_fraction is None:
            return None
        if maximum_drawdown_fraction != 0:
            return annualized_return / maximum_drawdown_fraction
        if annualized_return > 0:
            return Decimal("Infinity")
        if annualized_return < 0:
            return Decimal("-Infinity")
        return None

    def _validate_scope_and_config(self, scope, configuration, as_of):
        if not scope.immutable or as_of < 0 or not all(str(value).strip() for value in (scope.id, scope.strategy_id, scope.symbol, scope.timeframe, scope.input_version, scope.source_version, scope.calculation_version, scope.historical_version, scope.account_timezone)):
            return "RISK_ADJUSTED_SCOPE_INVALID"
        if not configuration.immutable or not configuration.id or not configuration.version:
            return "RISK_ADJUSTED_CONFIGURATION_INVALID"
        try:
            periods = self._decimal(configuration.annualization_periods)
            risk_free = self._decimal(configuration.risk_free_rate)
        except ValueError:
            return "RISK_ADJUSTED_CONFIGURATION_NON_FINITE"
        if periods != Decimal(252) or risk_free != Decimal(0):
            return "NON_CANONICAL_RISK_ADJUSTED_CONFIGURATION"
        return None

    def _validate_trade(self, scope, trade):
        if not trade.immutable:
            return "NON_FINAL_ACCOUNTING_RECORD"
        if trade.strategy_id != scope.strategy_id or trade.symbol != scope.symbol or trade.timeframe.lower() != scope.timeframe.lower() or trade.model != scope.setup_model or trade.direction != scope.direction:
            return "RISK_ADJUSTED_ACCOUNTING_SCOPE_MISMATCH"
        if trade.input_version != scope.input_version or trade.opened_time > trade.closed_time or trade.accounting_time < trade.closed_time:
            return "RISK_ADJUSTED_ACCOUNTING_VERSION_OR_CHRONOLOGY_INVALID"
        try:
            self._decimal(trade.net_pnl)
            self._decimal(trade.post_trade_equity)
        except ValueError:
            return "NON_FINITE_ACCOUNTING_INPUT"
        return None

    def _validate_period(self, scope, period):
        if not period.immutable or period.period_type != PeriodType.DAILY or period.period_start >= period.period_end or period.finalized_time < period.period_end:
            return "DAILY_PERIOD_INVALID_OR_NON_FINAL"
        if (period.scope_id, period.strategy_id, period.symbol, period.timeframe.lower(), period.setup_model, period.direction) != (scope.id, scope.strategy_id, scope.symbol, scope.timeframe.lower(), scope.setup_model, scope.direction):
            return "RISK_ADJUSTED_PERIOD_SCOPE_MISMATCH"
        if (period.input_version, period.source_version, period.calculation_version, period.historical_version, period.account_timezone) != (scope.input_version, scope.source_version, scope.calculation_version, scope.historical_version, scope.account_timezone):
            return "RISK_ADJUSTED_PERIOD_VERSION_MISMATCH"
        if len(period.source_trade_ids) != len(set(period.source_trade_ids)) or len(period.source_accounting_ids) != len(set(period.source_accounting_ids)):
            return "DUPLICATE_PERIOD_SOURCE"
        return None

    def _validate_drawdown(self, scope, drawdown, as_of):
        if not drawdown.immutable or drawdown.as_of_time != as_of:
            return "DRAWDOWN_NOT_FINAL_AT_AS_OF"
        if (drawdown.scope_id, drawdown.strategy_id, drawdown.symbol, drawdown.timeframe.lower(), drawdown.setup_model, drawdown.direction, drawdown.input_version, drawdown.calculation_version) != (scope.id, scope.strategy_id, scope.symbol, scope.timeframe.lower(), scope.setup_model, scope.direction, scope.input_version, scope.calculation_version):
            return "RISK_ADJUSTED_DRAWDOWN_SCOPE_MISMATCH"
        try:
            maximum_abs = self._decimal(drawdown.maximum_drawdown_abs)
            maximum_pct = self._decimal(drawdown.maximum_drawdown_pct) if drawdown.maximum_drawdown_pct is not None else None
        except ValueError:
            return "NON_FINITE_DRAWDOWN_INPUT"
        if maximum_abs < 0 or (maximum_pct is not None and maximum_pct < 0):
            return "NEGATIVE_DRAWDOWN_INPUT"
        return None
