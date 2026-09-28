from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.owner_policies import OWNER_WIN_RATE_OBJECTIVE_ID
from strategy.trading_brain.p29_7_2_1_trade_classification_count import TradeClassificationCount
from strategy.trading_brain.p29_7_2_3_expectancy import ExpectancySnapshot


class PerformanceObjectiveOutcome(str, Enum):
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    OBJECTIVE_NOT_MET = "OBJECTIVE_NOT_MET"
    OBJECTIVE_MET = "OBJECTIVE_MET"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class PerformanceObjective:
    id: str = OWNER_WIN_RATE_OBJECTIVE_ID
    version: str = "1"
    target_win_rate: Decimal = Decimal("0.60")
    minimum_sample: int = 200
    required_markets: tuple[str, ...] = ("BTC", "ES", "NQ")
    immutable: bool = True


OWNER_WIN_RATE_OBJECTIVE_V1 = PerformanceObjective()


@dataclass(frozen=True)
class PerformanceReadinessSnapshot:
    id: str
    objective_id: str
    objective_version: str
    outcome: PerformanceObjectiveOutcome
    reason: str
    market: str
    scope_id: str
    dataset_id: str
    period_id: str
    sample_type: str
    as_of_time: int
    sample_size: int
    wins: int
    losses: int
    breakevens: int
    win_rate: Decimal | None
    target_win_rate: Decimal
    minimum_sample: int
    net_expectancy: Decimal | None
    source_count_id: str
    source_expectancy_id: str
    source_trade_ids: tuple[str, ...]
    input_version: str
    calculation_version: str
    eligible_for_live_pilot_review: bool
    live_trading_authorized: bool = False
    immutable: bool = True


@dataclass(frozen=True)
class PerformanceReadinessHistory:
    snapshots: tuple[PerformanceReadinessSnapshot, ...] = ()


@dataclass(frozen=True)
class PerformanceReadinessResult:
    snapshot: PerformanceReadinessSnapshot
    history: PerformanceReadinessHistory


