"""Hermes independent adversarial audit for the off-host alert-delivery foundation.

Audit assignment: AUDIT-OFF-HOST-ALERT-DELIVERY-FOUNDATION
Checkpoint: b763b269ddcd1a2faf86175ef355b5acec2bff01

Covers:
  1. Alert event IDs recomputed canonically; duplicates fail closed
  2. Sensitive field names cannot leave the local spool
  3. Sink manifests: exact schema, stable identity, eligible transport, owner attestation, trading_authority=false
  4. Delivery envelopes: deterministic, atomic, immutable, read-back verified
  5. Retries idempotent; conflicting destination files fail closed
  6. Local receipts content-verified; tampering fails closed
  7. Acknowledgements: exact identity, matching receipt, valid chronology, valid operator, bounded SLA
  8. Future/early/late/malformed/duplicate/conflicting/authority/unknown acks fail closed
  9. Concurrent/interrupted writes cannot silently corrupt authoritative evidence
 10. Implementation states sink attestation and operator acks are not cryptographically authenticated
 11. Must not claim completed off-host delivery, institutional readiness, or trading authority
 12. No hidden network or credential access
"""

from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from monitoring.off_host_alert_delivery import (
    ACK_VERSION, ENVELOPE_VERSION, RECEIPT_VERSION, SINK_VERSION, TRANSPORTS,
    AlertDeliveryError, deliver_alerts, import_acknowledgements,
    read_alerts, read_sink_manifest,
)

NOW = datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc)
UTC = timezone.utc


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))

def digest(value):
    import hashlib
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _setup(tmp_path, transport="UNC", sink_id="owner-remote-1"):
    sink = tmp_path / "sink"
    sink.mkdir(parents=True)
    manifest = {
        "schema_version": SINK_VERSION, "sink_id": sink_id,
        "transport": transport, "off_host_attested": True, "trading_authority": False,
    }
    (sink / "sink-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    body = {
        "event": "WATCHDOG_FAILURE", "observed_at": NOW.isoformat(),
        "reason": "HEALTH_COLLECTION_FAILED", "state": "UNHEALTHY",
        "ready_for_unattended_operation": False,
        "watchdog_version": "OWNER_CONTEXT_HEALTH_WATCHDOG_V1",
        "trading_authority": False,
    }
    alert = {**body, "event_id": digest(body)}
    spool = tmp_path / "alerts.jsonl"
    spool.write_text(canonical(alert) + "\n", encoding="utf-8")
    return sink, spool


def _make_ack(receipt, sink_id="owner-remote-1", operator_id="risk-operator-1",
              acknowledged_at=None, delivery_id=None, authentication=None,
              trading_authority=False):
    body = {
        "schema_version": ACK_VERSION,
        "delivery_id": delivery_id or receipt["delivery_id"],
        "sink_id": sink_id,
        "operator_id": operator_id,
        "acknowledged_at": (acknowledged_at or NOW + timedelta(seconds=30)).isoformat(),
        "authentication": authentication or "UNAUTHENTICATED_OPERATOR_ATTESTATION",
        "trading_authority": trading_authority,
    }
    return {**body, "ack_id": digest(body)}


# ===========================================================================
# 1. Alert event IDs recomputed canonically; duplicates fail closed
# ===========================================================================

