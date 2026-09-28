from __future__ import annotations

import json
from pathlib import Path

import pytest

from futures_data import pass_b_backfill as base
from futures_data import pass_b_continuation as continuation


def test_frozen_continuation_identity_links_and_caps():
    repository=Path(__file__).resolve().parents[1]
    value,original,evidence=continuation._load_and_verify(repository)
    assert value["id"]=="cd39f6dc8a3fa93502144bad5f55a1c3d4839a3c4be9ac21439938d7c76d443e"
    assert value["original_plan_id"]==original["id"]
    assert value["base_state"]["committed_requests"]==123 and value["base_state"]["retained_requests"]==124
    assert evidence["committed_requests"] in (123,130) and evidence["retained_requests"] in (124,130)
    assert value["continuation_start_ordinal"]==124 and value["first_network_ordinal"]==125
    assert value["caps"]=={"requests":130,"rows":1_000_000,"raw_bytes":300*1024*1024,
        "normalized_bytes":400*1024*1024,"combined_bytes":650*1024*1024,"response_bytes":25*1024*1024}
    assert value["estimate"]["conservative_final_normalized_bytes"]<value["caps"]["normalized_bytes"]
    assert value["estimate"]["conservative_final_combined_bytes"]<value["caps"]["combined_bytes"]


def test_original_plan_and_caps_remain_immutable():
    repository=Path(__file__).resolve().parents[1]
    original=json.loads((repository/"data/backtests"/base.PLAN_DIR/"plan.json").read_text())
    assert original["id"]=="2a4b82d4d5d5dc97d87d9fb57cb6b3ce05379af4239f1717bee55eda9d91820f"
    assert original["caps"]["normalized_bytes"]==300*1024*1024
    assert base.MAX_NORMALIZED_BYTES==300*1024*1024


def test_retained_124_is_offline_and_first_fetch_is_125(monkeypatch):
    repository=Path(__file__).resolve().parents[1]
    if (repository/"data/backtests"/base.ARCHIVE_DIR).exists():
        _,_,evidence=continuation._load_and_verify(repository)
        assert evidence["committed_requests"]==130 and evidence["retained_requests"]==130
        return
    calls=[]
    class StopAfterFirst(continuation.ContinuationStore):
        def commit(self,root,request,normalized,rows,reconciliation=None):
            if request["id"].startswith("7bf93577"):
                calls.append(("offline_commit",request["id"],rows));return
            raise continuation.ContinuationError("bounded test stop")
    monkeypatch.setattr(continuation,"ContinuationStore",StopAfterFirst)
    def fetch(request,_key):
        calls.append(("fetch",request["id"]));raise RuntimeError("bounded test stop")
    with pytest.raises(continuation.ContinuationError,match="provider request failed"):
        continuation.execute(repository,"synthetic-canary",fetch=fetch,sleep=lambda _:None)
    assert calls[0][0]=="offline_commit" and calls[0][1].startswith("7bf93577")
    assert calls[1][0]=="fetch" and calls[1][1].startswith("efe8b710")
    assert len(calls)==2


def test_cap_and_free_space_fail_closed(monkeypatch):
    repository=Path(__file__).resolve().parents[1]
    value,_,_=continuation._load_and_verify(repository)
    monkeypatch.setattr(continuation.shutil,"disk_usage",lambda _path:type("Disk",(),{"free":value["minimum_required_free_bytes"]-1})())
    with pytest.raises(continuation.ContinuationError,match="insufficient destination free space"):
        continuation.execute(repository,"synthetic",fetch=lambda *_:pytest.fail("no fetch"))


def test_revised_normalized_and_combined_caps_are_enforced(tmp_path):
    original={"id":"original","markets":{"ES":{"requests":[]},"NQ":{"requests":[]}}};caps={"requests":130,"rows":1_000_000,"raw_bytes":100,
        "normalized_bytes":3,"combined_bytes":100,"response_bytes":100}
    store=continuation.ContinuationStore(tmp_path,original,{"id":"continuation","caps":caps})
    request={"id":"request","root":"ES","ticker":"ESM6","contract_id":"contract","maximum_rows":1}
    store.retain("ES",request,b"{}",200,None)
    with pytest.raises(continuation.ContinuationError,match="cumulative cap"):
        store.commit("ES",request,b"four",1)
    combined=continuation.ContinuationStore(tmp_path/"combined",original,{"id":"continuation","caps":{**caps,"normalized_bytes":100,"combined_bytes":3}})
    combined.retain("ES",request,b"{}",200,None)
    with pytest.raises(continuation.ContinuationError,match="cumulative cap"):
        combined.commit("ES",request,b"xx",1)


def test_checkpoint_link_conflict_rejected(tmp_path):
    repository=Path(__file__).resolve().parents[1]
    value=json.loads((repository/"data/backtests"/continuation.PLAN_DIR/"plan.json").read_text())
    altered={**value,"stable_prefix_fingerprint":"0"*64};path=tmp_path/"plan.json";path.write_text(json.dumps(altered))
    expected=dict(altered);identity=expected.pop("id")
    assert continuation.sha256(continuation._canonical(expected)).hexdigest()!=identity


def test_promotion_requires_all_requests_and_no_recorder_capability(tmp_path):
    store=continuation.ContinuationStore(tmp_path,{"id":"original","markets":{"ES":{"requests":[]},"NQ":{"requests":[]}}},{"id":"continuation","caps":{"requests":130,"rows":1_000_000,
        "raw_bytes":300*1024*1024,"normalized_bytes":400*1024*1024,"combined_bytes":650*1024*1024,"response_bytes":25*1024*1024}})
    with pytest.raises(base.PassBError,match="promotion boundary invalid"): store.promote()
    source=(Path(__file__).with_name("pass_b_continuation.py")).read_text().lower()
    assert "start_recorder" not in source and "continuous recorder" not in source


def test_wrapper_is_hidden_stdin_redacted_and_traceback_free():
    repository=Path(__file__).resolve().parents[1]
    text=(repository/"scripts/enter_massive_es_nq_pass_b_continuation_key.ps1").read_text()
    assert "Read-Host" in text and "-AsSecureString" in text
    assert "Get-Content $secretPath -Raw|& $python" in text and "--api-key" not in text.lower()
    assert "2>$null" in text and "[Console]::Error.WriteLine($failureMessage)" in text
    assert "record" not in text.lower() and "recorder" not in text.lower()
