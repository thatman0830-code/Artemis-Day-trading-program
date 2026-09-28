from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from monitoring.off_host_alert_delivery import (
    ACK_VERSION, AlertDeliveryError, deliver_alerts, import_acknowledgements, main,
    verify_delivery,
)
from monitoring.onedrive_delivery_verifier import main as verify_main

NOW=datetime(2026,8,31,20,tzinfo=timezone.utc)


def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"))
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()


def setup(tmp_path):
    sink=tmp_path/"sink"; sink.mkdir(parents=True)
    manifest={"schema_version":"owner-alert-sink-v1","sink_id":"owner-remote-1",
        "transport":"UNC","off_host_attested":True,"trading_authority":False}
    (sink/"sink-manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    body={"event":"WATCHDOG_FAILURE","observed_at":NOW.isoformat(),"reason":"HEALTH_COLLECTION_FAILED",
        "state":"UNHEALTHY","ready_for_unattended_operation":False,
        "watchdog_version":"OWNER_CONTEXT_HEALTH_WATCHDOG_V1","trading_authority":False}
    alert={**body,"event_id":digest(body)}; spool=tmp_path/"alerts.jsonl"
    spool.write_text(canonical(alert)+"\n",encoding="utf-8")
    return sink,spool


def test_delivery_is_atomic_idempotent_and_content_verified(tmp_path):
    sink,spool=setup(tmp_path); receipts=tmp_path/"receipts"
    first=deliver_alerts(alerts_path=spool,sink=sink,local_receipts=receipts,delivered_at=NOW)
    second=deliver_alerts(alerts_path=spool,sink=sink,local_receipts=receipts,delivered_at=NOW+timedelta(seconds=1))
    assert first == second and len(first) == 1
    envelope=json.loads(next((sink/"inbox").glob("*.json")).read_text("utf-8"))
    assert envelope["alert_sha256"] == digest(envelope["alert"])
    assert envelope["trading_authority"] is False


@pytest.mark.parametrize("attack",("authority","event_id","duplicate","sink"))
def test_delivery_rejects_authority_identity_duplicate_and_sink_attacks(tmp_path,attack):
    sink,spool=setup(tmp_path)
    if attack == "sink":
        value=json.loads((sink/"sink-manifest.json").read_text()); value["off_host_attested"]=False
        (sink/"sink-manifest.json").write_text(json.dumps(value))
    else:
        value=json.loads(spool.read_text())
        if attack == "authority": value["trading_authority"]=True
        if attack == "event_id": value["event_id"]="0"*64
        spool.write_text(canonical(value)+"\n"+(canonical(value)+"\n" if attack=="duplicate" else ""))
    with pytest.raises(AlertDeliveryError):
        deliver_alerts(alerts_path=spool,sink=sink,local_receipts=tmp_path/"receipts",delivered_at=NOW)


def test_acknowledgement_requires_receipt_integrity_chronology_and_sla(tmp_path):
    sink,spool=setup(tmp_path); receipts=tmp_path/"receipts"; local_acks=tmp_path/"acks"
    receipt=deliver_alerts(alerts_path=spool,sink=sink,local_receipts=receipts,delivered_at=NOW)[0]
    (sink/"acknowledgements").mkdir(); body={"schema_version":ACK_VERSION,
        "delivery_id":receipt["delivery_id"],"sink_id":"owner-remote-1","operator_id":"risk-operator-1",
        "acknowledged_at":(NOW+timedelta(seconds=30)).isoformat(),
        "authentication":"UNAUTHENTICATED_OPERATOR_ATTESTATION","trading_authority":False}
    ack={**body,"ack_id":digest(body)}
    (sink/"acknowledgements"/"ack.json").write_text(json.dumps(ack),encoding="utf-8")
    accepted=import_acknowledgements(sink=sink,local_receipts=receipts,local_acks=local_acks,
        as_of=NOW+timedelta(seconds=30),acknowledgement_sla_seconds=60)
    assert accepted == (ack,) and next(local_acks.glob("*.json")).is_file()
    with pytest.raises(AlertDeliveryError,match="SLA"):
        import_acknowledgements(sink=sink,local_receipts=receipts,local_acks=tmp_path/"late",
            as_of=NOW+timedelta(seconds=30),acknowledgement_sla_seconds=10)


