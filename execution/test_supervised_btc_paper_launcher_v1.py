from pathlib import Path
import inspect
import pytest

from execution.supervised_btc_paper_launcher_v1 import (
    SupervisedBTCPaperLauncherError,_confirmation,_run_collector,_verify_checkout,
)
from execution.test_paper_performance_ledger_v1 import T,H


def test_confirmation_uses_approved_hard_limits_and_no_authority():
    value=_confirmation(now=T,checkpoint=H("checkpoint"),supervision=True,stop_control=True)
    assert value.maximum_order_notional==100 and value.maximum_gross_exposure==100
    assert value.maximum_session_seconds==300 and value.maximum_commands==5
    assert value.trading_authority is False


def test_missing_fresh_owner_acknowledgements_reject():
    with pytest.raises(SupervisedBTCPaperLauncherError,match="fresh supervision"):
        _confirmation(now=T,checkpoint=H("checkpoint"),supervision=False,stop_control=True)


def test_collector_timeout_is_bounded_and_forwarded(monkeypatch,tmp_path):
    seen={}
    class Completed:returncode=0
    def run(*args,**kwargs):seen.update(kwargs);return Completed()
    monkeypatch.setattr("execution.supervised_btc_paper_launcher_v1.subprocess.run",run)
    _run_collector(powershell=tmp_path/"powershell.exe",collector=tmp_path/"collector.ps1",
        output_path=tmp_path/"facts.json",repository=tmp_path,label="launch evidence",
        timeout_seconds=45)
    assert seen["timeout"]==45 and seen["check"] is False
    with pytest.raises(SupervisedBTCPaperLauncherError,match="timeout is invalid"):
        _run_collector(powershell="x",collector="y",output_path="z",repository=tmp_path,
            label="test",timeout_seconds=46)


def test_collector_retries_transient_failure_but_remains_bounded(monkeypatch,tmp_path):
    class Completed:
        def __init__(self,code):self.returncode=code
    answers=iter((Completed(1),Completed(1),Completed(0)));calls=[]
    monkeypatch.setattr("execution.supervised_btc_paper_launcher_v1.subprocess.run",
        lambda *args,**kwargs:(calls.append(1)or next(answers)))
    monkeypatch.setattr("execution.supervised_btc_paper_launcher_v1.time.sleep",lambda _:None)
    _run_collector(powershell="x",collector="y",output_path="z",repository=tmp_path,
        label="health")
    assert len(calls)==3


def test_checkout_must_be_clean_and_match_evidence(monkeypatch,tmp_path):
    class Result:
        def __init__(self,stdout):self.stdout=stdout
    answers=iter((Result(H("wrong")+"\n"),Result("")))
    monkeypatch.setattr("subprocess.run",lambda *args,**kwargs:next(answers))
    with pytest.raises(SupervisedBTCPaperLauncherError,match="clean current checkout"):
        _verify_checkout(tmp_path,H("expected"))


def test_preflight_branch_cannot_invoke_controller_and_launcher_has_no_order_transport():
    source=inspect.getsource(__import__("execution.supervised_btc_paper_launcher_v1",fromlist=["*"]))
    before_execute=source.split('if args.mode=="preflight":',1)[1].split("def operational_reader",1)[0]
    assert "controller.run" not in before_execute and '"session_started":False' in before_execute
    for prohibited in ("private_key","place_order","submit_order","wallet","credential"):
        assert prohibited not in source.lower()
    assert '"trading_authority":False' in source
    assert '"--specification-bundle"' in source
    assert '"--strategy-mode"' in source and '"canonical"' in source
    assert source.index("status=worker.poll")<source.index("controller.run")
    assert "CANONICAL_PRIME_TIMEOUT_SECONDS=60" in source
    assert "exact repository launch-evidence collector required" in source
    assert source.index("label=\"launch evidence\"")<source.index("status=worker.poll")
    assert "timeout_seconds=45" in source
    assert source.index("status=worker.poll")<source.index("assembly,health=prepare_launcher")
    assert source.index("label=\"operational health\"")<source.index("assembly,health=prepare_launcher")
    assert '"--refresh-public-evidence"' in source
    assert source.index("public=acquire_once")>source.index("label=\"operational health\"")
    assert source.index("compile_paper_specification_bundle")<source.index("assembly,health=prepare_launcher")
    assert "write_failure" in source and 'sys.argv.index("--session-root")' in source


def test_atomic_wrapper_retains_exact_collectors_and_defers_public_refresh():
    source=(Path(__file__).parents[1]/"scripts"/
        "run_fresh_canonical_btc_paper_session.ps1").read_text().lower()
    assert "$confirmsupervision" in source and "$confirmstopcontrol" in source
    assert "--confirm-supervision" in source and "--confirm-stop-control" in source
    assert "--launch-evidence-collector" in source
    assert "collect_supervised_paper_launch_evidence.ps1" in source
    assert "--health-facts" in source
    assert "--health-collector" in source and "collect_btc_paper_cycle_health.ps1" in source
    assert "--refresh-public-evidence" in source
    assert "btc_perpetual_public_evidence_acquisition_v1" not in source


def test_launch_evidence_collection_refreshes_authoritative_watchdog_first():
    source=(__import__("pathlib").Path(__file__).parents[1]/"scripts"/
        "collect_supervised_paper_launch_evidence.ps1").read_text().lower()
    assert "run_owner_context_health_watchdog.ps1" in source
    assert source.index("& $watchdog")<source.index("supervised_paper_launch_evidence_collector_v1")
    assert "for($attempt=1;$attempt-le 5;$attempt++)" in source
    assert "ready_for_unattended_operation-eq$true" in source
    assert "start-sleep -seconds 2" in source
    assert "fresh healthy owner-context watchdog evidence is unavailable after bounded retry" in source


def test_watchdog_writer_is_single_instance_across_task_and_launcher():
    source=(__import__("pathlib").Path(__file__).parents[1]/"scripts"/
        "run_owner_context_health_watchdog.ps1").read_text().lower()
    assert "global\\hyperliquidownercontexthealthwatchdogv1" in source
    assert "waitone([timespan]::fromseconds(15))" in source
    assert "$mutex.releasemutex()" in source and "$mutex.dispose()" in source


def test_owner_health_hashing_has_no_profile_dependent_cmdlet():
    source=(__import__("pathlib").Path(__file__).parents[1]/"scripts"/
        "collect_owner_context_health_facts.ps1").read_text().lower()
    assert "get-filehash" not in source
    assert "security.cryptography.sha256" in source
    assert "[io.file]::openread" in source


def test_cycle_health_tail_does_not_lock_the_active_recorder_log():
    source=(__import__("pathlib").Path(__file__).parents[1]/"scripts"/
        "collect_btc_paper_cycle_health.ps1").read_text().lower()
    event_section=source.split("$eventpath=",1)[1].split("$manifestpath=",1)[0]
    assert "get-content" not in event_section
    assert "[io.fileshare]::readwrite" in event_section
    assert "[io.fileshare]::delete" in event_section
    assert "262144" in event_section and "select-object -last 100" in event_section


def test_canonical_history_does_not_prepopulate_fresh_session_directory():
    source=inspect.getsource(__import__("execution.supervised_btc_paper_launcher_v1",
        fromlist=["*"]))
    assert 'args.session_root.name+"-canonical-strategy-history.jsonl"' in source
    assert 'args.session_root/"canonical-strategy-history.jsonl"' not in source
