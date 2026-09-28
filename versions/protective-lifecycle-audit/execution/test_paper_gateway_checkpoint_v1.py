from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import pytest

from execution.paper_gateway_checkpoint_v1 import *
from execution.paper_gateway_v2 import PaperGatewayPolicyV1, PaperGatewaySnapshotV1

canonical=lambda value: json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def state():
    return PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(Decimal("500"),Decimal("800"),2,timedelta(seconds=5)))

def test_round_trip_is_deterministic_and_preserves_integrity(tmp_path):
    store=PaperGatewayCheckpointStoreV1(tmp_path/"state.json");store.save(state())
    loaded=store.load()
    assert loaded==state() and checkpoint_bytes(loaded)==checkpoint_bytes(state())

def test_second_save_atomically_replaces_existing(tmp_path):
    store=PaperGatewayCheckpointStoreV1(tmp_path/"state.json");store.save(state())
    changed=state().activate_kill_switch();store.save(changed)
    assert store.load()==changed and not list(tmp_path.glob("*.tmp")) and not store.lock_path.exists()

def test_existing_lock_fails_closed_and_preserves_checkpoint(tmp_path):
    store=PaperGatewayCheckpointStoreV1(tmp_path/"state.json");store.save(state());before=store.path.read_bytes()
    store.lock_path.write_text("busy")
    with pytest.raises(PaperCheckpointError,match="lock"):
        store.save(state().activate_kill_switch())
    assert store.path.read_bytes()==before

def test_tamper_truncation_unknown_and_duplicate_fields_reject(tmp_path):
    raw=checkpoint_bytes(state());doc=json.loads(raw)
    doc["payload"]["connected"]=False
    with pytest.raises(PaperCheckpointError,match="checksum"):snapshot_from_bytes(json.dumps(doc).encode())
    with pytest.raises(PaperCheckpointError):snapshot_from_bytes(raw[:20])
    doc=json.loads(raw);doc["extra"]=1
    with pytest.raises(PaperCheckpointError,match="fields"):snapshot_from_bytes(json.dumps(doc).encode())
    with pytest.raises(PaperCheckpointError,match="duplicate"):snapshot_from_bytes(b'{"schema_version":"a","schema_version":"b"}')

def test_snapshot_id_and_trading_authority_tamper_reject_even_with_new_checksum():
    doc=json.loads(checkpoint_bytes(state()))
    for field,value in (("snapshot_id","0"*64),("trading_authority",True)):
        changed=json.loads(json.dumps(doc));changed["payload"][field]=value
        changed["payload_sha256"]=__import__('hashlib').sha256(canonical(changed["payload"])).hexdigest()
        with pytest.raises(PaperCheckpointError):snapshot_from_bytes(canonical(changed))

def test_missing_parent_symlink_and_missing_checkpoint_reject(tmp_path):
    with pytest.raises(PaperCheckpointError,match="parent"):
        PaperGatewayCheckpointStoreV1(tmp_path/"missing"/"state.json").save(state())
    with pytest.raises(PaperCheckpointError,match="missing"):
        PaperGatewayCheckpointStoreV1(tmp_path/"none.json").load()

def test_module_has_no_network_credentials_pickle_or_live_submission():
    source=Path(__file__).with_name("paper_gateway_checkpoint_v1.py").read_text("utf-8").lower()
    for prohibited in ("requests","httpx","socket","websocket","pickle","private_key","api_key","submit_live"):
        assert prohibited not in source

def test_unknown_record_field_and_non_boolean_state_reject_even_when_rehashed():
    doc=json.loads(checkpoint_bytes(state()));doc["payload"]["connected"]="false"
    doc["payload_sha256"]=__import__('hashlib').sha256(canonical(doc["payload"])).hexdigest()
    with pytest.raises(PaperCheckpointError):snapshot_from_bytes(canonical(doc))
    doc=json.loads(checkpoint_bytes(state()));doc["payload"]["records"]=[{"extra":1}]
    doc["payload_sha256"]=__import__('hashlib').sha256(canonical(doc["payload"])).hexdigest()
    with pytest.raises(PaperCheckpointError,match="record fields"):
        snapshot_from_bytes(canonical(doc))

def test_boolean_open_order_limit_rejects():
    with pytest.raises(ValueError,match="max_open_orders"):
        PaperGatewayPolicyV1(Decimal("1"),Decimal("1"),True,timedelta(seconds=1))

def test_malformed_decimal_is_normalized_to_checkpoint_error():
    doc=json.loads(checkpoint_bytes(state()))
    doc["payload"]["policy"]["max_order_notional"]="not-a-decimal"
    doc["payload_sha256"]=__import__('hashlib').sha256(canonical(doc["payload"])).hexdigest()
    with pytest.raises(PaperCheckpointError,match="payload is invalid"):
        snapshot_from_bytes(canonical(doc))
