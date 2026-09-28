"""Sanitized, immutable failure evidence for supervised paper attempts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


SCHEMA = "paper-attempt-failure-v1"
CODES = {"CLOCK_FAILURE","PERSISTENCE_FAILURE","RISK_LIMIT",
         "RECONCILIATION_FAILURE","SESSION_SAFETY_FAILURE","LAUNCH_FAILURE",
         "RUNTIME_FAILURE","STALE_OPERATIONAL_HEALTH","RECORDER_FAILURE",
         "WATCHDOG_FAILURE","RECORDER_GAP","CONTROLLER_FAILURE",
         "FAILED_CLOSED_UNCLASSIFIED"}


class PaperAttemptFailureError(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode()


def classify_failure(exc: BaseException) -> str:
    chain=[];current=exc
    while current is not None and current not in chain:
        chain.append(current);current=current.__cause__ or current.__context__
    for item in chain:
        code=getattr(item,"failure_code",None)
        if code in CODES:return code
    names={type(item).__name__ for item in chain}
    if "PaperClockError" in names:return "CLOCK_FAILURE"
    if names & {"PaperPerformanceError","PaperPerformanceCheckpointError",
                "PaperAdapterCheckpointError","PaperCheckpointError"}:
        return "PERSISTENCE_FAILURE"
    if "BoundedPaperSessionError" in names:
        message=str(next(item for item in chain if type(item).__name__=="BoundedPaperSessionError"))
        if any(word in message for word in ("limit","exposure","notional","capacity","budget")):
            return "RISK_LIMIT"
        if "reconcil" in message:return "RECONCILIATION_FAILURE"
        return "SESSION_SAFETY_FAILURE"
    if "SupervisedBTCPaperLauncherError" in names:return "LAUNCH_FAILURE"
    if "SupervisedPaperRuntimeError" in names:return "RUNTIME_FAILURE"
    return "FAILED_CLOSED_UNCLASSIFIED"


def write_failure(session_root: Path, exc: BaseException) -> Path:
    root=Path(session_root).resolve()
    if not root.is_dir() or root.is_symlink():
        raise PaperAttemptFailureError("safe session directory required")
    evidence={}
    for name in ("latest-health.json","adapter-checkpoint.json",
                 "performance-checkpoint.json","canonical-strategy-status.json"):
        path=root/name
        evidence[name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    payload={"schema_version":SCHEMA,"session_directory":root.name,
             "failure_code":classify_failure(exc),"evidence_sha256":evidence,
             "advisory_only":True,"live_trading_permitted":False,
             "trading_authority":False}
    document={"schema_version":SCHEMA,"payload":payload,
              "payload_sha256":hashlib.sha256(_canonical(payload)).hexdigest()}
    raw=_canonical(document)+b"\n";path=root/"attempt-failure.json"
    if path.exists():
        if path.read_bytes()==raw:return path
        raise PaperAttemptFailureError("immutable failure evidence already exists")
    temporary=root/f".attempt-failure.{os.getpid()}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        try:os.link(temporary,path)
        except FileExistsError as cause:
            raise PaperAttemptFailureError("immutable failure evidence already exists")from cause
    finally:temporary.unlink(missing_ok=True)
    return path
