from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest

from .reporting_validation import *
from .specifications import canonical_json_bytes

UTC=timezone.utc; T=datetime(2026,1,1,tzinfo=UTC)
def H(x): return __import__('hashlib').sha256(x.encode()).hexdigest()
def D(x): return Decimal(x)

def trade(i=0, *, market="ES", partition=EvidencePartition.UNTOUCHED_OOS, net=D("8"),
          gross=D("10"), funding=D("0"), rr=D("2"), run=H("run"), strategy="s1"):
    costs=D("2")
    return FinalizedTradeV2.create(run_id=run, market=market, instrument_id=market,
        contract_id=market+"M6", opened_at=T+timedelta(hours=i*2), closed_at=T+timedelta(hours=i*2+1),
        partition=partition, strategy_version=strategy, accounting_version="a1", quantity=D("1"),
        planned_risk=D("1"), planned_reward=rr, gross_pnl=gross, commission=D(".5"), fees=D(".5"),
        slippage=D("1"), funding=funding, settlement_cost=D("0"), rollover_friction=D("0"),
        infrastructure_cost=D("0"), net_pnl=net, entry_notional=D("100"), exit_notional=D("110"),
        source_ids=(H("source"+str(i)),))

def recon(unresolved=()):
    return reconcile(ReconciliationInputV2(H("run"),*(H(str(i)) for i in range(8)),unresolved))

def metrics(ts, partition=EvidencePartition.UNTOUCHED_OOS):
    return calculate_metrics(trades=tuple(ts),run_id=H("run"),market="ES",partition=partition,as_of=T+timedelta(days=30))

def test_trade_cost_reconciliation_and_signed_funding():
    t=trade(funding=D("1"),gross=D("10"),net=D("9")); assert t.net_pnl==D("9")
def test_trade_cost_mismatch_fails_closed():
    with pytest.raises(Phase7Error,match="COST_RECONCILIATION"): trade(net=D("9"))
def test_trade_decimal_only():
    with pytest.raises(ValueError): trade(net=8.0)
def test_trade_is_immutable_and_deterministic():
    a=trade(); b=trade(); assert a==b
    with pytest.raises(FrozenInstanceError): a.net_pnl=D("0")
def test_trade_chronology():
    t=trade();
    with pytest.raises(ValueError): replace(t,closed_at=t.opened_at)

def test_reconciliation_complete_and_deterministic():
    assert recon()==recon() and recon().complete
def test_reconciliation_unresolved_fails_completion():
    r=recon((H("open-roll"),)); assert not r.complete and r.reason is Phase7Reason.UNRESOLVED_UPSTREAM_STATE
def test_reconciliation_duplicate_lineage_rejected():
    h=H("same")
    with pytest.raises(Phase7Error): reconcile(ReconciliationInputV2(H("run"),*(h for _ in range(8))))

def test_metrics_normal_results_and_costs():
    m=metrics((trade(0),trade(1,net=D("-4"),gross=D("-2"))))
    assert (m.trade_count,m.wins,m.losses,m.net_pnl,m.total_cost)==(2,1,1,D("4"),D("4"))
    assert m.expectancy==D("2") and m.profit_factor==D("2")
def test_metrics_empty_has_null_semantics():
    m=metrics(()); assert m.expectancy is None and m.profit_factor is None and m.tail_loss is None
def test_metrics_single_trade_sharpe_sortino_null():
    m=metrics((trade(),)); assert m.sharpe is None and m.sortino is None
def test_metrics_zero_variance_null_sharpe():
    assert metrics((trade(0),trade(1))).sharpe is None
def test_metrics_drawdown_tail_and_recovery():
    m=metrics((trade(0),trade(1,net=D("-10"),gross=D("-8")),trade(2,net=D("12"),gross=D("14"))))
    assert m.maximum_drawdown==D("10") and m.tail_loss==D("-10") and m.recovery_trades==1
