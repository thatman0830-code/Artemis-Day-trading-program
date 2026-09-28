from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backtesting.execution_accounting_v2 import (
    ACCOUNTING_VERSION, AccountingSnapshotPhase4V2, InstrumentProfile,
    InstrumentSpecificationV2, MarginBasis, MarginSpecificationV2, OHLCBarV2,
    OrderSide, PipelinePriority, PortfolioRiskContextV2, PositionStateV2,
    PreTradeRiskRequestV2, RISK_POLICY_VERSION, RiskDecision, RiskLimitsV2,
    RiskReason, RiskSessionError, RiskSessionLedgerV2, VerifiedSessionV2,
    completed_run_gate, evaluate_post_accounting, evaluate_pre_trade, evaluate_session_flatten,
    resolve_session, validate_forced_flatten_bar,
)

T0 = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
H = lambda x: __import__("hashlib").sha256(x.encode()).hexdigest()
D = Decimal


def session(**kw):
    values = dict(market="CME", instrument_id="ES", contract_id="ESH6",
        session_date=date(2026, 1, 5), timezone="America/Chicago", open_time=T0,
        close_time=T0 + timedelta(hours=6), effective_from=T0 - timedelta(days=1),
        effective_to=T0 + timedelta(days=2), calendar_version="calendar-v1", source_ids=(H("calendar"),))
    values.update(kw)
    return VerifiedSessionV2.create(**values)


def limits(**kw):
    values = dict(run_id=H("run"), market="CME", instrument_id="ES", contract_id="ESH6",
        effective_from=T0 - timedelta(days=1), effective_to=T0 + timedelta(days=2),
        max_gross_exposure=D("1000000"), max_net_exposure=D("1000000"),
        max_position_quantity=D("100"), max_concentration=D("1"), max_leverage=D("100"),
        max_initial_margin=D("1000000"), max_session_loss=D("1000"), max_drawdown=D("1500"),
        flatten_buffer_seconds=60, risk_policy_version=RISK_POLICY_VERSION, source_ids=(H("owner"),))
    values.update(kw)
    return RiskLimitsV2.create(**values)


def instrument():
    return InstrumentSpecificationV2("instrument-spec-v2-1", H("instrument"), "CME", "ES", "ESH6",
        InstrumentProfile.ES_FUTURE, "USD", D("0.25"), D("1"), D("50"), D("50"),
        T0 - timedelta(days=1), T0 + timedelta(days=2), (H("rules"),))


def margin():
    return MarginSpecificationV2("margin-specification-v2-1", H("margin"), "CME", "ES", "ESH6",
        T0 - timedelta(days=1), T0 + timedelta(days=2), MarginBasis.PER_CONTRACT,
        D("5000"), D("4000"), D("6000"), D("4500"), "margin-v1")


def snapshot(*, equity=D("10000"), qty=D("1"), breach=False, as_of=T0 + timedelta(minutes=1)):
    pos = PositionStateV2(qty, D("5000") if qty else None, D("5000") if qty else None, None)
    cash = equity
    values = ("instrument-accounting-snapshot-v2-1", H(f"snap-{equity}-{qty}-{as_of}"), H("run"), as_of,
        "CME", "ES", "ESH6", InstrumentProfile.ES_FUTURE, "USD", pos, D("10000"), cash,
        D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), equity,
        D("5000") if qty else D("0"), D("4000") if qty else D("0"),
        D("6000") if qty else D("0"), D("4500") if qty else D("0"), breach,
        (H("accounting-event"),), ACCOUNTING_VERSION, H(f"fp-{equity}-{qty}-{as_of}"))
    return AccountingSnapshotPhase4V2(*values)


def request(**kw):
    values = dict(run_id=H("run"), evaluated_at=T0 + timedelta(minutes=2), market="CME",
        instrument_id="ES", contract_id="ESH6", side=OrderSide.BUY, quantity=D("1"),
        reference_price=D("5000"), source_action_id=H("action"), source_bar_id=H("bar"))
    values.update(kw)
    return PreTradeRiskRequestV2.create(**values)


def context(**kw):
    values = dict(run_id=H("run"), as_of=T0 + timedelta(minutes=2), equity=D("10000"),
        gross_exposure_before=D("250000"), net_exposure_before=D("250000"),
        session_reference_equity=D("10000"), session_peak_equity=D("10000"),
        source_snapshot_ids=(H("snapshot-source"),))
    values.update(kw)
    return PortfolioRiskContextV2.create(**values)


def decision(**kw):
    return evaluate_pre_trade(request=request(**kw), snapshot=snapshot(), context=context(), limits=limits(),
                              session=session(), instrument=instrument(), margin=margin())


