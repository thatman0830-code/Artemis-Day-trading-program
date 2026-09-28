from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2.contracts import (
    InstrumentSpecificationV2, OrderIntentV2, OrderSide, OrderState, OrderType, TimeInForce,
)
from backtesting.execution_accounting_v2.ohlc_execution import (
    CollisionGroupV2, EXECUTION_POLICY_VERSION, LIQUIDITY_POLICY_VERSION,
    ExecutionInstructionV2, ExecutionPolicyV2, ExecutionPriority, ExecutionReason,
    ExecutionSourceLineageV2, OHLCBarV2, OHLCExecutionError, evaluate_bar,
)
from backtesting.execution_accounting_v2.order_ledger import (
    LedgerEventKind, OrderLedgerEventV2, OrderLedgerV2,
)
from backtesting.execution_accounting_v2.specifications import InstrumentProfile


UTC = timezone.utc
START = datetime(2025, 6, 1, tzinfo=UTC)
H = lambda value: hashlib.sha256(value.encode()).hexdigest()


def intent(name="order", **changes):
    values = dict(schema_version="order-intent-v2-1", order_id=H(name), run_id=H("run"),
        action_id=H(f"action-{name}"), market="ES", instrument_id="ES", contract_id="ESM5",
        side=OrderSide.BUY, quantity=Decimal("3"), order_type=OrderType.MARKET,
        time_in_force=TimeInForce.GTC, limit_price=None, stop_price=None,
        submitted_at=START, activation_at=START + timedelta(minutes=2), expires_at=None,
        parent_order_id=None, replaces_order_id=None, configuration_version="config-v2",
        execution_policy_version=EXECUTION_POLICY_VERSION)
    values.update(changes)
    return OrderIntentV2(**values)


def ledger_for(*intents):
    ledger = OrderLedgerV2.create(tuple(intents))
    for kind, minute in ((LedgerEventKind.SUBMIT, 1), (LedgerEventKind.ACCEPT, 2),
                         (LedgerEventKind.ACTIVATE, 3)):
        ordered = sorted(intents, key=lambda selected:
            H(f"setup-{kind.value}-{selected.order_id}"))
        for selected in ordered:
            snap = ledger.order(selected.order_id)
            event_time = max(START + timedelta(minutes=minute), selected.activation_at) if kind == LedgerEventKind.ACTIVATE else START + timedelta(minutes=minute)
            event = OrderLedgerEventV2("order-ledger-event-v2-1",
                H(f"setup-{kind.value}-{selected.order_id}"), selected.order_id,
                kind, event_time, len(ledger.events) + 1,
                snap.order_version, selected.market, selected.instrument_id, selected.contract_id,
                H(f"setup-source-{len(ledger.events)+1}"), kind.value,
                contract_eligibility_verified=True)
            ledger = ledger.apply(event)
    return ledger


def instrument(**changes):
    values = dict(schema_version="instrument-spec-v2-1", specification_id=H("instrument"),
        market="ES", instrument_id="ES", contract_id="ESM5",
        profile=InstrumentProfile.ES_FUTURE, currency="USD", tick_size=Decimal("0.25"),
        quantity_step=Decimal("1"), contract_multiplier=Decimal("50"),
        point_value=Decimal("50"), effective_from=START - timedelta(days=1),
        effective_to=None, evidence_ids=(H("evidence"),))
    values.update(changes)
    return InstrumentSpecificationV2(**values)


def policy(**changes):
    values = dict(schema_version="ohlc-execution-policy-v2-1", policy_id=H("policy"),
        execution_policy_version=EXECUTION_POLICY_VERSION,
        liquidity_policy_version=LIQUIDITY_POLICY_VERSION,
        maximum_participation_rate=Decimal("0.10"), assumption_version="assumption-v1")
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
    return ExecutionInstructionV2("execution-instruction-v2-1", H(f"instruction-{order.order_id}"),
        order.order_id, priority, Decimal(participation), Decimal(slippage), "assumption-v1", lineage)


def bar(name="bar", **changes):
    values = dict(schema_version="ohlc-bar-v2-1", bar_id=H(name), market="ES",
        instrument_id="ES", contract_id="ESM5", open_time=START + timedelta(minutes=10),
        close_time=START + timedelta(minutes=11), available_at=START + timedelta(minutes=11),
        open=Decimal("100.00"), high=Decimal("102.00"), low=Decimal("98.00"),
        close=Decimal("101.00"), volume=Decimal("100"), finalized=True,
        session_eligible=True, data_quality_valid=True, contract_eligible=True,
        source_version="dataset-v1")
    values.update(changes)
    return OHLCBarV2(**values)


