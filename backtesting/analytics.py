from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backtesting.manifests import BacktestRunManifest
from backtesting.simulation import TradeSimulationState
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_2_1_trade_classification_count import TradeClassificationCountEngine, TradeCountScope
from strategy.trading_brain.p29_7_2_2_return_statistics import ReturnStatisticsEngine
from strategy.trading_brain.p29_7_2_3_expectancy import ExpectancyEngine
from strategy.trading_brain.p29_7_2_4_profit_factor import ProfitFactorEngine
from strategy.trading_brain.p29_7_2_5_cumulative_pnl_r import CumulativePnLREngine
from strategy.trading_brain.p29_7_2_6_equity_curve import EquityCurveEngine
from strategy.trading_brain.p29_7_2_7_drawdown import DrawdownEngine
from strategy.trading_brain.p29_7_2_8_streak_statistics import StreakStatisticsEngine
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodDefinition, PeriodStatisticsEngine, PeriodType
from strategy.trading_brain.p29_7_2_10_distribution_statistics import DistributionScope, DistributionStatisticsEngine
from strategy.trading_brain.p29_7_2_12_recovery import RecoveryScope, RecoveryStatisticsEngine, StartingEquityObservation
from strategy.trading_brain.p29_7_2_13_underwater import UnderwaterScope, UnderwaterStatisticsEngine
from strategy.trading_brain.p29_7_2_14_trade_sequence import TradeSequenceEngine, TradeSequenceScope
from strategy.trading_brain.p29_7_2_15_strategy_aggregation import (
    StrategyAggregationEngine, StrategyAggregationScope, StrategyStartingEquity,
)
from strategy.trading_brain.p29_7_2_18_strategy_overlap import OverlapScope, StrategyOverlapEngine
from strategy.trading_brain.owner_policies import OWNER_WIN_RATE_OBJECTIVE_ID
from strategy.trading_brain.p29_7_2_owner_performance_readiness import PerformanceReadinessEngine


def _hash(*parts: object) -> str:
    return sha256("\x1f".join(map(str, parts)).encode()).hexdigest()


