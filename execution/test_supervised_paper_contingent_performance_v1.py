from datetime import timedelta
from decimal import Decimal

import pytest

from backtesting.execution_accounting_v2.accounting import FillEconomicsV2
from backtesting.execution_accounting_v2.contracts import (
    OrderIntentV2,
    OrderSide,
    OrderType,
    TimeInForce,
)
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1
from execution.paper_gateway_v2 import (
    PaperContingentPairV1,
    PaperContingentResolutionV1,
    PaperEventKind,
    PaperGatewayPolicyV1,
    PaperGatewaySnapshotV1,
    PaperOrderEventV1,
    PaperOrderState,
    PaperSubmissionV1,
)
from execution.supervised_paper_performance_v1 import (
    SupervisedPaperPerformanceError,
    SupervisedPaperPerformanceV1,
    VerifiedPaperFillV1,
)
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperCycleV1,
    SupervisedPaperPolicyV1,
    SupervisedPaperWorkflowV1,
)
from execution.paper_exchange_adapter_v1 import PaperExchangeAdapterV1
from execution.test_paper_performance_ledger_v1 import H, T, accounting


def intent(name, side, quantity, order_type, *, parent=None, limit=None, stop=None):
    return OrderIntentV2(
        "order-intent-v2-1",
        H("order-" + name),
        H("paper-run"),
        H("action-" + name),
        "BTC",
        "BTC",
        None,
        side,
        Decimal(quantity),
        order_type,
        TimeInForce.IOC if order_type is OrderType.MARKET else TimeInForce.GTC,
        limit,
        stop,
        T,
        T,
        None,
        parent,
        None,
        "paper-config-v1",
        "paper-execution-v1",
    )


def submission(name, order, price):
    return PaperSubmissionV1(
        H("key-" + name), order, Decimal(price), T, T, H("authorization"), True, False
    )


def execution_fill(name, order, event, price):
    return ExecutionFillV2(
        "execution-fill-v2-1",
        H("fill-" + name),
        order.order_id,
        H("bar-" + name),
        None,
        "BTC",
        "BTC",
        None,
        event.occurred_at,
        order.side,
        event.fill_quantity,
        Decimal(price),
        Decimal(price),
        Decimal(price),
        Decimal(0),
        Decimal("100"),
        Decimal("100"),
        Decimal("100"),
        "PAPER_PROTECTIVE_FILL",
        "paper-execution-v1",
        "paper-liquidity-v1",
        "paper-assumption-v1",
    )


def economics(name, fill):
    return FillEconomicsV2(
        "fill-economics-v2-1",
        H("economics-" + name),
        fill.fill_id,
        Decimal("0.10"),
        Decimal("0.20"),
        Decimal(0),
        "USD",
        (H("fee-spec"),),
        "paper-cost-v1",
    )


def cycle(item, at, command=None, verified_fill=None):
    return item.cycle(
        SupervisedPaperCycleV1(at, at, command), verified_fill=verified_fill
    )