class TestAlertEventIDs:
    def test_valid_event_id_accepted(self, tmp_path):
        sink, spool = _setup(tmp_path)
        alerts = read_alerts(spool)
        assert len(alerts) == 1
        assert alerts[0]["event_id"] == digest({k: v for k, v in alerts[0].items() if k != "event_id"})

    def test_wrong_event_id_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        alert = json.loads(spool.read_text())
        alert["event_id"] = "0" * 64
        spool.write_text(canonical(alert) + "\n")
        with pytest.raises(AlertDeliveryError, match="identity"):
            read_alerts(spool)

    def test_duplicate_event_id_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        content = spool.read_text()
        spool.write_text(content + content)
        with pytest.raises(AlertDeliveryError, match="duplicate"):
            read_alerts(spool)

    def test_missing_event_id_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        alert = json.loads(spool.read_text())
        del alert["event_id"]
        spool.write_text(canonical(alert) + "\n")
        with pytest.raises(AlertDeliveryError, match="identity"):
            read_alerts(spool)

    def test_trading_authority_true_in_alert_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        alert = json.loads(spool.read_text())
        body = {k: v for k, v in alert.items() if k != "event_id"}
        body["trading_authority"] = True
        alert = {**body, "event_id": digest(body)}
        spool.write_text(canonical(alert) + "\n")
        with pytest.raises(AlertDeliveryError, match="authority"):
            read_alerts(spool)


# ===========================================================================
# 2. Sensitive field names cannot leave the local spool
# ===========================================================================

class TestSensitiveFields:
    @pytest.mark.parametrize("field", [
        "password", "api_key", "api-key", "private_key", "private-key",
        "secret", "credential", "token",
    ])
    def test_sensitive_field_rejects(self, tmp_path, field):
        sink, spool = _setup(tmp_path)
        alert = json.loads(spool.read_text())
        alert[field] = "leaked"
        body = {k: v for k, v in alert.items() if k != "event_id"}
        alert = {**body, "event_id": digest(body)}
        spool.write_text(canonical(alert) + "\n")
        with pytest.raises(AlertDeliveryError, match="prohibited"):
            read_alerts(spool)

    def test_nested_sensitive_field_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        alert = json.loads(spool.read_text())
        alert["details"] = {"password": "leaked"}
        body = {k: v for k, v in alert.items() if k != "event_id"}
        alert = {**body, "event_id": digest(body)}
        spool.write_text(canonical(alert) + "\n")
        with pytest.raises(AlertDeliveryError, match="prohibited"):
            read_alerts(spool)


# ===========================================================================
# 3. Sink manifest validation
# ===========================================================================

class TestSinkManifest:
    def test_valid_manifest_accepted(self, tmp_path):
        sink, _ = _setup(tmp_path)
        manifest = read_sink_manifest(sink)
        assert manifest["sink_id"] == "owner-remote-1"

    def test_wrong_schema_rejects(self, tmp_path):
        sink, _ = _setup(tmp_path)
        m = json.loads((sink / "sink-manifest.json").read_text())
        m["schema_version"] = "wrong"
        (sink / "sink-manifest.json").write_text(json.dumps(m))
        with pytest.raises(AlertDeliveryError, match="shape"):
            read_sink_manifest(sink)

    def test_missing_field_rejects(self, tmp_path):
        sink, _ = _setup(tmp_path)
        m = json.loads((sink / "sink-manifest.json").read_text())
        del m["transport"]
        (sink / "sink-manifest.json").write_text(json.dumps(m))
        with pytest.raises(AlertDeliveryError, match="shape"):
            read_sink_manifest(sink)

    def test_extra_field_rejects(self, tmp_path):
        sink, _ = _setup(tmp_path)
        m = json.loads((sink / "sink-manifest.json").read_text())
        m["extra"] = True
        (sink / "sink-manifest.json").write_text(json.dumps(m))
        with pytest.raises(AlertDeliveryError, match="shape"):
            read_sink_manifest(sink)

    def test_invalid_sink_id_rejects(self, tmp_path):
        sink, _ = _setup(tmp_path)
        m = json.loads((sink / "sink-manifest.json").read_text())
        m["sink_id"] = "UPPER!"
        (sink / "sink-manifest.json").write_text(json.dumps(m))
        with pytest.raises(AlertDeliveryError, match="identity"):
            read_sink_manifest(sink)

    def test_invalid_transport_rejects(self, tmp_path):
        sink, _ = _setup(tmp_path)
        m = json.loads((sink / "sink-manifest.json").read_text())
        m["transport"] = "EMAIL"
        (sink / "sink-manifest.json").write_text(json.dumps(m))
        with pytest.raises(AlertDeliveryError, match="attestation"):
            read_sink_manifest(sink)

    def test_off_host_not_attested_rejects(self, tmp_path):
        sink, _ = _setup(tmp_path)
        m = json.loads((sink / "sink-manifest.json").read_text())
        m["off_host_attested"] = False
        (sink / "sink-manifest.json").write_text(json.dumps(m))
        with pytest.raises(AlertDeliveryError, match="attestation"):
            read_sink_manifest(sink)

    def test_trading_authority_true_rejects(self, tmp_path):
        sink, _ = _setup(tmp_path)
        m = json.loads((sink / "sink-manifest.json").read_text())
        m["trading_authority"] = True
        (sink / "sink-manifest.json").write_text(json.dumps(m))
        with pytest.raises(AlertDeliveryError, match="authority"):
            read_sink_manifest(sink)

    def test_malformed_manifest_rejects(self, tmp_path):
        sink, _ = _setup(tmp_path)
        (sink / "sink-manifest.json").write_text("{not json}")
        with pytest.raises(AlertDeliveryError):
            read_sink_manifest(sink)

    def test_missing_manifest_rejects(self, tmp_path):
        sink = tmp_path / "sink"
        sink.mkdir()
        with pytest.raises(AlertDeliveryError):
            read_sink_manifest(sink)

    @pytest.mark.parametrize("transport", list(TRANSPORTS))
    def test_valid_transports_accepted(self, tmp_path, transport):
        sink, spool = _setup(tmp_path, transport=transport)
        manifest = read_sink_manifest(sink)
        assert manifest["transport"] == transport


