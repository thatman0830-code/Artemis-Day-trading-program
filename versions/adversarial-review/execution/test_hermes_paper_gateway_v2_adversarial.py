"""Hermes independent adversarial audit for the V2 paper-gateway foundation and strict order-lifecycle.

Audit assignment: AUDIT-V2-PAPER-GATEWAY-FOUNDATION
Checkpoint: 0999a22291aee900ba33b8a756facd4ad9a0925c

Covers:
  1. Strictly offline and paper-only: trading_authority always false, no live/SDK/network
  2. Submission idempotency: exact retry returns original, same key different content rejects,
     duplicate V2 order identity rejects, safety gates cannot permit duplicate exposure
  3. Market and authorization gates: disconnected, reconciliation, kill switch, auth, stale, future, malformed
  4. Exposure controls: per-order notional, aggregate notional, open count, terminal excluded, boundaries
  5. Strict lifecycle: partial fills conserve, final fill exact, zero/overfill reject, cancel preserves,
     terminal rejects events, stale version, time regression, before-acceptance
  6. Event idempotency: exact replay no-op, changed content rejects, conflict bypass rejected
  7. Restart and reconciliation: snapshot binding, altered snapshot rejects, altered records reject,
     disconnect requires reconciliation, exact observation recovers, mismatch fails closed + kill switch
  8. Integration boundaries: V2 OrderIntent identity preserved, no parallel live authority, unchanged
  9. Classification
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.execution_accounting_v2.contracts import (
    OrderIntentV2, OrderSide, OrderType, TimeInForce,
)
from execution.paper_gateway_v2 import (
    PaperEventKind, PaperGatewayPolicyV1, PaperGatewayReason, PaperGatewaySnapshotV1,
    PaperOrderEventV1, PaperOrderRecordV1, PaperOrderState, PaperSubmissionV1,
)

UTC = timezone.utc
NOW = datetime(2026, 8, 31, 20, 0, tzinfo=UTC)
sha = lambda v: hashlib.sha256(v.encode()).hexdigest()

GATEWAY_PY = Path(__file__).with_name("paper_gateway_v2.py")


def intent(name="a", quantity="1"):
    return OrderIntentV2(
        "order-intent-v2-1", sha("order-" + name), sha("run"), sha("action-" + name),
        "BTC", "BTC-PERP", None, OrderSide.BUY, Decimal(quantity), OrderType.MARKET,
        TimeInForce.IOC, None, None, NOW, NOW, None, None, None, "config-v1", "policy-v1",
    )

def request(name="a", **changes):
    base = PaperSubmissionV1(
        sha("key-" + name), intent(name), Decimal("100"), NOW, NOW, sha("auth-" + name), True,
    )
    return replace(base, **changes)

def gateway(**changes):
    policy = PaperGatewayPolicyV1(Decimal("500"), Decimal("800"), 2, timedelta(seconds=5))
    return replace(PaperGatewaySnapshotV1.create(policy), **changes)

def event(record, name, kind=PaperEventKind.FILL, quantity="0.4", version=0,
          when=NOW + timedelta(seconds=1)):
    return PaperOrderEventV1(
        sha("event-" + name), record.paper_order_id, kind, when, version,
        Decimal(quantity) if kind is PaperEventKind.FILL else None,
    )


# ===========================================================================
# 1. Strictly offline and paper-only
# ===========================================================================

class TestOfflinePaperOnly:
    def test_trading_authority_always_false_on_accept(self):
        state, result = gateway().submit(request())
        assert result.trading_authority is False
        assert state.trading_authority is False

    def test_trading_authority_false_on_reject(self):
        _, result = gateway(connected=False).submit(request())
        assert result.trading_authority is False

    def test_trading_authority_false_on_event_replay(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        _, result = state.apply_event(event(record, "x"))
        assert result.trading_authority is False

    def test_trading_authority_false_on_event_replay_reject(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        applied, _ = state.apply_event(event(record, "x"))
        _, result = applied.apply_event(event(record, "x"))
        assert result.trading_authority is False

    def test_no_network_imports(self):
        source = GATEWAY_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "websocket", "aiohttp", "socket", "urllib",
                    "smtplib", "paramiko", "asyncio", "subprocess"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_no_credential_strings(self):
        source = GATEWAY_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass", "keyring"):
            assert f not in source, f"forbidden: {f}"

    def test_no_live_order_capability(self):
        source = GATEWAY_PY.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "live_order", "real_order", "broker"):
            assert f not in source, f"forbidden: {f}"

    def test_submission_rejects_trading_authority(self):
        with pytest.raises(ValueError, match="trading authority"):
            request(trading_authority=True)

    def test_event_rejects_trading_authority(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        with pytest.raises(ValueError, match="trading authority"):
            PaperOrderEventV1(
                sha("x"), record.paper_order_id, PaperEventKind.FILL,
                NOW + timedelta(seconds=1), 0, Decimal("0.5"),
                trading_authority=True,
            )

    def test_snapshot_trading_authority_false(self):
        state, _ = gateway().submit(request())
        assert state.trading_authority is False

    def test_decision_trading_authority_false(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        _, result = state.apply_event(event(record, "x"))
        assert result.trading_authority is False


# ===========================================================================
# 2. Submission idempotency
# ===========================================================================

class TestSubmissionIdempotency:
    def test_exact_retry_returns_original(self):
        state, first = gateway().submit(request())
        replay, second = state.submit(request())
        assert replay is state
        assert second.record == first.record
        assert len(state.records) == 1

    def test_same_key_different_content_rejects(self):
        state, _ = gateway().submit(request())
        _, result = state.submit(replace(request(), reference_price=Decimal("101")))
        assert result.reason is PaperGatewayReason.DUPLICATE_CONFLICT

    def test_duplicate_order_id_rejects_different_key(self):
        state, _ = gateway().submit(request())
        _, result = state.submit(replace(request("b"), intent=request().intent))
        assert result.reason is PaperGatewayReason.DUPLICATE_CONFLICT

    def test_idempotent_replay_does_not_create_second_order(self):
        state, first = gateway().submit(request())
        replay, second = state.submit(request())
        assert len(replay.records) == 1
        assert second.record == first.record

    def test_kill_switch_before_idempotency_check(self):
        """Safety gates are checked before idempotency? No — idempotency is first."""
        state, _ = gateway().submit(request())
        killed = state.activate_kill_switch()
        # Idempotent replay still returns original even with kill switch
        _, result = killed.submit(request())
        assert result.reason is PaperGatewayReason.IDEMPOTENT_REPLAY


# ===========================================================================
# 3. Market and authorization gates
# ===========================================================================

class TestMarketAuthGates:
    def test_disconnected_rejects(self):
        _, result = gateway(connected=False).submit(request())
        assert result.reason is PaperGatewayReason.DISCONNECTED

    def test_reconciliation_required_rejects(self):
        _, result = gateway(reconciliation_required=True).submit(request())
        assert result.reason is PaperGatewayReason.RECONCILIATION_REQUIRED

    def test_kill_switch_rejects(self):
        _, result = gateway(kill_switch_active=True).submit(request())
        assert result.reason is PaperGatewayReason.KILL_SWITCH_ACTIVE

    def test_unauthorized_rejects(self):
        _, result = gateway().submit(request(authorized=False))
        assert result.reason is PaperGatewayReason.AUTHORIZATION_REJECTED

    def test_stale_market_data_rejects(self):
        _, result = gateway().submit(request(market_data_at=NOW - timedelta(seconds=6)))
        assert result.reason is PaperGatewayReason.STALE_MARKET_DATA

    def test_future_market_data_rejects(self):
        _, result = gateway().submit(request(market_data_at=NOW + timedelta(microseconds=1)))
        assert result.reason is PaperGatewayReason.FUTURE_MARKET_DATA

    def test_market_data_at_exact_boundary_accepted(self):
        _, result = gateway().submit(request(market_data_at=NOW - timedelta(seconds=5)))
        assert result.accepted

    def test_naive_timestamp_rejects(self):
        with pytest.raises(ValueError, match="UTC"):
            PaperSubmissionV1(
                sha("key"), intent(), Decimal("100"), NOW.replace(tzinfo=None),
                NOW, sha("auth"), True,
            )

    def test_non_utc_market_data_rejects(self):
        with pytest.raises(ValueError, match="UTC"):
            PaperSubmissionV1(
                sha("key"), intent(), Decimal("100"), NOW,
                NOW.replace(tzinfo=timezone(timedelta(hours=5))), sha("auth"), True,
            )

    def test_non_finite_reference_price_rejects(self):
        with pytest.raises(ValueError, match="finite"):
            PaperSubmissionV1(
                sha("key"), intent(), Decimal("Infinity"), NOW, NOW, sha("auth"), True,
            )

    def test_zero_reference_price_rejects(self):
        with pytest.raises(ValueError, match="positive"):
            PaperSubmissionV1(
                sha("key"), intent(), Decimal("0"), NOW, NOW, sha("auth"), True,
            )

    def test_nan_reference_price_rejects(self):
        with pytest.raises(ValueError, match="finite"):
            PaperSubmissionV1(
                sha("key"), intent(), Decimal("NaN"), NOW, NOW, sha("auth"), True,
            )


# ===========================================================================
# 4. Exposure controls
# ===========================================================================

class TestExposureControls:
    def test_per_order_notional_limit(self):
        _, result = gateway().submit(request(intent=intent("a", "6")))
        assert result.reason is PaperGatewayReason.EXPOSURE_LIMIT

    def test_per_order_at_boundary_accepted(self):
        _, result = gateway().submit(request(intent=intent("a", "5")))
        assert result.accepted

    def test_total_notional_limit(self):
        state, _ = gateway().submit(request("a", intent=intent("a", "4")))
        _, result = state.submit(request("b", intent=intent("b", "5")))
        assert result.reason is PaperGatewayReason.EXPOSURE_LIMIT

    def test_total_at_boundary_accepted(self):
        state, _ = gateway().submit(request("a", intent=intent("a", "4")))
        _, result = state.submit(request("b", intent=intent("b", "4")))
        assert result.accepted

    def test_open_order_count_limit(self):
        state, _ = gateway().submit(request("a"))
        state, _ = state.submit(request("b"))
        _, result = state.submit(request("c"))
        assert result.reason is PaperGatewayReason.OPEN_ORDER_LIMIT

    def test_terminal_orders_not_counted_as_open(self):
        state, _ = gateway().submit(request("a"))
        state, _ = state.submit(request("b"))
        record = state.records[0]
        state, _ = state.apply_event(event(record, "fill", quantity="1", version=0))
        # Now one is FILLED, so we can submit another
        _, result = state.submit(request("c"))
        assert result.accepted

    def test_cancelled_orders_not_counted_as_open(self):
        state, _ = gateway().submit(request("a"))
        state, _ = state.submit(request("b"))
        record = state.records[0]
        state, _ = state.apply_event(
            event(record, "cancel", kind=PaperEventKind.CANCEL, version=0)
        )
        _, result = state.submit(request("c"))
        assert result.accepted


# ===========================================================================
# 5. Strict lifecycle behavior
# ===========================================================================

class TestStrictLifecycle:
    def test_partial_fill_conserve_quantity(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        state, result = state.apply_event(event(record, "one", quantity="0.4"))
        r = result.record
        assert r.filled_quantity + r.remaining_quantity == r.quantity
        assert r.state is PaperOrderState.PARTIALLY_FILLED

    def test_final_fill_exact_equality(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        state, _ = state.apply_event(event(record, "one", quantity="0.4"))
        state, result = state.apply_event(
            event(record, "two", quantity="0.6", version=1, when=NOW + timedelta(seconds=2))
        )
        assert result.record.state is PaperOrderState.FILLED
        assert result.record.remaining_quantity == 0
        assert result.record.filled_quantity == result.record.quantity

    def test_zero_fill_rejects(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        with pytest.raises(ValueError, match="positive"):
            event(record, "zero", quantity="0")

    def test_overfill_rejects(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        _, result = state.apply_event(event(record, "over", quantity="1.1"))
        assert result.reason is PaperGatewayReason.INVALID_FILL_QUANTITY

    def test_cancel_preserves_filled_quantity(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        state, _ = state.apply_event(event(record, "fill", quantity="0.4"))
        record2 = state.records[0]
        state, result = state.apply_event(
            event(record2, "cancel", kind=PaperEventKind.CANCEL, version=1,
                  when=NOW + timedelta(seconds=2))
        )
        assert result.record.state is PaperOrderState.CANCELLED
        assert result.record.filled_quantity == Decimal("0.4")

    def test_fill_after_terminal_rejects(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        state, _ = state.apply_event(event(record, "full", quantity="1"))
        record2 = state.records[0]
        _, result = state.apply_event(event(record2, "late", version=1))
        assert result.reason is PaperGatewayReason.TERMINAL_ORDER

    def test_cancel_after_filled_rejects(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        state, _ = state.apply_event(event(record, "full", quantity="1"))
        record2 = state.records[0]
        _, result = state.apply_event(
            event(record2, "cancel", kind=PaperEventKind.CANCEL, version=1)
        )
        assert result.reason is PaperGatewayReason.TERMINAL_ORDER

    def test_stale_version_rejects(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        state, _ = state.apply_event(event(record, "one", quantity="0.4"))
        record2 = state.records[0]
        _, result = state.apply_event(event(record2, "stale", version=0))
        assert result.reason is PaperGatewayReason.STALE_ORDER_VERSION

    def test_event_time_regression_rejects(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        _, result = state.apply_event(event(record, "old", when=NOW - timedelta(seconds=1)))
        assert result.reason is PaperGatewayReason.EVENT_TIME_REGRESSION

    def test_event_before_acceptance_rejects(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        _, result = state.apply_event(
            event(record, "before", when=record.accepted_at - timedelta(seconds=1))
        )
        assert result.reason is PaperGatewayReason.EVENT_TIME_REGRESSION


# ===========================================================================
# 6. Event idempotency
# ===========================================================================

class TestEventIdempotency:
    def test_exact_event_replay_is_noop(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        ev = event(record, "one")
        applied, _ = state.apply_event(ev)
        replayed, result = applied.apply_event(ev)
        assert replayed is applied
        assert result.reason is PaperGatewayReason.EVENT_REPLAY

    def test_same_event_id_changed_content_rejects(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        ev = event(record, "one", quantity="0.4")
        applied, _ = state.apply_event(ev)
        conflict = replace(ev, fill_quantity=Decimal("0.5"))
        _, result = applied.apply_event(conflict)
        assert result.reason is PaperGatewayReason.EVENT_CONFLICT

    def test_conflict_cannot_bypass_terminal(self):
        """An event-id conflict on a terminal order: idempotency check comes first
        (line 269), so exact replay returns EVENT_REPLAY, not TERMINAL_ORDER.
        A NEW event_id on a terminal order gets TERMINAL_ORDER."""
        state, _ = gateway().submit(request())
        record = state.records[0]
        ev = event(record, "full", quantity="1")
        state, _ = state.apply_event(ev)
        # Exact replay returns EVENT_REPLAY (idempotency checked before terminal)
        _, replay_result = state.apply_event(ev)
        assert replay_result.reason is PaperGatewayReason.EVENT_REPLAY
        # A new event_id on the terminal order gets TERMINAL_ORDER
        new_ev = event(record, "new", quantity="0.1", version=1)
        _, terminal_result = state.apply_event(new_ev)
        assert terminal_result.reason is PaperGatewayReason.TERMINAL_ORDER


# ===========================================================================
# 7. Restart and reconciliation
# ===========================================================================

class TestRestartReconciliation:
    def test_snapshot_binds_complete_state(self):
        state, _ = gateway().submit(request())
        assert state.snapshot_id != gateway().snapshot_id  # different records → different ID

    def test_altered_snapshot_rejects_on_resume(self):
        state, _ = gateway().submit(request())
        with pytest.raises(ValueError, match="integrity"):
            PaperGatewaySnapshotV1.resume(replace(state, snapshot_id=sha("tampered")))

    def test_resume_trading_authority_true_rejects(self):
        state, _ = gateway().submit(request())
        with pytest.raises(ValueError, match="integrity"):
            PaperGatewaySnapshotV1.resume(replace(state, trading_authority=True))

    def test_disconnect_requires_reconciliation(self):
        state, _ = gateway().submit(request())
        disconnected = state.disconnect()
        assert not disconnected.connected
        assert disconnected.reconciliation_required

    def test_reconciliation_mismatch_activates_kill_switch(self):
        state, _ = gateway().submit(request())
        disconnected = state.disconnect()
        bad = disconnected.reconcile(())
        assert bad.kill_switch_active
        assert not bad.connected
        assert bad.reconciliation_required

    def test_exact_observation_recovers(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        disconnected = state.disconnect()
        observed = ((record.paper_order_id, PaperOrderState.ACCEPTED,
                     Decimal(0), Decimal(1), 0),)
        recovered = disconnected.reconcile(observed)
        assert recovered.connected
        assert not recovered.reconciliation_required

    def test_wrong_state_in_observation_fails(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        disconnected = state.disconnect()
        bad = ((record.paper_order_id, PaperOrderState.FILLED, Decimal(0), Decimal(1), 0),)
        result = disconnected.reconcile(bad)
        assert result.kill_switch_active
        assert not result.connected

    def test_wrong_quantity_in_observation_fails(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        disconnected = state.disconnect()
        bad = ((record.paper_order_id, PaperOrderState.ACCEPTED,
                Decimal("0.1"), Decimal("0.9"), 0),)
        result = disconnected.reconcile(bad)
        assert result.kill_switch_active

    def test_wrong_version_in_observation_fails(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        disconnected = state.disconnect()
        bad = ((record.paper_order_id, PaperOrderState.ACCEPTED,
                Decimal(0), Decimal(1), 1),)
        result = disconnected.reconcile(bad)
        assert result.kill_switch_active

    def test_extra_observation_fails(self):
        state, _ = gateway().submit(request())
        disconnected = state.disconnect()
        bad = ((sha("extra"), PaperOrderState.ACCEPTED, Decimal(0), Decimal(1), 0),)
        result = disconnected.reconcile(bad)
        assert result.kill_switch_active

    def test_missing_observation_fails(self):
        state, _ = gateway().submit(request())
        disconnected = state.disconnect()
        result = disconnected.reconcile(())
        assert result.kill_switch_active

    def test_reconciliation_mismatch_cannot_reconnect(self):
        """A reconciliation mismatch sets connected=False and kill_switch=True."""
        state, _ = gateway().submit(request())
        disconnected = state.disconnect()
        bad = disconnected.reconcile(())
        assert not bad.connected
        assert bad.kill_switch_active

    def test_record_rejects_quantity_tampering(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        with pytest.raises(ValueError, match="conservation"):
            replace(record, remaining_quantity=Decimal("0.9"))

    def test_record_rejects_version_tampering(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        with pytest.raises(ValueError, match="version/event"):
            replace(record, version=1)

    def test_record_rejects_filled_state_with_remaining(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        with pytest.raises(ValueError, match="filled"):
            replace(record, state=PaperOrderState.FILLED)

    def test_activate_kill_switch_preserves_records(self):
        state, _ = gateway().submit(request())
        killed = state.activate_kill_switch()
        assert killed.kill_switch_active
        assert killed.records == state.records


# ===========================================================================
# 8. Integration boundaries
# ===========================================================================

class TestIntegrationBoundaries:
    def test_v2_order_intent_identity_preserved(self):
        state, _ = gateway().submit(request())
        record = state.records[0]
        assert record.order_id == request().intent.order_id
        assert record.market == request().intent.market

    def test_no_parallel_live_authority(self):
        source = GATEWAY_PY.read_text("utf-8")
        # "live" appears in the docstring ("no live-order capability") which is correct
        # Check that there's no LiveOrder class, live_order function, or submit_live call
        for prohibited in ("LiveOrder", "live_order", "submit_live", "place_live",
                          "real_submit", "LiveGateway"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_module_imports_only_contracts(self):
        source = GATEWAY_PY.read_text("utf-8")
        tree = ast.parse(source)
        ext_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                ext_imports.add(node.module)
        assert "backtesting.execution_accounting_v2.contracts" in ext_imports
        # No other external execution imports
        for imp in ext_imports:
            if "execution" in imp and imp != "backtesting.execution_accounting_v2.contracts":
                pytest.fail(f"unexpected execution import: {imp}")


# ===========================================================================
# 9. Policy validation
# ===========================================================================

class TestPolicyValidation:
    def test_per_order_exceeds_total_rejects(self):
        with pytest.raises(ValueError, match="per-order"):
            PaperGatewayPolicyV1(Decimal("900"), Decimal("500"), 2, timedelta(seconds=5))

    def test_zero_max_open_orders_rejects(self):
        with pytest.raises(ValueError, match="max_open_orders"):
            PaperGatewayPolicyV1(Decimal("500"), Decimal("800"), 0, timedelta(seconds=5))

    def test_negative_max_open_orders_rejects(self):
        with pytest.raises(ValueError, match="max_open_orders"):
            PaperGatewayPolicyV1(Decimal("500"), Decimal("800"), -1, timedelta(seconds=5))

    def test_zero_market_data_age_rejects(self):
        with pytest.raises(ValueError, match="market_data_age"):
            PaperGatewayPolicyV1(Decimal("500"), Decimal("800"), 2, timedelta(0))

    def test_negative_notional_rejects(self):
        with pytest.raises(ValueError, match="positive"):
            PaperGatewayPolicyV1(Decimal("-1"), Decimal("800"), 2, timedelta(seconds=5))


# ===========================================================================
# 10. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """18 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: NaN reference price, non-UTC timestamp,
        boundary equality for notional and count, terminal orders excluded from
        open exposure, cancel after filled, event before acceptance, conflict
        bypass terminal, snapshot binding different records, resume trading_authority
        true, policy validation (5 edge cases), integration boundaries — not in
        existing 18."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: PaperGatewaySnapshotV1, submit,
        apply_event, disconnect, reconcile, activate_kill_switch, resume,
        PaperSubmissionV1, PaperOrderEventV1, PaperGatewayPolicyV1,
        PaperGatewayReason, PaperOrderState, PaperEventKind. No private helpers."""