def _ms(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("as_of must be UTC timezone-aware")
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _ceil_ms(value: datetime) -> int:
    floor = _ms(value)
    return floor + (1 if value.astimezone(timezone.utc).microsecond % 1000 else 0)


@dataclass(frozen=True)
class AnalyticsConfiguration:
    id: str
    strategy_id: str
    timeframe: str
    setup_model: SetupModel
    direction: StructuralRegime
    input_version: str
    source_version: str
    calculation_version: str
    historical_version: str
    account_timezone: str = "UTC"
    immutable: bool = True
    performance_objective_id: str = "NONE"


@dataclass(frozen=True)
class AnalyticsReference:
    owner: str
    status: str
    record_id: str | None
    record: object | None
    reason: str | None = None


@dataclass(frozen=True)
class BacktestResult:
    id: str
    run_id: str
    dataset_id: str
    dataset_fingerprint: str
    trading_brain_contract_version: str
    strategy_configuration_version: str
    model_configuration_version: str
    replay_start_inclusive: datetime
    replay_end_exclusive: datetime
    as_of: datetime
    starting_equity: object
    ending_equity: object
    finalized_trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    analytics: tuple[AnalyticsReference, ...]
    source_lineage_fingerprint: str
    completion_status: str
    mode: str = "PAPER_SIMULATION"
    exchange_submission_enabled: bool = False
    immutable: bool = True
    risk_reward_policy_id: str = "CANONICAL_MIN_RR_V1"
    performance_objective_id: str = "NONE"

    def reference(self, owner: str) -> AnalyticsReference:
        return next(item for item in self.analytics if item.owner == owner)


@dataclass(frozen=True)
class AnalyticsCheckpoint:
    id: str
    run_id: str
    simulation_state_id: str
    accounting_cursor_id: str | None
    equity_snapshot_id: str
    result_id: str
    as_of: datetime


class CanonicalAnalyticsOrchestrator:
    """Calls frozen #29.7.2 owners; contains no analytics formulas."""

    def __init__(self, *, run: BacktestRunManifest, configuration: AnalyticsConfiguration):
        self.run, self.configuration = run, configuration
        if configuration.strategy_id != run.strategy_configuration_version:
            raise ValueError("analytics strategy/run identity mismatch")
        try:
            ZoneInfo(configuration.account_timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("analytics AccountTimezone must be a valid IANA timezone") from error

    @staticmethod
    def _ref(owner, result):
        record = getattr(result, "snapshot", None) or getattr(result, "record", None)
        error = getattr(result, "error", None)
        return AnalyticsReference(owner, "COMPLETE" if record is not None and error is None else "MISSING",
                                  getattr(record, "id", None), record,
                                  getattr(error, "reason", None))

    def calculate(self, *, state: TradeSimulationState, as_of: datetime) -> BacktestResult:
        now = _ceil_ms(as_of)
        if as_of < self.run.replay_end_exclusive:
            raise ValueError("final BacktestResult requires completed replay interval")
        if state.run_id != self.run.id or state.dataset_id != self.run.dataset_id or state.dataset_fingerprint != self.run.dataset_fingerprint:
            raise ValueError("analytics run/dataset identity mismatch")
        if state.equity_ledger is None or not state.equity_ledger.snapshots:
            raise ValueError("finalized equity lineage is required")
        if any(trade.exit is None for trade in state.trades):
            raise ValueError("incomplete lifecycle cannot produce final analytics")
        trades = tuple(sorted(state.accounting_history.records, key=lambda x: (x.closed_time, x.trade_id)))
        if len({x.id for x in trades}) != len(trades) or len({x.trade_id for x in trades}) != len(trades):
            raise ValueError("duplicate finalized accounting facts")
        if any(t.accounting_time > now or t.closed_time > now for t in trades):
            raise ValueError("future accounting cannot enter analytics")
        c = self.configuration
        if any((t.strategy_id, t.symbol, t.timeframe.lower(), t.model, t.direction, t.input_version) !=
               (c.strategy_id, self.run.symbol, c.timeframe.lower(), c.setup_model, c.direction, c.input_version)
               for t in trades):
            raise ValueError("analytics trade scope/version mismatch")
        scope = TradeCountScope(_hash("scope", c.id), c.strategy_id, self.run.symbol,
            c.timeframe, c.setup_model, c.direction, c.input_version, c.calculation_version)
        refs = []
        count = TradeClassificationCountEngine().calculate(scope=scope, trades=trades, as_of_time=now); refs.append(self._ref("#29.7.2.1", count))
        returns = ReturnStatisticsEngine().calculate(scope=scope, trades=trades, as_of_time=now); refs.append(self._ref("#29.7.2.2", returns))
        expectancy = ExpectancyEngine().calculate(scope=scope, trades=trades, as_of_time=now); refs.append(self._ref("#29.7.2.3", expectancy))
        profit = ProfitFactorEngine().calculate(scope=scope, trades=trades, as_of_time=now); refs.append(self._ref("#29.7.2.4", profit))
        cumulative = CumulativePnLREngine().calculate(scope=scope, trades=trades, as_of_time=now); refs.append(self._ref("#29.7.2.5", cumulative))
        curve = EquityCurveEngine().calculate(cumulative=cumulative.snapshot, starting_equity=self.run.starting_equity, as_of_time=now); refs.append(self._ref("#29.7.2.6", curve))
        drawdown = DrawdownEngine().calculate(equity_curve=curve.snapshot, as_of_time=now); refs.append(self._ref("#29.7.2.7", drawdown))
        streak = StreakStatisticsEngine().calculate(scope=scope, trades=trades, as_of_time=now); refs.append(self._ref("#29.7.2.8", streak))
        period_def = PeriodDefinition(PeriodType.FULL_HISTORY, c.account_timezone,
            _ms(self.run.replay_start_inclusive), _ceil_ms(self.run.replay_end_exclusive),
            c.source_version, c.historical_version)
        period = PeriodStatisticsEngine().calculate(scope=scope, period=period_def, trades=trades, as_of_time=now); refs.append(self._ref("#29.7.2.9", period))
        if c.performance_objective_id == OWNER_WIN_RATE_OBJECTIVE_ID:
            readiness = PerformanceReadinessEngine().evaluate(
                count=count.snapshot, expectancy=expectancy.snapshot,
                dataset_id=self.run.dataset_id, period_id=period.snapshot.id,
                as_of_time=now, sample_type=self.run.performance_sample_type,
            )
            refs.append(AnalyticsReference(
                OWNER_WIN_RATE_OBJECTIVE_ID, "COMPLETE", readiness.snapshot.id,
                readiness.snapshot, readiness.snapshot.reason,
            ))
        elif c.performance_objective_id != "NONE":
            raise ValueError("unknown performance objective identity")
        dscope = DistributionScope(_hash("distribution", c.id), c.strategy_id, self.run.symbol,
            c.timeframe, c.setup_model, c.direction, c.input_version, c.source_version,
            c.calculation_version, c.historical_version)
        distribution = DistributionStatisticsEngine().calculate(scope=dscope, trades=trades, as_of_time=now); refs.append(self._ref("#29.7.2.10", distribution))
        refs.append(AnalyticsReference("#29.7.2.11", "NOT_APPLICABLE", None, None,
            "No finalized DAILY period/equity observation series was requested."))
        baseline = StartingEquityObservation(_hash("baseline", c.id),
            _ms(self.run.replay_start_inclusive), self.run.starting_equity, curve.snapshot.id)
        rscope = RecoveryScope(scope.id, c.strategy_id, self.run.symbol,
            c.timeframe, c.setup_model, c.direction, c.input_version, c.calculation_version)
        recovery = RecoveryStatisticsEngine().calculate(scope=rscope, drawdown=drawdown.snapshot,
            starting_equity=baseline, as_of_time=now); refs.append(self._ref("#29.7.2.12", recovery))
        uscope = UnderwaterScope(scope.id, c.strategy_id, self.run.symbol,
            c.timeframe, c.setup_model, c.direction, c.input_version, c.calculation_version)
        underwater = UnderwaterStatisticsEngine().calculate(scope=uscope, drawdown=drawdown.snapshot,
            recovery=recovery.snapshot, starting_equity=baseline, as_of_time=now); refs.append(self._ref("#29.7.2.13", underwater))
        sscope = TradeSequenceScope(scope.id, c.strategy_id, self.run.symbol,
            c.timeframe, c.setup_model, c.direction, c.input_version, c.source_version,
            c.calculation_version, c.historical_version)
        sequence = TradeSequenceEngine().calculate(scope=sscope, trades=trades,
            cumulative=cumulative.snapshot, streaks=streak.snapshot, as_of_time=now); refs.append(self._ref("#29.7.2.14", sequence))
        agscope = StrategyAggregationScope(scope.id, c.strategy_id,
            self.run.symbol, c.timeframe, c.setup_model, c.direction, c.input_version,
            c.source_version, c.calculation_version, c.historical_version,
            PeriodType.FULL_HISTORY, c.account_timezone)
        starting = StrategyStartingEquity(_hash("strategy-equity", c.id), c.strategy_id,
            self.run.starting_equity, c.source_version, c.historical_version)
        aggregation = StrategyAggregationEngine().calculate(scope=agscope, trades=trades,
            periods=(period.snapshot,), starting_equity=starting, as_of_time=now); refs.append(self._ref("#29.7.2.15", aggregation))
        for owner in ("#29.7.2.16", "#29.7.2.17"):
            refs.append(AnalyticsReference(owner, "NOT_APPLICABLE", None, None,
                "Explicit compatible portfolio/universe definition was not supplied."))
        oscope = OverlapScope(scope.id, c.input_version, c.calculation_version,
                              c.historical_version)
        overlap = StrategyOverlapEngine().calculate(scope=oscope, trades=trades,
                                                     as_of_time=now)
        refs.append(self._ref("#29.7.2.18", overlap))
        for owner in ("#29.7.2.19", "#29.7.2.20"):
            refs.append(AnalyticsReference(owner, "NOT_APPLICABLE", None, None,
                "Explicit compatible portfolio/universe definition was not supplied."))
        if any(r.status == "MISSING" for r in refs):
            raise ValueError("canonical analytics dependency failed closed: " + ",".join(r.owner for r in refs if r.status == "MISSING"))
        counts = count.snapshot
        lineage = _hash("phase5b-lineage-v1", self.run.id, state.id, state.equity_ledger.id,
                        *(t.id for t in trades), *(r.record_id or r.status for r in refs))
        rid = _hash("phase5b-result-v1", lineage, now, c.id)
        return BacktestResult(rid, self.run.id, self.run.dataset_id, self.run.dataset_fingerprint,
            self.run.trading_brain_contract_version, self.run.strategy_configuration_version,
            self.run.model_configuration_version, self.run.replay_start_inclusive,
            self.run.replay_end_exclusive, as_of, self.run.starting_equity,
            state.equity_ledger.latest.equity, counts.trade_count, counts.win_count,
            counts.loss_count, counts.breakeven_count, tuple(refs), lineage, "COMPLETE",
            "PAPER_SIMULATION", False, True, self.run.risk_reward_policy_id,
            self.run.performance_objective_id)

    def checkpoint(self, *, state: TradeSimulationState, result: BacktestResult) -> AnalyticsCheckpoint:
        if result.run_id != state.run_id or state.equity_ledger is None:
            raise ValueError("analytics checkpoint identity mismatch")
        cursor = state.accounting_history.records[-1].id if state.accounting_history.records else None
        ident = _hash("phase5b-checkpoint-v1", state.id, cursor or "NONE",
                      state.equity_ledger.latest.id, result.id)
        return AnalyticsCheckpoint(ident, state.run_id, state.id, cursor,
                                   state.equity_ledger.latest.id, result.id, result.as_of)

    def validate_resume(self, *, state: TradeSimulationState, result: BacktestResult,
                        checkpoint: AnalyticsCheckpoint) -> None:
        if checkpoint != self.checkpoint(state=state, result=result):
            raise ValueError("analytics checkpoint or result mismatch")
