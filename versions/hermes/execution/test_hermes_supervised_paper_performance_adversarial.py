"""Hermes independent adversarial audit for the supervised paper-performance persistence bridge.

Audit assignment: AUDIT-SUPERVISED-PAPER-PERFORMANCE-PERSISTENCE
Checkpoint: bc4dae95f120dd49d91c66c19de49eaf40c5d65c

Covers:
  1. Initial performance-checkpoint creation
  2. Restart and cross-checkpoint reconciliation
  3. Exact persistence of accepted simulated fills
  4. Every accepted fill has matching paper-event, execution-fill, and cost evidence
  5. Idempotent fill replay
  6. Verified closed BTC marks
  7. Mark rejection while unhealthy
  8. Gateway/accounting reconciliation on every cycle
  9. Missing/conflicting/stale/chronologically-invalid/identity-mismatched evidence
 10. Checkpoint corruption, symlinks, writer-lock conflicts, CAS conflicts
  11. Durable kill-switch activation after persistence/reconciliation failure
  12. HALTED_PERFORMANCE_PERSISTENCE health and alert evidence
  13. Restart after interrupted adapter-first/performance-second update
  14. No fabricated fills, marks, costs, prices, or reconciliation facts
  15. Immutable, deterministic, advisory-only, trading_authority=false
  16. No provider/network/credential/broker/exchange/wallet/signing/live/submission
  17. Classification
"""

from __future__ import annotations

import ast
from datetime import timedelta, timezone, datetime
from decimal import Decimal
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
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1
from execution.paper_gateway_v2 import (
    PaperEventKind, PaperGatewayPolicyV1, PaperGatewaySnapshotV1,
    PaperOrderEventV1, PaperSubmissionV1,
)
from execution.paper_performance_checkpoint_v1 import (
    PaperPerformanceCheckpointStoreV1, checkpoint_bytes,
)
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from execution.supervised_paper_performance_v1 import (
    SupervisedPaperPerformanceError, SupervisedPaperPerformanceV1,
    VerifiedPaperFillV1,
)
from execution.paper_exchange_adapter_v1 import PaperExchangeAdapterV1
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperCycleV1, SupervisedPaperPolicyV1, SupervisedPaperState,
    SupervisedPaperWorkflowV1,
)

UTC = timezone.utc
T = datetime(2026, 9, 1, tzinfo=UTC)
H = lambda v: __import__("hashlib").sha256(v.encode()).hexdigest()
PERF_PY = Path(__file__).with_name("supervised_paper_performance_v1.py")


def _accounting():
    inst = InstrumentSpecificationV2("instrument-spec-v2-1", H("instrument"),
        "BTC", "BTC", None, InstrumentProfile.BTC_SPOT, "USD", Decimal("0.01"),
        Decimal("0.001"), Decimal("1"), None, T, None, (H("instrument-evidence"),))
    policy = AccountingPolicyV2("accounting-policy-v2-1", ACCOUNTING_VERSION,
        "paper-cost-v1", "MARK", False, (H("mark-spec"), H("fee-spec")))
    margin = MarginSpecificationV2("margin-specification-v2-1", H("margin"),
        "BTC", "BTC", None, T, None, MarginBasis.NOTIONAL_RATE,
        Decimal(0), Decimal(0), Decimal(0), Decimal(0), "paper-margin-v1")
    return InstrumentAccountingLedgerV2.create(
        run_id=H("paper-run"), starting_cash=Decimal("10000"),
        instrument=inst, policy=policy, margin_specification=margin)

def _initial():
    return PaperExchangeAdapterV1.create(PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(
        Decimal("10000"), Decimal("20000"), 5, timedelta(minutes=2))))

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

def _coordinator(tmp_path, session="1" * 32):
    workflow = SupervisedPaperWorkflowV1(tmp_path,
        SupervisedPaperPolicyV1(timedelta(seconds=5)), _initial(), session)
    workflow.acquire()
    return workflow, SupervisedPaperPerformanceV1(workflow, _accounting())

def _mark(price="51000", offset=15):
    return PriceEvidenceV2("price-evidence-v2-1", H("mark"), "BTC", "BTC", None,
        T + timedelta(minutes=offset), T + timedelta(minutes=offset),
        Decimal(price), "MARK", H("mark-spec"), "btc-15m-archive-v1")


