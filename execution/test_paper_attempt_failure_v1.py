import json
from pathlib import Path

import pytest

from execution.paper_attempt_failure_v1 import (
    PaperAttemptFailureError,classify_failure,write_failure,
)
from execution.paper_clock_guard_v1 import PaperClockError
from execution.supervised_btc_paper_session_controller_v1 import BTCPaperSessionControllerError


@pytest.mark.parametrize("error,code",[
    (PaperClockError("detail"),"CLOCK_FAILURE"),
    (BTCPaperSessionControllerError("blocked","RECORDER_FAILURE"),"RECORDER_FAILURE"),
    (RuntimeError("secret diagnostic"),"FAILED_CLOSED_UNCLASSIFIED"),
])
def test_classification_uses_fixed_codes(error,code):
    assert classify_failure(error)==code


def test_failure_artifact_is_sanitized_hash_bound_and_idempotent(tmp_path):
    root=tmp_path/"session";root.mkdir();(root/"latest-health.json").write_text("health")
    first=write_failure(root,RuntimeError("credential=must-not-appear"))
    second=write_failure(root,RuntimeError("different detail"))
    assert first==second
    document=json.loads(first.read_text());payload=document["payload"]
    assert payload["failure_code"]=="FAILED_CLOSED_UNCLASSIFIED"
    assert "credential" not in first.read_text()
    assert payload["evidence_sha256"]["latest-health.json"] is not None
    assert payload["trading_authority"] is False


def test_existing_conflicting_failure_artifact_cannot_be_overwritten(tmp_path):
    root=tmp_path/"session";root.mkdir();(root/"attempt-failure.json").write_text("{}")
    with pytest.raises(PaperAttemptFailureError,match="immutable"):
        write_failure(root,RuntimeError())


def test_module_has_no_transport_or_exception_message_persistence():
    source=Path(__file__).with_name("paper_attempt_failure_v1.py").read_text().lower()
    for prohibited in ("requests","urllib","websocket","place_order","submit_order","str(exc)"):
        assert prohibited not in source
    assert '"trading_authority":false' in source
