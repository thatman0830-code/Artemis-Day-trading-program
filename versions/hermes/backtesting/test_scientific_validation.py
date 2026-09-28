from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backtesting.scientific_validation import (
    AntiOverfittingAssessment, BootstrapConfiguration, ChronologicalPartition,
    LockedStrategyConfiguration, MultipleTestingRecord,
    ParameterSensitivityObservation, ParameterSensitivityStudy, PartitionRole,
    RegimeKind, RegimeLabelFact, ScientificValidationEngine,
    ValidationOutcome, ValidationPlan, ValidationTradeFact, WalkForwardFold,
    WalkForwardFoldResult,
    bootstrap_intervals,
)
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult


UTC = timezone.utc
BASE = datetime(2026, 1, 1, tzinfo=UTC)


def locked(symbol="BTC"):
    return LockedStrategyConfiguration.create(
        strategy_configuration_id="strategy-v1", model_configuration_id="model-v1",
        trading_brain_contract_version="brain-contract-v1",
        risk_reward_policy_id="OWNER_MIN_RR_V1",
        execution_cost_configuration_id="research-cost-v1",
        dataset_id="btc-dataset", dataset_fingerprint="f" * 64,
        symbol=symbol, source_version="input-v1", calculation_version="calc-v1",
        locked_at=BASE - timedelta(days=1),
    )


def protocol():
    lock = locked()
    boundaries = (BASE, BASE + timedelta(days=30), BASE + timedelta(days=60),
                  BASE + timedelta(days=90))
    parts = tuple(ChronologicalPartition.create(
        role=role, start_inclusive=boundaries[index],
        end_exclusive=boundaries[index + 1], locked_configuration_id=lock.id,
        dataset_fingerprint=lock.dataset_fingerprint,
    ) for index, role in enumerate(PartitionRole))
    folds = (
        WalkForwardFold.create(sequence=0, train_start_inclusive=boundaries[0],
            train_end_exclusive=BASE + timedelta(days=15),
            validation_start_inclusive=BASE + timedelta(days=15),
            validation_end_exclusive=boundaries[1], locked_configuration_id=lock.id),
        WalkForwardFold.create(sequence=1, train_start_inclusive=boundaries[0],
            train_end_exclusive=boundaries[1], validation_start_inclusive=boundaries[1],
            validation_end_exclusive=boundaries[2], locked_configuration_id=lock.id),
    )
    plan = ValidationPlan.create(locked_configuration=lock, partitions=parts,
                                 folds=folds, created_at=BASE)
    return lock, plan


def research_records(lock, plan):
    cutoff = plan.partition(PartitionRole.TEST).start_inclusive
    observations = tuple(ParameterSensitivityObservation.create(
        parameter_name="minimum_rr", owner_rule_id="OWNER_MIN_RR_V1",
        baseline_value=Decimal("1.0"), evaluated_value=value,
        metric_name="NET_EXPECTANCY", metric_value=metric, sample_size=1,
        observation_end_exclusive=cutoff,
        source_trade_ids=(f"validation-{index}",),
    ) for index, (value, metric) in enumerate(((Decimal("0.9"), Decimal("1")),
                                                (Decimal("1.0"), Decimal("2")),
                                                (Decimal("1.1"), Decimal("1.5")))))
    sensitivity = ParameterSensitivityStudy.create(
        locked_configuration_id=lock.id, observations=observations,
        final_test_start=cutoff)
    multiple = MultipleTestingRecord.create(
        family_id="owner-rule-sensitivity-v1",
        hypothesis_ids=tuple(item.id for item in observations))
    fold_results = tuple(WalkForwardFoldResult.create(
        fold=fold, metric_name="NET_EXPECTANCY", train_metric=Decimal("2.0"),
        validation_metric=Decimal("1.8"),
        train_source_trade_ids=(f"fold-{fold.sequence}-train",),
        validation_source_trade_ids=(f"fold-{fold.sequence}-validation",),
        evaluated_at=fold.validation_end_exclusive,
        final_test_start=plan.partition(PartitionRole.TEST).start_inclusive,
    ) for fold in plan.folds)
    anti = AntiOverfittingAssessment.create(
        locked_configuration_id=lock.id, fold_results=fold_results,
        sensitivity_study_id=sensitivity.id,
        multiple_testing_record_id=multiple.id,
        maximum_allowed_degradation=Decimal("0.25"))
    return sensitivity, multiple, anti


def trades(lock, plan, *, count=200, wins=120, planned_rr=Decimal("1.0"),
           pnl_win=Decimal("2"), pnl_loss=Decimal("-1")):
    start = plan.partition(PartitionRole.TEST).start_inclusive
    result = []
    for index in range(count):
        outcome = TradeResult.WIN if index < wins else TradeResult.LOSS
        pnl = pnl_win if outcome is TradeResult.WIN else pnl_loss
        result.append(ValidationTradeFact.create(
            source_accounting_id=f"accounting-{index}", trade_id=f"trade-{index:04d}",
            setup_id=f"setup-{index}", closed_time=start + timedelta(minutes=index),
            trade_result=outcome, net_pnl=pnl,
            net_r=Decimal("2") if outcome is TradeResult.WIN else Decimal("-1"),
            planned_risk_reward=planned_rr, locked_configuration=lock))
    return tuple(result)


