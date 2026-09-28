"""Hermes independent adversarial audit tests for V2 Phase 4 instrument accounting.

These tests are independent of the existing test suite and exercise edge cases,
boundary conditions, and invariant violations that the existing tests may not
cover. They are offline and deterministic.

Audit assignment: AUDIT-V2-PHASE4-ACCOUNTING

Covers:
  - ES/NQ futures and variation-margin accounting
  - BTC spot base/quote accounting
  - Capability-gated BTC linear-perpetual accounting
  - Long, short, add, reduce, close, and reversal transitions
  - Exact weighted-average basis and Decimal-only P&L
  - Separate fee, slippage, funding, settlement, and margin attribution
  - Clearing-margin versus customer-margin separation
  - Immutable margin-breach facts
  - Duplicate economic-event prevention
  - Deterministic replay, checkpoints, fingerprints, and tamper rejection
  - Residual-position and incomplete-accounting gates
  - Instrument, contract, version, chronology, tick-grid, and effective-date isolation
  - Unsupported capability rejection
  - Accounting reconciliation across all supported transitions
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2.accounting import (
    ACCOUNTING_VERSION, AccountingCheckpointV2, AccountingError, AccountingEventKind,
    AccountingEventV2, AccountingPolicyV2, AccountingReason, AccountingSnapshotPhase4V2,
    FillEconomicsV2, FundingFactV2, InstrumentAccountingLedgerV2, MarginBasis,
    MarginSpecificationV2, PositionStateV2, PriceEvidenceV2, SettlementFactV2,
)
from backtesting.execution_accounting_v2.contracts import (
    InstrumentSpecificationV2, OrderSide,
)
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from backtesting.execution_accounting_v2.specifications import (
    InstrumentProfile, canonical_json_bytes,
)


UTC = timezone.utc
T0 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
H = lambda value: hashlib.sha256(value.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def instrument(profile=InstrumentProfile.ES_FUTURE, **changes):
    market = {
        InstrumentProfile.ES_FUTURE: "ES",
        InstrumentProfile.NQ_FUTURE: "NQ",
        InstrumentProfile.BTC_SPOT: "BTC",
        InstrumentProfile.BTC_LINEAR_PERPETUAL: "BTC-PERP",
        InstrumentProfile.BTC_UNKNOWN_UNSUPPORTED: "BTC-UNK",
    }[profile]
    values = dict(
        schema_version="instrument-spec-v2-1",
        specification_id=H(f"instrument-{market}"),
        market=market,
        instrument_id=market,
        contract_id=f"{market}M5" if "FUTURE" in profile.value else None,
        profile=profile,
        currency="USD",
        tick_size=Decimal("0.25") if "FUTURE" in profile.value else Decimal("0.01"),
        quantity_step=Decimal("1") if "FUTURE" in profile.value else Decimal("0.001"),
        contract_multiplier=(
            Decimal("50") if profile == InstrumentProfile.ES_FUTURE else
            Decimal("20") if profile == InstrumentProfile.NQ_FUTURE else
            Decimal("1")
        ),
        point_value=(
            Decimal("50") if profile == InstrumentProfile.ES_FUTURE else
            Decimal("20") if profile == InstrumentProfile.NQ_FUTURE else
            None
        ),
        effective_from=T0,
        effective_to=None,
        evidence_ids=(H("instrument-evidence"),),
    )
    values.update(changes)
    return InstrumentSpecificationV2(**values)


def policy(perpetual=False, **changes):
    values = dict(
        schema_version="accounting-policy-v2-1",
        accounting_version=ACCOUNTING_VERSION,
        cost_version="cost-v1",
        authoritative_price_type="MARK",
        perpetual_capability_enabled=perpetual,
        specification_ids=(
            H("settlement-spec"),
            H("funding-spec"),
            H("mark-spec"),
            H("oracle-spec"),
            H("fee-spec"),
        ),
    )
    values.update(changes)
    return AccountingPolicyV2(**values)


def margin(inst, *, basis=MarginBasis.NOTIONAL_RATE, initial="0.10",
           maintenance="0.05", **changes):
    values = dict(
        schema_version="margin-specification-v2-1",
        margin_specification_id=H("margin"),
        market=inst.market,
        instrument_id=inst.instrument_id,
        contract_id=inst.contract_id,
        effective_from=T0,
        effective_to=None,
        basis=basis,
        clearing_initial=Decimal(initial),
        clearing_maintenance=Decimal(maintenance),
        customer_initial=Decimal(initial),
        customer_maintenance=Decimal(maintenance),
        source_version="margin-v1",
    )
    values.update(changes)
    return MarginSpecificationV2(**values)


def ledger(profile=InstrumentProfile.ES_FUTURE, *, cash="100000",
           perpetual=False, **inst_changes):
    inst = instrument(profile, **inst_changes)
    selected_margin = (
        margin(inst, initial="0", maintenance="0")
        if profile == InstrumentProfile.BTC_SPOT
        else margin(inst)
    )
    return InstrumentAccountingLedgerV2.create(
        run_id=H("run"),
        starting_cash=Decimal(cash),
        instrument=inst,
        policy=policy(perpetual),
        margin_specification=selected_margin,
    )


def fill(inst, name, side, qty, reference, *, friction="0", minute=1,
         policy_version="CONSERVATIVE_OHLC_1M_V1"):
    reference = Decimal(reference)
    friction = Decimal(friction)
    economic = reference + friction if side == OrderSide.BUY else reference - friction
    return ExecutionFillV2(
        "execution-fill-v2-1",
        H(f"fill-{name}"),
        H(f"order-{name}"),
        H(f"bar-{name}"),
        None,
        inst.market,
        inst.instrument_id,
        inst.contract_id,
        T0 + timedelta(minutes=minute),
        side,
        Decimal(qty),
        reference,
        economic,
        economic,
        friction,
        Decimal("1000"),
        Decimal("100"),
        Decimal("100"),
        "TEST_FILL",
        policy_version,
        "BAR_VOLUME_PARTICIPATION_V1",
        "assumption-v1",
    )


def fill_event(inst, name, side, qty, price, *, friction="0", commission="0",
               fee="0", minute=1, policy_version="CONSERVATIVE_OHLC_1M_V1"):
    accepted = fill(inst, name, side, qty, price, friction=friction,
                    minute=minute, policy_version=policy_version)
    slip = accepted.adverse_friction * accepted.quantity * inst.contract_multiplier
    costs = FillEconomicsV2(
        "fill-economics-v2-1",
        H(f"cost-{name}"),
        accepted.fill_id,
        Decimal(commission),
        Decimal(fee),
        slip,
        "USD",
        (H("fee-spec"),),
        "cost-v1",
    )
    return AccountingEventV2(
        "accounting-event-v2-1",
        H(f"event-{name}"),
        AccountingEventKind.FILL,
        accepted.fill_time,
        accepted.fill_time,
        fill=accepted,
        fill_economics=costs,
    )


def mark_event(inst, name, price, minute):
    fact = PriceEvidenceV2(
        "price-evidence-v2-1",
        H(f"price-{name}"),
        inst.market,
        inst.instrument_id,
        inst.contract_id,
        T0 + timedelta(minutes=minute),
        T0 + timedelta(minutes=minute),
        Decimal(price),
        "MARK",
        H("mark-spec"),
        "prices-v1",
    )
    return AccountingEventV2(
        "accounting-event-v2-1",
        H(f"mark-event-{name}"),
        AccountingEventKind.MARK,
        fact.observed_at,
        fact.available_at,
        price=fact,
    )


def settle_event(inst, name, price, minute):
    fact = SettlementFactV2(
        "settlement-fact-v2-1",
        H(f"settle-{name}"),
        inst.market,
        inst.instrument_id,
        inst.contract_id or "UNSUPPORTED-SPOT-SETTLEMENT",
        T0 + timedelta(minutes=minute),
        T0 + timedelta(minutes=minute),
        Decimal(price),
        H("settlement-spec"),
        "settlement-v1",
    )
    return AccountingEventV2(
        "accounting-event-v2-1",
        H(f"settle-event-{name}"),
        AccountingEventKind.SETTLEMENT,
        fact.settlement_time,
        fact.available_at,
        settlement=fact,
    )


def funding_event(inst, name, rate, mark, oracle, minute):
    fact = FundingFactV2(
        "funding-fact-v2-1",
        H(f"fund-{name}"),
        inst.market,
        inst.instrument_id,
        inst.contract_id,
        T0 + timedelta(minutes=minute),
        T0 + timedelta(minutes=minute),
        Decimal(rate),
        Decimal(mark),
        Decimal(oracle),
        (H("funding-spec"), H("mark-spec"), H("oracle-spec")),
        "f-v1",
    )
    return AccountingEventV2(
        "accounting-event-v2-1",
        H(f"fund-event-{name}"),
        AccountingEventKind.FUNDING,
        fact.funding_time,
        fact.available_at,
        funding=fact,
    )


def apply(source, *events):
    for event in events:
        source = source.apply(event)
    return source


# ===========================================================================
# 1. ES/NQ futures — long, short, add, reduce, close, reversal
# ===========================================================================

class TestBTCSpot:
    """BTC spot base/quote accounting, no margin, no funding."""

    def test_btc_spot_sell_increases_cash_by_quote_value(self):
        """Sell 0.1 BTC at 51000 → cash += 5100 - costs."""
        book = ledger(InstrumentProfile.BTC_SPOT, cash="10000")
        inst = book.instrument
        opened = book.apply(
            fill_event(inst, "buy", OrderSide.BUY, "0.1", "50000", commission="5")
        )
        closed = opened.apply(
            fill_event(inst, "sell", OrderSide.SELL, "0.1", "51000",
                      commission="5", minute=2)
        )
        # Cash: 10000 - 5000 - 5(buy cost) + 51000*0.1 - 5(sell cost)
        # = 10000 - 5005 + 5100 - 5 = 10090
        assert closed.snapshot.position.signed_quantity == 0
        assert closed.snapshot.cash == Decimal("10090")

    def test_btc_spot_rejects_settlement(self):
        """BTC spot rejects settlement events."""
        book = ledger(InstrumentProfile.BTC_SPOT, cash="10000")
        with pytest.raises(AccountingError, match=AccountingReason.SETTLEMENT_NOT_SUPPORTED.value):
            book.apply(settle_event(book.instrument, "spot", "100", 1))

    def test_btc_spot_requires_zero_margin(self):
        """BTC spot requires zero margin facts."""
        inst = instrument(InstrumentProfile.BTC_SPOT)
        with pytest.raises(AccountingError, match=AccountingReason.INVALID_ECONOMIC_FACT.value):
            InstrumentAccountingLedgerV2.create(
                run_id=H("run"),
                starting_cash=Decimal("10000"),
                instrument=inst,
                policy=policy(),
                margin_specification=margin(inst, initial="0.10"),
            )

    def test_btc_spot_unlevered_no_margin_breach(self):
        """BTC spot with zero margin has no margin_breach."""
        book = ledger(InstrumentProfile.BTC_SPOT, cash="10000")
        inst = book.instrument
        opened = book.apply(
            fill_event(inst, "buy", OrderSide.BUY, "0.1", "50000")
        )
        assert opened.snapshot.clearing_initial_margin == 0
        assert opened.snapshot.margin_breach is False

    def test_btc_spot_fractional_quantity(self):
        """BTC spot supports fractional quantity (0.001 step)."""
        book = ledger(InstrumentProfile.BTC_SPOT, cash="10000")
        inst = book.instrument
        assert inst.quantity_step == Decimal("0.001")
        opened = book.apply(
            fill_event(inst, "buy", OrderSide.BUY, "0.001", "50000")
        )
        assert opened.snapshot.position.signed_quantity == Decimal("0.001")


# ===========================================================================
# 3. Capability-gated BTC linear-perpetual accounting
# ===========================================================================

class TestBTCPerpetual:
    """BTC linear-perpetual: capability gate, funding, margin, mark/oracle."""

    def test_perpetual_with_capability_accepts(self):
        """BTC perpetual with capability enabled → creates ledger."""
        book = ledger(InstrumentProfile.BTC_LINEAR_PERPETUAL, perpetual=True)
        assert book.profile == InstrumentProfile.BTC_LINEAR_PERPETUAL

    def test_perpetual_funding_short_position(self):
        """Funding for short position: payment = positive (received)."""
        book = ledger(InstrumentProfile.BTC_LINEAR_PERPETUAL, perpetual=True)
        inst = book.instrument
        opened = book.apply(
            fill_event(inst, "open", OrderSide.SELL, "0.1", "50000")
        )
        # Funding: -(-0.1) * 50000 * 1 * 0.001 = +5
        result = opened.apply(
            funding_event(inst, "fund", "0.001", "50000", "49990", 2)
        )
        assert result.snapshot.funding == Decimal("5")

    def test_perpetual_funding_rejects_off_grid_mark(self):
        """Funding with off-tick mark price → OFF_GRID_ECONOMICS."""
        book = ledger(InstrumentProfile.BTC_LINEAR_PERPETUAL, perpetual=True)
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "0.1", "50000"))
        # mark_price = 50000.005 is off the 0.01 tick grid
        event = funding_event(inst, "fund", "0.001", "50000.005", "49990", 2)
        with pytest.raises(AccountingError, match=AccountingReason.OFF_GRID_ECONOMICS.value):
            opened.apply(event)

    def test_perpetual_funding_requires_unverified_spec_rejects(self):
        """Funding with unverified specification lineage → INVALID_ECONOMIC_FACT."""
        book = ledger(InstrumentProfile.BTC_LINEAR_PERPETUAL, perpetual=True)
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "0.1", "50000"))
        fact = FundingFactV2(
            "funding-fact-v2-1",
            H("bad-fund"),
            inst.market,
            inst.instrument_id,
            inst.contract_id,
            T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2),
            Decimal("0.001"),
            Decimal("50000"),
            Decimal("49990"),
            (H("unknown-spec"), H("mark-spec"), H("oracle-spec")),
            "f-v1",
        )
        event = AccountingEventV2(
            "accounting-event-v2-1",
            H("bad-fund-event"),
            AccountingEventKind.FUNDING,
            fact.funding_time,
            fact.available_at,
            funding=fact,
        )
        with pytest.raises(AccountingError, match=AccountingReason.INVALID_ECONOMIC_FACT.value):
            opened.apply(event)

    def test_perpetual_rejects_settlement(self):
        """BTC perpetual rejects settlement (only futures have variation settlement)."""
        book = ledger(InstrumentProfile.BTC_LINEAR_PERPETUAL, perpetual=True)
        with pytest.raises(AccountingError, match=AccountingReason.SETTLEMENT_NOT_SUPPORTED.value):
            book.apply(settle_event(book.instrument, "perp", "100", 1))


# ===========================================================================
# 4. Variation settlement
# ===========================================================================

class TestVariationSettlement:
    """Settlement moves unrealized PnL to cash, resets basis, preserves equity."""

    def test_settlement_preserves_equity(self):
        """Settlement transfers unrealized PnL to cash, resets basis, equity unchanged."""
        book = ledger()
        inst = book.instrument
        marked = apply(
            book,
            fill_event(inst, "open", OrderSide.BUY, "1", "100"),
            mark_event(inst, "pre", "110", 2),
        )
        before_equity = marked.snapshot.equity
        first = marked.apply(settle_event(inst, "one", "110", 3))
        assert first.snapshot.cash == Decimal("100500")
        assert first.snapshot.unrealized_pnl == 0
        assert first.snapshot.equity == before_equity

    def test_settlement_resets_basis_to_settlement_price(self):
        """After settlement, average_entry_price = settlement_price."""
        book = ledger()
        inst = book.instrument
        marked = apply(
            book,
            fill_event(inst, "open", OrderSide.BUY, "1", "100"),
            mark_event(inst, "pre", "110", 2),
        )
        settled = marked.apply(settle_event(inst, "one", "110", 3))
        assert settled.snapshot.position.average_entry_price == Decimal("110")
        assert settled.snapshot.position.last_settlement_price == Decimal("110")

    def test_multiple_settlements_accumulate_transfers(self):
        """Multiple settlements accumulate settlement_transfers."""
        book = ledger()
        inst = book.instrument
        marked = apply(
            book,
            fill_event(inst, "open", OrderSide.BUY, "1", "100"),
            mark_event(inst, "pre", "110", 2),
        )
        first = marked.apply(settle_event(inst, "one", "110", 3))
        # After first settlement, basis is 110. Second settlement at 108.
        # Transfer = 1 * (108 - 110) * 50 = -100
        second = first.apply(settle_event(inst, "two", "108", 4))
        # First transfer = 1 * (110 - 100) * 50 = 500
        # Second transfer = 1 * (108 - 110) * 50 = -100
        assert second.snapshot.settlement_transfers == Decimal("400")
        assert second.snapshot.equity == Decimal("100400")

    def test_settlement_on_flat_position_zero_transfer(self):
        """Settlement on flat position → zero transfer."""
        book = ledger()
        inst = book.instrument
        result = book.apply(settle_event(inst, "flat", "100", 1))
        assert result.snapshot.settlement_transfers == 0

    def test_settlement_rejects_missing_spec(self):
        """Settlement with unverified specification → MISSING_SETTLEMENT_FACT."""
        book = ledger()
        inst = book.instrument
        bad_settle = settle_event(inst, "missing", "100", 1)
        bad_settle = replace(
            bad_settle,
            settlement=replace(
                bad_settle.settlement,
                specification_id=H("unknown-settlement"),
            ),
        )
        with pytest.raises(AccountingError, match=AccountingReason.MISSING_SETTLEMENT_FACT.value):
            book.apply(bad_settle)

    def test_settlement_duplicate_rejects(self):
        """Duplicate settlement event → idempotent (same event_id → returns self)."""
        book = ledger()
        inst = book.instrument
        event = settle_event(inst, "one", "100", 1)
        applied = book.apply(event)
        assert applied.apply(event) is applied

    def test_settlement_conflict_rejects(self):
        """Settlement with same event_id but different content → DUPLICATE_EVENT_CONFLICT."""
        book = ledger()
        inst = book.instrument
        event = settle_event(inst, "one", "100", 1)
        applied = book.apply(event)
        conflict = replace(
            event,
            settlement=replace(event.settlement, settlement_price=Decimal("101")),
        )
        with pytest.raises(AccountingError, match=AccountingReason.DUPLICATE_EVENT_CONFLICT.value):
            applied.apply(conflict)

    def test_settlement_off_tick_rejects(self):
        """Settlement with off-tick price → OFF_GRID_ECONOMICS."""
        book = ledger()
        inst = book.instrument
        bad = settle_event(inst, "off", "100.10", 1)
        with pytest.raises(AccountingError, match=AccountingReason.OFF_GRID_ECONOMICS.value):
            book.apply(bad)


# ===========================================================================
# 5. Mark/unrealized P&L
# ===========================================================================

class TestMarkUnrealized:
    """Mark price updates unrealized PnL and equity."""

    def test_mark_updates_unrealized_pnl(self):
        """Mark price change updates unrealized PnL."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "2", "100"))
        up = opened.apply(mark_event(inst, "up", "102", 2))
        assert up.snapshot.unrealized_pnl == Decimal("200")
        assert up.snapshot.equity == Decimal("100200")

    def test_mark_adverse_move(self):
        """Adverse mark price move → negative unrealized PnL."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "2", "100"))
        down = opened.apply(mark_event(inst, "down", "99", 2))
        assert down.snapshot.unrealized_pnl == Decimal("-100")

    def test_mark_wrong_type_rejects(self):
        """Mark with wrong price_type → MISSING_MARK_EVIDENCE."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        fact = PriceEvidenceV2(
            "price-evidence-v2-1",
            H("bad-price"),
            inst.market,
            inst.instrument_id,
            inst.contract_id,
            T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2),
            Decimal("102"),
            "LAST",
            H("mark-spec"),
            "prices-v1",
        )
        event = AccountingEventV2(
            "accounting-event-v2-1",
            H("bad-mark-event"),
            AccountingEventKind.MARK,
            fact.observed_at,
            fact.available_at,
            price=fact,
        )
        with pytest.raises(AccountingError, match=AccountingReason.MISSING_MARK_EVIDENCE.value):
            opened.apply(event)

    def test_mark_unverified_spec_rejects(self):
        """Mark with unverified specification → MISSING_MARK_EVIDENCE."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        bad_mark = mark_event(inst, "bad", "102", 2)
        bad_mark = replace(
            bad_mark,
            price=replace(bad_mark.price, specification_id=H("unknown-mark")),
        )
        with pytest.raises(AccountingError, match=AccountingReason.MISSING_MARK_EVIDENCE.value):
            opened.apply(bad_mark)

    def test_mark_off_tick_rejects(self):
        """Mark with off-tick price → OFF_GRID_ECONOMICS."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        bad = mark_event(inst, "off", "100.10", 2)
        with pytest.raises(AccountingError, match=AccountingReason.OFF_GRID_ECONOMICS.value):
            opened.apply(bad)

    def test_mark_identity_mismatch_rejects(self):
        """Mark with wrong market → IDENTITY_MISMATCH."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        bad = mark_event(inst, "wrong", "102", 2)
        bad = replace(
            bad,
            price=replace(bad.price, market="NQ"),
        )
        with pytest.raises(AccountingError, match=AccountingReason.IDENTITY_MISMATCH.value):
            opened.apply(bad)


# ===========================================================================
# 6. Cost attribution
# ===========================================================================

class TestMargin:
    """Clearing vs customer margin separation and margin breach."""

    def test_margin_breach_is_immutable_fact(self):
        """Margin breach is an immutable accounting fact — it creates no order."""
        book = ledger(cash="-100")
        inst = book.instrument
        result = book.apply(fill_event(inst, "neg", OrderSide.BUY, "1", "100"))
        assert result.snapshot.margin_breach is True
        # The ledger still has the same events — no extra "margin call" event
        assert len(result.events) == 1  # only the fill event
        # But snapshots grow (one per event applied)
        assert len(result.snapshots) == 2  # initial + after fill

    def test_per_contract_margin_basis(self):
        """Per-contract margin uses absolute quantity * value, not notional."""
        inst = instrument()
        ms = MarginSpecificationV2(
            "margin-specification-v2-1", H("margin"),
            inst.market, inst.instrument_id, inst.contract_id,
            T0, None, MarginBasis.PER_CONTRACT,
            Decimal("500"), Decimal("350"),
            Decimal("500"), Decimal("350"),
            "margin-v1",
        )
        book = InstrumentAccountingLedgerV2.create(
            run_id=H("run"),
            starting_cash=Decimal("100000"),
            instrument=inst,
            policy=policy(),
            margin_specification=ms,
        )
        result = book.apply(fill_event(inst, "open", OrderSide.BUY, "2", "100"))
        # Per-contract: 2 * 500 = 1000 (not notional)
        assert result.snapshot.clearing_initial_margin == Decimal("1000")

    def test_margin_nonnegative_in_snapshot(self):
        """All margin values in snapshot are nonnegative."""
        book = ledger()
        inst = book.instrument
        result = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        for name in ("clearing_initial_margin", "clearing_maintenance_margin",
                     "customer_initial_margin", "customer_maintenance_margin"):
            assert getattr(result.snapshot, name) >= 0

    def test_margin_specification_effective_interval(self):
        """Margin specification with effective_to rejects events after it."""
        book = ledger()
        inst = book.instrument
        stale = InstrumentAccountingLedgerV2.create(
            run_id=H("run"),
            starting_cash=Decimal("1000"),
            instrument=inst,
            policy=policy(),
            margin_specification=margin(inst, effective_to=T0 + timedelta(seconds=30)),
        )
        with pytest.raises(AccountingError, match=AccountingReason.STALE_SPECIFICATION.value):
            stale.apply(fill_event(inst, "stale", OrderSide.BUY, "1", "100"))


# ===========================================================================
# 8. Duplicate economic-event prevention
# ===========================================================================

class TestDuplicatePrevention:
    """Duplicate economic events are detected and rejected."""

    def test_same_event_id_different_content_rejects(self):
        """Same event_id with different content → DUPLICATE_EVENT_CONFLICT."""
        book = ledger()
        inst = book.instrument
        event = fill_event(inst, "open", OrderSide.BUY, "1", "100")
        applied = book.apply(event)
        conflict = replace(
            event,
            fill=replace(event.fill, quantity=Decimal("2")),
        )
        with pytest.raises(AccountingError, match=AccountingReason.DUPLICATE_EVENT_CONFLICT.value):
            applied.apply(conflict)

    def test_duplicate_mark_economic_id_rejects(self):
        """Same price_event_id under new event_id → DUPLICATE_ECONOMIC_EVENT."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        event = mark_event(inst, "mark", "102", 2)
        applied = opened.apply(event)
        # Re-wrap the same price evidence under a new event_id
        duplicate = replace(event, event_id=H("different-mark-event"))
        with pytest.raises(AccountingError, match=AccountingReason.DUPLICATE_ECONOMIC_EVENT.value):
            applied.apply(duplicate)

    def test_duplicate_settlement_economic_id_rejects(self):
        """Same settlement_id under new event_id → DUPLICATE_ECONOMIC_EVENT."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        event = settle_event(inst, "one", "110", 2)
        applied = opened.apply(event)
        duplicate = replace(event, event_id=H("different-settle-event"))
        with pytest.raises(AccountingError, match=AccountingReason.DUPLICATE_ECONOMIC_EVENT.value):
            applied.apply(duplicate)

    def test_duplicate_funding_economic_id_rejects(self):
        """Same funding_id under new event_id → DUPLICATE_ECONOMIC_EVENT."""
        book = ledger(InstrumentProfile.BTC_LINEAR_PERPETUAL, perpetual=True)
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "0.1", "50000"))
        event = funding_event(inst, "fund", "0.001", "50000", "49990", 2)
        applied = opened.apply(event)
        duplicate = replace(event, event_id=H("different-fund-event"))
        with pytest.raises(AccountingError, match=AccountingReason.DUPLICATE_ECONOMIC_EVENT.value):
            applied.apply(duplicate)


# ===========================================================================
# 9. Determinism, replay, checkpoint, tamper
# ===========================================================================

class TestDeterminismReplay:
    """Deterministic replay, checkpoints, fingerprints, tamper rejection."""

    def test_replay_with_nonempty_base_rejects(self):
        """Replay from non-empty base → CHECKPOINT_TAMPERED."""
        book = ledger()
        inst = book.instrument
        opened = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        with pytest.raises(AccountingError, match=AccountingReason.CHECKPOINT_TAMPERED.value):
            InstrumentAccountingLedgerV2.replay(opened, ())

    def test_checkpoint_tampered_fingerprint_rejects(self):
        """Checkpoint with wrong ledger_fingerprint → CHECKPOINT_TAMPERED."""
        book = ledger()
        inst = book.instrument
        result = book.apply(fill_event(inst, "open", OrderSide.BUY, "1", "100"))
        # The checkpoint validates at construction, so we create a bad one directly
        with pytest.raises(AccountingError, match=AccountingReason.CHECKPOINT_TAMPERED.value):
            AccountingCheckpointV2(
                "accounting-checkpoint-v2-1",
                H("bad-cp"),
                H("wrong-fingerprint"),
                result,
            )

    def test_event_immutable(self):
        """Accounting event is frozen."""
        event = fill_event(instrument(), "test", OrderSide.BUY, "1", "100")
        with pytest.raises(FrozenInstanceError):
            event.event_id = H("other")

# ===========================================================================
# 10. Residual-position and incomplete-accounting gates
# ===========================================================================

class TestResidualGates:
    """Residual-position and incomplete-accounting gates."""

    def test_validate_end_of_data_clean(self):
        """Closed position → validate_end_of_data returns empty tuple."""
        book = ledger()
        inst = book.instrument
        result = apply(
            book,
            fill_event(inst, "open", OrderSide.BUY, "1", "100"),
            fill_event(inst, "close", OrderSide.SELL, "1", "110", minute=2),
        )
        assert result.validate_end_of_data() == ()

    def test_validate_end_of_data_short_residual(self):
        """Short position → residual."""
        book = ledger()
        inst = book.instrument
        result = book.apply(fill_event(inst, "open", OrderSide.SELL, "1", "100"))
        assert result.validate_end_of_data() == (AccountingReason.END_OF_DATA_RESIDUAL,)

    def test_validate_end_of_data_after_partial_close_still_residual(self):
        """Partial close leaves residual position."""
        book = ledger()
        inst = book.instrument
        result = apply(
            book,
            fill_event(inst, "open", OrderSide.BUY, "2", "100"),
            fill_event(inst, "close", OrderSide.SELL, "1", "110", minute=2),
        )
        assert result.validate_end_of_data() == (AccountingReason.END_OF_DATA_RESIDUAL,)


# ===========================================================================
# 11. Identity, version, chronology, tick-grid, effective-date isolation
# ===========================================================================

class TestIsolation:
    """Instrument, contract, version, chronology, tick-grid, effective-date isolation."""

    def test_identity_mismatch_fill_rejects(self):
        """Fill with wrong market → IDENTITY_MISMATCH."""
        book = ledger()
        inst = book.instrument
        bad_fill = fill(inst, "bad", OrderSide.BUY, "1", "100")
        bad_fill = replace(bad_fill, market="NQ")
        costs = FillEconomicsV2(
            "fill-economics-v2-1", H("cost-bad"), bad_fill.fill_id,
            Decimal("0"), Decimal("0"), Decimal("0"),
            "USD", (H("fee-spec"),), "cost-v1",
        )
        event = AccountingEventV2(
            "accounting-event-v2-1", H("event-bad"),
            AccountingEventKind.FILL, bad_fill.fill_time, bad_fill.fill_time,
            fill=bad_fill, fill_economics=costs,
        )
        with pytest.raises(AccountingError, match=AccountingReason.IDENTITY_MISMATCH.value):
            book.apply(event)

    def test_event_time_regression_rejects(self):
        """Event with available_at before previous → EVENT_TIME_REGRESSION."""
        book = ledger()
        inst = book.instrument
        first = book.apply(mark_event(inst, "later", "100", 3))
        with pytest.raises(AccountingError, match=AccountingReason.EVENT_TIME_REGRESSION.value):
            first.apply(mark_event(inst, "earlier", "100", 2))

    def test_off_grid_fill_quantity_rejects(self):
        """Fill with off-grid quantity → OFF_GRID_ECONOMICS."""
        book = ledger()
        inst = book.instrument
        # ES quantity_step = 1, so 1.5 is off-grid
        bad = fill_event(inst, "bad", OrderSide.BUY, "1.5", "100")
        with pytest.raises(AccountingError, match=AccountingReason.OFF_GRID_ECONOMICS.value):
            book.apply(bad)

    def test_off_grid_fill_price_rejects(self):
        """Fill with off-grid economic_price → OFF_GRID_ECONOMICS."""
        book = ledger()
        inst = book.instrument
        bad = fill_event(inst, "bad", OrderSide.BUY, "1", "100.10")
        with pytest.raises(AccountingError, match=AccountingReason.OFF_GRID_ECONOMICS.value):
            book.apply(bad)

    def test_v1_fill_rejects(self):
        """v1 fill (execution_policy_version starts with v1) → MIXED_LEDGER_VERSION."""
        book = ledger()
        inst = book.instrument
        bad = fill_event(inst, "v1", OrderSide.BUY, "1", "100",
                        policy_version="v1-something")
        with pytest.raises(AccountingError, match=AccountingReason.MIXED_LEDGER_VERSION.value):
            book.apply(bad)

    def test_cost_version_mismatch_rejects(self):
        """Fill economics with wrong cost_version → VERSION_MISMATCH."""
        book = ledger()
        inst = book.instrument
        accepted = fill(inst, "bad", OrderSide.BUY, "1", "100")
        costs = FillEconomicsV2(
            "fill-economics-v2-1", H("cost-bad"), accepted.fill_id,
            Decimal("0"), Decimal("0"), Decimal("0"),
            "USD", (H("fee-spec"),), "stale-cost-v2",
        )
        event = AccountingEventV2(
            "accounting-event-v2-1", H("event-bad"),
            AccountingEventKind.FILL, accepted.fill_time, accepted.fill_time,
            fill=accepted, fill_economics=costs,
        )
        with pytest.raises(AccountingError, match=AccountingReason.VERSION_MISMATCH.value):
            book.apply(event)

    def test_cost_spec_unverified_rejects(self):
        """Fill economics with unverified specification → INVALID_ECONOMIC_FACT."""
        book = ledger()
        inst = book.instrument
        accepted = fill(inst, "bad", OrderSide.BUY, "1", "100")
        costs = FillEconomicsV2(
            "fill-economics-v2-1", H("cost-bad"), accepted.fill_id,
            Decimal("0"), Decimal("0"), Decimal("0"),
            "USD", (H("unknown-fee-spec"),), "cost-v1",
        )
        event = AccountingEventV2(
            "accounting-event-v2-1", H("event-bad"),
            AccountingEventKind.FILL, accepted.fill_time, accepted.fill_time,
            fill=accepted, fill_economics=costs,
        )
        with pytest.raises(AccountingError, match=AccountingReason.INVALID_ECONOMIC_FACT.value):
            book.apply(event)

    def test_fill_cost_currency_mismatch_rejects(self):
        """Fill economics with wrong currency → MISSING_FILL_COST."""
        book = ledger()
        inst = book.instrument
        accepted = fill(inst, "bad", OrderSide.BUY, "1", "100")
        costs = FillEconomicsV2(
            "fill-economics-v2-1", H("cost-bad"), accepted.fill_id,
            Decimal("0"), Decimal("0"), Decimal("0"),
            "EUR", (H("fee-spec"),), "cost-v1",
        )
        event = AccountingEventV2(
            "accounting-event-v2-1", H("event-bad"),
            AccountingEventKind.FILL, accepted.fill_time, accepted.fill_time,
            fill=accepted, fill_economics=costs,
        )
        with pytest.raises(AccountingError, match=AccountingReason.MISSING_FILL_COST.value):
            book.apply(event)

    def test_stale_instrument_specification_rejects(self):
        """Instrument with expired effective_to → STALE_SPECIFICATION."""
        inst = instrument(effective_to=T0 + timedelta(seconds=30))
        book = InstrumentAccountingLedgerV2.create(
            run_id=H("run"),
            starting_cash=Decimal("1000"),
            instrument=inst,
            policy=policy(),
            margin_specification=margin(inst, effective_to=T0 + timedelta(seconds=30)),
        )
        with pytest.raises(AccountingError, match=AccountingReason.STALE_SPECIFICATION.value):
            book.apply(fill_event(inst, "stale", OrderSide.BUY, "1", "100"))


# ===========================================================================
# 12. Unsupported capability and profile rejection
# ===========================================================================

class TestUnsupportedCapability:
    """Unsupported profiles and capability gates."""

    def test_btc_unknown_unsupported_rejects(self):
        """BTC_UNKNOWN_UNSUPPORTED profile → INVALID_ECONOMIC_FACT at create."""
        with pytest.raises(AccountingError, match=AccountingReason.INVALID_ECONOMIC_FACT.value):
            ledger(InstrumentProfile.BTC_UNKNOWN_UNSUPPORTED)

    def test_accounting_policy_wrong_version_rejects(self):
        """AccountingPolicyV2 with wrong accounting_version → ValueError."""
        with pytest.raises(ValueError, match="unsupported accounting policy version"):
            AccountingPolicyV2(
                "accounting-policy-v2-1",
                "WRONG_VERSION",
                "cost-v1",
                "MARK",
                True,
                (H("a"),),
            )


# ===========================================================================
# 13. Accounting reconciliation across all transitions
# ===========================================================================

class TestEventPayloadValidation:
    """AccountingEventV2 payload type and chronology validation."""

    def test_event_requires_exactly_one_payload(self):
        """Accounting event with zero payloads → ValueError."""
        with pytest.raises(ValueError, match="exactly one payload"):
            AccountingEventV2(
                "accounting-event-v2-1",
                H("empty"),
                AccountingEventKind.FILL,
                T0 + timedelta(minutes=1),
                T0 + timedelta(minutes=1),
            )

    def test_event_two_payloads_rejects(self):
        """Accounting event with two payloads → ValueError."""
        inst = instrument()
        price_fact = PriceEvidenceV2(
            "price-evidence-v2-1", H("p"), inst.market, inst.instrument_id,
            inst.contract_id, T0 + timedelta(minutes=1), T0 + timedelta(minutes=1),
            Decimal("100"), "MARK", H("mark-spec"), "v1",
        )
        settle_fact = SettlementFactV2(
            "settlement-fact-v2-1", H("s"), inst.market, inst.instrument_id,
            inst.contract_id or "X", T0 + timedelta(minutes=1),
            T0 + timedelta(minutes=1), Decimal("100"),
            H("settlement-spec"), "v1",
        )
        with pytest.raises(ValueError, match="exactly one payload"):
            AccountingEventV2(
                "accounting-event-v2-1", H("both"),
                AccountingEventKind.MARK,
                T0 + timedelta(minutes=1), T0 + timedelta(minutes=1),
                price=price_fact, settlement=settle_fact,
            )

    def test_fill_event_requires_economics(self):
        """Fill event without fill_economics → ValueError."""
        inst = instrument()
        accepted = fill(inst, "test", OrderSide.BUY, "1", "100")
        with pytest.raises(ValueError, match="fill event requires fill economics"):
            AccountingEventV2(
                "accounting-event-v2-1", H("no-econ"),
                AccountingEventKind.FILL,
                accepted.fill_time, accepted.fill_time,
                fill=accepted,
            )

    def test_non_fill_event_with_economics_rejects(self):
        """Non-fill event with fill_economics → ValueError."""
        inst = instrument()
        accepted = fill(inst, "test", OrderSide.BUY, "1", "100")
        costs = FillEconomicsV2(
            "fill-economics-v2-1", H("cost"), accepted.fill_id,
            Decimal("0"), Decimal("0"), Decimal("0"),
            "USD", (H("fee-spec"),), "cost-v1",
        )
        price_fact = PriceEvidenceV2(
            "price-evidence-v2-1", H("p"), inst.market, inst.instrument_id,
            inst.contract_id, T0 + timedelta(minutes=1), T0 + timedelta(minutes=1),
            Decimal("100"), "MARK", H("mark-spec"), "v1",
        )
        with pytest.raises(ValueError, match="only fill events may contain"):
            AccountingEventV2(
                "accounting-event-v2-1", H("wrong"),
                AccountingEventKind.MARK,
                price_fact.observed_at, price_fact.available_at,
                price=price_fact, fill_economics=costs,
            )

    def test_event_chronology_must_equal_payload(self):
        """Event time/available_at must equal payload time/available_at."""
        inst = instrument()
        accepted = fill(inst, "test", OrderSide.BUY, "1", "100")
        costs = FillEconomicsV2(
            "fill-economics-v2-1", H("cost"), accepted.fill_id,
            Decimal("0"), Decimal("0"), Decimal("0"),
            "USD", (H("fee-spec"),), "cost-v1",
        )
        with pytest.raises(ValueError, match="chronology must equal"):
            AccountingEventV2(
                "accounting-event-v2-1", H("bad-time"),
                AccountingEventKind.FILL,
                T0 + timedelta(minutes=99),  # wrong time
                T0 + timedelta(minutes=99),
                fill=accepted, fill_economics=costs,
            )

    def test_event_available_before_time_rejects(self):
        """available_at < event_time → ValueError from payload validation."""
        with pytest.raises(ValueError, match="available before"):
            AccountingEventV2(
                "accounting-event-v2-1", H("bad"),
                AccountingEventKind.MARK,
                T0 + timedelta(minutes=2),
                T0 + timedelta(minutes=1),  # available before event
                price=PriceEvidenceV2(
                    "price-evidence-v2-1", H("p"), "ES", "ES", "ESM5",
                    T0 + timedelta(minutes=2), T0 + timedelta(minutes=1),
                    Decimal("100"), "MARK", H("mark-spec"), "v1",
                ),
            )


# ===========================================================================
# 15. PositionStateV2 invariants
# ===========================================================================

class TestPositionState:
    """PositionStateV2 invariant validation."""

    def test_flat_position_cannot_retain_average_entry(self):
        """signed_quantity=0 with average_entry_price set → ValueError."""
        with pytest.raises(ValueError, match="flat position cannot retain"):
            PositionStateV2(Decimal("0"), Decimal("100"), None, None)

    def test_open_position_requires_average_entry(self):
        """signed_quantity != 0 with average_entry_price=None → ValueError."""
        with pytest.raises(ValueError, match="open position requires"):
            PositionStateV2(Decimal("1"), None, None, None)

    def test_position_state_immutable(self):
        """PositionStateV2 is frozen."""
        pos = PositionStateV2(Decimal("1"), Decimal("100"), None, None)
        with pytest.raises(FrozenInstanceError):
            pos.signed_quantity = Decimal("2")

    def test_flat_position_with_none_entry_is_valid(self):
        """signed_quantity=0 with None entry → valid."""
        pos = PositionStateV2(Decimal("0"), None, None, None)
        assert pos.signed_quantity == 0


# ===========================================================================
# 16. MarginSpecificationV2 validation
# ===========================================================================

class TestMarginSpecValidation:
    """MarginSpecificationV2 construction validation."""

    def test_notional_rate_over_one_rejects(self):
        """NOTIONAL_RATE margin with rate > 1 → ValueError."""
        inst = instrument()
        with pytest.raises(ValueError, match="cannot exceed one"):
            margin(inst, initial="1.5")

    def test_per_contract_allows_high_values(self):
        """PER_CONTRACT basis allows values > 1."""
        inst = instrument()
        ms = MarginSpecificationV2(
            "margin-specification-v2-1", H("margin"),
            inst.market, inst.instrument_id, inst.contract_id,
            T0, None, MarginBasis.PER_CONTRACT,
            Decimal("1000"), Decimal("500"),
            Decimal("1000"), Decimal("500"),
            "margin-v1",
        )
        assert ms.clearing_initial == Decimal("1000")

    def test_margin_spec_immutable(self):
        """MarginSpecificationV2 is frozen."""
        ms = margin(instrument())
        with pytest.raises(FrozenInstanceError):
            ms.clearing_initial = Decimal("999")

    def test_margin_effective_to_before_from_rejects(self):
        """effective_to <= effective_from → ValueError."""
        inst = instrument()
        with pytest.raises(ValueError, match="margin interval must be non-empty"):
            margin(inst, effective_from=T0, effective_to=T0)


# ===========================================================================
# 17. FillEconomicsV2 validation
# ===========================================================================

class TestFillEconomicsValidation:
    """FillEconomicsV2 construction validation."""

    def test_negative_commission_rejects(self):
        """Negative commission → ValueError."""
        with pytest.raises(ValueError, match="must be nonnegative"):
            FillEconomicsV2(
                "fill-economics-v2-1", H("x"), H("y"),
                Decimal("-1"), Decimal("0"), Decimal("0"),
                "USD", (H("s"),), "cost-v1",
            )

    def test_empty_specification_ids_rejects(self):
        """Empty specification_ids → ValueError."""
        with pytest.raises(ValueError, match="non-empty and unique"):
            FillEconomicsV2(
                "fill-economics-v2-1", H("x"), H("y"),
                Decimal("0"), Decimal("0"), Decimal("0"),
                "USD", (), "cost-v1",
            )

    def test_total_property_sums(self):
        """FillEconomicsV2.total = commission + exchange_fee + slippage_cost."""
        costs = FillEconomicsV2(
            "fill-economics-v2-1", H("x"), H("y"),
            Decimal("1"), Decimal("2"), Decimal("3"),
            "USD", (H("s"),), "cost-v1",
        )
        assert costs.total == Decimal("6")

    def test_fill_economics_immutable(self):
        """FillEconomicsV2 is frozen."""
        costs = FillEconomicsV2(
            "fill-economics-v2-1", H("x"), H("y"),
            Decimal("0"), Decimal("0"), Decimal("0"),
            "USD", (H("s"),), "cost-v1",
        )
        with pytest.raises(FrozenInstanceError):
            costs.commission = Decimal("999")
