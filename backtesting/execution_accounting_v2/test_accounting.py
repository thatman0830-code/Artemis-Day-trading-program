from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2.accounting import (
    ACCOUNTING_VERSION, AccountingError, AccountingEventKind, AccountingEventV2,
    AccountingPolicyV2, AccountingReason, FillEconomicsV2, FundingFactV2,
    InstrumentAccountingLedgerV2, MarginBasis, MarginSpecificationV2,
    PriceEvidenceV2, SettlementFactV2,
)
from backtesting.execution_accounting_v2.contracts import InstrumentSpecificationV2, OrderSide
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from backtesting.execution_accounting_v2.specifications import InstrumentProfile, canonical_json_bytes

UTC = timezone.utc
T0 = datetime(2025, 6, 1, tzinfo=UTC)
H = lambda value: hashlib.sha256(value.encode()).hexdigest()


def instrument(profile=InstrumentProfile.ES_FUTURE, **changes):
    market = {InstrumentProfile.ES_FUTURE: "ES", InstrumentProfile.NQ_FUTURE: "NQ",
              InstrumentProfile.BTC_SPOT: "BTC", InstrumentProfile.BTC_LINEAR_PERPETUAL: "BTC-PERP"}[profile]
    values = dict(schema_version="instrument-spec-v2-1", specification_id=H(f"instrument-{market}"),
        market=market, instrument_id=market, contract_id=f"{market}M5" if "FUTURE" in profile.value else None,
        profile=profile, currency="USD", tick_size=Decimal("0.25") if "FUTURE" in profile.value else Decimal("0.01"),
        quantity_step=Decimal("1") if "FUTURE" in profile.value else Decimal("0.001"),
        contract_multiplier=Decimal("50") if profile == InstrumentProfile.ES_FUTURE else
            Decimal("20") if profile == InstrumentProfile.NQ_FUTURE else Decimal("1"),
        point_value=Decimal("50") if profile == InstrumentProfile.ES_FUTURE else
            Decimal("20") if profile == InstrumentProfile.NQ_FUTURE else None,
        effective_from=T0, effective_to=None, evidence_ids=(H("instrument-evidence"),))
    values.update(changes)
    return InstrumentSpecificationV2(**values)


def policy(perpetual=False, **changes):
    values = dict(schema_version="accounting-policy-v2-1", accounting_version=ACCOUNTING_VERSION,
        cost_version="cost-v1", authoritative_price_type="MARK",
        perpetual_capability_enabled=perpetual,
        specification_ids=(H("settlement-spec"), H("funding-spec"), H("mark-spec"), H("oracle-spec"), H("fee-spec")))
    values.update(changes)
    return AccountingPolicyV2(**values)


def margin(inst, *, basis=MarginBasis.NOTIONAL_RATE, initial="0.10", maintenance="0.05", **changes):
    values = dict(schema_version="margin-specification-v2-1", margin_specification_id=H("margin"),
        market=inst.market, instrument_id=inst.instrument_id, contract_id=inst.contract_id,
        effective_from=T0, effective_to=None, basis=basis,
        clearing_initial=Decimal(initial), clearing_maintenance=Decimal(maintenance),
        customer_initial=Decimal(initial), customer_maintenance=Decimal(maintenance), source_version="margin-v1")
    values.update(changes)
    return MarginSpecificationV2(**values)


def ledger(profile=InstrumentProfile.ES_FUTURE, *, cash="100000", perpetual=False, **inst_changes):
    inst = instrument(profile, **inst_changes)
    selected_margin = margin(inst, initial="0", maintenance="0") if profile == InstrumentProfile.BTC_SPOT else margin(inst)
    return InstrumentAccountingLedgerV2.create(run_id=H("run"), starting_cash=Decimal(cash),
        instrument=inst, policy=policy(perpetual), margin_specification=selected_margin)