def evaluate(order, selected_bar=None, selected_instruction=None):
    source = ledger_for(order)
    observed = selected_bar or bar()
    return source, evaluate_bar(ledger=source, bar=observed, evaluated_at=observed.available_at,
        instrument=instrument(), policy=policy(),
        instructions=(selected_instruction or instruction(order),))


def test_market_buy_uses_next_open_plus_adverse_slippage_and_preserves_input():
    order = intent()
    source, result = evaluate(order)
    fill = result.fills[0]
    assert (fill.reference_price, fill.unrounded_economic_price, fill.economic_price,
            fill.adverse_friction) == (Decimal("100"), Decimal("100.25"),
                                       Decimal("100.25"), Decimal("0.25"))
    assert result.output_ledger.order(order.order_id).state == OrderState.FILLED
    assert source.order(order.order_id).state == OrderState.ACTIVE
    assert result.initial_bar_budget == Decimal("10")


def test_sell_market_rounds_adversely_down_when_slippage_is_fractional_tick():
    order = intent(side=OrderSide.SELL)
    source = ledger_for(order); observed = bar()
    selected = instruction(order, slippage="0.5")
    result = evaluate_bar(ledger=source, bar=observed, evaluated_at=observed.available_at,
        instrument=instrument(), policy=policy(), instructions=(selected,))
    assert result.fills[0].unrounded_economic_price == Decimal("99.875")
    assert result.fills[0].economic_price == Decimal("99.75")


def test_limit_touch_records_frozen_limit_without_favorable_gap_improvement():
    order = intent(order_type=OrderType.LIMIT, limit_price=Decimal("101"))
    _, result = evaluate(order)
    assert result.fills[0].reference_price == result.fills[0].economic_price == Decimal("101")
    no_touch = bar("no-touch", low=Decimal("101.25"), open=Decimal("102"),
                   high=Decimal("103"), close=Decimal("102"))
    source = ledger_for(order)
    outcome = evaluate_bar(ledger=source, bar=no_touch, evaluated_at=no_touch.available_at,
        instrument=instrument(), policy=policy(), instructions=(instruction(order),))
    assert outcome.fills == () and outcome.output_ledger == source


@pytest.mark.parametrize("opening,expected,rule", [
    (Decimal("102"), Decimal("102.25"), "STOP_MARKET_GAP_OPEN"),
    (Decimal("100"), Decimal("101.25"), "STOP_MARKET_THRESHOLD"),
])
def test_stop_market_gap_and_intrabar_threshold(opening, expected, rule):
    order = intent(order_type=OrderType.STOP_MARKET, stop_price=Decimal("101"))
    observed = bar(f"stop-{opening}", open=opening, high=Decimal("103"),
                   low=Decimal("99"), close=Decimal("102"))
    _, result = evaluate(order, observed)
    assert result.fills[0].economic_price == expected
    assert result.fills[0].execution_rule_code == rule
    assert len(result.trigger_event_ids) == 1


def test_stop_limit_trigger_bar_never_fills_and_later_bar_may_fill():
    order = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("101"),
                   limit_price=Decimal("101.25"))
    source = ledger_for(order); first = bar("trigger")
    triggered = evaluate_bar(ledger=source, bar=first, evaluated_at=first.available_at,
        instrument=instrument(), policy=policy(), instructions=(instruction(order),))
    assert triggered.fills == ()
    assert triggered.output_ledger.order(order.order_id).state == OrderState.TRIGGERED
    second = bar("later", open_time=START + timedelta(minutes=11),
                 close_time=START + timedelta(minutes=12),
                 available_at=START + timedelta(minutes=12))
    filled = evaluate_bar(ledger=triggered.output_ledger, bar=second,
        evaluated_at=second.available_at, instrument=instrument(), policy=policy(),
        instructions=(instruction(order),))
    assert filled.fills[0].economic_price == Decimal("101.25")
    assert filled.fills[0].trigger_market_event_id == first.bar_id


def test_shared_volume_budget_allocates_by_declared_priority_then_order_identity():
    entry = intent("entry", quantity=Decimal("8"))
    forced = intent("forced", quantity=Decimal("8"), side=OrderSide.SELL)
    source = ledger_for(entry, forced); observed = bar(volume=Decimal("100"))
    result = evaluate_bar(ledger=source, bar=observed, evaluated_at=observed.available_at,
        instrument=instrument(), policy=policy(), instructions=(
            instruction(entry), instruction(forced,
                priority=ExecutionPriority.RISK_SESSION_END_LIQUIDATION)))
    assert [(fill.order_id, fill.quantity) for fill in result.fills] == [
        (forced.order_id, Decimal("8")), (entry.order_id, Decimal("2"))]
    assert result.remaining_bar_budget == 0


