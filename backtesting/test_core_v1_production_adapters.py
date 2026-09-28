from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import pytest

from backtesting.core_v1.production_adapters import (ArchiveEligibility, BTCPhase7PartialAdapter,
    PASS_B_SCHEMA, PassBV3ArchiveAdapter)


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+"\n", encoding="utf-8", newline="\n")


def h(path): return sha256(path.read_bytes()).hexdigest()


def pass_b_fixture(tmp_path: Path, market="ES"):
    repo=tmp_path; plan_root=repo/"plan"; cont_root=repo/"continuation"; archive=repo/"archive"
    ticker=market+"M6"; contract="c-"+market; rid="r-"+market; plan_id="plan-1"; cid="continuation-1"
    session="2026-01-05"; start=1767623400000000000
    row={"close":"101","contract_id":contract,"high":"102","low":"99","open":"100",
         "plan_id":plan_id,"root":market,"schema_version":PASS_B_SCHEMA,"session_date":session,
         "ticker":ticker,"volume":"7","window_start_ns":start}
    normalized=archive/market/"normalized"/(rid+".jsonl"); normalized.parent.mkdir(parents=True)
    normalized.write_text(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
    raw=archive/market/"raw"/(rid+".json")
    dump(raw,{"results":[{"ticker":ticker,"session_end_date":session,"window_start":start,
        "open":"100","high":"102","low":"99","close":"101","volume":"7"}]})
    request={"id":rid,"root":market,"ticker":ticker,"contract_id":contract,"sessions":[session],
             "start_utc":"2026-01-05T14:30:00Z","end_utc":"2026-01-05T14:32:00Z","maximum_rows":2}
    calendar={"schema_version":PASS_B_SCHEMA,"sessions":[{"session_date":session,"active_intervals":[{
        "start_utc":"2026-01-05T14:30:00Z","end_exclusive_utc":"2026-01-05T14:32:00Z"}]}]}
    roll={"schema_version":PASS_B_SCHEMA,"markets":{market:{"active_windows":[{
        "contract_id":contract,"ticker":ticker,"start":session,"end_exclusive":"2026-01-06",
        "roll_decision_id":"roll-1"}]}}}
    plan={"id":plan_id,"schema_version":PASS_B_SCHEMA,"markets":{market:{"requests":[request]}},
          "calendar":calendar,"rollovers":roll}
    dump(plan_root/"plan.json",plan);dump(plan_root/"calendar.json",calendar);dump(plan_root/"rollovers.json",roll)
    dump(plan_root/"artifact_manifest.json",{"plan_id":plan_id,"sha256":{
        "plan.json":h(plan_root/"plan.json"),"calendar.json":h(plan_root/"calendar.json"),
        "rollovers.json":h(plan_root/"rollovers.json")}})
    continuation={"id":cid,"original_plan_id":plan_id}
    dump(cont_root/"plan.json",continuation);dump(cont_root/"artifact_manifest.json",{
        "plan_id":cid,"plan_sha256":h(cont_root/"plan.json")})
    manifest={"schema_version":PASS_B_SCHEMA,"request_id":rid,"plan_id":plan_id,"root":market,
        "ticker":ticker,"contract_id":contract,"raw_relative_path":f"raw/{rid}.json",
        "normalized_relative_path":f"normalized/{rid}.jsonl","raw_sha256":h(raw),
        "normalized_sha256":h(normalized),"raw_bytes":raw.stat().st_size,
        "normalized_bytes":normalized.stat().st_size,"normalized_rows":1,"missing_aggregate_minutes":1}
    mp=archive/market/"manifests"/(rid+".json");dump(mp,manifest)
    pp=archive/market/"pending"/(rid+".json");dump(pp,{"request_id":rid,"raw_sha256":h(raw)})
    cp=archive/market/"checkpoints"/(rid+".json");dump(cp,{"request_id":rid,"plan_id":plan_id,"manifest_sha256":h(mp)})
    artifacts=[]
    for path in (raw,pp,normalized,mp,cp):
        artifacts.append({"path":path.relative_to(repo).as_posix(),"sha256":h(path),"bytes":path.stat().st_size})
    tree=sha256((json.dumps(sorted(artifacts,key=lambda x:x["path"]),sort_keys=True,separators=(",",":"))+"\n").encode()).hexdigest()
    audit={"state":"FINAL_ES_NQ_ARCHIVE_AUDIT_PASS","continuous_adjustment":False,
        "archive_path":str(archive.resolve()),"archive_tree_sha256":tree,"artifact_hashes":artifacts,
        "original_plan_id":plan_id,"continuation_plan_id":cid,"markets":{market:{"requests":1,"rows":1,
            "raw_bytes":raw.stat().st_size,"normalized_bytes":normalized.stat().st_size}},
        "plan_hashes":{(plan_root/"plan.json").relative_to(repo).as_posix():h(plan_root/"plan.json"),
          (plan_root/"artifact_manifest.json").relative_to(repo).as_posix():h(plan_root/"artifact_manifest.json"),
          (cont_root/"plan.json").relative_to(repo).as_posix():h(cont_root/"plan.json"),
          (cont_root/"artifact_manifest.json").relative_to(repo).as_posix():h(cont_root/"artifact_manifest.json")}}
    audit_path=repo/"audit.json";dump(audit_path,audit)
    return PassBV3ArchiveAdapter(repository_root=repo,market=market,archive_root=archive,
        plan_root=plan_root,continuation_root=cont_root,final_audit_path=audit_path), {
        "repo":repo,"archive":archive,"audit":audit_path,"manifest":mp,"normalized":normalized,
        "plan":plan_root/"plan.json","plan_root":plan_root,"continuation_root":cont_root,
        "raw":raw,"pending":pp,"checkpoint":cp,"ticker":ticker,"contract":contract,"market":market}


def refresh_fixture(paths):
    manifest=json.loads(paths["manifest"].read_text()); rows=paths["normalized"].read_text().splitlines()
    manifest.update(raw_sha256=h(paths["raw"]),raw_bytes=paths["raw"].stat().st_size,
        normalized_sha256=h(paths["normalized"]),normalized_bytes=paths["normalized"].stat().st_size,
        normalized_rows=len(rows),missing_aggregate_minutes=max(0,2-len(rows)))
    dump(paths["manifest"],manifest)
    dump(paths["pending"],{"request_id":manifest["request_id"],"raw_sha256":h(paths["raw"])})
    dump(paths["checkpoint"],{"request_id":manifest["request_id"],"plan_id":manifest["plan_id"],
                              "manifest_sha256":h(paths["manifest"])})
    pm=json.loads((paths["plan_root"]/"artifact_manifest.json").read_text())
    for name in ("plan.json","calendar.json","rollovers.json"): pm["sha256"][name]=h(paths["plan_root"]/name)
    dump(paths["plan_root"]/"artifact_manifest.json",pm)
    audit=json.loads(paths["audit"].read_text()); artifacts=[]
    for path in (paths["raw"],paths["pending"],paths["normalized"],paths["manifest"],paths["checkpoint"]):
        artifacts.append({"path":path.relative_to(paths["repo"]).as_posix(),"sha256":h(path),"bytes":path.stat().st_size})
    audit["artifact_hashes"]=artifacts
    audit["archive_tree_sha256"]=sha256((json.dumps(sorted(artifacts,key=lambda x:x["path"]),
        sort_keys=True,separators=(",",":"))+"\n").encode()).hexdigest()
    audit["markets"][paths["market"]].update(rows=len(rows),raw_bytes=paths["raw"].stat().st_size,
                                               normalized_bytes=paths["normalized"].stat().st_size)
    for path in (paths["plan_root"]/"plan.json",paths["plan_root"]/"artifact_manifest.json",
                 paths["continuation_root"]/"plan.json",paths["continuation_root"]/"artifact_manifest.json"):
        audit["plan_hashes"][path.relative_to(paths["repo"]).as_posix()]=h(path)
    dump(paths["audit"],audit)


def btc_fixture(tmp_path):
    root=tmp_path/"btc";root.mkdir();csv_path=root/"BTC_1m.csv"
    csv_path.write_text("symbol,timeframe,open_time,close_time,open,high,low,close,volume,is_closed\n"
        "BTC,1m,2026-01-01T00:00:00.000Z,2026-01-01T00:01:00.000Z,100,102,99,101,2,true\n",
        encoding="utf-8",newline="\n")
    dump(root/"partial_manifest.json",{"schema_version":"backtesting-public-download-v1","request_id":"btc-r",
        "completed":{"1m":{"sha256":h(csv_path),"through":"2026-01-01T00:01:00.000Z"}}})
    return BTCPhase7PartialAdapter(root),csv_path


def test_pass_b_chain_stream_decimal_ns_gap_and_rollover(tmp_path):
    adapter,_=pass_b_fixture(tmp_path)
    meta=adapter.validate(); events=adapter.iter_events(); first=next(events)
    assert first.bar.open.as_tuple().exponent == 0 and first.bar.open_time.microsecond == 0
    assert first.bar.contract_id=="c-ES" and first.bar.rollover_decision_id=="roll-1"
    assert len(adapter.data_quality_events)==1 and adapter.data_quality_events[0].missing_intervals==1
    assert meta.eligibility.permits(ArchiveEligibility.UNTOUCHED_OOS)
    with pytest.raises(StopIteration): next(events)


@pytest.mark.parametrize("field,value",[("plan_id","wrong"),("root","NQ"),("ticker","MESM6"),("contract_id","wrong")])
def test_pass_b_wrong_identity_rejected(tmp_path,field,value):
    adapter,paths=pass_b_fixture(tmp_path);data=json.loads(paths["manifest"].read_text());data[field]=value;dump(paths["manifest"],data)
    with pytest.raises(ValueError):adapter.validate()


def test_pass_b_checksum_missing_link_and_staging_rejected(tmp_path):
    adapter,paths=pass_b_fixture(tmp_path);paths["normalized"].write_text("corrupt\n")
    with pytest.raises(ValueError,match="checksum"):adapter.validate()
    adapter,paths=pass_b_fixture(tmp_path/"two");paths["manifest"].unlink()
    with pytest.raises(ValueError,match="link missing"):adapter.validate()
    adapter,paths=pass_b_fixture(tmp_path/"three");(paths["archive"]/"staging-rejected").mkdir()
    with pytest.raises(ValueError,match="unpromoted"):adapter.validate()


@pytest.mark.parametrize("mode",["duplicate","out_of_order","session"])
def test_pass_b_adversarial_normalized_rows_rejected(tmp_path,mode):
    adapter,paths=pass_b_fixture(tmp_path);row=json.loads(paths["normalized"].read_text())
    if mode=="duplicate": rows=[row,row]
    elif mode=="out_of_order":
        second=dict(row);second["window_start_ns"]-=60_000_000_000;rows=[row,second]
    else:
        row["session_date"]="2026-01-06";rows=[row]
    paths["normalized"].write_text("".join(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n" for x in rows),encoding="utf-8")
    raw={"results":[{"ticker":x["ticker"],"session_end_date":x["session_date"],"window_start":x["window_start_ns"],
        **{k:x[k] for k in ("open","high","low","close","volume")}} for x in rows]};dump(paths["raw"],raw)
    refresh_fixture(paths)
    with pytest.raises(ValueError):adapter.validate()


def test_pass_b_active_window_mismatch_rejected(tmp_path):
    adapter,paths=pass_b_fixture(tmp_path);roll=paths["plan_root"]/"rollovers.json";value=json.loads(roll.read_text())
    value["markets"]["ES"]["active_windows"][0]["contract_id"]="other";dump(roll,value);refresh_fixture(paths)
    with pytest.raises(ValueError,match="active-contract"):adapter.validate()


def test_pass_b_es_nq_isolation(tmp_path):
    es,_=pass_b_fixture(tmp_path/"es","ES");nq,_=pass_b_fixture(tmp_path/"nq","NQ")
    assert es.validate().dataset_fingerprint != nq.validate().dataset_fingerprint
    assert next(es.iter_events()).bar.market=="ES" and next(nq.iter_events()).bar.market=="NQ"


def test_btc_completed_boundary_and_partial_eligibility(tmp_path):
    adapter,_=btc_fixture(tmp_path);meta=adapter.validate();row=next(adapter.iter_events()).bar
    assert row.market=="BTC" and row.close_time==meta.coverage_end_exclusive
    assert meta.eligibility.smoke_replay and not meta.eligibility.training_validation
    assert not meta.eligibility.untouched_oos and meta.eligibility.classification=="PARTIAL_RESEARCH_ONLY"


def test_btc_changed_file_fails_closed(tmp_path):
    adapter,path=btc_fixture(tmp_path);path.write_text(path.read_text()+"x")
    with pytest.raises(ValueError,match="checksum"):adapter.validate()


def test_adapter_sources_are_read_only_and_network_free():
    source=(Path(__file__).parent/"core_v1"/"production_adapters.py").read_text().lower()
    assert '.open("w' not in source and "write_text" not in source and "write_bytes" not in source
    for token in ("import requests", "import httpx", "import urllib", "import socket", "import subprocess"):
        assert token not in source
