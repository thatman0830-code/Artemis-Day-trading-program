"""Deterministic advisory scientific validation downstream of finalized BTC facts.

This module owns research protocol records.  It has no strategy, risk,
execution, account, exchange, or trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, localcontext
from enum import Enum
from hashlib import sha256
from random import Random

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeResult


VALIDATION_VERSION = "btc-scientific-validation-v1"


def _hash(*parts: object) -> str:
    return sha256("\x1f".join(map(str, parts)).encode("utf-8")).hexdigest()


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonblank")
    return value


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC timezone-aware")
    return value.astimezone(timezone.utc)


def _decimal(value: Decimal, field: str, *, nonnegative: bool = False) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field} must be Decimal; implicit float conversion is prohibited")
    if not value.is_finite() or (nonnegative and value < 0):
        raise ValueError(f"{field} must be finite" + (" and nonnegative" if nonnegative else ""))
    return value


class ValidationOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PartitionRole(str, Enum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


class RegimeKind(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNCLASSIFIED = "UNCLASSIFIED"


class MultipleTestingMethod(str, Enum):
    BONFERRONI = "BONFERRONI"


@dataclass(frozen=True)
class LockedStrategyConfiguration:
    id: str
    strategy_configuration_id: str
    model_configuration_id: str
    trading_brain_contract_version: str
    risk_reward_policy_id: str
    execution_cost_configuration_id: str
    dataset_id: str
    dataset_fingerprint: str
    symbol: str
    source_version: str
    calculation_version: str
    locked_at: datetime
    immutable: bool = True

    @classmethod
    def create(cls, *, strategy_configuration_id: str, model_configuration_id: str,
               trading_brain_contract_version: str, risk_reward_policy_id: str,
               execution_cost_configuration_id: str, dataset_id: str,
               dataset_fingerprint: str, symbol: str, source_version: str,
               calculation_version: str, locked_at: datetime) -> "LockedStrategyConfiguration":
        values = (strategy_configuration_id, model_configuration_id,
                  trading_brain_contract_version, risk_reward_policy_id,
                  execution_cost_configuration_id, dataset_id, dataset_fingerprint,
                  source_version, calculation_version)
        for value in values:
            _text(value, "configuration identity")
        if symbol != "BTC":
            raise ValueError("scientific validation v1 is BTC-only")
        locked = _utc(locked_at, "locked_at")
        ident = _hash(VALIDATION_VERSION, *values, symbol, locked.isoformat())
        return cls(ident, strategy_configuration_id, model_configuration_id,
                   trading_brain_contract_version, risk_reward_policy_id,
                   execution_cost_configuration_id, dataset_id, dataset_fingerprint,
                   symbol, source_version, calculation_version, locked)


@dataclass(frozen=True)
class ChronologicalPartition:
    id: str
    role: PartitionRole
    start_inclusive: datetime
    end_exclusive: datetime
    locked_configuration_id: str
    dataset_fingerprint: str
    immutable: bool = True

    @classmethod
    def create(cls, *, role: PartitionRole, start_inclusive: datetime,
               end_exclusive: datetime, locked_configuration_id: str,
               dataset_fingerprint: str) -> "ChronologicalPartition":
        if not isinstance(role, PartitionRole):
            raise TypeError("partition role must be canonical")
        start, end = _utc(start_inclusive, "start_inclusive"), _utc(end_exclusive, "end_exclusive")
        if start >= end:
            raise ValueError("partition must be a nonempty [start,end) interval")
        _text(locked_configuration_id, "locked_configuration_id")
        _text(dataset_fingerprint, "dataset_fingerprint")
        ident = _hash(VALIDATION_VERSION, "partition", role.value, start.isoformat(),
                      end.isoformat(), locked_configuration_id, dataset_fingerprint)
        return cls(ident, role, start, end, locked_configuration_id, dataset_fingerprint)

    def contains(self, value: datetime) -> bool:
        point = _utc(value, "partition observation time")
        return self.start_inclusive <= point < self.end_exclusive


@dataclass(frozen=True)
class WalkForwardFold:
    id: str
    sequence: int
    train_start_inclusive: datetime
    train_end_exclusive: datetime
    validation_start_inclusive: datetime
    validation_end_exclusive: datetime
    locked_configuration_id: str
    immutable: bool = True

    @classmethod
    def create(cls, *, sequence: int, train_start_inclusive: datetime,
               train_end_exclusive: datetime, validation_start_inclusive: datetime,
               validation_end_exclusive: datetime,
               locked_configuration_id: str) -> "WalkForwardFold":
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError("fold sequence must be a nonnegative integer")
        ts, te = _utc(train_start_inclusive, "train_start"), _utc(train_end_exclusive, "train_end")
        vs, ve = _utc(validation_start_inclusive, "validation_start"), _utc(validation_end_exclusive, "validation_end")
        if not ts < te <= vs < ve:
            raise ValueError("walk-forward fold must train strictly before validation")
        _text(locked_configuration_id, "locked_configuration_id")
        ident = _hash(VALIDATION_VERSION, "fold", sequence, ts.isoformat(), te.isoformat(),
                      vs.isoformat(), ve.isoformat(), locked_configuration_id)
        return cls(ident, sequence, ts, te, vs, ve, locked_configuration_id)


@dataclass(frozen=True)
class ValidationPlan:
    id: str
    locked_configuration_id: str
    partitions: tuple[ChronologicalPartition, ...]
    folds: tuple[WalkForwardFold, ...]
    created_at: datetime
    immutable: bool = True

    @classmethod
    def create(cls, *, locked_configuration: LockedStrategyConfiguration,
               partitions: tuple[ChronologicalPartition, ...],
               folds: tuple[WalkForwardFold, ...], created_at: datetime) -> "ValidationPlan":
        if not isinstance(partitions, tuple) or tuple(p.role for p in partitions) != tuple(PartitionRole):
            raise ValueError("partitions must be exactly TRAIN, VALIDATION, TEST in order")
        if any((p.locked_configuration_id, p.dataset_fingerprint) !=
               (locked_configuration.id, locked_configuration.dataset_fingerprint) for p in partitions):
            raise ValueError("partition identity is incompatible with locked configuration")
        train, validation, test = partitions
        if train.end_exclusive != validation.start_inclusive or validation.end_exclusive != test.start_inclusive:
            raise ValueError("TRAIN, VALIDATION, and TEST must be contiguous and chronological")
        if not isinstance(folds, tuple) or not folds:
            raise ValueError("at least one immutable walk-forward fold is required")
        if tuple(f.sequence for f in folds) != tuple(range(len(folds))):
            raise ValueError("fold sequence must be contiguous and deterministic")
        for fold in folds:
            if fold.locked_configuration_id != locked_configuration.id:
                raise ValueError("fold configuration mismatch")
            if not (train.start_inclusive <= fold.train_start_inclusive and
                    fold.validation_end_exclusive <= test.start_inclusive):
                raise ValueError("walk-forward folds may use train/validation history only")
        if any(a.validation_end_exclusive > b.validation_start_inclusive for a, b in zip(folds, folds[1:])):
            raise ValueError("walk-forward folds must advance chronologically without overlap")
        created = _utc(created_at, "created_at")
        if not locked_configuration.locked_at <= created <= train.start_inclusive:
            raise ValueError("strategy and validation plan must be locked before evaluation begins")
        ident = _hash(VALIDATION_VERSION, "plan", locked_configuration.id,
                      *(p.id for p in partitions), *(f.id for f in folds), created.isoformat())
        return cls(ident, locked_configuration.id, partitions, folds, created)

    def partition(self, role: PartitionRole) -> ChronologicalPartition:
        return next(item for item in self.partitions if item.role is role)


@dataclass(frozen=True)
class RegimeLabelFact:
    id: str
    symbol: str
    start_inclusive: datetime
    end_exclusive: datetime
    available_at: datetime
    regime: RegimeKind
    method_version: str
    source_ids: tuple[str, ...]
    descriptive_only: bool = True
    immutable: bool = True

    @classmethod
    def create(cls, *, symbol: str, start_inclusive: datetime, end_exclusive: datetime,
               available_at: datetime, regime: RegimeKind, method_version: str,
               source_ids: tuple[str, ...]) -> "RegimeLabelFact":
        if symbol != "BTC" or not isinstance(regime, RegimeKind):
            raise ValueError("regime fact must use BTC and a canonical descriptive label")
        start, end, available = (_utc(start_inclusive, "start_inclusive"),
                                 _utc(end_exclusive, "end_exclusive"),
                                 _utc(available_at, "available_at"))
        if not start < end <= available:
            raise ValueError("regime label cannot be available before its source interval closes")
        _text(method_version, "method_version")
        if not isinstance(source_ids, tuple) or not source_ids or any(not x for x in source_ids):
            raise ValueError("regime source lineage is required")
        ident = _hash(VALIDATION_VERSION, "regime", symbol, start.isoformat(), end.isoformat(),
                      available.isoformat(), regime.value, method_version, *source_ids)
        return cls(ident, symbol, start, end, available, regime, method_version, source_ids)


@dataclass(frozen=True)
class ParameterSensitivityObservation:
    id: str
    parameter_name: str
    owner_rule_id: str
    baseline_value: Decimal
    evaluated_value: Decimal
    metric_name: str
    metric_value: Decimal | None
    sample_size: int
    observation_end_exclusive: datetime
    source_trade_ids: tuple[str, ...]
    immutable: bool = True

    @classmethod
    def create(cls, *, parameter_name: str, owner_rule_id: str,
               baseline_value: Decimal, evaluated_value: Decimal,
               metric_name: str, metric_value: Decimal | None, sample_size: int,
               observation_end_exclusive: datetime,
               source_trade_ids: tuple[str, ...]) -> "ParameterSensitivityObservation":
        for value, name in ((parameter_name, "parameter_name"), (owner_rule_id, "owner_rule_id"),
                            (metric_name, "metric_name")):
            _text(value, name)
        baseline = _decimal(baseline_value, "baseline_value")
        evaluated = _decimal(evaluated_value, "evaluated_value")
        if metric_value is not None:
            _decimal(metric_value, "metric_value")
        if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 0:
            raise ValueError("sample_size must be nonnegative")
        end = _utc(observation_end_exclusive, "observation_end_exclusive")
        if len(source_trade_ids) != sample_size or len(set(source_trade_ids)) != len(source_trade_ids):
            raise ValueError("sensitivity source lineage/sample size mismatch")
        ident = _hash(VALIDATION_VERSION, "sensitivity", parameter_name, owner_rule_id,
                      baseline, evaluated, metric_name, metric_value, sample_size,
                      end.isoformat(), *source_trade_ids)
        return cls(ident, parameter_name, owner_rule_id, baseline, evaluated,
                   metric_name, metric_value, sample_size, end, source_trade_ids)


@dataclass(frozen=True)
class ParameterSensitivityStudy:
    id: str
    locked_configuration_id: str
    observations: tuple[ParameterSensitivityObservation, ...]
    automatically_apply: bool = False
    advisory_only: bool = True
    immutable: bool = True

    @classmethod
    def create(cls, *, locked_configuration_id: str,
               observations: tuple[ParameterSensitivityObservation, ...],
               final_test_start: datetime) -> "ParameterSensitivityStudy":
        _text(locked_configuration_id, "locked_configuration_id")
        cutoff = _utc(final_test_start, "final_test_start")
        if not isinstance(observations, tuple) or not observations:
            raise ValueError("sensitivity observations are required")
        if len({x.id for x in observations}) != len(observations):
            raise ValueError("duplicate sensitivity observations")
        if any(x.observation_end_exclusive > cutoff for x in observations):
            raise ValueError("final test outcomes cannot influence parameter sensitivity")
        groups: dict[tuple[str, str, Decimal], set[Decimal]] = {}
        for item in observations:
            groups.setdefault((item.parameter_name, item.owner_rule_id, item.baseline_value), set()).add(item.evaluated_value)
        if any(baseline not in values or not any(v < baseline for v in values) or
               not any(v > baseline for v in values) for (_, _, baseline), values in groups.items()):
            raise ValueError("sensitivity must include baseline and values on both sides")
        ident = _hash(VALIDATION_VERSION, "sensitivity-study", locked_configuration_id,
                      *(x.id for x in observations))
        return cls(ident, locked_configuration_id, observations)


@dataclass(frozen=True)
class MultipleTestingRecord:
    id: str
    family_id: str
    hypothesis_ids: tuple[str, ...]
    familywise_alpha: Decimal
    adjusted_alpha: Decimal
    method: MultipleTestingMethod
    immutable: bool = True

    @classmethod
    def create(cls, *, family_id: str, hypothesis_ids: tuple[str, ...],
               familywise_alpha: Decimal = Decimal("0.05")) -> "MultipleTestingRecord":
        _text(family_id, "family_id")
        alpha = _decimal(familywise_alpha, "familywise_alpha")
        if alpha <= 0 or alpha > Decimal("0.05"):
            raise ValueError("familywise alpha must be in (0,0.05]")
        if not isinstance(hypothesis_ids, tuple) or not hypothesis_ids or len(set(hypothesis_ids)) != len(hypothesis_ids):
            raise ValueError("unique explicit hypothesis identities are required")
        adjusted = alpha / Decimal(len(hypothesis_ids))
        ident = _hash(VALIDATION_VERSION, "multiple-testing", family_id,
                      *hypothesis_ids, alpha, adjusted, MultipleTestingMethod.BONFERRONI.value)
        return cls(ident, family_id, hypothesis_ids, alpha, adjusted,
                   MultipleTestingMethod.BONFERRONI)


@dataclass(frozen=True)
class WalkForwardFoldResult:
    id: str
    fold_id: str
    metric_name: str
    train_metric: Decimal
    validation_metric: Decimal
    train_source_trade_ids: tuple[str, ...]
    validation_source_trade_ids: tuple[str, ...]
    evaluated_at: datetime
    finalized: bool = True
    immutable: bool = True

    @classmethod
    def create(cls, *, fold: WalkForwardFold, metric_name: str,
               train_metric: Decimal, validation_metric: Decimal,
               train_source_trade_ids: tuple[str, ...],
               validation_source_trade_ids: tuple[str, ...],
               evaluated_at: datetime, final_test_start: datetime) -> "WalkForwardFoldResult":
        _text(metric_name, "metric_name")
        train = _decimal(train_metric, "train_metric")
        validation = _decimal(validation_metric, "validation_metric")
        evaluated, cutoff = _utc(evaluated_at, "evaluated_at"), _utc(final_test_start, "final_test_start")
        if not fold.validation_end_exclusive <= evaluated <= cutoff:
            raise ValueError("fold evaluation must follow validation close and precede final test")
        if (not train_source_trade_ids or not validation_source_trade_ids or
                len(set(train_source_trade_ids)) != len(train_source_trade_ids) or
                len(set(validation_source_trade_ids)) != len(validation_source_trade_ids) or
                set(train_source_trade_ids) & set(validation_source_trade_ids)):
            raise ValueError("walk-forward train/validation lineage must be nonempty, unique, and disjoint")
        ident = _hash(VALIDATION_VERSION, "fold-result", fold.id, metric_name, train,
                      validation, *train_source_trade_ids, "validation",
                      *validation_source_trade_ids, evaluated.isoformat())
        return cls(ident, fold.id, metric_name, train, validation,
                   train_source_trade_ids, validation_source_trade_ids, evaluated)


@dataclass(frozen=True)
class AntiOverfittingAssessment:
    id: str
    locked_configuration_id: str
    fold_ids: tuple[str, ...]
    fold_result_ids: tuple[str, ...]
    sensitivity_study_id: str
    multiple_testing_record_id: str
    train_metric: Decimal
    validation_metric: Decimal
    degradation: Decimal
    stable: bool
    reason: str
    advisory_only: bool = True
    immutable: bool = True

    @classmethod
    def create(cls, *, locked_configuration_id: str,
               fold_results: tuple[WalkForwardFoldResult, ...],
               sensitivity_study_id: str, multiple_testing_record_id: str,
               maximum_allowed_degradation: Decimal) -> "AntiOverfittingAssessment":
        if (not fold_results or len({x.id for x in fold_results}) != len(fold_results) or
                len({x.fold_id for x in fold_results}) != len(fold_results)):
            raise ValueError("one unique finalized result per fold is required")
        if len({x.metric_name for x in fold_results}) != 1 or any(
                not x.finalized or not x.immutable for x in fold_results):
            raise ValueError("fold results must be finalized and use one metric")
        train = _mean(tuple(x.train_metric for x in fold_results))
        validation = _mean(tuple(x.validation_metric for x in fold_results))
        maximum = _decimal(maximum_allowed_degradation, "maximum_allowed_degradation", nonnegative=True)
        degradation = train - validation
        stable = degradation <= maximum
        reason = "WITHIN_LOCKED_DEGRADATION_BOUND" if stable else "VALIDATION_DEGRADATION_EXCEEDS_LOCKED_BOUND"
        ident = _hash(VALIDATION_VERSION, "anti-overfit", locked_configuration_id,
                      *(x.id for x in fold_results), sensitivity_study_id, multiple_testing_record_id,
                      train, validation, maximum, stable)
        return cls(ident, locked_configuration_id,
                   tuple(x.fold_id for x in fold_results),
                   tuple(x.id for x in fold_results), sensitivity_study_id,
                   multiple_testing_record_id, train, validation, degradation,
                   stable, reason)


@dataclass(frozen=True)
class ValidationTradeFact:
    id: str
    source_accounting_id: str
    trade_id: str
    setup_id: str
    symbol: str
    strategy_id: str
    input_version: str
    locked_configuration_id: str
    closed_time: datetime
    trade_result: TradeResult
    net_pnl: Decimal
    net_r: Decimal
    planned_risk_reward: Decimal
    finalized: bool = True
    immutable: bool = True

    @classmethod
    def create(cls, *, source_accounting_id: str, trade_id: str, setup_id: str,
               closed_time: datetime, trade_result: TradeResult, net_pnl: Decimal,
               net_r: Decimal, planned_risk_reward: Decimal,
               locked_configuration: LockedStrategyConfiguration) -> "ValidationTradeFact":
        for value, name in ((source_accounting_id, "source_accounting_id"),
                            (trade_id, "trade_id"), (setup_id, "setup_id")):
            _text(value, name)
        if not isinstance(trade_result, TradeResult):
            raise TypeError("trade_result must remain authoritative canonical accounting output")
        closed = _utc(closed_time, "closed_time")
        pnl = _decimal(net_pnl, "net_pnl")
        realized_r = _decimal(net_r, "net_r")
        planned = _decimal(planned_risk_reward, "planned_risk_reward", nonnegative=True)
        ident = _hash(VALIDATION_VERSION, "trade", source_accounting_id, trade_id,
                      setup_id, locked_configuration.id, closed.isoformat(),
                      trade_result.value, pnl, realized_r, planned)
        return cls(ident, source_accounting_id, trade_id, setup_id, "BTC",
                   locked_configuration.strategy_configuration_id,
                   locked_configuration.source_version, locked_configuration.id,
                   closed, trade_result, pnl, realized_r, planned)

    @classmethod
    def from_accounting(cls, accounting: TradeAccounting, *, planned_risk_reward: Decimal,
                        locked_configuration: LockedStrategyConfiguration) -> "ValidationTradeFact":
        if not isinstance(accounting, TradeAccounting) or not accounting.immutable:
            raise TypeError("immutable canonical #29.7.1 accounting is required")
        planned = _decimal(planned_risk_reward, "planned_risk_reward", nonnegative=True)
        closed = datetime.fromtimestamp(accounting.closed_time / 1000, timezone.utc)
        if (accounting.symbol, accounting.strategy_id, accounting.input_version) != (
                locked_configuration.symbol, locked_configuration.strategy_configuration_id,
                locked_configuration.source_version):
            raise ValueError("accounting and locked strategy scope/version mismatch")
        ident = _hash(VALIDATION_VERSION, "trade", accounting.id,
                      accounting.trade_id, accounting.setup_id, locked_configuration.id,
                      closed.isoformat(), accounting.trade_result.value,
                      accounting.net_pnl, accounting.net_r, planned)
        return cls(ident, accounting.id, accounting.trade_id, accounting.setup_id,
                   accounting.symbol, accounting.strategy_id, accounting.input_version,
                   locked_configuration.id, closed, accounting.trade_result,
                   accounting.net_pnl, accounting.net_r, planned)


@dataclass(frozen=True)
class ConfidenceInterval:
    metric: str
    confidence_level: Decimal
    lower: Decimal
    estimate: Decimal
    upper: Decimal
    method: str
    resamples: int
    seed: int


@dataclass(frozen=True)
class BootstrapConfiguration:
    id: str
    confidence_level: Decimal
    resamples: int
    seed: int
    method_version: str = "PERCENTILE_NEAREST_RANK_V1"
    immutable: bool = True

    @classmethod
    def create(cls, *, resamples: int, seed: int,
               confidence_level: Decimal = Decimal("0.95")) -> "BootstrapConfiguration":
        confidence = _decimal(confidence_level, "confidence_level")
        if confidence != Decimal("0.95"):
            raise ValueError("scientific validation v1 requires 95% confidence intervals")
        if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 100:
            raise ValueError("at least 100 deterministic bootstrap resamples are required")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("bootstrap seed must be an integer")
        ident = _hash(VALIDATION_VERSION, "bootstrap", confidence, resamples, seed,
                      "PERCENTILE_NEAREST_RANK_V1")
        return cls(ident, confidence, resamples, seed)


def _mean(values: tuple[Decimal, ...]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _percentile(values: list[Decimal], probability: Decimal) -> Decimal:
    ordered = sorted(values)
    index = max(0, int((probability * Decimal(len(ordered))).to_integral_value(
        rounding=ROUND_CEILING)) - 1)
    return ordered[index]


def bootstrap_intervals(*, trades: tuple[ValidationTradeFact, ...],
                        configuration: BootstrapConfiguration) -> tuple[ConfidenceInterval, ...]:
    if not trades:
        return ()
    rng = Random(configuration.seed)
    n = len(trades)
    win_samples: list[Decimal] = []
    pnl_samples: list[Decimal] = []
    return_samples: list[Decimal] = []
    with localcontext() as context:
        context.prec = max(context.prec, 28)
        for _ in range(configuration.resamples):
            sample = tuple(trades[rng.randrange(n)] for _ in range(n))
            win_samples.append(Decimal(sum(x.trade_result is TradeResult.WIN for x in sample)) / Decimal(n))
            pnl_samples.append(_mean(tuple(x.net_pnl for x in sample)))
            return_samples.append(_mean(tuple(x.net_r for x in sample)))
    tail = (Decimal("1") - configuration.confidence_level) / Decimal("2")
    estimates = (
        ("WIN_RATE", Decimal(sum(x.trade_result is TradeResult.WIN for x in trades)) / Decimal(n), win_samples),
        ("NET_EXPECTANCY", _mean(tuple(x.net_pnl for x in trades)), pnl_samples),
        ("MEAN_NET_R", _mean(tuple(x.net_r for x in trades)), return_samples),
    )
    return tuple(ConfidenceInterval(metric, configuration.confidence_level,
                    _percentile(samples, tail), estimate,
                    _percentile(samples, Decimal("1") - tail),
                    configuration.method_version, configuration.resamples,
                    configuration.seed) for metric, estimate, samples in estimates)


@dataclass(frozen=True)
class ScientificValidationSnapshot:
    id: str
    locked_configuration_id: str
    validation_plan_id: str
    outcome: ValidationOutcome
    reasons: tuple[str, ...]
    as_of: datetime
    symbol: str
    finalized_out_of_sample_trades: int
    wins: int
    losses: int
    breakevens: int
    win_rate: Decimal | None
    net_expectancy: Decimal | None
    minimum_planned_risk_reward: Decimal | None
    confidence_intervals: tuple[ConfidenceInterval, ...]
    source_trade_ids: tuple[str, ...]
    regime_fact_ids: tuple[str, ...]
    sensitivity_study_id: str
    anti_overfitting_assessment_id: str
    multiple_testing_record_id: str
    advisory_only: bool = True
    trading_authorized: bool = False
    strategy_modified: bool = False
    immutable: bool = True


@dataclass(frozen=True)
class ScientificValidationHistory:
    snapshots: tuple[ScientificValidationSnapshot, ...] = ()


class ScientificValidationEngine:
    """Advisory owner gate.  It cannot feed results into trading behavior."""

    def evaluate(self, *, locked_configuration: LockedStrategyConfiguration,
                 plan: ValidationPlan, trades: tuple[ValidationTradeFact, ...],
                 regimes: tuple[RegimeLabelFact, ...],
                 sensitivity: ParameterSensitivityStudy,
                 multiple_testing: MultipleTestingRecord,
                 anti_overfitting: AntiOverfittingAssessment,
                 bootstrap: BootstrapConfiguration, as_of: datetime,
                 history: ScientificValidationHistory = ScientificValidationHistory(),
                 minimum_trades: int = 200,
                 target_win_rate: Decimal = Decimal("0.60"),
                 minimum_planned_risk_reward: Decimal = Decimal("1.0"),
                 ) -> tuple[ScientificValidationSnapshot, ScientificValidationHistory]:
        now = _utc(as_of, "as_of")
        target = _decimal(target_win_rate, "target_win_rate")
        minimum_rr = _decimal(minimum_planned_risk_reward, "minimum_planned_risk_reward")
        if (minimum_trades, target, minimum_rr) != (200, Decimal("0.60"), Decimal("1.0")):
            raise ValueError("owner objective gate is immutable in validation v1")
        if plan.locked_configuration_id != locked_configuration.id:
            raise ValueError("plan/locked configuration mismatch")
        if any(item.locked_configuration_id != locked_configuration.id for item in (sensitivity, anti_overfitting)):
            raise ValueError("research record/configuration mismatch")
        if anti_overfitting.fold_ids != tuple(f.id for f in plan.folds):
            raise ValueError("anti-overfitting fold lineage mismatch")
        if (anti_overfitting.sensitivity_study_id != sensitivity.id or
                anti_overfitting.multiple_testing_record_id != multiple_testing.id):
            raise ValueError("anti-overfitting dependency mismatch")
        test = plan.partition(PartitionRole.TEST)
        if now < test.end_exclusive:
            raise ValueError("final untouched test interval is not yet complete")
        if len({x.id for x in trades}) != len(trades) or len({x.trade_id for x in trades}) != len(trades):
            raise ValueError("duplicate or conflicting finalized trade facts")
        ordered = tuple(sorted(trades, key=lambda x: (x.closed_time, x.trade_id)))
        if ordered != trades:
            raise ValueError("trades must use closed_time ASC, trade_id ASC ordering")
        if any(not x.finalized or not x.immutable for x in trades):
            raise ValueError("only immutable finalized trades are eligible")
        if any(x.closed_time > now for x in trades):
            raise ValueError("future trades violate point-in-time evaluation")
        if any((x.symbol, x.strategy_id, x.input_version, x.locked_configuration_id) !=
               ("BTC", locked_configuration.strategy_configuration_id,
                locked_configuration.source_version, locked_configuration.id) for x in trades):
            raise ValueError("BTC strategy/version scopes must remain isolated")
        if any(not plan.partitions[0].start_inclusive <= x.closed_time < test.end_exclusive for x in trades):
            raise ValueError("trade lies outside the locked validation horizon")
        if len({x.id for x in regimes}) != len(regimes) or any(
                x.symbol != "BTC" or not x.descriptive_only or x.available_at > now
                for x in regimes):
            raise ValueError("regime facts are invalid, future, or non-descriptive")
        test_trades = tuple(x for x in trades if test.contains(x.closed_time))
        wins = sum(x.trade_result is TradeResult.WIN for x in test_trades)
        losses = sum(x.trade_result is TradeResult.LOSS for x in test_trades)
        breakevens = sum(x.trade_result is TradeResult.BREAKEVEN for x in test_trades)
        count = len(test_trades)
        win_rate = Decimal(wins) / Decimal(count) if count else None
        expectancy = _mean(tuple(x.net_pnl for x in test_trades)) if count else None
        observed_minimum_rr = min((x.planned_risk_reward for x in test_trades), default=None)
        intervals = bootstrap_intervals(trades=test_trades, configuration=bootstrap)
        reasons: list[str] = []
        if count < minimum_trades:
            outcome = ValidationOutcome.INSUFFICIENT_EVIDENCE
            reasons.append("FINALIZED_OUT_OF_SAMPLE_BTC_TRADES_BELOW_200")
        else:
            if win_rate is None or win_rate < target:
                reasons.append("WIN_RATE_BELOW_0_60")
            if expectancy is None or expectancy <= 0:
                reasons.append("NET_EXPECTANCY_NOT_POSITIVE_AFTER_MODELED_COSTS")
            if observed_minimum_rr is None or observed_minimum_rr < minimum_rr:
                reasons.append("ACCEPTED_SETUP_PLANNED_RR_BELOW_1_0")
            outcome = ValidationOutcome.FAIL if reasons else ValidationOutcome.PASS
        source_ids = tuple(x.id for x in test_trades)
        ident = _hash(VALIDATION_VERSION, "snapshot", locked_configuration.id,
                      plan.id, now.isoformat(), outcome.value, *reasons, *source_ids,
                      *(x.id for x in regimes), sensitivity.id, anti_overfitting.id,
                      multiple_testing.id, bootstrap.id)
        exact = next((x for x in history.snapshots if x.id == ident), None)
        if exact is not None:
            return exact, history
        key = (locked_configuration.id, plan.id, now)
        if any((x.locked_configuration_id, x.validation_plan_id, x.as_of) == key
               for x in history.snapshots):
            raise ValueError("conflicting validation snapshot identity")
        snapshot = ScientificValidationSnapshot(
            ident, locked_configuration.id, plan.id, outcome, tuple(reasons), now,
            "BTC", count, wins, losses, breakevens, win_rate, expectancy,
            observed_minimum_rr, intervals, source_ids, tuple(x.id for x in regimes),
            sensitivity.id, anti_overfitting.id, multiple_testing.id,
        )
        return snapshot, ScientificValidationHistory(history.snapshots + (snapshot,))
