"""Content-addressed deployment policy boundary for Windows clock evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from execution.paper_windows_clock_evidence_v1 import WindowsClockPolicyV1

VERSION="windows-paper-clock-policy-v1"


class WindowsClockPolicyError(ValueError): pass


def _canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"))


def read_windows_clock_policy(path, *, require_approved=True):
    try: value=json.loads(Path(path).read_text("utf-8"))
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise WindowsClockPolicyError("clock policy is unreadable") from exc
    fields={"schema_version","allowed_sources","local_uncertainty_ns",
        "drift_ns_per_second","approval_state","trading_authority","policy_id"}
    if not isinstance(value,dict) or set(value)!=fields or value["schema_version"]!=VERSION:
        raise WindowsClockPolicyError("clock policy shape or version is invalid")
    supplied=value["policy_id"];body={key:item for key,item in value.items() if key!="policy_id"}
    if (not isinstance(supplied,str) or supplied!=hashlib.sha256(_canonical(body).encode()).hexdigest()
            or value["approval_state"] not in ("CANDIDATE","OWNER_APPROVED")
            or value["trading_authority"] is not False):
        raise WindowsClockPolicyError("clock policy identity or authority is invalid")
    if require_approved and value["approval_state"]!="OWNER_APPROVED":
        raise WindowsClockPolicyError("clock policy is not owner-approved")
    try:
        return WindowsClockPolicyV1(tuple(value["allowed_sources"]),
            value["local_uncertainty_ns"],value["drift_ns_per_second"],supplied)
    except (TypeError,ValueError) as exc:
        raise WindowsClockPolicyError("clock policy assumptions are invalid") from exc