def bar(*, at=T0 + timedelta(minutes=2), bar_id=None, **kw):
    values = dict(schema_version="ohlc-bar-v2-1", bar_id=bar_id or H(f"bar-{at}"), market="CME",
        instrument_id="ES", contract_id="ESH6", open_time=at, close_time=at + timedelta(minutes=1),
        available_at=at + timedelta(minutes=1), open=D("5000"), high=D("5001"), low=D("4999"),
        close=D("5000"), volume=D("10"), finalized=True, session_eligible=True,
        data_quality_valid=True, contract_eligible=True, source_version="bars-v1")
    values.update(kw)
    return OHLCBarV2(**values)


def test_verified_session_requires_utc_half_open_interval_and_lineage():
    s = session(); assert resolve_session((s,), at=s.open_time, market="CME", instrument_id="ES", contract_id="ESH6") == s
    with pytest.raises(RiskSessionError): resolve_session((s,), at=s.close_time, market="CME", instrument_id="ES", contract_id="ESH6")


def test_verified_session_rejects_naive_time_invalid_timezone_and_effective_gap():
    with pytest.raises(ValueError): session(open_time=T0.replace(tzinfo=None))
    with pytest.raises(ValueError): session(timezone="Invalid/Zone")
    with pytest.raises(ValueError): session(effective_from=T0 + timedelta(minutes=1))


def test_session_resolution_rejects_missing_overlapping_and_mismatched_sessions():
    with pytest.raises(RiskSessionError): resolve_session((), at=T0, market="CME", instrument_id="ES", contract_id="ESH6")
    with pytest.raises(RiskSessionError) as exc: resolve_session((session(), session(source_ids=(H("other"),))), at=T0, market="CME", instrument_id="ES", contract_id="ESH6")
    assert exc.value.reason == RiskReason.SESSION_OVERLAP


def test_risk_limits_require_decimal_finite_effective_versioned_values():
    with pytest.raises((TypeError, ValueError)): limits(max_drawdown=1.0)
    with pytest.raises(ValueError): limits(max_leverage=D("NaN"))
    with pytest.raises(ValueError): limits(risk_policy_version="wrong")


def test_risk_records_are_frozen_and_identifiers_are_deterministic():
    assert decision() == decision()
    with pytest.raises(FrozenInstanceError): decision().action = None


def test_pretrade_accepts_projection_within_every_limit():
    result = decision(); assert result.event.decision == RiskDecision.ALLOW and result.event.reason_codes == ("OK",)


@pytest.mark.parametrize(("change", "reason"), [
    ({"max_gross_exposure": D("300000")}, RiskReason.GROSS_EXPOSURE_LIMIT),
    ({"max_net_exposure": D("300000")}, RiskReason.NET_EXPOSURE_LIMIT),
    ({"max_position_quantity": D("1")}, RiskReason.POSITION_LIMIT),
    ({"max_concentration": D("0.5")}, RiskReason.CONCENTRATION_LIMIT),
    ({"max_leverage": D("10")}, RiskReason.LEVERAGE_LIMIT),
    ({"max_initial_margin": D("10000")}, RiskReason.INITIAL_MARGIN_LIMIT),
])
def test_pretrade_limit_reasons(change, reason):
    result = evaluate_pre_trade(request=request(), snapshot=snapshot(), context=context(), limits=limits(**change), session=session(), instrument=instrument(), margin=margin())
    assert reason.value in result.event.reason_codes and result.event.decision == RiskDecision.REJECT


def test_pretrade_rejects_missing_stale_or_mismatched_limits():
    with pytest.raises(RiskSessionError) as exc: evaluate_pre_trade(request=request(), snapshot=snapshot(), context=context(), limits=limits(effective_to=T0), session=session(), instrument=instrument(), margin=margin())
    assert exc.value.reason == RiskReason.STALE_RISK_LIMITS


def test_pretrade_is_advisory_and_creates_no_order_or_fill():
    result = decision(); assert not hasattr(result, "order") and not hasattr(result, "fill")


def test_session_loss_and_drawdown_use_verified_reference_equity():
    first = evaluate_post_accounting(snapshot=snapshot(), prior_state=None, limits=limits(), session=session(), trigger_bar_id=H("b1"))
    second = evaluate_post_accounting(snapshot=snapshot(equity=D("8000"), as_of=T0 + timedelta(minutes=2)), prior_state=first.state, limits=limits(), session=session(), trigger_bar_id=H("b2"))
    assert second.state.session_loss == D("2000") and second.state.drawdown == D("2000")


def test_session_reference_cannot_reset_after_session_activity():
    prior = evaluate_post_accounting(snapshot=snapshot(), prior_state=None, limits=limits(), session=session(), trigger_bar_id=H("b1")).state
    with pytest.raises(RiskSessionError): evaluate_post_accounting(snapshot=snapshot(as_of=T0), prior_state=prior, limits=limits(), session=session(), trigger_bar_id=H("b2"))


