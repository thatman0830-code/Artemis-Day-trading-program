from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


class TaskEnablePolicyError(RuntimeError):
    pass


EXPECTED_NAME="ES-NQ Delayed Daily Research Collector"
EXPECTED_PATH="\\"
EXPECTED_EXECUTABLE=r"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe"
EXPECTED_ARGUMENTS='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\\Users\\fjone\\hyperliquid-trading-bot\\scripts\\run_es_nq_delayed_forward_collector.ps1"'
EXPECTED_WORKDIR=r"C:\Users\fjone\hyperliquid-trading-bot"


def validate_enable_facts(facts:dict,*,now:datetime|None=None)->None:
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    exact={"task_name":EXPECTED_NAME,"task_path":EXPECTED_PATH,"state":"Disabled","logon_type":"Password","run_level":"Limited",
        "execute":EXPECTED_EXECUTABLE,"arguments":EXPECTED_ARGUMENTS,"working_directory":EXPECTED_WORKDIR,
        "days_interval":1,"start_when_available":True,"multiple_instances":"IgnoreNew","execution_time_limit":"PT2H",
        "restart_count":0,"disallow_start_on_batteries":True,"stop_on_batteries":True,"run_only_if_network_available":False}
    for key,value in exact.items():
        if facts.get(key)!=value:raise TaskEnablePolicyError("installed task definition mismatch")
    if not facts.get("owner_matches"):raise TaskEnablePolicyError("installed task owner mismatch")
    if facts.get("health")!="HEALTHY":raise TaskEnablePolicyError("collector health is not HEALTHY")
    if facts.get("lock_present"):raise TaskEnablePolicyError("collector lock is present")
    if facts.get("stop_requested"):raise TaskEnablePolicyError("collector stop is requested")
    if not facts.get("credential_present") or not facts.get("credential_owner_scoped"):
        raise TaskEnablePolicyError("owner-scoped credential presence rejected")
    if not facts.get("configuration_valid"):raise TaskEnablePolicyError("finalized configuration integrity rejected")
    next_run=facts.get("next_run_time")
    if not isinstance(next_run,str):raise TaskEnablePolicyError("next scheduled run unavailable")
    parsed=datetime.fromisoformat(next_run.replace("Z","+00:00"))
    if parsed.tzinfo is None or parsed.astimezone(timezone.utc)<=now:raise TaskEnablePolicyError("next scheduled run is not safely in the future")


def main(argv=None)->int:
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument("--facts",type=Path,required=True);args=parser.parse_args(argv)
    try:validate_enable_facts(json.loads(args.facts.read_text(encoding="utf-8")))
    except (OSError,ValueError,KeyError,TypeError,TaskEnablePolicyError):
        print("BLOCKED: local ES/NQ task enable policy rejected",file=sys.stderr);return 2
    return 0


if __name__=="__main__":raise SystemExit(main())
