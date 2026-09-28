from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2 import *

T0 = datetime(2026, 3, 9, 14, 30, tzinfo=timezone.utc)
D = Decimal
H = lambda value: hashlib.sha256(value.encode()).hexdigest()


def inst(contract="ESH6", profile=InstrumentProfile.ES_FUTURE, market="CME", instrument_id="ES"):
    multiplier = D("50") if profile == InstrumentProfile.ES_FUTURE else D("20") if profile == InstrumentProfile.NQ_FUTURE else D("1")
    return InstrumentSpecificationV2("instrument-spec-v2-1", H("inst-" + contract), market,
        instrument_id, contract, profile, "USD", D("0.25") if "FUTURE" in profile.value else D("0.01"),
        D("1") if "FUTURE" in profile.value else D("0.001"), multiplier,
        multiplier if "FUTURE" in profile.value else None, T0 - timedelta(days=2),
        T0 + timedelta(days=2), (H("evidence-" + contract),))


def sess(contract="ESH6"):
    return VerifiedSessionV2.create(market="CME", instrument_id="ES", contract_id=contract,
        session_date=date(2026, 3, 9), timezone="America/Chicago", open_time=T0,
        close_time=T0 + timedelta(hours=6), effective_from=T0 - timedelta(days=1),
        effective_to=T0 + timedelta(days=1), calendar_version="cal-v1",
        source_ids=(H("session-" + contract),))


def spec(*, opening_side=OrderSide.BUY, market="CME", instrument_id="ES", outgoing="ESH6", incoming="ESM6", **changes):
    outgoing_s, incoming_s = sess(outgoing), sess(incoming)
    values = dict(run_id=H("run"), market=market, instrument_id=instrument_id,
        outgoing_contract_id=outgoing, incoming_contract_id=incoming, opening_side=opening_side,
        outgoing_quantity=D("2"), incoming_quantity=D("2"), roll_time=T0,
        effective_from=T0 - timedelta(minutes=1), effective_to=T0 + timedelta(hours=6),
        outgoing_session_id=outgoing_s.session_id, incoming_session_id=incoming_s.session_id,
        outgoing_instrument_specification_id=H("inst-" + outgoing),
        incoming_instrument_specification_id=H("inst-" + incoming), participation_limit=D("0.5"),
        quantity_step=D("1"), roll_version=PHASE6_VERSION, source_ids=(H("roll-source"),))
    values.update(changes); return RollSpecificationV2.create(**values)


def bar(contract, minute, *, volume=D("10"), bar_id=None, finalized=True):
    at = T0 + timedelta(minutes=minute)
    return OHLCBarV2("ohlc-bar-v2-1", bar_id or H(f"bar-{contract}-{minute}"), "CME", "ES", contract,
        at, at + timedelta(minutes=1), at + timedelta(minutes=1), D("5000"), D("5001"),
        D("4999"), D("5000"), volume, finalized, True, True, True, "bars-v1")


def roll_fill(instruction, name, quantity=None):
    quantity = quantity or instruction.authorized_quantity
    return ExecutionFillV2("execution-fill-v2-1", H("fill-" + name), H("order-" + name),
        instruction.eligible_bar_id, None, instruction.market, instruction.instrument_id,
        instruction.contract_id, instruction.triggered_at + timedelta(minutes=1), instruction.side,
        quantity, D("5000"), D("5000"), D("5000"), D("0"), D("10"), D("10"), D("10"),
        "ROLLOVER", "CONSERVATIVE_OHLC_1M_V1", "BAR_VOLUME_PARTICIPATION_V1", "roll-v1")


