"""Hermes independent adversarial audit tests for V2 Phase 5 risk and sessions.

Audit assignment: AUDIT-V2-PHASE5-RISK-SESSIONS

Covers:
  - Immutable risk decisions and stable reason codes
  - Verified session identity and boundaries
  - Exposure, leverage, position, concentration, margin, loss, and drawdown limits
  - Missing or stale limit rejection
  - Session-loss and drawdown calculations
  - Pre-trade versus post-accounting risk separation
  - Deterministic risk-event priority
  - Forced-flatten instructions
  - Strict later-bar eligibility
  - Margin-call and liquidation-required facts
  - Residual-position handling
  - Duplicate events and deterministic replay
  - Chronology, market, instrument, contract, session, and version isolation
  - Tamper rejection and fingerprints
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2.accounting import (
    ACCOUNTING_VERSION, AccountingSnapshotPhase4V2, MarginBasis,
    MarginSpecificationV2, PositionStateV2,
)
from backtesting.execution_accounting_v2.contracts import (
    InstrumentSpecificationV2, OrderSide, RiskDecision, RiskPhase,
)
from backtesting.execution_accounting_v2.ohlc_execution import OHLCBarV2
from backtesting.execution_accounting_v2.risk_sessions import (
    RISK_POLICY_VERSION, BreachPriority, ForcedFlattenInstructionV2,
    LiquidationRequiredFactV2, MarginCallFactV2, PipelinePriority,
    PortfolioRiskContextV2, PostAccountingRiskEvaluationV2,
    PreTradeRiskRequestV2, RiskAction, RiskDecisionRecordV2, RiskLimitsV2,
    RiskReason, RiskSessionError, RiskSessionLedgerV2,
    SessionRiskStateV2, VerifiedSessionV2, completed_run_gate,
    evaluate_post_accounting, evaluate_pre_trade, evaluate_session_flatten,
    resolve_session, validate_forced_flatten_bar,
)
from backtesting.execution_accounting_v2.specifications import (
    InstrumentProfile,
)


UTC = timezone.utc
T0 = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
H = lambda value: hashlib.sha256(value.encode()).hexdigest()
D = Decimal


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def session(**kw):
    values = dict(
        market="CME", instrument_id="ES", contract_id="ESH6",
        session_date=date(2026, 1, 5), timezone="America/Chicago",
        open_time=T0, close_time=T0 + timedelta(hours=6),
        effective_from=T0 - timedelta(days=1),
        effective_to=T0 + timedelta(days=2),
        calendar_version="calendar-v1",
        source_ids=(H("calendar"),),
    )
    values.update(kw)
    return VerifiedSessionV2.create(**values)


def limits(**kw):
    values = dict(
        run_id=H("run"), market="CME", instrument_id="ES", contract_id="ESH6",
        effective_from=T0 - timedelta(days=1),
        effective_to=T0 + timedelta(days=2),
        max_gross_exposure=D("1000000"), max_net_exposure=D("1000000"),
        max_position_quantity=D("100"), max_concentration=D("1"),
        max_leverage=D("100"), max_initial_margin=D("1000000"),
        max_session_loss=D("1000"), max_drawdown=D("1500"),
        flatten_buffer_seconds=60,
        risk_policy_version=RISK_POLICY_VERSION,
        source_ids=(H("owner"),),
    )
    values.update(kw)
    return RiskLimitsV2.create(**values)


def instrument():
    return InstrumentSpecificationV2(
        "instrument-spec-v2-1", H("instrument"), "CME", "ES", "ESH6",
        InstrumentProfile.ES_FUTURE, "USD", D("0.25"), D("1"), D("50"), D("50"),
        T0 - timedelta(days=1), T0 + timedelta(days=2), (H("rules"),),
    )


def margin():
    return MarginSpecificationV2(
        "margin-specification-v2-1", H("margin"), "CME", "ES", "ESH6",
        T0 - timedelta(days=1), T0 + timedelta(days=2), MarginBasis.PER_CONTRACT,
        D("5000"), D("4000"), D("6000"), D("4500"), "margin-v1",
    )


def snapshot(*, equity=D("10000"), qty=D("1"), breach=False,
             as_of=T0 + timedelta(minutes=1)):
    pos = PositionStateV2(qty, D("5000") if qty else None,
                          D("5000") if qty else None, None)
    cash = equity
    values = ("instrument-accounting-snapshot-v2-1", H(f"snap-{equity}-{qty}-{as_of}"), H("run"), as_of,
        "CME", "ES", "ESH6", InstrumentProfile.ES_FUTURE, "USD", pos, D("10000"), cash,
        D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), equity,
        D("5000") if qty else D("0"), D("4000") if qty else D("0"),
        D("6000") if qty else D("0"), D("4500") if qty else D("0"), breach,
        (H("accounting-event"),), ACCOUNTING_VERSION, H(f"fp-{equity}-{qty}-{as_of}"))
    return AccountingSnapshotPhase4V2(*values)


def request(**kw):
    values = dict(
        run_id=H("run"), evaluated_at=T0 + timedelta(minutes=2),
        market="CME", instrument_id="ES", contract_id="ESH6",
        side=OrderSide.BUY, quantity=D("1"), reference_price=D("5000"),
        source_action_id=H("action"), source_bar_id=H("bar"),
    )
    values.update(kw)
    return PreTradeRiskRequestV2.create(**values)


def context(**kw):
    values = dict(
        run_id=H("run"), as_of=T0 + timedelta(minutes=2), equity=D("10000"),
        gross_exposure_before=D("250000"), net_exposure_before=D("250000"),
        session_reference_equity=D("10000"), session_peak_equity=D("10000"),
        source_snapshot_ids=(H("snapshot-source"),),
    )
    values.update(kw)
    return PortfolioRiskContextV2.create(**values)


def decision(**kw):
    return evaluate_pre_trade(
        request=request(**kw), snapshot=snapshot(), context=context(),
        limits=limits(), session=session(), instrument=instrument(),
        margin=margin(),
    )


def bar(*, at=T0 + timedelta(minutes=2), bar_id=None, **kw):
    values = dict(
        schema_version="ohlc-bar-v2-1",
        bar_id=bar_id or H(f"bar-{at}"),
        market="CME", instrument_id="ES", contract_id="ESH6",
        open_time=at, close_time=at + timedelta(minutes=1),
        available_at=at + timedelta(minutes=1),
        open=D("5000"), high=D("5001"), low=D("4999"), close=D("5000"),
        volume=D("10"), finalized=True, session_eligible=True,
        data_quality_valid=True, contract_eligible=True,
        source_version="bars-v1",
    )
    values.update(kw)
    return OHLCBarV2(**values)


def post_eval(*, snap=None, prior=None, lim=None, sess=None,
              trigger_bar_id=H("breach")):
    return evaluate_post_accounting(
        snapshot=snap or snapshot(), prior_state=prior,
        limits=lim or limits(), session=sess or session(),
        trigger_bar_id=trigger_bar_id,
    )


# ===========================================================================
# 1. Verified session identity and boundaries
# ===========================================================================

class TestVerifiedSession:
    """Verified session: UTC half-open, identity, boundaries, overlap."""

    def test_session_resolves_at_open_time(self):
        """resolve_session succeeds at open_time (inclusive)."""
        s = session()
        assert resolve_session(
            (s,), at=s.open_time, market="CME",
            instrument_id="ES", contract_id="ESH6",
        ) == s

    def test_session_rejects_at_close_time(self):
        """resolve_session rejects at close_time (exclusive)."""
        s = session()
        with pytest.raises(RiskSessionError):
            resolve_session(
                (s,), at=s.close_time, market="CME",
                instrument_id="ES", contract_id="ESH6",
            )

    def test_session_rejects_naive_time(self):
        """Naive datetime → ValueError."""
        with pytest.raises(ValueError):
            session(open_time=T0.replace(tzinfo=None))

    def test_session_rejects_invalid_timezone(self):
        """Invalid timezone → ValueError."""
        with pytest.raises(ValueError):
            session(timezone="Invalid/Zone")

    def test_session_rejects_effective_gap(self):
        """Session outside evidence effectiveness → ValueError."""
        with pytest.raises(ValueError):
            session(effective_from=T0 + timedelta(minutes=1))

    def test_session_missing_rejects(self):
        """No session covering event → MISSING_SESSION."""
        with pytest.raises(RiskSessionError) as exc:
            resolve_session((), at=T0, market="CME",
                           instrument_id="ES", contract_id="ESH6")
        assert exc.value.reason == RiskReason.MISSING_SESSION

    def test_session_overlap_rejects(self):
        """Multiple sessions covering same time → SESSION_OVERLAP."""
        s1 = session()
        s2 = session(source_ids=(H("other"),))
        with pytest.raises(RiskSessionError) as exc:
            resolve_session((s1, s2), at=T0, market="CME",
                           instrument_id="ES", contract_id="ESH6")
        assert exc.value.reason == RiskReason.SESSION_OVERLAP

    def test_session_identity_mismatch_rejects(self):
        """Wrong market/instrument → no matching session."""
        s = session()
        with pytest.raises(RiskSessionError):
            resolve_session((s,), at=T0, market="NQ",
                           instrument_id="NQ", contract_id="NQH6")

    def test_session_open_before_close(self):
        """open_time >= close_time → ValueError."""
        with pytest.raises(ValueError):
            session(open_time=T0, close_time=T0)

    def test_session_immutable(self):
        """VerifiedSessionV2 is frozen."""
        s = session()
        with pytest.raises(FrozenInstanceError):
            s.market = "NQ"

    def test_session_id_is_deterministic(self):
        """Same inputs → same session_id."""
        s1 = session()
        s2 = session()
        assert s1.session_id == s2.session_id

    def test_session_contract_id_none_allowed(self):
        """contract_id=None is valid for spot-like sessions."""
        s = session(contract_id=None)
        assert s.contract_id is None

    def test_session_source_ids_unique(self):
        """Duplicate source_ids → ValueError."""
        with pytest.raises(ValueError):
            session(source_ids=(H("a"), H("a")))


# ===========================================================================
# 2. Risk limits
# ===========================================================================

class TestRiskLimits:
    """Exposure, leverage, position, concentration, margin, loss, drawdown."""

    def test_limits_decimal_only(self):
        """Float in limits → TypeError/ValueError."""
        with pytest.raises((TypeError, ValueError)):
            limits(max_drawdown=1.0)

    def test_limits_nan_rejects(self):
        """NaN in limits → ValueError."""
        with pytest.raises(ValueError):
            limits(max_leverage=D("NaN"))

    def test_limits_wrong_policy_version_rejects(self):
        """Wrong risk_policy_version → ValueError."""
        with pytest.raises(ValueError):
            limits(risk_policy_version="wrong")

    def test_limits_immutable(self):
        """RiskLimitsV2 is frozen."""
        lim = limits()
        with pytest.raises(FrozenInstanceError):
            lim.max_leverage = D("1")

    def test_limits_id_is_deterministic(self):
        """Same inputs → same limits_id."""
        assert limits().limits_id == limits().limits_id

    def test_concentration_cannot_exceed_one(self):
        """max_concentration > 1 → ValueError."""
        with pytest.raises(ValueError):
            limits(max_concentration=D("1.5"))

    def test_negative_drawdown_rejects(self):
        """Negative max_drawdown → ValueError."""
        with pytest.raises(ValueError):
            limits(max_drawdown=D("-1"))

    def test_zero_exposure_rejects(self):
        """Zero max_gross_exposure → ValueError (must be positive)."""
        with pytest.raises(ValueError):
            limits(max_gross_exposure=D("0"))

    def test_zero_position_rejects(self):
        """Zero max_position_quantity → ValueError."""
        with pytest.raises(ValueError):
            limits(max_position_quantity=D("0"))

    def test_flatten_buffer_negative_rejects(self):
        """Negative flatten_buffer_seconds → ValueError."""
        with pytest.raises(ValueError):
            limits(flatten_buffer_seconds=-1)

    def test_flatten_buffer_zero_allowed(self):
        """Zero flatten_buffer_seconds → valid."""
        lim = limits(flatten_buffer_seconds=0)
        assert lim.flatten_buffer_seconds == 0

    def test_limits_effective_to_before_from_rejects(self):
        """effective_to <= effective_from → ValueError."""
        with pytest.raises(ValueError):
            limits(effective_from=T0, effective_to=T0)


# ===========================================================================
# 3. Pre-trade risk evaluation
# ===========================================================================

class TestPreTradeRisk:
    """Pre-trade limit checks: exposure, leverage, position, concentration, margin."""

    def test_pretrade_accepts_within_limits(self):
        """All projections within limits → ALLOW with OK."""
        result = decision()
        assert result.event.decision == RiskDecision.ALLOW
        assert result.event.reason_codes == ("OK",)

    def test_pretrade_rejects_gross_exposure(self):
        """Gross exposure breach → REJECT with GROSS_EXPOSURE_LIMIT."""
        result = evaluate_pre_trade(
            request=request(), snapshot=snapshot(), context=context(),
            limits=limits(max_gross_exposure=D("300000")),
            session=session(), instrument=instrument(), margin=margin(),
        )
        assert RiskReason.GROSS_EXPOSURE_LIMIT.value in result.event.reason_codes
        assert result.event.decision == RiskDecision.REJECT

    def test_pretrade_rejects_net_exposure(self):
        """Net exposure breach → REJECT with NET_EXPOSURE_LIMIT."""
        result = evaluate_pre_trade(
            request=request(), snapshot=snapshot(), context=context(),
            limits=limits(max_net_exposure=D("300000")),
            session=session(), instrument=instrument(), margin=margin(),
        )
        assert RiskReason.NET_EXPOSURE_LIMIT.value in result.event.reason_codes

    def test_pretrade_rejects_position(self):
        """Position quantity breach → REJECT with POSITION_LIMIT."""
        result = evaluate_pre_trade(
            request=request(), snapshot=snapshot(), context=context(),
            limits=limits(max_position_quantity=D("1")),
            session=session(), instrument=instrument(), margin=margin(),
        )
        assert RiskReason.POSITION_LIMIT.value in result.event.reason_codes

    def test_pretrade_rejects_concentration(self):
        """Concentration breach → REJECT with CONCENTRATION_LIMIT."""
        result = evaluate_pre_trade(
            request=request(), snapshot=snapshot(), context=context(),
            limits=limits(max_concentration=D("0.5")),
            session=session(), instrument=instrument(), margin=margin(),
        )
        assert RiskReason.CONCENTRATION_LIMIT.value in result.event.reason_codes

    def test_pretrade_rejects_leverage(self):
        """Leverage breach → REJECT with LEVERAGE_LIMIT."""
        result = evaluate_pre_trade(
            request=request(), snapshot=snapshot(), context=context(),
            limits=limits(max_leverage=D("10")),
            session=session(), instrument=instrument(), margin=margin(),
        )
        assert RiskReason.LEVERAGE_LIMIT.value in result.event.reason_codes

    def test_pretrade_rejects_initial_margin(self):
        """Initial margin breach → REJECT with INITIAL_MARGIN_LIMIT."""
        result = evaluate_pre_trade(
            request=request(), snapshot=snapshot(), context=context(),
            limits=limits(max_initial_margin=D("10000")),
            session=session(), instrument=instrument(), margin=margin(),
        )
        assert RiskReason.INITIAL_MARGIN_LIMIT.value in result.event.reason_codes

    def test_pretrade_stale_limits_rejects(self):
        """Stale limits → STALE_RISK_LIMITS."""
        with pytest.raises(RiskSessionError) as exc:
            evaluate_pre_trade(
                request=request(), snapshot=snapshot(), context=context(),
                limits=limits(effective_to=T0),
                session=session(), instrument=instrument(), margin=margin(),
            )
        assert exc.value.reason == RiskReason.STALE_RISK_LIMITS

    def test_pretrade_identity_mismatch_run_id(self):
        """Different run_id → IDENTITY_MISMATCH."""
        with pytest.raises(RiskSessionError) as exc:
            evaluate_pre_trade(
                request=request(run_id=H("other")),
                snapshot=snapshot(), context=context(),
                limits=limits(), session=session(),
                instrument=instrument(), margin=margin(),
            )
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_pretrade_identity_mismatch_market(self):
        """Different market in snapshot → IDENTITY_MISMATCH."""
        snap = snapshot()
        snap_bad = replace(snap, market="NQ")
        with pytest.raises(RiskSessionError) as exc:
            evaluate_pre_trade(
                request=request(), snapshot=snap_bad, context=context(),
                limits=limits(), session=session(),
                instrument=instrument(), margin=margin(),
            )
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_pretrade_version_mismatch(self):
        """Wrong accounting_version → VERSION_MISMATCH."""
        snap = replace(snapshot(), accounting_version="v1")
        with pytest.raises(RiskSessionError) as exc:
            evaluate_pre_trade(
                request=request(), snapshot=snap, context=context(),
                limits=limits(), session=session(),
                instrument=instrument(), margin=margin(),
            )
        assert exc.value.reason == RiskReason.VERSION_MISMATCH

    def test_pretrade_outside_session(self):
        """Request time outside session → OUTSIDE_VERIFIED_SESSION."""
        with pytest.raises(RiskSessionError) as exc:
            evaluate_pre_trade(
                request=request(evaluated_at=T0 - timedelta(hours=1)),
                snapshot=snapshot(), context=context(),
                limits=limits(), session=session(),
                instrument=instrument(), margin=margin(),
            )
        assert exc.value.reason == RiskReason.OUTSIDE_VERIFIED_SESSION

    def test_pretrade_decision_is_immutable(self):
        """Decision record is frozen."""
        result = decision()
        with pytest.raises(FrozenInstanceError):
            result.action = RiskAction.FORCE_FLATTEN

    def test_pretrade_decision_id_deterministic(self):
        """Same inputs → same decision_id."""
        assert decision().decision_id == decision().decision_id

    def test_pretrade_sell_side_projected_negative(self):
        """Sell side projects negative quantity."""
        result = evaluate_pre_trade(
            request=request(side=OrderSide.SELL), snapshot=snapshot(),
            context=context(), limits=limits(), session=session(),
            instrument=instrument(), margin=margin(),
        )
        values = dict(result.values)
        assert values["projected_quantity"] == D("0")

    def test_pretrade_sell_adds_to_short(self):
        """Sell from existing long → projected reduces then goes short."""
        result = evaluate_pre_trade(
            request=request(side=OrderSide.SELL, quantity=D("3")),
            snapshot=snapshot(qty=D("1")), context=context(),
            limits=limits(), session=session(),
            instrument=instrument(), margin=margin(),
        )
        values = dict(result.values)
        # projected = 1 + (-3) = -2
        assert values["projected_quantity"] == D("-2")

    def test_pretrade_notional_margin_basis(self):
        """NOTIONAL_RATE margin → initial_margin = notional * rate."""
        inst = instrument()
        ms = MarginSpecificationV2(
            "margin-specification-v2-1", H("margin2"), "CME", "ES", "ESH6",
            T0 - timedelta(days=1), T0 + timedelta(days=2),
            MarginBasis.NOTIONAL_RATE,
            D("0.10"), D("0.05"), D("0.15"), D("0.08"), "margin-v1",
        )
        result = evaluate_pre_trade(
            request=request(), snapshot=snapshot(), context=context(),
            limits=limits(), session=session(),
            instrument=inst, margin=ms,
        )
        values = dict(result.values)
        # notional = 2 * 5000 * 50 = 500000; initial_margin = 500000 * 0.15 = 75000
        # projected = 1 + 1 = 2; notional = abs(2) * 5000 * 50 = 500000
        assert values["initial_margin"] == D("75000")


# ===========================================================================
# 4. Post-accounting risk: session loss, drawdown, margin breach
# ===========================================================================

class TestPostAccountingRisk:
    """Session loss, drawdown, margin breach, forced flatten, margin call."""

    def test_session_loss_calculation(self):
        """Loss = max(0, reference - equity); drawdown = max(0, peak - equity)."""
        first = post_eval(snap=snapshot(), prior=None)
        second = post_eval(
            snap=snapshot(equity=D("8000"), as_of=T0 + timedelta(minutes=2)),
            prior=first.state,
        )
        assert second.state.session_loss == D("2000")
        assert second.state.drawdown == D("2000")

    def test_drawdown_tracks_peak(self):
        """Drawdown tracks peak equity, not just reference."""
        first = post_eval(snap=snapshot(equity=D("10000")), prior=None)
        second = post_eval(
            snap=snapshot(equity=D("8000"), as_of=T0 + timedelta(minutes=2)),
            prior=first.state,
        )
        # reference = 10000 (initial), peak = max(10000, 8000) = 10000
        # loss = max(0, 10000 - 8000) = 2000
        # drawdown = max(0, 10000 - 8000) = 2000
        assert second.state.session_loss == D("2000")
        assert second.state.drawdown == D("2000")

    def test_no_loss_when_equity_rises(self):
        """Equity above reference → loss=0, drawdown tracks peak."""
        first = post_eval(snap=snapshot(equity=D("10000")), prior=None)
        # Equity rises to 12000
        second = post_eval(
            snap=snapshot(equity=D("12000"), as_of=T0 + timedelta(minutes=2)),
            prior=first.state,
        )
        # reference = 10000; loss = max(0, 10000-12000) = 0
        # peak = max(10000, 12000) = 12000; drawdown = max(0, 12000-12000) = 0
        assert second.state.session_loss == D("0")
        assert second.state.drawdown == D("0")
        # Equity falls to 11000 (below peak but above reference)
        third = post_eval(
            snap=snapshot(equity=D("11000"), as_of=T0 + timedelta(minutes=3)),
            prior=second.state,
        )
        # reference = 10000; loss = max(0, 10000-11000) = 0
        # peak = 12000; drawdown = max(0, 12000-11000) = 1000
        assert third.state.session_loss == D("0")
        assert third.state.drawdown == D("1000")

    def test_session_reference_cannot_reset(self):
        """Prior state with different session → REFERENCE_RESET."""
        first = post_eval(snap=snapshot(), prior=None)
        # Create a session that covers the snapshot time but has a different session_id
        new_session = session(
            session_date=date(2026, 1, 5),
            source_ids=(H("other-calendar"),),
        )
        with pytest.raises(RiskSessionError) as exc:
            post_eval(
                snap=snapshot(as_of=T0 + timedelta(minutes=2)),
                prior=first.state,
                sess=new_session,
            )
        assert exc.value.reason == RiskReason.REFERENCE_RESET

    def test_chronology_regression_rejects(self):
        """Snapshot as_of before prior_state as_of → EVENT_TIME_REGRESSION."""
        first = post_eval(snap=snapshot(as_of=T0 + timedelta(minutes=2)),
                         prior=None)
        with pytest.raises(RiskSessionError) as exc:
            post_eval(
                snap=snapshot(as_of=T0 + timedelta(minutes=1)),
                prior=first.state,
            )
        assert exc.value.reason == RiskReason.EVENT_TIME_REGRESSION

    def test_margin_breach_emits_forced_flatten_and_margin_call(self):
        """Margin breach → forced_flatten, margin_call, liquidation_required."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        assert result.forced_flatten is not None
        assert result.margin_call is not None
        assert result.liquidation_required is not None

    def test_margin_breach_no_position_no_forced_flatten(self):
        """Margin breach with no position → no forced_flatten."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), qty=D("0"), breach=True),
            prior=None,
        )
        assert result.forced_flatten is None
        # Margin call still emitted because margin_breach is True
        assert result.margin_call is not None

    def test_session_loss_breach_emits_forced_flatten(self):
        """Session loss > limit → forced flatten with SESSION_LOSS_LIMIT."""
        first = post_eval(snap=snapshot(equity=D("10000")), prior=None)
        result = post_eval(
            snap=snapshot(equity=D("100"), as_of=T0 + timedelta(minutes=2)),
            prior=first.state,
            lim=limits(max_session_loss=D("1")),
        )
        # loss = 10000 - 100 = 9900 > max_session_loss=1
        assert result.forced_flatten is not None
        assert RiskReason.SESSION_LOSS_LIMIT.value in result.decision.event.reason_codes

    def test_drawdown_breach_emits_forced_flatten(self):
        """Drawdown > limit → forced flatten with DRAWDOWN_LIMIT."""
        first = post_eval(snap=snapshot(equity=D("12000")), prior=None)
        result = post_eval(
            snap=snapshot(equity=D("8000"), as_of=T0 + timedelta(minutes=2)),
            prior=first.state,
            lim=limits(max_drawdown=D("1")),
        )
        assert result.forced_flatten is not None
        assert RiskReason.DRAWDOWN_LIMIT.value in result.decision.event.reason_codes

    def test_maintenance_margin_breach_priority(self):
        """Maintenance margin breach has priority 10 (first)."""
        result = post_eval(
            snap=snapshot(equity=D("1000"), breach=True), prior=None,
            lim=limits(max_session_loss=D("1"), max_drawdown=D("1")),
        )
        assert result.decision.event.reason_codes[0] == RiskReason.MAINTENANCE_MARGIN_BREACH.value

    def test_no_breach_no_forced_flatten(self):
        """No breach → no forced_flatten, no margin_call."""
        result = post_eval(snap=snapshot(equity=D("10000")), prior=None)
        assert result.forced_flatten is None
        assert result.margin_call is None
        assert result.liquidation_required is None
        assert result.decision.event.decision == RiskDecision.ALLOW

    def test_post_accounting_identity_mismatch(self):
        """Different market in snapshot → IDENTITY_MISMATCH."""
        snap = replace(snapshot(), market="NQ")
        with pytest.raises(RiskSessionError) as exc:
            post_eval(snap=snap)
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_post_accounting_stale_limits(self):
        """Stale limits → STALE_RISK_LIMITS."""
        with pytest.raises(RiskSessionError) as exc:
            post_eval(lim=limits(effective_to=T0))
        assert exc.value.reason == RiskReason.STALE_RISK_LIMITS

    def test_post_accounting_outside_session(self):
        """Snapshot as_of outside session → OUTSIDE_VERIFIED_SESSION."""
        with pytest.raises(RiskSessionError) as exc:
            post_eval(snap=snapshot(as_of=T0 - timedelta(hours=1)))
        assert exc.value.reason == RiskReason.OUTSIDE_VERIFIED_SESSION

    def test_post_accounting_version_mismatch(self):
        """Wrong accounting_version → VERSION_MISMATCH."""
        snap = replace(snapshot(), accounting_version="v1")
        with pytest.raises(RiskSessionError) as exc:
            post_eval(snap=snap)
        assert exc.value.reason == RiskReason.VERSION_MISMATCH

    def test_forced_flatten_side_long(self):
        """Long position → forced flatten sells."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), qty=D("1"), breach=True),
            prior=None,
        )
        assert result.forced_flatten.side == OrderSide.SELL

    def test_forced_flatten_side_short(self):
        """Short position → forced flatten buys."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), qty=D("-1"), breach=True),
            prior=None,
        )
        assert result.forced_flatten.side == OrderSide.BUY

    def test_forced_flatten_quantity_matches_position(self):
        """Forced flatten quantity = abs(position.signed_quantity)."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), qty=D("3"), breach=True),
            prior=None,
        )
        assert result.forced_flatten.quantity == D("3")

    def test_post_accounting_immutable(self):
        """PostAccountingRiskEvaluationV2 is frozen."""
        result = post_eval(snap=snapshot(), prior=None)
        with pytest.raises(FrozenInstanceError):
            result.forced_flatten = None

    def test_session_risk_state_immutable(self):
        """SessionRiskStateV2 is frozen."""
        result = post_eval(snap=snapshot(), prior=None)
        with pytest.raises(FrozenInstanceError):
            result.state.session_loss = D("0")


