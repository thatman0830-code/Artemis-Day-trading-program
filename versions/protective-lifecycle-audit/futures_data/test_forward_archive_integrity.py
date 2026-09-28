from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import pytest

from futures_data.forward_archive_integrity import ForwardArchiveIntegrityError, audit_forward_archive


def put(path, value): path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(value)
def dump(path,value): put(path,(json.dumps(value,sort_keys=True)+"\n").encode())


def archive(tmp_path):
    for root,ticker in (("ES","ESU6"),("NQ","NQU6")):
        base=tmp_path/"data/futures_forward"/root; stem=f"2026-08-28-{ticker}"
        raw=b"{}\n"; normalized=(json.dumps({"root":root,"ticker":ticker,"session_date":"2026-08-28","contract_id":"c","window_start_ns":1,"volume":"2"})+"\n").encode()
        put(base/"raw"/(stem+".json"),raw);put(base/"normalized"/(stem+".jsonl"),normalized)
        common={"schema_version":"es-nq-delayed-forward-v1","root":root,"ticker":ticker,"session_date":"2026-08-28","contract_id":"c","run_id":"r","raw_relative_path":f"raw/{stem}.json","raw_sha256":sha256(raw).hexdigest(),"raw_bytes":len(raw)}
        pending={**common};dump(base/"pending"/(stem+".json"),pending)
        manifest={**common,"normalized_relative_path":f"normalized/{stem}.jsonl","normalized_sha256":sha256(normalized).hexdigest(),"normalized_bytes":len(normalized),"normalized_rows":1,"observed_volume":"2","missing_aggregate_minutes":0}
        mp=base/"manifests"/(stem+".json");dump(mp,manifest)
        dump(base/"checkpoints"/(stem+".json"),{"schema_version":"es-nq-delayed-forward-v1","root":root,"ticker":ticker,"session_date":"2026-08-28","manifest_relative_path":f"manifests/{stem}.json","manifest_sha256":sha256(mp.read_bytes()).hexdigest()})
    return tmp_path


def test_complete_archive_is_deterministic_and_nontrading(tmp_path):
    first=audit_forward_archive(archive(tmp_path));second=audit_forward_archive(tmp_path)
    assert first==second and first.state=="VERIFIED" and first.session_count==2 and not first.trading_authority


@pytest.mark.parametrize("target",("raw","normalized","pending","manifest","checkpoint"))
def test_missing_or_altered_artifact_fails_closed(tmp_path,target):
    archive(tmp_path); base=tmp_path/"data/futures_forward/ES"; suffix=".jsonl" if target=="normalized" else ".json"
    folder={"manifest":"manifests","checkpoint":"checkpoints"}.get(target,target)
    path=next((base/folder).glob("*"+suffix)); path.unlink()
    with pytest.raises(ForwardArchiveIntegrityError): audit_forward_archive(tmp_path)


def test_checksum_row_count_identity_chronology_and_volume_fail_closed(tmp_path):
    archive(tmp_path); path=next((tmp_path/"data/futures_forward/ES/normalized").glob("*.jsonl"))
    original=path.read_text(); path.write_text(original+original)
    with pytest.raises(ForwardArchiveIntegrityError): audit_forward_archive(tmp_path)


def test_unexpected_extra_artifact_fails_closed(tmp_path):
    archive(tmp_path); dump(tmp_path/"data/futures_forward/ES/raw/extra.json",{})
    with pytest.raises(ForwardArchiveIntegrityError,match="inventory"): audit_forward_archive(tmp_path)
