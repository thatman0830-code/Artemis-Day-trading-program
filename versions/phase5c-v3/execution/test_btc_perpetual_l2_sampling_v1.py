from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import pytest

from execution.btc_perpetual_l2_evidence_v1 import collect_btc_l2_evidence
from execution.btc_perpetual_l2_sampling_v1 import *
from execution.btc_perpetual_l2_sampling_v1 import _is_due
from execution.test_btc_perpetual_l2_aggregate_v1 import _payload,_retain


START=datetime(2026,9,3,tzinfo=timezone.utc)


def _acquirer(calls):
    def acquire(*,output_root):
        at=START+INTERVAL*len(calls);calls.append(at);raw=_payload(at,len(calls))
        return collect_btc_l2_evidence(transport=lambda *_:(200,raw),output_root=output_root,captured_at=at)
    return acquire


def test_first_cycle_acquires_exactly_once_and_writes_advisory_status(tmp_path):
    calls=[];status=run_sampling_cycle(output_root=tmp_path,now=START,acquire=_acquirer(calls))
    assert calls==[START] and status.verified_count==1 and status.acquired_receipt_id
    assert status.maximum_requests_this_cycle==1 and not status.complete
    assert status.policy_approved is status.trading_authority is False
    document=json.loads((tmp_path/"sampling-status.json").read_text())
    assert document["version"]==VERSION and document["trading_authority"] is False


def test_early_restart_makes_no_request_then_due_cycle_resumes(tmp_path):
    calls=[];acquire=_acquirer(calls)
    run_sampling_cycle(output_root=tmp_path,now=START,acquire=acquire)
    early=run_sampling_cycle(output_root=tmp_path,now=START+timedelta(minutes=19),acquire=acquire)
    due=run_sampling_cycle(output_root=tmp_path,now=START+timedelta(minutes=20),acquire=acquire)
    assert len(calls)==2 and early.acquired_receipt_id is None and due.verified_count==2


def test_five_second_scheduler_tolerance_prevents_alternating_skips():
    due=START+INTERVAL
    assert _is_due(due-timedelta(seconds=5),due)
    assert not _is_due(due-timedelta(seconds=5,microseconds=1),due)


def test_lock_conflict_rejects_without_request(tmp_path,monkeypatch):
    calls=[]
    def conflict(path):raise BTCL2SamplingError("sampling cycle is already active")
    monkeypatch.setattr("execution.btc_perpetual_l2_sampling_v1._acquire_lock",conflict)
    with pytest.raises(BTCL2SamplingError,match="already active"):
        run_sampling_cycle(output_root=tmp_path,now=START,acquire=_acquirer(calls))
    assert calls==[]


def test_tampered_evidence_stops_before_request(tmp_path):
    path=_retain(tmp_path,START);document=json.loads(path.read_text())
    (tmp_path/document["raw_relative_path"]).write_bytes(b"tampered");calls=[]
    with pytest.raises(BTCL2SamplingError,match="verification"):
        run_sampling_cycle(output_root=tmp_path,now=START+INTERVAL,acquire=_acquirer(calls))
    assert calls==[]
    # The persistent lock file is harmless; the operating-system lock was released.
    with pytest.raises(BTCL2SamplingError,match="verification"):
        run_sampling_cycle(output_root=tmp_path,now=START+INTERVAL,
            acquire=lambda **kwargs:pytest.fail("tampered evidence must still stop acquisition"))


def test_acquirer_must_retain_exactly_one_receipt(tmp_path):
    class Result:receipt_id="missing"
    with pytest.raises(BTCL2SamplingError,match="exactly one"):
        run_sampling_cycle(output_root=tmp_path,now=START,
            acquire=lambda **kwargs:Result())


def test_sufficient_existing_set_is_complete_without_request(tmp_path):
    paths=[_retain(tmp_path,START+timedelta(minutes=20*i),i) for i in range(24)]
    calls=[];now=START+timedelta(minutes=20*24)
    status=run_sampling_cycle(output_root=tmp_path,now=now,acquire=_acquirer(calls))
    assert not calls and status.complete and status.evidence_sufficient
    assert status.verified_count==len(paths) and status.next_due_at is None


def test_operational_scripts_preserve_disabled_owner_policy():
    repository=Path(__file__).resolve().parents[1]
    runner=(repository/"scripts/run_btc_perpetual_l2_sampler.ps1").read_text()
    installer=(repository/"scripts/install_btc_perpetual_l2_sampler_task.ps1").read_text()
    auditor=(repository/"scripts/audit_btc_perpetual_l2_sampler_task.ps1").read_text()
    assert "if($Execute){$arguments+='--execute'}" in runner
    assert "-RepetitionInterval (New-TimeSpan -Minutes 20)" in installer
    assert "Disable-ScheduledTask" in installer and "-RunLevel Limited" in installer
    assert "-MultipleInstances IgnoreNew" in installer and "-ExecutionTimeLimit (New-TimeSpan -Minutes 2)" in installer
    assert "PT20M" in auditor and "maximum_requests_per_run=1" in auditor
    assert "trading_authority=$false" in auditor and "credentials_used=$false" in auditor
