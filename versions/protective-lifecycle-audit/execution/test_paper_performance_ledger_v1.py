from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2.accounting import (
    ACCOUNTING_VERSION, AccountingPolicyV2, FillEconomicsV2,
    InstrumentAccountingLedgerV2, MarginBasis, MarginSpecificationV2,
    PriceEvidenceV2,
)
from backtesting.execution_accounting_v2.contracts import (
    InstrumentSpecificationV2, OrderIntentV2, OrderSide, OrderType, TimeInForce,
)
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from execution.paper_gateway_v2 import (
    PaperEventKind, PaperGatewayPolicyV1, PaperGatewaySnapshotV1,
    PaperOrderEventV1, PaperSubmissionV1,
)
from execution.paper_performance_ledger_v1 import (
    PaperPerformanceError, PaperPerformanceLedgerV1,
)


UTC = timezone.utc
T = datetime(2026, 9, 1, tzinfo=UTC)
H = lambda value: hashlib.sha256(value.encode()).hexdigest()


def accounting():
    inst = InstrumentSpecificationV2("instrument-spec-v2-1", H("instrument"),
        "BTC", "BTC", None, InstrumentProfile.BTC_SPOT, "USD", Decimal("0.01"),
        Decimal("0.001"), Decimal("1"), None, T, None, (H("instrument-evidence"),))
    policy = AccountingPolicyV2("accounting-policy-v2-1", ACCOUNTING_VERSION,
        "paper-cost-v1", "MARK", False, (H("mark-spec"), H("fee-spec")))
    margin = MarginSpecificationV2("margin-specification-v2-1", H("margin"),
        "BTC", "BTC", None, T, None, MarginBasis.NOTIONAL_RATE,
        Decimal(0), Decimal(0), Decimal(0), Decimal(0), "paper-margin-v1")
    return InstrumentAccountingLedgerV2.create(run_id=H("paper-run"),
        starting_cash=Decimal("10000"), instrument=inst, policy=policy,
        margin_specification=margin)


def gateway_fill(*, side=OrderSide.BUY, quantity="0.1", price="50000"):
    gateway = PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(
        Decimal("10000"), Decimal("20000"), 5, timedelta(minutes=2)))
    intent = OrderIntentV2("order-intent-v2-1", H("order"), H("run"), H("action"),
        "BTC", "BTC", None, side, Decimal(quantity), OrderType.MARKET,
        TimeInForce.IOC, None, None, T, T, None, None, None,
        "paper-config-v1", "paper-execution-v1")
    submission = PaperSubmissionV1(H("idempotency"), intent, Decimal(price), T,
        T, H("authorization"), True, False)
    gateway, decision = gateway.submit(submission)
    paper_event = PaperOrderEventV1(H("paper-fill"), decision.record.paper_order_id,
        PaperEventKind.FILL, T + timedelta(seconds=1), 0, Decimal(quantity), False)
    gateway, _ = gateway.apply_event(paper_event)
    fill = ExecutionFillV2("execution-fill-v2-1", H("execution-fill"), intent.order_id,
        H("bar"), None, "BTC", "BTC", None, paper_event.occurred_at, side,
        Decimal(quantity), Decimal(price), Decimal(price), Decimal(price), Decimal(0),
        Decimal("100"), Decimal("100"), Decimal("100"), "PAPER_MARKET_FILL",
        "paper-execution-v1", "paper-liquidity-v1", "paper-assumption-v1")
    costs = FillEconomicsV2("fill-economics-v2-1", H("cost"), fill.fill_id,
        Decimal("1"), Decimal("2"), Decimal(0), "USD", (H("fee-spec"),),
        "paper-cost-v1")
    return gateway, paper_event, fill, costs