def test_metrics_scope_partition_isolation():
    with pytest.raises(Phase7Error,match="IDENTITY_MISMATCH"): metrics((trade(partition=EvidencePartition.TRAINING),))
def test_metrics_no_lookahead():
    with pytest.raises(Phase7Error,match="LOOKAHEAD"): calculate_metrics(trades=(trade(),),run_id=H("run"),market="ES",partition=EvidencePartition.UNTOUCHED_OOS,as_of=T)
def test_metrics_duplicate_rejected():
    t=trade();
    with pytest.raises(Phase7Error,match="DUPLICATE"): metrics((t,t))
def test_metrics_ordering_and_replay_byte_stable():
    a=metrics((trade(1),trade(0))); b=metrics((trade(0),trade(1)))
    assert canonical_json_bytes(a)==canonical_json_bytes(b)
def test_market_isolation():
    with pytest.raises(Phase7Error): metrics((trade(market="NQ"),))
def test_strategy_and_accounting_versions_cannot_mix():
    a=trade(0); b=trade(1,strategy="s2")
    with pytest.raises(Phase7Error,match="VERSION_MISMATCH"): metrics((a,b))

def test_regime_label_point_in_time():
    r=RegimeLabelV2.create(market="ES",instrument_id="ES",effective_from=T,effective_to=T+timedelta(days=1),known_at=T,
        volatility="HIGH",trend="UP",liquidity="NORMAL",session="RTH",label_version="r1",source_ids=(H("x"),))
    assert r.known_at==r.effective_from
def test_regime_label_lookahead_rejected():
    with pytest.raises(Phase7Error,match="LOOKAHEAD"):
        RegimeLabelV2.create(market="ES",instrument_id="ES",effective_from=T,effective_to=T+timedelta(days=1),known_at=T+timedelta(seconds=1),volatility="H",trend="U",liquidity="N",session="R",label_version="r",source_ids=(H("x"),))
def test_regime_segmentation_preserves_trade_identity():
    label=RegimeLabelV2.create(market="ES",instrument_id="ES",effective_from=T,effective_to=T+timedelta(days=1),known_at=T,
        volatility="HIGH",trend="UP",liquidity="NORMAL",session="RTH",label_version="r1",source_ids=(H("x"),))
    t=trade(); assert segment_trades_by_regime(trades=(t,),labels=(label,))==((label.label_id,(t.trade_id,)),)
def test_regime_segmentation_missing_or_overlap_fails_closed():
    with pytest.raises(Phase7Error,match="MISSING_REGIME_LABEL"): segment_trades_by_regime(trades=(trade(),),labels=())
def test_partition_registry_relabeling_rejected():
    with pytest.raises(Phase7Error,match="BLENDED_EVIDENCE"):
        validate_evidence_partitions((trade(0,partition=EvidencePartition.TRAINING),trade(0,partition=EvidencePartition.UNTOUCHED_OOS)))
def test_partition_registry_overlap_rejected():
    a=trade(0,partition=EvidencePartition.TRAINING); b=trade(0,partition=EvidencePartition.VALIDATION)
    b=FinalizedTradeV2.create(run_id=b.run_id,market=b.market,instrument_id=b.instrument_id,contract_id=b.contract_id,
        opened_at=b.opened_at,closed_at=b.closed_at,partition=b.partition,strategy_version=b.strategy_version,
        accounting_version=b.accounting_version,quantity=b.quantity,planned_risk=b.planned_risk,planned_reward=b.planned_reward,
        gross_pnl=b.gross_pnl,commission=b.commission,fees=b.fees,slippage=b.slippage,funding=b.funding,
        settlement_cost=b.settlement_cost,rollover_friction=b.rollover_friction,infrastructure_cost=b.infrastructure_cost,
        net_pnl=b.net_pnl,entry_notional=b.entry_notional,exit_notional=b.exit_notional,source_ids=(H("distinct"),))
    with pytest.raises(Phase7Error,match="BLENDED_EVIDENCE"): validate_evidence_partitions((a,b))