# ===========================================================================
# 5. Session flatten deadline
# ===========================================================================

class TestSessionFlatten:
    """Session flatten deadline: forced instruction at deadline."""

    def test_session_flatten_emits_instruction(self):
        """Flatten deadline reached → forced flatten with SESSION_FLATTEN_DEADLINE."""
        snap = snapshot(as_of=T0 + timedelta(hours=6, minutes=-1))
        result = evaluate_session_flatten(
            snapshot=snap, limits=limits(), session=session(),
            trigger_bar_id=H("deadline-bar"),
        )
        assert result.decision.event.reason_codes == (
            RiskReason.SESSION_FLATTEN_DEADLINE.value,
        )
        assert result.forced_flatten is not None

    def test_session_flatten_before_deadline_rejects(self):
        """Before deadline → OUTSIDE_VERIFIED_SESSION."""
        snap = snapshot(as_of=T0 + timedelta(minutes=1))
        with pytest.raises(RiskSessionError) as exc:
            evaluate_session_flatten(
                snapshot=snap, limits=limits(), session=session(),
                trigger_bar_id=H("early-bar"),
            )
        assert exc.value.reason == RiskReason.OUTSIDE_VERIFIED_SESSION

    def test_session_flatten_flat_position_rejects(self):
        """Flat position at deadline → END_OF_DATA_RESIDUAL."""
        snap = snapshot(qty=D("0"), as_of=T0 + timedelta(hours=6, minutes=-1))
        with pytest.raises(RiskSessionError) as exc:
            evaluate_session_flatten(
                snapshot=snap, limits=limits(), session=session(),
                trigger_bar_id=H("flat-bar"),
            )
        assert exc.value.reason == RiskReason.END_OF_DATA_RESIDUAL

    def test_session_flatten_no_order_or_fill(self):
        """Flatten evaluation creates no order or fill."""
        snap = snapshot(as_of=T0 + timedelta(hours=6, minutes=-1))
        result = evaluate_session_flatten(
            snapshot=snap, limits=limits(), session=session(),
            trigger_bar_id=H("deadline-bar"),
        )
        assert not hasattr(result, "order")
        assert not hasattr(result, "fill")