def prepared(tmp_path):
    policy = PaperGatewayPolicyV1(
        Decimal("100000"), Decimal("200000"), 5, timedelta(minutes=2)
    )
    workflow = SupervisedPaperWorkflowV1(
        tmp_path,
        SupervisedPaperPolicyV1(timedelta(seconds=5)),
        PaperExchangeAdapterV1.create(PaperGatewaySnapshotV1.create(policy)),
        "1" * 32,
    )
    workflow.acquire()
    item = SupervisedPaperPerformanceV1(workflow, accounting())
    adapter, _ = item.start()

    entry = intent("entry", OrderSide.BUY, "0.1", OrderType.MARKET)
    submit_entry = PaperAdapterCommandV1(
        H("submit-entry"),
        adapter.gateway.snapshot_id,
        submission=submission("entry", entry, "50000"),
    )
    adapter, _, _, _ = cycle(item, T, submit_entry)
    entry_record = adapter.gateway.records[0]
    entry_event = PaperOrderEventV1(
        H("entry-event"),
        entry_record.paper_order_id,
        PaperEventKind.FILL,
        T + timedelta(seconds=1),
        0,
        Decimal("0.1"),
        False,
    )
    entry_fill = execution_fill("entry", entry, entry_event, "50000")
    adapter, _, _, _ = cycle(
        item,
        entry_event.occurred_at,
        PaperAdapterCommandV1(
            H("fill-entry"), adapter.gateway.snapshot_id, event=entry_event
        ),
        VerifiedPaperFillV1(entry_event, entry_fill, economics("entry", entry_fill)),
    )

    stop = intent(
        "stop",
        OrderSide.SELL,
        "0.1",
        OrderType.STOP_MARKET,
        parent=entry.order_id,
        stop=Decimal("49000"),
    )
    target = intent(
        "target",
        OrderSide.SELL,
        "0.1",
        OrderType.LIMIT,
        parent=entry.order_id,
        limit=Decimal("52000"),
    )
    pair = PaperContingentPairV1.create(
        submission("stop", stop, "50000"), submission("target", target, "50000")
    )
    adapter, receipt, _, _ = cycle(
        item,
        T + timedelta(seconds=2),
        PaperAdapterCommandV1(
            H("submit-pair"), adapter.gateway.snapshot_id, contingent_pair=pair
        ),
    )
    records = tuple(
        next(record for record in adapter.gateway.records if record.paper_order_id == order_id)
        for order_id in receipt.paper_order_ids
    )
    fill_event = PaperOrderEventV1(
        H("stop-fill-event"),
        records[0].paper_order_id,
        PaperEventKind.FILL,
        T + timedelta(seconds=3),
        0,
        Decimal("0.1"),
        False,
    )
    cancel_event = PaperOrderEventV1(
        H("target-cancel-event"),
        records[1].paper_order_id,
        PaperEventKind.CANCEL,
        T + timedelta(seconds=4),
        0,
        None,
        False,
    )
    resolution = PaperContingentResolutionV1.create(
        pair_id=pair.pair_id,
        paper_order_ids=receipt.paper_order_ids,
        fill=fill_event,
        cancellations=(cancel_event,),
    )
    fill = execution_fill("stop", stop, fill_event, "49000")
    command = PaperAdapterCommandV1(
        H("resolve-pair"),
        adapter.gateway.snapshot_id,
        contingent_resolution=resolution,
    )
    return workflow, item, command, VerifiedPaperFillV1(
        fill_event, fill, economics("stop", fill)
    )


def test_atomic_resolution_persists_gateway_and_performance_together(tmp_path):
    workflow, item, command, evidence = prepared(tmp_path)
    try:
        adapter, receipt, _, ledger = cycle(
            item, T + timedelta(seconds=4), command, evidence
        )
        assert receipt.accepted
        assert [record.state for record in adapter.gateway.records[1:]] == [
            PaperOrderState.FILLED,
            PaperOrderState.CANCELLED,
        ]
        assert ledger.gateway_snapshot_id == adapter.gateway.snapshot_id
        assert ledger.snapshot.position.signed_quantity == 0
        assert len(ledger.fill_bindings) == 2
        assert item.store.load() == ledger
    finally:
        workflow.release()


def test_atomic_resolution_replay_does_not_duplicate_performance(tmp_path):
    workflow, item, command, evidence = prepared(tmp_path)
    try:
        adapter, _, _, first = cycle(
            item, T + timedelta(seconds=4), command, evidence
        )
        replayed, receipt, _, second = cycle(
            item, T + timedelta(seconds=4), command, evidence
        )
        assert replayed is not adapter
        assert replayed.gateway == adapter.gateway
        assert receipt.reason.value == "IDEMPOTENT_REPLAY"
        assert second.accounting == first.accounting
        assert second.fill_bindings == first.fill_bindings
        assert len(second.fill_bindings) == 2
    finally:
        workflow.release()


def test_atomic_resolution_without_matching_economics_halts_durably(tmp_path):
    workflow, item, command, _ = prepared(tmp_path)
    try:
        with pytest.raises(SupervisedPaperPerformanceError, match="must correspond"):
            cycle(item, T + timedelta(seconds=4), command)
        halted = workflow.store.load().gateway
        assert halted.kill_switch_active and not halted.connected
        assert halted.records[1].state is PaperOrderState.FILLED
        assert halted.records[2].state is PaperOrderState.CANCELLED
    finally:
        workflow.release()
