from dataclasses import replace, FrozenInstanceError, fields
from datetime import timedelta
from decimal import Decimal

import pytest

from execution.strategy_paper_pretrade_v1 import PaperSizingPolicyV1, PaperPretradeError, plan_strategy_paper_pretrade
from execution.test_strategy_paper_intent_v1 import arguments
from execution.test_paper_performance_ledger_v1 import accounting,T,H
from execution.test_supervised_paper_workflow_v1 import initial
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from backtesting.execution_accounting_v2.accounting import InstrumentAccountingLedgerV2
from backtesting.execution_accounting_v2.risk_sessions import (
    PortfolioRiskContextV2, VerifiedSessionV2, RiskLimitsV2, RISK_POLICY_VERSION,
)

D=Decimal


def setup():
    args=arguments(); args.pop("quantity");args.pop("quantity_evidence_sha256")
    original=accounting()
    book=InstrumentAccountingLedgerV2.create(run_id=original.run_id,starting_cash=original.starting_cash,
        instrument=args["instrument"],policy=original.policy,margin_specification=original.margin_specification)
    args["run_id"]=book.run_id
    gateway=initial().gateway
    perf=PaperPerformanceLedgerV1.create(book,gateway)
    context=PortfolioRiskContextV2.create(run_id=book.run_id,as_of=T,equity=book.snapshot.equity,
        gross_exposure_before=D(0),net_exposure_before=D(0),session_reference_equity=D(10000),
        session_peak_equity=D(10000),source_snapshot_ids=(book.snapshot.snapshot_id,))
    session=VerifiedSessionV2.create(market="BTC",instrument_id="BTC",contract_id=None,
        session_date=T.date(),timezone="UTC",open_time=T,close_time=T+timedelta(hours=1),
        effective_from=T,effective_to=T+timedelta(days=1),calendar_version="fixture",source_ids=(H("calendar"),))
    limits=RiskLimitsV2.create(run_id=book.run_id,market="BTC",instrument_id="BTC",contract_id=None,
        effective_from=T,effective_to=T+timedelta(hours=1),max_gross_exposure=D(200),max_net_exposure=D(200),
        max_position_quantity=D(2),max_concentration=D(1),max_leverage=D(1),max_initial_margin=D(100),
        max_session_loss=D(100),max_drawdown=D(100),flatten_buffer_seconds=60,
        risk_policy_version=RISK_POLICY_VERSION,source_ids=(H("risk limits"),))
    policy=PaperSizingPolicyV1(T,T+timedelta(hours=1),D("0.001"),D(5),D(1),D("0.5"),H("synthetic policy"))
    return dict(strategy_inputs=args,performance=perf,gateway=gateway,context=context,
                limits=limits,session=session,sizing_policy=policy,source_bar_id=H("actual bar identity"))


def rebuilt(record, **changes):
    omit={"schema_version","context_id","limits_id","session_id"}
    args={f.name:getattr(record,f.name) for f in fields(record) if f.name not in omit}
    return type(record).create(**{**args,**changes})


def test_strategy_sizing_and_v2_risk_without_fill_or_mutation():
    args=setup(); before=args["performance"].ledger_id
    result=plan_strategy_paper_pretrade(**args)
    assert result==plan_strategy_paper_pretrade(**args)
    assert result.quantity==D(1)  # Existing 100 notional cap, entry 100.
    assert result.planned_stop_loss_with_allowances==D("3.5")
    assert result.reserved_cash==D("101.5")
    assert result.risk_eligible and not result.submission_authorized and not result.trading_authority
    assert args["performance"].ledger_id==before and not args["gateway"].records
    assert not args["performance"].accounting.events
    with pytest.raises(FrozenInstanceError): result.quantity=D(2)
    with pytest.raises(PaperPretradeError): replace(result,submission_authorized=True)