def fill(inst, name, side, qty, reference, *, friction="0", minute=1, policy_version="CONSERVATIVE_OHLC_1M_V1"):
    reference = Decimal(reference); friction = Decimal(friction)
    economic = reference + friction if side == OrderSide.BUY else reference - friction
    return ExecutionFillV2("execution-fill-v2-1", H(f"fill-{name}"), H(f"order-{name}"), H(f"bar-{name}"), None,
        inst.market, inst.instrument_id, inst.contract_id, T0 + timedelta(minutes=minute), side,
        Decimal(qty), reference, economic, economic, friction, Decimal("1000"), Decimal("100"),
        Decimal("100"), "TEST_FILL", policy_version, "BAR_VOLUME_PARTICIPATION_V1", "assumption-v1")


def fill_event(inst, name, side, qty, price, *, friction="0", commission="0", fee="0", minute=1,
               policy_version="CONSERVATIVE_OHLC_1M_V1"):
    accepted = fill(inst, name, side, qty, price, friction=friction, minute=minute,
                    policy_version=policy_version)
    slip = accepted.adverse_friction * accepted.quantity * inst.contract_multiplier
    costs = FillEconomicsV2("fill-economics-v2-1", H(f"cost-{name}"), accepted.fill_id,
        Decimal(commission), Decimal(fee), slip, "USD", (H("fee-spec"),), "cost-v1")
    return AccountingEventV2("accounting-event-v2-1", H(f"event-{name}"), AccountingEventKind.FILL,
        accepted.fill_time, accepted.fill_time, fill=accepted, fill_economics=costs)


def mark_event(inst, name, price, minute):
    fact = PriceEvidenceV2("price-evidence-v2-1", H(f"price-{name}"), inst.market, inst.instrument_id,
        inst.contract_id, T0 + timedelta(minutes=minute), T0 + timedelta(minutes=minute), Decimal(price),
        "MARK", H("mark-spec"), "prices-v1")
    return AccountingEventV2("accounting-event-v2-1", H(f"mark-event-{name}"), AccountingEventKind.MARK,
        fact.observed_at, fact.available_at, price=fact)


def settle_event(inst, name, price, minute):
    fact = SettlementFactV2("settlement-fact-v2-1", H(f"settle-{name}"), inst.market,
        inst.instrument_id, inst.contract_id or "UNSUPPORTED-SPOT-SETTLEMENT", T0 + timedelta(minutes=minute),
        T0 + timedelta(minutes=minute), Decimal(price), H("settlement-spec"), "settlement-v1")
    return AccountingEventV2("accounting-event-v2-1", H(f"settle-event-{name}"),
        AccountingEventKind.SETTLEMENT, fact.settlement_time, fact.available_at, settlement=fact)


def apply(source, *events):
    for event in events:
        source = source.apply(event)
    return source


@pytest.mark.parametrize("side,close_side,expected", [
    (OrderSide.BUY, OrderSide.SELL, Decimal("500")),
    (OrderSide.SELL, OrderSide.BUY, Decimal("500")),
])
def test_futures_long_and_short_open_close(side, close_side, expected):
    book = ledger(); inst = book.instrument
    prices = ("100", "110") if side == OrderSide.BUY else ("110", "100")
    result = apply(book, fill_event(inst, "open", side, "1", prices[0]),
                   fill_event(inst, "close", close_side, "1", prices[1], minute=2))
    assert result.snapshot.position.signed_quantity == 0
    assert result.snapshot.gross_realized_pnl == expected
    assert result.snapshot.cash == Decimal("100000") + expected
    assert result.validate_end_of_data() == ()


def test_nq_uses_its_verified_multiplier():
    book = ledger(InstrumentProfile.NQ_FUTURE); inst = book.instrument
    result = apply(book, fill_event(inst, "open", OrderSide.BUY, "1", "100"),
                   fill_event(inst, "close", OrderSide.SELL, "1", "110", minute=2))
    assert result.snapshot.gross_realized_pnl == Decimal("200")


