"""Hermes independent adversarial audit tests for V2 Phase 3 conservative OHLC execution.

These tests are independent of the existing test suite and exercise edge cases,
boundary conditions, and invariant violations that the existing tests may not
cover. They are offline and deterministic.

Audit assignment: AUDIT-V2-PHASE3-CONSERVATIVE-OHLC

Covers all 9 required audit cases:
  1. Market orders — no signal-bar fill, later-bar eligibility, absent next bar,
     invalid session/contract/data rejection
  2. Limit orders — exact touch, no-touch, gap through, no favorable improvement,
     buy/sell symmetry
  3. Stop-market orders — exact trigger, gap through, next observable open + adverse
     slippage, buy/sell symmetry
  4. Stop-limit orders — trigger/fill separation, no same-event trigger/fill,
     triggered-unfilled persistence, later eligible limit fill, cancellation/expiration
  5. Intrabar collisions — adverse threshold wins, unresolved ownership rejects,
     no fabricated OHLC path
  6. Tick rounding and costs — buys round adversely upward, sells downward, exact
     tick boundaries unchanged, slippage applied once, Decimal-only
  7. Participation — shared per-contract/bar volume budget, zero volume no fill,
     missing required volume rejects, deterministic priority, stable tie-break,
     partial fills conserve quantity, combined fills never exceed budget
  8. IOC and order lifecycle — first eligible evaluation only, residual cancellation,
     no later fill after cancellation, ledger/fill lineage immutability
  9. Determinism and replay — repeated execution byte-identical, reordered economic
     inputs reject or resolve by frozen priority, schema/version mismatch rejects,
     checkpoint/replay equivalence, tampering detected
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2.contracts import (
    InstrumentSpecificationV2, OrderIntentV2, OrderSide, OrderState, OrderType,
    TimeInForce,
)
from backtesting.execution_accounting_v2.ohlc_execution import (
    CollisionGroupV2, CollisionRole, EXECUTION_POLICY_VERSION,
    LIQUIDITY_POLICY_VERSION, ExecutionEvaluationV2, ExecutionFillV2,
    ExecutionInstructionV2, ExecutionPolicyV2, ExecutionPriority,
    ExecutionReason, ExecutionSourceLineageV2, OHLCBarV2, OHLCExecutionError, evaluate_bar,
)
from backtesting.execution_accounting_v2.order_ledger import (
    LedgerCheckpointV2, LedgerEventKind, OrderLedgerError, OrderLedgerEventV2,
    OrderLedgerReason, OrderLedgerV2,
)
from backtesting.execution_accounting_v2.specifications import (
    InstrumentProfile, canonical_fingerprint, canonical_json_bytes,
)


UTC = timezone.utc
START = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
H = lambda value: hashlib.sha256(value.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def intent(name="order", **changes):
    values = dict(
        schema_version="order-intent-v2-1",
        order_id=H(name),
        run_id=H("run"),
        action_id=H(f"action-{name}"),
        market="ES",
        instrument_id="ES",
        contract_id="ESM5",
        side=OrderSide.BUY,
        quantity=Decimal("3"),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.GTC,
        limit_price=None,
        stop_price=None,
        submitted_at=START,
        activation_at=START + timedelta(minutes=2),
        expires_at=None,
        parent_order_id=None,
        replaces_order_id=None,
        configuration_version="config-v2",
        execution_policy_version=EXECUTION_POLICY_VERSION,
    )
    values.update(changes)
    return OrderIntentV2(**values)


def ledger_for(*intents):
    """Build a ledger with SUBMIT→ACCEPT→ACTIVATE for each intent."""
    ledger = OrderLedgerV2.create(tuple(intents))
    for kind, minute in (
        (LedgerEventKind.SUBMIT, 1),
        (LedgerEventKind.ACCEPT, 2),
        (LedgerEventKind.ACTIVATE, 3),
    ):
        ordered = sorted(intents, key=lambda selected:
            H(f"setup-{kind.value}-{selected.order_id}"))
        for selected in ordered:
            snap = ledger.order(selected.order_id)
            event_time = max(START + timedelta(minutes=minute), selected.activation_at) if kind == LedgerEventKind.ACTIVATE else START + timedelta(minutes=minute)
            event = OrderLedgerEventV2(
                "order-ledger-event-v2-1",
                H(f"setup-{kind.value}-{selected.order_id}"),
                selected.order_id,
                kind,
                event_time,
                len(ledger.events) + 1,
                snap.order_version,
                selected.market,
                selected.instrument_id,
                selected.contract_id,
                H(f"setup-source-{len(ledger.events)+1}"),
                kind.value,
                contract_eligibility_verified=True,
            )
            ledger = ledger.apply(event)
    return ledger


def instrument(**changes):
    values = dict(
        schema_version="instrument-spec-v2-1",
        specification_id=H("instrument"),
        market="ES",
        instrument_id="ES",
        contract_id="ESM5",
        profile=InstrumentProfile.ES_FUTURE,
        currency="USD",
        tick_size=Decimal("0.25"),
        quantity_step=Decimal("1"),
        contract_multiplier=Decimal("50"),
        point_value=Decimal("50"),
        effective_from=START - timedelta(days=1),
        effective_to=None,
        evidence_ids=(H("evidence"),),
    )
    values.update(changes)
    return InstrumentSpecificationV2(**values)


def policy(**changes):
    values = dict(
        schema_version="ohlc-execution-policy-v2-1",
        policy_id=H("policy"),
        execution_policy_version=EXECUTION_POLICY_VERSION,
        liquidity_policy_version=LIQUIDITY_POLICY_VERSION,
        maximum_participation_rate=Decimal("0.10"),
        assumption_version="assumption-v1",
    )
    values.update(changes)
    return ExecutionPolicyV2(**values)


def source_bar(order, **changes):
    values = dict(schema_version="ohlc-bar-v2-1", bar_id=H(f"source-{order.order_id}"),
        market=order.market, instrument_id=order.instrument_id, contract_id=order.contract_id,
        open_time=START - timedelta(minutes=1), close_time=START, available_at=START,
        open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"),
        volume=Decimal("100"), finalized=True, session_eligible=True, data_quality_valid=True,
        contract_eligible=True, source_version="dataset-v1")
    values.update(changes)
    return OHLCBarV2(**values)


def instruction(order, *, priority=ExecutionPriority.ENTRY_OR_ROLLOVER_INCOMING,
                participation="0.10", slippage="1", source=None):
    activation_time = max(START + timedelta(minutes=3), order.activation_at)
    lineage = ExecutionSourceLineageV2.create(source_bar=source or source_bar(order),
        action_id=order.action_id, order_id=order.order_id,
        activation_event_id=H(f"setup-{LedgerEventKind.ACTIVATE.value}-{order.order_id}"),
        activation_event_time=activation_time)
    return ExecutionInstructionV2(
        "execution-instruction-v2-1",
        H(f"instruction-{order.order_id}"),
        order.order_id,
        priority,
        Decimal(participation),
        Decimal(slippage),
        "assumption-v1",
        lineage,
    )


def bar(name="bar", **changes):
    values = dict(
        schema_version="ohlc-bar-v2-1",
        bar_id=H(name),
        market="ES",
        instrument_id="ES",
        contract_id="ESM5",
        open_time=START + timedelta(minutes=10),
        close_time=START + timedelta(minutes=11),
        available_at=START + timedelta(minutes=11),
        open=Decimal("100.00"),
        high=Decimal("102.00"),
        low=Decimal("98.00"),
        close=Decimal("101.00"),
        volume=Decimal("100"),
        finalized=True,
        session_eligible=True,
        data_quality_valid=True,
        contract_eligible=True,
        source_version="dataset-v1",
    )
    values.update(changes)
    return OHLCBarV2(**values)


def evaluate(order, selected_bar=None, selected_instruction=None,
             selected_policy=None, selected_instrument=None,
             collision_groups=()):
    source = ledger_for(order)
    observed = selected_bar or bar()
    return source, evaluate_bar(
        ledger=source,
        bar=observed,
        evaluated_at=observed.available_at,
        instrument=selected_instrument or instrument(),
        policy=selected_policy or policy(),
        instructions=(selected_instruction or instruction(order),),
        collision_groups=collision_groups,
    )


def next_bar(name="next", minute_offset=12, **changes):
    """A bar one minute after the default bar."""
    return bar(name,
        open_time=START + timedelta(minutes=minute_offset),
        close_time=START + timedelta(minutes=minute_offset + 1),
        available_at=START + timedelta(minutes=minute_offset + 1),
        **changes)


# ===========================================================================
# 1. Market orders
# ===========================================================================

class TestMarketOrders:
    """Market orders never fill on the signal bar; first eligible later bar."""

    def test_prior_finalized_bar_order_active_at_next_bar_open_is_eligible(self):
        """Equality is eligible only with cryptographically bound prior-bar lineage."""
        order = intent(activation_at=START + timedelta(minutes=10))
        source = ledger_for(order)
        evaluated_bar = bar()
        assert evaluated_bar.open_time == order.activation_at
        result = evaluate_bar(
            ledger=source, bar=evaluated_bar, evaluated_at=evaluated_bar.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert len(result.fills) == 1  # fills normally

    def test_market_buy_strictly_after_bar_open_rejects(self):
        """activation_at > bar.open_time → SAME_SOURCE_BAR_INELIGIBLE."""
        late = intent(activation_at=START + timedelta(minutes=10, seconds=1))
        late_source = ledger_for(late)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=late_source, bar=bar(), evaluated_at=bar().available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(late),),
            )
        assert exc.value.reason == ExecutionReason.SAME_SOURCE_BAR_INELIGIBLE

    def test_market_buy_fills_at_first_eligible_later_bar(self):
        """Market buy fills at the open of the first eligible later bar."""
        order = intent()
        source, result = evaluate(order)
        fill = result.fills[0]
        assert fill.execution_rule_code == "MARKET_NEXT_ELIGIBLE_OPEN"
        assert fill.reference_price == Decimal("100")
        # economic = open + slip (BUY: 100 + 0.25 = 100.25)
        assert fill.economic_price == Decimal("100.25")

    def test_market_sell_fills_at_first_eligible_later_bar(self):
        """Market sell fills at open minus adverse slippage."""
        order = intent(side=OrderSide.SELL)
        source, result = evaluate(order)
        fill = result.fills[0]
        assert fill.execution_rule_code == "MARKET_NEXT_ELIGIBLE_OPEN"
        assert fill.reference_price == Decimal("100")
        # economic = open - slip (SELL: 100 - 0.25 = 99.75)
        assert fill.economic_price == Decimal("99.75")

    def test_market_buy_does_not_fill_on_current_bar_if_not_active(self):
        """Order not yet active at bar open → SAME_SOURCE_BAR_INELIGIBLE."""
        late = intent(activation_at=START + timedelta(minutes=10, seconds=1))
        late_source = ledger_for(late)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=late_source, bar=bar(), evaluated_at=bar().available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(late),),
            )
        assert exc.value.reason == ExecutionReason.SAME_SOURCE_BAR_INELIGIBLE

    def test_invalid_session_rejects(self):
        """Bar with session_eligible=False is rejected."""
        order = intent()
        source = ledger_for(order)
        bad_bar = bar(session_eligible=False)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=bad_bar, evaluated_at=bad_bar.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.BAR_INELIGIBLE

    def test_invalid_data_quality_rejects(self):
        """Bar with data_quality_valid=False is rejected."""
        order = intent()
        source = ledger_for(order)
        bad_bar = bar(data_quality_valid=False)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=bad_bar, evaluated_at=bad_bar.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.BAR_INELIGIBLE

    def test_invalid_contract_eligible_rejects(self):
        """Bar with contract_eligible=False is rejected."""
        order = intent()
        source = ledger_for(order)
        bad_bar = bar(contract_eligible=False)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=bad_bar, evaluated_at=bad_bar.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.BAR_INELIGIBLE

    def test_forming_bar_rejects(self):
        """Non-finalized bar is rejected."""
        order = intent()
        source = ledger_for(order)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=bar(finalized=False),
                evaluated_at=bar().available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.BAR_NOT_FINAL

    def test_evaluation_before_available_at_rejects(self):
        """Evaluation before bar.available_at is look-ahead → reject."""
        order = intent()
        source = ledger_for(order)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=bar(),
                evaluated_at=START + timedelta(minutes=10),
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.BAR_NOT_AVAILABLE

    def test_identity_mismatch_market_rejects(self):
        """Bar with different market/instrument is rejected."""
        order = intent()
        source = ledger_for(order)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=bar(market="NQ"),
                evaluated_at=bar().available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.IDENTITY_MISMATCH

    def test_version_mismatch_rejects(self):
        """Wrong execution_policy_version is rejected at construction."""
        with pytest.raises(ValueError, match="unsupported execution policy"):
            ExecutionPolicyV2(
                "ohlc-execution-policy-v2-1",
                H("badpolicy"),
                "WRONG_POLICY",
                LIQUIDITY_POLICY_VERSION,
                Decimal("0.10"),
                "assumption-v1",
            )

    def test_source_bar_falsely_labeled_active_at_its_open_rejects(self):
        """A timestamp cannot override identical source/evaluated bar identity."""
        signal_order = intent(activation_at=START + timedelta(minutes=10))
        signal_source = ledger_for(signal_order)
        signal_bar = bar()  # open_time = START + 10
        assert signal_bar.open_time == signal_order.activation_at
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(ledger=signal_source, bar=signal_bar,
                evaluated_at=signal_bar.available_at, instrument=instrument(), policy=policy(),
                instructions=(instruction(signal_order, source=signal_bar),))
        assert exc.value.reason == ExecutionReason.SAME_SOURCE_BAR_INELIGIBLE

    def test_identical_timestamps_with_distinct_source_bar_identity_are_eligible(self):
        order = intent(submitted_at=START + timedelta(minutes=10),
                       activation_at=START + timedelta(minutes=10))
        source = ledger_for(order); evaluated = bar("evaluated")
        prior = source_bar(order, available_at=evaluated.open_time,
                           close_time=evaluated.open_time,
                           open_time=evaluated.open_time - timedelta(minutes=1))
        result = evaluate_bar(ledger=source, bar=evaluated, evaluated_at=evaluated.available_at,
            instrument=instrument(), policy=policy(), instructions=(instruction(order, source=prior),))
        assert len(result.fills) == 1

    def test_missing_source_bar_lineage_rejects(self):
        order = intent(); source = ledger_for(order); observed = bar()
        unproven = replace(instruction(order), source_lineage=None)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(), instructions=(unproven,))
        assert exc.value.reason == ExecutionReason.SOURCE_LINEAGE_UNPROVEN

    def test_source_unavailable_until_after_evaluated_open_rejects(self):
        order = intent(submitted_at=START + timedelta(minutes=11),
                       activation_at=START + timedelta(minutes=11))
        source = ledger_for(order); observed = bar()
        late_source = source_bar(order, open_time=START + timedelta(minutes=10),
            close_time=START + timedelta(minutes=11), available_at=START + timedelta(minutes=11))
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order, source=late_source),))
        assert exc.value.reason == ExecutionReason.SOURCE_LINEAGE_UNPROVEN

    def test_first_genuinely_later_eligible_bar_uses_bound_source(self):
        order = intent(submitted_at=START + timedelta(minutes=3),
                       activation_at=START + timedelta(minutes=3))
        source = ledger_for(order)
        prior = source_bar(order, open_time=START + timedelta(minutes=2),
                           close_time=START + timedelta(minutes=3),
                           available_at=START + timedelta(minutes=3))
        first = bar("first-later", open_time=START + timedelta(minutes=3),
                    close_time=START + timedelta(minutes=4),
                    available_at=START + timedelta(minutes=4))
        result = evaluate_bar(ledger=source, bar=first, evaluated_at=first.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order, source=prior),))
        assert result.fills[0].market_event_id == first.bar_id


# ===========================================================================
# 2. Limit orders
# ===========================================================================

class TestLimitOrders:
    """Limit orders: exact touch, no-touch, gap through, no favorable improvement."""

    def test_buy_limit_exact_touch_at_low(self):
        """Buy limit fills when low <= limit_price."""
        order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("101"))
        source, result = evaluate(order)
        fill = result.fills[0]
        assert fill.reference_price == Decimal("101")
        assert fill.economic_price == Decimal("101")
        assert fill.execution_rule_code == "LIMIT_AT_FROZEN_PRICE"

    def test_buy_limit_touch_at_open(self):
        """Buy limit fills when open <= limit_price (open touches limit)."""
        order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("101"))
        touch_bar = bar(open=Decimal("101"), low=Decimal("98"))
        source, result = evaluate(order, selected_bar=touch_bar)
        fill = result.fills[0]
        assert fill.economic_price == Decimal("101")

    def test_buy_limit_no_touch(self):
        """Buy limit does not fill when low > limit_price."""
        order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("101"))
        no_touch = bar("no-touch", low=Decimal("101.25"), open=Decimal("102"),
                       high=Decimal("103"), close=Decimal("102"))
        source = ledger_for(order)
        result = evaluate_bar(
            ledger=source, bar=no_touch, evaluated_at=no_touch.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert result.fills == ()
        assert result.output_ledger == source

    def test_buy_limit_gap_through_still_at_limit(self):
        """Gap through limit (open < limit) still fills at limit, no improvement."""
        order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("101"))
        gap_bar = bar("gap", open=Decimal("99"), low=Decimal("99"),
                       high=Decimal("103"), close=Decimal("102"))
        source, result = evaluate(order, selected_bar=gap_bar)
        fill = result.fills[0]
        # Even though open is 99 (more favorable), fill is at 101
        assert fill.economic_price == Decimal("101")
        assert fill.reference_price == Decimal("101")

    def test_buy_limit_no_favorable_improvement(self):
        """Limit fill is always at the limit price, never better."""
        order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("99"))
        # bar open is 100, low is 98 — limit at 99 would touch via low
        source, result = evaluate(order)
        fill = result.fills[0]
        assert fill.economic_price == Decimal("99")
        # Even though low is 98 (better for buyer), price stays at 99

    def test_sell_limit_exact_touch_at_high(self):
        """Sell limit fills when high >= limit_price."""
        order = intent(side=OrderSide.SELL, order_type=OrderType.LIMIT,
                       limit_price=Decimal("101"))
        source, result = evaluate(order)
        fill = result.fills[0]
        assert fill.reference_price == Decimal("101")
        assert fill.economic_price == Decimal("101")
        assert fill.execution_rule_code == "LIMIT_AT_FROZEN_PRICE"

    def test_sell_limit_no_touch(self):
        """Sell limit does not fill when high < limit_price."""
        order = intent(side=OrderSide.SELL, order_type=OrderType.LIMIT,
                       limit_price=Decimal("103"))
        no_touch = bar("no-touch-sell", high=Decimal("102.25"),
                        open=Decimal("100"), low=Decimal("98"),
                        close=Decimal("101"))
        source = ledger_for(order)
        result = evaluate_bar(
            ledger=source, bar=no_touch, evaluated_at=no_touch.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert result.fills == ()

    def test_sell_limit_gap_through_still_at_limit(self):
        """Sell limit gap through (open > limit) still fills at limit."""
        order = intent(side=OrderSide.SELL, order_type=OrderType.LIMIT,
                       limit_price=Decimal("101"))
        gap_bar = bar("gap-sell", open=Decimal("103"), high=Decimal("104"),
                       low=Decimal("100"), close=Decimal("102"))
        source, result = evaluate(order, selected_bar=gap_bar)
        fill = result.fills[0]
        assert fill.economic_price == Decimal("101")

    def test_buy_sell_limit_symmetry(self):
        """Buy and sell limit at same price produce symmetric fill prices."""
        buy_order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("100"))
        sell_order = intent(side=OrderSide.SELL, order_type=OrderType.LIMIT,
                           limit_price=Decimal("100"))
        _, buy_result = evaluate(buy_order)
        _, sell_result = evaluate(sell_order)
        # Both fill at limit price 100
        assert buy_result.fills[0].economic_price == Decimal("100")
        assert sell_result.fills[0].economic_price == Decimal("100")

    def test_limit_does_not_apply_slippage(self):
        """Limit orders never have slippage applied — unrounded == economic == reference."""
        order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("101"))
        source, result = evaluate(order,
            selected_instruction=instruction(order, slippage="5"))
        fill = result.fills[0]
        assert fill.unrounded_economic_price == fill.economic_price == fill.reference_price

    def test_limit_friction_is_zero(self):
        """Limit fill friction is zero since economic == reference."""
        order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("101"))
        source, result = evaluate(order)
        fill = result.fills[0]
        assert fill.adverse_friction == Decimal("0")


# ===========================================================================
# 3. Stop-market orders
# ===========================================================================

class TestStopMarketOrders:
    """Stop-market: exact trigger, gap through, next open + slippage, symmetry."""

    def test_buy_stop_market_gap_trigger(self):
        """Buy stop triggers on gap (open >= stop_price) → fills at open + slip."""
        order = intent(order_type=OrderType.STOP_MARKET, stop_price=Decimal("101"))
        gap_bar = bar("gap", open=Decimal("102"), high=Decimal("103"),
                       low=Decimal("99"), close=Decimal("102"))
        source, result = evaluate(order, selected_bar=gap_bar)
        fill = result.fills[0]
        assert fill.execution_rule_code == "STOP_MARKET_GAP_OPEN"
        assert fill.reference_price == Decimal("102")
        # economic = 102 + 0.25 = 102.25
        assert fill.economic_price == Decimal("102.25")
        assert len(result.trigger_event_ids) == 1

    def test_buy_stop_market_intrabar_trigger(self):
        """Buy stop triggers intrabar (high >= stop) → fills at stop + slip."""
        order = intent(order_type=OrderType.STOP_MARKET, stop_price=Decimal("101"))
        intrabar = bar("intrabar", open=Decimal("100"), high=Decimal("103"),
                       low=Decimal("99"), close=Decimal("102"))
        source, result = evaluate(order, selected_bar=intrabar)
        fill = result.fills[0]
        assert fill.execution_rule_code == "STOP_MARKET_THRESHOLD"
        assert fill.reference_price == Decimal("101")
        assert fill.economic_price == Decimal("101.25")

    def test_buy_stop_market_no_trigger(self):
        """Buy stop does not trigger when high < stop_price."""
        order = intent(order_type=OrderType.STOP_MARKET, stop_price=Decimal("103"))
        no_touch = bar("no-trigger", high=Decimal("102.75"),
                       open=Decimal("100"), low=Decimal("98"), close=Decimal("101"))
        source = ledger_for(order)
        result = evaluate_bar(
            ledger=source, bar=no_touch, evaluated_at=no_touch.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert result.fills == ()

    def test_sell_stop_market_gap_trigger(self):
        """Sell stop triggers on gap (open <= stop_price) → fills at open - slip."""
        order = intent(side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                       stop_price=Decimal("99"))
        gap_bar = bar("gap-sell", open=Decimal("98"), high=Decimal("100"),
                       low=Decimal("97"), close=Decimal("98"))
        source, result = evaluate(order, selected_bar=gap_bar)
        fill = result.fills[0]
        assert fill.execution_rule_code == "STOP_MARKET_GAP_OPEN"
        assert fill.reference_price == Decimal("98")
        assert fill.economic_price == Decimal("97.75")

    def test_sell_stop_market_intrabar_trigger(self):
        """Sell stop triggers intrabar (low <= stop) → fills at stop - slip."""
        order = intent(side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                       stop_price=Decimal("99"))
        intrabar = bar("intrabar-sell", open=Decimal("100"), high=Decimal("102"),
                       low=Decimal("98"), close=Decimal("99"))
        source, result = evaluate(order, selected_bar=intrabar)
        fill = result.fills[0]
        assert fill.execution_rule_code == "STOP_MARKET_THRESHOLD"
        assert fill.reference_price == Decimal("99")
        assert fill.economic_price == Decimal("98.75")

    def test_sell_stop_market_no_trigger(self):
        """Sell stop does not trigger when low > stop_price."""
        order = intent(side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                       stop_price=Decimal("97"))
        no_touch = bar("no-trigger-sell", low=Decimal("97.25"),
                       open=Decimal("100"), high=Decimal("102"), close=Decimal("101"))
        source = ledger_for(order)
        result = evaluate_bar(
            ledger=source, bar=no_touch, evaluated_at=no_touch.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert result.fills == ()

    def test_buy_sell_stop_market_symmetry(self):
        """Buy and sell stop at same level produce symmetric slippage."""
        buy_order = intent(order_type=OrderType.STOP_MARKET, stop_price=Decimal("101"))
        sell_order = intent(side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                           stop_price=Decimal("101"))
        # Use a bar where buy triggers via intrabar (high >= 101)
        # and sell triggers via gap (open <= 101) or intrabar (low <= 101)
        sym_bar = bar("sym", open=Decimal("100"), high=Decimal("103"),
                       low=Decimal("99"), close=Decimal("101"))
        _, buy_result = evaluate(buy_order, selected_bar=sym_bar)
        # Buy: open=100 < 101, high=103 >= 101 → intrabar trigger at stop=101
        # economic = 101 + 0.25 = 101.25
        assert buy_result.fills[0].economic_price == Decimal("101.25")

        # Sell: open=100 <= 101 → gap trigger at open=100
        # economic = 100 - 0.25 = 99.75
        _, sell_result = evaluate(sell_order, selected_bar=sym_bar)
        assert sell_result.fills[0].economic_price == Decimal("99.75")

        # Verify symmetry: buy is stop+slip, sell is open-slip (different refs)
        # but slippage magnitude is the same (0.25)
        buy_friction = buy_result.fills[0].adverse_friction
        sell_friction = sell_result.fills[0].adverse_friction
        assert buy_friction == sell_friction == Decimal("0.25")

    def test_stop_market_triggers_and_fills_in_same_bar(self):
        """Stop-market triggers and fills in the same bar (distinct events)."""
        order = intent(order_type=OrderType.STOP_MARKET, stop_price=Decimal("101"))
        source, result = evaluate(order)
        # Trigger event and fill event are distinct
        assert len(result.trigger_event_ids) == 1
        assert len(result.fill_event_ids) == 1
        # Trigger event ID != fill event ID (different kind → different hash)
        assert result.trigger_event_ids[0] != result.fill_event_ids[0]


# ===========================================================================
# 4. Stop-limit orders
# ===========================================================================

class TestStopLimitOrders:
    """Stop-limit: trigger/fill separation, triggered-unfilled, later fill, cancel."""

    def test_trigger_bar_never_fills_stop_limit(self):
        """Stop-limit trigger bar never fills, even if limit is also touched."""
        order = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("101"),
                       limit_price=Decimal("101.25"))
        source = ledger_for(order)
        first = bar("trigger")
        triggered = evaluate_bar(
            ledger=source, bar=first, evaluated_at=first.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert triggered.fills == ()
        assert (triggered.output_ledger.order(order.order_id).state
                == OrderState.TRIGGERED)

    def test_no_same_event_trigger_and_fill(self):
        """Trigger and fill cannot happen in the same bar for stop-limit."""
        order = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("101"),
                       limit_price=Decimal("101.25"))
        # Bar where both stop and limit are touched
        both = bar("both", open=Decimal("100"), high=Decimal("103"),
                   low=Decimal("98"), close=Decimal("102"))
        source = ledger_for(order)
        result = evaluate_bar(
            ledger=source, bar=both, evaluated_at=both.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        # Trigger happens but NO fill (even though limit is touched)
        assert len(result.trigger_event_ids) == 1
        assert result.fills == ()

    def test_triggered_unfilled_state_persists(self):
        """After trigger without fill, order stays TRIGGERED for next bar."""
        order = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("101"),
                       limit_price=Decimal("101.25"))
        source = ledger_for(order)
        first = bar("trigger")
        triggered = evaluate_bar(
            ledger=source, bar=first, evaluated_at=first.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        # State is TRIGGERED, not FILLED
        assert (triggered.output_ledger.order(order.order_id).state
                == OrderState.TRIGGERED)

    def test_later_eligible_bar_fills_at_limit(self):
        """After trigger, a later eligible bar fills at the limit price."""
        order = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("101"),
                       limit_price=Decimal("101.25"))
        source = ledger_for(order)
        first = bar("trigger")
        triggered = evaluate_bar(
            ledger=source, bar=first, evaluated_at=first.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        second = next_bar("later")
        filled = evaluate_bar(
            ledger=triggered.output_ledger, bar=second,
            evaluated_at=second.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert len(filled.fills) == 1
        assert filled.fills[0].economic_price == Decimal("101.25")
        assert filled.fills[0].execution_rule_code == "STOP_LIMIT_LATER_BAR_LIMIT"

    def test_trigger_market_event_id_links_to_trigger_bar(self):
        """Fill's trigger_market_event_id links to the trigger bar."""
        order = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("101"),
                       limit_price=Decimal("101.25"))
        source = ledger_for(order)
        first = bar("trigger")
        triggered = evaluate_bar(
            ledger=source, bar=first, evaluated_at=first.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        second = next_bar("later")
        filled = evaluate_bar(
            ledger=triggered.output_ledger, bar=second,
            evaluated_at=second.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        # trigger_market_event_id should be the trigger event's source_event_id
        assert filled.fills[0].trigger_market_event_id is not None
        assert filled.fills[0].trigger_market_event_id == first.bar_id

    def test_triggered_unfilled_then_no_touch_remains_unfilled(self):
        """If limit is not touched on later bar, order stays TRIGGERED."""
        order = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("101"),
                       limit_price=Decimal("100.50"))
        source = ledger_for(order)
        first = bar("trigger")
        triggered = evaluate_bar(
            ledger=source, bar=first, evaluated_at=first.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        # Later bar where low > limit_price → no touch
        high_bar = next_bar("no-touch", open=Decimal("102"), high=Decimal("103"),
                            low=Decimal("101"), close=Decimal("102"))
        result = evaluate_bar(
            ledger=triggered.output_ledger, bar=high_bar,
            evaluated_at=high_bar.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert result.fills == ()
        assert (result.output_ledger.order(order.order_id).state
                == OrderState.TRIGGERED)

    def test_stop_limit_buy_symmetry(self):
        """Buy stop-limit: trigger when high >= stop, fill when low <= limit."""
        order = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("101"),
                       limit_price=Decimal("100.50"))
        source = ledger_for(order)
        # Trigger bar
        first = bar("trigger", high=Decimal("102"))
        triggered = evaluate_bar(
            ledger=source, bar=first, evaluated_at=first.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert (triggered.output_ledger.order(order.order_id).state
                == OrderState.TRIGGERED)
        # Later bar where low <= limit_price
        second = next_bar("fill", low=Decimal("100"))
        filled = evaluate_bar(
            ledger=triggered.output_ledger, bar=second,
            evaluated_at=second.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert filled.fills[0].economic_price == Decimal("100.50")

    def test_stop_limit_sell_symmetry(self):
        """Sell stop-limit: trigger when low <= stop, fill when high >= limit."""
        order = intent(side=OrderSide.SELL, order_type=OrderType.STOP_LIMIT,
                       stop_price=Decimal("99"), limit_price=Decimal("99.50"))
        source = ledger_for(order)
        first = bar("trigger-sell", low=Decimal("98"))
        triggered = evaluate_bar(
            ledger=source, bar=first, evaluated_at=first.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert (triggered.output_ledger.order(order.order_id).state
                == OrderState.TRIGGERED)
        second = next_bar("fill-sell", high=Decimal("100"),
                          open=Decimal("100"), low=Decimal("98"),
                          close=Decimal("100"))
        filled = evaluate_bar(
            ledger=triggered.output_ledger, bar=second,
            evaluated_at=second.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert filled.fills[0].economic_price == Decimal("99.50")


# ===========================================================================
# 5. Intrabar collisions
# ===========================================================================

class TestIntrabarCollisions:
    """Adverse threshold wins; unresolved ownership rejects; no fabricated path."""

    def test_adverse_collision_suppresses_favorable(self):
        """When adverse order and favorable order both trigger, adverse wins."""
        stop = intent("stop", side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                      stop_price=Decimal("99"))
        target = intent("target", side=OrderSide.SELL, order_type=OrderType.LIMIT,
                        limit_price=Decimal("101"))
        source = ledger_for(stop, target)
        observed = bar("collision")
        group = CollisionGroupV2(
            "collision-group-v2-1", H("group"),
            stop.order_id, target.order_id,
        )
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(stop), instruction(target)),
            collision_groups=(group,),
        )
        assert [fill.order_id for fill in result.fills] == [stop.order_id]
        assert result.suppressed_favorable_order_ids == (target.order_id,)

    def test_ambiguous_collision_without_ownership_rejects(self):
        """Collision without declared adverse ownership → AMBIGUOUS_INTRABAR_REJECTED."""
        stop = intent("stop", side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                      stop_price=Decimal("99"))
        target = intent("target", side=OrderSide.SELL, order_type=OrderType.LIMIT,
                        limit_price=Decimal("101"))
        source = ledger_for(stop, target)
        observed = bar("collision-ambiguous")
        ambiguous = CollisionGroupV2(
            "collision-group-v2-1", H("group"),
            stop.order_id, target.order_id,
            ownership_declared=False,
        )
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(stop), instruction(target)),
                collision_groups=(ambiguous,),
            )
        assert exc.value.reason == ExecutionReason.AMBIGUOUS_INTRABAR_REJECTED

    def test_collision_order_in_multiple_groups_rejects(self):
        """Order appearing in multiple collision groups → INVALID_COLLISION_GROUP."""
        stop1 = intent("stop1", side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                       stop_price=Decimal("99"))
        stop2 = intent("stop2", side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                       stop_price=Decimal("98"))
        target = intent("target", side=OrderSide.SELL, order_type=OrderType.LIMIT,
                        limit_price=Decimal("101"))
        source = ledger_for(stop1, stop2, target)
        observed = bar("collision-multi")
        g1 = CollisionGroupV2("collision-group-v2-1", H("g1"),
                              stop1.order_id, target.order_id)
        g2 = CollisionGroupV2("collision-group-v2-1", H("g2"),
                              stop2.order_id, target.order_id)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(stop1), instruction(stop2),
                              instruction(target)),
                collision_groups=(g1, g2),
            )
        assert exc.value.reason == ExecutionReason.INVALID_COLLISION_GROUP

    def test_collision_missing_instruction_rejects(self):
        """Collision group referencing non-instruction order → reject."""
        stop = intent("stop", side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                      stop_price=Decimal("99"))
        target = intent("target", side=OrderSide.SELL, order_type=OrderType.LIMIT,
                        limit_price=Decimal("101"))
        source = ledger_for(stop, target)
        observed = bar("collision-missing")
        group = CollisionGroupV2(
            "collision-group-v2-1", H("group"),
            stop.order_id, target.order_id,
        )
        # Only pass instruction for stop, not target
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(stop),),
                collision_groups=(group,),
            )
        assert exc.value.reason == ExecutionReason.INVALID_COLLISION_GROUP

    def test_no_fabricated_ohlc_path_in_collision(self):
        """Collision resolution does not invent a bar path — fill uses bar data."""
        stop = intent("stop", side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                      stop_price=Decimal("99"))
        target = intent("target", side=OrderSide.SELL, order_type=OrderType.LIMIT,
                        limit_price=Decimal("101"))
        source = ledger_for(stop, target)
        observed = bar("collision-path")
        group = CollisionGroupV2(
            "collision-group-v2-1", H("group"),
            stop.order_id, target.order_id,
        )
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(stop), instruction(target)),
            collision_groups=(group,),
        )
        # The fill uses the actual bar data (open, volume), not invented path
        fill = result.fills[0]
        assert fill.bar_volume == observed.volume
        assert fill.fill_time == observed.available_at