def test_verified_fill_enters_phase4_accounting_exactly_once():
    gateway, event, fill, costs = gateway_fill()
    book = PaperPerformanceLedgerV1.create(accounting(), gateway)
    result = book.apply_fill(gateway=gateway, paper_event=event, fill=fill, economics=costs)
    assert result.snapshot.position.signed_quantity == Decimal("0.1")
    assert result.snapshot.position.average_entry_price == Decimal("50000")
    assert result.snapshot.total_costs == Decimal("3")
    assert result.snapshot.cash == Decimal("4997")
    assert result.apply_fill(gateway=gateway, paper_event=event, fill=fill, economics=costs) is result


def test_exact_mark_produces_equity_without_fabrication():
    gateway, event, fill, costs = gateway_fill()
    result = PaperPerformanceLedgerV1.create(accounting(), gateway).apply_fill(
        gateway=gateway, paper_event=event, fill=fill, economics=costs)
    mark = PriceEvidenceV2("price-evidence-v2-1", H("mark"), "BTC", "BTC", None,
        T + timedelta(minutes=15), T + timedelta(minutes=15), Decimal("51000"),
        "MARK", H("mark-spec"), "btc-15m-archive-v1")
    marked = result.apply_mark(mark)
    assert marked.snapshot.unrealized_pnl == Decimal("100")
    assert marked.snapshot.equity == Decimal("10097")
    assert marked.apply_mark(mark) is marked


@pytest.mark.parametrize("change,match", [
    ("event", "absent or conflicts"),
    ("order", "gateway and execution"),
    ("quantity", "gateway and execution"),
    ("cost", "different fill"),
])
def test_mismatched_fill_evidence_fails_closed(change, match):
    gateway, event, fill, costs = gateway_fill()
    if change == "event": event = replace(event, event_id=H("other-event"))
    elif change == "order": fill = replace(fill, order_id=H("other-order"))
    elif change == "quantity": fill = replace(fill, quantity=Decimal("0.2"))
    else: costs = replace(costs, fill_id=H("other-fill"))
    with pytest.raises(PaperPerformanceError, match=match):
        PaperPerformanceLedgerV1.create(accounting(), gateway).apply_fill(
            gateway=gateway, paper_event=event, fill=fill, economics=costs)


def test_cancel_event_cannot_enter_accounting():
    gateway, event, fill, costs = gateway_fill()
    event = replace(event, kind=PaperEventKind.CANCEL, fill_quantity=None)
    with pytest.raises(PaperPerformanceError, match="only paper fill"):
        PaperPerformanceLedgerV1.create(accounting(), gateway).apply_fill(
            gateway=gateway, paper_event=event, fill=fill, economics=costs)


def test_gateway_reconciliation_detects_missing_accounted_fill():
    gateway, event, fill, costs = gateway_fill()
    result = PaperPerformanceLedgerV1.create(accounting(), gateway).apply_fill(
        gateway=gateway, paper_event=event, fill=fill, economics=costs)
    empty = PaperGatewaySnapshotV1.create(gateway.policy)
    with pytest.raises(PaperPerformanceError, match="not retained"):
        result.reconcile_gateway(empty)


def test_empty_accounting_and_btc_are_required():
    gateway, event, fill, costs = gateway_fill()
    source = accounting()
    book = PaperPerformanceLedgerV1.create(source, gateway).apply_fill(
        gateway=gateway, paper_event=event, fill=fill, economics=costs)
    with pytest.raises(PaperPerformanceError, match="empty accounting"):
        PaperPerformanceLedgerV1.create(book.accounting, gateway)


def test_ledger_is_immutable_and_has_no_authority():
    gateway, *_ = gateway_fill()
    result = PaperPerformanceLedgerV1.create(accounting(), gateway)
    assert result.advisory_only is True
    assert result.live_trading_permitted is False
    assert result.trading_authority is False
    with pytest.raises(FrozenInstanceError):
        result.trading_authority = True


def test_tampered_identity_rejects():
    gateway, *_ = gateway_fill()
    result = PaperPerformanceLedgerV1.create(accounting(), gateway)
    with pytest.raises(PaperPerformanceError, match="identity mismatch"):
        replace(result, ledger_id="0" * 64)