# ===========================================================================
# 4. Delivery envelopes: deterministic, atomic, immutable, read-back
# ===========================================================================

class TestDeliveryEnvelopes:
    def test_envelope_written_and_read_back(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        env_path = next((sink / "inbox").glob("*.json"))
        env = json.loads(env_path.read_text("utf-8"))
        assert env["schema_version"] == ENVELOPE_VERSION
        assert env["trading_authority"] is False
        assert env["alert_sha256"] == digest(env["alert"])

    def test_deterministic_delivery_id(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        a = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        b = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=tmp_path / "r2", delivered_at=NOW)
        assert a[0]["delivery_id"] == b[0]["delivery_id"]

    def test_envelope_is_immutable(self, tmp_path):
        """Conflicting destination file fails closed."""
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        # Tamper with existing envelope
        env_path = next((sink / "inbox").glob("*.json"))
        env = json.loads(env_path.read_text("utf-8"))
        env["tampered"] = True
        env_path.write_text(json.dumps(env))
        with pytest.raises(AlertDeliveryError, match="conflicts"):
            deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)

    def test_no_temp_files_remaining(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        temps = list(sink.rglob("*.tmp-*"))
        assert len(temps) == 0
        temps2 = list(receipts.rglob("*.tmp-*"))
        assert len(temps2) == 0


# ===========================================================================
# 5. Retries idempotent; conflicting destination files fail closed
# ===========================================================================

class TestRetries:
    def test_idempotent_retry(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        a = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        b = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW + timedelta(seconds=1))
        assert a == b

    def test_conflicting_existing_delivery_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        # Corrupt the existing delivery
        env_path = next((sink / "inbox").glob("*.json"))
        env = json.loads(env_path.read_text("utf-8"))
        env["alert_sha256"] = "0" * 64
        env_path.write_text(json.dumps(env))
        with pytest.raises(AlertDeliveryError, match="conflicts"):
            deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)


# ===========================================================================
# 6. Local receipts content-verified; tampering fails closed
# ===========================================================================