def test_postaccounting_margin_breach_emits_margin_call_and_liquidation_required_facts():
    result = evaluate_post_accounting(snapshot=snapshot(equity=D("3000"), breach=True), prior_state=None, limits=limits(), session=session(), trigger_bar_id=H("breach"))
    assert result.margin_call and result.liquidation_required and result.forced_flatten


def test_postaccounting_priority_is_deterministic_when_breaches_collide():
    result = evaluate_post_accounting(snapshot=snapshot(equity=D("1000"), breach=True), prior_state=None, limits=limits(max_session_loss=D("1"), max_drawdown=D("1")), session=session(), trigger_bar_id=H("breach"))
    assert result.decision.event.reason_codes[0] == RiskReason.MAINTENANCE_MARGIN_BREACH.value


def test_duplicate_postaccounting_evaluation_is_idempotent():
    result = evaluate_post_accounting(snapshot=snapshot(equity=D("3000"), breach=True), prior_state=None, limits=limits(), session=session(), trigger_bar_id=H("breach"))
    ledger = RiskSessionLedgerV2.create(H("run")).apply(result); assert ledger.apply(result) is ledger


def test_forced_flatten_rejects_breach_bar_and_accepts_only_later_finalized_valid_bar():
    result = evaluate_post_accounting(snapshot=snapshot(equity=D("3000"), breach=True), prior_state=None, limits=limits(), session=session(), trigger_bar_id=H("breach"))
    with pytest.raises(RiskSessionError): validate_forced_flatten_bar(result.forced_flatten, bar(at=T0 + timedelta(minutes=1), bar_id=H("breach")), session())
    validate_forced_flatten_bar(result.forced_flatten, bar(at=T0 + timedelta(minutes=2)), session())


def test_forced_flatten_rejects_wrong_session_contract_and_unverified_bar():
    result = evaluate_post_accounting(snapshot=snapshot(equity=D("3000"), breach=True), prior_state=None, limits=limits(), session=session(), trigger_bar_id=H("breach"))
    with pytest.raises(RiskSessionError): validate_forced_flatten_bar(result.forced_flatten, bar(finalized=False), session())


def test_unresolved_forced_flatten_remains_explicit_at_end_of_data():
    result = evaluate_post_accounting(snapshot=snapshot(equity=D("3000"), breach=True), prior_state=None, limits=limits(), session=session(), trigger_bar_id=H("breach"))
    with pytest.raises(RiskSessionError) as exc: completed_run_gate(snapshot(equity=D("3000"), breach=True), (result.forced_flatten,))
    assert exc.value.reason == RiskReason.END_OF_DATA_RESIDUAL


def test_session_flatten_deadline_emits_instruction_only_and_requires_later_bar():
    snap = snapshot(as_of=T0 + timedelta(hours=6, minutes=-1))
    result = evaluate_session_flatten(snapshot=snap, limits=limits(), session=session(), trigger_bar_id=H("deadline-bar"))
    assert result.decision.event.reason_codes == (RiskReason.SESSION_FLATTEN_DEADLINE.value,)
    assert result.forced_flatten and not hasattr(result, "order") and not hasattr(result, "fill")
    with pytest.raises(RiskSessionError):
        validate_forced_flatten_bar(result.forced_flatten, bar(at=snap.as_of, bar_id=H("deadline-bar")), session())


def test_pipeline_priority_matches_frozen_phase_order():
    assert [int(x) for x in PipelinePriority] == list(range(10, 100, 10))


def test_risk_ledger_replay_and_checkpoint_are_byte_identical():
    r = decision(); a = RiskSessionLedgerV2.create(H("run")).apply(r); b = RiskSessionLedgerV2.create(H("run")).apply(r)
    assert a == b and a.checkpoint() == b.checkpoint()


def test_checkpoint_tamper_and_mixed_accounting_version_reject():
    ledger = RiskSessionLedgerV2.create(H("run")); tampered = replace(ledger, ledger_fingerprint=H("tamper"))
    with pytest.raises(RiskSessionError): tampered.verify_integrity()
    with pytest.raises(RiskSessionError): evaluate_pre_trade(request=request(), snapshot=replace(snapshot(), accounting_version="v1"), context=context(), limits=limits(), session=session(), instrument=instrument(), margin=margin())


def test_reason_catalog_covers_every_phase5_failure_and_transition():
    assert len({reason.value for reason in RiskReason}) == len(RiskReason)


def test_phase5_import_graph_has_no_strategy_provider_or_execution_authority():
    import inspect, backtesting.execution_accounting_v2.risk_sessions as module
    source = inspect.getsource(module).lower()
    assert "requests" not in source and "private_key" not in source and "submit_order" not in source