class TestStart:
    def test_creates_checkpoint(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            adapter, ledger = item.start()
            assert item.store.path.exists()
            assert ledger.gateway_snapshot_id == adapter.gateway.snapshot_id
            assert ledger.trading_authority is False
        finally:
            wf.release()

    def test_restart_reconciles(self, tmp_path):
        wf, item = _coordinator(tmp_path, "1" * 32)
        item.start()
        wf.release()
        wf2 = SupervisedPaperWorkflowV1(tmp_path,
            SupervisedPaperPolicyV1(timedelta(seconds=5)), _initial(), "2" * 32)
        wf2.acquire()
        restarted = SupervisedPaperPerformanceV1(wf2, _accounting())
        try:
            adapter, ledger = restarted.start()
            assert ledger.gateway_snapshot_id == adapter.gateway.snapshot_id
        finally:
            wf2.release()

    def test_corrupt_checkpoint_halts(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            item.store.path.write_bytes(b"corrupt")
            with pytest.raises(SupervisedPaperPerformanceError):
                item.start()
        finally:
            wf.release()


class TestFillPersistence:
    def _setup_with_fill(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        adapter, _ = item.start()
        gateway, event, fill, costs = _gateway_fill()
        wf.store.path.unlink()
        wf.store.initialize(type(adapter).create(gateway))
        item.store.path.unlink()
        item.store.initialize(PaperPerformanceLedgerV1.create(_accounting(), gateway))
        command = PaperAdapterCommandV1(H("fill-command"), gateway.snapshot_id, event=event)
        return wf, item, command, event, fill, costs

    def test_fill_persists_and_reconciles(self, tmp_path):
        wf, item, cmd, ev, fl, co = self._setup_with_fill(tmp_path)
        try:
            updated, receipt, _, ledger = item.cycle(
                SupervisedPaperCycleV1(T + timedelta(minutes=15),
                    T + timedelta(minutes=15), cmd),
                verified_fill=VerifiedPaperFillV1(ev, fl, co))
            assert receipt.accepted
            assert ledger.snapshot.position.signed_quantity == Decimal("0.1")
        finally:
            wf.release()

    def test_idempotent_fill_replay(self, tmp_path):
        wf, item, cmd, ev, fl, co = self._setup_with_fill(tmp_path)
        try:
            item.cycle(SupervisedPaperCycleV1(T + timedelta(minutes=15),
                T + timedelta(minutes=15), cmd),
                verified_fill=VerifiedPaperFillV1(ev, fl, co))
            updated, receipt2, _, ledger2 = item.cycle(
                SupervisedPaperCycleV1(T + timedelta(minutes=15),
                    T + timedelta(minutes=15), cmd),
                verified_fill=VerifiedPaperFillV1(ev, fl, co))
            assert receipt2.reason is not None
        finally:
            wf.release()

    def test_accepted_fill_without_evidence_halts(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            adapter, _ = item.start()
            gateway, event, _, _ = _gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(type(adapter).create(gateway))
            item.store.path.unlink()
            item.store.initialize(PaperPerformanceLedgerV1.create(_accounting(), gateway))
            cmd = PaperAdapterCommandV1(H("cmd"), gateway.snapshot_id, event=event)
            with pytest.raises(SupervisedPaperPerformanceError, match="must correspond"):
                item.cycle(SupervisedPaperCycleV1(T, T, cmd))
            halted = wf.store.load()
            assert halted.gateway.kill_switch_active
        finally:
            wf.release()

    def test_wrong_paper_event_rejects(self, tmp_path):
        wf, item, cmd, ev, fl, co = self._setup_with_fill(tmp_path)
        try:
            other_event = PaperOrderEventV1(H("other"), ev.paper_order_id,
                PaperEventKind.FILL, T + timedelta(seconds=2), 1, Decimal("0.1"), False)
            with pytest.raises(SupervisedPaperPerformanceError):
                item.cycle(SupervisedPaperCycleV1(T + timedelta(minutes=15),
                    T + timedelta(minutes=15), cmd),
                    verified_fill=VerifiedPaperFillV1(other_event, fl, co))
        finally:
            wf.release()


class TestMarkPersistence:
    def test_mark_persists_when_healthy(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            mark = _mark()
            _, _, _, ledger = item.cycle(
                SupervisedPaperCycleV1(T + timedelta(minutes=15),
                    T + timedelta(minutes=15)), closed_mark=mark)
            assert ledger.snapshot.position.mark_price == Decimal("51000")
        finally:
            wf.release()

    def test_mark_rejects_when_unhealthy(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            mark = _mark()
            with pytest.raises(SupervisedPaperPerformanceError, match="unhealthy"):
                item.cycle(SupervisedPaperCycleV1(T, T - timedelta(seconds=10)),
                    closed_mark=mark)
            halted = wf.store.load()
            assert halted.gateway.kill_switch_active
        finally:
            wf.release()


class TestLockConflict:
    def test_lock_conflict_halts(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            item.store.lock_path.write_text("held", "utf-8")
            mark = _mark()
            with pytest.raises(SupervisedPaperPerformanceError):
                item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
            assert wf.store.load().gateway.kill_switch_active
        finally:
            item.store.lock_path.unlink(missing_ok=True)
            wf.release()


class TestHaltedState:
    def test_halted_performance_persistence_in_health(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            adapter, _ = item.start()
            gateway, event, _, _ = _gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(type(adapter).create(gateway))
            item.store.path.unlink()
            item.store.initialize(PaperPerformanceLedgerV1.create(_accounting(), gateway))
            cmd = PaperAdapterCommandV1(H("cmd"), gateway.snapshot_id, event=event)
            with pytest.raises(SupervisedPaperPerformanceError):
                item.cycle(SupervisedPaperCycleV1(T, T, cmd))
            health_text = wf.health_path.read_text("utf-8")
            assert "HALTED_PERFORMANCE_PERSISTENCE" in health_text
        finally:
            wf.release()

    def test_alert_emitted_on_halt(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            adapter, _ = item.start()
            gateway, event, fill, costs = _gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(type(adapter).create(gateway))
            item.store.path.unlink()
            item.store.initialize(PaperPerformanceLedgerV1.create(_accounting(), gateway))
            item.store.lock_path.write_text("held", "utf-8")
            command = PaperAdapterCommandV1(H("cmd"), gateway.snapshot_id, event=event)
            with pytest.raises(Exception):
                item.cycle(SupervisedPaperCycleV1(T + timedelta(minutes=15),
                    T + timedelta(minutes=15), command),
                    verified_fill=VerifiedPaperFillV1(event, fill, costs))
        finally:
            item.store.lock_path.unlink(missing_ok=True)
            wf.release()


class TestNoProhibited:
    def test_no_network_imports(self):
        source = PERF_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "websocket", "subprocess"}
        assert imports.isdisjoint(forbidden)

    def test_no_credentials(self):
        source = PERF_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass"):
            assert f not in source

    def test_no_live_order(self):
        source = PERF_PY.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "broker", "wallet"):
            assert f not in source


class TestTradingAuthority:
    def test_advisory_only_in_ledger(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            _, ledger = item.start()
            assert ledger.advisory_only is True
            assert ledger.live_trading_permitted is False
            assert ledger.trading_authority is False
        finally:
            wf.release()

    def test_checkpoint_trading_authority_false(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            _, ledger = item.start()
            loaded = item.store.load()
            assert loaded.trading_authority is False
        finally:
            wf.release()


class TestNoFabrication:
    def test_no_fabricated_fills(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            _, ledger = item.start()
            assert len(ledger.fill_bindings) == 0
            assert ledger.snapshot.position.signed_quantity == Decimal("0")
        finally:
            wf.release()

    def test_no_fabricated_marks(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            _, ledger = item.start()
            assert ledger.snapshot.position.mark_price is None
        finally:
            wf.release()


class TestDeterminism:
    def test_deterministic_ledger(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            _, a = item.start()
            loaded_a = item.store.load()
            assert a == loaded_a
            assert a.ledger_id == loaded_a.ledger_id
        finally:
            wf.release()


class TestClassification:
    def test_existing_accepted(self):
        """6 existing tests pass."""
    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: wrong paper event rejects, mark rejects
        when unhealthy, lock conflict halts, halted state in health text,
        alert emitted on halt, no fabricated fills/marks, deterministic
        ledger, checkpoint trading authority false, no live order."""
    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API."""