def test_partition_registry_accepts_chronological_boundaries():
    validate_evidence_partitions((trade(0,partition=EvidencePartition.TRAINING),trade(1,partition=EvidencePartition.VALIDATION)))

@pytest.mark.parametrize("kind",list(StressKind))
def test_all_stress_kinds_deterministic(kind):
    s=StressScenarioV2.create(kind=kind,loss_multiplier=D(".25"),additional_cost_per_trade=D("1"),cluster_size=1,ruin_floor=D("0"),scenario_version="v1")
    assert run_stress(trades=(trade(),),scenario=s,starting_capital=D("100"))==run_stress(trades=(trade(),),scenario=s,starting_capital=D("100"))
def test_stress_clustered_loss_and_ruin():
    s=StressScenarioV2.create(kind=StressKind.CLUSTERED_LOSS,loss_multiplier=D("2"),additional_cost_per_trade=D("20"),cluster_size=2,ruin_floor=D("90"),scenario_version="v1")
    r=run_stress(trades=(trade(),trade(1)),scenario=s,starting_capital=D("100")); assert r.ruin_observed
def test_stress_no_float():
    with pytest.raises(ValueError): StressScenarioV2.create(kind=StressKind.GAP,loss_multiplier=.2,additional_cost_per_trade=D("0"),cluster_size=1,ruin_floor=D("0"),scenario_version="v")
def test_probability_of_ruin_exact_and_deterministic():
    r=probability_of_ruin(paths=((D("-11"),),(D("1"),D("1"))),starting_capital=D("10"),ruin_floor=D("0"))
    assert r.probability==D("0.5") and r.ruined_paths==1
def test_probability_of_ruin_empty_fails_closed():
    with pytest.raises(Phase7Error,match="EMPTY_SAMPLE"): probability_of_ruin(paths=(),starting_capital=D("10"),ruin_floor=D("0"))

def test_hurdles_by_capital():
    hs=economic_hurdles(metrics((trade(),)),(D("100"),D("1000")),D(".01")); assert hs[0].passed and not hs[1].passed
def test_hurdle_zero_capital_rejects():
    with pytest.raises(ValueError): economic_hurdles(metrics(()),(D("0"),),D("0"))

def test_promotion_pass_at_200_oos_trades():
    ts=tuple(trade(i) for i in range(200)); m=metrics(ts); hs=economic_hurdles(m,(D("1000"),),D("0"))
    d=evaluate_promotion(metrics=m,trades=ts,hurdles=hs,reconciliation=recon()); assert d.outcome is PromotionOutcome.PASS and d.advisory_only
def test_promotion_insufficient_evidence():
    ts=(trade(),); d=evaluate_promotion(metrics=metrics(ts),trades=ts,hurdles=economic_hurdles(metrics(ts),(D("100"),),D("0")),reconciliation=recon())
    assert d.outcome is PromotionOutcome.INSUFFICIENT_EVIDENCE
def test_promotion_rejects_nonpositive_expectancy():
    ts=tuple(trade(i,net=D("-2"),gross=D("0")) for i in range(200)); m=metrics(ts)
    d=evaluate_promotion(metrics=m,trades=ts,hurdles=economic_hurdles(m,(D("100"),),D("-100")),reconciliation=recon()); assert Phase7Reason.NONPOSITIVE_EXPECTANCY in d.reasons
def test_promotion_rejects_rr_below_one():
    ts=tuple(trade(i,rr=D(".9")) for i in range(200)); m=metrics(ts)
    assert Phase7Reason.PLANNED_RR_BELOW_MINIMUM in evaluate_promotion(metrics=m,trades=ts,hurdles=economic_hurdles(m,(D("100"),),D("0")),reconciliation=recon()).reasons