def test_exact_fractional_floor_and_one_step_boundaries():
    args=setup()
    args["sizing_policy"]=replace(args["sizing_policy"],maximum_planned_loss=D("1.006"))
    result=plan_strategy_paper_pretrade(**args)
    assert result.quantity==D("0.002")
    assert result.planned_stop_loss_with_allowances==D("1.005")
    args["sizing_policy"]=replace(args["sizing_policy"],maximum_planned_loss=D("1.0024"))
    with pytest.raises(PaperPretradeError,match="one quantity step"):
        plan_strategy_paper_pretrade(**args)


def test_v2_rejection_is_not_converted_to_allow():
    args=setup(); args["limits"]=rebuilt(args["limits"],max_gross_exposure=D(1))
    result=plan_strategy_paper_pretrade(**args)
    assert not result.risk_eligible
    assert "GROSS_EXPOSURE_LIMIT" in result.risk_decision.event.reason_codes
    assert not result.submission_authorized


@pytest.mark.parametrize("changes",[dict(equity=D(9999)),dict(gross_exposure_before=D(1)),
    dict(source_snapshot_ids=(H("other"),)),dict(as_of=T+timedelta(seconds=1)),
    dict(as_of=T-timedelta(seconds=6)),dict(session_peak_equity=D(10100)),
    dict(session_reference_equity=D(10100),session_peak_equity=D(10100))])
def test_mismatched_stale_or_breached_context_rejects(changes):
    args=setup(); args["context"]=rebuilt(args["context"],**changes)
    with pytest.raises(PaperPretradeError): plan_strategy_paper_pretrade(**args)


def test_identity_coverage_and_quantity_bypass_reject():
    args=setup();args["strategy_inputs"]["quantity"]=D(1)
    with pytest.raises(PaperPretradeError): plan_strategy_paper_pretrade(**args)
    args=setup();args["strategy_inputs"]["run_id"]=H("other")
    with pytest.raises(PaperPretradeError): plan_strategy_paper_pretrade(**args)
    args=setup();args["sizing_policy"]=replace(args["sizing_policy"],effective_to=T+timedelta(seconds=1))
    with pytest.raises(PaperPretradeError): plan_strategy_paper_pretrade(**args)
    args=setup();args["session"]=rebuilt(args["session"],close_time=T+timedelta(seconds=150))
    with pytest.raises(PaperPretradeError): plan_strategy_paper_pretrade(**args)


@pytest.mark.parametrize("changes",[dict(maximum_equity_risk_fraction=D(0)),
    dict(maximum_equity_risk_fraction=D(2)),dict(maximum_planned_loss=True),
    dict(fixed_cost_allowance=D(-1)),dict(per_unit_cost_allowance=0.1),
    dict(per_unit_cost_allowance=D("NaN")),dict(evidence_sha256="")])
def test_policy_requires_explicit_valid_assumptions(changes):
    with pytest.raises(ValueError): replace(setup()["sizing_policy"],**changes)


def test_policy_evidence_and_source_bar_are_bound_in_plan():
    args=setup(); first=plan_strategy_paper_pretrade(**args)
    args["sizing_policy"]=replace(args["sizing_policy"],evidence_sha256=H("other"))
    assert plan_strategy_paper_pretrade(**args).plan_id!=first.plan_id
    args=setup();args["source_bar_id"]=H("different bar")
    assert plan_strategy_paper_pretrade(**args).plan_id!=first.plan_id


def test_cash_affordability_includes_explicit_cost_allowances():
    args=setup(); old=args["performance"].accounting
    book=InstrumentAccountingLedgerV2.create(run_id=old.run_id,starting_cash=D(50),
        instrument=old.instrument,policy=old.policy,margin_specification=old.margin_specification)
    args["performance"]=PaperPerformanceLedgerV1.create(book,args["gateway"])
    args["context"]=rebuilt(args["context"],equity=D(50),session_reference_equity=D(50),
        session_peak_equity=D(50),source_snapshot_ids=(book.snapshot.snapshot_id,))
    args["sizing_policy"]=replace(args["sizing_policy"],maximum_equity_risk_fraction=D("0.5"))
    result=plan_strategy_paper_pretrade(**args)
    assert result.quantity==D("0.487")
    assert result.reserved_cash==D("49.9435")
    assert result.reserved_cash <= book.snapshot.cash