# ===========================================================================
# 6. Tick rounding and costs
# ===========================================================================

class TestTickRounding:
    """Buys round adversely upward, sells downward, boundaries unchanged, once."""

    def test_buy_rounds_adversely_upward(self):
        """Buy slippage rounds up to next tick."""
        order = intent()
        source, result = evaluate(order,
            selected_instruction=instruction(order, slippage="0.5"))
        fill = result.fills[0]
        # slip = 0.5 * 0.25 = 0.125; unrounded = 100 + 0.125 = 100.125
        assert fill.unrounded_economic_price == Decimal("100.125")
        # BUY rounds CEILING → 100.25
        assert fill.economic_price == Decimal("100.25")

    def test_sell_rounds_adversely_downward(self):
        """Sell slippage rounds down to next tick."""
        order = intent(side=OrderSide.SELL)
        source, result = evaluate(order,
            selected_instruction=instruction(order, slippage="0.5"))
        fill = result.fills[0]
        # slip = 0.125; unrounded = 100 - 0.125 = 99.875
        assert fill.unrounded_economic_price == Decimal("99.875")
        # SELL rounds FLOOR → 99.75
        assert fill.economic_price == Decimal("99.75")

    def test_exact_tick_boundary_remains_unchanged(self):
        """When slippage lands exactly on a tick, rounding doesn't change it."""
        order = intent()
        source, result = evaluate(order,
            selected_instruction=instruction(order, slippage="1"))
        fill = result.fills[0]
        # slip = 1 * 0.25 = 0.25; unrounded = 100 + 0.25 = 100.25
        assert fill.unrounded_economic_price == Decimal("100.25")
        assert fill.economic_price == Decimal("100.25")
        assert fill.adverse_friction == Decimal("0.25")

    def test_sell_exact_tick_boundary_remains_unchanged(self):
        """Sell slippage on exact tick → no extra rounding."""
        order = intent(side=OrderSide.SELL)
        source, result = evaluate(order,
            selected_instruction=instruction(order, slippage="1"))
        fill = result.fills[0]
        assert fill.unrounded_economic_price == Decimal("99.75")
        assert fill.economic_price == Decimal("99.75")

    def test_slippage_applied_exactly_once(self):
        """Slippage is applied exactly once — not compounded."""
        order = intent()
        source, result = evaluate(order,
            selected_instruction=instruction(order, slippage="2"))
        fill = result.fills[0]
        # slip = 2 * 0.25 = 0.50; economic = 100 + 0.50 = 100.50
        assert fill.economic_price == Decimal("100.50")
        # friction = economic - reference = 0.50
        assert fill.adverse_friction == Decimal("0.50")

    def test_decimal_only_arithmetic(self):
        """All economic values are Decimal, never float."""
        order = intent()
        source, result = evaluate(order)
        fill = result.fills[0]
        for value in (fill.quantity, fill.reference_price,
                      fill.unrounded_economic_price, fill.economic_price,
                      fill.adverse_friction, fill.bar_volume,
                      fill.bar_available_quantity, fill.order_participation_cap):
            assert isinstance(value, Decimal)
            assert value.is_finite()

    def test_zero_slippage_still_rounds_correctly(self):
        """Zero slippage → economic == reference for market orders."""
        order = intent()
        source, result = evaluate(order,
            selected_instruction=instruction(order, slippage="0"))
        fill = result.fills[0]
        assert fill.unrounded_economic_price == Decimal("100")
        assert fill.economic_price == Decimal("100")
        assert fill.adverse_friction == Decimal("0")

    def test_friction_sign_buy_positive(self):
        """Buy friction = economic - reference >= 0 (adverse)."""
        order = intent()
        source, result = evaluate(order)
        fill = result.fills[0]
        assert fill.adverse_friction >= 0

    def test_friction_sign_sell_positive(self):
        """Sell friction = reference - economic >= 0 (adverse)."""
        order = intent(side=OrderSide.SELL)
        source, result = evaluate(order)
        fill = result.fills[0]
        assert fill.adverse_friction >= 0