def test_weighted_add_partial_reduce_complete_close_and_conservation():
    book = ledger(); inst = book.instrument
    result = apply(book, fill_event(inst, "a", OrderSide.BUY, "2", "100"),
        fill_event(inst, "b", OrderSide.BUY, "1", "103", minute=2),
        fill_event(inst, "c", OrderSide.SELL, "1", "104", minute=3))
    assert result.snapshot.position.signed_quantity == Decimal("2")
    assert result.snapshot.position.average_entry_price == Decimal("101")
    assert result.snapshot.gross_realized_pnl == Decimal("150")
    closed = result.apply(fill_event(inst, "d", OrderSide.SELL, "2", "99", minute=4))
    assert closed.snapshot.position.signed_quantity == 0
    assert closed.snapshot.gross_realized_pnl == Decimal("-50")
    assert sum(e.fill.quantity * (1 if e.fill.side == OrderSide.BUY else -1)
               for e in closed.events if e.kind == AccountingEventKind.FILL) == 0


@pytest.mark.parametrize("opening,closing,residual", [
    (OrderSide.BUY, OrderSide.SELL, Decimal("-1")),
    (OrderSide.SELL, OrderSide.BUY, Decimal("1")),
])
def test_reversal_closes_then_opens_residual_at_new_basis(opening, closing, residual):
    book = ledger(); inst = book.instrument
    result = apply(book, fill_event(inst, "open", opening, "1", "100"),
                   fill_event(inst, "reverse", closing, "2", "105", minute=2))
    assert result.snapshot.position.signed_quantity == residual
    assert result.snapshot.position.average_entry_price == Decimal("105")
    assert abs(result.snapshot.gross_realized_pnl) == Decimal("250")


def test_mark_unrealized_equity_and_favorable_adverse_moves():
    book = ledger(); inst = book.instrument
    opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "2", "100"))
    up = opened.apply(mark_event(inst, "up", "102", 2))
    assert up.snapshot.unrealized_pnl == Decimal("200")
    assert up.snapshot.equity == Decimal("100200")
    down = up.apply(mark_event(inst, "down", "99", 3))
    assert down.snapshot.unrealized_pnl == Decimal("-100")


def test_cost_attribution_applied_once_and_gross_minus_costs_is_net():
    book = ledger(); inst = book.instrument
    opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100", friction="0.25",
        commission="2", fee="1"))
    result = opened.apply(fill_event(inst, "close", OrderSide.SELL, "1", "110", friction="0.25",
        commission="2", fee="1", minute=2))
    assert (result.snapshot.commissions, result.snapshot.exchange_fees,
            result.snapshot.slippage_costs) == (Decimal("4"), Decimal("2"), Decimal("25"))
    assert result.snapshot.total_costs == Decimal("31")
    assert result.snapshot.net_result == result.snapshot.gross_realized_pnl - result.snapshot.total_costs
    assert result.snapshot.cash == Decimal("100000") + result.snapshot.net_result
    assert result.apply(result.events[-1]) is result


def test_variation_settlement_preserves_equity_and_resets_basis_multiple_times():
    book = ledger(); inst = book.instrument
    marked = apply(book, fill_event(inst, "open", OrderSide.BUY, "1", "100"),
                   mark_event(inst, "pre", "110", 2))
    before = marked.snapshot.equity
    first = marked.apply(settle_event(inst, "one", "110", 3))
    assert first.snapshot.cash == Decimal("100500")
    assert first.snapshot.unrealized_pnl == 0 and first.snapshot.equity == before
    second = first.apply(settle_event(inst, "two", "108", 4))
    assert second.snapshot.settlement_transfers == Decimal("400")
    assert second.snapshot.equity == Decimal("100400")


def test_missing_settlement_and_wrong_mark_specifications_fail_closed():
    book = ledger(); inst = book.instrument
    bad_settle = settle_event(inst, "missing", "100", 1)
    bad_settle = replace(bad_settle, settlement=replace(bad_settle.settlement,
                         specification_id=H("unknown-settlement")))
    with pytest.raises(AccountingError, match=AccountingReason.MISSING_SETTLEMENT_FACT.value):
        book.apply(bad_settle)
    bad_mark = mark_event(inst, "missing", "100", 1)
    bad_mark = replace(bad_mark, price=replace(bad_mark.price, specification_id=H("unknown-mark")))
    with pytest.raises(AccountingError, match=AccountingReason.MISSING_MARK_EVIDENCE.value):
        book.apply(bad_mark)