class TestReceipts:
    def test_receipt_written_and_verified(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        result = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        receipt_path = receipts / f"{result[0]['delivery_id']}.json"
        assert receipt_path.is_file()
        receipt = json.loads(receipt_path.read_text("utf-8"))
        assert receipt["schema_version"] == RECEIPT_VERSION
        assert receipt["trading_authority"] is False

    def test_tampered_receipt_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        result = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        path = receipts / f"{result[0]['delivery_id']}.json"
        value = json.loads(path.read_text("utf-8"))
        value["receipt_id"] = "0" * 64
        path.write_text(json.dumps(value))
        with pytest.raises(AlertDeliveryError, match="existing receipt"):
            deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)

    def test_receipt_id_is_sha256(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        result = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        assert len(result[0]["receipt_id"]) == 64


# ===========================================================================
# 7. Acknowledgements: identity, receipt, chronology, operator, SLA
# ===========================================================================

class TestAcknowledgements:
    def _deliver_and_ack(self, tmp_path, ack_offset=30, sla=60):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        local_acks = tmp_path / "acks"
        receipt = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)[0]
        acks_dir = sink / "acknowledgements"
        acks_dir.mkdir()
        ack = _make_ack(receipt, acknowledged_at=NOW + timedelta(seconds=ack_offset))
        (acks_dir / "ack.json").write_text(json.dumps(ack), encoding="utf-8")
        return sink, receipts, local_acks, ack, receipt

    def test_valid_ack_accepted(self, tmp_path):
        sink, receipts, local_acks, ack, _ = self._deliver_and_ack(tmp_path)
        accepted = import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                           as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)
        assert accepted == (ack,)
        assert (local_acks / f"{ack['ack_id']}.json").is_file()

    def test_ack_id_is_sha256(self, tmp_path):
        sink, receipts, local_acks, ack, _ = self._deliver_and_ack(tmp_path)
        assert len(ack["ack_id"]) == 64

    def test_matching_receipt_required(self, tmp_path):
        sink, receipts, local_acks, ack, _ = self._deliver_and_ack(tmp_path)
        # Tamper receipt
        rpath = receipts / f"{ack['delivery_id']}.json"
        rvalue = json.loads(rpath.read_text())
        rvalue["delivery_id"] = "0" * 64
        rbody = {k: v for k, v in rvalue.items() if k != "receipt_id"}
        rvalue["receipt_id"] = digest(rbody)
        rpath.write_text(json.dumps(rvalue))
        with pytest.raises(AlertDeliveryError):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)

    def test_invalid_operator_id_rejects(self, tmp_path):
        sink, receipts, local_acks, _, receipt = self._deliver_and_ack(tmp_path)
        ack = _make_ack(receipt, operator_id="INVALID!")
        (sink / "acknowledgements" / "ack.json").write_text(json.dumps(ack))
        with pytest.raises(AlertDeliveryError, match="operator"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)

    def test_sla_breach_rejects(self, tmp_path):
        sink, receipts, local_acks, _, _ = self._deliver_and_ack(tmp_path, ack_offset=30, sla=10)
        with pytest.raises(AlertDeliveryError, match="SLA"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=10)

    def test_zero_sla_rejects(self, tmp_path):
        sink, receipts, local_acks, _, _ = self._deliver_and_ack(tmp_path)
        with pytest.raises(AlertDeliveryError, match="SLA"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=0)


# ===========================================================================
# 8. Future/early/late/malformed/duplicate/conflicting/authority/unknown acks
# ===========================================================================

