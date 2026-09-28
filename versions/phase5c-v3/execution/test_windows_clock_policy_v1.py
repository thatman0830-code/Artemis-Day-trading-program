import json
from dataclasses import replace

import pytest

from execution.windows_clock_policy_v1 import WindowsClockPolicyError,read_windows_clock_policy


CANDIDATE="windows_clock_policy_candidate_v1.json"
APPROVED="windows_clock_policy_approved_v1.json"


def source(): return __import__("pathlib").Path(__file__).with_name(CANDIDATE)


def test_candidate_is_valid_but_cannot_authorize_runtime():
    policy=read_windows_clock_policy(source(),require_approved=False)
    assert policy.allowed_sources==("time.windows.com,0x8",)
    assert policy.local_uncertainty_ns==100_000_000 and policy.drift_ns_per_second==15_000
    with pytest.raises(WindowsClockPolicyError,match="not owner-approved"):
        read_windows_clock_policy(source())


def test_distinct_owner_approved_policy_is_runtime_eligible():
    candidate=read_windows_clock_policy(source(),require_approved=False)
    approved=read_windows_clock_policy(source().with_name(APPROVED))
    assert approved.allowed_sources==candidate.allowed_sources
    assert approved.local_uncertainty_ns==candidate.local_uncertainty_ns
    assert approved.drift_ns_per_second==candidate.drift_ns_per_second
    assert approved.evidence_sha256!=candidate.evidence_sha256


@pytest.mark.parametrize("field,value",[("approval_state","APPROVED"),
    ("trading_authority",True),("local_uncertainty_ns",0),
    ("drift_ns_per_second",14999),("allowed_sources",[]),("unexpected",1)])
def test_tampering_or_invalid_assumptions_reject(tmp_path,field,value):
    document=json.loads(source().read_text());document[field]=value
    path=tmp_path/"policy.json";path.write_text(json.dumps(document))
    with pytest.raises(WindowsClockPolicyError):read_windows_clock_policy(path,require_approved=False)


def test_owner_approved_label_requires_matching_new_identity(tmp_path):
    document=json.loads(source().read_text());document["approval_state"]="OWNER_APPROVED"
    path=tmp_path/"policy.json";path.write_text(json.dumps(document))
    with pytest.raises(WindowsClockPolicyError,match="identity"):
        read_windows_clock_policy(path)


def test_missing_malformed_and_nonobject_reject(tmp_path):
    for body in ("{", "[]", "null"):
        path=tmp_path/(str(len(body))+".json");path.write_text(body)
        with pytest.raises(WindowsClockPolicyError):read_windows_clock_policy(path)
    with pytest.raises(WindowsClockPolicyError):read_windows_clock_policy(tmp_path/"missing.json")
