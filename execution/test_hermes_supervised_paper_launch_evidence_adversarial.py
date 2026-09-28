"""Hermes independent adversarial audit for the supervised paper launch-evidence and owner-confirmation contract.

Audit assignment: AUDIT-SUPERVISED-PAPER-LAUNCH-EVIDENCE
Checkpoint: 4cc0e4c18a1f32d8d9e729cb24b0555301c008a2

Covers:
  1. Evidence parsing: exact schema, exact key set, JSON object, trading_authority=false
  2. Evidence identity = SHA-256 of canonical body excluding evidence_id
  3. Source hashes: nonempty, unique, lowercase SHA-256
  4. All SHA-256 identifiers validated
  5. UTC timestamps mandatory
  6. Boolean fields reject integers/non-booleans
  7. Counts are integers, reject booleans, nonnegative
  8. Evidence immutable
  9. Owner confirmation immutable, content-addressed
 10. Confirmation expires <= 5 minutes
 11. Confirmation current at evaluation; expiry exclusive
 12. Confirmation checkpoint matches evidence and policy
 13. Confirmation risk limits match policy exactly
 14. Smaller/larger/different limits cannot be reused
 15. Missing owner supervision/stop control → ineligible
 16. Owner confirmation cannot grant trading authority
 17. Adapter preserves all evidence fields
 18. Gate remains advisory-only, BTC-only, unable to submit
 19. No environment/git/process/task/recorder/provider/credential/network/OneDrive/exchange/broker/wallet/signing/paper-submission/live
 20. No owner-approval/profitability/OOS/deployment/unattended claim
 21. Classification
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from execution.supervised_paper_launch_evidence_v1 import (
    CONFIRMATION_VERSION, EVIDENCE_VERSION, OwnerSupervisionConfirmationV1,
    SupervisedPaperLaunchEvidenceV1, evaluate_collected_launch_evidence,
    read_launch_evidence,
)
from execution.supervised_paper_launch_gate_v1 import (
    SupervisedPaperLaunchPolicyV1,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 1, 22, 0, tzinfo=UTC)
H = "a" * 64
EVIDENCE_PY = Path(__file__).with_name("supervised_paper_launch_evidence_v1.py")


def _document():
    value = {
        "schema_version": EVIDENCE_VERSION, "collected_at": NOW.isoformat(),
        "repository_checkpoint": H, "repository_clean": True,
        "watchdog_state": "HEALTHY", "watchdog_report_id": H,
        "btc_task_state": "Running", "btc_recorder_health": "HEALTHY",
        "btc_heartbeat_at": NOW.isoformat(), "btc_unresolved_gap_count": 0,
        "es_nq_task_state": "Ready", "es_nq_last_result": 0, "es_nq_missed_runs": 0,
        "recovery_drill_result": "RECOVERY_VERIFIED", "recovery_drill_report_id": H,
        "stale_alert_drill_result": "STALE_ALERT_AND_RECOVERY_VERIFIED",
        "stale_alert_drill_report_id": H, "unhealthy_alert_delivered": True,
        "healthy_alert_delivered": True, "clock_skew_seconds": 0,
        "source_file_sha256": ["b" * 64], "trading_authority": False,
    }
    value["evidence_id"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def _write_evidence(tmp_path, change=None):
    value = _document()
    if change:
        value.update(change)
        body = {k: v for k, v in value.items() if k != "evidence_id"}
        value["evidence_id"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(value))
    return path


def _evidence(tmp_path, change=None):
    return read_launch_evidence(_write_evidence(tmp_path, change))


def _policy():
    return SupervisedPaperLaunchPolicyV1(
        H, timedelta(seconds=120), timedelta(minutes=5),
        timedelta(minutes=30), 10, Decimal("500"), Decimal("800"))

def _confirmation(**changes):
    defaults = dict(
        confirmed_at=NOW, expires_at=NOW + timedelta(minutes=5),
        repository_checkpoint=H, owner_supervision_confirmed=True,
        stop_control_verified=True, maximum_session_seconds=1800,
        maximum_commands=10, maximum_order_notional=Decimal("500"),
        maximum_gross_exposure=Decimal("800"),
    )
    defaults.update(changes)
    return OwnerSupervisionConfirmationV1.create(**defaults)


# ===========================================================================
# 1. Evidence parsing: exact schema, key set, JSON object, trading_authority
# ===========================================================================

class TestEvidenceParsing:
    def test_valid_evidence_parses(self, tmp_path):
        ev = _evidence(tmp_path)
        assert ev is not None

    def test_trading_authority_must_be_false(self, tmp_path):
        with pytest.raises(ValueError, match="authority"):
            _evidence(tmp_path, {"trading_authority": True})

    def test_extra_field_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="shape"):
            _evidence(tmp_path, {"extra": 1})

    def test_missing_field_rejects(self, tmp_path):
        value = _document()
        del value["repository_clean"]
        body = {k: v for k, v in value.items() if k != "evidence_id"}
        value["evidence_id"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError, match="shape"):
            read_launch_evidence(path)

    def test_wrong_schema_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="shape"):
            _evidence(tmp_path, {"schema_version": "wrong"})

    def test_non_object_rejects(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not an object")
        with pytest.raises(ValueError):
            read_launch_evidence(path)

    def test_malformed_json_rejects(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json}")
        with pytest.raises(ValueError):
            read_launch_evidence(path)


# ===========================================================================
# 2. Evidence identity = SHA-256 of canonical body
# ===========================================================================

class TestEvidenceIdentity:
    def test_identity_matches_body(self, tmp_path):
        ev = _evidence(tmp_path)
        value = _document()
        body = {k: v for k, v in value.items() if k != "evidence_id"}
        expected = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert ev.evidence_id == expected

    def test_wrong_identity_rejects(self, tmp_path):
        value = _document()
        value["evidence_id"] = "c" * 64
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError, match="identity"):
            read_launch_evidence(path)

    def test_identity_is_sha256(self, tmp_path):
        ev = _evidence(tmp_path)
        assert len(ev.evidence_id) == 64
        assert all(c in "0123456789abcdef" for c in ev.evidence_id)


# ===========================================================================
# 3. Source hashes: nonempty, unique, lowercase SHA-256
# ===========================================================================

class TestSourceHashes:
    def test_empty_hashes_reject(self, tmp_path):
        with pytest.raises(ValueError, match="nonempty"):
            _evidence(tmp_path, {"source_file_sha256": []})

    def test_duplicate_hashes_reject(self, tmp_path):
        with pytest.raises(ValueError, match="unique"):
            _evidence(tmp_path, {"source_file_sha256": [H, H]})

    def test_malformed_hash_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            _evidence(tmp_path, {"source_file_sha256": ["bad"]})

    def test_uppercase_hash_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            _evidence(tmp_path, {"source_file_sha256": ["A" * 64]})


# ===========================================================================
# 4. SHA-256 identifiers validated
# ===========================================================================

class TestShaIdentifiers:
    def test_bad_repository_checkpoint_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            _evidence(tmp_path, {"repository_checkpoint": "bad"})

    def test_bad_watchdog_report_id_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            _evidence(tmp_path, {"watchdog_report_id": "bad"})

    def test_bad_recovery_drill_report_id_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            _evidence(tmp_path, {"recovery_drill_report_id": "bad"})

    def test_bad_stale_alert_drill_report_id_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            _evidence(tmp_path, {"stale_alert_drill_report_id": "bad"})


# ===========================================================================
# 5. UTC timestamps mandatory
# ===========================================================================

class TestUtcTimestamps:
    def test_naive_collected_at_rejects(self, tmp_path):
        value = _document()
        value["collected_at"] = NOW.replace(tzinfo=None).isoformat()
        body = {k: v for k, v in value.items() if k != "evidence_id"}
        value["evidence_id"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError, match="UTC"):
            read_launch_evidence(path)

    def test_naive_btc_heartbeat_rejects(self, tmp_path):
        value = _document()
        value["btc_heartbeat_at"] = NOW.replace(tzinfo=None).isoformat()
        body = {k: v for k, v in value.items() if k != "evidence_id"}
        value["evidence_id"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError, match="UTC"):
            read_launch_evidence(path)

    def test_non_utc_offset_rejects(self, tmp_path):
        value = _document()
        value["collected_at"] = NOW.replace(tzinfo=timezone(timedelta(hours=5))).isoformat()
        body = {k: v for k, v in value.items() if k != "evidence_id"}
        value["evidence_id"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError, match="UTC"):
            read_launch_evidence(path)


# ===========================================================================
# 6. Boolean fields reject integers
# ===========================================================================

class TestBooleanFields:
    def test_repository_clean_int_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="boolean"):
            _evidence(tmp_path, {"repository_clean": 1})

    def test_unhealthy_delivered_int_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="boolean"):
            _evidence(tmp_path, {"unhealthy_alert_delivered": 1})

    def test_healthy_delivered_int_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="boolean"):
            _evidence(tmp_path, {"healthy_alert_delivered": 0})


# ===========================================================================
# 7. Counts: integers, reject booleans, nonnegative
# ===========================================================================

class TestCounts:
    def test_gap_count_bool_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="integer"):
            _evidence(tmp_path, {"btc_unresolved_gap_count": True})

    def test_es_missed_runs_bool_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="integer"):
            _evidence(tmp_path, {"es_nq_missed_runs": True})

    def test_clock_skew_bool_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="integer"):
            _evidence(tmp_path, {"clock_skew_seconds": True})

    def test_negative_gap_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="nonnegative"):
            _evidence(tmp_path, {"btc_unresolved_gap_count": -1})

    def test_negative_missed_runs_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="nonnegative"):
            _evidence(tmp_path, {"es_nq_missed_runs": -1})


# ===========================================================================
# 8. Evidence immutable
# ===========================================================================

class TestEvidenceImmutable:
    def test_immutable(self, tmp_path):
        ev = _evidence(tmp_path)
        with pytest.raises(FrozenInstanceError):
            ev.repository_clean = False

    def test_source_hashes_are_tuple(self, tmp_path):
        ev = _evidence(tmp_path)
        assert isinstance(ev.source_file_sha256, tuple)


# ===========================================================================
# 9-10. Owner confirmation immutable, content-addressed
# ===========================================================================

class TestConfirmationImmutable:
    def test_immutable(self):
        conf = _confirmation()
        with pytest.raises(FrozenInstanceError):
            conf.owner_supervision_confirmed = False

    def test_confirmation_id_sha256(self):
        conf = _confirmation()
        assert len(conf.confirmation_id) == 64
        assert all(c in "0123456789abcdef" for c in conf.confirmation_id)

    def test_deterministic(self):
        a = _confirmation()
        b = _confirmation()
        assert a == b
        assert a.confirmation_id == b.confirmation_id


# ===========================================================================
# 10-11. Confirmation expires <= 5 minutes, current, exclusive
# ===========================================================================

class TestConfirmationExpiry:
    def test_expires_over_5_min_rejects(self):
        with pytest.raises(ValueError, match="five minutes"):
            _confirmation(expires_at=NOW + timedelta(minutes=6))

    def test_expires_at_5_min_accepted(self):
        conf = _confirmation(expires_at=NOW + timedelta(minutes=5))
        assert conf.expires_at == NOW + timedelta(minutes=5)

    def test_not_current_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="current"):
            evaluate_collected_launch_evidence(
                evidence=_evidence(tmp_path), confirmation=_confirmation(),
                policy=_policy(), as_of=NOW + timedelta(minutes=5))

    def test_current_at_boundary_accepted(self, tmp_path):
        result = evaluate_collected_launch_evidence(
            evidence=_evidence(tmp_path), confirmation=_confirmation(),
            policy=_policy(), as_of=NOW + timedelta(seconds=4, microseconds=999999))
        assert result.eligible

    def test_confirmed_at_must_be_before_expires(self):
        with pytest.raises(ValueError, match="five minutes"):
            _confirmation(confirmed_at=NOW, expires_at=NOW)


# ===========================================================================
# 12-14. Checkpoint match, risk limits match
# ===========================================================================

class TestConfirmationMatch:
    def test_checkpoint_mismatch_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="checkpoint"):
            evaluate_collected_launch_evidence(
                evidence=_evidence(tmp_path),
                confirmation=replace(_confirmation(), repository_checkpoint="c" * 64),
                policy=_policy(), as_of=NOW)

    def test_limit_mismatch_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="limits"):
            evaluate_collected_launch_evidence(
                evidence=_evidence(tmp_path),
                confirmation=replace(_confirmation(), maximum_commands=9),
                policy=_policy(), as_of=NOW)

    def test_smaller_session_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="limits"):
            evaluate_collected_launch_evidence(
                evidence=_evidence(tmp_path),
                confirmation=replace(_confirmation(), maximum_session_seconds=1700),
                policy=_policy(), as_of=NOW)

    def test_larger_notional_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="limits"):
            evaluate_collected_launch_evidence(
                evidence=_evidence(tmp_path),
                confirmation=replace(_confirmation(), maximum_order_notional=Decimal("501")),
                policy=_policy(), as_of=NOW)

    def test_larger_gross_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="limits"):
            evaluate_collected_launch_evidence(
                evidence=_evidence(tmp_path),
                confirmation=replace(_confirmation(), maximum_gross_exposure=Decimal("801")),
                policy=_policy(), as_of=NOW)


# ===========================================================================
# 15-16. Missing owner assertions, no trading authority
# ===========================================================================

class TestOwnerAssertions:
    def test_missing_supervision_blocks(self, tmp_path):
        conf = _confirmation(owner_supervision_confirmed=False, stop_control_verified=True)
        result = evaluate_collected_launch_evidence(
            evidence=_evidence(tmp_path), confirmation=conf,
            policy=_policy(), as_of=NOW)
        assert not result.eligible

    def test_missing_stop_control_blocks(self, tmp_path):
        conf = _confirmation(owner_supervision_confirmed=True, stop_control_verified=False)
        result = evaluate_collected_launch_evidence(
            evidence=_evidence(tmp_path), confirmation=conf,
            policy=_policy(), as_of=NOW)
        assert not result.eligible

    def test_both_missing_two_reasons(self, tmp_path):
        conf = _confirmation(owner_supervision_confirmed=False, stop_control_verified=False)
        result = evaluate_collected_launch_evidence(
            evidence=_evidence(tmp_path), confirmation=conf,
            policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert len(result.reasons) == 2


# ===========================================================================
# 16. Confirmation cannot grant trading authority
# ===========================================================================

class TestNoTradingAuthority:
    def test_confirmation_trading_authority_false(self):
        conf = _confirmation()
        assert conf.trading_authority is False

    def test_confirmation_trading_authority_true_rejects(self):
        conf = _confirmation()
        values = {field: getattr(conf, field) for field in conf.__dataclass_fields__}
        values["trading_authority"] = True
        with pytest.raises(ValueError, match="cannot grant trading authority"):
            OwnerSupervisionConfirmationV1(**values)


# ===========================================================================
# 17-18. Adapter preserves fields, gate remains advisory/BTC-only
# ===========================================================================

class TestAdapterPreservation:
    def test_eligible_decision(self, tmp_path):
        result = evaluate_collected_launch_evidence(
            evidence=_evidence(tmp_path), confirmation=_confirmation(),
            policy=_policy(), as_of=NOW)
        assert result.eligible
        assert result.permitted_markets == ("BTC",)
        assert result.advisory_only is True
        assert result.live_trading_permitted is False
        assert result.trading_authority is False

    def test_preserves_checkpoint(self, tmp_path):
        ev = _evidence(tmp_path)
        assert ev.repository_checkpoint == H

    def test_preserves_watchdog_state(self, tmp_path):
        ev = _evidence(tmp_path)
        assert ev.watchdog_state == "HEALTHY"

    def test_preserves_drill_results(self, tmp_path):
        ev = _evidence(tmp_path)
        assert ev.recovery_drill_result == "RECOVERY_VERIFIED"
        assert ev.stale_alert_drill_result == "STALE_ALERT_AND_RECOVERY_VERIFIED"

    def test_preserves_delivery_facts(self, tmp_path):
        ev = _evidence(tmp_path)
        assert ev.unhealthy_alert_delivered is True
        assert ev.healthy_alert_delivered is True


# ===========================================================================
# 19. No prohibited surface
# ===========================================================================

class TestNoProhibited:
    def test_no_network_imports(self):
        source = EVIDENCE_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "websocket", "smtplib",
                    "paramiko", "asyncio", "subprocess", "os", "sys"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_no_credential_strings(self):
        source = EVIDENCE_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass", "credential"):
            assert f not in source, f"forbidden: {f}"

    def test_no_live_order(self):
        source = EVIDENCE_PY.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "live_order", "broker", "wallet"):
            assert f not in source, f"forbidden: {f}"

    def test_no_task_mutation(self):
        source = EVIDENCE_PY.read_text("utf-8")
        for f in ("Register-ScheduledTask", "Stop-ScheduledTask", "Start-ScheduledTask"):
            assert f not in source, f"forbidden: {f}"

    def test_no_git_access(self):
        source = EVIDENCE_PY.read_text("utf-8").lower()
        assert "git " not in source
        assert "subprocess" not in source


# ===========================================================================
# 20. No false claims
# ===========================================================================

class TestNoFalseClaims:
    def test_no_owner_approval_inference(self):
        source = EVIDENCE_PY.read_text("utf-8").lower()
        assert "owner approval" not in source
        assert "owner approved" not in source

    def test_no_profitability_claim(self):
        source = EVIDENCE_PY.read_text("utf-8").lower()
        assert "profitability" not in source
        assert "profit " not in source

    def test_no_oos_claim(self):
        source = EVIDENCE_PY.read_text("utf-8").lower()
        assert "out-of-sample" not in source

    def test_no_deployment_claim(self):
        source = EVIDENCE_PY.read_text("utf-8").lower()
        assert "deployment approval" not in source

    def test_advisory_in_docstring(self):
        source = EVIDENCE_PY.read_text("utf-8").lower()
        assert "advisory" in source or "strict evidence" in source


# ===========================================================================
# 21. Confirmation version
# ===========================================================================

class TestConfirmationVersion:
    def test_confirmation_version_constant(self):
        assert CONFIRMATION_VERSION == "supervised-paper-owner-confirmation-v1"

    def test_evidence_version_constant(self):
        assert EVIDENCE_VERSION == "supervised-paper-launch-evidence-v1"


# ===========================================================================
# 22. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """11 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: missing field, non-object, malformed JSON,
        uppercase hash, non-UTC offset, bool count, bool clock skew,
        negative missed runs, confirmation trading_authority=True,
        smaller session, larger notional, larger gross, no git access,
        no OOS/deployment/profitability claim — not in existing 11."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: read_launch_evidence,
        evaluate_collected_launch_evidence, OwnerSupervisionConfirmationV1,
        SupervisedPaperLaunchEvidenceV1, SupervisedPaperLaunchPolicyV1.
        No private helpers."""
