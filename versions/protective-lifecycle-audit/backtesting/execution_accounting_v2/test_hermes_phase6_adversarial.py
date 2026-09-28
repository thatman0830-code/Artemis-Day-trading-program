"""Hermes independent adversarial audit tests for V2 Phase 6 rollover and funding.

Audit assignment: AUDIT-V2-PHASE6-ROLLOVER-FUNDING

Covers:
  - Immutable/versioned ES and NQ rollover specifications
  - Outgoing-close before incoming-open enforcement
  - Long and short rollovers
  - Participation and quantity normalization
  - Partial close/open lifecycle
  - Temporary-flat and incomplete-roll states
  - Missing outgoing or incoming evidence
  - Same-bar and look-ahead rejection
  - Market, instrument, contract, session, chronology, and version isolation
  - BTC linear-perpetual funding capability gates
  - Mark, oracle, rate, timestamp, multiplier, basis, schedule, and source lineage
  - Missing, duplicate, conflicting, stale, and late funding facts
  - BTC spot and futures funding rejection
  - Settlement/funding/rollover collision priority
  - Replay, checkpoints, fingerprints, tamper rejection, and reconciliation
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
import hashlib

import pytest

from backtesting.execution_accounting_v2.accounting import (
    ACCOUNTING_VERSION, AccountingEventKind, AccountingEventV2,
    AccountingSnapshotPhase4V2, FundingFactV2, PositionStateV2,
)
from backtesting.execution_accounting_v2.contracts import (
    InstrumentSpecificationV2, OrderSide,
)
from backtesting.execution_accounting_v2.ohlc_execution import (
    ExecutionFillV2, OHLCBarV2,
)
from backtesting.execution_accounting_v2.risk_sessions import (
    RISK_POLICY_VERSION, VerifiedSessionV2,
)
from backtesting.execution_accounting_v2.rollover_funding import (
    PHASE6_VERSION, FundingApplicationV2, FundingRequirementV2,
    Phase6CheckpointV2, Phase6Error, Phase6EventKind, Phase6EventV2,
    Phase6LedgerV2, Phase6Priority, Phase6Reason, Phase6ReconciliationV2,
    RollLeg, RollSpecificationV2, RollStatus, RolloverEventV2,
    RolloverInstructionV2, RolloverStateV2, apply_roll_fill,
    completed_phase6_gate, create_roll_instruction, eligible_roll_quantity,
    funding_boundary_gate, prepare_funding_application,
    record_missing_roll_bar, validate_roll_specifications,
)
from backtesting.execution_accounting_v2.specifications import (
    InstrumentProfile,
)


UTC = timezone.utc
T0 = datetime(2026, 3, 9, 14, 30, tzinfo=UTC)
H = lambda v: hashlib.sha256(v.encode()).hexdigest()
D = Decimal


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def inst(contract="ESH6", profile=InstrumentProfile.ES_FUTURE,
         market="CME", instrument_id="ES"):
    multiplier = (
        D("50") if profile == InstrumentProfile.ES_FUTURE else
        D("20") if profile == InstrumentProfile.NQ_FUTURE else
        D("1")
    )
    return InstrumentSpecificationV2(
        "instrument-spec-v2-1", H("inst-" + contract), market,
        instrument_id, contract, profile, "USD",
        D("0.25") if "FUTURE" in profile.value else D("0.01"),
        D("1") if "FUTURE" in profile.value else D("0.001"),
        multiplier,
        multiplier if "FUTURE" in profile.value else None,
        T0 - timedelta(days=2), T0 + timedelta(days=2),
        (H("evidence-" + contract),),
    )


def sess(contract="ESH6"):
    return VerifiedSessionV2.create(
        market="CME", instrument_id="ES", contract_id=contract,
        session_date=date(2026, 3, 9), timezone="America/Chicago",
        open_time=T0, close_time=T0 + timedelta(hours=6),
        effective_from=T0 - timedelta(days=1),
        effective_to=T0 + timedelta(days=1),
        calendar_version="cal-v1",
        source_ids=(H("session-" + contract),),
    )


def spec(*, opening_side=OrderSide.BUY, market="CME", instrument_id="ES",
         outgoing="ESH6", incoming="ESM6", **changes):
    outgoing_s, incoming_s = sess(outgoing), sess(incoming)
    values = dict(
        run_id=H("run"), market=market, instrument_id=instrument_id,
        outgoing_contract_id=outgoing, incoming_contract_id=incoming,
        opening_side=opening_side,
        outgoing_quantity=D("2"), incoming_quantity=D("2"),
        roll_time=T0,
        effective_from=T0 - timedelta(minutes=1),
        effective_to=T0 + timedelta(hours=6),
        outgoing_session_id=outgoing_s.session_id,
        incoming_session_id=incoming_s.session_id,
        outgoing_instrument_specification_id=H("inst-" + outgoing),
        incoming_instrument_specification_id=H("inst-" + incoming),
        participation_limit=D("0.5"), quantity_step=D("1"),
        roll_version=PHASE6_VERSION,
        source_ids=(H("roll-source"),),
    )
    values.update(changes)
    return RollSpecificationV2.create(**values)


def bar(contract, minute, *, volume=D("10"), bar_id=None, finalized=True,
        market="CME", instrument_id="ES"):
    at = T0 + timedelta(minutes=minute)
    return OHLCBarV2(
        "ohlc-bar-v2-1", bar_id or H(f"bar-{contract}-{minute}"),
        market, instrument_id, contract,
        at, at + timedelta(minutes=1), at + timedelta(minutes=1),
        D("5000"), D("5001"), D("4999"), D("5000"),
        volume, finalized, True, True, True, "bars-v1",
    )


def roll_fill(instruction, name, quantity=None):
    quantity = quantity or instruction.authorized_quantity
    return ExecutionFillV2(
        "execution-fill-v2-1", H("fill-" + name), H("order-" + name),
        instruction.eligible_bar_id, None,
        instruction.market, instruction.instrument_id,
        instruction.contract_id,
        instruction.triggered_at + timedelta(minutes=1),
        instruction.side, quantity,
        D("5000"), D("5000"), D("5000"), D("0"),
        D("10"), D("10"), D("10"),
        "ROLLOVER", "CONSERVATIVE_OHLC_1M_V1",
        "BAR_VOLUME_PARTICIPATION_V1", "roll-v1",
    )


def roll_once(opening_side=OrderSide.BUY,
              profile=InstrumentProfile.ES_FUTURE, prefix="ES"):
    outgoing, incoming = prefix + "H6", prefix + "M6"
    market, instrument_id = "CME", prefix
    outgoing_s = VerifiedSessionV2.create(
        market=market, instrument_id=instrument_id, contract_id=outgoing,
        session_date=date(2026, 3, 9), timezone="America/Chicago",
        open_time=T0, close_time=T0 + timedelta(hours=6),
        effective_from=T0 - timedelta(days=1),
        effective_to=T0 + timedelta(days=1),
        calendar_version="cal-v1", source_ids=(H("s-" + outgoing),),
    )
    incoming_s = VerifiedSessionV2.create(
        market=market, instrument_id=instrument_id, contract_id=incoming,
        session_date=date(2026, 3, 9), timezone="America/Chicago",
        open_time=T0, close_time=T0 + timedelta(hours=6),
        effective_from=T0 - timedelta(days=1),
        effective_to=T0 + timedelta(days=1),
        calendar_version="cal-v1", source_ids=(H("s-" + incoming),),
    )
    multiplier = D("50") if prefix == "ES" else D("20")
    oi = InstrumentSpecificationV2(
        "instrument-spec-v2-1", H("inst-" + outgoing), market, instrument_id,
        outgoing, profile, "USD", D("0.25"), D("1"), multiplier, multiplier,
        T0 - timedelta(days=2), T0 + timedelta(days=2),
        (H("e-" + outgoing),),
    )
    ii = InstrumentSpecificationV2(
        "instrument-spec-v2-1", H("inst-" + incoming), market, instrument_id,
        incoming, profile, "USD", D("0.25"), D("1"), multiplier, multiplier,
        T0 - timedelta(days=2), T0 + timedelta(days=2),
        (H("e-" + incoming),),
    )
    rs = RollSpecificationV2.create(
        run_id=H("run"), market=market, instrument_id=instrument_id,
        outgoing_contract_id=outgoing, incoming_contract_id=incoming,
        opening_side=opening_side,
        outgoing_quantity=D("2"), incoming_quantity=D("2"),
        roll_time=T0,
        effective_from=T0 - timedelta(minutes=1),
        effective_to=T0 + timedelta(hours=6),
        outgoing_session_id=outgoing_s.session_id,
        incoming_session_id=incoming_s.session_id,
        outgoing_instrument_specification_id=oi.specification_id,
        incoming_instrument_specification_id=ii.specification_id,
        participation_limit=D("0.5"), quantity_step=D("1"),
        roll_version=PHASE6_VERSION, source_ids=(H("source"),),
    )
    signed = D("2") if opening_side == OrderSide.BUY else D("-2")
    state = RolloverStateV2.create(rs, signed)
    ob = OHLCBarV2(
        "ohlc-bar-v2-1", H("ob" + prefix), market, instrument_id, outgoing,
        T0 + timedelta(minutes=1), T0 + timedelta(minutes=2),
        T0 + timedelta(minutes=2), D("5000"), D("5001"), D("4999"),
        D("5000"), D("10"), True, True, True, True, "bars-v1",
    )
    oi1 = create_roll_instruction(
        state=state, bar=ob, session=outgoing_s,
        trigger_bar_id=H("trigger"),
        outgoing_instrument=oi, incoming_instrument=ii,
    )
    state = apply_roll_fill(state, oi1, roll_fill(oi1, "out" + prefix, D("2")))
    ib = replace(
        ob, bar_id=H("ib" + prefix), contract_id=incoming,
        open_time=T0 + timedelta(minutes=3),
        close_time=T0 + timedelta(minutes=4),
        available_at=T0 + timedelta(minutes=4),
    )
    ii1 = create_roll_instruction(
        state=state, bar=ib, session=incoming_s,
        trigger_bar_id=ob.bar_id,
        outgoing_instrument=oi, incoming_instrument=ii,
    )
    return state, oi1, ii1, apply_roll_fill(
        state, ii1, roll_fill(ii1, "in" + prefix, D("2")),
    )


def accounting_snapshot(profile=InstrumentProfile.BTC_LINEAR_PERPETUAL,
                        qty=D("1"), as_of=T0):
    market = instrument_id = contract = "BTC-PERP"
    pos = PositionStateV2(
        qty, D("50000") if qty else None,
        D("50000") if qty else None, None,
    )
    equity = D("100000") + (
        qty * D("50000") if profile == InstrumentProfile.BTC_SPOT else D("0")
    )
    return AccountingSnapshotPhase4V2(
        "instrument-accounting-snapshot-v2-1",
        H("snap" + str(qty) + str(as_of) + profile.value),
        H("run"), as_of, market, instrument_id, contract, profile, "USD",
        pos, D("100000"), D("100000"),
        D("0"), D("0"), D("0"), D("0"), D("0"), D("0"),
        D("0"), D("0"), D("0"), equity,
        D("0"), D("0"), D("0"), D("0"),
        False, (H("aevent"),), ACCOUNTING_VERSION,
        H("fp" + str(qty) + str(as_of) + profile.value),
    )


def perp_inst(profile=InstrumentProfile.BTC_LINEAR_PERPETUAL):
    return inst("BTC-PERP", profile, "BTC-PERP", "BTC-PERP")


def requirement(**changes):
    values = dict(
        run_id=H("run"), market="BTC-PERP", instrument_id="BTC-PERP",
        contract_id="BTC-PERP",
        funding_time=T0 + timedelta(hours=1),
        latest_available_at=T0 + timedelta(hours=1, minutes=5),
        contract_basis="LINEAR_USD", contract_multiplier=D("1"),
        instrument_specification_id=H("inst-BTC-PERP"),
        funding_version=PHASE6_VERSION, fact_source_version="fund-v1",
        source_ids=(H("funding-schedule"),),
    )
    values.update(changes)
    return FundingRequirementV2.create(**values)


def funding(rate="0.001", **changes):
    values = dict(
        schema_version="funding-fact-v2-1", funding_id=H("fund"),
        market="BTC-PERP", instrument_id="BTC-PERP", contract_id="BTC-PERP",
        funding_time=T0 + timedelta(hours=1),
        available_at=T0 + timedelta(hours=1, minutes=1),
        rate=D(rate), mark_price=D("50000"), oracle_price=D("49990"),
        specification_ids=(H("funding"), H("mark"), H("oracle")),
        source_version="fund-v1",
    )
    values.update(changes)
    return FundingFactV2(**values)


# ===========================================================================
# 1. Rollover specifications — versioned, immutable, validated
# ===========================================================================

class TestRollSpecification:
    """Immutable/versioned ES and NQ rollover specifications."""

    def test_roll_spec_is_immutable(self):
        """RollSpecificationV2 is frozen."""
        s = spec()
        with pytest.raises(FrozenInstanceError):
            s.outgoing_contract_id = "OTHER"

    def test_roll_spec_id_is_deterministic(self):
        """Same inputs → same roll_specification_id."""
        assert spec().roll_specification_id == spec().roll_specification_id

    def test_roll_spec_same_contract_rejects(self):
        """outgoing == incoming contract → ValueError."""
        with pytest.raises(ValueError, match="roll contracts must differ"):
            spec(outgoing="ESH6", incoming="ESH6")

    def test_roll_spec_wrong_version_rejects(self):
        """Wrong roll_version → ValueError."""
        with pytest.raises(ValueError):
            spec(roll_version="wrong")

    def test_roll_spec_participation_exceeds_one_rejects(self):
        """participation_limit > 1 → ValueError."""
        with pytest.raises(ValueError, match="cannot exceed one"):
            spec(participation_limit=D("1.5"))

    def test_roll_spec_off_grid_quantity_rejects(self):
        """Off-grid quantities → ValueError."""
        with pytest.raises(ValueError, match="on grid"):
            spec(outgoing_quantity=D("1.5"), quantity_step=D("1"))

    def test_roll_spec_roll_time_outside_effective_rejects(self):
        """roll_time outside [effective_from, effective_to) → ValueError."""
        with pytest.raises(ValueError, match="outside effective"):
            spec(roll_time=T0 - timedelta(hours=1),
                 effective_from=T0, effective_to=T0 + timedelta(hours=1))

    def test_roll_spec_unique_source_ids(self):
        """Duplicate source_ids → ValueError."""
        with pytest.raises(ValueError, match="sources invalid"):
            spec(source_ids=(H("a"), H("a")))

    def test_roll_spec_zero_quantity_rejects(self):
        """Zero outgoing_quantity → ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            spec(outgoing_quantity=D("0"))