def test_zero_volume_produces_no_fill_and_missing_volume_fails_closed():
    order = intent()
    source = ledger_for(order); zero = bar("zero", volume=Decimal("0"))
    result = evaluate_bar(ledger=source, bar=zero, evaluated_at=zero.available_at,
        instrument=instrument(), policy=policy(), instructions=(instruction(order),))
    assert result.fills == () and result.output_ledger == source
    with pytest.raises(OHLCExecutionError) as exc:
        evaluate_bar(ledger=source, bar=bar("missing", volume=None),
            evaluated_at=bar("missing", volume=None).available_at, instrument=instrument(),
            policy=policy(), instructions=(instruction(order),))
    assert exc.value.reason == ExecutionReason.MISSING_VOLUME


def test_ioc_no_touch_evaluates_once_and_cancels_residual():
    order = intent(time_in_force=TimeInForce.IOC, order_type=OrderType.LIMIT,
                   limit_price=Decimal("90"))
    source, result = evaluate(order)
    assert result.fills == () and len(result.evaluation_event_ids) == 1
    assert result.output_ledger.order(order.order_id).state == OrderState.CANCELLED


def test_adverse_collision_suppresses_favorable_order_without_inventing_path():
    stop = intent("stop", side=OrderSide.SELL, order_type=OrderType.STOP_MARKET,
                  stop_price=Decimal("99"))
    target = intent("target", side=OrderSide.SELL, order_type=OrderType.LIMIT,
                    limit_price=Decimal("101"))
    source = ledger_for(stop, target); observed = bar("collision")
    group = CollisionGroupV2("collision-group-v2-1", H("group"), stop.order_id, target.order_id)
    result = evaluate_bar(ledger=source, bar=observed, evaluated_at=observed.available_at,
        instrument=instrument(), policy=policy(), instructions=(instruction(stop), instruction(target)),
        collision_groups=(group,))
    assert [fill.order_id for fill in result.fills] == [stop.order_id]
    assert result.suppressed_favorable_order_ids == (target.order_id,)
    ambiguous = replace(group, ownership_declared=False)
    with pytest.raises(OHLCExecutionError) as exc:
        evaluate_bar(ledger=source, bar=observed, evaluated_at=observed.available_at,
            instrument=instrument(), policy=policy(),
            instructions=(instruction(stop), instruction(target)),
            collision_groups=(ambiguous,))
    assert exc.value.reason == ExecutionReason.AMBIGUOUS_INTRABAR_REJECTED


def test_forming_future_wrong_identity_and_same_source_bar_fail_closed():
    order = intent()
    source = ledger_for(order)
    with pytest.raises(OHLCExecutionError) as exc:
        evaluate_bar(ledger=source, bar=bar(finalized=False), evaluated_at=bar().available_at,
            instrument=instrument(), policy=policy(), instructions=(instruction(order),))
    assert exc.value.reason == ExecutionReason.BAR_NOT_FINAL
    with pytest.raises(OHLCExecutionError) as exc:
        evaluate_bar(ledger=source, bar=bar(), evaluated_at=START + timedelta(minutes=10),
            instrument=instrument(), policy=policy(), instructions=(instruction(order),))
    assert exc.value.reason == ExecutionReason.BAR_NOT_AVAILABLE
    with pytest.raises(OHLCExecutionError) as exc:
        evaluate_bar(ledger=source, bar=bar(market="NQ"), evaluated_at=bar().available_at,
            instrument=instrument(), policy=policy(), instructions=(instruction(order),))
    assert exc.value.reason == ExecutionReason.IDENTITY_MISMATCH
    late = replace(order, activation_at=START + timedelta(minutes=10, seconds=1))
    late_source = ledger_for(late)
    with pytest.raises(OHLCExecutionError) as exc:
        evaluate_bar(ledger=late_source, bar=bar(), evaluated_at=bar().available_at,
            instrument=instrument(), policy=policy(), instructions=(instruction(late),))
    assert exc.value.reason == ExecutionReason.SAME_SOURCE_BAR_INELIGIBLE
    with pytest.raises(ValueError, match="aligned one-minute"):
        bar(close_time=START + timedelta(minutes=11, seconds=1),
            available_at=START + timedelta(minutes=11, seconds=1))


def test_replay_is_deterministic_idempotent_and_records_are_immutable_decimal_only():
    order = intent()
    source = ledger_for(order); observed = bar()
    kwargs = dict(ledger=source, bar=observed, evaluated_at=observed.available_at,
                  instrument=instrument(), policy=policy(), instructions=(instruction(order),))
    first = evaluate_bar(**kwargs); second = evaluate_bar(**kwargs)
    assert first == second and first.evaluation_id == second.evaluation_id
    assert first.output_ledger.serialize() == second.output_ledger.serialize()
    with pytest.raises(FrozenInstanceError):
        first.fills[0].quantity = Decimal("2")
    with pytest.raises(ValueError):
        replace(instruction(order), participation_rate=0.1)