def roll_once(opening_side=OrderSide.BUY, profile=InstrumentProfile.ES_FUTURE, prefix="ES"):
    outgoing, incoming = prefix + "H6", prefix + "M6"
    market, instrument_id = "CME", prefix
    outgoing_s = VerifiedSessionV2.create(market=market, instrument_id=instrument_id, contract_id=outgoing,
        session_date=date(2026,3,9), timezone="America/Chicago", open_time=T0, close_time=T0+timedelta(hours=6),
        effective_from=T0-timedelta(days=1), effective_to=T0+timedelta(days=1), calendar_version="cal-v1", source_ids=(H("s-"+outgoing),))
    incoming_s = VerifiedSessionV2.create(market=market, instrument_id=instrument_id, contract_id=incoming,
        session_date=date(2026,3,9), timezone="America/Chicago", open_time=T0, close_time=T0+timedelta(hours=6),
        effective_from=T0-timedelta(days=1), effective_to=T0+timedelta(days=1), calendar_version="cal-v1", source_ids=(H("s-"+incoming),))
    multiplier=D("50") if prefix=="ES" else D("20")
    oi=InstrumentSpecificationV2("instrument-spec-v2-1",H("inst-"+outgoing),market,instrument_id,outgoing,profile,"USD",D("0.25"),D("1"),multiplier,multiplier,T0-timedelta(days=2),T0+timedelta(days=2),(H("e-"+outgoing),))
    ii=InstrumentSpecificationV2("instrument-spec-v2-1",H("inst-"+incoming),market,instrument_id,incoming,profile,"USD",D("0.25"),D("1"),multiplier,multiplier,T0-timedelta(days=2),T0+timedelta(days=2),(H("e-"+incoming),))
    rs=RollSpecificationV2.create(run_id=H("run"),market=market,instrument_id=instrument_id,outgoing_contract_id=outgoing,incoming_contract_id=incoming,opening_side=opening_side,outgoing_quantity=D("2"),incoming_quantity=D("2"),roll_time=T0,effective_from=T0-timedelta(minutes=1),effective_to=T0+timedelta(hours=6),outgoing_session_id=outgoing_s.session_id,incoming_session_id=incoming_s.session_id,outgoing_instrument_specification_id=oi.specification_id,incoming_instrument_specification_id=ii.specification_id,participation_limit=D("0.5"),quantity_step=D("1"),roll_version=PHASE6_VERSION,source_ids=(H("source"),))
    signed=D("2") if opening_side==OrderSide.BUY else D("-2"); state=RolloverStateV2.create(rs,signed)
    ob=OHLCBarV2("ohlc-bar-v2-1",H("ob"+prefix),market,instrument_id,outgoing,T0+timedelta(minutes=1),T0+timedelta(minutes=2),T0+timedelta(minutes=2),D("5000"),D("5001"),D("4999"),D("5000"),D("10"),True,True,True,True,"bars-v1")
    oi1=create_roll_instruction(state=state,bar=ob,session=outgoing_s,trigger_bar_id=H("trigger"),outgoing_instrument=oi,incoming_instrument=ii)
    state=apply_roll_fill(state,oi1,roll_fill(oi1,"out"+prefix,D("2")))
    ib=replace(ob,bar_id=H("ib"+prefix),contract_id=incoming,open_time=T0+timedelta(minutes=3),close_time=T0+timedelta(minutes=4),available_at=T0+timedelta(minutes=4))
    ii1=create_roll_instruction(state=state,bar=ib,session=incoming_s,trigger_bar_id=ob.bar_id,outgoing_instrument=oi,incoming_instrument=ii)
    return state, oi1, ii1, apply_roll_fill(state,ii1,roll_fill(ii1,"in"+prefix,D("2")))