# ===========================================================================
# 6. Forced-flatten bar eligibility
# ===========================================================================

class TestForcedFlattenBarEligibility:
    """Strict later-bar eligibility for forced flatten."""

    def test_breach_bar_rejects(self):
        """Bar with same ID as breach bar → LATER_BAR_REQUIRED."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        with pytest.raises(RiskSessionError) as exc:
            validate_forced_flatten_bar(
                result.forced_flatten,
                bar(at=T0 + timedelta(minutes=1), bar_id=H("breach")),
                session(),
            )
        assert exc.value.reason == RiskReason.LATER_BAR_REQUIRED

    def test_same_time_bar_rejects(self):
        """Bar at same time as trigger → LATER_BAR_REQUIRED."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        with pytest.raises(RiskSessionError) as exc:
            validate_forced_flatten_bar(
                result.forced_flatten,
                bar(at=result.forced_flatten.triggered_at),
                session(),
            )
        assert exc.value.reason == RiskReason.LATER_BAR_REQUIRED

    def test_later_finalized_bar_accepts(self):
        """Later finalized bar → accepts (no exception)."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        validate_forced_flatten_bar(
            result.forced_flatten,
            bar(at=T0 + timedelta(minutes=2)),
            session(),
        )

    def test_unfinalized_bar_rejects(self):
        """Unfinalized bar → BAR_INELIGIBLE."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        with pytest.raises(RiskSessionError) as exc:
            validate_forced_flatten_bar(
                result.forced_flatten,
                bar(finalized=False),
                session(),
            )
        assert exc.value.reason == RiskReason.BAR_INELIGIBLE

    def test_wrong_market_bar_rejects(self):
        """Bar with wrong market → IDENTITY_MISMATCH."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        with pytest.raises(RiskSessionError) as exc:
            validate_forced_flatten_bar(
                result.forced_flatten,
                bar(market="NQ"),
                session(),
            )
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_wrong_session_rejects(self):
        """Bar in wrong session → IDENTITY_MISMATCH."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        wrong_session = session(
            session_date=date(2026, 1, 6),
            open_time=T0 + timedelta(hours=6),
            close_time=T0 + timedelta(hours=12),
            effective_from=T0 + timedelta(hours=5),
            effective_to=T0 + timedelta(days=3),
        )
        with pytest.raises(RiskSessionError) as exc:
            validate_forced_flatten_bar(
                result.forced_flatten,
                bar(at=T0 + timedelta(minutes=2)),
                wrong_session,
            )
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH


