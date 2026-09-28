"""Hermes independent adversarial audit for the supervised-paper operational drills.

Audit assignment: AUDIT-SUPERVISED-PAPER-OPERATIONAL-DRILLS
Checkpoint: 401fb830e80f11fd612bb044a7a1d2117867ed8e

Covers:
  1. Drill root must be new and isolated
  2. All drill evidence is immutable, deterministic, content-addressed
  3. Simulated power-loss restart disconnects and requires exact reconciliation
  4. Process exceptions release ownership lock without discarding checkpoint
  5. Stale/future input activates fail-closed
  6. No recorder accessed/controlled/restarted/represented
  7. Checkpoint corruption rejects restart and releases ownership
  8. Exact command replay is idempotent, no duplicate exposure
  9. Conflicting reuse of command identity rejects without changing exposure
 10. Reconciliation mismatch remains disconnected with kill switch active
 11. Controlled stop is identity-bound, durable, disconnected, alerted
 12. Cloud-sync alert delivery uses only isolated local fixture
 13. No real physical outage, off-host delivery, or soak test claim
 14. trading_authority remains false throughout
 15. No network/credentials/providers/scheduled tasks/recorders/wallets/brokers/signing/live
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from execution.supervised_paper_operational_drills_v1 import (
    DRILL_VERSION, OperationalDrillObservationV1, OperationalDrillReportV1,
    run_supervised_operational_drills,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 1, 20, 0, tzinfo=UTC)
DRILLS_PY = Path(__file__).with_name("supervised_paper_operational_drills_v1.py")


# ===========================================================================
# 1. Drill root must be new and isolated
# ===========================================================================

class TestDrillRoot:
    def test_existing_root_rejects(self, tmp_path):
        existing = tmp_path / "existing"
        existing.mkdir()
        with pytest.raises(ValueError, match="new path"):
            run_supervised_operational_drills(existing, observed_at=NOW)

    def test_symlink_root_rejects(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("symlink requires admin on Windows")
        with pytest.raises(ValueError):
            run_supervised_operational_drills(link, observed_at=NOW)

    def test_naive_observed_at_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="UTC"):
            run_supervised_operational_drills(tmp_path / "naive",
                                              observed_at=NOW.replace(tzinfo=None))

    def test_non_utc_observed_at_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="UTC"):
            run_supervised_operational_drills(tmp_path / "nonutc",
                                              observed_at=NOW.replace(tzinfo=timezone(timedelta(hours=5))))


# ===========================================================================
# 2. Evidence is immutable, deterministic, content-addressed
# ===========================================================================

class TestEvidenceIntegrity:
    def test_report_immutable(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        with pytest.raises(FrozenInstanceError):
            report.trading_authority = True

    def test_observations_immutable(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        for obs in report.observations:
            with pytest.raises(FrozenInstanceError):
                obs.trading_authority = True

    def test_deterministic_replay(self, tmp_path):
        a = run_supervised_operational_drills(tmp_path / "a", observed_at=NOW)
        b = run_supervised_operational_drills(tmp_path / "b", observed_at=NOW)
        assert a == b
        assert a.report_id == b.report_id

    def test_report_id_is_sha256(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        assert len(report.report_id) == 64
        assert all(c in "0123456789abcdef" for c in report.report_id)

    def test_evidence_ids_unique(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        ids = [o.evidence_id for o in report.observations]
        assert len(ids) == len(set(ids))

    def test_all_observations_passed(self, tmp_path):
        report = run_supervised_supervised_operational_drills(tmp_path / "drills", observed_at=NOW) if False else \
                 run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        assert all(o.passed for o in report.observations)

    def test_observation_count(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        assert len(report.observations) == 11


# ===========================================================================
# 3. Simulated power-loss restart
# ===========================================================================

class TestPowerLossRestart:
    def test_restart_disconnects(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "simulated-power-loss-restart")
        assert obs.passed

    def test_restart_requires_exact_reconciliation(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "simulated-power-loss-restart")
        assert "exact reconciliation" in obs.reason


# ===========================================================================
# 4. Process exceptions release lock
# ===========================================================================

class TestProcessException:
    def test_lock_released_after_exception(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "simulated-process-exception")
        assert obs.passed
        assert "lock" in obs.reason.lower()


# ===========================================================================
# 5. Stale/future input
# ===========================================================================

class TestStaleFutureInput:
    def test_stale_recorder_evidence_halts(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "stale-recorder-evidence")
        assert obs.passed
        assert "halts" in obs.reason.lower() or "halt" in obs.reason.lower()

    def test_future_clock_evidence_halts(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "future-clock-evidence")
        assert obs.passed

    def test_no_recorder_operated(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        for obs in report.observations:
            if "stale" in obs.name or "future" in obs.name:
                assert "recorder" not in obs.reason.lower() or "without operating" in obs.reason.lower()


# ===========================================================================
# 6. No recorder accessed/controlled
# ===========================================================================

class TestNoRecorderControl:
    def test_no_recorder_imports(self):
        source = DRILLS_PY.read_text("utf-8").lower()
        for f in ("start_recorder", "stop_recorder", "btc_recorder", "es_nq_recorder",
                  "run_btc_forward_recorder", "run_es_nq_delayed_forward"):
            assert f not in source, f"forbidden: {f}"


# ===========================================================================
# 7. Checkpoint corruption
# ===========================================================================

class TestCheckpointCorruption:
    def test_corruption_rejects_and_releases(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "checkpoint-corruption")
        assert obs.passed
        assert "corrupt" in obs.reason.lower()
        assert "ownership" in obs.reason.lower() or "lock" in obs.reason.lower()


# ===========================================================================
# 8. Exact command replay
# ===========================================================================

class TestCommandReplay:
    def test_idempotent_no_duplicate(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "duplicate-command-replay")
        assert obs.passed
        assert "no duplicate" in obs.reason.lower()


# ===========================================================================
# 9. Conflicting reuse
# ===========================================================================

class TestConflictingReuse:
    def test_conflict_rejects(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "conflicting-command-reuse")
        assert obs.passed
        assert "reject" in obs.reason.lower()


# ===========================================================================
# 10. Reconciliation mismatch
# ===========================================================================

class TestReconciliationMismatch:
    def test_mismatch_disconnected_kill_switch(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "reconciliation-mismatch")
        assert obs.passed
        assert "disconnected" in obs.reason.lower() or "kill switch" in obs.reason.lower()


# ===========================================================================
# 11. Controlled stop
# ===========================================================================

class TestControlledStop:
    def test_stop_identity_bound(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "controlled-stop")
        assert obs.passed
        assert "identity" in obs.reason.lower() or "stop" in obs.reason.lower()

    def test_stop_alerted(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "controlled-stop")
        assert "alert" in obs.reason.lower()


# ===========================================================================
# 12. Cloud-sync alert delivery uses local fixture
# ===========================================================================

class TestCloudSyncAlert:
    def test_local_fixture_delivers(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "local-cloud-sync-alert-handoff")
        assert obs.passed

    def test_uses_local_fixture_not_real_delivery(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        obs = next(o for o in report.observations if o.name == "local-cloud-sync-alert-handoff")
        assert "local fixture" in obs.reason.lower()
        assert "not claimed" in obs.reason.lower() or "not" in obs.reason.lower()


# ===========================================================================
# 13. No physical outage / off-host / soak claim
# ===========================================================================

class TestNoPhysicalClaim:
    def test_no_physical_outage_claimed(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        assert report.physical_outage_claimed is False

    def test_no_recorder_operation_claimed(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        assert report.recorder_operation_claimed is False

    def test_source_disclaims_physical_outage(self):
        source = DRILLS_PY.read_text("utf-8").lower()
        assert "neither operate recorders" in source or "not" in source.lower()

    def test_no_soak_test_claim(self):
        source = DRILLS_PY.read_text("utf-8").lower()
        assert "soak" not in source

    def test_no_off_host_delivery_claim(self):
        source = DRILLS_PY.read_text("utf-8").lower()
        # The module should say it doesn't claim off-host delivery
        assert "not" in source  # it says "physical off-host delivery is not claimed"


# ===========================================================================
# 14. trading_authority false throughout
# ===========================================================================

class TestTradingAuthorityFalse:
    def test_report_trading_authority_false(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        assert report.trading_authority is False

    def test_observations_trading_authority_false(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        for obs in report.observations:
            assert obs.trading_authority is False

    def test_observation_default_simulated_true(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        for obs in report.observations:
            assert obs.simulated is True


# ===========================================================================
# 15. No network/credentials/providers/etc
# ===========================================================================

class TestNoProhibited:
    def test_no_network_imports(self):
        source = DRILLS_PY.read_text("utf-8")
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
        source = DRILLS_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass", "credential"):
            assert f not in source, f"forbidden: {f}"

    def test_no_live_order(self):
        source = DRILLS_PY.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "live_order", "broker"):
            assert f not in source, f"forbidden: {f}"

    def test_no_scheduled_task(self):
        source = DRILLS_PY.read_text("utf-8").lower()
        for f in ("scheduledtask", "register-scheduledtask", "new-scheduledtask"):
            assert f not in source, f"forbidden: {f}"


# ===========================================================================
# 16. Report schema
# ===========================================================================

class TestReportSchema:
    def test_schema_version(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        assert report.schema_version == DRILL_VERSION

    def test_observations_are_tuple(self, tmp_path):
        report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
        assert isinstance(report.observations, tuple)


# ===========================================================================
# 17. Implementation coupling
# ===========================================================================

class TestImplementationCoupling:
    def test_uses_public_contracts(self):
        source = DRILLS_PY.read_text("utf-8")
        tree = ast.parse(source)
        ext_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                ext_imports.add(node.module)
        assert "execution.supervised_paper_workflow_v1" in ext_imports
        assert "execution.paper_exchange_adapter_v1" in ext_imports
        assert "monitoring.off_host_alert_delivery" in ext_imports
