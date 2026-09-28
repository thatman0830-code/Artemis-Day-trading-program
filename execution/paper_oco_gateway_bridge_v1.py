"""Deterministic bridge from an offline OCO result to the paper gateway.

The bridge creates no market observation, fill, price, cost, or external order.
It translates one already-verified OCO execution fill into the paper gateway's
atomic fill-and-cancel command and binds the same fill to explicit economics for
the supervised performance coordinator.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from backtesting.execution_accounting_v2.accounting import FillEconomicsV2
from backtesting.execution_accounting_v2.ohlc_execution import (
    ExecutionEvaluationV2,
    ExecutionFillV2,
)
from backtesting.execution_accounting_v2.contracts import OrderState
from backtesting.execution_accounting_v2.order_ledger import (
    LedgerEventKind,
    OrderLedgerEventV2,
)
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from execution.paper_exchange_adapter_v1 import (
    PaperAdapterCommandV1,
    PaperAdapterPairReceiptV1,
    PaperAdapterReason,
    PaperExchangeAdapterV1,
)
from execution.paper_gateway_v2 import (
    PaperContingentResolutionV1,
    PaperEventKind,
    PaperOrderEventV1,
    PaperOrderState,
)
from execution.paper_oco_execution_v1 import (
    PaperOCOCoordinatorV1,
    PaperOCOError,
    PaperOCOResultV1,
)
from execution.supervised_paper_performance_v1 import VerifiedPaperFillV1


VERSION = "paper-oco-gateway-bridge-v1"


@dataclass(frozen=True, slots=True)
class PaperOCOGatewayHandoffV1:
    bridge_id: str
    command: PaperAdapterCommandV1
    verified_fill: VerifiedPaperFillV1
    oco_cancellations: tuple[OrderLedgerEventV2, ...]
    trading_authority: bool = False

    def __post_init__(self) -> None:
        expected = canonical_fingerprint(
            VERSION, self.command, self.verified_fill, self.oco_cancellations, False
        )
        if self.bridge_id != expected or self.trading_authority is not False:
            raise PaperOCOError("OCO gateway handoff integrity failure")


def build_oco_gateway_handoff(*, coordinator: PaperOCOCoordinatorV1,
                              result: PaperOCOResultV1,
                              adapter: PaperExchangeAdapterV1,
                              pair_receipt: PaperAdapterPairReceiptV1,
                              economics: FillEconomicsV2,
                              resolved_at: datetime) -> PaperOCOGatewayHandoffV1:
    """Translate one pending OCO fill into an atomic paper-only resolution."""
    if type(coordinator) is not PaperOCOCoordinatorV1 or type(result) is not PaperOCOResultV1:
        raise PaperOCOError("active coordinator and typed OCO result required")
    result.__post_init__()
    if (coordinator.state != "AWAITING_ACCOUNTING"
            or coordinator.pending != result
            or coordinator.ledger != result.evaluation.output_ledger):
        raise PaperOCOError("result is not the active coordinator's pending evaluation")
    adapter.verify_integrity()
    if type(pair_receipt) is not PaperAdapterPairReceiptV1:
        raise PaperOCOError("typed contingent-pair receipt required")
    pair_receipt.__post_init__()
    if (not pair_receipt.accepted
            or pair_receipt.reason is not PaperAdapterReason.CONTINGENT_PAIR_APPLIED
            or pair_receipt not in adapter.receipts):
        raise PaperOCOError("accepted retained contingent-pair receipt required")
    if (resolved_at.tzinfo is None or resolved_at.utcoffset() != timedelta(0)):
        raise PaperOCOError("resolved_at must be UTC")

    evaluation = result.evaluation
    if type(evaluation) is not ExecutionEvaluationV2:
        raise PaperOCOError("typed OCO evaluation required")
    evaluation.__post_init__()
    if result.state != "AWAITING_ACCOUNTING" or len(evaluation.fills) != 1:
        raise PaperOCOError("exactly one pending OCO fill required")
    fill = evaluation.fills[0]
    if type(fill) is not ExecutionFillV2 or type(economics) is not FillEconomicsV2:
        raise PaperOCOError("typed fill and economics required")
    fill.__post_init__()
    economics.__post_init__()
    if economics.fill_id != fill.fill_id:
        raise PaperOCOError("fill economics reference a different OCO fill")
    if resolved_at < evaluation.evaluated_at or resolved_at <= fill.fill_time:
        raise PaperOCOError("resolution must follow the evaluated fill")

    records = tuple(
        next(
            (
                record
                for record in adapter.gateway.records
                if record.paper_order_id == paper_order_id
            ),
            None,
        )
        for paper_order_id in pair_receipt.paper_order_ids
    )
    if (any(record is None for record in records)
            or any(record.state is not PaperOrderState.ACCEPTED for record in records)
            or any(record.version != 0 or record.filled_quantity != 0 for record in records)
            or len({record.order_id for record in records}) != 2):
        raise PaperOCOError("gateway pair is missing, changed, or already resolved")
    winner = next((record for record in records if record.order_id == fill.order_id), None)
    if winner is None:
        raise PaperOCOError("OCO fill does not belong to the retained gateway pair")
    sibling = next(record for record in records if record is not winner)
    if (fill.market != winner.market or fill.quantity > winner.remaining_quantity
            or fill.quantity <= 0
            or result.projected_remaining_quantity != winner.quantity - fill.quantity
            or fill.order_id in evaluation.suppressed_favorable_order_ids
            or any(order_id not in {record.order_id for record in records}
                   for order_id in evaluation.suppressed_favorable_order_ids)):
        raise PaperOCOError("OCO fill and gateway pair do not reconcile")

    fill_event = PaperOrderEventV1(
        canonical_fingerprint(VERSION, result.result_id, fill.fill_id,
                              winner.paper_order_id, "FILL"),
        winner.paper_order_id,
        PaperEventKind.FILL,
        fill.fill_time,
        winner.version,
        fill.quantity,
        False,
    )
    cancellations = []
    if fill.quantity < winner.remaining_quantity:
        cancellations.append(PaperOrderEventV1(
            canonical_fingerprint(VERSION, result.result_id, fill.fill_id,
                                  winner.paper_order_id, "CANCEL_RESIDUAL"),
            winner.paper_order_id,
            PaperEventKind.CANCEL,
            resolved_at,
            winner.version + 1,
            None,
            False,
        ))
    cancellations.append(PaperOrderEventV1(
        canonical_fingerprint(VERSION, result.result_id, fill.fill_id,
                              sibling.paper_order_id, "CANCEL_SIBLING"),
        sibling.paper_order_id,
        PaperEventKind.CANCEL,
        resolved_at,
        sibling.version,
        None,
        False,
    ))
    resolution = PaperContingentResolutionV1.create(
        pair_id=pair_receipt.pair_id,
        paper_order_ids=pair_receipt.paper_order_ids,
        fill=fill_event,
        cancellations=tuple(cancellations),
    )
    command = PaperAdapterCommandV1(
        canonical_fingerprint(VERSION, result.result_id, resolution.resolution_id,
                              adapter.gateway.snapshot_id),
        adapter.gateway.snapshot_id,
        contingent_resolution=resolution,
    )
    verified_fill = VerifiedPaperFillV1(fill_event, fill, economics)
    oco_ledger = coordinator.ledger
    oco_cancellations = []
    for order in sorted(oco_ledger.orders, key=lambda item: item.intent.order_id):
        if order.state is OrderState.FILLED:
            continue
        for kind in (LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL):
            current = oco_ledger.order(order.intent.order_id)
            event_time = resolved_at + timedelta(
                microseconds=len(oco_cancellations)
            )
            event = OrderLedgerEventV2(
                "order-ledger-event-v2-1",
                canonical_fingerprint(VERSION, result.result_id,
                                      order.intent.order_id, kind.value),
                order.intent.order_id,
                kind,
                event_time,
                len(oco_ledger.events) + 1,
                current.order_version,
                order.intent.market,
                order.intent.instrument_id,
                order.intent.contract_id,
                result.result_id,
                "SUPERVISED_PAPER_ATOMIC_OCO_RESOLUTION",
            )
            oco_ledger = oco_ledger.apply(event)
            oco_cancellations.append(event)
    oco_cancellations = tuple(oco_cancellations)
    if not 1 <= len(oco_cancellations) <= 4:
        raise PaperOCOError("bounded OCO cancellation evidence required")
    identity = canonical_fingerprint(
        VERSION, command, verified_fill, oco_cancellations, False
    )
    return PaperOCOGatewayHandoffV1(
        identity, command, verified_fill, oco_cancellations, False
    )