def test_outstanding_order_and_gateway_mismatch_reject():
    from execution.paper_gateway_v2 import PaperSubmissionV1
    args=setup(); plan=plan_strategy_paper_pretrade(**args)
    intent=plan.strategy_intent.intent
    req=PaperSubmissionV1(H("test-only-authorized-request"),intent,intent.limit_price,T,T,H("fixture"),True,False)
    args["gateway"],_=args["gateway"].submit(req)
    with pytest.raises(PaperPretradeError,match="bound to current"):
        plan_strategy_paper_pretrade(**args)
    args["performance"]=args["performance"].reconcile_gateway(args["gateway"])
    with pytest.raises(PaperPretradeError,match="outstanding"):
        plan_strategy_paper_pretrade(**args)


def test_disconnected_gateway_rejects_even_if_reconciled():
    args=setup();args["gateway"]=args["gateway"].disconnect()
    args["performance"]=args["performance"].reconcile_gateway(args["gateway"])
    with pytest.raises(PaperPretradeError,match="not healthy"):
        plan_strategy_paper_pretrade(**args)


def test_perpetual_intent_uses_margin_cash_capacity_and_v2_risk(tmp_path):
    from execution.test_btc_perpetual_strategy_intent_v1 import arguments as perp_arguments
    strategy=perp_arguments(tmp_path)
    now=strategy["now"]
    strategy.pop("quantity"); strategy.pop("quantity_evidence_sha256")
    original=accounting(); instrument=strategy["economics"].instrument
    policy=replace(original.policy,perpetual_capability_enabled=True)
    book=InstrumentAccountingLedgerV2.create(run_id=original.run_id,starting_cash=D(10000),
        instrument=instrument,policy=policy,margin_specification=strategy["margin"])
    strategy["run_id"]=book.run_id
    gateway=initial().gateway
    performance=PaperPerformanceLedgerV1.create(book,gateway)
    context=PortfolioRiskContextV2.create(run_id=book.run_id,as_of=now,equity=book.snapshot.equity,
        gross_exposure_before=D(0),net_exposure_before=D(0),session_reference_equity=D(10000),
        session_peak_equity=D(10000),source_snapshot_ids=(book.snapshot.snapshot_id,))
    session=VerifiedSessionV2.create(market="BTC-PERP",instrument_id="BTC",contract_id="BTC-PERP",
        session_date=now.date(),timezone="UTC",open_time=now,close_time=now+timedelta(hours=1),
        effective_from=now,effective_to=now+timedelta(days=1),calendar_version="fixture",
        source_ids=(H("perp session"),))
    limits=RiskLimitsV2.create(run_id=book.run_id,market="BTC-PERP",instrument_id="BTC",
        contract_id="BTC-PERP",effective_from=now,effective_to=now+timedelta(hours=1),
        max_gross_exposure=D(200),max_net_exposure=D(200),max_position_quantity=D(2),
        max_concentration=D(1),max_leverage=D(1),max_initial_margin=D(100),
        max_session_loss=D(100),max_drawdown=D(100),flatten_buffer_seconds=60,
        risk_policy_version=RISK_POLICY_VERSION,source_ids=(H("perp limits"),))
    sizing=PaperSizingPolicyV1(now,now+timedelta(hours=1),D("0.001"),D(5),D(1),D("0.5"),
        H("perp sizing policy"))
    result=plan_strategy_paper_pretrade(strategy_inputs=strategy,performance=performance,
        gateway=gateway,context=context,limits=limits,session=session,sizing_policy=sizing,
        source_bar_id=H("perp source bar"))
    assert result.quantity==D("1")  # Existing global 100-notional supervised-paper cap.
    assert result.reserved_cash==D("4")
    assert result.risk_eligible
    assert result.strategy_intent.intent.market=="BTC-PERP"
    assert not result.submission_authorized and not result.trading_authority