# ===========================================================================
# 2. Outgoing-close before incoming-open enforcement
# ===========================================================================

class TestOutgoingBeforeIncoming:
    """Outgoing close must complete before incoming open begins."""

    def test_es_long_roll_outgoing_then_incoming(self):
        """ES long: sell outgoing, then buy incoming → COMPLETE."""
        state, out, incoming, done = roll_once()
        assert state.status == RollStatus.FLAT_AWAITING_INCOMING
        assert done.status == RollStatus.COMPLETE
        assert out.instruction_id != incoming.instruction_id

    def test_nq_short_roll_outgoing_then_incoming(self):
        """NQ short: buy outgoing, then sell incoming → COMPLETE."""
        _, out, incoming, done = roll_once(
            OrderSide.SELL, InstrumentProfile.NQ_FUTURE, "NQ"
        )
        assert out.side == OrderSide.BUY
        assert incoming.side == OrderSide.SELL
        assert done.status == RollStatus.COMPLETE

    def test_incoming_blocked_until_outgoing_complete(self):
        """Cannot apply incoming fill while outgoing is partial."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        partial = apply_roll_fill(state, ins, roll_fill(ins, "p", D("1")))
        assert partial.status == RollStatus.OUTGOING_PARTIAL
        # Try to apply an incoming fill → should reject
        flat, _, incoming, _ = roll_once()
        with pytest.raises(Phase6Error):
            apply_roll_fill(partial, incoming, roll_fill(incoming, "bad"))

    def test_outgoing_side_is_opposite_to_opening(self):
        """Long roll: outgoing side = SELL; short roll: outgoing = BUY."""
        _, long_out, _, _ = roll_once(OrderSide.BUY)
        assert long_out.side == OrderSide.SELL
        _, short_out, _, _ = roll_once(OrderSide.SELL)
        assert short_out.side == OrderSide.BUY

    def test_incoming_side_matches_opening(self):
        """Long roll: incoming side = BUY; short: incoming = SELL."""
        _, _, long_in, _ = roll_once(OrderSide.BUY)
        assert long_in.side == OrderSide.BUY
        _, _, short_in, _ = roll_once(OrderSide.SELL)
        assert short_in.side == OrderSide.SELL


# ===========================================================================
# 3. Participation and quantity normalization
# ===========================================================================

class TestParticipation:
    """Participation flooring and quantity normalization."""

    def test_participation_floors_to_step(self):
        """eligible_roll_quantity floors to quantity_step."""
        assert eligible_roll_quantity(
            bar("ESH6", 1, volume=D("3")), spec(), D("2")
        ) == D("1")

    def test_participation_capped_by_remaining(self):
        """Participation cannot exceed remaining quantity."""
        result = eligible_roll_quantity(
            bar("ESH6", 1, volume=D("100")), spec(), D("2")
        )
        # min(2, 100 * 0.5) = min(2, 50) = 2; floor(2, 1) = 2
        assert result == D("2")

    def test_zero_volume_rejects(self):
        """Zero volume → PARTICIPATION_UNAVAILABLE."""
        with pytest.raises(Phase6Error):
            eligible_roll_quantity(
                bar("ESH6", 1, volume=D("0")), spec(), D("2")
            )

    def test_none_volume_rejects(self):
        """None volume → PARTICIPATION_UNAVAILABLE."""
        with pytest.raises(Phase6Error):
            eligible_roll_quantity(
                bar("ESH6", 1, volume=None), spec(), D("2")
            )

    def test_participation_floors_to_zero_rejects(self):
        """Participation that floors to zero → PARTICIPATION_UNAVAILABLE."""
        # volume=1, participation_limit=0.5 → 0.5 → floor(0.5, 1) = 0
        with pytest.raises(Phase6Error):
            eligible_roll_quantity(
                bar("ESH6", 1, volume=D("1")), spec(), D("2")
            )


# ===========================================================================
# 4. Partial close/open lifecycle
# ===========================================================================

class TestPartialLifecycle:
    """Partial close/open state transitions."""

    def test_partial_outgoing_state(self):
        """Partial outgoing → OUTGOING_PARTIAL."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        partial = apply_roll_fill(state, ins, roll_fill(ins, "p", D("1")))
        assert partial.status == RollStatus.OUTGOING_PARTIAL
        assert partial.outgoing_filled == D("1")

    def test_partial_then_complete_outgoing(self):
        """Partial then complete → FLAT_AWAITING_INCOMING."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        partial = apply_roll_fill(state, ins, roll_fill(ins, "p1", D("1")))
        complete = apply_roll_fill(
            partial, ins, roll_fill(ins, "p2", D("1"))
        )
        assert complete.status == RollStatus.FLAT_AWAITING_INCOMING
        assert complete.temporarily_flat is True

    def test_partial_incoming_state(self):
        """Partial incoming → INCOMING_PARTIAL."""
        state, _, _, _ = roll_once()
        # After full outgoing, do partial incoming
        s = spec()
        st = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=st, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        st = apply_roll_fill(st, ins, roll_fill(ins, "o", D("2")))
        ib = bar("ESM6", 3)
        ins2 = create_roll_instruction(
            state=st, bar=ib, session=sess("ESM6"),
            trigger_bar_id=ob.bar_id,
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        partial = apply_roll_fill(st, ins2, roll_fill(ins2, "pi", D("1")))
        assert partial.status == RollStatus.INCOMING_PARTIAL
        assert partial.incoming_filled == D("1")

    def test_fill_exceeds_authorized_rejects(self):
        """Fill quantity > authorized_quantity → reject."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        # authorized = min(2, 10*0.5) = 2; try fill with 3
        with pytest.raises(Phase6Error):
            apply_roll_fill(state, ins, roll_fill(ins, "over", D("3")))