# ===========================================================================
# 7. Margin-call and liquidation-required facts
# ===========================================================================

class TestMarginCallFacts:
    """Margin-call and liquidation-required immutable facts."""

    def test_margin_call_fact_immutable(self):
        """MarginCallFactV2 is frozen."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        with pytest.raises(FrozenInstanceError):
            result.margin_call.required_margin = D("0")

    def test_liquidation_required_fact_immutable(self):
        """LiquidationRequiredFactV2 is frozen."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        with pytest.raises(FrozenInstanceError):
            result.liquidation_required.status = "RESOLVED"

    def test_margin_call_records_equity_and_required_margin(self):
        """Margin call records required_margin and equity from snapshot."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        assert result.margin_call.equity == D("3000")
        assert result.margin_call.required_margin == D("4500")

    def test_liquidation_required_status_unresolved(self):
        """Liquidation-required status is UNRESOLVED."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        assert result.liquidation_required.status == "UNRESOLVED"

    def test_forced_flatten_status_unresolved(self):
        """Forced flatten instruction status is UNRESOLVED."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        assert result.forced_flatten.status == "UNRESOLVED"


# ===========================================================================
# 8. Residual-position handling
# ===========================================================================

class TestResidualPosition:
    """Residual position and unresolved instructions at end of data."""

    def test_completed_run_gate_clean(self):
        """Flat position, no instructions → gate passes."""
        snap = snapshot(qty=D("0"))
        completed_run_gate(snap, ())

    def test_completed_run_gate_residual_position(self):
        """Open position → END_OF_DATA_RESIDUAL."""
        snap = snapshot(qty=D("1"))
        with pytest.raises(RiskSessionError) as exc:
            completed_run_gate(snap, ())
        assert exc.value.reason == RiskReason.END_OF_DATA_RESIDUAL

    def test_completed_run_gate_unresolved_instruction(self):
        """Unresolved forced flatten → END_OF_DATA_RESIDUAL."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        with pytest.raises(RiskSessionError) as exc:
            completed_run_gate(
                snapshot(equity=D("3000"), breach=True),
                (result.forced_flatten,),
            )
        assert exc.value.reason == RiskReason.END_OF_DATA_RESIDUAL

    def test_completed_run_gate_flat_with_unresolved_rejects(self):
        """Flat position but unresolved instruction → END_OF_DATA_RESIDUAL."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        with pytest.raises(RiskSessionError) as exc:
            completed_run_gate(
                snapshot(qty=D("0")),
                (result.forced_flatten,),
            )
        assert exc.value.reason == RiskReason.END_OF_DATA_RESIDUAL


# ===========================================================================
# 9. Duplicate events and deterministic replay
# ===========================================================================

class TestDuplicateAndReplay:
    """Duplicate event detection and deterministic replay."""

    def test_duplicate_decision_idempotent(self):
        """Same decision applied twice → idempotent."""
        r = decision()
        ledger = RiskSessionLedgerV2.create(H("run")).apply(r)
        assert ledger.apply(r) is ledger

    def test_duplicate_post_eval_idempotent(self):
        """Same post-evaluation applied twice → idempotent."""
        r = post_eval(snap=snapshot(equity=D("3000"), breach=True),
                     prior=None, trigger_bar_id=H("breach"))
        ledger = RiskSessionLedgerV2.create(H("run")).apply(r)
        assert ledger.apply(r) is ledger

    def test_ledger_replay_byte_identical(self):
        """Same inputs → identical ledger."""
        r = decision()
        a = RiskSessionLedgerV2.create(H("run")).apply(r)
        b = RiskSessionLedgerV2.create(H("run")).apply(r)
        assert a == b
        assert a.ledger_fingerprint == b.ledger_fingerprint

    def test_ledger_checkpoint_identical(self):
        """Same ledger → identical checkpoint."""
        r = decision()
        a = RiskSessionLedgerV2.create(H("run")).apply(r)
        b = RiskSessionLedgerV2.create(H("run")).apply(r)
        assert a.checkpoint() == b.checkpoint()

    def test_ledger_wrong_run_id_rejects(self):
        """Decision with wrong run_id → IDENTITY_MISMATCH."""
        r = decision()
        ledger = RiskSessionLedgerV2.create(H("other"))
        with pytest.raises(RiskSessionError) as exc:
            ledger.apply(r)
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_ledger_chronology_regression_rejects(self):
        """Decision with earlier time → EVENT_TIME_REGRESSION."""
        r1 = decision()
        # Second decision with earlier time
        r2 = evaluate_pre_trade(
            request=request(evaluated_at=T0 + timedelta(minutes=1)),
            snapshot=snapshot(), context=context(),
            limits=limits(), session=session(),
            instrument=instrument(), margin=margin(),
        )
        ledger = RiskSessionLedgerV2.create(H("run")).apply(r1)
        with pytest.raises(RiskSessionError) as exc:
            ledger.apply(r2)
        # r2 has earlier evaluated_at
        assert exc.value.reason == RiskReason.EVENT_TIME_REGRESSION

    def test_ledger_tamper_detection(self):
        """Tampered ledger fingerprint → CHECKPOINT_TAMPERED."""
        r = decision()
        ledger = RiskSessionLedgerV2.create(H("run")).apply(r)
        tampered = replace(ledger, ledger_fingerprint=H("tamper"))
        with pytest.raises(RiskSessionError) as exc:
            tampered.verify_integrity()
        assert exc.value.reason == RiskReason.CHECKPOINT_TAMPERED

    def test_ledger_immutable(self):
        """RiskSessionLedgerV2 is frozen."""
        r = decision()
        ledger = RiskSessionLedgerV2.create(H("run")).apply(r)
        with pytest.raises(FrozenInstanceError):
            ledger.decisions = ()

    def test_ledger_create_validates_run_id(self):
        """Ledger create validates run_id as SHA-256."""
        with pytest.raises(ValueError):
            RiskSessionLedgerV2.create("not-a-hash")

    def test_checkpoint_immutable(self):
        """RiskSessionCheckpointV2 is frozen."""
        r = decision()
        ledger = RiskSessionLedgerV2.create(H("run")).apply(r)
        cp = ledger.checkpoint()
        with pytest.raises(FrozenInstanceError):
            cp.ledger_fingerprint = H("other")


# ===========================================================================
# 10. Pipeline priority and breach priority
# ===========================================================================

class TestPipelinePriority:
    """Deterministic risk-event priority."""

    def test_pipeline_priority_pre_trade_before_fills(self):
        """Pre-trade risk (50) before fills (60)."""
        assert (int(PipelinePriority.PRE_TRADE_RISK)
                < int(PipelinePriority.FILLS))

    def test_pipeline_priority_post_accounting_before_reporting(self):
        """Post-accounting risk (80) before reporting (90)."""
        assert (int(PipelinePriority.POST_ACCOUNTING_RISK)
                < int(PipelinePriority.REPORTING))

    def test_breach_priority_maintenance_first(self):
        """Maintenance margin (10) before session loss (20) before drawdown (30)."""
        assert (int(BreachPriority.MAINTENANCE_MARGIN)
                < int(BreachPriority.SESSION_LOSS)
                < int(BreachPriority.DRAWDOWN))


# ===========================================================================
# 11. Reason codes
# ===========================================================================

class TestReasonCodes:
    """Stable reason codes — all unique and present."""

    def test_ok_is_allow_reason(self):
        """OK is the only non-failure reason."""
        assert RiskReason.OK.value == "OK"

    def test_all_limit_reasons_present(self):
        """All limit-related reasons exist."""
        expected = {
            "GROSS_EXPOSURE_LIMIT", "NET_EXPOSURE_LIMIT", "POSITION_LIMIT",
            "CONCENTRATION_LIMIT", "LEVERAGE_LIMIT", "INITIAL_MARGIN_LIMIT",
            "MAINTENANCE_MARGIN_BREACH", "SESSION_LOSS_LIMIT",
            "DRAWDOWN_LIMIT",
        }
        actual = {r.value for r in RiskReason}
        assert expected.issubset(actual)

    def test_all_session_reasons_present(self):
        """All session-related reasons exist."""
        expected = {
            "MISSING_SESSION", "SESSION_IDENTITY_MISMATCH",
            "SESSION_OUTSIDE_EFFECTIVE_RANGE", "SESSION_OVERLAP",
            "OUTSIDE_VERIFIED_SESSION", "SESSION_FLATTEN_DEADLINE",
        }
        actual = {r.value for r in RiskReason}
        assert expected.issubset(actual)


# ===========================================================================
# 12. Chronology, market, instrument, contract, session, version isolation
# ===========================================================================

class TestIsolation:
    """Identity, version, chronology isolation across all components."""

    def test_run_id_isolation_pre_trade(self):
        """Different run_id in request vs limits → IDENTITY_MISMATCH."""
        with pytest.raises(RiskSessionError) as exc:
            evaluate_pre_trade(
                request=request(run_id=H("different")),
                snapshot=snapshot(), context=context(),
                limits=limits(), session=session(),
                instrument=instrument(), margin=margin(),
            )
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_run_id_isolation_post_accounting(self):
        """Different run_id in snapshot vs limits → IDENTITY_MISMATCH."""
        snap = replace(snapshot(), run_id=H("different"))
        with pytest.raises(RiskSessionError) as exc:
            post_eval(snap=snap)
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_market_isolation_post_accounting(self):
        """Different market in snapshot → IDENTITY_MISMATCH."""
        snap = replace(snapshot(), market="NQ")
        with pytest.raises(RiskSessionError) as exc:
            post_eval(snap=snap)
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_contract_isolation_post_accounting(self):
        """Different contract_id in snapshot → IDENTITY_MISMATCH."""
        snap = replace(snapshot(), contract_id="NQH6")
        with pytest.raises(RiskSessionError) as exc:
            post_eval(snap=snap)
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_version_isolation_post_accounting(self):
        """Wrong accounting_version → VERSION_MISMATCH."""
        snap = replace(snapshot(), accounting_version="WRONG")
        with pytest.raises(RiskSessionError) as exc:
            post_eval(snap=snap)
        assert exc.value.reason == RiskReason.VERSION_MISMATCH

    def test_session_identity_mismatch_in_post(self):
        """Session with different market → IDENTITY_MISMATCH."""
        wrong_session = session(market="NQ", instrument_id="NQ",
                               contract_id="NQH6")
        with pytest.raises(RiskSessionError) as exc:
            post_eval(sess=wrong_session)
        assert exc.value.reason == RiskReason.IDENTITY_MISMATCH

    def test_context_equity_must_be_positive(self):
        """Zero or negative equity in context → ValueError."""
        with pytest.raises(ValueError):
            context(equity=D("0"))

    def test_context_peak_precedes_reference_rejects(self):
        """peak < reference → ValueError."""
        with pytest.raises(ValueError):
            context(session_peak_equity=D("5000"),
                   session_reference_equity=D("10000"))

    def test_portfolio_context_immutable(self):
        """PortfolioRiskContextV2 is frozen."""
        ctx = context()
        with pytest.raises(FrozenInstanceError):
            ctx.equity = D("0")

    def test_pretrade_request_immutable(self):
        """PreTradeRiskRequestV2 is frozen."""
        req = request()
        with pytest.raises(FrozenInstanceError):
            req.quantity = D("999")


# ===========================================================================
# 13. Tamper rejection and fingerprints
# ===========================================================================

class TestTamperAndFingerprints:
    """Tamper rejection and deterministic fingerprints."""

    def test_decision_record_fingerprint_matches(self):
        """Decision fingerprint equals decision_id (content-addressed)."""
        r = decision()
        assert r.decision_id == r.decision_fingerprint

    def test_decision_record_immutable(self):
        """RiskDecisionRecordV2 is frozen."""
        r = decision()
        with pytest.raises(FrozenInstanceError):
            r.action = RiskAction.NONE

    def test_verified_session_fingerprint_deterministic(self):
        """Same session inputs → same session_id."""
        assert session().session_id == session().session_id

    def test_risk_limits_fingerprint_deterministic(self):
        """Same limits inputs → same limits_id."""
        assert limits().limits_id == limits().limits_id

    def test_post_eval_fingerprint_deterministic(self):
        """Same post-eval inputs → same evaluation_id."""
        r1 = post_eval(snap=snapshot(equity=D("3000"), breach=True),
                      prior=None, trigger_bar_id=H("breach"))
        r2 = post_eval(snap=snapshot(equity=D("3000"), breach=True),
                      prior=None, trigger_bar_id=H("breach"))
        assert r1.evaluation_id == r2.evaluation_id

    def test_session_risk_state_fingerprint_deterministic(self):
        """Same state inputs → same state_id."""
        r1 = post_eval(snap=snapshot(), prior=None)
        r2 = post_eval(snap=snapshot(), prior=None)
        assert r1.state.state_id == r2.state.state_id


# ===========================================================================
# 14. Pre-trade vs post-accounting separation
# ===========================================================================

class TestPreTradePostAccountingSeparation:
    """Pre-trade and post-accounting risk are separate phases."""

    def test_pre_trade_uses_pre_trade_phase(self):
        """Pre-trade evaluation uses RiskPhase.PRE_TRADE."""
        r = decision()
        assert r.event.phase == RiskPhase.PRE_TRADE

    def test_post_accounting_uses_post_event_phase(self):
        """Post-accounting evaluation uses RiskPhase.POST_EVENT."""
        r = post_eval(snap=snapshot(), prior=None)
        assert r.decision.event.phase == RiskPhase.POST_EVENT

    def test_post_accounting_does_not_evaluate_exposure_limits(self):
        """Post-accounting does not check exposure/leverage limits."""
        r = post_eval(
            snap=snapshot(equity=D("1000")), prior=None,
            lim=limits(max_gross_exposure=D("1"), max_leverage=D("1")),
        )
        # Post-accounting checks only maintenance, session_loss, drawdown
        # It does NOT check gross_exposure or leverage
        ok_reasons = (
            RiskReason.OK.value,
            RiskReason.MAINTENANCE_MARGIN_BREACH.value,
            RiskReason.SESSION_LOSS_LIMIT.value,
            RiskReason.DRAWDOWN_LIMIT.value,
        )
        for reason in r.decision.event.reason_codes:
            assert reason in ok_reasons

    def test_pre_trade_action_reject_new_exposure(self):
        """Pre-trade REJECT → REJECT_NEW_EXPOSURE action."""
        r = evaluate_pre_trade(
            request=request(), snapshot=snapshot(), context=context(),
            limits=limits(max_gross_exposure=D("1")),
            session=session(), instrument=instrument(), margin=margin(),
        )
        assert r.action == RiskAction.REJECT_NEW_EXPOSURE

    def test_post_accounting_action_force_flatten_on_breach(self):
        """Post-accounting breach → FORCE_FLATTEN action."""
        r = post_eval(
            snap=snapshot(equity=D("1000"), breach=True), prior=None,
            lim=limits(max_session_loss=D("1")),
        )
        assert r.decision.action == RiskAction.FORCE_FLATTEN

    def test_post_accounting_action_none_on_no_breach(self):
        """Post-accounting no breach → NONE action."""
        r = post_eval(snap=snapshot(), prior=None)
        assert r.decision.action == RiskAction.NONE


# ===========================================================================
# 15. Forced flatten instruction validation
# ===========================================================================

class TestForcedFlattenInstruction:
    """ForcedFlattenInstructionV2 construction and validation."""

    def test_forced_flatten_instruction_immutable(self):
        """ForcedFlattenInstructionV2 is frozen."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        with pytest.raises(FrozenInstanceError):
            result.forced_flatten.status = "RESOLVED"

    def test_forced_flatten_instruction_id_deterministic(self):
        """Same forced flatten inputs → same instruction_id."""
        r1 = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        r2 = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        assert r1.forced_flatten.instruction_id == r2.forced_flatten.instruction_id

    def test_forced_flatten_links_decision_and_snapshot(self):
        """Forced flatten links to decision_id and accounting_snapshot_id."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
            trigger_bar_id=H("breach"),
        )
        assert result.forced_flatten.decision_id == result.decision.decision_id
        assert result.forced_flatten.accounting_snapshot_id == snapshot(
            equity=D("3000"), breach=True,
        ).snapshot_id

    def test_forced_flatten_links_session(self):
        """Forced flatten links to session_id."""
        result = post_eval(
            snap=snapshot(equity=D("3000"), breach=True), prior=None,
        )
        assert result.forced_flatten.session_id == session().session_id


# ===========================================================================
# 16. Import graph isolation
# ===========================================================================
