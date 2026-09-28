from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from backtesting.execution_accounting_v2.accounting import FillEconomicsV2
from execution.paper_exchange_adapter_v1 import (
    PaperAdapterCommandV1,
    PaperExchangeAdapterV1,
)
from execution.paper_gateway_v2 import (
    PaperContingentPairV1,
    PaperGatewayPolicyV1,
    PaperGatewaySnapshotV1,
    PaperOrderState,
    PaperSubmissionV1,
)
from execution.paper_oco_execution_v1 import PaperOCOCoordinatorV1, PaperOCOError
from execution.paper_oco_gateway_bridge_v1 import build_oco_gateway_handoff
from execution.test_paper_oco_execution_v1 import H, account, fixture, observed


def prepared(volume="100"):
    args, stop, target = fixture()
    coordinator = PaperOCOCoordinatorV1(**args)
    result = coordinator.evaluate(
        bar=observed(volume=Decimal(volume)),
        evaluated_at=observed().available_at,
        accounting=args["accounting"],
    )
    gateway = PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(
        Decimal("1000"), Decimal("2000"), 2, timedelta(minutes=2)
    ))
    requested_at = args["armed_at"]
    gateway_stop = replace(stop, submitted_at=requested_at, activation_at=requested_at)
    gateway_target = replace(target, submitted_at=requested_at, activation_at=requested_at)
    pair = PaperContingentPairV1.create(
        PaperSubmissionV1(H("stop-key"), gateway_stop, Decimal("100"), requested_at,
                          requested_at, H("authorization"), True, False),
        PaperSubmissionV1(H("target-key"), gateway_target, Decimal("100"), requested_at,
                          requested_at, H("authorization"), True, False),
    )
    adapter = PaperExchangeAdapterV1.create(gateway)
    adapter, receipt = adapter.execute(PaperAdapterCommandV1(
        H("pair-command"), adapter.gateway.snapshot_id, contingent_pair=pair
    ))
    fill = result.evaluation.fills[0]
    costs = FillEconomicsV2(
        "fill-economics-v2-1", H("cost-" + fill.fill_id), fill.fill_id,
        Decimal("0.1"), Decimal("0.2"), Decimal("0.3"), "USD",
        (H("fee-spec"),), "paper-cost-v1"
    )
    return coordinator, result, adapter, receipt, costs, result.evaluation.evaluated_at + timedelta(microseconds=1)


@pytest.mark.parametrize("volume,paper_cancellations,oco_cancellations", [
    ("100", 1, 2), ("10", 2, 4),
])
def test_builds_deterministic_atomic_resolution(
        volume, paper_cancellations, oco_cancellations):
    coordinator, result, adapter, receipt, costs, resolved_at = prepared(volume)
    handoff = build_oco_gateway_handoff(coordinator=coordinator, result=result, adapter=adapter,
        pair_receipt=receipt, economics=costs, resolved_at=resolved_at)
    repeated = build_oco_gateway_handoff(coordinator=coordinator, result=result, adapter=adapter,
        pair_receipt=receipt, economics=costs, resolved_at=resolved_at)
    assert handoff == repeated
    assert handoff.trading_authority is False
    assert handoff.verified_fill.fill == result.evaluation.fills[0]
    assert len(handoff.command.contingent_resolution.cancellations) == paper_cancellations
    assert len(handoff.oco_cancellations) == oco_cancellations

    updated, applied = adapter.execute(handoff.command)
    assert applied.accepted
    assert all(record.state in (PaperOrderState.FILLED, PaperOrderState.CANCELLED)
               for record in updated.gateway.records)
    book = account(coordinator.accounting, result)
    coordinator.acknowledge_accounting(book)
    final = coordinator.acknowledge_cancellation(
        accounting=book, cancellations=handoff.oco_cancellations
    )
    assert final in ("CLOSED_FLAT", "CANCELLED_REQUIRES_REARM")


@pytest.mark.parametrize("damage", ["cost", "quantity", "order", "time", "receipt"])
def test_mismatched_or_stale_inputs_fail_before_creating_command(damage):
    coordinator, result, adapter, receipt, costs, resolved_at = prepared()
    if damage == "cost":
        costs = replace(costs, fill_id=H("foreign-fill"))
    elif damage == "quantity":
        result = replace(result, projected_remaining_quantity=Decimal("1"))
    elif damage == "order":
        fill = replace(result.evaluation.fills[0], order_id=H("foreign-order"))
        result = replace(result, evaluation=replace(result.evaluation, fills=(fill,)))
    elif damage == "time":
        resolved_at = result.evaluation.fills[0].fill_time
    else:
        receipt = replace(receipt, pair_id=H("foreign-pair"))
    with pytest.raises((PaperOCOError, ValueError)):
        build_oco_gateway_handoff(coordinator=coordinator, result=result, adapter=adapter,
            pair_receipt=receipt, economics=costs, resolved_at=resolved_at)


def test_detached_result_from_another_coordinator_is_rejected():
    coordinator, result, adapter, receipt, costs, resolved_at = prepared()
    other_args, _, _ = fixture()
    other = PaperOCOCoordinatorV1(**other_args)
    with pytest.raises(PaperOCOError, match="active coordinator"):
        build_oco_gateway_handoff(coordinator=other, result=result, adapter=adapter,
            pair_receipt=receipt, economics=costs, resolved_at=resolved_at)


def test_bridge_has_no_transport_or_fabricated_economics_surface():
    from pathlib import Path
    source = Path(__file__).with_name("paper_oco_gateway_bridge_v1.py").read_text("utf-8").lower()
    for word in ("requests", "httpx", "socket", "websocket", "api_key",
                 "private_key", "place_order", "submit_live", "subprocess"):
        assert word not in source