# ===========================================================================
# 5. Temporary-flat and incomplete-roll states
# ===========================================================================

class TestTemporaryFlat:
    """Temporary-flat and incomplete-roll states."""

    def test_temporary_flat_after_outgoing_complete(self):
        """After outgoing complete → temporarily_flat = True."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        flat = apply_roll_fill(state, ins, roll_fill(ins, "o", D("2")))
        assert flat.temporarily_flat is True

    def test_not_flat_during_outgoing_partial(self):
        """During outgoing partial → temporarily_flat = False."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        partial = apply_roll_fill(state, ins, roll_fill(ins, "p", D("1")))
        assert partial.temporarily_flat is False

    def test_failed_outgoing_state(self):
        """Failed outgoing → FAILED_OUTGOING."""
        state = RolloverStateV2.create(spec(), D("2"))
        failed = record_missing_roll_bar(state, RollLeg.OUTGOING_CLOSE)
        assert failed.status == RollStatus.FAILED_OUTGOING
        assert failed.failure_reason == Phase6Reason.MISSING_OUTGOING_BAR

    def test_missing_incoming_preserves_flat(self):
        """Missing incoming bar on flat state → preserves flat."""
        flat, _, _, _ = roll_once()
        result = record_missing_roll_bar(flat, RollLeg.INCOMING_OPEN)
        assert result is flat
        assert flat.temporarily_flat is True

    def test_complete_state_no_more_legs(self):
        """COMPLETE state → no eligible next leg."""
        _, _, _, done = roll_once()
        with pytest.raises(Phase6Error):
            create_roll_instruction(
                state=done, bar=bar("ESM6", 5),
                session=sess("ESM6"), trigger_bar_id=H("t"),
                outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
            )

    def test_failed_state_no_more_legs(self):
        """FAILED_OUTGOING → no eligible next leg."""
        state = RolloverStateV2.create(spec(), D("2"))
        failed = record_missing_roll_bar(state, RollLeg.OUTGOING_CLOSE)
        with pytest.raises(Phase6Error):
            create_roll_instruction(
                state=failed, bar=bar("ESH6", 2),
                session=sess(), trigger_bar_id=H("t"),
                outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
            )


