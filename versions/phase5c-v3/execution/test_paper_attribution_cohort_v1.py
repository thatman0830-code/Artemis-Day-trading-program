import json
from decimal import Decimal
from pathlib import Path

import pytest

from execution.paper_attribution_cohort_v1 import (
    PaperAttributionCohortError, evaluate, write_evaluation,
)
from execution.paper_session_attribution_v1 import _canonical, _sha, SCHEMA as ATTRIBUTION_SCHEMA


def attribution(root, name, outcome, net=None, reason="OUTCOME_TEST", exit_status="PROVEN"):
    directory=root/name;directory.mkdir(parents=True)
    payload={"schema_version":ATTRIBUTION_SCHEMA,"session_directory":name,
             "runtime":{"stopped_at":f"2025-01-{len(list(root.iterdir())):02d}T00:00:00Z"},
             "strategy":{"decision_reason":reason},"outcome":outcome,
             "session_financials":None if net is None else {"net_result":net},
             "exit_reason_status":exit_status,"advisory_only":True,
             "termination_reason":"SUPERVISOR_STOP","termination_reason_status":"PROVEN",
             "live_trading_permitted":False,"trading_authority":False}
    document={"schema_version":ATTRIBUTION_SCHEMA,"payload":payload,
              "payload_sha256":_sha(_canonical(payload))}
    (directory/"session-attribution-v2.json").write_bytes(_canonical(document)+b"\n")


def test_empty_cohort_is_honest_and_ineligible(tmp_path):
    result=evaluate(tmp_path)["payload"]
    assert result["session_count"]==0
    assert result["performance"]["win_rate"] is None
    assert result["performance"]["expectancy_per_finalized_trade"] is None
    assert result["evidence_gate"]["untouched_oos_eligibility"] is False


def test_statistics_use_session_deltas_and_include_no_trade_reasons(tmp_path):
    attribution(tmp_path,"a","WIN","3")
    attribution(tmp_path,"b","LOSS","-2")
    attribution(tmp_path,"c","BREAK_EVEN","0")
    attribution(tmp_path,"d","NO_TRADE",None,"OUTCOME_NO_SETUP","NOT_APPLICABLE")
    result=evaluate(tmp_path,minimum_finalized_trades=3)["payload"]
    performance=result["performance"]
    assert performance["net_result"]=="1"
    assert performance["expectancy_per_finalized_trade"]==str(Decimal(1)/3)
    assert performance["win_rate"]==str(Decimal(1)/3)
    assert performance["profit_factor"]=="1.5"
    assert performance["maximum_session_sequence_drawdown"]=="2"
    assert result["strategy_reason_counts"]["OUTCOME_NO_SETUP"]==1
    assert all(item["strategy_history_binding_sha256"] is None for item in result["attributions"])
    assert result["evidence_gate"]["untouched_oos_eligibility"] is True


def test_drawdown_and_loss_streak_follow_chronology(tmp_path):
    attribution(tmp_path,"a","WIN","5")
    attribution(tmp_path,"b","LOSS","-2")
    attribution(tmp_path,"c","LOSS","-4")
    result=evaluate(tmp_path)["payload"]["performance"]
    assert result["maximum_session_sequence_drawdown"]=="6"
    assert result["longest_loss_streak"]==2


def test_unresolved_and_missing_exit_attribution_block_gate(tmp_path):
    attribution(tmp_path,"a","WIN","1",exit_status="NOT_PROVEN")
    attribution(tmp_path,"b","OPEN_EXPOSURE",None,exit_status="NOT_PROVEN")
    gate=evaluate(tmp_path,minimum_finalized_trades=1)["payload"]["evidence_gate"]
    assert gate=={"minimum_finalized_trades_required":1,"minimum_sample_met":True,
                  "complete_exit_attribution":False,"complete_termination_attribution":True,
                  "no_unresolved_sessions":False,
                  "untouched_oos_eligibility":False}


def test_tampering_rejects(tmp_path):
    attribution(tmp_path,"a","WIN","1")
    path=tmp_path/"a"/"session-attribution-v2.json"
    document=json.loads(path.read_text());document["payload"]["trading_authority"]=True
    path.write_text(json.dumps(document))
    with pytest.raises(PaperAttributionCohortError,match="checksum mismatch"):
        evaluate(tmp_path)


def test_content_addressed_output_and_latest_pointer_are_deterministic(tmp_path):
    sessions=tmp_path/"sessions";sessions.mkdir();attribution(sessions,"a","NO_TRADE",None,exit_status="NOT_APPLICABLE")
    output=tmp_path/"output"
    first=write_evaluation(sessions,output);second=write_evaluation(sessions,output)
    assert first==second
    pointer=json.loads((output/"latest.json").read_text())
    assert pointer["evaluation_file"]==first.name and pointer["trading_authority"] is False


def test_module_has_no_transport_or_strategy_tuning():
    source=Path(__file__).with_name("paper_attribution_cohort_v1.py").read_text().lower()
    for prohibited in ("requests","urllib","websocket","place_order","submit_order","optimize","parameter_search"):
        assert prohibited not in source
    assert '"trading_authority": false' in source
