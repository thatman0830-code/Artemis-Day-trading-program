import hashlib
import json

import pytest

from execution.paper_session_attribution_v1 import (
    PaperSessionAttributionError, build_attribution, write_attribution,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def envelope(payload):
    return {"schema_version": "test", "payload": payload,
            "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest()}


def session(root, *, net="0", baseline_net="0", position="0", fills=(), commands=0,
            protective_exit=None):
    root.mkdir()
    runtime={"runtime_id":"r","session_id":"s","started_at":"2025-01-01T00:01:00+00:00","stopped_at":"2025-01-01T00:03:00+00:00",
             "state":"STOPPED","cycles":2,"commands":commands,
             "termination_reason":"SUPERVISOR_STOP","trading_authority":False}
    strategy={"observation_id":"o","result_id":"x","result_outcome":"NO_SETUP",
              "decision_reason":"OUTCOME_NO_SETUP","actionable":False,
              "qualification_present":False,"entry_zone_present":False,"status_id":"status",
              "trading_authority":False}
    gateway={"snapshot_id":"g","records":[]};receipts=[]
    if protective_exit:
        order_ids=["stop","target"]
        winner=0 if protective_exit=="STOP_LOSS" else 1
        gateway["records"]=[{"paper_order_id":value,"state":"FILLED" if index==winner else "CANCELLED"}
                            for index,value in enumerate(order_ids)]
        common={"accepted":True,"pair_id":"pair","paper_order_ids":order_ids}
        receipts=[{**common,"reason":"CONTINGENT_PAIR_APPLIED"},
                  {**common,"reason":"CONTINGENT_RESOLUTION_APPLIED"}]
        fills=({"fields":{"paper_order_id":order_ids[winner]}},)
        commands=max(commands,2)
    adapter={"receipts":receipts,"gateway_checkpoint":{"payload":gateway}}
    baseline={"snapshot_id":"before","as_of":{"$datetime":"2025-01-01T00:00:00Z"},
              "net_result":{"$decimal":baseline_net},"total_costs":{"$decimal":"0"},
              "gross_realized_pnl":{"$decimal":baseline_net}}
    fields={"snapshot_id":"after","as_of":{"$datetime":"2025-01-01T00:02:00Z"},
            "cash":{"$decimal":"100"},"equity":{"$decimal":"100"},
            "gross_realized_pnl":{"$decimal":net},"net_result":{"$decimal":net},
            "total_costs":{"$decimal":"0"},"unrealized_pnl":{"$decimal":"0"},
            "position":{"fields":{"signed_quantity":{"$decimal":position}}}}
    ledger={"ledger_id":"l","gateway_snapshot_id":"g","fill_bindings":{"$tuple":list(fills)},
            "accounting":{"fields":{"snapshots":{"$tuple":[{"fields":baseline},{"fields":fields}]}}}}
    for name,value in (("runtime-result.json",runtime),("canonical-strategy-status.json",strategy),
                       ("adapter-checkpoint.json",envelope(adapter)),
                       ("performance-checkpoint.json",envelope({"ledger":{"fields":ledger}})),
                       ("latest-health.json",{"state":"STOPPED","trading_authority":False})):
        (root/name).write_text(json.dumps(value))
    body={"schema_version":"btc-canonical-strategy-status-history-v1","sequence":0,
          "previous_event_id":None,"status_id":"status","state":"READY",
          "observed_at":"2025-01-01T00:02:00+00:00","observation_id":"o","result_id":"x",
          "actionable":False,"failure_code":None,"result_outcome":"NO_SETUP",
          "qualification_present":False,"entry_zone_present":False,
          "decision_reason":"OUTCOME_NO_SETUP","trading_authority":False}
    event={**body,"event_id":hashlib.sha256(canonical(body)).hexdigest()}
    (root.parent/(root.name+"-canonical-strategy-history.jsonl")).write_bytes(canonical(event)+b"\n")


def test_no_trade_attribution_binds_all_evidence_and_is_idempotent(tmp_path):
    root=tmp_path/"session";session(root)
    first=write_attribution(root,attempt_exit_code=0)
    second=write_attribution(root,attempt_exit_code=0)
    assert first==second and first["payload"]["outcome"]=="NO_TRADE"
    assert first["payload"]["exit_reason_status"]=="NOT_APPLICABLE"
    hashes=first["payload"]["evidence_sha256"]
    assert all(value for name,value in hashes.items() if name!="attempt-failure.json")
    assert hashes["attempt-failure.json"] is None
    assert first["payload"]["missing_evidence"]==[]
    assert first["payload"]["strategy_history"]["event_count"]==1
    assert hashes["canonical-strategy-history.jsonl"] is not None
    assert first["payload"]["trading_authority"] is False


@pytest.mark.parametrize("net,outcome",[("1.25","WIN"),("-0.5","LOSS"),("0","BREAK_EVEN")])
def test_flat_filled_session_uses_verified_net_result(tmp_path,net,outcome):
    root=tmp_path/outcome;session(root,net=net,fills=({"fill_id":"f"},),commands=1)
    result=build_attribution(root,attempt_exit_code=0)
    assert result["payload"]["outcome"]==outcome
    assert result["payload"]["exit_reason"] is None
    assert result["payload"]["exit_reason_status"]=="NOT_PROVEN"


def test_classification_uses_session_delta_not_cumulative_ledger_result(tmp_path):
    root=tmp_path/"delta";session(root,baseline_net="10",net="9",fills=({"fill_id":"f"},),commands=1)
    result=build_attribution(root,attempt_exit_code=0)["payload"]
    assert result["outcome"]=="LOSS"
    assert result["session_financials"]["net_result"]=="-1"


@pytest.mark.parametrize("reason",["STOP_LOSS","PROFIT_TARGET"])
def test_protective_exit_requires_pair_resolution_terminal_state_and_accounting(tmp_path,reason):
    root=tmp_path/reason;session(root,net="-1" if reason=="STOP_LOSS" else "2",
                                 protective_exit=reason)
    result=build_attribution(root,attempt_exit_code=0)["payload"]
    assert result["exit_reason"]==reason and result["exit_reason_status"]=="PROVEN"


def test_unbound_protective_winner_fails_closed(tmp_path):
    root=tmp_path/"unbound";session(root,net="1",protective_exit="PROFIT_TARGET")
    performance=json.loads((root/"performance-checkpoint.json").read_text())
    performance["payload"]["ledger"]["fields"]["fill_bindings"]={"$tuple":[]}
    performance=envelope(performance["payload"])
    (root/"performance-checkpoint.json").write_text(json.dumps(performance))
    with pytest.raises(PaperSessionAttributionError,match="lacks accounting binding"):
        build_attribution(root,attempt_exit_code=0)


def test_failed_attempt_records_missing_evidence_without_fabrication(tmp_path):
    root=tmp_path/"failed";root.mkdir()
    result=build_attribution(root,attempt_exit_code=7)["payload"]
    assert result["outcome"]=="FAILED_CLOSED" and len(result["missing_evidence"])==7
    assert result["final_accounting"] is None and result["strategy"] is None
    assert result["termination_reason"]=="FAILED_CLOSED_UNCLASSIFIED"
    assert result["termination_reason_status"]=="NOT_PROVEN"


@pytest.mark.parametrize("state,reason",[
    ("HALTED_STALE_INPUT","STALE_INPUT"),
    ("HALTED_FUTURE_INPUT","FUTURE_INPUT_OR_CLOCK_FAILURE"),
    ("HALTED_PERFORMANCE_PERSISTENCE","PERSISTENCE_FAILURE"),
    ("RECONCILIATION_REQUIRED","RECONCILIATION_REQUIRED"),
])
def test_failed_attempt_uses_durable_health_termination(tmp_path,state,reason):
    root=tmp_path/state;root.mkdir()
    (root/"latest-health.json").write_text(json.dumps({"state":state,"trading_authority":False}))
    result=build_attribution(root,attempt_exit_code=1)["payload"]
    assert result["termination_reason"]==reason
    assert result["termination_reason_status"]=="PROVEN"


def test_tampering_and_cross_checkpoint_mismatch_fail_closed(tmp_path):
    root=tmp_path/"bad";session(root)
    adapter=json.loads((root/"adapter-checkpoint.json").read_text())
    adapter["payload"]["receipts"].append({"forged":True})
    (root/"adapter-checkpoint.json").write_text(json.dumps(adapter))
    with pytest.raises(PaperSessionAttributionError,match="checksum mismatch"):
        build_attribution(root,attempt_exit_code=0)


def test_strategy_history_chain_tampering_and_final_status_mismatch_fail_closed(tmp_path):
    root=tmp_path/"history";session(root);path=root.parent/(root.name+"-canonical-strategy-history.jsonl")
    event=json.loads(path.read_text());event["sequence"]=1;path.write_text(json.dumps(event)+"\n")
    with pytest.raises(PaperSessionAttributionError,match="history chain"):
        build_attribution(root,attempt_exit_code=0)
    event["sequence"]=0;body={key:value for key,value in event.items() if key!="event_id"}
    event["event_id"]=hashlib.sha256(canonical(body)).hexdigest();event["status_id"]="wrong"
    body={key:value for key,value in event.items() if key!="event_id"};event["event_id"]=hashlib.sha256(canonical(body)).hexdigest()
    path.write_text(json.dumps(event)+"\n")
    with pytest.raises(PaperSessionAttributionError,match="final status mismatch"):
        build_attribution(root,attempt_exit_code=0)


def test_existing_different_attribution_cannot_be_overwritten(tmp_path):
    root=tmp_path/"immutable";session(root)
    (root/"session-attribution-v2.json").write_text("{}")
    with pytest.raises(PaperSessionAttributionError,match="immutable"):
        write_attribution(root,attempt_exit_code=0)


def test_any_trading_authority_claim_fails_closed(tmp_path):
    root=tmp_path/"authority";session(root)
    runtime=json.loads((root/"runtime-result.json").read_text())
    runtime["trading_authority"]=True
    (root/"runtime-result.json").write_text(json.dumps(runtime))
    with pytest.raises(PaperSessionAttributionError,match="trading authority"):
        build_attribution(root,attempt_exit_code=0)


def test_module_has_no_transport_or_trading_authority():
    source=__import__("pathlib").Path(__file__).with_name("paper_session_attribution_v1.py").read_text().lower()
    for prohibited in ("requests","urllib","websocket","private_key","place_order","submit_order"):
        assert prohibited not in source
    assert '"trading_authority": false' in source