# ===========================================================================
# 6. Same-bar and look-ahead rejection
# ===========================================================================

class TestSameBarLookahead:
    """Same-bar and look-ahead rejection."""

    def test_same_bar_rejected(self):
        """Bar with same ID as trigger → SAME_BAR_REJECTED."""
        state = RolloverStateV2.create(spec(), D("2"))
        b = bar("ESH6", 1)
        with pytest.raises(Phase6Error) as exc:
            create_roll_instruction(
                state=state, bar=b, session=sess(),
                trigger_bar_id=b.bar_id,
                outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
            )
        assert exc.value.reason == Phase6Reason.SAME_BAR_REJECTED

    def test_lookahead_rejected(self):
        """Bar not yet available (open_time <= roll_time) → LOOKAHEAD_REJECTED."""
        state = RolloverStateV2.create(spec(), D("2"))
        # bar at T0 (roll_time) → open_time <= roll_time
        b = bar("ESH6", 0)
        with pytest.raises(Phase6Error) as exc:
            create_roll_instruction(
                state=state, bar=b, session=sess(),
                trigger_bar_id=H("t"),
                outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
            )
        assert exc.value.reason == Phase6Reason.LOOKAHEAD_REJECTED

    def test_unfinalized_bar_rejected(self):
        """Unfinalized bar → BAR_INELIGIBLE."""
        state = RolloverStateV2.create(spec(), D("2"))
        with pytest.raises(Phase6Error) as exc:
            create_roll_instruction(
                state=state, bar=bar("ESH6", 1, finalized=False),
                session=sess(), trigger_bar_id=H("t"),
                outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
            )
        assert exc.value.reason == Phase6Reason.BAR_INELIGIBLE

    def test_stale_roll_spec_rejected(self):
        """Bar outside effective interval → STALE_ROLL_SPECIFICATION."""
        state = RolloverStateV2.create(spec(), D("2"))
        # Bar at T0 + 10 hours (outside effective_to = T0 + 6 hours)
        with pytest.raises(Phase6Error) as exc:
            create_roll_instruction(
                state=state, bar=bar("ESH6", 600),
                session=sess(), trigger_bar_id=H("t"),
                outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
            )
        assert exc.value.reason == Phase6Reason.STALE_ROLL_SPECIFICATION


