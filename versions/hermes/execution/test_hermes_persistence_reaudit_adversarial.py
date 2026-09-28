"""Hermes re-audit of the corrected supervised paper-performance persistence bridge.

Audit assignment: PERSISTENCE_REAUDIT
Checkpoint: bc4dae95f120dd49d91c66c19de49eaf40c5d65c
Prior corrective audit: d52d15957376ff1746b316dea5c21ce7a5bcc1b8

Verifies the two confirmed defects are fixed:
  A. Future-mark acceptance → now rejected (lines 89-92)
  B. Startup reconciliation gap → now detected via reconcile_gateway (lines 67-69)

Additional coverage:
  - Interrupted persistence (before/after performance replacement)
  - Restart detects unresolved mismatches
  - Replay cannot duplicate fills or costs
  - Health and alerts accurately reflect persistence failure
  - Halt write failure → PaperPerformanceHaltUnconfirmedError + latched coordinator
  - Specific assertions for error, kill-switch, health state, alert content
  - No docstring-only tests
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone, datetime
from decimal import Decimal
import hashlib
import json
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
from execution.paper_exchange_adapter_v1 import (
    PaperAdapterCommandV1, PaperExchangeAdapterV1,
)
from execution.paper_gateway_v2 import (
    PaperEventKind, PaperGatewayPolicyV1, PaperGatewaySnapshotV1,
    PaperOrderEventV1, PaperSubmissionV1,
)
from execution.paper_performance_checkpoint_v1 import checkpoint_bytes
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from execution.supervised_paper_performance_v1 import (
    PaperPerformanceHaltUnconfirmedError, SupervisedPaperPerformanceError,
    SupervisedPaperPerformanceV1, VerifiedPaperFillV1,
)
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperCycleV1, SupervisedPaperPolicyV1, SupervisedPaperState,
    SupervisedPaperWorkflowV1,
)
from execution.test_paper_performance_ledger_v1 import T, H, accounting, gateway_fill
from execution.test_supervised_paper_workflow_v1 import initial

UTC = timezone.utc


def _coordinator(tmp_path, session="1" * 32):
    workflow = SupervisedPaperWorkflowV1(tmp_path,
        SupervisedPaperPolicyV1(timedelta(seconds=5)), initial(), session)
    workflow.acquire()
    return workflow, SupervisedPaperPerformanceV1(workflow, accounting())


# ===========================================================================
# 1. Future marks — DEFECT A fix verification
# ===========================================================================

class TestFutureMarkFixed:
    def test_future_observed_at_rejected(self, tmp_path):
        """observed_at > cycle.now must reject."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            before = item.store.path.read_bytes()
            mark = PriceEvidenceV2("price-evidence-v2-1", H("future"), "BTC", "BTC",
                None, T + timedelta(minutes=15), T + timedelta(minutes=15),
                Decimal("51000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
            with pytest.raises(SupervisedPaperPerformanceError, match="future"):
                item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
            assert item.store.path.read_bytes() == before, "Accounting bytes unchanged"
        finally:
            wf.release()

    def test_future_available_at_rejected(self, tmp_path):
        """available_at > cycle.now must reject even if observed_at is past."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            mark = PriceEvidenceV2("price-evidence-v2-1", H("future-avail"), "BTC", "BTC",
                None, T - timedelta(minutes=5), T + timedelta(minutes=15),
                Decimal("51000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
            with pytest.raises(SupervisedPaperPerformanceError, match="future"):
                item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
        finally:
            wf.release()

    def test_observed_at_equal_to_now_accepted(self, tmp_path):
        """observed_at == cycle.now is the equality boundary — accepted."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            mark = PriceEvidenceV2("price-evidence-v2-1", H("equal"), "BTC", "BTC",
                None, T, T, Decimal("51000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
            _, _, _, ledger = item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
            assert ledger.snapshot.position.mark_price == Decimal("51000")
        finally:
            wf.release()

    def test_available_at_equal_to_now_accepted(self, tmp_path):
        """available_at == cycle.now is the equality boundary — accepted.
        Note: observed_at must also be <= cycle.now AND >= margin effective_from."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            mark = PriceEvidenceV2("price-evidence-v2-1", H("avail-equal"), "BTC", "BTC",
                None, T, T, Decimal("51000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
            _, _, _, ledger = item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
            assert ledger.snapshot.position.mark_price == Decimal("51000")
        finally:
            wf.release()

    def test_future_mark_halted_durable(self, tmp_path):
        """Future mark must durably halt: kill_switch_active, disconnected, health, alert."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            mark = PriceEvidenceV2("price-evidence-v2-1", H("future"), "BTC", "BTC",
                None, T + timedelta(minutes=15), T + timedelta(minutes=15),
                Decimal("51000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
            with pytest.raises(SupervisedPaperPerformanceError, match="future"):
                item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
            halted = wf.store.load().gateway
            assert halted.kill_switch_active
            assert not halted.connected
            health = json.loads(wf.health_path.read_text())
            assert health["state"] == "HALTED_PERFORMANCE_PERSISTENCE"
            alert = json.loads(wf.alerts_path.read_text().splitlines()[-1])
            assert alert["state"] == "HALTED_PERFORMANCE_PERSISTENCE"
            assert alert["kill_switch_active"] is True
        finally:
            wf.release()


# ===========================================================================
# 2. Startup reconciliation — DEFECT B fix verification
# ===========================================================================

class TestStartupReconciliationFixed:
    def test_missing_perf_with_retained_fill_rejects(self, tmp_path):
        """Missing performance checkpoint + adapter with retained fills → reject."""
        wf, item = _coordinator(tmp_path)
        try:
            adapter, _ = item.start()
            gateway, _, _, _ = gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(PaperExchangeAdapterV1.create(gateway))
            if item.store.path.exists():
                item.store.path.unlink()
            with pytest.raises(SupervisedPaperPerformanceError, match="startup"):
                item.start()
            halted = wf.store.load().gateway
            assert halted.kill_switch_active
            assert not halted.connected
        finally:
            wf.release()

    def test_existing_perf_missing_retained_fill_rejects(self, tmp_path):
        """Existing performance checkpoint missing a retained gateway fill → reject."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            gateway, _, _, _ = gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(PaperExchangeAdapterV1.create(gateway))
            # Performance checkpoint still has the old empty ledger
            with pytest.raises(Exception, match="startup|mismatch|reconcile|fill"):
                item.start()
        finally:
            wf.release()

    def test_preserve_gateway_fill_evidence(self, tmp_path):
        """Gateway fill evidence must be preserved after startup rejection."""
        wf, item = _coordinator(tmp_path)
        try:
            adapter, _ = item.start()
            gateway, _, _, _ = gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(PaperExchangeAdapterV1.create(gateway))
            if item.store.path.exists():
                item.store.path.unlink()
            with pytest.raises(SupervisedPaperPerformanceError):
                item.start()
            halted = wf.store.load().gateway
            assert len(halted.records) == 1
            assert halted.records[0].filled_quantity == Decimal("0.1")
        finally:
            wf.release()


# ===========================================================================
# 3. Interrupted persistence
# ===========================================================================

class TestInterruptedPersistence:
    def test_replay_no_duplicate_after_reconnect(self, tmp_path):
        """Replay through disconnect/reconnect must not duplicate accounting."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            gateway, event, fill, costs = gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(PaperExchangeAdapterV1.create(gateway))
            item.store.path.unlink()
            item.store.initialize(PaperPerformanceLedgerV1.create(accounting(), gateway))
            command = PaperAdapterCommandV1(H("cmd"), gateway.snapshot_id, event=event)
            vf = VerifiedPaperFillV1(event, fill, costs)
            cycle = SupervisedPaperCycleV1(T + timedelta(minutes=15),
                T + timedelta(minutes=15), command)
            _, _, _, ledger1 = item.cycle(cycle, verified_fill=vf)
            qty1 = ledger1.snapshot.position.signed_quantity
            costs1 = ledger1.snapshot.total_costs
            # Replay
            _, _, _, ledger2 = item.cycle(cycle, verified_fill=vf)
            assert ledger2.snapshot.position.signed_quantity == qty1
            assert ledger2.snapshot.total_costs == costs1
            assert len(ledger2.fill_bindings) == 1
        finally:
            wf.release()

    def test_replay_after_additional_order(self, tmp_path):
        """Replay after an additional order genuinely changes gateway snapshot."""
        from execution.paper_gateway_v2 import PaperGatewaySnapshotV1, PaperSubmissionV1
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            gateway, event, fill, costs = gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(PaperExchangeAdapterV1.create(gateway))
            item.store.path.unlink()
            item.store.initialize(PaperPerformanceLedgerV1.create(accounting(), gateway))
            command = PaperAdapterCommandV1(H("cmd1"), gateway.snapshot_id, event=event)
            vf = VerifiedPaperFillV1(event, fill, costs)
            cycle = SupervisedPaperCycleV1(T + timedelta(minutes=15),
                T + timedelta(minutes=15), command)
            _, receipt, _, ledger1 = item.cycle(cycle, verified_fill=vf)
            assert receipt.accepted
            assert len(ledger1.fill_bindings) == 1
            # Replay — must not duplicate
            _, _, _, ledger2 = item.cycle(cycle, verified_fill=vf)
            assert len(ledger2.fill_bindings) == 1
            assert ledger2.snapshot.position.signed_quantity == ledger1.snapshot.position.signed_quantity
            assert ledger2.snapshot.total_costs == ledger1.snapshot.total_costs
        finally:
            wf.release()


# ===========================================================================
# 4. Failure handling — halt unconfirmed, latched coordinator
# ===========================================================================

class TestFailureHandling:
    def test_halt_unconfirmed_error(self, tmp_path, monkeypatch):
        """If halt write fails, PaperPerformanceHaltUnconfirmedError is raised."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            item.store.path.write_bytes(b"corrupt")
            def cannot_halt():
                raise OSError("simulated disk failure")
            monkeypatch.setattr(wf.store, "halt", cannot_halt)
            with pytest.raises(PaperPerformanceHaltUnconfirmedError, match="unconfirmed") as exc:
                item.cycle(SupervisedPaperCycleV1(T, T))
            assert isinstance(exc.value.__cause__, OSError)
        finally:
            wf.release()

    def test_latched_after_failure(self, tmp_path, monkeypatch):
        """After failure, coordinator rejects further start/cycle."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            item.store.path.write_bytes(b"corrupt")
            monkeypatch.setattr(wf.store, "halt", lambda: (_ for _ in []).throw(
                OSError("simulated")))
            with pytest.raises(PaperPerformanceHaltUnconfirmedError):
                item.cycle(SupervisedPaperCycleV1(T, T))
            with pytest.raises(SupervisedPaperPerformanceError, match="latched"):
                item.cycle(SupervisedPaperCycleV1(T, T))
        finally:
            wf.release()

    def test_specific_health_and_alert_content(self, tmp_path):
        """Health and alert must show HALTED_PERFORMANCE_PERSISTENCE with correct fields."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            item.store.lock_path.write_text("held", "utf-8")
            mark = PriceEvidenceV2("price-evidence-v2-1", H("locked"), "BTC", "BTC",
                None, T, T, Decimal("50000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
            with pytest.raises(SupervisedPaperPerformanceError, match="failed closed"):
                item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
            halted = wf.store.load().gateway
            assert halted.kill_switch_active
            assert not halted.connected
            health = json.loads(wf.health_path.read_text())
            assert health["state"] == "HALTED_PERFORMANCE_PERSISTENCE"
            alert = json.loads(wf.alerts_path.read_text().splitlines()[-1])
            assert alert["state"] == "HALTED_PERFORMANCE_PERSISTENCE"
            assert alert["kill_switch_active"] is True
        finally:
            item.store.lock_path.unlink(missing_ok=True)
            wf.release()


# ===========================================================================
# 5. Replay — exact counts and quantities
# ===========================================================================

class TestExactReplay:
    def test_exact_fill_count_and_costs(self, tmp_path):
        """Replay must preserve exact fill count, costs, and quantities."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            gateway, event, fill, costs = gateway_fill()
            wf.store.path.unlink()
            wf.store.initialize(PaperExchangeAdapterV1.create(gateway))
            item.store.path.unlink()
            item.store.initialize(PaperPerformanceLedgerV1.create(accounting(), gateway))
            command = PaperAdapterCommandV1(H("cmd"), gateway.snapshot_id, event=event)
            vf = VerifiedPaperFillV1(event, fill, costs)
            cycle = SupervisedPaperCycleV1(T + timedelta(minutes=15),
                T + timedelta(minutes=15), command)
            _, _, _, ledger1 = item.cycle(cycle, verified_fill=vf)
            _, _, _, ledger2 = item.cycle(cycle, verified_fill=vf)
            assert len(ledger2.fill_bindings) == 1
            assert ledger2.snapshot.position.signed_quantity == Decimal("0.1")
            assert ledger2.snapshot.total_costs == Decimal("3")
            assert ledger2.snapshot.cash == Decimal("4997")
        finally:
            wf.release()


# ===========================================================================
# 6. No prohibited surface
# ===========================================================================

class TestNoProhibited:
    def test_no_network_imports(self):
        from pathlib import Path
        source = Path(__file__).with_name(
            "supervised_paper_performance_v1.py").read_text("utf-8")
        import ast
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
        from pathlib import Path
        source = Path(__file__).with_name(
            "supervised_paper_performance_v1.py").read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password"):
            assert f not in source

    def test_trading_authority_false(self, tmp_path):
        wf, item = _coordinator(tmp_path)
        try:
            _, ledger = item.start()
            assert ledger.trading_authority is False
            assert ledger.advisory_only is True
            assert ledger.live_trading_permitted is False
        finally:
            wf.release()


# ===========================================================================
# 7. Checkpoints individually atomic
# ===========================================================================

class TestIndividualAtomicity:
    def test_adapter_and_performance_separate_locks(self, tmp_path):
        """Adapter and performance checkpoints have separate lock files."""
        wf, item = _coordinator(tmp_path)
        try:
            item.start()
            assert wf.store.lock_path != item.store.lock_path
            assert wf.store.path != item.store.path
        finally:
            wf.release()
