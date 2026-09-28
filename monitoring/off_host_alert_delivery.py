"""Provider-neutral, fail-closed alert delivery evidence.

This module proves filesystem handoff and acknowledgement integrity. It does not
authenticate an operator or prove that a configured directory is physically
off-host; those remain deployment and drill gates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

SINK_VERSION = "owner-alert-sink-v1"
ENVELOPE_VERSION = "owner-alert-envelope-v1"
RECEIPT_VERSION = "owner-alert-receipt-v1"
ACK_VERSION = "owner-alert-acknowledgement-v1"
TRANSPORTS = frozenset({"UNC", "CLOUD_SYNC", "REMOVABLE"})
_IDENTITY = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_SENSITIVE = re.compile(r"(?i)(password|api[_-]?key|private[_-]?key|secret|credential|token)")


class AlertDeliveryError(ValueError):
    pass


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise AlertDeliveryError(f"{field} must be an ISO UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlertDeliveryError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise AlertDeliveryError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


def _utc(value: datetime) -> str:
    return _time(value.isoformat(), "timestamp").isoformat().replace("+00:00", "Z")


def _atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    temporary.write_text(_canonical(value) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AlertDeliveryError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise AlertDeliveryError(f"{label} must be an object")
    return value


def _reject_sensitive_names(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or _SENSITIVE.search(key):
                raise AlertDeliveryError("alert contains a prohibited field name")
            _reject_sensitive_names(item)
    elif isinstance(value, list):
        for item in value: _reject_sensitive_names(item)


def read_sink_manifest(sink: Path) -> dict:
    value = _object(sink / "sink-manifest.json", "sink manifest")
    required = {"schema_version", "sink_id", "transport", "off_host_attested",
                "trading_authority"}
    if set(value) != required or value["schema_version"] != SINK_VERSION:
        raise AlertDeliveryError("sink manifest shape or version mismatch")
    if not isinstance(value["sink_id"], str) or not _IDENTITY.fullmatch(value["sink_id"]):
        raise AlertDeliveryError("sink identity is invalid")
    if value["transport"] not in TRANSPORTS or value["off_host_attested"] is not True:
        raise AlertDeliveryError("sink lacks an eligible owner attestation")
    if value["trading_authority"] is not False:
        raise AlertDeliveryError("sink authority boundary mismatch")
    return value


def read_alerts(alerts_path: Path) -> tuple[dict, ...]:
    try:
        lines = alerts_path.read_text("utf-8").splitlines()
    except OSError as exc:
        raise AlertDeliveryError("alert spool is unreadable") from exc
    if not lines:
        raise AlertDeliveryError("alert spool is empty")
    alerts: list[dict] = []
    seen: set[str] = set()
    for line in lines:
        try: alert = json.loads(line)
        except json.JSONDecodeError as exc: raise AlertDeliveryError("alert spool is malformed") from exc
        if not isinstance(alert, dict) or alert.get("trading_authority") is not False:
            raise AlertDeliveryError("alert authority or shape mismatch")
        _reject_sensitive_names(alert)
        event_id = alert.get("event_id")
        body = {key: value for key, value in alert.items() if key != "event_id"}
        if not isinstance(event_id, str) or event_id != _digest(body) or event_id in seen:
            raise AlertDeliveryError("alert identity mismatch or duplicate")
        _time(alert.get("observed_at"), "observed_at")
        seen.add(event_id); alerts.append(alert)
    return tuple(alerts)


def deliver_alerts(*, alerts_path: Path, sink: Path, local_receipts: Path,
                   delivered_at: datetime) -> tuple[dict, ...]:
    manifest = read_sink_manifest(sink); sink_id = manifest["sink_id"]
    delivered = _utc(delivered_at); receipts: list[dict] = []
    for alert in read_alerts(alerts_path):
        alert_id = alert["event_id"]
        delivery_id = hashlib.sha256(f"{sink_id}:{alert_id}".encode("ascii")).hexdigest()
        envelope_body = {"schema_version": ENVELOPE_VERSION, "delivery_id": delivery_id,
            "sink_id": sink_id, "alert_event_id": alert_id, "alert_sha256": _digest(alert),
            "alert": alert, "trading_authority": False}
        destination = sink / "inbox" / f"{delivery_id}.json"
        if destination.exists():
            if _object(destination, "existing delivery") != envelope_body:
                raise AlertDeliveryError("existing delivery conflicts with immutable envelope")
        else:
            _atomic(destination, envelope_body)
        if _object(destination, "delivered envelope") != envelope_body:
            raise AlertDeliveryError("delivery read-back verification failed")
        receipt = {"schema_version": RECEIPT_VERSION, "delivery_id": delivery_id,
            "sink_id": sink_id, "alert_event_id": alert_id, "delivered_at": delivered,
            "envelope_sha256": _digest(envelope_body), "trading_authority": False}
        receipt["receipt_id"] = _digest(receipt)
        receipt_path = local_receipts / f"{delivery_id}.json"
        if receipt_path.exists():
            existing = _object(receipt_path, "delivery receipt")
            receipt_keys = {"schema_version","delivery_id","sink_id","alert_event_id","delivered_at",
                            "envelope_sha256","trading_authority","receipt_id"}
            existing_body = {key: value for key, value in existing.items() if key != "receipt_id"}
            if (set(existing) != receipt_keys or existing.get("schema_version") != RECEIPT_VERSION or
                    existing.get("receipt_id") != _digest(existing_body) or
                    existing.get("sink_id") != sink_id or existing.get("trading_authority") is not False or
                    existing.get("delivery_id") != delivery_id or
                    existing.get("envelope_sha256") != receipt["envelope_sha256"]):
                raise AlertDeliveryError("existing receipt conflicts with delivery")
            receipt = existing
        else:
            _atomic(receipt_path, receipt)
        receipts.append(receipt)
    return tuple(receipts)


def verify_delivery(*, alerts_path: Path, sink: Path, local_receipts: Path) -> int:
    manifest = read_sink_manifest(sink); sink_id = manifest["sink_id"]; verified = 0
    for alert in read_alerts(alerts_path):
        alert_id = alert["event_id"]
        delivery_id = hashlib.sha256(f"{sink_id}:{alert_id}".encode("ascii")).hexdigest()
        envelope = _object(sink / "inbox" / f"{delivery_id}.json", "delivered envelope")
        expected = {"schema_version": ENVELOPE_VERSION, "delivery_id": delivery_id,
            "sink_id": sink_id, "alert_event_id": alert_id, "alert_sha256": _digest(alert),
            "alert": alert, "trading_authority": False}
        if envelope != expected:
            raise AlertDeliveryError("delivered envelope verification failed")
        receipt = _object(local_receipts / f"{delivery_id}.json", "delivery receipt")
        required = {"schema_version","delivery_id","sink_id","alert_event_id","delivered_at",
                    "envelope_sha256","trading_authority","receipt_id"}
        body = {key: value for key, value in receipt.items() if key != "receipt_id"}
        if (set(receipt) != required or receipt.get("schema_version") != RECEIPT_VERSION or
                receipt.get("receipt_id") != _digest(body) or receipt.get("delivery_id") != delivery_id or
                receipt.get("sink_id") != sink_id or receipt.get("alert_event_id") != alert_id or
                receipt.get("envelope_sha256") != _digest(envelope) or
                receipt.get("trading_authority") is not False):
            raise AlertDeliveryError("delivery receipt verification failed")
        _time(receipt.get("delivered_at"), "delivered_at"); verified += 1
    return verified


def import_acknowledgements(*, sink: Path, local_receipts: Path, local_acks: Path,
                            as_of: datetime, acknowledgement_sla_seconds: int) -> tuple[dict, ...]:
    if acknowledgement_sla_seconds <= 0:
        raise AlertDeliveryError("acknowledgement SLA must be positive")
    manifest = read_sink_manifest(sink); now = _time(_utc(as_of), "as_of")
    accepted: list[dict] = []
    for path in sorted((sink / "acknowledgements").glob("*.json")):
        ack = _object(path, "acknowledgement")
        required = {"schema_version","ack_id","delivery_id","sink_id","operator_id",
                    "acknowledged_at","authentication","trading_authority"}
        if set(ack) != required or ack["schema_version"] != ACK_VERSION:
            raise AlertDeliveryError("acknowledgement shape or version mismatch")
        body = {key: value for key, value in ack.items() if key != "ack_id"}
        if ack["ack_id"] != _digest(body) or ack["sink_id"] != manifest["sink_id"]:
            raise AlertDeliveryError("acknowledgement identity mismatch")
        if ack["authentication"] != "UNAUTHENTICATED_OPERATOR_ATTESTATION" or ack["trading_authority"] is not False:
            raise AlertDeliveryError("acknowledgement authority boundary mismatch")
        if not isinstance(ack["operator_id"], str) or not _IDENTITY.fullmatch(ack["operator_id"]):
            raise AlertDeliveryError("acknowledgement operator identity is invalid")
        receipt = _object(local_receipts / f"{ack['delivery_id']}.json", "delivery receipt")
        receipt_body = {key: value for key, value in receipt.items() if key != "receipt_id"}
        if (receipt.get("receipt_id") != _digest(receipt_body) or receipt.get("sink_id") != manifest["sink_id"] or
                receipt.get("delivery_id") != ack["delivery_id"] or receipt.get("trading_authority") is not False):
            raise AlertDeliveryError("delivery receipt identity mismatch")
        delivered = _time(receipt.get("delivered_at"), "delivered_at")
        acknowledged = _time(ack["acknowledged_at"], "acknowledged_at")
        if acknowledged < delivered or acknowledged > now + timedelta(minutes=1):
            raise AlertDeliveryError("acknowledgement chronology is invalid")
        if (acknowledged - delivered).total_seconds() > acknowledgement_sla_seconds:
            raise AlertDeliveryError("acknowledgement SLA breached")
        _atomic(local_acks / f"{ack['ack_id']}.json", ack); accepted.append(ack)
    return tuple(accepted)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deliver sanitized watchdog alert evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    deliver = subparsers.add_parser("deliver")
    deliver.add_argument("--alerts", type=Path, required=True)
    deliver.add_argument("--sink", type=Path, required=True)
    deliver.add_argument("--receipts", type=Path, required=True)
    acknowledge = subparsers.add_parser("import-acknowledgements")
    acknowledge.add_argument("--sink", type=Path, required=True)
    acknowledge.add_argument("--receipts", type=Path, required=True)
    acknowledge.add_argument("--acknowledgements", type=Path, required=True)
    acknowledge.add_argument("--sla-seconds", type=int, required=True)
    args = parser.parse_args(); now = datetime.now(timezone.utc)
    if args.command == "deliver":
        receipts = deliver_alerts(alerts_path=args.alerts, sink=args.sink,
                                  local_receipts=args.receipts, delivered_at=now)
        print(_canonical({"state":"DELIVERED","receipt_count":len(receipts),
                          "trading_authority":False}))
    else:
        acknowledgements = import_acknowledgements(
            sink=args.sink, local_receipts=args.receipts,
            local_acks=args.acknowledgements, as_of=now,
            acknowledgement_sla_seconds=args.sla_seconds)
        print(_canonical({"state":"ACKNOWLEDGEMENTS_IMPORTED",
                          "acknowledgement_count":len(acknowledgements),
                          "trading_authority":False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