def test_acknowledgement_is_explicitly_not_authenticated(tmp_path):
    sink,spool=setup(tmp_path); receipts=tmp_path/"receipts"
    receipt=deliver_alerts(alerts_path=spool,sink=sink,local_receipts=receipts,delivered_at=NOW)[0]
    (sink/"acknowledgements").mkdir(); body={"schema_version":ACK_VERSION,
        "delivery_id":receipt["delivery_id"],"sink_id":"owner-remote-1","operator_id":"risk-operator-1",
        "acknowledged_at":NOW.isoformat(),"authentication":"SIGNED",
        "trading_authority":False}; ack={**body,"ack_id":digest(body)}
    (sink/"acknowledgements"/"ack.json").write_text(json.dumps(ack))
    with pytest.raises(AlertDeliveryError,match="authority boundary"):
        import_acknowledgements(sink=sink,local_receipts=receipts,local_acks=tmp_path/"acks",
            as_of=NOW,acknowledgement_sla_seconds=60)


def test_sensitive_field_names_and_tampered_receipts_fail_closed(tmp_path):
    sink,spool=setup(tmp_path); alert=json.loads(spool.read_text()); alert["api_token"]="not-exportable"
    body={key:value for key,value in alert.items() if key != "event_id"}; alert["event_id"]=digest(body)
    spool.write_text(canonical(alert)+"\n")
    with pytest.raises(AlertDeliveryError,match="prohibited field"):
        deliver_alerts(alerts_path=spool,sink=sink,local_receipts=tmp_path/"receipts",delivered_at=NOW)
    sink,spool=setup(tmp_path/"second"); receipts=tmp_path/"second"/"receipts"
    receipt=deliver_alerts(alerts_path=spool,sink=sink,local_receipts=receipts,delivered_at=NOW)[0]
    path=receipts/f"{receipt['delivery_id']}.json"; value=json.loads(path.read_text()); value["receipt_id"]="0"*64
    path.write_text(json.dumps(value))
    with pytest.raises(AlertDeliveryError,match="existing receipt"):
        deliver_alerts(alerts_path=spool,sink=sink,local_receipts=receipts,delivered_at=NOW)


def test_cli_delivers_without_exposing_authority(tmp_path,monkeypatch,capsys):
    sink,spool=setup(tmp_path); receipts=tmp_path/"receipts"
    monkeypatch.setattr("sys.argv",["delivery","deliver","--alerts",str(spool),
        "--sink",str(sink),"--receipts",str(receipts)])
    assert main() == 0
    output=json.loads(capsys.readouterr().out)
    assert output == {"state":"DELIVERED","receipt_count":1,"trading_authority":False}


def test_onedrive_runner_is_narrow_and_secret_free():
    source=(__import__("pathlib").Path(__file__).parents[1]/"scripts"/"run_onedrive_alert_delivery.ps1").read_text("utf-8")
    assert "TradingSystem\\AlertEvidence" in source and "sink-manifest.json" in source
    assert "monitoring.off_host_alert_delivery deliver" in source
    assert source.index("$oneDrive = $env:OneDrive") < source.index("GetEnvironmentVariable('OneDrive','User')")
    for prohibited in ("Get-Credential","password","api_key","private_key","Start-ScheduledTask",
                       "Stop-ScheduledTask","Enable-ScheduledTask","Disable-ScheduledTask"):
        assert prohibited.lower() not in source.lower()


def test_read_only_delivery_verifier_requires_every_envelope_and_receipt(tmp_path):
    sink,spool=setup(tmp_path); receipts=tmp_path/"receipts"
    delivered=deliver_alerts(alerts_path=spool,sink=sink,local_receipts=receipts,delivered_at=NOW)
    assert verify_delivery(alerts_path=spool,sink=sink,local_receipts=receipts) == 1
    (receipts/f"{delivered[0]['delivery_id']}.json").unlink()
    with pytest.raises(AlertDeliveryError,match="receipt is unreadable"):
        verify_delivery(alerts_path=spool,sink=sink,local_receipts=receipts)


def test_verify_cli_is_nontrading_and_read_only(tmp_path,monkeypatch,capsys):
    sink,spool=setup(tmp_path); receipts=tmp_path/"receipts"
    deliver_alerts(alerts_path=spool,sink=sink,local_receipts=receipts,delivered_at=NOW)
    before={p:p.read_bytes() for p in tmp_path.rglob("*.json")}
    monkeypatch.setattr("sys.argv",["verify","--alerts",str(spool),
        "--sink",str(sink),"--receipts",str(receipts)])
    assert verify_main() == 0
    assert json.loads(capsys.readouterr().out)=={"state":"DELIVERY_VERIFIED","verified_count":1,"trading_authority":False}
    assert before=={p:p.read_bytes() for p in tmp_path.rglob("*.json")}
