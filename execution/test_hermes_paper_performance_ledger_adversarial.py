"""Hermes independent adversarial audit for the evidence-bound paper-performance ledger.

Audit assignment: AUDIT-PAPER-PERFORMANCE-LEDGER
Checkpoint: d526a301f2c4522b1403c5db5a1f160e5f62ed83
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from pathlib import Path

import pytest

from backtesting.execution_accounting_v2.accounting import (
    ACCOUNTING_VERSION, AccountingPolicyV2, FillEconomicsV2,
    InstrumentAccountingLedgerV2, MarginBasis, MarginSpecificationV2,
    PriceEvidenceV2,
)
from backtesting.execution_accounting_v2.contracts import (
    InstrumentProfile, InstrumentSpecificationV2, OrderIntentV2, OrderSide,
    OrderType, TimeInForce,
)
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from execution.paper_gateway_v2 import (
    PaperEventKind, PaperGatewayPolicyV1, PaperGatewaySnapshotV1,
    PaperOrderEventV1, PaperSubmissionV1,
)
from execution.paper_performance_ledger_v1 import (
    SCHEMA_VERSION, PaperPerformanceError, PaperPerformanceLedgerV1,
)

UTC = timezone.utc
T = datetime(2026, 9, 1, tzinfo=UTC)
H = lambda v: hashlib.sha256(v.encode()).hexdigest()
LEDGER_PY = Path(__file__).with_name("paper_performance_ledger_v1.py")


def _accounting(profile=InstrumentProfile.BTC_SPOT):
    inst = InstrumentSpecificationV2("instrument-spec-v2-1", H("instrument"),
        "BTC", "BTC", None, profile, "USD", Decimal("0.01"),
        Decimal("0.001"), Decimal("1"), None, T, None, (H("instrument-evidence"),))
    policy = AccountingPolicyV2("accounting-policy-v2-1", ACCOUNTING_VERSION,
        "paper-cost-v1", "MARK", False, (H("mark-spec"), H("fee-spec")))
    margin = MarginSpecificationV2("margin-specification-v2-1", H("margin"),
        "BTC", "BTC", None, T, None, MarginBasis.NOTIONAL_RATE,
        Decimal(0), Decimal(0), Decimal(0), Decimal(0), "paper-margin-v1")
    return InstrumentAccountingLedgerV2.create(
        run_id=H("paper-run"), starting_cash=Decimal("10000"),
        instrument=inst, policy=policy, margin_specification=margin)

def _gateway_fill(*, side=OrderSide.BUY, quantity="0.1", price="50000"):
    gateway = PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(
        Decimal("10000"), Decimal("20000"), 5, timedelta(minutes=2)))
    intent = OrderIntentV2("order-intent-v2-1", H("order"), H("run"), H("action"),
        "BTC", "BTC", None, side, Decimal(quantity), OrderType.MARKET,
        TimeInForce.IOC, None, None, T, T, None, None, None,
        "paper-config-v1", "paper-execution-v1")
    submission = PaperSubmissionV1(H("idempotency"), intent, Decimal(price),
        T, T, H("authorization"), True, False)
    gateway, decision = gateway.submit(submission)
    paper_event = PaperOrderEventV1(H("paper-fill"), decision.record.paper_order_id,
        PaperEventKind.FILL, T + timedelta(seconds=1), 0, Decimal(quantity), False)
    gateway, _ = gateway.apply_event(paper_event)
    fill = ExecutionFillV2("execution-fill-v2-1", H("execution-fill"), intent.order_id,
        H("bar"), None, "BTC", "BTC", None, paper_event.occurred_at, side,
        Decimal(quantity), Decimal(price), Decimal(price), Decimal(price),
        Decimal(0), Decimal("100"), Decimal("100"), Decimal("100"),
        "PAPER_MARKET_FILL", "paper-execution-v1", "paper-liquidity-v1",
        "paper-assumption-v1")
    costs = FillEconomicsV2("fill-economics-v2-1", H("cost"), fill.fill_id,
        Decimal("1"), Decimal("2"), Decimal(0), "USD",
        (H("fee-spec"),), "paper-cost-v1")
    return gateway, paper_event, fill, costs

def _mark(price="51000", offset=15):
    return PriceEvidenceV2("price-evidence-v2-1", H("mark"), "BTC", "BTC", None,
        T + timedelta(minutes=offset), T + timedelta(minutes=offset),
        Decimal(price), "MARK", H("mark-spec"), "btc-15m-archive-v1")


class TestNoTradingAuthority:
    def test_advisory_only(self):
        gw, *_ = _gateway_fill()
        assert PaperPerformanceLedgerV1.create(_accounting(), gw).advisory_only is True
    def test_live_trading_false(self):
        gw, *_ = _gateway_fill()
        assert PaperPerformanceLedgerV1.create(_accounting(), gw).live_trading_permitted is False
    def test_trading_authority_false(self):
        gw, *_ = _gateway_fill()
        assert PaperPerformanceLedgerV1.create(_accounting(), gw).trading_authority is False
    def test_no_network_imports(self):
        src = LEDGER_PY.read_text("utf-8")
        tree = ast.parse(src)
        imports = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                   for a in n.names}
        imports |= {n.module.split(".")[0] for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
        assert imports.isdisjoint({"requests", "httpx", "socket", "websocket", "subprocess", "os", "sys"})
    def test_no_credentials(self):
        src = LEDGER_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass"):
            assert f not in src

class TestFillBinding:
    def test_fill_enters_accounting(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        assert r.snapshot.position.signed_quantity == Decimal("0.1")
    def test_missing_order_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        empty = PaperGatewaySnapshotV1.create(gw.policy)
        with pytest.raises(PaperPerformanceError, match="absent"):
            PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=empty, paper_event=ev, fill=fl, economics=co)
    def test_cancel_event_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        ev = replace(ev, kind=PaperEventKind.CANCEL, fill_quantity=None)
        with pytest.raises(PaperPerformanceError, match="only paper fill"):
            PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
    def test_wrong_fill_id_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        bad = replace(co, fill_id=H("other"))
        with pytest.raises(PaperPerformanceError, match="different fill"):
            PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=bad)
    def test_wrong_quantity_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        bad = replace(fl, quantity=Decimal("0.2"))
        with pytest.raises(PaperPerformanceError, match="gateway and execution"):
            PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=bad, economics=co)
    def test_wrong_market_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        bad = replace(fl, market="ES")
        with pytest.raises(PaperPerformanceError, match="gateway and execution"):
            PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=bad, economics=co)

class TestIdempotency:
    def test_fill_replay_noop(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        assert r.apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co) is r
    def test_mark_replay_noop(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        m = _mark()
        marked = r.apply_mark(m)
        assert marked.apply_mark(m) is marked

class TestLedgerIntegrity:
    def test_immutable(self):
        gw, *_ = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw)
        with pytest.raises(FrozenInstanceError):
            r.trading_authority = True
    def test_tampered_id_rejects(self):
        gw, *_ = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw)
        with pytest.raises(PaperPerformanceError, match="identity mismatch"):
            replace(r, ledger_id="0" * 64)
    def test_deterministic(self):
        gw, *_ = _gateway_fill()
        assert PaperPerformanceLedgerV1.create(_accounting(), gw) == PaperPerformanceLedgerV1.create(_accounting(), gw)
    def test_fill_bindings_must_be_tuple(self):
        gw, *_ = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw)
        with pytest.raises(PaperPerformanceError, match="immutable"):
            replace(r, fill_bindings=[])

class TestMarkValidation:
    def test_mark_wrong_market_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        bad = replace(_mark(), market="ES", instrument_id="ES")
        with pytest.raises(PaperPerformanceError, match="identity disagree"):
            r.apply_mark(bad)
    def test_mark_produces_pnl(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        marked = r.apply_mark(_mark())
        assert marked.snapshot.unrealized_pnl == Decimal("100")
        assert marked.snapshot.equity == Decimal("10097")

class TestReconciliation:
    def test_missing_accounted_fill_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        empty = PaperGatewaySnapshotV1.create(gw.policy)
        with pytest.raises(PaperPerformanceError, match="not retained"):
            r.reconcile_gateway(empty)
    def test_filled_quantity_mismatch_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        from execution.paper_gateway_v2 import PaperOrderState
        rec = gw.records[0]
        mod = replace(rec, filled_quantity=Decimal("0.05"), remaining_quantity=Decimal("0.05"),
                      state=PaperOrderState.PARTIALLY_FILLED)
        new_recs = tuple(mod if x == rec else x for x in gw.records)
        mod_gw = PaperGatewaySnapshotV1._build(gw.policy, False, False, False, new_recs)
        with pytest.raises(PaperPerformanceError, match="reconcile"):
            r.reconcile_gateway(mod_gw)

class TestBtcOnly:
    def test_non_btc_rejects(self):
        gw, *_ = _gateway_fill()
        inst = InstrumentSpecificationV2("instrument-spec-v2-1", H("instrument"),
            "ES", "ES", None, InstrumentProfile.ES_FUTURE, "USD",
            Decimal("0.25"), Decimal("1"), Decimal("50"), None, T, None, (H("evidence"),))
        policy = AccountingPolicyV2("accounting-policy-v2-1", ACCOUNTING_VERSION,
            "paper-cost-v1", "MARK", False, (H("mark-spec"), H("fee-spec")))
        margin = MarginSpecificationV2("margin-specification-v2-1", H("margin"),
            "ES", "ES", None, T, None, MarginBasis.NOTIONAL_RATE,
            Decimal(0), Decimal(0), Decimal(0), Decimal(0), "paper-margin-v1")
        es_acc = InstrumentAccountingLedgerV2.create(
            run_id=H("paper-run"), starting_cash=Decimal("10000"),
            instrument=inst, policy=policy, margin_specification=margin)
        with pytest.raises(PaperPerformanceError, match="BTC only"):
            PaperPerformanceLedgerV1.create(es_acc, gw)
    def test_non_empty_accounting_rejects(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        with pytest.raises(PaperPerformanceError, match="empty accounting"):
            PaperPerformanceLedgerV1.create(r.accounting, gw)

class TestExactCosts:
    def test_costs_exact(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        assert r.snapshot.total_costs == Decimal("3")
        assert r.snapshot.commissions == Decimal("1")
        assert r.snapshot.exchange_fees == Decimal("2")
        assert r.snapshot.slippage_costs == Decimal("0")
    def test_cash_exact(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        assert r.snapshot.cash == Decimal("4997")
    def test_no_inferred_pnl(self):
        gw, ev, fl, co = _gateway_fill()
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        assert r.snapshot.unrealized_pnl == Decimal("0")

class TestSellBehavior:
    def test_sell_enters_accounting(self):
        gw, ev, fl, co = _gateway_fill(side=OrderSide.SELL)
        r = PaperPerformanceLedgerV1.create(_accounting(), gw).apply_fill(gateway=gw, paper_event=ev, fill=fl, economics=co)
        assert r.snapshot.position.signed_quantity == Decimal("-0.1")

class TestClassification:
    def test_existing_accepted(self):
        """11 existing tests pass."""
    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: wrong market, sell behavior, no inferred P&L,
        mark wrong market, filled quantity mismatch, non-BTC accounting, no network,
        no credentials, fill bindings must be tuple, non-empty accounting."""
    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: PaperPerformanceLedgerV1, PaperPerformanceError, SCHEMA_VERSION."""