def evaluate(sample, lock, plan, *, history=None):
    sensitivity, multiple, anti = research_records(lock, plan)
    regime = RegimeLabelFact.create(
        symbol="BTC", start_inclusive=BASE, end_exclusive=BASE + timedelta(days=1),
        available_at=BASE + timedelta(days=1), regime=RegimeKind.RANGING,
        method_version="descriptive-v1", source_ids=("candle-1",))
    kwargs = dict(locked_configuration=lock, plan=plan, trades=sample,
        regimes=(regime,), sensitivity=sensitivity, multiple_testing=multiple,
        anti_overfitting=anti,
        bootstrap=BootstrapConfiguration.create(resamples=200, seed=17),
        as_of=plan.partition(PartitionRole.TEST).end_exclusive)
    if history is not None:
        kwargs["history"] = history
    return ScientificValidationEngine().evaluate(**kwargs)


def test_locked_identity_partitions_folds_and_immutability():
    lock, plan = protocol()
    assert tuple(x.role for x in plan.partitions) == tuple(PartitionRole)
    assert plan.partition(PartitionRole.TEST).start_inclusive == BASE + timedelta(days=60)
    assert tuple(x.sequence for x in plan.folds) == (0, 1)
    with pytest.raises(FrozenInstanceError):
        lock.symbol = "ES"
    with pytest.raises(ValueError, match="BTC-only"):
        locked("ES")
    with pytest.raises(ValueError, match="contiguous"):
        ValidationPlan.create(locked_configuration=lock,
            partitions=(plan.partitions[0], replace(plan.partitions[1],
                start_inclusive=plan.partitions[1].start_inclusive + timedelta(hours=1)),
                plan.partitions[2]), folds=plan.folds, created_at=BASE)


def test_walk_forward_and_sensitivity_never_use_final_test():
    lock, plan = protocol()
    with pytest.raises(ValueError, match="before validation"):
        WalkForwardFold.create(sequence=0, train_start_inclusive=BASE,
            train_end_exclusive=BASE + timedelta(days=2),
            validation_start_inclusive=BASE + timedelta(days=1),
            validation_end_exclusive=BASE + timedelta(days=3),
            locked_configuration_id=lock.id)
    sensitivity, _, _ = research_records(lock, plan)
    future = replace(sensitivity.observations[0],
        observation_end_exclusive=plan.partition(PartitionRole.TEST).start_inclusive + timedelta(seconds=1))
    with pytest.raises(ValueError, match="final test outcomes"):
        ParameterSensitivityStudy.create(locked_configuration_id=lock.id,
            observations=(future,) + sensitivity.observations[1:],
            final_test_start=plan.partition(PartitionRole.TEST).start_inclusive)
    assert not sensitivity.automatically_apply and sensitivity.advisory_only


def test_multiple_testing_and_anti_overfitting_are_explicit_advisory_facts():
    lock, plan = protocol()
    sensitivity, multiple, anti = research_records(lock, plan)
    assert multiple.adjusted_alpha == Decimal("0.05") / Decimal("3")
    assert anti.stable and anti.advisory_only
    unstable_results = tuple(replace(result, validation_metric=Decimal("1"))
                             for result in (WalkForwardFoldResult.create(
        fold=fold, metric_name="NET_EXPECTANCY", train_metric=Decimal("2"),
        validation_metric=Decimal("1.8"),
        train_source_trade_ids=(f"unstable-{fold.sequence}-train",),
        validation_source_trade_ids=(f"unstable-{fold.sequence}-validation",),
        evaluated_at=fold.validation_end_exclusive,
        final_test_start=plan.partition(PartitionRole.TEST).start_inclusive,
    ) for fold in plan.folds))
    unstable = AntiOverfittingAssessment.create(
        locked_configuration_id=lock.id, fold_results=unstable_results,
        sensitivity_study_id=sensitivity.id,
        multiple_testing_record_id=multiple.id,
        maximum_allowed_degradation=Decimal("0.25"))
    assert not unstable.stable
    with pytest.raises(ValueError):
        MultipleTestingRecord.create(family_id="family", hypothesis_ids=("same", "same"))


def test_deterministic_bootstrap_95_percent_decimal_intervals():
    lock, plan = protocol()
    sample = trades(lock, plan, count=10, wins=6)
    config = BootstrapConfiguration.create(resamples=200, seed=42)
    first = bootstrap_intervals(trades=sample, configuration=config)
    second = bootstrap_intervals(trades=sample, configuration=config)
    assert first == second and {x.metric for x in first} == {"WIN_RATE", "NET_EXPECTANCY", "MEAN_NET_R"}
    assert all(x.confidence_level == Decimal("0.95") and
               isinstance(x.estimate, Decimal) and x.lower <= x.estimate <= x.upper
               for x in first)
    with pytest.raises(TypeError, match="Decimal"):
        BootstrapConfiguration.create(resamples=100, seed=1, confidence_level=0.95)