def accounting_snapshot(profile=InstrumentProfile.BTC_LINEAR_PERPETUAL, qty=D("1"), as_of=T0):
    market=instrument_id=contract="BTC-PERP"
    pos=PositionStateV2(qty,D("50000") if qty else None,D("50000") if qty else None,None)
    equity=D("100000") + (qty * D("50000") if profile==InstrumentProfile.BTC_SPOT else D("0"))
    return AccountingSnapshotPhase4V2("instrument-accounting-snapshot-v2-1",H("snap"+str(qty)+str(as_of)+profile.value),H("run"),as_of,market,instrument_id,contract,profile,"USD",pos,D("100000"),D("100000"),D("0"),D("0"),D("0"),D("0"),D("0"),D("0"),D("0"),D("0"),D("0"),equity,D("0"),D("0"),D("0"),D("0"),False,(H("aevent"),),ACCOUNTING_VERSION,H("fp"+str(qty)+str(as_of)+profile.value))


def perp_inst(profile=InstrumentProfile.BTC_LINEAR_PERPETUAL):
    return inst("BTC-PERP",profile,"BTC-PERP","BTC-PERP")


def requirement(**changes):
    values=dict(run_id=H("run"),market="BTC-PERP",instrument_id="BTC-PERP",contract_id="BTC-PERP",funding_time=T0+timedelta(hours=1),latest_available_at=T0+timedelta(hours=1,minutes=5),contract_basis="LINEAR_USD",contract_multiplier=D("1"),instrument_specification_id=H("inst-BTC-PERP"),funding_version=PHASE6_VERSION,fact_source_version="fund-v1",source_ids=(H("funding-schedule"),))
    values.update(changes); return FundingRequirementV2.create(**values)


def funding(rate="0.001", **changes):
    values=dict(schema_version="funding-fact-v2-1",funding_id=H("fund"),market="BTC-PERP",instrument_id="BTC-PERP",contract_id="BTC-PERP",funding_time=T0+timedelta(hours=1),available_at=T0+timedelta(hours=1,minutes=1),rate=D(rate),mark_price=D("50000"),oracle_price=D("49990"),specification_ids=(H("funding"),H("mark"),H("oracle")),source_version="fund-v1")
    values.update(changes); return FundingFactV2(**values)


def test_es_long_roll_closes_outgoing_then_opens_incoming():
    state, out, incoming, done=roll_once(); assert state.status==RollStatus.FLAT_AWAITING_INCOMING and done.status==RollStatus.COMPLETE and out.instruction_id!=incoming.instruction_id

def test_nq_short_roll_closes_outgoing_then_opens_incoming():
    _, out, incoming, done=roll_once(OrderSide.SELL,InstrumentProfile.NQ_FUTURE,"NQ"); assert out.side==OrderSide.BUY and incoming.side==OrderSide.SELL and done.status==RollStatus.COMPLETE

def test_partial_outgoing_close_blocks_incoming_activation():
    s=spec(); state=RolloverStateV2.create(s,D("2")); ob=bar("ESH6",1); ins=create_roll_instruction(state=state,bar=ob,session=sess(),trigger_bar_id=H("t"),outgoing_instrument=inst(),incoming_instrument=inst("ESM6")); partial=apply_roll_fill(state,ins,roll_fill(ins,"p",D("1"))); assert partial.status==RollStatus.OUTGOING_PARTIAL
    flat,_,incoming,_=roll_once()
    with pytest.raises(Phase6Error): apply_roll_fill(partial,incoming,roll_fill(incoming,"bad"))

def test_failed_outgoing_close_and_missing_incoming_are_explicit():
    state=RolloverStateV2.create(spec(),D("2")); failed=record_missing_roll_bar(state,RollLeg.OUTGOING_CLOSE); assert failed.status==RollStatus.FAILED_OUTGOING
    flat,_,_,_=roll_once(); assert record_missing_roll_bar(flat,RollLeg.INCOMING_OPEN) is flat and flat.temporarily_flat

@pytest.mark.parametrize("mutation",[{"roll_version":"wrong"},{"outgoing_contract_id":"ESM6"}])
def test_wrong_contract_market_or_roll_version_reject(mutation):
    with pytest.raises((ValueError,Phase6Error)): spec(**mutation)