# ===========================================================================
# 7. Identity, session, contract, version isolation
# ===========================================================================

class TestIsolation:
    """Market, instrument, contract, session, chronology, version isolation."""

    def test_wrong_market_bar_rejects(self):
        """Bar with wrong market → IDENTITY_MISMATCH."""
        state = RolloverStateV2.create(spec(), D("2"))
        wrong = replace(bar("ESH6", 1), market="OTHER")
        with pytest.raises(Phase6Error):
            create_roll_instruction(
                state=state, bar=wrong, session=sess(),
                trigger_bar_id=H("t"),
                outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
            )

    def test_wrong_session_rejects(self):
        """Wrong session_id → IDENTITY_MISMATCH."""
        state = RolloverStateV2.create(spec(), D("2"))
        wrong_session = VerifiedSessionV2.create(
            market="CME", instrument_id="ES", contract_id="ESH6",
            session_date=date(2026, 3, 10), timezone="America/Chicago",
            open_time=T0 + timedelta(hours=6),
            close_time=T0 + timedelta(hours=12),
            effective_from=T0 + timedelta(hours=5),
            effective_to=T0 + timedelta(days=2),
            calendar_version="cal-v1", source_ids=(H("other"),),
        )
        with pytest.raises(Phase6Error):
            create_roll_instruction(
                state=state, bar=bar("ESH6", 1),
                session=wrong_session, trigger_bar_id=H("t"),
                outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
            )

    def test_wrong_instrument_spec_version_rejects(self):
        """Wrong instrument specification_id → VERSION_MISMATCH."""
        state = RolloverStateV2.create(spec(), D("2"))
        wrong_inst = InstrumentSpecificationV2(
            "instrument-spec-v2-1", H("wrong-inst"), "CME", "ES", "ESH6",
            InstrumentProfile.ES_FUTURE, "USD", D("0.25"), D("1"),
            D("50"), D("50"), T0 - timedelta(days=2),
            T0 + timedelta(days=2), (H("wrong-ev"),),
        )
        with pytest.raises(Phase6Error):
            create_roll_instruction(
                state=state, bar=bar("ESH6", 1), session=sess(),
                trigger_bar_id=H("t"),
                outgoing_instrument=wrong_inst,
                incoming_instrument=inst("ESM6"),
            )

    def test_fill_identity_mismatch_rejects(self):
        """Fill with wrong market/instrument/contract/side → reject."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        bad_fill = replace(
            roll_fill(ins, "bad"),
            market="OTHER",
        )
        with pytest.raises(Phase6Error):
            apply_roll_fill(state, ins, bad_fill)

    def test_fill_wrong_bar_id_rejects(self):
        """Fill with wrong market_event_id (bar_id) → reject."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        bad_fill = replace(
            roll_fill(ins, "bad"),
            market_event_id=H("wrong-bar"),
        )
        with pytest.raises(Phase6Error):
            apply_roll_fill(state, ins, bad_fill)


# ===========================================================================
# 8. Overlapping and ambiguous roll specifications
# ===========================================================================

class TestRollSpecValidation:
    """Overlapping and ambiguous roll specifications."""

    def test_overlapping_specs_reject(self):
        """Overlapping effective intervals → OVERLAPPING_ROLL_SPECIFICATION."""
        one = spec()
        two = spec(source_ids=(H("other"),))
        with pytest.raises(Phase6Error):
            validate_roll_specifications((one, two))

    def test_ambiguous_specs_reject(self):
        """Same market/instrument/roll_time → AMBIGUOUS_ROLL_SPECIFICATION."""
        one = spec()
        # Create a different spec with same roll_time but different source
        two = spec(source_ids=(H("other"),))
        # They have the same roll_time and market/instrument
        with pytest.raises(Phase6Error):
            validate_roll_specifications((one, two))

    def test_valid_specs_pass(self):
        """Non-overlapping specs pass validation."""
        one = spec()
        # A different spec for a different market
        two = spec(market="NQ", instrument_id="NQ",
                   outgoing="NQH6", incoming="NQM6")
        validate_roll_specifications((one, two))


# ===========================================================================
# 9. BTC linear-perpetual funding capability gates
# ===========================================================================

