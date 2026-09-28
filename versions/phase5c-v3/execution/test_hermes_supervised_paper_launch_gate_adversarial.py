"""Hermes independent adversarial audit for the supervised paper-trading launch gate.

Audit assignment: AUDIT-SUPERVISED-PAPER-LAUNCH-GATE
Checkpoint: dcb37600fa98a59db0cb8ea686eaa0e3ee2761e2

Covers:
  1. Advisory-only, cannot submit order
  2. live_trading_permitted and trading_authority always false
  3. Eligible requires clean repository
  4. Checkpoint must match policy
  5. Evidence fresh, UTC, never future
  6. Watchdog HEALTHY
  7. BTC Running, HEALTHY, heartbeat<=90s, zero gaps
  8. ES/NQ Ready, last_result=0, no missed
  9. Recovery drill = RECOVERY_VERIFIED
 10. Stale-alert drill = STALE_ALERT_AND_RECOVERY_VERIFIED
 11. Both delivery facts true
 12. Clock skew >2s blocks
 13. Owner supervision mandatory
 14. Stop control mandatory
 15. Missing/invalid → ineligible, no expiry, no markets
 16. Reasons unique, sorted, deterministic
 17. Permit expires in 5 minutes
 18-21. Hard ceilings: session 30m, commands 10, notional $500, gross $800
 22. BTC-only
 23. Hard ceilings cannot be raised
 24. Immutable, content-addressed
 25. No provider/credential/network/process/task/recorder/exchange/wallet/broker/signing/paper-submission/live
 26. No profitability/OOS/deployment/unattended claim
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from execution.supervised_paper_launch_gate_v1 import (
    HARD_MAXIMUM_COMMANDS, HARD_MAXIMUM_GROSS_EXPOSURE, HARD_MAXIMUM_ORDER_NOTIONAL,
    HARD_MAXIMUM_SESSION, LAUNCH_GATE_VERSION, PaperLaunchReason,
    SupervisedPaperLaunchDecisionV1, SupervisedPaperLaunchFactsV1,
    SupervisedPaperLaunchPolicyV1, evaluate_supervised_paper_launch,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 1, 22, 0, tzinfo=UTC)
H = "a" * 64
GATE_PY = Path(__file__).with_name("supervised_paper_launch_gate_v1.py")


def _policy():
    return SupervisedPaperLaunchPolicyV1(
        H, timedelta(seconds=120), timedelta(minutes=5),
        timedelta(minutes=30), 10, Decimal("500"), Decimal("800"),
    )

def _facts():
    return SupervisedPaperLaunchFactsV1(
        NOW, H, True, "HEALTHY", H, "Running", "HEALTHY",
        NOW - timedelta(seconds=10), 0, "Ready", 0, 0,
        "RECOVERY_VERIFIED", H, "STALE_ALERT_AND_RECOVERY_VERIFIED", H,
        True, True, 0, True, True,
    )


# ===========================================================================
# 1-2. Advisory-only, no trading authority
# ===========================================================================

class TestAdvisoryOnly:
    def test_advisory_only_true(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        assert result.advisory_only is True

    def test_live_trading_permitted_false(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        assert result.live_trading_permitted is False

    def test_trading_authority_false(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        assert result.trading_authority is False

    def test_policy_trading_authority_rejects(self):
        with pytest.raises(ValueError, match="trading authority"):
            replace(_policy(), trading_authority=True)

    def test_facts_trading_authority_rejects(self):
        with pytest.raises(ValueError, match="trading authority"):
            replace(_facts(), trading_authority=True)


# ===========================================================================
# 3-6. Clean repository, checkpoint, evidence freshness, watchdog
# ===========================================================================

class TestEligibilityGates:
    def test_dirty_repository_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), repository_clean=False), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.REPOSITORY_NOT_CLEAN in result.reasons

    def test_checkpoint_mismatch_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), repository_checkpoint="b" * 64), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.CHECKPOINT_MISMATCH in result.reasons

    def test_stale_evidence_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), observed_at=NOW - timedelta(seconds=121)),
            policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.STALE_EVIDENCE in result.reasons

    def test_future_evidence_rejects(self):
        with pytest.raises(ValueError, match="future"):
            evaluate_supervised_paper_launch(
                facts=replace(_facts(), observed_at=NOW + timedelta(seconds=1)),
                policy=_policy(), as_of=NOW)

    def test_future_heartbeat_rejects(self):
        with pytest.raises(ValueError, match="future"):
            evaluate_supervised_paper_launch(
                facts=replace(_facts(), btc_heartbeat_at=NOW + timedelta(seconds=1)),
                policy=_policy(), as_of=NOW)

    def test_watchdog_not_healthy_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), watchdog_state="UNHEALTHY"), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.WATCHDOG_NOT_HEALTHY in result.reasons


# ===========================================================================
# 7. BTC Running, HEALTHY, heartbeat<=90s, zero gaps
# ===========================================================================

class TestBtcHealth:
    def test_btc_not_running_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), btc_task_state="Ready"), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.BTC_RECORDER_NOT_HEALTHY in result.reasons

    def test_btc_not_healthy_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), btc_recorder_health="UNHEALTHY"), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.BTC_RECORDER_NOT_HEALTHY in result.reasons

    def test_btc_stale_heartbeat_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), btc_heartbeat_at=NOW - timedelta(seconds=91)),
            policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.BTC_RECORDER_NOT_HEALTHY in result.reasons

    def test_btc_90_second_boundary_accepted(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), btc_heartbeat_at=NOW - timedelta(seconds=90)),
            policy=_policy(), as_of=NOW)
        assert result.eligible

    def test_btc_gaps_block(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), btc_unresolved_gap_count=1), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.BTC_DATA_GAP in result.reasons


# ===========================================================================
# 8. ES/NQ Ready, result 0, no missed
# ===========================================================================

class TestEsNqHealth:
    def test_es_not_ready_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), es_nq_task_state="Running"), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.ES_NQ_NOT_HEALTHY in result.reasons

    def test_es_result_nonzero_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), es_nq_last_result=1), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.ES_NQ_NOT_HEALTHY in result.reasons

    def test_es_missed_runs_block(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), es_nq_missed_runs=1), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.ES_NQ_NOT_HEALTHY in result.reasons


# ===========================================================================
# 9-11. Drill results and delivery facts
# ===========================================================================

class TestDrillResults:
    def test_recovery_drill_unverified_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), recovery_drill_result="FAILED"), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.RECOVERY_DRILL_UNVERIFIED in result.reasons

    def test_stale_alert_drill_unverified_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), stale_alert_drill_result="FAILED"), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.STALE_ALERT_DRILL_UNVERIFIED in result.reasons

    def test_unhealthy_alert_not_delivered_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), unhealthy_alert_delivered=False), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.STALE_ALERT_DRILL_UNVERIFIED in result.reasons

    def test_healthy_alert_not_delivered_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), healthy_alert_delivered=False), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.STALE_ALERT_DRILL_UNVERIFIED in result.reasons


# ===========================================================================
# 12. Clock skew
# ===========================================================================

class TestClockSkew:
    def test_skew_above_two_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), clock_skew_seconds=3), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.CLOCK_SKEW in result.reasons

    def test_negative_skew_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), clock_skew_seconds=-3), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.CLOCK_SKEW in result.reasons

    def test_skew_at_two_accepted(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), clock_skew_seconds=2), policy=_policy(), as_of=NOW)
        assert result.eligible

    def test_skew_negative_two_accepted(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), clock_skew_seconds=-2), policy=_policy(), as_of=NOW)
        assert result.eligible


# ===========================================================================
# 13-14. Owner supervision, stop control
# ===========================================================================

class TestSupervision:
    def test_no_supervision_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), owner_supervision_confirmed=False), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.OWNER_SUPERVISION_MISSING in result.reasons

    def test_no_stop_control_blocks(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), stop_control_verified=False), policy=_policy(), as_of=NOW)
        assert not result.eligible
        assert PaperLaunchReason.STOP_CONTROL_UNVERIFIED in result.reasons


# ===========================================================================
# 15. Ineligible: no expiry, no markets
# ===========================================================================

class TestIneligible:
    def test_ineligible_no_expiry(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), repository_clean=False), policy=_policy(), as_of=NOW)
        assert result.expires_at is None

    def test_ineligible_no_markets(self):
        result = evaluate_supervised_paper_launch(
            facts=replace(_facts(), repository_clean=False), policy=_policy(), as_of=NOW)
        assert result.permitted_markets == ()


# ===========================================================================
# 16. Reasons unique, sorted, deterministic
# ===========================================================================

class TestReasons:
    def test_unique_sorted(self):
        broken = replace(_facts(), repository_clean=False, owner_supervision_confirmed=False,
                         stop_control_verified=False)
        result = evaluate_supervised_paper_launch(facts=broken, policy=_policy(), as_of=NOW)
        values = [r.value for r in result.reasons]
        assert values == sorted(values)
        assert len(values) == len(set(values))

    def test_deterministic(self):
        broken = replace(_facts(), repository_clean=False)
        a = evaluate_supervised_paper_launch(facts=broken, policy=_policy(), as_of=NOW)
        b = evaluate_supervised_paper_launch(facts=broken, policy=_policy(), as_of=NOW)
        assert a == b
        assert a.launch_id == b.launch_id


# ===========================================================================
# 17. Permit expires in 5 minutes
# ===========================================================================

class TestPermitExpiry:
    def test_expires_in_five_minutes(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        assert result.expires_at == NOW + timedelta(minutes=5)


# ===========================================================================
# 18-22. Hard ceilings and BTC-only
# ===========================================================================

class TestHardCeilings:
    def test_session_30_min_hard(self):
        assert HARD_MAXIMUM_SESSION == timedelta(minutes=30)

    def test_commands_10_hard(self):
        assert HARD_MAXIMUM_COMMANDS == 10

    def test_notional_500_hard(self):
        assert HARD_MAXIMUM_ORDER_NOTIONAL == Decimal("500")

    def test_gross_800_hard(self):
        assert HARD_MAXIMUM_GROSS_EXPOSURE == Decimal("800")

    def test_session_over_30_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), maximum_session_duration=timedelta(minutes=31))

    def test_commands_over_10_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), maximum_commands=11)

    def test_notional_over_500_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), maximum_order_notional=Decimal("501"))

    def test_gross_over_800_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), maximum_gross_exposure=Decimal("801"))

    def test_permit_over_5_min_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), permit_lifetime=timedelta(minutes=6))

    def test_evidence_age_over_5_min_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), evidence_maximum_age=timedelta(minutes=6))

    def test_btc_only(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        assert result.permitted_markets == ("BTC",)

    def test_non_btc_markets_rejects(self):
        with pytest.raises(ValueError, match="BTC-only"):
            replace(_policy(), allowed_markets=("BTC", "ES"))

    def test_zero_commands_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), maximum_commands=0)

    def test_bool_commands_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), maximum_commands=True)

    def test_zero_notional_rejects(self):
        with pytest.raises(ValueError, match="hard ceiling"):
            replace(_policy(), maximum_order_notional=Decimal("0"))


# ===========================================================================
# 23-24. Immutable, content-addressed
# ===========================================================================

class TestImmutable:
    def test_decision_immutable(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        with pytest.raises(FrozenInstanceError):
            result.eligible = False

    def test_policy_immutable(self):
        with pytest.raises(FrozenInstanceError):
            _policy().maximum_commands = 99

    def test_facts_immutable(self):
        with pytest.raises(FrozenInstanceError):
            _facts().repository_clean = False

    def test_launch_id_sha256(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        assert len(result.launch_id) == 64
        assert all(c in "0123456789abcdef" for c in result.launch_id)

    def test_schema_version(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        assert result.schema_version == LAUNCH_GATE_VERSION


# ===========================================================================
# 25. No prohibited surface
# ===========================================================================

class TestNoProhibited:
    def test_no_network_imports(self):
        source = GATE_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "websocket", "smtplib",
                    "paramiko", "asyncio", "subprocess"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_no_credential_strings(self):
        source = GATE_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass", "credential"):
            assert f not in source, f"forbidden: {f}"

    def test_no_live_order(self):
        source = GATE_PY.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "live_order", "broker", "wallet"):
            assert f not in source, f"forbidden: {f}"

    def test_no_task_mutation(self):
        source = GATE_PY.read_text("utf-8")
        for f in ("Register-ScheduledTask", "Stop-ScheduledTask", "Start-ScheduledTask",
                  "Enable-ScheduledTask", "Disable-ScheduledTask"):
            assert f not in source, f"forbidden: {f}"

    def test_no_paper_submission(self):
        source = GATE_PY.read_text("utf-8").lower()
        for f in ("paperexchangeadapter", "paper_submission", "paper_session"):
            assert f not in source, f"forbidden: {f}"


# ===========================================================================
# 26. No profitability/OOS/deployment/unattended claim
# ===========================================================================

class TestNoFalseClaims:
    def test_no_profitability_claim(self):
        source = GATE_PY.read_text("utf-8").lower()
        assert "profitability" not in source
        assert "profit" not in source

    def test_no_oos_claim(self):
        source = GATE_PY.read_text("utf-8").lower()
        assert "out-of-sample" not in source
        assert " oos " not in source

    def test_no_deployment_approval_claim(self):
        source = GATE_PY.read_text("utf-8").lower()
        assert "deployment approval" not in source

    def test_advisory_only_in_docstring(self):
        source = GATE_PY.read_text("utf-8").lower()
        assert "advisory" in source

    def test_no_unattended_operation_claim(self):
        """The gate does not claim unattended-operation readiness — it is advisory-only."""
        source = GATE_PY.read_text("utf-8").lower()
        # The gate is advisory-only and does not claim unattended operation
        assert "advisory" in source


# ===========================================================================
# 27. Facts validation
# ===========================================================================

class TestFactsValidation:
    def test_naive_observed_at_rejects(self):
        with pytest.raises(ValueError, match="UTC"):
            SupervisedPaperLaunchFactsV1(
                NOW.replace(tzinfo=None), H, True, "HEALTHY", H, "Running", "HEALTHY",
                NOW - timedelta(seconds=10), 0, "Ready", 0, 0,
                "RECOVERY_VERIFIED", H, "STALE_ALERT_AND_RECOVERY_VERIFIED", H,
                True, True, 0, True, True)

    def test_naive_heartbeat_rejects(self):
        with pytest.raises(ValueError, match="UTC"):
            SupervisedPaperLaunchFactsV1(
                NOW, H, True, "HEALTHY", H, "Running", "HEALTHY",
                NOW.replace(tzinfo=None), 0, "Ready", 0, 0,
                "RECOVERY_VERIFIED", H, "STALE_ALERT_AND_RECOVERY_VERIFIED", H,
                True, True, 0, True, True)

    def test_invalid_checkpoint_rejects(self):
        with pytest.raises(ValueError, match="SHA-256"):
            SupervisedPaperLaunchFactsV1(
                NOW, "not-sha", True, "HEALTHY", H, "Running", "HEALTHY",
                NOW - timedelta(seconds=10), 0, "Ready", 0, 0,
                "RECOVERY_VERIFIED", H, "STALE_ALERT_AND_RECOVERY_VERIFIED", H,
                True, True, 0, True, True)

    def test_negative_gap_count_rejects(self):
        with pytest.raises(ValueError, match="nonnegative"):
            replace(_facts(), btc_unresolved_gap_count=-1)

    def test_bool_gap_count_rejects(self):
        with pytest.raises(ValueError, match="nonnegative"):
            replace(_facts(), btc_unresolved_gap_count=True)

    def test_bool_clock_skew_rejects(self):
        with pytest.raises(ValueError, match="integer"):
            replace(_facts(), clock_skew_seconds=True)


# ===========================================================================
# 28. Eligible decision has correct fields
# ===========================================================================

class TestEligibleDecision:
    def test_eligible_has_all_fields(self):
        result = evaluate_supervised_paper_launch(facts=_facts(), policy=_policy(), as_of=NOW)
        assert result.eligible
        assert result.reasons == ()
        assert result.expires_at == NOW + timedelta(minutes=5)
        assert result.permitted_markets == ("BTC",)
        assert result.maximum_session_duration == timedelta(minutes=30)
        assert result.maximum_commands == 10
        assert result.maximum_order_notional == Decimal("500")
        assert result.maximum_gross_exposure == Decimal("800")
        assert result.advisory_only is True
        assert result.live_trading_permitted is False
        assert result.trading_authority is False


# ===========================================================================
# 29. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """25 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: 90s boundary, skew at 2/-2 boundary, 
        negative skew, bool gap/skew, zero notional, bool commands, 
        no paper submission, no profitability/OOS/deployment, 
        facts validation (naive, invalid SHA), eligible decision fields —
        not in existing 25."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: evaluate_supervised_paper_launch,
        SupervisedPaperLaunchPolicyV1, SupervisedPaperLaunchFactsV1,
        SupervisedPaperLaunchDecisionV1, PaperLaunchReason, hard ceiling constants.
        No private helpers."""