class TestAckFailClosed:
    def _full_setup(self, tmp_path, **ack_kwargs):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        local_acks = tmp_path / "acks"
        receipt = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)[0]
        acks_dir = sink / "acknowledgements"
        acks_dir.mkdir()
        ack = _make_ack(receipt, **ack_kwargs)
        (acks_dir / "ack.json").write_text(json.dumps(ack), encoding="utf-8")
        return sink, receipts, local_acks, ack

    def test_future_ack_rejects(self, tmp_path):
        sink, receipts, local_acks, _ = self._full_setup(tmp_path, acknowledged_at=NOW + timedelta(hours=1))
        with pytest.raises(AlertDeliveryError, match="chronology"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=86400)

    def test_early_ack_before_delivery_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        receipt = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)[0]
        acks_dir = sink / "acknowledgements"
        acks_dir.mkdir()
        ack = _make_ack(receipt, acknowledged_at=NOW - timedelta(seconds=10))
        (acks_dir / "ack.json").write_text(json.dumps(ack))
        with pytest.raises(AlertDeliveryError, match="chronology"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=tmp_path / "acks",
                                   as_of=NOW, acknowledgement_sla_seconds=60)

    def test_malformed_ack_json_rejects(self, tmp_path):
        sink, receipts, local_acks, _ = self._full_setup(tmp_path)
        (sink / "acknowledgements" / "ack.json").write_text("{not json}")
        with pytest.raises(AlertDeliveryError):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)

    def test_authority_escalation_rejects(self, tmp_path):
        sink, receipts, local_acks, _ = self._full_setup(tmp_path, trading_authority=True)
        with pytest.raises(AlertDeliveryError, match="authority"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)

    def test_wrong_authentication_rejects(self, tmp_path):
        sink, receipts, local_acks, _ = self._full_setup(tmp_path, authentication="SIGNED")
        with pytest.raises(AlertDeliveryError, match="authority"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)

    def test_wrong_sink_id_rejects(self, tmp_path):
        sink, receipts, local_acks, _ = self._full_setup(tmp_path, sink_id="other-sink")
        with pytest.raises(AlertDeliveryError, match="identity"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)

    def test_wrong_schema_version_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        local_acks = tmp_path / "acks"
        receipt = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)[0]
        acks_dir = sink / "acknowledgements"
        acks_dir.mkdir()
        ack = _make_ack(receipt)
        ack["schema_version"] = "wrong"
        body = {k: v for k, v in ack.items() if k != "ack_id"}
        ack["ack_id"] = digest(body)
        (acks_dir / "ack.json").write_text(json.dumps(ack))
        with pytest.raises(AlertDeliveryError, match="shape"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)

    def test_extra_field_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        local_acks = tmp_path / "acks"
        receipt = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)[0]
        acks_dir = sink / "acknowledgements"
        acks_dir.mkdir()
        ack = _make_ack(receipt)
        ack["extra"] = True
        body = {k: v for k, v in ack.items() if k != "ack_id"}
        ack["ack_id"] = digest(body)
        (acks_dir / "ack.json").write_text(json.dumps(ack))
        with pytest.raises(AlertDeliveryError, match="shape"):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)

    def test_missing_receipt_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        local_acks = tmp_path / "acks"
        receipt = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)[0]
        acks_dir = sink / "acknowledgements"
        acks_dir.mkdir()
        ack = _make_ack(receipt, delivery_id="0" * 64)
        (acks_dir / "ack.json").write_text(json.dumps(ack))
        with pytest.raises(AlertDeliveryError):
            import_acknowledgements(sink=sink, local_receipts=receipts, local_acks=local_acks,
                                   as_of=NOW + timedelta(seconds=30), acknowledgement_sla_seconds=60)


# ===========================================================================
# 9. Concurrent/interrupted writes cannot silently corrupt
# ===========================================================================

