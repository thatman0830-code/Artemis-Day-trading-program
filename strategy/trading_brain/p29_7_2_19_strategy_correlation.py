from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodType
from strategy.trading_brain.p29_7_2_15_strategy_aggregation import StrategyPeriodReturnObservation


class CorrelationStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    UNDEFINED_CONSTANT_SERIES = "UNDEFINED_CONSTANT_SERIES"


class CorrelationClassification(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    ZERO = "ZERO"


@dataclass(frozen=True)
class CorrelationScope:
    id: str
    strategy_a_id: str
    strategy_b_id: str
    symbol_a: str
    symbol_b: str
    timeframe_a: str
    timeframe_b: str
    setup_model_a: object
    setup_model_b: object
    direction_a: object
    direction_b: object
    period_type: PeriodType
    account_timezone: str
    source_version: str
    strategy_calculation_version: str
    calculation_version: str
    historical_version: str
    immutable: bool = True


@dataclass(frozen=True)
class AlignedReturnPair:
    id: str
    sequence: int
    period_start: int
    period_end: int
    net_r_a: Decimal
    net_r_b: Decimal
    observation_a_id: str
    observation_b_id: str
    period_a_id: str
    period_b_id: str
    source_period_snapshot_a_id: str
    source_period_snapshot_b_id: str
    immutable: bool = True


@dataclass(frozen=True)
class StrategyCorrelation:
    id: str
    scope_id: str
    strategy_a_id: str
    strategy_b_id: str
    symbol_a: str
    symbol_b: str
    timeframe_a: str
    timeframe_b: str
    setup_model_a: object
    setup_model_b: object
    direction_a: object
    direction_b: object
    analysis_period: PeriodType
    account_timezone: str
    source_version: str
    strategy_calculation_version: str
    calculation_version: str
    historical_version: str
    observation_start: int | None
    observation_end: int | None
    sample_size: int
    mean_a: Decimal | None
    mean_b: Decimal | None
    covariance: Decimal | None
    variance_a: Decimal | None
    variance_b: Decimal | None
    standard_deviation_a: Decimal | None
    standard_deviation_b: Decimal | None
    correlation: Decimal | None
    classification: CorrelationClassification | None
    status: CorrelationStatus
    aligned_pairs: tuple[AlignedReturnPair, ...]
    source_observation_a_ids: tuple[str, ...]
    source_observation_b_ids: tuple[str, ...]
    source_period_end_ids: tuple[int, ...]
    missing_period_end_ids_a: tuple[int, ...]
    missing_period_end_ids_b: tuple[int, ...]
    future_excluded_observation_ids: tuple[str, ...]
    created_time: int
    finalized_time: int
    active: bool
    historical: bool
    immutable: bool = True


@dataclass(frozen=True)
class CorrelationError:
    id: str
    code: AnalyticsErrorCode
    reason: str
    scope_id: str | None
    as_of_time: int
    immutable: bool = True


@dataclass(frozen=True)
class CorrelationHistory:
    records: tuple[StrategyCorrelation, ...] = ()


@dataclass(frozen=True)
class CorrelationResult:
    record: StrategyCorrelation | None
    error: CorrelationError | None
    history: CorrelationHistory

    @property
    def valid(self) -> bool:
        return self.record is not None and self.error is None


class StrategyCorrelationEngine:
    """Canonical #29.7.2.19 pairwise period-net-R Pearson correlation."""

    @staticmethod
    def _uid(kind: str, *parts: object) -> str:
        return str(uuid5(NAMESPACE_URL, "trading-brain:#29.7.2.19:" + kind + ":" + ":".join(map(str, parts))))

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
        error = CorrelationError(self._uid("error", scope_id or "NONE", code.value, reason, as_of), code, reason, scope_id, as_of)
        return CorrelationResult(None, error, history)

    def calculate(self, *, scope: CorrelationScope | None,
                  observations: tuple[StrategyPeriodReturnObservation, ...] | None,
                  as_of_time: int, history: CorrelationHistory = CorrelationHistory()) -> CorrelationResult:
        as_of = int(as_of_time)
        if scope is None or observations is None:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "REQUIRED_CORRELATION_INPUT_MISSING", scope, as_of, history)
        reason = self._validate_scope(scope, as_of)
        if reason:
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        ids = tuple(item.id for item in observations)
        canonical_keys = tuple((item.strategy_id, item.period_end, item.source_version) for item in observations)
        if len(ids) != len(set(ids)) or len(canonical_keys) != len(set(canonical_keys)):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "DUPLICATE_STRATEGY_PERIOD_OBSERVATION", scope, as_of, history)
        if observations != tuple(sorted(observations, key=lambda item: (item.period_end, item.strategy_id, item.id))):
            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "CORRELATION_OBSERVATION_ORDER_INVALID", scope, as_of, history)
        for item in observations:
            reason = self._validate_observation(scope, item)
            if reason:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, reason, scope, as_of, history)
        eligible = tuple(item for item in observations if item.period_end <= as_of and item.finalized_time <= as_of)
        future = tuple(item.id for item in observations if item not in eligible)
        by_strategy = {
            strategy_id: {item.period_end: item for item in eligible if item.strategy_id == strategy_id}
            for strategy_id in (scope.strategy_a_id, scope.strategy_b_id)
        }
        ends_a = set(by_strategy[scope.strategy_a_id])
        ends_b = set(by_strategy[scope.strategy_b_id])
        common = tuple(sorted(ends_a & ends_b))
        pairs = []
        for sequence, period_end in enumerate(common, start=1):
            a = by_strategy[scope.strategy_a_id][period_end]
            b = by_strategy[scope.strategy_b_id][period_end]
            if (a.period_start, a.period_end, a.period_type, a.account_timezone) != (b.period_start, b.period_end, b.period_type, b.account_timezone):
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "CORRELATION_PERIOD_ALIGNMENT_INVALID", scope, as_of, history)
            try:
                value_a = self._decimal(a.net_r); value_b = self._decimal(b.net_r)
            except ValueError:
                return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "NON_FINITE_CORRELATION_INPUT", scope, as_of, history)
            pairs.append(AlignedReturnPair(
                self._uid("pair", scope.id, period_end, a.id, b.id), sequence, a.period_start, period_end,
                value_a, value_b, a.id, b.id, a.period_id, b.period_id,
                a.source_period_snapshot_id, b.source_period_snapshot_id,
            ))
        aligned = tuple(pairs)
        sample_size = len(aligned)
        mean_a = mean_b = covariance = variance_a = variance_b = std_a = std_b = correlation = None
        classification = None
        status = CorrelationStatus.INSUFFICIENT_SAMPLE
        if sample_size:
            with localcontext() as context:
                context.prec = 50
                denominator_n = Decimal(sample_size)
                mean_a = sum((row.net_r_a for row in aligned), Decimal(0)) / denominator_n
                mean_b = sum((row.net_r_b for row in aligned), Decimal(0)) / denominator_n
                if sample_size >= 2:
                    denominator_sample = Decimal(sample_size - 1)
                    centered_cross = sum(((row.net_r_a - mean_a) * (row.net_r_b - mean_b) for row in aligned), Decimal(0))
                    centered_a = sum(((row.net_r_a - mean_a) ** 2 for row in aligned), Decimal(0))
                    centered_b = sum(((row.net_r_b - mean_b) ** 2 for row in aligned), Decimal(0))
                    covariance = centered_cross / denominator_sample
                    variance_a = centered_a / denominator_sample
                    variance_b = centered_b / denominator_sample
                    std_a = variance_a.sqrt(); std_b = variance_b.sqrt()
                    if variance_a == 0 or variance_b == 0:
                        status = CorrelationStatus.UNDEFINED_CONSTANT_SERIES
                    else:
                        correlation = centered_cross / (centered_a * centered_b).sqrt()
                        if correlation > 1 and correlation - 1 < Decimal("1e-45"):
                            correlation = Decimal(1)
                        elif correlation < -1 and -1 - correlation < Decimal("1e-45"):
                            correlation = Decimal(-1)
                        if correlation < -1 or correlation > 1:
                            return self._invalid(AnalyticsErrorCode.PERFORMANCE_DATA_INVALID, "CORRELATION_RANGE_INVARIANT_FAILED", scope, as_of, history)
                        status = CorrelationStatus.VALID
                        classification = CorrelationClassification.POSITIVE if correlation > 0 else CorrelationClassification.NEGATIVE if correlation < 0 else CorrelationClassification.ZERO
        source_a = tuple(row.observation_a_id for row in aligned)
        source_b = tuple(row.observation_b_id for row in aligned)
        record_id = self._uid("record", scope.id, scope.strategy_a_id, scope.strategy_b_id, as_of, scope.calculation_version, *source_a, *source_b)
        exact = next((item for item in history.records if item.id == record_id), None)
        if exact:
            return CorrelationResult(exact, None, history)
        if any((item.scope_id, item.strategy_a_id, item.strategy_b_id, item.as_of_time if hasattr(item, "as_of_time") else item.finalized_time,
                item.source_version, item.calculation_version, item.historical_version) ==
               (scope.id, scope.strategy_a_id, scope.strategy_b_id, as_of, scope.source_version, scope.calculation_version, scope.historical_version)
               for item in history.records):
            return self._invalid(AnalyticsErrorCode.DATA_INTEGRITY_ERROR, "CONFLICTING_CORRELATION_RECORD", scope, as_of, history)
        record = StrategyCorrelation(
            record_id, scope.id, scope.strategy_a_id, scope.strategy_b_id, scope.symbol_a, scope.symbol_b,
            scope.timeframe_a, scope.timeframe_b, scope.setup_model_a, scope.setup_model_b,
            scope.direction_a, scope.direction_b, scope.period_type, scope.account_timezone,
            scope.source_version, scope.strategy_calculation_version, scope.calculation_version,
            scope.historical_version, aligned[0].period_start if aligned else None,
            aligned[-1].period_end if aligned else None, sample_size, mean_a, mean_b, covariance,
            variance_a, variance_b, std_a, std_b, correlation, classification, status, aligned,
            source_a, source_b, common, tuple(sorted(ends_b - ends_a)), tuple(sorted(ends_a - ends_b)),
            future, as_of, as_of, False, True,
        )
        return CorrelationResult(record, None, CorrelationHistory(history.records + (record,)))

    @staticmethod
    def _validate_scope(scope, as_of):
        if not scope.immutable or as_of < 0 or scope.period_type not in tuple(PeriodType):
            return "CORRELATION_SCOPE_INVALID"
        if scope.strategy_a_id >= scope.strategy_b_id:
            return "CORRELATION_PAIR_ORDER_INVALID"
        identity = (
            scope.id, scope.strategy_a_id, scope.strategy_b_id, scope.symbol_a, scope.symbol_b,
            scope.timeframe_a, scope.timeframe_b, scope.account_timezone, scope.source_version,
            scope.strategy_calculation_version, scope.calculation_version, scope.historical_version,
        )
        if not all(str(value).strip() for value in identity):
            return "CORRELATION_SCOPE_IDENTITY_MISSING"
        return None

    def _validate_observation(self, scope, item):
        if not item.immutable or not item.finalized:
            return "NON_FINAL_PERIOD_RETURN_OBSERVATION"
        if item.strategy_id not in (scope.strategy_a_id, scope.strategy_b_id):
            return "CORRELATION_STRATEGY_PAIR_MISMATCH"
        expected = (
            (scope.symbol_a, scope.timeframe_a, scope.setup_model_a, scope.direction_a)
            if item.strategy_id == scope.strategy_a_id else
            (scope.symbol_b, scope.timeframe_b, scope.setup_model_b, scope.direction_b)
        )
        if (item.symbol, item.timeframe, item.setup_model, item.direction) != expected:
            return "CORRELATION_SERIES_SCOPE_MISMATCH"
        if (item.period_type, item.account_timezone, item.source_version, item.calculation_version, item.historical_version) != (
            scope.period_type, scope.account_timezone, scope.source_version,
            scope.strategy_calculation_version, scope.historical_version,
        ):
            return "CORRELATION_PERIOD_OR_VERSION_MISMATCH"
        if item.period_start < 0 or item.period_end <= item.period_start or item.finalized_time < item.period_end:
            return "CORRELATION_PERIOD_CHRONOLOGY_INVALID"
        if not all(str(value).strip() for value in (item.id, item.period_id, item.source_period_snapshot_id)):
            return "CORRELATION_OBSERVATION_IDENTITY_MISSING"
        try:
            self._decimal(item.net_r)
        except ValueError:
            return "NON_FINITE_CORRELATION_INPUT"
        return None
