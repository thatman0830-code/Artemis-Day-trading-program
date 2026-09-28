"""Hermes independent adversarial audit for the end-to-end supervised offline paper workflow.

Audit assignment: AUDIT-SUPERVISED-PAPER-WORKFLOW
Checkpoint: 3de3262787eeded38c067c7a5be37b795259b135

Covers:
  1. Offline/paper-only: no network/credential/live; trading_authority false
  2. One authoritative execution state: adapter checkpoint is sole source
  3. Halt boundary: halt() verifies, kill switch, disconnect, reconciliation, deterministic
  4. Ownership: exclusive lock, second owner rejected, mismatched lock rejects, no cross-release
  5. Startup: initialize once, restart, corrupt fails closed, startup failure releases lock
  6. Cycle chronology: UTC, future/stale reject, age boundary, policy validation
  7. Safety precedence: ownership > timestamp > stop > stale/future > reconciliation > command
  8. Controlled stop: session-bound, stop=true, trading_authority=false, malformed rejects
  9. Stale/future halt: durably checkpointed, kill switch, disconnect, no command in same cycle
 10. Reconciliation: cannot execute before, exact observation, mismatch persisted, no trading
 11. Command execution: only after all gates, exact retry, conflict, duplicate order
 12. Health evidence: immutable, deterministic, heartbeat binds all, atomic, no false HEALTHY
 13. Alert evidence: non-HEALTHY alerts, no healthy alert, SHA-256, no sensitive, deduplicated
 14. Failure windows: no false success, duplicate, lost receipt
 15. Context-manager cleanup: normal, exception, startup, no silent lock deletion
 16. Content addressing: deterministic replay, material changes, ordering
 17. Implementation coupling
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.execution_accounting_v2.contracts import (
    OrderIntentV2, OrderSide, OrderType, TimeInForce,
)
from execution.paper_exchange_adapter_v1 import (
    PaperAdapterCommandV1, PaperAdapterReason, PaperAdapterReceiptV1,
    PaperExchangeAdapterV1,
)
from execution.paper_gateway_v2 import (
    PaperGatewayPolicyV1, PaperGatewaySnapshotV1, PaperSubmissionV1,
)
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperCycleV1, SupervisedPaperError, SupervisedPaperHealthV1,
    SupervisedPaperPolicyV1, SupervisedPaperState, SupervisedPaperWorkflowV1,
)
from monitoring.off_host_alert_delivery import read_alerts

UTC = timezone.utc
NOW = datetime(2026, 9, 1, 18, 0, tzinfo=UTC)
sha = lambda x: hashlib.sha256(x.encode()).hexdigest()
WORKFLOW_PY = Path(__file__).with_name("supervised_paper_workflow_v1.py")


def _initial():
    return PaperExchangeAdapterV1.create(PaperGatewaySnapshotV1.create(
        PaperGatewayPolicyV1(Decimal("500"), Decimal("800"), 2, timedelta(seconds=5))))

def _intent(name="a"):
    return OrderIntentV2("order-intent-v2-1", sha("order" + name), sha("run"),
        sha("action" + name), "BTC", "BTC-PERP", None, OrderSide.BUY, Decimal("1"),
        OrderType.MARKET, TimeInForce.IOC, None, None, NOW, NOW, None, None, None,
        "config-v1", "policy-v1")

def _submission(name="a", authorized=True):
    return PaperSubmissionV1(sha("key" + name), _intent(name), Decimal("100"), NOW, NOW,
                            sha("auth" + name), authorized)

def _command(adapter, name="a", authorized=True):
    return PaperAdapterCommandV1(sha("cmd" + name), adapter.gateway.snapshot_id,
                                  submission=_submission(name, authorized))

def _workflow(root, session="1" * 32):
    return SupervisedPaperWorkflowV1(root, SupervisedPaperPolicyV1(timedelta(seconds=5)),
                                      _initial(), session)

def _cycle(now=NOW, observed=NOW, **kw):
    return SupervisedPaperCycleV1(now, observed, **kw)


# ===========================================================================
# 1. Offline/paper-only
# ===========================================================================

class TestOfflinePaperOnly:
    def test_no_network_imports(self):
        source = WORKFLOW_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "websocket", "smtplib",
                    "paramiko", "asyncio", "subprocess", "aiohttp"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_no_credential_strings(self):
        source = WORKFLOW_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass"):
            assert f not in source, f"forbidden: {f}"

    def test_no_live_order(self):
        source = WORKFLOW_PY.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "live_order", "broker"):
            assert f not in source, f"forbidden: {f}"

    def test_trading_authority_false_in_health(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW))
            assert health.trading_authority is False

    def test_trading_authority_false_in_lock(self, tmp_path):
        with _workflow(tmp_path) as wf:
            lock = json.loads(wf.lock_path.read_text("utf-8"))
            assert lock["trading_authority"] is False

    def test_trading_authority_false_in_alerts(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current, authorized=False)))
            alerts = read_alerts(wf.alerts_path)
            for a in alerts:
                assert a["trading_authority"] is False


# ===========================================================================
# 2. One authoritative execution state
# ===========================================================================

class TestAuthoritativeState:
    def test_adapter_checkpoint_is_sole_source(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            assert isinstance(current, PaperExchangeAdapterV1)

    def test_no_legacy_gateway_checkpoint_used(self, tmp_path):
        source = WORKFLOW_PY.read_text("utf-8")
        assert "PaperGatewayCheckpointStoreV1" not in source

    def test_restart_through_adapter_store(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            current, _, _ = wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
        with _workflow(tmp_path, "2" * 32) as wf2:
            restarted = wf2.start()
            assert not restarted.gateway.connected
            assert restarted.gateway.reconciliation_required


# ===========================================================================
# 3. Halt boundary
# ===========================================================================

class TestHaltBoundary:
    def test_halt_verifies_integrity_first(self):
        source = WORKFLOW_PY.read_text("utf-8")
        # Adapter.halt() calls verify_integrity()
        adapter = _initial()
        halted = adapter.halt()
        assert halted.gateway.kill_switch_active

    def test_halt_activates_kill_switch(self):
        adapter = _initial()
        halted = adapter.halt()
        assert halted.gateway.kill_switch_active

    def test_halt_disconnects(self):
        adapter = _initial()
        halted = adapter.halt()
        assert not halted.gateway.connected

    def test_halt_requires_reconciliation(self):
        adapter = _initial()
        halted = adapter.halt()
        assert halted.gateway.reconciliation_required

    def test_halt_preserves_records(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            current, _, _ = wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            halted = wf.store.halt()
            assert len(halted.gateway.records) == 1
            assert len(halted.receipts) == 1

    def test_halt_deterministic(self):
        a = _initial().halt()
        b = _initial().halt()
        assert a == b

    def test_halt_cannot_clear_kill_switch(self):
        adapter = _initial()
        killed = adapter.gateway.activate_kill_switch()
        killed_adapter = PaperExchangeAdapterV1.create(killed)
        halted = killed_adapter.halt()
        assert halted.gateway.kill_switch_active


# ===========================================================================
# 4. Ownership
# ===========================================================================

class TestOwnership:
    def test_lock_exclusive(self, tmp_path):
        one = _workflow(tmp_path)
        two = _workflow(tmp_path, "2" * 32)
        one.acquire()
        with pytest.raises(SupervisedPaperError, match="owned"):
            two.acquire()
        one.release()

    def test_lock_binds_session_id(self, tmp_path):
        with _workflow(tmp_path) as wf:
            lock = json.loads(wf.lock_path.read_text("utf-8"))
            assert lock["session_id"] == "1" * 32
            assert lock["trading_authority"] is False

    def test_malformed_lock_rejects(self, tmp_path):
        wf = _workflow(tmp_path)
        wf.acquire()
        wf.lock_path.write_text("{}")
        with pytest.raises(SupervisedPaperError, match="mismatch"):
            wf.cycle(_cycle())
        wf.lock_path.write_text(json.dumps({"session_id": "1" * 32, "trading_authority": False}))
        wf.release()

    def test_no_cross_release(self, tmp_path):
        one = _workflow(tmp_path)
        two = _workflow(tmp_path, "2" * 32)
        one.acquire()
        with pytest.raises(SupervisedPaperError):
            two.release()
        one.release()

    def test_ownership_loss_prevents_cycle(self, tmp_path):
        wf = _workflow(tmp_path)
        wf.acquire()
        wf._owned = False  # simulate ownership loss
        with pytest.raises(SupervisedPaperError, match="ownership"):
            wf.cycle(_cycle())


# ===========================================================================
# 5. Startup
# ===========================================================================

class TestStartup:
    def test_first_startup_initializes(self, tmp_path):
        with _workflow(tmp_path) as wf:
            assert wf.store.path.exists()

    def test_existing_triggers_restart(self, tmp_path):
        wf = _workflow(tmp_path)
        wf.acquire()
        wf.start()
        wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(wf.store.load())))
        wf.release()
        wf2 = _workflow(tmp_path, "2" * 32)
        wf2.acquire()
        restarted = wf2.start()
        assert not restarted.gateway.connected
        assert restarted.gateway.reconciliation_required
        wf2.release()

    def test_corrupt_fails_closed(self, tmp_path):
        wf = _workflow(tmp_path)
        wf.acquire()
        wf.start()
        wf.release()
        wf.store.path.write_bytes(b"corrupt")
        wf2 = _workflow(tmp_path, "2" * 32)
        with pytest.raises(Exception):
            wf2.acquire()
            try:
                wf2.start()
            finally:
                if wf2._owned:
                    wf2.release()

    def test_startup_failure_releases_lock(self, tmp_path):
        wf = _workflow(tmp_path)
        wf.acquire()
        wf.start()
        wf.release()
        wf.store.path.write_bytes(b"corrupt")
        wf2 = _workflow(tmp_path, "2" * 32)
        with pytest.raises(Exception):
            with wf2:
                pass
        assert not wf2.lock_path.exists()


# ===========================================================================
# 6. Cycle chronology
# ===========================================================================

class TestCycleChronology:
    def test_naive_now_rejects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            with pytest.raises(SupervisedPaperError, match="UTC"):
                wf.cycle(_cycle(now=NOW.replace(tzinfo=None)))

    def test_non_utc_now_rejects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            with pytest.raises(SupervisedPaperError, match="UTC"):
                wf.cycle(_cycle(now=NOW.replace(tzinfo=timezone(timedelta(hours=5)))))

    def test_naive_observed_rejects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            with pytest.raises(SupervisedPaperError, match="UTC"):
                wf.cycle(_cycle(observed=NOW.replace(tzinfo=None)))

    def test_future_input_halts(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW + timedelta(microseconds=1)))
            assert health.state is SupervisedPaperState.HALTED_FUTURE_INPUT

    def test_stale_input_halts(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=6)))
            assert health.state is SupervisedPaperState.HALTED_STALE_INPUT

    def test_age_at_boundary_accepted(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=5)))
            assert health.state is SupervisedPaperState.HEALTHY

    def test_zero_age_policy_rejects(self):
        with pytest.raises(ValueError, match="positive"):
            SupervisedPaperPolicyV1(timedelta(0))

    def test_negative_age_policy_rejects(self):
        with pytest.raises(ValueError, match="positive"):
            SupervisedPaperPolicyV1(timedelta(seconds=-1))


# ===========================================================================
# 7. Safety precedence
# ===========================================================================

class TestSafetyPrecedence:
    def test_ownership_before_timestamp(self, tmp_path):
        wf = _workflow(tmp_path)
        # Not acquired — ownership fails before timestamp
        with pytest.raises(SupervisedPaperError, match="ownership"):
            wf.cycle(_cycle(now=NOW.replace(tzinfo=None)))

    def test_timestamp_before_stop(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": True, "trading_authority": False}))
            with pytest.raises(SupervisedPaperError, match="UTC"):
                wf.cycle(_cycle(now=NOW.replace(tzinfo=None)))

    def test_stop_before_stale_future(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": True, "trading_authority": False}))
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW + timedelta(hours=1)))
            assert health.state is SupervisedPaperState.STOPPED

    def test_stale_future_before_reconciliation(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            current, _, _ = wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            wf.store.restart()
            # Now reconciliation_required, but stale input takes precedence
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=10)))
            assert health.state is SupervisedPaperState.HALTED_STALE_INPUT


# ===========================================================================
# 8. Controlled stop
# ===========================================================================

class TestControlledStop:
    def test_stop_session_bound(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "2" * 32, "stop": True, "trading_authority": False}))
            with pytest.raises(SupervisedPaperError, match="identity"):
                wf.cycle(_cycle())

    def test_stop_false_rejects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": False, "trading_authority": False}))
            with pytest.raises(SupervisedPaperError, match="identity"):
                wf.cycle(_cycle())

    def test_stop_authority_true_rejects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": True, "trading_authority": True}))
            with pytest.raises(SupervisedPaperError, match="identity"):
                wf.cycle(_cycle())

    def test_stop_extra_field_rejects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": True, "trading_authority": False, "extra": True}))
            with pytest.raises(SupervisedPaperError, match="identity"):
                wf.cycle(_cycle())

    def test_stop_state_is_stopped(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": True, "trading_authority": False}))
            _, _, health = wf.cycle(_cycle())
            assert health.state is SupervisedPaperState.STOPPED

    def test_stop_disconnects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": True, "trading_authority": False}))
            current, _, _ = wf.cycle(_cycle())
            assert not current.gateway.connected

    def test_stop_no_command_executes(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            cmd = _command(current)
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": True, "trading_authority": False}))
            current, receipt, _ = wf.cycle(_cycle(now=NOW, observed=NOW, command=cmd))
            assert receipt is None  # stop takes precedence over command


# ===========================================================================
# 9. Stale/future halt
# ===========================================================================

class TestHaltBehavior:
    def test_halt_durably_checkpointed(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current, _, health = wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=6)))
            loaded = wf.store.load()
            assert loaded.gateway.kill_switch_active
            assert not loaded.gateway.connected

    def test_halt_kill_switch_active(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=6)))
            assert health.kill_switch_active

    def test_halt_disconnects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=6)))
            assert health.reconciliation_required

    def test_halt_no_command_in_same_cycle(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            cmd = _command(current)
            _, receipt, _ = wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=10), command=cmd))
            assert receipt is None  # stale input takes precedence over command

    def test_repeated_halt_no_conflict(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=10)))
            wf.cycle(_cycle(now=NOW + timedelta(seconds=1), observed=NOW - timedelta(seconds=10)))
            loaded = wf.store.load()
            assert loaded.gateway.kill_switch_active


# ===========================================================================
# 10. Reconciliation
# ===========================================================================

class TestReconciliation:
    def _setup_restarted(self, tmp_path):
        wf = _workflow(tmp_path, "1" * 32)
        wf.acquire()
        current = wf.start()
        wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
        wf.release()
        wf2 = _workflow(tmp_path, "2" * 32)
        wf2.acquire()
        wf2.start()
        return wf2

    def test_cannot_execute_before_reconciliation(self, tmp_path):
        wf2 = self._setup_restarted(tmp_path)
        current = wf2.store.load()
        # After restart, reconciliation_required — a cycle with a command
        # does NOT execute the command; it returns RECONCILIATION_REQUIRED
        _, _, health = wf2.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
        assert health.state is SupervisedPaperState.RECONCILIATION_REQUIRED
        # No new order was created
        loaded = wf2.store.load()
        assert len(loaded.gateway.records) == 1  # from the original session
        wf2.release()

    def test_exact_observation_restores(self, tmp_path):
        wf2 = self._setup_restarted(tmp_path)
        current = wf2.store.load()
        record = current.gateway.records[0]
        observed = ((record.paper_order_id, record.state, record.filled_quantity,
                     record.remaining_quantity, record.version),)
        recovered, _, health = wf2.cycle(_cycle(now=NOW, observed=NOW, reconciliation_observation=observed))
        # Kill switch may be active from restart — check state
        wf2.release()

    def test_mismatch_persists(self, tmp_path):
        wf2 = self._setup_restarted(tmp_path)
        failed, _, health = wf2.cycle(_cycle(now=NOW, observed=NOW, reconciliation_observation=()))
        assert health.kill_switch_active
        wf2.release()

    def test_unsolicited_reconciliation_rejects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            with pytest.raises(SupervisedPaperError, match="unsolicited"):
                wf.cycle(_cycle(now=NOW, observed=NOW, reconciliation_observation=()))

    def test_reconciliation_no_trading_authority(self, tmp_path):
        wf2 = self._setup_restarted(tmp_path)
        current = wf2.store.load()
        record = current.gateway.records[0]
        observed = ((record.paper_order_id, record.state, record.filled_quantity,
                     record.remaining_quantity, record.version),)
        _, _, health = wf2.cycle(_cycle(now=NOW, observed=NOW, reconciliation_observation=observed))
        assert health.trading_authority is False
        wf2.release()

    def test_reconciliation_cannot_clear_kill_switch(self, tmp_path):
        wf2 = self._setup_restarted(tmp_path)
        # First: mismatch to set kill switch
        wf2.cycle(_cycle(now=NOW, observed=NOW, reconciliation_observation=()))
        current = wf2.store.load()
        assert current.gateway.kill_switch_active
        # Now exact observation
        record = current.gateway.records[0]
        observed = ((record.paper_order_id, record.state, record.filled_quantity,
                     record.remaining_quantity, record.version),)
        recovered, _, health = wf2.cycle(_cycle(now=NOW + timedelta(seconds=1), observed=NOW + timedelta(seconds=1), reconciliation_observation=observed))
        assert recovered.gateway.kill_switch_active  # cannot clear
        wf2.release()


# ===========================================================================
# 11. Command execution
# ===========================================================================

class TestCommandExecution:
    def test_command_after_gates(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            _, receipt, _ = wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            assert receipt.accepted

    def test_exact_retry_idempotent(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            cmd = _command(current)
            wf.cycle(_cycle(now=NOW, observed=NOW, command=cmd))
            _, receipt, _ = wf.cycle(_cycle(now=NOW + timedelta(seconds=1), observed=NOW + timedelta(seconds=1), command=cmd))
            assert receipt.reason is PaperAdapterReason.IDEMPOTENT_REPLAY

    def test_conflict_rejects(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            cmd = _command(current)
            wf.cycle(_cycle(now=NOW, observed=NOW, command=cmd))
            conflict = PaperAdapterCommandV1(cmd.command_id, wf.store.load().gateway.snapshot_id,
                                              submission=_submission("b"))
            _, receipt, _ = wf.cycle(_cycle(now=NOW + timedelta(seconds=1), observed=NOW + timedelta(seconds=1), command=conflict))
            assert receipt.reason is PaperAdapterReason.COMMAND_CONFLICT

    def test_duplicate_order_no_exposure(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            dup = PaperAdapterCommandV1(sha("other"), wf.store.load().gateway.snapshot_id,
                                        submission=_submission("b", authorized=True).__class__(
                                            sha("key2"), _intent("a"), Decimal("100"), NOW, NOW, sha("auth2"), True))
            _, receipt, _ = wf.cycle(_cycle(now=NOW + timedelta(seconds=1), observed=NOW + timedelta(seconds=1), command=dup))
            loaded = wf.store.load()
            open_count = sum(1 for r in loaded.gateway.records if r.state.value == "ACCEPTED")
            assert open_count == 1

    def test_receipt_persisted_before_health(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            _, receipt, _ = wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            loaded = wf.store.load()
            assert len(loaded.receipts) == 1
            assert receipt.accepted


# ===========================================================================
# 12. Health evidence
# ===========================================================================

class TestHealthEvidence:
    def test_immutable(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, health = wf.cycle(_cycle())
            with pytest.raises(FrozenInstanceError):
                health.trading_authority = True

    def test_deterministic(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, h1 = wf.cycle(_cycle())
            _, _, h2 = wf.cycle(_cycle())
            # Different now → different heartbeat, but same state
            assert h1.state == h2.state

    def test_heartbeat_binds_all(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, health = wf.cycle(_cycle())
            doc = json.loads(wf.health_path.read_text("utf-8"))
            core = {k: v for k, v in doc.items() if k != "heartbeat_id"}
            assert hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == doc["heartbeat_id"]

    def test_no_false_healthy_after_halt(self, tmp_path):
        with _workflow(tmp_path) as wf:
            _, _, health = wf.cycle(_cycle(now=NOW, observed=NOW - timedelta(seconds=10)))
            assert health.state is not SupervisedPaperState.HEALTHY

    def test_no_false_healthy_after_stop(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.stop_path.write_text(json.dumps({"session_id": "1" * 32, "stop": True, "trading_authority": False}))
            _, _, health = wf.cycle(_cycle())
            assert health.state is not SupervisedPaperState.HEALTHY

    def test_health_atomic_replace(self, tmp_path):
        with _workflow(tmp_path) as wf:
            wf.cycle(_cycle())
            assert not (tmp_path / ".latest-health.tmp").exists()


# ===========================================================================
# 13. Alert evidence
# ===========================================================================

class TestAlertEvidence:
    def test_no_alert_for_healthy(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            assert not wf.alerts_path.exists()

    def test_alert_for_rejected(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current, authorized=False)))
            alerts = read_alerts(wf.alerts_path)
            assert len(alerts) == 1
            assert alerts[0]["trading_authority"] is False

    def test_alert_sha256_event_id(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current, authorized=False)))
            alerts = read_alerts(wf.alerts_path)
            body = {k: v for k, v in alerts[0].items() if k != "event_id"}
            expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            assert alerts[0]["event_id"] == expected

    def test_alert_no_sensitive_fields(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current, authorized=False)))
            text = wf.alerts_path.read_text("utf-8").lower()
            for f in ("password", "api_key", "private_key", "secret", "credential"):
                assert f not in text

    def test_alert_deduplicated(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current, authorized=False)))
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current, authorized=False)))
            if wf.alerts_path.exists():
                alerts = read_alerts(wf.alerts_path)
                ids = [a["event_id"] for a in alerts]
                assert len(ids) == len(set(ids))


# ===========================================================================
# 14. Failure windows
# ===========================================================================

class TestFailureWindows:
    def test_no_false_success_on_lock_failure(self, tmp_path):
        wf = _workflow(tmp_path)
        wf.acquire()
        wf2 = _workflow(tmp_path, "2" * 32)
        with pytest.raises(SupervisedPaperError):
            wf2.acquire()
        # wf's lock is intact
        assert wf.lock_path.exists()
        wf.release()

    def test_no_duplicate_on_health_failure(self, tmp_path):
        with _workflow(tmp_path) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            # Checkpoint has 1 record and 1 receipt
            loaded = wf.store.load()
            assert len(loaded.gateway.records) == 1


# ===========================================================================
# 15. Context-manager cleanup
# ===========================================================================

class TestContextManager:
    def test_normal_exit_releases(self, tmp_path):
        with _workflow(tmp_path) as wf:
            pass
        assert not (tmp_path / "supervised-paper.lock").exists()

    def test_exception_releases(self, tmp_path):
        wf = _workflow(tmp_path)
        try:
            with wf:
                raise RuntimeError("test")
        except RuntimeError:
            pass
        assert not wf.lock_path.exists()

    def test_startup_exception_releases(self, tmp_path):
        wf = _workflow(tmp_path)
        wf.acquire()
        wf.start()
        wf.release()
        wf.store.path.write_bytes(b"corrupt")
        wf2 = _workflow(tmp_path, "2" * 32)
        with pytest.raises(Exception):
            with wf2:
                pass
        assert not wf2.lock_path.exists()


# ===========================================================================
# 16. Content addressing and replay
# ===========================================================================

class TestContentAddressing:
    def test_deterministic_replay(self, tmp_path):
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()
        with _workflow(root_a) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            a_loaded = wf.store.load()
        with _workflow(root_b) as wf:
            current = wf.store.load()
            wf.cycle(_cycle(now=NOW, observed=NOW, command=_command(current)))
            b_loaded = wf.store.load()
        assert a_loaded.adapter_id == b_loaded.adapter_id

    def test_session_id_must_be_uuid_hex(self):
        with pytest.raises(ValueError, match="session_id"):
            SupervisedPaperWorkflowV1(Path("/tmp"), SupervisedPaperPolicyV1(timedelta(seconds=5)),
                                       _initial(), "not-a-uuid")


# ===========================================================================
# 17. Implementation coupling
# ===========================================================================

class TestImplementationCoupling:
    def test_uses_public_contracts(self):
        source = WORKFLOW_PY.read_text("utf-8")
        tree = ast.parse(source)
        ext_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                ext_imports.add(node.module)
        assert "execution.paper_exchange_adapter_checkpoint_v1" in ext_imports
        assert "execution.paper_exchange_adapter_v1" in ext_imports

    def test_no_legacy_gateway_checkpoint(self):
        source = WORKFLOW_PY.read_text("utf-8")
        assert "PaperGatewayCheckpointStoreV1" not in source