def test_duplicate_settlement_conflict_and_spot_settlement_reject():
    book = ledger(); fact = settle_event(book.instrument, "one", "100", 1)
    assert book.apply(fact).apply(fact).events == (fact,)
    conflict = replace(fact, settlement=replace(fact.settlement, settlement_price=Decimal("101")))
    with pytest.raises(AccountingError, match=AccountingReason.DUPLICATE_EVENT_CONFLICT.value):
        book.apply(fact).apply(conflict)
    spot = ledger(InstrumentProfile.BTC_SPOT)
    with pytest.raises(AccountingError, match=AccountingReason.SETTLEMENT_NOT_SUPPORTED.value):
        spot.apply(settle_event(spot.instrument, "spot", "100", 1))


def test_same_economic_fact_under_new_event_identity_rejects():
    book = ledger(); original = fill_event(book.instrument, "one", OrderSide.BUY, "1", "100")
    duplicate = replace(original, event_id=H("different-wrapper"))
    with pytest.raises(AccountingError, match=AccountingReason.DUPLICATE_ECONOMIC_EVENT.value):
        book.apply(original).apply(duplicate)


def test_btc_spot_base_quantity_quote_cash_and_no_funding():
    book = ledger(InstrumentProfile.BTC_SPOT, cash="10000"); inst = book.instrument
    opened = book.apply(fill_event(inst, "buy", OrderSide.BUY, "0.1", "50000", commission="5"))
    assert opened.snapshot.cash == Decimal("4995")
    assert opened.snapshot.position.signed_quantity == Decimal("0.1")
    marked = opened.apply(mark_event(inst, "spot", "51000", 2))
    assert marked.snapshot.equity == Decimal("10095")
    dummy = FundingFactV2("funding-fact-v2-1", H("fund"), inst.market, inst.instrument_id,
        inst.contract_id, T0 + timedelta(minutes=3), T0 + timedelta(minutes=3), Decimal("0.001"),
        Decimal("51000"), Decimal("51000"), (H("funding-spec"), H("mark-spec"), H("oracle-spec")), "f-v1")
    event = AccountingEventV2("accounting-event-v2-1", H("fund-event"), AccountingEventKind.FUNDING,
        dummy.funding_time, dummy.available_at, funding=dummy)
    with pytest.raises(AccountingError, match=AccountingReason.FUNDING_NOT_SUPPORTED.value):
        marked.apply(event)


def test_perpetual_capability_and_verified_funding_exactly_once():
    with pytest.raises(AccountingError, match=AccountingReason.MISSING_PERPETUAL_CAPABILITY.value):
        ledger(InstrumentProfile.BTC_LINEAR_PERPETUAL)
    book = ledger(InstrumentProfile.BTC_LINEAR_PERPETUAL, perpetual=True); inst = book.instrument
    opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "0.1", "50000"))
    fact = FundingFactV2("funding-fact-v2-1", H("fund"), inst.market, inst.instrument_id,
        inst.contract_id, T0 + timedelta(minutes=2), T0 + timedelta(minutes=2), Decimal("0.001"),
        Decimal("50000"), Decimal("49990"), (H("funding-spec"), H("mark-spec"), H("oracle-spec")), "f-v1")
    event = AccountingEventV2("accounting-event-v2-1", H("fund-event"), AccountingEventKind.FUNDING,
        fact.funding_time, fact.available_at, funding=fact)
    result = opened.apply(event)
    assert result.snapshot.funding == Decimal("-5") and result.snapshot.cash == Decimal("99995")
    assert result.apply(event) is result


