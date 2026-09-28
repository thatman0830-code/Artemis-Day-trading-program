"""Bounded read-only acquisition of Windows Time status for paper sessions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import stat
import subprocess

from execution.paper_windows_clock_evidence_v1 import (
    WindowsClockPolicyV1, WindowsClockReceiptV1, decode_windows_clock_status,
)


MAXIMUM_OUTPUT_BYTES = 16_384
QUERY_TIMEOUT_SECONDS = 5


class WindowsClockHealthSourceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ClockQueryCaptureV1:
    payload: bytes
    started_at: datetime
    completed_at: datetime
    exit_code: int
    stderr: bytes


def _plain_executable(path):
    path = Path(path)
    if not path.is_absolute() or path.name.lower() != "w32tm.exe":
        raise WindowsClockHealthSourceError("absolute w32tm executable is required")
    try: info = path.lstat()
    except OSError as exc: raise WindowsClockHealthSourceError("w32tm executable is unreadable") from exc
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or getattr(info,"st_file_attributes",0) & 0x400):
        raise WindowsClockHealthSourceError("w32tm executable is unsafe")
    return path


def query_windows_clock(executable, *, run=None, now=None):
    """Execute only `w32tm /query /status /verbose`, with no shell or mutation."""
    executable = _plain_executable(executable)
    run = subprocess.run if run is None else run
    now = (lambda:datetime.now(timezone.utc)) if now is None else now
    started = now()
    try:
        result = run([str(executable),"/query","/status","/verbose"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=QUERY_TIMEOUT_SECONDS,check=False,shell=False)
    except (OSError,subprocess.SubprocessError) as exc:
        raise WindowsClockHealthSourceError("Windows clock query failed") from exc
    completed = now()
    payload=result.stdout; error=result.stderr
    if (type(result.returncode) is not int or result.returncode != 0
            or type(payload) is not bytes or not 0 < len(payload) <= MAXIMUM_OUTPUT_BYTES
            or type(error) is not bytes or error.strip()):
        raise WindowsClockHealthSourceError("Windows clock query returned ineligible output")
    return ClockQueryCaptureV1(payload,started,completed,result.returncode,error)


def acquire_windows_clock_health(executable, *, policy, run=None, now=None):
    if not isinstance(policy,WindowsClockPolicyV1):
        raise WindowsClockHealthSourceError("reviewed clock policy is required")
    capture=query_windows_clock(executable,run=run,now=now)
    try:
        return decode_windows_clock_status(capture.payload,
            expected_sha256=hashlib.sha256(capture.payload).hexdigest(),
            query_started_at=capture.started_at,query_completed_at=capture.completed_at,
            as_of=capture.completed_at,policy=policy)
    except Exception as exc:
        raise WindowsClockHealthSourceError("Windows clock evidence rejected") from exc