def test_owner_gate_pass_is_btc_oos_advisory_only_and_idempotent():
    lock, plan = protocol()
    snapshot, history = evaluate(trades(lock, plan), lock, plan)
    assert snapshot.outcome is ValidationOutcome.PASS
    assert snapshot.finalized_out_of_sample_trades == 200
    assert snapshot.win_rate == Decimal("0.60")
    assert snapshot.net_expectancy == Decimal("0.8")
    assert snapshot.minimum_planned_risk_reward == Decimal("1.0")
    assert not snapshot.trading_authorized and not snapshot.strategy_modified
    replay, replay_history = evaluate(trades(lock, plan), lock, plan, history=history)
    assert replay == snapshot and replay_history == history


def test_owner_gate_insufficient_and_each_failure_boundary():
    lock, plan = protocol()
    insufficient, _ = evaluate(trades(lock, plan, count=199, wins=150), lock, plan)
    assert insufficient.outcome is ValidationOutcome.INSUFFICIENT_EVIDENCE
    low_win, _ = evaluate(trades(lock, plan, wins=119), lock, plan)
    assert low_win.outcome is ValidationOutcome.FAIL and "WIN_RATE_BELOW_0_60" in low_win.reasons
    negative, _ = evaluate(trades(lock, plan, wins=120, pnl_win=Decimal("0.5")), lock, plan)
    assert "NET_EXPECTANCY_NOT_POSITIVE_AFTER_MODELED_COSTS" in negative.reasons
    low_rr = list(trades(lock, plan)); low_rr[-1] = ValidationTradeFact.create(
        source_accounting_id="accounting-low-rr", trade_id="trade-9999", setup_id="setup-low",
        closed_time=low_rr[-1].closed_time, trade_result=TradeResult.LOSS,
        net_pnl=Decimal("-1"), net_r=Decimal("-1"),
        planned_risk_reward=Decimal("0.99"), locked_configuration=lock)
    low_rr_result, _ = evaluate(tuple(low_rr), lock, plan)
    assert "ACCEPTED_SETUP_PLANNED_RR_BELOW_1_0" in low_rr_result.reasons


def test_no_lookahead_order_scope_duplicates_and_regimes_fail_closed():
    lock, plan = protocol(); sample = trades(lock, plan)
    with pytest.raises(ValueError, match="not yet complete"):
        sensitivity, multiple, anti = research_records(lock, plan)
        ScientificValidationEngine().evaluate(locked_configuration=lock, plan=plan,
            trades=sample, regimes=(), sensitivity=sensitivity,
            multiple_testing=multiple, anti_overfitting=anti,
            bootstrap=BootstrapConfiguration.create(resamples=100, seed=1),
            as_of=plan.partition(PartitionRole.TEST).end_exclusive - timedelta(seconds=1))
    with pytest.raises(ValueError, match="ordering"):
        evaluate(tuple(reversed(sample)), lock, plan)
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(sample + (sample[-1],), lock, plan)
    wrong = replace(sample[0], symbol="ES")
    with pytest.raises(ValueError, match="scopes"):
        evaluate((wrong,) + sample[1:], lock, plan)
    with pytest.raises(ValueError, match="before its source interval closes"):
        RegimeLabelFact.create(symbol="BTC", start_inclusive=BASE,
            end_exclusive=BASE + timedelta(days=1), available_at=BASE + timedelta(hours=1),
            regime=RegimeKind.TRENDING, method_version="v1", source_ids=("x",))


def test_float_economic_values_and_conflicting_snapshot_fail_closed():
    lock, plan = protocol()
    with pytest.raises(TypeError, match="Decimal"):
        ValidationTradeFact.create(source_accounting_id="a", trade_id="t", setup_id="s",
            closed_time=plan.partition(PartitionRole.TEST).start_inclusive,
            trade_result=TradeResult.WIN, net_pnl=1.0, net_r=Decimal("1"),
            planned_risk_reward=Decimal("1"), locked_configuration=lock)
    snapshot, history = evaluate(trades(lock, plan), lock, plan)
    changed = list(trades(lock, plan)); changed[-1] = ValidationTradeFact.create(
        source_accounting_id="changed", trade_id="trade-9999", setup_id="changed",
        closed_time=changed[-1].closed_time, trade_result=TradeResult.WIN,
        net_pnl=Decimal("3"), net_r=Decimal("3"),
        planned_risk_reward=Decimal("1"), locked_configuration=lock)
    with pytest.raises(ValueError, match="conflicting validation snapshot"):
        evaluate(tuple(changed), lock, plan, history=history)
    assert snapshot.advisory_only