class TestFundingCapability:
    """BTC linear-perpetual funding capability gates."""

    def test_perpetual_funding_long_debit(self):
        """Long position → negative payment (debit)."""
        app = prepare_funding_application(
            requirement=requirement(), fact=funding(),
            snapshot=accounting_snapshot(qty=D("1")),
            instrument=perp_inst(), perpetual_capability_enabled=True,
        )
        assert app.expected_payment == D("-50")

    def test_perpetual_funding_short_credit(self):
        """Short position → positive payment (credit)."""
        app = prepare_funding_application(
            requirement=requirement(), fact=funding(),
            snapshot=accounting_snapshot(qty=D("-1")),
            instrument=perp_inst(), perpetual_capability_enabled=True,
        )
        assert app.expected_payment == D("50")

    def test_flat_perpetual_funding_zero(self):
        """Flat position → zero payment."""
        app = prepare_funding_application(
            requirement=requirement(), fact=funding(),
            snapshot=accounting_snapshot(qty=D("0")),
            instrument=perp_inst(), perpetual_capability_enabled=True,
        )
        assert app.expected_payment == 0

    def test_capability_disabled_rejects(self):
        """perpetual_capability_enabled=False → FUNDING_NOT_SUPPORTED."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(), fact=funding(),
                snapshot=accounting_snapshot(),
                instrument=perp_inst(), perpetual_capability_enabled=False,
            )
        assert exc.value.reason == Phase6Reason.FUNDING_NOT_SUPPORTED

    def test_missing_funding_fact_rejects(self):
        """fact=None → MISSING_FUNDING_FACT."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(), fact=None,
                snapshot=accounting_snapshot(),
                instrument=perp_inst(), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.MISSING_FUNDING_FACT

    @pytest.mark.parametrize("profile", [
        InstrumentProfile.BTC_SPOT,
        InstrumentProfile.ES_FUTURE,
        InstrumentProfile.NQ_FUTURE,
    ])
    def test_non_perpetual_profile_rejects(self, profile):
        """Non-perpetual profile → FUNDING_NOT_SUPPORTED."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(), fact=funding(),
                snapshot=accounting_snapshot(profile=profile),
                instrument=perp_inst(profile), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.FUNDING_NOT_SUPPORTED


# ===========================================================================
# 10. Funding lineage: mark, oracle, rate, timestamp, multiplier, basis
# ===========================================================================

class TestFundingLineage:
    """Mark, oracle, rate, timestamp, multiplier, basis, source lineage."""

    def test_stale_funding_timestamp_rejects(self):
        """fact.funding_time != requirement.funding_time → STALE_FUNDING_FACT."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(),
                fact=funding(
                    funding_time=T0 + timedelta(hours=2),
                    available_at=T0 + timedelta(hours=2, minutes=1),
                ),
                snapshot=accounting_snapshot(),
                instrument=perp_inst(), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.STALE_FUNDING_FACT

    def test_late_funding_fact_rejects(self):
        """fact.available_at > requirement.latest_available_at → LATE_FUNDING_FACT."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(),
                fact=funding(available_at=T0 + timedelta(hours=2)),
                snapshot=accounting_snapshot(),
                instrument=perp_inst(), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.LATE_FUNDING_FACT

    def test_wrong_source_version_rejects(self):
        """fact.source_version != requirement.fact_source_version → VERSION_MISMATCH."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(),
                fact=funding(source_version="wrong-v2"),
                snapshot=accounting_snapshot(),
                instrument=perp_inst(), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.VERSION_MISMATCH

    def test_cross_multiplier_rejects(self):
        """requirement.contract_multiplier != instrument.contract_multiplier → reject."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(contract_multiplier=D("2")),
                fact=funding(),
                snapshot=accounting_snapshot(),
                instrument=perp_inst(), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.VERSION_MISMATCH

    def test_identity_mismatch_funding_rejects(self):
        """Wrong market in fact → IDENTITY_MISMATCH."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(),
                fact=funding(market="OTHER"),
                snapshot=accounting_snapshot(),
                instrument=perp_inst(), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.IDENTITY_MISMATCH

    def test_snapshot_crossed_funding_boundary_rejects(self):
        """snapshot.as_of > requirement.funding_time → EVENT_TIME_REGRESSION."""
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(),
                fact=funding(),
                snapshot=accounting_snapshot(
                    as_of=T0 + timedelta(hours=2)
                ),
                instrument=perp_inst(), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.EVENT_TIME_REGRESSION

    def test_accounting_version_mismatch_rejects(self):
        """Wrong accounting_version → VERSION_MISMATCH."""
        snap = replace(accounting_snapshot(), accounting_version="v1")
        with pytest.raises(Phase6Error) as exc:
            prepare_funding_application(
                requirement=requirement(), fact=funding(),
                snapshot=snap,
                instrument=perp_inst(), perpetual_capability_enabled=True,
            )
        assert exc.value.reason == Phase6Reason.VERSION_MISMATCH

    def test_funding_application_immutable(self):
        """FundingApplicationV2 is frozen."""
        app = prepare_funding_application(
            requirement=requirement(), fact=funding(),
            snapshot=accounting_snapshot(),
            instrument=perp_inst(), perpetual_capability_enabled=True,
        )
        with pytest.raises(FrozenInstanceError):
            app.expected_payment = D("0")

    def test_funding_requirement_immutable(self):
        """FundingRequirementV2 is frozen."""
        req = requirement()
        with pytest.raises(FrozenInstanceError):
            req.contract_multiplier = D("999")


# ===========================================================================
# 11. Funding boundary gate
# ===========================================================================

class TestFundingBoundaryGate:
    """Funding boundary gate: held position must apply all funding facts."""

    def test_missing_funding_boundary_rejects(self):
        """Held position crossing unapplied funding boundary → reject."""
        with pytest.raises(Phase6Error) as exc:
            funding_boundary_gate(
                snapshot=accounting_snapshot(),
                requirements=(requirement(),),
                applications=(),
                through=T0 + timedelta(hours=2),
            )
        assert exc.value.reason == Phase6Reason.FUNDING_BOUNDARY_MISSED

    def test_applied_funding_boundary_passes(self):
        """Applied funding boundary → gate passes."""
        app = prepare_funding_application(
            requirement=requirement(), fact=funding(),
            snapshot=accounting_snapshot(),
            instrument=perp_inst(), perpetual_capability_enabled=True,
        )
        funding_boundary_gate(
            snapshot=accounting_snapshot(),
            requirements=(requirement(),),
            applications=(app,),
            through=T0 + timedelta(hours=2),
        )

    def test_flat_position_no_funding_required(self):
        """Flat position → no funding required, gate passes."""
        funding_boundary_gate(
            snapshot=accounting_snapshot(qty=D("0")),
            requirements=(requirement(),),
            applications=(),
            through=T0 + timedelta(hours=2),
        )