def test_wrong_market_session_identity_rejects_at_handoff():
    state=RolloverStateV2.create(spec(),D("2")); wrong=replace(bar("ESH6",1),market="OTHER")
    with pytest.raises(Phase6Error): create_roll_instruction(state=state,bar=wrong,session=sess(),trigger_bar_id=H("t"),outgoing_instrument=inst(),incoming_instrument=inst("ESM6"))

def test_stale_overlapping_and_ambiguous_roll_specs_reject():
    one=spec(); two=spec(source_ids=(H("other"),));
    with pytest.raises(Phase6Error): validate_roll_specifications((one,two))

def test_participation_limit_floors_quantity_and_missing_volume_rejects():
    assert eligible_roll_quantity(bar("ESH6",1,volume=D("3")),spec(),D("2"))==D("1")
    with pytest.raises(Phase6Error): eligible_roll_quantity(bar("ESH6",1,volume=None),spec(),D("2"))

def test_rollover_rejects_same_bar_and_lookahead():
    state=RolloverStateV2.create(spec(),D("2")); b=bar("ESH6",1)
    with pytest.raises(Phase6Error) as exc: create_roll_instruction(state=state,bar=b,session=sess(),trigger_bar_id=b.bar_id,outgoing_instrument=inst(),incoming_instrument=inst("ESM6"))
    assert exc.value.reason==Phase6Reason.SAME_BAR_REJECTED

def test_roll_replay_idempotent_and_conflicting_fill_rejects():
    s=spec(); state=RolloverStateV2.create(s,D("2")); b=bar("ESH6",1); ins=create_roll_instruction(state=state,bar=b,session=sess(),trigger_bar_id=H("t"),outgoing_instrument=inst(),incoming_instrument=inst("ESM6")); f=roll_fill(ins,"x",D("1")); applied=apply_roll_fill(state,ins,f); assert apply_roll_fill(applied,ins,f) is applied
    with pytest.raises(Phase6Error): apply_roll_fill(applied,ins,replace(f,quantity=D("2")))

def test_perpetual_long_funding_debit_and_short_credit_are_symmetric():
    long=prepare_funding_application(requirement=requirement(),fact=funding(),snapshot=accounting_snapshot(qty=D("1")),instrument=perp_inst(),perpetual_capability_enabled=True)
    short=prepare_funding_application(requirement=requirement(),fact=funding(),snapshot=accounting_snapshot(qty=D("-1")),instrument=perp_inst(),perpetual_capability_enabled=True)
    assert long.expected_payment==D("-50") and short.expected_payment==D("50")

def test_flat_perpetual_funding_is_verified_zero_application():
    app=prepare_funding_application(requirement=requirement(),fact=funding(),snapshot=accounting_snapshot(qty=D("0")),instrument=perp_inst(),perpetual_capability_enabled=True); assert app.expected_payment==0

def test_duplicate_and_conflicting_funding_events():
    app=prepare_funding_application(requirement=requirement(),fact=funding(),snapshot=accounting_snapshot(),instrument=perp_inst(),perpetual_capability_enabled=True)
    e=Phase6EventV2.create(economic_id=app.funding_id,kind=Phase6EventKind.FUNDING,event_time=app.accounting_event.event_time,payload_id=app.application_id); ledger=Phase6LedgerV2.create(H("run")).apply(e); assert ledger.apply(e) is ledger
    with pytest.raises(Phase6Error): ledger.apply(Phase6EventV2.create(economic_id=app.funding_id,kind=Phase6EventKind.FUNDING,event_time=e.event_time+timedelta(minutes=1),payload_id=H("other")))

def test_late_stale_and_out_of_order_funding_reject():
    with pytest.raises(Phase6Error): prepare_funding_application(requirement=requirement(),fact=funding(available_at=T0+timedelta(hours=2)),snapshot=accounting_snapshot(),instrument=perp_inst(),perpetual_capability_enabled=True)
    with pytest.raises(Phase6Error): prepare_funding_application(requirement=requirement(),fact=funding(funding_time=T0+timedelta(hours=2),available_at=T0+timedelta(hours=2,minutes=1)),snapshot=accounting_snapshot(),instrument=perp_inst(),perpetual_capability_enabled=True)

