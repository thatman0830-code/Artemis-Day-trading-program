from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import pytest
from execution.paper_gateway_v2 import PaperGatewayPolicyV1,PaperGatewaySnapshotV1
from execution.paper_session_drills_v1 import *
from execution.paper_session_supervisor_v1 import PaperSessionPolicyV1,PaperSessionState
NOW=datetime(2026,8,31,20,tzinfo=timezone.utc)
def gateway():return PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(Decimal("5"),Decimal("10"),2,timedelta(seconds=5)))
def policy():return PaperSessionPolicyV1(timedelta(seconds=5),timedelta(seconds=1))
def test_bounded_runner_runs_exact_cycles_and_releases_lock(tmp_path):
    state,health=run_bounded(tmp_path,gateway(),policy(),((NOW,NOW),(NOW+timedelta(seconds=1),NOW+timedelta(seconds=1))))
    assert len(health)==2 and all(x.state is PaperSessionState.HEALTHY for x in health)
    assert not (tmp_path/"paper-session.lock").exists()
def test_bounded_runner_stops_after_first_halt(tmp_path):
    _,health=run_bounded(tmp_path,gateway(),policy(),((NOW,NOW-timedelta(seconds=6)),(NOW,NOW)))
    assert len(health)==1 and health[0].state is PaperSessionState.HALTED_STALE_INPUT
def test_empty_run_rejects(tmp_path):
    with pytest.raises(ValueError):run_bounded(tmp_path,gateway(),policy(),())
def test_recovery_drills_all_pass_and_are_deterministic(tmp_path):
    first=run_recovery_drills(tmp_path/"a",gateway(),NOW);second=run_recovery_drills(tmp_path/"b",gateway(),NOW)
    assert all(x.passed for x in first.observations) and first.report_id==second.report_id and not first.trading_authority
def test_no_network_credentials_schedulers_or_live_submission():
    source=Path(__file__).with_name("paper_session_drills_v1.py").read_text("utf-8").lower()
    for value in ("requests","httpx","socket","private_key","api_key","scheduledtask","submit_live"):assert value not in source
