from datetime import datetime, timezone
import hashlib, json
import pytest

from .oos_evidence import MissingIntervalV1
from .session_gap_reconciler import GapClassification, SessionGapError, reconcile_session_gaps

UTC=timezone.utc
def t(hour,minute=0): return datetime(2026,1,1,hour,minute,tzinfo=UTC)
def setup(tmp_path, *, mutate=None):
    results=[]
    for day,pre,opened,closed in (("2026-01-01",t(0),t(1),t(3)),
                                   ("2026-01-02",t(5),t(6),t(8))):
        for event,stamp in (("pre_open",pre),("open",opened),("close",closed)):
            results.append({"product_code":"ES","product_name":"E-mini ES","trading_venue":"XCME",
                            "session_end_date":day,"event":event,"timestamp":stamp.isoformat()})
    raw={"status":"OK","results":results}
    if mutate: mutate(raw)
    schedule=tmp_path/"evidence"/"ES"/"raw"/"schedules.json";schedule.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(raw).encode();schedule.write_bytes(payload)
    manifest=tmp_path/"evidence"/"ES"/"manifests"/"schedules.json";manifest.parent.mkdir(parents=True,exist_ok=True)
    value={"schema_version":"x","root":"ES","endpoint_class":"futures_schedules","http_status":200,
           "raw_bytes":len(payload),"raw_sha256":hashlib.sha256(payload).hexdigest(),
           "raw_relative_path":"ES/raw/schedules.json","automatic_retry":False}
    manifest.write_text(json.dumps(value),encoding="utf-8")
    return "evidence/ES/raw/schedules.json","evidence/ES/manifests/schedules.json"
def run(tmp_path,gaps,**kwargs):
    schedule,manifest=setup(tmp_path,**kwargs)
    return reconcile_session_gaps(repository=tmp_path,schedule_relative_path=schedule,
        manifest_relative_path=manifest,market="ES",product_name="E-mini ES",gaps=tuple(gaps))
def gap(start,end): return MissingIntervalV1("1m",start,end,"UNCLASSIFIED_ARCHIVE_DISCONTINUITY")

def test_closed_open_and_mixed_classification(tmp_path):
    result=run(tmp_path,(gap(t(3),t(6)),gap(t(1,30),t(2)),gap(t(2,30),t(3,30))))
    assert tuple(x.classification for x in result.gaps)==(
        GapClassification.SCHEDULED_NON_TRADING_INTERVAL,
        GapClassification.MISSING_OPEN_SESSION_DATA,GapClassification.MIXED_REQUIRES_SPLIT)
    assert result.trading_authority is False

def test_exact_hashes_and_determinism(tmp_path):
    args=(gap(t(3),t(6)),); a=run(tmp_path,args)
    schedule=tmp_path/"evidence/ES/raw/schedules.json";manifest=tmp_path/"evidence/ES/manifests/schedules.json"
    assert a.schedule_sha256==hashlib.sha256(schedule.read_bytes()).hexdigest()
    assert a.schedule_manifest_sha256==hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert a==reconcile_session_gaps(repository=tmp_path,schedule_relative_path="evidence/ES/raw/schedules.json",
        manifest_relative_path="evidence/ES/manifests/schedules.json",market="ES",product_name="E-mini ES",gaps=args)

@pytest.mark.parametrize("change",[
 lambda r:r.update(status="ERROR"), lambda r:r.update(next_url="https://example.invalid"),
 lambda r:r["results"].pop(), lambda r:r["results"].append(dict(r["results"][1])),
 lambda r:r["results"][0].update(trading_venue="OTHER"),
 lambda r:r["results"][2].update(timestamp=t(0).isoformat()),
])
def test_incomplete_or_conflicting_schedule_rejects(tmp_path,change):
    with pytest.raises(SessionGapError): run(tmp_path,(gap(t(3),t(6)),),mutate=change)

def test_tampered_schedule_rejects(tmp_path):
    schedule,manifest=setup(tmp_path);(tmp_path/schedule).write_bytes((tmp_path/schedule).read_bytes()+b" ")
    with pytest.raises(SessionGapError): reconcile_session_gaps(repository=tmp_path,schedule_relative_path=schedule,
        manifest_relative_path=manifest,market="ES",product_name="E-mini ES",gaps=())

def test_outside_coverage_and_wrong_timeframe_reject(tmp_path):
    with pytest.raises(SessionGapError): run(tmp_path,(gap(t(0),t(1)),))
    wrong=MissingIntervalV1("5m",t(3),t(6),"x")
    with pytest.raises(SessionGapError): run(tmp_path,(wrong,))

def test_wrong_product_or_market_rejects(tmp_path):
    schedule,manifest=setup(tmp_path)
    with pytest.raises(SessionGapError): reconcile_session_gaps(repository=tmp_path,
        schedule_relative_path=schedule,manifest_relative_path=manifest,market="NQ",
        product_name="E-mini ES",gaps=())
    with pytest.raises(SessionGapError): reconcile_session_gaps(repository=tmp_path,
        schedule_relative_path=schedule,manifest_relative_path=manifest,market="ES",
        product_name="other",gaps=())