# ===========================================================================
# 7. Participation
# ===========================================================================

class TestParticipation:
    """Shared volume budget, zero volume, priority, tie-break, partial, budget cap."""

    def test_shared_volume_budget_basic(self):
        """Bar budget = volume * max_participation_rate, floored to quantity_step."""
        order = intent()
        source, result = evaluate(order)
        # budget = floor(100 * 0.10) = 10
        assert result.initial_bar_budget == Decimal("10")
        assert result.consumed_bar_budget == Decimal("3")  # fill qty = 3
        assert result.remaining_bar_budget == Decimal("7")

    def test_zero_volume_no_fill(self):
        """Zero volume → budget = 0 → no fill."""
        order = intent()
        source = ledger_for(order)
        zero = bar("zero", volume=Decimal("0"))
        result = evaluate_bar(
            ledger=source, bar=zero, evaluated_at=zero.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert result.fills == ()
        assert result.initial_bar_budget == Decimal("0")

    def test_missing_volume_rejects(self):
        """None volume → MISSING_VOLUME rejection."""
        order = intent()
        source = ledger_for(order)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=bar("missing", volume=None),
                evaluated_at=bar("missing", volume=None).available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.MISSING_VOLUME

    def test_priority_ordering_forced_exit_before_entry(self):
        """Forced exit (RISK_SESSION_END_LIQUIDATION) fills before entry."""
        entry = intent("entry", quantity=Decimal("8"))
        forced = intent("forced", quantity=Decimal("8"), side=OrderSide.SELL)
        source = ledger_for(entry, forced)
        observed = bar(volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(
                instruction(entry),
                instruction(forced, priority=ExecutionPriority.RISK_SESSION_END_LIQUIDATION),
            ),
        )
        # Forced exit (priority 10) fills first, then entry gets remaining
        fills = [(fill.order_id, fill.quantity) for fill in result.fills]
        assert fills == [(forced.order_id, Decimal("8")),
                         (entry.order_id, Decimal("2"))]
        assert result.remaining_bar_budget == 0

    def test_priority_ordering_rollover_before_reduction(self):
        """Rollover close (priority 20) before ordinary position reducing (30)."""
        rollover = intent("rollover", quantity=Decimal("5"), side=OrderSide.SELL)
        reducing = intent("reducing", quantity=Decimal("5"), side=OrderSide.SELL)
        source = ledger_for(rollover, reducing)
        observed = bar("priority-test", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(
                instruction(rollover, priority=ExecutionPriority.ROLLOVER_OUTGOING_CLOSE),
                instruction(reducing, priority=ExecutionPriority.ORDINARY_POSITION_REDUCING),
            ),
        )
        # Rollover fills first, then reducing gets remaining budget
        assert result.fills[0].order_id == rollover.order_id
        assert result.fills[1].order_id == reducing.order_id

    def test_priority_ordering_strategy_exit_before_entry(self):
        """Strategy exit (40) before entry (50)."""
        exit_order = intent("exit", quantity=Decimal("5"), side=OrderSide.SELL)
        entry = intent("entry2", quantity=Decimal("5"))
        source = ledger_for(exit_order, entry)
        observed = bar("exit-test", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(
                instruction(exit_order, priority=ExecutionPriority.STRATEGY_EXIT),
                instruction(entry, priority=ExecutionPriority.ENTRY_OR_ROLLOVER_INCOMING),
            ),
        )
        assert result.fills[0].order_id == exit_order.order_id

    def test_stable_tie_break_by_activation_then_submission_then_id(self):
        """Same priority → activation_at, then submitted_at, then order_id."""
        # Two entries with same priority but different activation times
        early = intent("early-act", quantity=Decimal("5"),
                       activation_at=START + timedelta(minutes=1))
        late = intent("late-act", quantity=Decimal("5"),
                      activation_at=START + timedelta(minutes=2))
        source = ledger_for(early, late)
        observed = bar("tie-break", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(
                instruction(early),
                instruction(late),
            ),
        )
        # Early activation fills first
        assert result.fills[0].order_id == early.order_id

    def test_combined_fills_never_exceed_budget(self):
        """Sum of fill quantities <= initial_bar_budget."""
        order1 = intent("o1", quantity=Decimal("10"))
        order2 = intent("o2", quantity=Decimal("10"))
        source = ledger_for(order1, order2)
        observed = bar("budget-cap", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(
                instruction(order1),
                instruction(order2),
            ),
        )
        total = sum(fill.quantity for fill in result.fills)
        assert total <= result.initial_bar_budget
        assert result.consumed_bar_budget == total
        assert result.consumed_bar_budget + result.remaining_bar_budget == result.initial_bar_budget

    def test_partial_fills_conserve_quantity(self):
        """Partial fill conserves remaining quantity in ledger."""
        order = intent("partial", quantity=Decimal("20"))
        source = ledger_for(order)
        observed = bar("partial", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        # Budget = 10, order qty = 20 → fill 10, remaining 10
        fill = result.fills[0]
        assert fill.quantity == Decimal("10")
        snap = result.output_ledger.order(order.order_id)
        assert snap.state == OrderState.PARTIALLY_FILLED
        assert snap.filled_quantity == Decimal("10")
        assert snap.remaining_quantity == Decimal("10")
        assert snap.accepted_quantity == snap.filled_quantity + snap.remaining_quantity

    def test_participation_rate_exceeding_global_rejects(self):
        """Instruction participation > policy max → INVALID_POLICY."""
        order = intent()
        source = ledger_for(order)
        observed = bar()
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order, participation="0.50"),),
            )
        assert exc.value.reason == ExecutionReason.INVALID_POLICY

    def test_order_participation_cap_is_per_order(self):
        """Order cap = volume * participation_rate, floored to quantity_step."""
        order = intent("cap-test", quantity=Decimal("20"))
        source = ledger_for(order)
        observed = bar("cap-bar", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order, participation="0.05"),),
        )
        # order_cap = floor(100 * 0.05) = 5
        fill = result.fills[0]
        assert fill.order_participation_cap == Decimal("5")
        assert fill.quantity == Decimal("5")

    def test_budget_reconciliation_in_evaluation(self):
        """initial == consumed + remaining in evaluation record."""
        order = intent()
        source, result = evaluate(order)
        assert (result.initial_bar_budget
                == result.consumed_bar_budget + result.remaining_bar_budget)