class PerformanceReadinessEngine:
    """Owner governance only; consumes analytics and has no trading authority."""

    @staticmethod
    def _uid(*parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:owner-readiness:" + ":".join(map(str, parts))))

    def evaluate(
        self, *, count: TradeClassificationCount | None,
        expectancy: ExpectancySnapshot | None, dataset_id: str,
        period_id: str, as_of_time: int,
        sample_type: str = "OUT_OF_SAMPLE",
        objective: PerformanceObjective = OWNER_WIN_RATE_OBJECTIVE_V1,
        history: PerformanceReadinessHistory = PerformanceReadinessHistory(),
    ) -> PerformanceReadinessResult:
        invalid = self._invalid_reason(count, expectancy, dataset_id, period_id, as_of_time, sample_type, objective)
        if invalid:
            market = count.symbol if count is not None else "INVALID"
            return self._emit(count, expectancy, dataset_id, period_id, as_of_time,
                              objective, PerformanceObjectiveOutcome.INVALID_INPUT,
                              invalid, market, sample_type, history)
        assert count is not None and expectancy is not None
        win_rate = Decimal(count.win_count) / Decimal(count.trade_count) if count.trade_count else None
        if count.trade_count < objective.minimum_sample:
            outcome, reason = PerformanceObjectiveOutcome.INSUFFICIENT_SAMPLE, "FINALIZED_OUT_OF_SAMPLE_TRADE_COUNT_BELOW_200"
        elif win_rate is None or expectancy.expectancy_net_pnl is None:
            outcome, reason = PerformanceObjectiveOutcome.INVALID_INPUT, "CANONICAL_ANALYTICS_RESULT_UNDEFINED"
        elif win_rate < objective.target_win_rate:
            outcome, reason = PerformanceObjectiveOutcome.OBJECTIVE_NOT_MET, "WIN_RATE_BELOW_OBJECTIVE"
        elif expectancy.expectancy_net_pnl <= 0:
            outcome, reason = PerformanceObjectiveOutcome.OBJECTIVE_NOT_MET, "NET_EXPECTANCY_NOT_POSITIVE"
        else:
            outcome, reason = PerformanceObjectiveOutcome.OBJECTIVE_MET, "WIN_RATE_AND_NET_EXPECTANCY_OBJECTIVES_MET"
        return self._emit(count, expectancy, dataset_id, period_id, as_of_time,
                          objective, outcome, reason, count.symbol, sample_type, history)

    def _emit(self, count, expectancy, dataset_id, period_id, as_of, objective,
              outcome, reason, market, sample_type, history):
        count_id = count.id if count else "NONE"
        expectancy_id = expectancy.id if expectancy else "NONE"
        ident = self._uid(objective.id, objective.version, count_id, expectancy_id,
                          dataset_id, period_id, sample_type, as_of)
        exact = next((item for item in history.snapshots if item.id == ident), None)
        if exact:
            return PerformanceReadinessResult(exact, history)
        key = (objective.id, market, dataset_id, period_id, int(as_of))
        if any((item.objective_id, item.market, item.dataset_id, item.period_id,
                item.as_of_time) == key for item in history.snapshots):
            # Conflicting reuse is represented as an immutable invalid snapshot.
            outcome, reason = PerformanceObjectiveOutcome.INVALID_INPUT, "CONFLICTING_OBJECTIVE_SNAPSHOT"
            ident = self._uid(*key, count_id, expectancy_id, reason)
        sample = count.trade_count if count else 0
        win_rate = Decimal(count.win_count) / Decimal(sample) if count and sample else None
        snapshot = PerformanceReadinessSnapshot(
            ident, objective.id, objective.version, outcome, reason, market,
            count.scope_id if count else "NONE", dataset_id, period_id, sample_type, int(as_of),
            sample, count.win_count if count else 0, count.loss_count if count else 0,
            count.breakeven_count if count else 0, win_rate, objective.target_win_rate,
            objective.minimum_sample, expectancy.expectancy_net_pnl if expectancy else None,
            count_id, expectancy_id, count.source_trade_ids if count else (),
            count.input_version if count else "NONE",
            count.calculation_version if count else "NONE",
            outcome == PerformanceObjectiveOutcome.OBJECTIVE_MET, False,
        )
        return PerformanceReadinessResult(snapshot,
            PerformanceReadinessHistory(history.snapshots + (snapshot,)))

    @staticmethod
    def _invalid_reason(count, expectancy, dataset_id, period_id, as_of, sample_type, objective):
        if count is None or expectancy is None:
            return "REQUIRED_FINALIZED_ANALYTICS_MISSING"
        if not dataset_id.strip() or not period_id.strip() or int(as_of) < 0:
            return "OBJECTIVE_LINEAGE_INVALID"
        if sample_type != "OUT_OF_SAMPLE":
            return "FINALIZED_OUT_OF_SAMPLE_SCOPE_REQUIRED"
        if count.symbol not in objective.required_markets:
            return "MARKET_NOT_IN_OBJECTIVE_SCOPE"
        if count.as_of_time != expectancy.as_of_time or count.as_of_time != int(as_of):
            return "ANALYTICS_POINT_IN_TIME_MISMATCH"
        if (count.scope_id, count.strategy_id, count.symbol, count.timeframe,
                count.setup_model, count.direction, count.input_version,
                count.calculation_version) != (
                expectancy.scope_id, expectancy.strategy_id, expectancy.symbol,
                expectancy.timeframe, expectancy.setup_model, expectancy.direction,
                expectancy.input_version, expectancy.calculation_version):
            return "ANALYTICS_SCOPE_OR_VERSION_MISMATCH"
        if count.trade_count != expectancy.trade_count:
            return "ANALYTICS_DENOMINATOR_MISMATCH"
        if count.source_trade_ids != expectancy.source_trade_ids:
            return "ANALYTICS_SOURCE_LINEAGE_MISMATCH"
        if count.trade_count != count.win_count + count.loss_count + count.breakeven_count:
            return "CANONICAL_CLASSIFICATION_COUNT_INVALID"
        if not count.immutable or not expectancy.immutable or not objective.immutable:
            return "NON_FINAL_OR_MUTABLE_ANALYTICS_INPUT"
        return None