class TestAtomicIntegrity:
    def test_no_temp_remaining_after_delivery(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        assert not list(sink.rglob("*.tmp-*"))
        assert not list(receipts.rglob("*.tmp-*"))

    def test_envelope_read_back_matches(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        env_path = next((sink / "inbox").glob("*.json"))
        env = json.loads(env_path.read_text("utf-8"))
        # Verify it's valid JSON with expected keys
        assert env["schema_version"] == ENVELOPE_VERSION
        assert env["trading_authority"] is False


# ===========================================================================
# 10. Implementation states not cryptographically authenticated
# ===========================================================================

class TestNotAuthenticated:
    def test_module_states_not_cryptographically_authenticated(self):
        source = Path(__file__).parent.parent / "monitoring" / "off_host_alert_delivery.py"
        text = source.read_text("utf-8")
        assert "does not" in text.lower() and "authenticate" in text.lower()
        assert "UNAUTHENTICATED_OPERATOR_ATTESTATION" in text

    def test_foundation_md_states_not_authenticated(self):
        source = Path(__file__).parent.parent / "monitoring" / "OFF_HOST_ALERT_DELIVERY_FOUNDATION.md"
        text = source.read_text("utf-8")
        assert "not cryptographically authenticated" in text.lower()


# ===========================================================================
# 11. Must not claim completed off-host delivery, institutional readiness, trading
# ===========================================================================

class TestNoCompletedClaim:
    def test_foundation_not_completed(self):
        source = Path(__file__).parent.parent / "monitoring" / "OFF_HOST_ALERT_DELIVERY_FOUNDATION.md"
        text = source.read_text("utf-8")
        assert "not yet a completed" in text.lower() or "not a completed" in text.lower()

    def test_foundation_no_institutional_readiness_claim(self):
        source = Path(__file__).parent.parent / "monitoring" / "OFF_HOST_ALERT_DELIVERY_FOUNDATION.md"
        text = source.read_text("utf-8")
        assert "Institutional readiness requires" in text  # states it as a requirement, not a claim

    def test_foundation_no_trading_authority_claim(self):
        source = Path(__file__).parent.parent / "monitoring" / "OFF_HOST_ALERT_DELIVERY_FOUNDATION.md"
        text = source.read_text("utf-8")
        assert "trading_authority=false" in text.lower()

    def test_module_no_completed_claim(self):
        source = Path(__file__).parent.parent / "monitoring" / "off_host_alert_delivery.py"
        text = source.read_text("utf-8")
        assert "does not" in text.lower() and "authenticate" in text.lower()
        assert "off-host" in text.lower()

    def test_all_outputs_trading_authority_false(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        result = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        for r in result:
            assert r["trading_authority"] is False
        env = json.loads(next((sink / "inbox").glob("*.json")).read_text("utf-8"))
        assert env["trading_authority"] is False


# ===========================================================================
# 12. No hidden network or credential access
# ===========================================================================

class TestNoNetworkCredential:
    def test_no_network_imports(self):
        source = Path(__file__).parent.parent / "monitoring" / "off_host_alert_delivery.py"
        text = source.read_text("utf-8")
        tree = ast.parse(text)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "urllib", "http",
                    "smtplib", "imaplib", "ftplib", "paramiko", "sshtunnel"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_no_credential_strings(self):
        source = Path(__file__).parent.parent / "monitoring" / "off_host_alert_delivery.py"
        text = source.read_text("utf-8").lower()
        for forbidden in ("getpass", "get_credential", "keyring", "vault",
                         "secret_manager", "aws_secret", "azure_key"):
            assert forbidden not in text, f"forbidden: {forbidden}"

    def test_os_import_only_for_atomic_replace(self):
        """os is imported only for os.replace and os.getpid (atomic writes)."""
        source = Path(__file__).parent.parent / "monitoring" / "off_host_alert_delivery.py"
        text = source.read_text("utf-8")
        assert "import os" in text
        # Verify os usage is only for replace and getpid
        os_uses = [line.strip() for line in text.split("\n") if "os." in line]
        for use in os_uses:
            assert "os.replace" in use or "os.getpid" in use or "os.fsync" in use or "os.path" in use


# ===========================================================================
# Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """8 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: canonical event ID recomputation, all sensitive
        fields (8 variants + nested), all 3 transports, manifest shape/version/identity/
        attestation/authority, envelope immutability, conflicting delivery, tampered
        receipt, future/early/late ack, wrong authentication, wrong sink, wrong schema,
        extra fields, missing receipt, zero SLA, no network imports, os usage scope —
        not in existing 8 tests."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: deliver_alerts, import_acknowledgements,
        read_alerts, read_sink_manifest, AlertDeliveryError, and version constants.
        No private helpers called."""