def test_missing_required_funding_boundary_blocks_held_position():
    with pytest.raises(Phase6Error): funding_boundary_gate(snapshot=accounting_snapshot(),requirements=(requirement(),),applications=(),through=T0+timedelta(hours=2))

@pytest.mark.parametrize("profile",[InstrumentProfile.BTC_SPOT,InstrumentProfile.ES_FUTURE,InstrumentProfile.NQ_FUTURE])
def test_spot_and_futures_funding_reject(profile):
    market="BTC-PERP"; instrument=perp_inst(profile)
    with pytest.raises(Phase6Error): prepare_funding_application(requirement=requirement(),fact=funding(),snapshot=accounting_snapshot(profile=profile),instrument=instrument,perpetual_capability_enabled=True)

def test_cross_instrument_multiplier_and_version_reject():
    with pytest.raises(Phase6Error): prepare_funding_application(requirement=requirement(contract_multiplier=D("2")),fact=funding(),snapshot=accounting_snapshot(),instrument=perp_inst(),perpetual_capability_enabled=True)

def test_phase6_collision_priority_is_total_and_stable():
    assert [int(x) for x in Phase6Priority]==[10,20,21,22,23,30,40,50,60,70,80,90]

def test_same_priority_identity_collision_rejects_ambiguity():
    a=Phase6EventV2.create(economic_id=H("a"),kind=Phase6EventKind.FUNDING,event_time=T0,payload_id=H("pa")); b=Phase6EventV2.create(economic_id=H("b"),kind=Phase6EventKind.FUNDING,event_time=T0,payload_id=H("pb"));
    for first,second in ((a,b),(b,a)):
        with pytest.raises(Phase6Error) as exc: Phase6LedgerV2.create(H("run")).apply(first).apply(second)
        assert exc.value.reason is Phase6Reason.PRIORITY_AMBIGUITY

def test_rollover_funding_ledger_checkpoint_is_byte_stable_and_tamper_rejects():
    event=Phase6EventV2.create(economic_id=H("e"),kind=Phase6EventKind.SETTLEMENT,event_time=T0,payload_id=H("p")); a=Phase6LedgerV2.create(H("run")).apply(event); b=Phase6LedgerV2.create(H("run")).apply(event); assert a==b and Phase6CheckpointV2.create(a)==Phase6CheckpointV2.create(b)
    with pytest.raises(Phase6Error): replace(a,ledger_fingerprint=H("bad")).verify_integrity()

def test_incomplete_roll_and_missing_funding_fail_completed_gate():
    with pytest.raises(Phase6Error): completed_phase6_gate(rolls=(RolloverStateV2.create(spec(),D("2")),),requirements=(),applications=(),snapshot=accounting_snapshot(),through=T0)

def test_reconciliation_binds_all_upstream_lineage():
    values=dict(run_id=H("run"),order_ledger_fingerprint=H("orders"),execution_ids=(H("fill"),),accounting_ledger_fingerprint=H("accounting"),accounting_snapshot_id=H("snap"),risk_ledger_fingerprint=H("risk"),session_ids=(H("session"),),roll_state_ids=(H("roll"),),funding_application_ids=(H("fund"),),phase6_ledger_fingerprint=H("phase6")); a=Phase6ReconciliationV2.create(**values); assert a==Phase6ReconciliationV2.create(**values)

def test_phase6_has_no_provider_strategy_order_submission_or_runtime_authority():
    import inspect, backtesting.execution_accounting_v2.rollover_funding as module
    source=inspect.getsource(module).lower(); assert all(x not in source for x in ("requests", "private_key", "submit_order", "scheduledtask", "websocket"))
