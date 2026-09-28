from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
import json
import subprocess

import pytest

from futures_data.task_enable_policy import (EXPECTED_ARGUMENTS,EXPECTED_EXECUTABLE,EXPECTED_NAME,EXPECTED_PATH,
    EXPECTED_WORKDIR,TaskEnablePolicyError,validate_enable_facts)


NOW=datetime(2026,8,27,20,tzinfo=timezone.utc)


def facts():
    return {"task_name":EXPECTED_NAME,"task_path":EXPECTED_PATH,"state":"Disabled","logon_type":"Password","run_level":"Limited",
        "execute":EXPECTED_EXECUTABLE,"arguments":EXPECTED_ARGUMENTS,"working_directory":EXPECTED_WORKDIR,"days_interval":1,
        "next_run_time":"2026-08-28T09:30:00Z","start_when_available":True,"multiple_instances":"IgnoreNew",
        "execution_time_limit":"PT2H","restart_count":0,"disallow_start_on_batteries":True,"stop_on_batteries":True,
        "run_only_if_network_available":False,"owner_matches":True,"health":"HEALTHY","lock_present":False,
        "stop_requested":False,"credential_present":True,"credential_owner_scoped":True,"configuration_valid":True}


def test_exact_audited_task_is_enable_eligible():validate_enable_facts(facts(),now=NOW)


@pytest.mark.parametrize("field,value",[("arguments","-File wrong.ps1"),("execute","cmd.exe"),("working_directory","C:\\wrong")])
def test_mismatched_action_is_rejected(field,value):
    value_facts=facts();value_facts[field]=value
    with pytest.raises(TaskEnablePolicyError,match="definition"):validate_enable_facts(value_facts,now=NOW)


@pytest.mark.parametrize("field,value,message",[("owner_matches",False,"owner"),("health","STALE","health"),("lock_present",True,"lock"),
    ("stop_requested",True,"stop"),("configuration_valid",False,"configuration"),("credential_present",False,"credential"),
    ("credential_owner_scoped",False,"credential")])
def test_fail_closed_gates(field,value,message):
    value_facts=facts();value_facts[field]=value
    with pytest.raises(TaskEnablePolicyError,match=message):validate_enable_facts(value_facts,now=NOW)


def test_enable_helper_never_starts_task_or_mentions_other_systems():
    source=(Path(__file__).resolve().parents[1]/"scripts/enable_es_nq_delayed_forward_task.ps1").read_text()
    assert "Enable-ScheduledTask" in source and "Start-ScheduledTask" not in source
    assert "-TaskPath $taskPath" in source
    for prohibited in ("btc","pass_b","backtest","wallet","broker","place_order","private_key"):
        assert prohibited not in source.lower()


def test_real_enable_helper_policy_path_runs_from_outside_repository(tmp_path):
    fixture=facts();fixture["next_run_time"]="2099-01-01T00:00:00Z"
    path=tmp_path/"enable policy facts.json";path.write_text(json.dumps(fixture),encoding="utf-8")
    repository=Path(__file__).resolve().parents[1];powershell=Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    result=subprocess.run([str(powershell),"-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",
        str(repository/"scripts/enable_es_nq_delayed_forward_task.ps1"),"-PolicyOnlyFactsPath",str(path)],cwd=Path.home(),text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=="TASK_ENABLE_POLICY_VALIDATED_OFFLINE"
    assert "traceback" not in (result.stdout+result.stderr).lower()


def test_all_owner_futures_helpers_anchor_python_modules_to_repository():
    scripts=Path(__file__).resolve().parents[1]/"scripts"
    for path in scripts.glob("*.ps1"):
        source=path.read_text()
        if "-m futures_data." in source:
            assert ("Push-Location" in source or "WorkingDirectory=$repository" in source or "WorkingDirectory = $repository" in source),path.name