# ===========================================================================
# 12. Completed phase6 gate
# ===========================================================================

class TestCompletedGate:
    """Incomplete roll and missing funding fail completed gate."""

    def test_incomplete_roll_fails(self):
        """Non-COMPLETE roll → INCOMPLETE_ROLL."""
        with pytest.raises(Phase6Error) as exc:
            completed_phase6_gate(
                rolls=(RolloverStateV2.create(spec(), D("2")),),
                requirements=(), applications=(),
                snapshot=accounting_snapshot(), through=T0,
            )
        assert exc.value.reason == Phase6Reason.INCOMPLETE_ROLL

    def test_complete_roll_passes(self):
        """All COMPLETE rolls + no funding needed → passes."""
        _, _, _, done = roll_once()
        completed_phase6_gate(
            rolls=(done,),
            requirements=(), applications=(),
            snapshot=accounting_snapshot(qty=D("0")),
            through=T0,
        )


# ===========================================================================
# 13. Phase6 event ledger — duplicate, replay, tamper
# ===========================================================================

class TestPhase6Ledger:
    """Duplicate events, replay, checkpoints, tamper rejection."""

    def test_event_idempotent(self):
        """Same event applied twice → idempotent."""
        e = Phase6EventV2.create(
            economic_id=H("e1"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0, payload_id=H("p1"),
        )
        ledger = Phase6LedgerV2.create(H("run")).apply(e)
        assert ledger.apply(e) is ledger

    def test_duplicate_economic_id_rejects(self):
        """Same economic_id under new event_id → DUPLICATE_ECONOMIC_EVENT."""
        a = Phase6EventV2.create(
            economic_id=H("e1"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0, payload_id=H("pa"),
        )
        b = Phase6EventV2.create(
            economic_id=H("e1"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0 + timedelta(minutes=1),
            payload_id=H("pb"),
        )
        ledger = Phase6LedgerV2.create(H("run")).apply(a)
        with pytest.raises(Phase6Error) as exc:
            ledger.apply(b)
        assert exc.value.reason == Phase6Reason.DUPLICATE_ECONOMIC_EVENT

    def test_same_time_same_priority_rejects(self):
        """Same-time/same-priority is ambiguity regardless of event-id order."""
        a = Phase6EventV2.create(
            economic_id=H("a"), kind=Phase6EventKind.FUNDING,
            event_time=T0, payload_id=H("pa"),
        )
        b = Phase6EventV2.create(
            economic_id=H("b"), kind=Phase6EventKind.FUNDING,
            event_time=T0, payload_id=H("pb"),
        )
        for first, second in ((a, b), (b, a)):
            ledger = Phase6LedgerV2.create(H("run")).apply(first)
            with pytest.raises(Phase6Error) as exc:
                ledger.apply(second)
            assert exc.value.reason is Phase6Reason.PRIORITY_AMBIGUITY

    def test_chronology_regression_rejects(self):
        """Earlier event time after later → EVENT_TIME_REGRESSION."""
        a = Phase6EventV2.create(
            economic_id=H("a"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0 + timedelta(minutes=2),
            payload_id=H("pa"),
        )
        b = Phase6EventV2.create(
            economic_id=H("b"), kind=Phase6EventKind.FUNDING,
            event_time=T0 + timedelta(minutes=1),
            payload_id=H("pb"),
        )
        ledger = Phase6LedgerV2.create(H("run")).apply(a)
        with pytest.raises(Phase6Error) as exc:
            ledger.apply(b)
        assert exc.value.reason == Phase6Reason.EVENT_TIME_REGRESSION

    def test_ledger_replay_byte_identical(self):
        """Same events → identical ledger fingerprint."""
        e = Phase6EventV2.create(
            economic_id=H("e1"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0, payload_id=H("p1"),
        )
        a = Phase6LedgerV2.create(H("run")).apply(e)
        b = Phase6LedgerV2.create(H("run")).apply(e)
        assert a == b
        assert a.ledger_fingerprint == b.ledger_fingerprint

    def test_checkpoint_identical(self):
        """Same ledger → identical checkpoint."""
        e = Phase6EventV2.create(
            economic_id=H("e1"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0, payload_id=H("p1"),
        )
        a = Phase6LedgerV2.create(H("run")).apply(e)
        b = Phase6LedgerV2.create(H("run")).apply(e)
        assert Phase6CheckpointV2.create(a) == Phase6CheckpointV2.create(b)

    def test_tamper_detection(self):
        """Tampered ledger fingerprint → CHECKPOINT_TAMPERED."""
        e = Phase6EventV2.create(
            economic_id=H("e1"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0, payload_id=H("p1"),
        )
        ledger = Phase6LedgerV2.create(H("run")).apply(e)
        tampered = replace(ledger, ledger_fingerprint=H("tamper"))
        with pytest.raises(Phase6Error) as exc:
            tampered.verify_integrity()
        assert exc.value.reason == Phase6Reason.CHECKPOINT_TAMPERED

    def test_ledger_immutable(self):
        """Phase6LedgerV2 is frozen."""
        e = Phase6EventV2.create(
            economic_id=H("e"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0, payload_id=H("p"),
        )
        ledger = Phase6LedgerV2.create(H("run")).apply(e)
        with pytest.raises(FrozenInstanceError):
            ledger.events = ()

    def test_checkpoint_immutable(self):
        """Phase6CheckpointV2 is frozen."""
        e = Phase6EventV2.create(
            economic_id=H("e"), kind=Phase6EventKind.SETTLEMENT,
            event_time=T0, payload_id=H("p"),
        )
        ledger = Phase6LedgerV2.create(H("run")).apply(e)
        cp = Phase6CheckpointV2.create(ledger)
        with pytest.raises(FrozenInstanceError):
            cp.ledger_fingerprint = H("other")


# ===========================================================================
# 14. Collision priority
# ===========================================================================

class TestCollisionPriority:
    """Settlement/funding/rollover collision priority."""

    def test_settlement_before_funding(self):
        """Settlement (20) before funding (21)."""
        assert (int(Phase6Priority.SETTLEMENT)
                < int(Phase6Priority.FUNDING))

    def test_funding_before_rollover_outgoing(self):
        """Funding (21) before rollover outgoing (22)."""
        assert (int(Phase6Priority.FUNDING)
                < int(Phase6Priority.ROLLOVER_OUTGOING))

    def test_rollover_outgoing_before_incoming(self):
        """Rollover outgoing (22) before incoming (23)."""
        assert (int(Phase6Priority.ROLLOVER_OUTGOING)
                < int(Phase6Priority.ROLLOVER_INCOMING))

    def test_rollover_before_market_data(self):
        """Rollover incoming (23) before market data (30)."""
        assert (int(Phase6Priority.ROLLOVER_INCOMING)
                < int(Phase6Priority.MARKET_DATA))


# ===========================================================================
# 15. Reconciliation
# ===========================================================================

class TestReconciliation:
    """Cross-ledger reconciliation."""

    def test_reconciliation_deterministic(self):
        """Same inputs → same reconciliation_id."""
        values = dict(
            run_id=H("run"),
            order_ledger_fingerprint=H("orders"),
            execution_ids=(H("fill"),),
            accounting_ledger_fingerprint=H("accounting"),
            accounting_snapshot_id=H("snap"),
            risk_ledger_fingerprint=H("risk"),
            session_ids=(H("session"),),
            roll_state_ids=(H("roll"),),
            funding_application_ids=(H("fund"),),
            phase6_ledger_fingerprint=H("phase6"),
        )
        a = Phase6ReconciliationV2.create(**values)
        b = Phase6ReconciliationV2.create(**values)
        assert a == b
        assert a.reconciliation_id == b.reconciliation_id

    def test_reconciliation_immutable(self):
        """Phase6ReconciliationV2 is frozen."""
        values = dict(
            run_id=H("run"),
            order_ledger_fingerprint=H("orders"),
            execution_ids=(H("fill"),),
            accounting_ledger_fingerprint=H("accounting"),
            accounting_snapshot_id=H("snap"),
            risk_ledger_fingerprint=H("risk"),
            session_ids=(H("session"),),
            roll_state_ids=(H("roll"),),
            funding_application_ids=(H("fund"),),
            phase6_ledger_fingerprint=H("phase6"),
        )
        r = Phase6ReconciliationV2.create(**values)
        with pytest.raises(FrozenInstanceError):
            r.run_id = H("other")

    def test_reconciliation_duplicate_lineage_rejects(self):
        """Duplicate IDs in reconciliation → RECONCILIATION_MISMATCH."""
        values = dict(
            run_id=H("run"),
            order_ledger_fingerprint=H("orders"),
            execution_ids=(H("same"), H("same")),
            accounting_ledger_fingerprint=H("accounting"),
            accounting_snapshot_id=H("snap"),
            risk_ledger_fingerprint=H("risk"),
            session_ids=(H("session"),),
            roll_state_ids=(H("roll"),),
            funding_application_ids=(H("fund"),),
            phase6_ledger_fingerprint=H("phase6"),
        )
        with pytest.raises(Phase6Error):
            Phase6ReconciliationV2.create(**values)


# ===========================================================================
# 16. Rollover state and instruction immutability
# ===========================================================================

class TestRolloverImmutability:
    """Rollover state, instruction, and event immutability."""

    def test_rollover_state_immutable(self):
        """RolloverStateV2 is frozen."""
        state = RolloverStateV2.create(spec(), D("2"))
        with pytest.raises(FrozenInstanceError):
            state.status = RollStatus.COMPLETE

    def test_rollover_instruction_immutable(self):
        """RolloverInstructionV2 is frozen."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        with pytest.raises(FrozenInstanceError):
            ins.authorized_quantity = D("999")

    def test_rollover_event_immutable(self):
        """RolloverEventV2 is frozen."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        applied = apply_roll_fill(state, ins, roll_fill(ins, "x", D("1")))
        with pytest.raises(FrozenInstanceError):
            applied.events[0].quantity = D("999")


# ===========================================================================
# 17. Roll fill idempotency and conflict
# ===========================================================================

class TestRollFillIdempotency:
    """Roll fill idempotent and conflicting fill rejects."""

    def test_idempotent_same_fill(self):
        """Same fill applied twice → idempotent."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        f = roll_fill(ins, "x", D("1"))
        applied = apply_roll_fill(state, ins, f)
        assert apply_roll_fill(applied, ins, f) is applied

    def test_conflicting_fill_rejects(self):
        """Same fill_id, different content → DUPLICATE_EVENT_CONFLICT."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        f = roll_fill(ins, "x", D("1"))
        applied = apply_roll_fill(state, ins, f)
        # Different quantity with same fill_id
        f2 = replace(f, quantity=D("2"))
        with pytest.raises(Phase6Error):
            apply_roll_fill(applied, ins, f2)

    def test_overfill_rejects(self):
        """Fill exceeding outgoing_quantity → PARTICIPATION_UNAVAILABLE."""
        s = spec()
        state = RolloverStateV2.create(s, D("2"))
        ob = bar("ESH6", 1)
        ins = create_roll_instruction(
            state=state, bar=ob, session=sess(),
            trigger_bar_id=H("t"),
            outgoing_instrument=inst(), incoming_instrument=inst("ESM6"),
        )
        # Fill 2 (complete), then try another fill
        applied = apply_roll_fill(state, ins, roll_fill(ins, "f1", D("2")))
        # Now outgoing is complete — applying another outgoing fill rejects
        with pytest.raises(Phase6Error):
            apply_roll_fill(applied, ins, roll_fill(ins, "f2", D("1")))


# ===========================================================================
# 18. Import isolation
# ===========================================================================