# ===========================================================================
# 8. IOC and order lifecycle
# ===========================================================================

class TestIOCAndLifecycle:
    """IOC first eligible evaluation, residual cancellation, no later fill."""

    def test_ioc_no_touch_evaluates_once_and_cancels(self):
        """IOC limit no-touch → evaluation event, then CANCELLED."""
        order = intent(time_in_force=TimeInForce.IOC, order_type=OrderType.LIMIT,
                       limit_price=Decimal("90"))
        source, result = evaluate(order)
        assert result.fills == ()
        assert len(result.evaluation_event_ids) == 1
        assert (result.output_ledger.order(order.order_id).state
                == OrderState.CANCELLED)

    def test_ioc_market_no_touch_still_cancels_residual(self):
        """IOC market order that doesn't get a fill → cancelled after evaluation."""
        order = intent(time_in_force=TimeInForce.IOC, quantity=Decimal("20"))
        source = ledger_for(order)
        zero = bar("ioc-zero", volume=Decimal("0"))
        result = evaluate_bar(
            ledger=source, bar=zero, evaluated_at=zero.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert result.fills == ()
        assert len(result.evaluation_event_ids) == 1
        assert (result.output_ledger.order(order.order_id).state
                == OrderState.CANCELLED)

    def test_ioc_partial_fill_then_cancel_residual(self):
        """IOC partial fill → FILLED partial then CANCELLED for residual."""
        order = intent("ioc-partial", time_in_force=TimeInForce.IOC,
                       quantity=Decimal("20"))
        source = ledger_for(order)
        observed = bar("ioc-partial-bar", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        # Budget = 10, order = 20 → partial fill 10, then cancel residual 10
        fill = result.fills[0]
        assert fill.quantity == Decimal("10")
        snap = result.output_ledger.order(order.order_id)
        assert snap.state == OrderState.CANCELLED
        assert snap.filled_quantity == Decimal("10")
        assert snap.remaining_quantity == Decimal("10")

    def test_ioc_no_later_fill_after_cancellation(self):
        """After IOC cancellation, a later bar cannot fill the order."""
        order = intent(time_in_force=TimeInForce.IOC, order_type=OrderType.LIMIT,
                       limit_price=Decimal("90"))
        source, result = evaluate(order)
        assert (result.output_ledger.order(order.order_id).state
                == OrderState.CANCELLED)
        # Try evaluating another bar — order is CANCELLED (terminal)
        second = next_bar("second")
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=result.output_ledger, bar=second,
                evaluated_at=second.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.ORDER_NOT_EXECUTABLE

    def test_ioc_full_fill_sets_ioc_evaluated(self):
        """IOC full fill sets ioc_evaluated=True (no residual cancel)."""
        order = intent("ioc-full", time_in_force=TimeInForce.IOC,
                       quantity=Decimal("3"))
        source = ledger_for(order)
        observed = bar("ioc-full-bar", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        snap = result.output_ledger.order(order.order_id)
        # IOC with full fill: filled_quantity == accepted, remaining == 0
        assert snap.state == OrderState.FILLED
        assert snap.ioc_evaluated is True

    def test_ioc_already_evaluated_rejects_second_evaluation(self):
        """IOC already evaluated → second EXECUTION_EVALUATED rejects."""
        order = intent(time_in_force=TimeInForce.IOC, order_type=OrderType.LIMIT,
                       limit_price=Decimal("90"))
        source, result = evaluate(order)
        # Order is now CANCELLED — any further evaluation should reject
        second = next_bar("second-eval")
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=result.output_ledger, bar=second,
                evaluated_at=second.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.ORDER_NOT_EXECUTABLE

    def test_fill_lineage_immutable(self):
        """Fill record is frozen — cannot mutate."""
        order = intent()
        source, result = evaluate(order)
        with pytest.raises(FrozenInstanceError):
            result.fills[0].quantity = Decimal("2")

    def test_ledger_lineage_immutable(self):
        """Ledger events are frozen — cannot mutate."""
        order = intent()
        source, result = evaluate(order)
        with pytest.raises(FrozenInstanceError):
            # Access the last event in the output ledger
            result.output_ledger.events[-1].reason_code = "HACKED"

    def test_evaluation_record_immutable(self):
        """Evaluation record is frozen — cannot mutate."""
        order = intent()
        source, result = evaluate(order)
        with pytest.raises(FrozenInstanceError):
            result.fills = ()

    def test_ioc_evaluation_event_has_no_fill_quantity(self):
        """IOC EXECUTION_EVALUATED event has fill_quantity=None."""
        order = intent(time_in_force=TimeInForce.IOC, order_type=OrderType.LIMIT,
                       limit_price=Decimal("90"))
        source, result = evaluate(order)
        # Find the EXECUTION_EVALUATED event in the output ledger
        eval_events = [e for e in result.output_ledger.events
                       if e.kind == LedgerEventKind.EXECUTION_EVALUATED]
        assert len(eval_events) == 1
        assert eval_events[0].fill_quantity is None


# ===========================================================================
# 9. Determinism and replay
# ===========================================================================

class TestDeterminismAndReplay:
    """Repeated execution byte-identical, version mismatch rejects, tamper detected."""

    def test_repeated_execution_byte_identical(self):
        """Calling evaluate_bar twice with same inputs produces identical output."""
        order = intent()
        source = ledger_for(order)
        observed = bar()
        kwargs = dict(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        first = evaluate_bar(**kwargs)
        second = evaluate_bar(**kwargs)
        assert first == second
        assert first.evaluation_id == second.evaluation_id
        assert first.output_ledger.serialize() == second.output_ledger.serialize()

    def test_repeated_execution_different_ledger_objects_same_result(self):
        """Two separate ledger_for calls produce same evaluate_bar output."""
        order = intent()
        source1 = ledger_for(order)
        source2 = ledger_for(order)
        observed = bar()
        r1 = evaluate_bar(ledger=source1, bar=observed, evaluated_at=observed.available_at,
                         instrument=instrument(), policy=policy(),
                         instructions=(instruction(order),))
        r2 = evaluate_bar(ledger=source2, bar=observed, evaluated_at=observed.available_at,
                         instrument=instrument(), policy=policy(),
                         instructions=(instruction(order),))
        assert r1.evaluation_id == r2.evaluation_id
        assert r1.output_ledger.serialize() == r2.output_ledger.serialize()

    def test_output_ledger_serialization_is_deterministic(self):
        """Ledger serialization is byte-identical across calls."""
        order = intent()
        source, result = evaluate(order)
        s1 = result.output_ledger.serialize()
        s2 = result.output_ledger.serialize()
        assert s1 == s2

    def test_schema_version_mismatch_bar_rejects(self):
        """Bar with wrong schema_version rejects at construction."""
        with pytest.raises(ValueError, match="unsupported OHLC bar schema_version"):
            OHLCBarV2(
                "wrong-schema",
                H("bar"), "ES", "ES", "ESM5",
                START + timedelta(minutes=10),
                START + timedelta(minutes=11),
                START + timedelta(minutes=11),
                Decimal("100"), Decimal("102"), Decimal("98"), Decimal("101"),
                Decimal("100"), True, True, True, True, "dataset-v1",
            )

    def test_schema_version_mismatch_fill_rejects(self):
        """ExecutionFillV2 with wrong schema rejects at construction."""
        with pytest.raises(ValueError, match="unsupported execution fill schema_version"):
            ExecutionFillV2(
                "wrong-schema",
                H("fill"), H("order"), H("bar"), None,
                "ES", "ES", "ESM5",
                START + timedelta(minutes=11),
                OrderSide.BUY, Decimal("3"),
                Decimal("100"), Decimal("100.25"), Decimal("100.25"),
                Decimal("0.25"), Decimal("100"), Decimal("10"),
                Decimal("10"), "MARKET_NEXT_ELIGIBLE_OPEN",
                EXECUTION_POLICY_VERSION, LIQUIDITY_POLICY_VERSION, "assumption-v1",
            )

    def test_policy_version_mismatch_rejects(self):
        """Policy with wrong execution_policy_version rejects."""
        with pytest.raises(ValueError, match="unsupported execution policy"):
            ExecutionPolicyV2(
                "ohlc-execution-policy-v2-1",
                H("bad"), "WRONG", LIQUIDITY_POLICY_VERSION,
                Decimal("0.10"), "assumption-v1",
            )

    def test_instruction_version_mismatch_rejects(self):
        """Instruction with wrong schema rejects."""
        with pytest.raises(ValueError, match="unsupported execution instruction"):
            ExecutionInstructionV2(
                "wrong-schema",
                H("instr"), H("order"),
                ExecutionPriority.ENTRY_OR_ROLLOVER_INCOMING,
                Decimal("0.10"), Decimal("1"), "assumption-v1",
            )

    def test_collision_group_version_mismatch_rejects(self):
        """Collision group with wrong schema rejects."""
        with pytest.raises(ValueError, match="unsupported collision group"):
            CollisionGroupV2(
                "wrong-schema",
                H("group"), H("adverse"), H("favorable"),
            )

    def test_evaluation_version_mismatch_rejects(self):
        """ExecutionEvaluationV2 with wrong schema rejects."""
        source = ledger_for(intent())
        with pytest.raises(ValueError, match="unsupported evaluation schema_version"):
            ExecutionEvaluationV2(
                "wrong-schema",
                H("eval"), START,
                H("input"), H("output"), H("bar"), H("policy"),
                (), (), (), (), (), Decimal("0"), Decimal("0"), Decimal("0"),
                source,
            )

    def test_checkpoint_replay_equivalence(self):
        """Checkpoint and replay produce identical ledger."""
        order = intent()
        source = ledger_for(order)
        observed = bar()
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        # Checkpoint the output ledger
        checkpoint = result.output_ledger.checkpoint()
        assert checkpoint.ledger_fingerprint == result.output_ledger_fingerprint
        # Verify checkpoint
        checkpoint.verify()
        # Replay from the same events should produce the same fingerprint
        replayed = OrderLedgerV2.replay(
            (source.orders[0].intent,),
            result.output_ledger.events,
        )
        assert replayed.ledger_fingerprint == result.output_ledger.ledger_fingerprint

    def test_tampering_detected_by_verify_integrity(self):
        """Tampering with ledger events is detected by verify_integrity."""
        order = intent()
        source, result = evaluate(order)
        # Create a tampered ledger by replacing an event with different content
        events = list(result.output_ledger.events)
        if len(events) >= 2:
            # Swap two events' content — different fingerprint
            from dataclasses import replace as dc_replace
            tampered_event = dc_replace(events[0], reason_code="TAMPERED")
            tampered = dc_replace(result.output_ledger,
                                   events=(tampered_event,) + tuple(events[1:]),
                                   ledger_fingerprint="")
            # verify_integrity should detect tampering
            with pytest.raises(OrderLedgerError):
                tampered.verify_integrity()

    def test_bar_tampering_detected_at_construction(self):
        """Bar with invalid OHLC geometry rejects at construction."""
        with pytest.raises(ValueError, match="OHLC geometry"):
            bar("bad-geom", high=Decimal("97"), low=Decimal("99"),
                open=Decimal("98"), close=Decimal("98"))

    def test_bar_chronology_invalid_rejects(self):
        """Bar with open_time >= close_time rejects."""
        with pytest.raises(ValueError, match="bar chronology"):
            bar("bad-time",
                open_time=START + timedelta(minutes=11),
                close_time=START + timedelta(minutes=11),
                available_at=START + timedelta(minutes=11))

    def test_bar_unaligned_interval_rejects(self):
        """Bar with non-1-minute interval rejects."""
        with pytest.raises(ValueError, match="aligned one-minute"):
            bar("unaligned",
                close_time=START + timedelta(minutes=10, seconds=30),
                available_at=START + timedelta(minutes=10, seconds=30))

    def test_off_tick_bar_rejects(self):
        """Bar with off-tick prices rejects."""
        order = intent()
        source = ledger_for(order)
        off_tick = bar("off-tick", open=Decimal("100.10"),
                       high=Decimal("102.10"), low=Decimal("98.10"),
                       close=Decimal("101.10"))
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=off_tick, evaluated_at=off_tick.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        assert exc.value.reason == ExecutionReason.INVALID_BAR

    def test_duplicate_instruction_order_rejects(self):
        """Duplicate instruction order_ids → DUPLICATE_IDENTITY_CONFLICT."""
        order = intent()
        source = ledger_for(order)
        observed = bar()
        dup_instruction = instruction(order)
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(dup_instruction, dup_instruction),
            )
        assert exc.value.reason == ExecutionReason.DUPLICATE_IDENTITY_CONFLICT

    def test_input_ledger_not_mutated(self):
        """evaluate_bar does not mutate its input ledger."""
        order = intent()
        source = ledger_for(order)
        original_fingerprint = source.ledger_fingerprint
        observed = bar()
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert source.ledger_fingerprint == original_fingerprint
        assert result.output_ledger != source
        assert result.input_ledger_fingerprint == original_fingerprint

    def test_assumption_version_mismatch_rejects(self):
        """Order/instruction with different assumption_version → VERSION_MISMATCH."""
        order = intent()
        source = ledger_for(order)
        observed = bar()
        bad_instruction = ExecutionInstructionV2(
            "execution-instruction-v2-1",
            H("bad-instr"), order.order_id,
            ExecutionPriority.ENTRY_OR_ROLLOVER_INCOMING,
            Decimal("0.10"), Decimal("1"), "wrong-assumption",
        )
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(bad_instruction,),
            )
        assert exc.value.reason == ExecutionReason.VERSION_MISMATCH

    def test_evaluation_id_is_deterministic(self):
        """Same inputs → same evaluation_id (SHA-256 fingerprint)."""
        order = intent()
        source1 = ledger_for(order)
        source2 = ledger_for(order)
        observed = bar()
        r1 = evaluate_bar(ledger=source1, bar=observed, evaluated_at=observed.available_at,
                         instrument=instrument(), policy=policy(),
                         instructions=(instruction(order),))
        r2 = evaluate_bar(ledger=source2, bar=observed, evaluated_at=observed.available_at,
                         instrument=instrument(), policy=policy(),
                         instructions=(instruction(order),))
        assert r1.evaluation_id == r2.evaluation_id

    def test_execution_fill_immutable(self):
        """Fill records are frozen dataclasses."""
        order = intent()
        source, result = evaluate(order)
        with pytest.raises(FrozenInstanceError):
            result.fills[0].economic_price = Decimal("999")

    def test_bar_immutable(self):
        """Bar records are frozen dataclasses."""
        observed = bar()
        with pytest.raises(FrozenInstanceError):
            observed.open = Decimal("999")

    def test_policy_immutable(self):
        """Policy is frozen."""
        p = policy()
        with pytest.raises(FrozenInstanceError):
            p.maximum_participation_rate = Decimal("1.0")

    def test_instruction_immutable(self):
        """Instruction is frozen."""
        order = intent()
        instr = instruction(order)
        with pytest.raises(FrozenInstanceError):
            instr.slippage_ticks = Decimal("999")

    def test_collision_group_immutable(self):
        """CollisionGroupV2 is frozen."""
        group = CollisionGroupV2(
            "collision-group-v2-1", H("g"), H("a"), H("b"),
        )
        with pytest.raises(FrozenInstanceError):
            group.ownership_declared = False

    def test_collision_group_same_order_rejects(self):
        """Collision group with same order for both sides rejects."""
        with pytest.raises(ValueError, match="collision orders must be distinct"):
            CollisionGroupV2(
                "collision-group-v2-1", H("g"),
                H("same"), H("same"),
            )

    def test_collision_role_enum_values(self):
        """CollisionRole has ADVERSE and FAVORABLE values."""
        assert CollisionRole.ADVERSE.value == "ADVERSE"
        assert CollisionRole.FAVORABLE.value == "FAVORABLE"

    def test_execution_priority_ordering(self):
        """ExecutionPriority values are in ascending severity order."""
        assert (int(ExecutionPriority.RISK_SESSION_END_LIQUIDATION)
                < int(ExecutionPriority.ROLLOVER_OUTGOING_CLOSE)
                < int(ExecutionPriority.ORDINARY_POSITION_REDUCING)
                < int(ExecutionPriority.STRATEGY_EXIT)
                < int(ExecutionPriority.ENTRY_OR_ROLLOVER_INCOMING))

    def test_execution_reason_all_codes_present(self):
        """All ExecutionReason codes are present and stable."""
        expected = {
            "INVALID_POLICY", "INVALID_BAR", "BAR_NOT_FINAL", "BAR_NOT_AVAILABLE",
            "BAR_INELIGIBLE", "IDENTITY_MISMATCH", "VERSION_MISMATCH",
            "ORDER_NOT_EXECUTABLE", "SAME_SOURCE_BAR_INELIGIBLE", "MISSING_VOLUME",
            "AMBIGUOUS_INTRABAR_REJECTED", "INVALID_COLLISION_GROUP",
            "DUPLICATE_IDENTITY_CONFLICT",
        }
        actual = {r.value for r in ExecutionReason}
        assert expected.issubset(actual)

    def test_max_participation_rate_over_one_rejects(self):
        """Maximum participation rate > 1 rejects at construction."""
        with pytest.raises(ValueError, match="cannot exceed one"):
            ExecutionPolicyV2(
                "ohlc-execution-policy-v2-1", H("p"),
                EXECUTION_POLICY_VERSION, LIQUIDITY_POLICY_VERSION,
                Decimal("1.5"), "assumption-v1",
            )

    def test_zero_participation_rate_rejects(self):
        """Zero participation rate rejects at construction."""
        with pytest.raises(ValueError, match="must be positive"):
            ExecutionPolicyV2(
                "ohlc-execution-policy-v2-1", H("p"),
                EXECUTION_POLICY_VERSION, LIQUIDITY_POLICY_VERSION,
                Decimal("0"), "assumption-v1",
            )

    def test_negative_slippage_rejects(self):
        """Negative slippage rejects at construction."""
        order = intent()
        with pytest.raises(ValueError, match="must be nonnegative"):
            ExecutionInstructionV2(
                "execution-instruction-v2-1",
                H("neg"), order.order_id,
                ExecutionPriority.ENTRY_OR_ROLLOVER_INCOMING,
                Decimal("0.10"), Decimal("-1"), "assumption-v1",
            )

    def test_bar_available_at_before_close_rejects(self):
        """available_at < close_time rejects (look-ahead)."""
        with pytest.raises(ValueError, match="bar chronology"):
            bar("lookahead",
                available_at=START + timedelta(minutes=10, seconds=59))

    def test_output_ledger_fingerprint_matches(self):
        """Output ledger fingerprint in evaluation matches ledger's own."""
        order = intent()
        source, result = evaluate(order)
        assert result.output_ledger_fingerprint == result.output_ledger.ledger_fingerprint

    def test_ioc_ioc_evaluated_flag_set_after_evaluation(self):
        """IOC order's ioc_evaluated flag is set True after evaluation."""
        order = intent(time_in_force=TimeInForce.IOC, order_type=OrderType.LIMIT,
                       limit_price=Decimal("90"))
        source, result = evaluate(order)
        snap = result.output_ledger.order(order.order_id)
        assert snap.ioc_evaluated is True

    def test_non_ioc_does_not_evaluate(self):
        """Non-IOC order without fill does not get EXECUTION_EVALUATED event."""
        order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("90"))
        source = ledger_for(order)
        observed = bar("no-touch-non-ioc", low=Decimal("91"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        assert result.fills == ()
        assert len(result.evaluation_event_ids) == 0
        assert (result.output_ledger.order(order.order_id).state
                == OrderState.ACTIVE)

    def test_fill_event_ids_unique(self):
        """All fill event IDs in evaluation are unique."""
        order1 = intent("f1")
        order2 = intent("f2")
        source = ledger_for(order1, order2)
        observed = bar("multi-fill", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order1), instruction(order2)),
        )
        all_ids = result.trigger_event_ids + result.fill_event_ids + result.evaluation_event_ids
        assert len(all_ids) == len(set(all_ids))

    def test_trigger_event_ids_unique_when_multiple_stops(self):
        """Multiple stop triggers in same bar have unique event IDs."""
        stop1 = intent("s1", order_type=OrderType.STOP_MARKET,
                       stop_price=Decimal("101"))
        stop2 = intent("s2", order_type=OrderType.STOP_MARKET,
                       stop_price=Decimal("100"))
        source = ledger_for(stop1, stop2)
        observed = bar("multi-stop", open=Decimal("99"), high=Decimal("103"),
                       low=Decimal("98"), close=Decimal("102"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(stop1), instruction(stop2)),
        )
        assert len(result.trigger_event_ids) == len(set(result.trigger_event_ids))

    def test_stop_limit_not_in_fill_candidates_on_trigger_bar(self):
        """Stop-limit is explicitly excluded from fill candidates on trigger bar."""
        # The code at line 421-423 excludes items where order_type == STOP_LIMIT and trigger == True
        order = intent(order_type=OrderType.STOP_LIMIT,
                       stop_price=Decimal("101"), limit_price=Decimal("100"))
        source = ledger_for(order)
        # Bar where both stop and limit would be touched
        both = bar("both-sl", open=Decimal("100"), high=Decimal("102"),
                   low=Decimal("99"), close=Decimal("101"))
        result = evaluate_bar(
            ledger=source, bar=both, evaluated_at=both.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order),),
        )
        # Trigger fires but no fill
        assert len(result.trigger_event_ids) == 1
        assert result.fills == ()

    def test_consumed_budget_equals_sum_of_fill_quantities(self):
        """Consumed bar budget equals sum of all fill quantities."""
        order1 = intent("cb1", quantity=Decimal("5"))
        order2 = intent("cb2", quantity=Decimal("5"), side=OrderSide.SELL)
        source = ledger_for(order1, order2)
        observed = bar("cb", volume=Decimal("100"))
        result = evaluate_bar(
            ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(order1), instruction(order2)),
        )
        total = sum(fill.quantity for fill in result.fills)
        assert result.consumed_bar_budget == total

    def test_bar_id_is_sha256(self):
        """Bar ID must be lowercase SHA-256."""
        with pytest.raises(ValueError, match="must be lowercase SHA-256"):
            OHLCBarV2(
                "ohlc-bar-v2-1", "NOT_A_HASH", "ES", "ES", "ESM5",
                START + timedelta(minutes=10), START + timedelta(minutes=11),
                START + timedelta(minutes=11),
                Decimal("100"), Decimal("102"), Decimal("98"), Decimal("101"),
                Decimal("100"), True, True, True, True, "dataset-v1",
            )

    def test_bar_negative_volume_rejects(self):
        """Bar with negative volume rejects at construction."""
        with pytest.raises(ValueError, match="must be nonnegative"):
            bar("neg-vol", volume=Decimal("-1"))

    def test_bar_negative_price_rejects(self):
        """Bar with negative price rejects at construction."""
        with pytest.raises(ValueError, match="must be positive"):
            bar("neg-price", open=Decimal("-1"))

    def test_instrument_effective_interval_mismatch_rejects(self):
        """Bar outside instrument effective interval → IDENTITY_MISMATCH."""
        order = intent()
        source = ledger_for(order)
        # Instrument effective_from is START - 1day, effective_to is None
        # Try a bar before instrument effective_from
        old_bar = bar("old",
            open_time=START - timedelta(days=2),
            close_time=START - timedelta(days=2, minutes=-1),
            available_at=START - timedelta(days=2, minutes=-1))
        with pytest.raises(OHLCExecutionError) as exc:
            evaluate_bar(
                ledger=source, bar=old_bar, evaluated_at=old_bar.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(order),),
            )
        # The bar's open_time < instrument.effective_from
        assert exc.value.reason == ExecutionReason.IDENTITY_MISMATCH

    def test_fill_id_is_deterministic(self):
        """Fill ID is a deterministic fingerprint of fill content."""
        order = intent()
        source1 = ledger_for(order)
        source2 = ledger_for(order)
        observed = bar()
        r1 = evaluate_bar(ledger=source1, bar=observed, evaluated_at=observed.available_at,
                         instrument=instrument(), policy=policy(),
                         instructions=(instruction(order),))
        r2 = evaluate_bar(ledger=source2, bar=observed, evaluated_at=observed.available_at,
                         instrument=instrument(), policy=policy(),
                         instructions=(instruction(order),))
        assert r1.fills[0].fill_id == r2.fills[0].fill_id

    def test_order_not_in_ledger_rejects(self):
        """Instruction referencing order not in ledger → ORDER_NOT_FOUND from ledger."""
        order = intent()
        other = intent("other")
        source = ledger_for(order)  # only 'order', not 'other'
        observed = bar()
        # instruction references 'other' which is not in the ledger
        with pytest.raises((OHLCExecutionError, OrderLedgerError)):
            evaluate_bar(
                ledger=source, bar=observed, evaluated_at=observed.available_at,
                instrument=instrument(), policy=policy(),
                instructions=(instruction(other),),
            )

    def test_ledger_verify_integrity_after_evaluation(self):
        """Output ledger passes verify_integrity after evaluation."""
        order = intent()
        source, result = evaluate(order)
        result.output_ledger.verify_integrity()

    def test_ledger_checkpoint_roundtrip(self):
        """Ledger checkpoint can be verified and resumes correctly."""
        order = intent()
        source = ledger_for(order)
        cp = source.checkpoint()
        cp.verify()
        assert cp.ledger_fingerprint == source.ledger_fingerprint
