import json
from pathlib import Path

from futures_data.archive_audit import _tree_fingerprint


def test_final_archive_audit_report_is_complete_and_content_addressed():
    root=Path(__file__).resolve().parents[1];path=root/"outputs/archive_audits/es_nq_pass_b_final_audit.json"
    value=json.loads(path.read_text())
    assert value["state"]=="FINAL_ES_NQ_ARCHIVE_AUDIT_PASS"
    assert value["totals"]["requests"]==130 and value["totals"]["rows"]==877679
    assert len(value["artifact_hashes"])==650
    assert _tree_fingerprint(sorted(value["artifact_hashes"],key=lambda x:x["path"]))==value["archive_tree_sha256"]
    assert value["duplicate_count"]==0 and value["synthesized_rows"]==0 and value["continuous_adjustment"] is False


def test_tree_fingerprint_changes_for_any_hash_or_path_change():
    first=[{"path":"ES/raw/a.json","sha256":"a"*64,"bytes":1}]
    second=[{"path":"ES/raw/a.json","sha256":"b"*64,"bytes":1}]
    assert _tree_fingerprint(first)!=_tree_fingerprint(second)