def test_margin_calculation_distinguishes_clearing_customer_and_exposes_breach():
    inst = instrument()
    ms = margin(inst, initial="0.10", maintenance="0.05",
                customer_initial=Decimal("0.20"), customer_maintenance=Decimal("0.15"))
    book = InstrumentAccountingLedgerV2.create(run_id=H("run"), starting_cash=Decimal("1000"),
        instrument=inst, policy=policy(), margin_specification=ms)
    result = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
    assert result.snapshot.clearing_initial_margin == Decimal("500")
    assert result.snapshot.customer_initial_margin == Decimal("1000")
    assert result.snapshot.customer_maintenance_margin == Decimal("750")
    assert result.snapshot.margin_breach is False
    negative = ledger(cash="-100").apply(fill_event(inst, "negative", OrderSide.BUY, "1", "100"))
    assert negative.snapshot.cash == Decimal("-100") and negative.snapshot.margin_breach is True


@pytest.mark.parametrize("mutation,reason", [
    (lambda e: replace(e, fill=replace(e.fill, quantity=Decimal("1.5"))), AccountingReason.OFF_GRID_ECONOMICS),
    (lambda e: replace(e, fill=replace(e.fill, economic_price=Decimal("100.10"))), AccountingReason.OFF_GRID_ECONOMICS),
    (lambda e: replace(e, fill=replace(e.fill, execution_policy_version="v1")), AccountingReason.MIXED_LEDGER_VERSION),
    (lambda e: replace(e, fill_economics=replace(e.fill_economics, cost_version="stale")), AccountingReason.VERSION_MISMATCH),
])
def test_invalid_fill_inputs_fail_closed(mutation, reason):
    book = ledger(); event = mutation(fill_event(book.instrument, "bad", OrderSide.BUY, "1", "100"))
    with pytest.raises(AccountingError, match=reason.value):
        book.apply(event)


def test_identity_chronology_and_stale_margin_reject():
    book = ledger(); inst = book.instrument
    first = book.apply(mark_event(inst, "later", "100", 3))
    with pytest.raises(AccountingError, match=AccountingReason.EVENT_TIME_REGRESSION.value):
        first.apply(mark_event(inst, "earlier", "100", 2))
    wrong = replace(mark_event(inst, "wrong", "100", 4),
                    price=replace(mark_event(inst, "wrong", "100", 4).price, market="NQ"))
    with pytest.raises(AccountingError, match=AccountingReason.IDENTITY_MISMATCH.value):
        first.apply(wrong)
    stale_inst = instrument()
    stale = InstrumentAccountingLedgerV2.create(run_id=H("run"), starting_cash=Decimal("1"),
        instrument=stale_inst, policy=policy(),
        margin_specification=margin(stale_inst, effective_to=T0 + timedelta(seconds=30)))
    with pytest.raises(AccountingError, match=AccountingReason.STALE_SPECIFICATION.value):
        stale.apply(fill_event(stale_inst, "stale", OrderSide.BUY, "1", "100"))


def test_replay_checkpoint_determinism_immutability_and_tamper_detection():
    base = ledger(); inst = base.instrument
    events = (fill_event(inst, "open", OrderSide.BUY, "1", "100"), mark_event(inst, "mark", "101", 2))
    direct = apply(base, *events)
    replayed = InstrumentAccountingLedgerV2.replay(base, events)
    assert direct == replayed
    assert canonical_json_bytes(direct.snapshots) == canonical_json_bytes(replayed.snapshots)
    resumed = InstrumentAccountingLedgerV2.resume(direct.checkpoint())
    assert resumed == direct
    with pytest.raises(FrozenInstanceError):
        direct.snapshot.cash = Decimal("0")
    with pytest.raises(AccountingError, match=AccountingReason.CHECKPOINT_TAMPERED.value):
        replace(direct, ledger_fingerprint=H("tamper")).verify_integrity()
    assert direct.validate_end_of_data() == (AccountingReason.END_OF_DATA_RESIDUAL,)


def test_no_float_economic_boundaries():
    with pytest.raises(ValueError, match="Decimal"):
        FillEconomicsV2("fill-economics-v2-1", H("x"), H("y"), 1.0,
                        Decimal("0"), Decimal("0"), "USD", (H("s"),), "cost-v1")
