from datetime import datetime,timedelta,timezone
from decimal import Decimal
import json
from pathlib import Path
import pytest
from execution.paper_gateway_v2 import PaperGatewayPolicyV1,PaperGatewaySnapshotV1
from execution.paper_session_supervisor_v1 import *

canonical=lambda value:json.dumps(value,sort_keys=True,separators=(",",":")).encode("utf-8")

NOW=datetime(2026,8,31,20,tzinfo=timezone.utc)
def gateway():return PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(Decimal("5"),Decimal("10"),2,timedelta(seconds=5)))
def supervisor(root,session="0"*32):return PaperSessionSupervisorV1(root,PaperSessionPolicyV1(timedelta(seconds=5),timedelta(seconds=1)),session)

def test_single_owner_and_release_only_owned_lock(tmp_path):
    one=supervisor(tmp_path);two=supervisor(tmp_path,"1"*32);one.acquire()
    with pytest.raises(PaperSessionError,match="already owned"):two.acquire()
    one.release();two.acquire();two.release()

def test_requires_checkpoint_or_explicit_initial_state(tmp_path):
    with supervisor(tmp_path) as value:
        with pytest.raises(PaperSessionError,match="required"):value.load_or_initialize()
        assert value.load_or_initialize(gateway())==gateway()

def test_healthy_cycle_writes_checkpoint_and_content_addressed_heartbeat(tmp_path):
    with supervisor(tmp_path) as value:
        state=value.load_or_initialize(gateway());state,health=value.cycle(state,NOW,NOW)
        assert health.state is PaperSessionState.HEALTHY and not health.trading_authority
        document=json.loads(value.health_path.read_text());core={k:v for k,v in document.items() if k!="heartbeat_id"}
        assert __import__('hashlib').sha256(canonical(core)).hexdigest()==document["heartbeat_id"]
        assert value.store.load()==state

@pytest.mark.parametrize("observed,expected",[(NOW-timedelta(seconds=6),PaperSessionState.HALTED_STALE_INPUT),(NOW+timedelta(microseconds=1),PaperSessionState.HALTED_FUTURE_INPUT)])
def test_bad_input_halts_disconnects_and_persists_kill_switch(tmp_path,observed,expected):
    with supervisor(tmp_path) as value:
        state=value.load_or_initialize(gateway());state,health=value.cycle(state,NOW,observed)
        assert health.state is expected and state.kill_switch_active and state.reconciliation_required and not state.connected
        assert value.store.load()==state

def test_controlled_stop_is_identity_bound_and_preserves_state(tmp_path):
    with supervisor(tmp_path) as value:
        state=value.load_or_initialize(gateway())
        value.stop_path.write_text(json.dumps({"session_id":value.session_id,"stop":True,"trading_authority":False}))
        state,health=value.cycle(state,NOW,NOW)
        assert health.state is PaperSessionState.STOPPED and health.stop_requested and value.store.load()==state

def test_malformed_or_foreign_stop_request_fails_closed(tmp_path):
    with supervisor(tmp_path) as value:
        state=value.load_or_initialize(gateway());value.stop_path.write_text("{}")
        with pytest.raises(PaperSessionError,match="identity"):value.cycle(state,NOW,NOW)

def test_lock_tamper_prevents_cycle_and_release(tmp_path):
    value=supervisor(tmp_path);value.acquire();value.lock_path.write_text('{}')
    with pytest.raises(PaperSessionError,match="mismatch"):value.cycle(gateway(),NOW,NOW)
    with pytest.raises(PaperSessionError,match="mismatch"):value.release()

def test_no_network_credentials_provider_or_live_submission():
    source=Path(__file__).with_name("paper_session_supervisor_v1.py").read_text("utf-8").lower()
    for prohibited in ("requests","httpx","socket","websocket","private_key","api_key","submit_live","scheduledtask"):
        assert prohibited not in source

def test_restart_from_existing_checkpoint_forces_reconciliation(tmp_path):
    first=supervisor(tmp_path);first.acquire();first.load_or_initialize(gateway());first.release()
    second=supervisor(tmp_path,"1"*32);second.acquire();restarted=second.load_or_initialize();second.release()
    assert not restarted.connected and restarted.reconciliation_required