def test_promotion_rejects_unresolved_reconciliation():
    ts=tuple(trade(i) for i in range(200)); m=metrics(ts)
    assert Phase7Reason.UNRESOLVED_UPSTREAM_STATE in evaluate_promotion(metrics=m,trades=ts,hurdles=economic_hurdles(m,(D("100"),),D("0")),reconciliation=recon((H("x"),))).reasons
def test_promotion_prohibits_blended_or_training_headline():
    m=calculate_metrics(trades=(),run_id=H("run"),market="ES",partition=EvidencePartition.TRAINING,as_of=T)
    with pytest.raises(Phase7Error,match="BLENDED"): evaluate_promotion(metrics=m,trades=(),hurdles=(),reconciliation=recon())
def test_promotion_rejects_mismatched_trade_lineage():
    t=trade(); m=metrics((t,))
    with pytest.raises(Phase7Error,match="RECONCILIATION_MISMATCH"): evaluate_promotion(metrics=m,trades=(),hurdles=(),reconciliation=recon())
def test_promotion_floor_cannot_be_lowered():
    t=trade(); m=metrics((t,))
    with pytest.raises(ValueError,match="200-trade"):
        evaluate_promotion(metrics=m,trades=(t,),hurdles=economic_hurdles(m,(D("1"),),D("0")),reconciliation=recon(),minimum_oos_trades=1)
def test_promotion_requires_explicit_stress_and_ruin_when_configured():
    ts=tuple(trade(i) for i in range(200)); m=metrics(ts); h=economic_hurdles(m,(D("1"),),D("0"))
    d=evaluate_promotion(metrics=m,trades=ts,hurdles=h,reconciliation=recon(),
        required_stress_kinds=(StressKind.GAP,),require_ruin=True)
    assert Phase7Reason.MISSING_STRESS_EVIDENCE in d.reasons and Phase7Reason.MISSING_RUIN_EVIDENCE in d.reasons
def test_market_promotion_is_independent():
    es=tuple(trade(i,market="ES") for i in range(200)); em=metrics(es)
    nq=tuple(trade(i,market="NQ") for i in range(200))
    with pytest.raises(Phase7Error,match="RECONCILIATION_MISMATCH"):
        evaluate_promotion(metrics=em,trades=nq,hurdles=economic_hurdles(em,(D("1"),),D("0")),reconciliation=recon())

def test_backtest_result_deterministic_and_tamper_detectable():
    m=metrics((trade(),)); r=BacktestResultV2.create(run_id=H("run"),reconciliation_id=recon().reconciliation_id,
        metric_snapshot_ids=(m.snapshot_id,),stress_result_ids=(),promotion_decision_ids=(),skip_reasons=(SkipReason.NO_SETUP,),reporting_version=PHASE7_VERSION)
    assert r==BacktestResultV2.create(run_id=H("run"),reconciliation_id=recon().reconciliation_id,metric_snapshot_ids=(m.snapshot_id,),stress_result_ids=(),promotion_decision_ids=(),skip_reasons=(SkipReason.NO_SETUP,),reporting_version=PHASE7_VERSION)
    with pytest.raises(ValueError): replace(r,result_id=H("tamper"))
def test_result_duplicate_lineage_rejected():
    h=H("m")
    with pytest.raises(Phase7Error): BacktestResultV2.create(run_id=H("run"),reconciliation_id=H("r"),metric_snapshot_ids=(h,h),stress_result_ids=(),promotion_decision_ids=(),skip_reasons=(),reporting_version=PHASE7_VERSION)
def test_schema_is_machine_readable():
    p=Path(__file__).parent/'schemas'/'reporting-validation-v2.schema.json'; assert json.loads(p.read_text())["$id"]
def test_no_profitability_guarantee_or_authority_fields():
    assert "guarantee" not in BacktestResultV2.__dataclass_fields__
    assert not {"submit","authorize_trade","wallet","credential"}&set(BacktestResultV2.__dataclass_fields__)
