from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from execution.windows_clock_health_source_v1 import (
    MAXIMUM_OUTPUT_BYTES, WindowsClockHealthSourceError,
    acquire_windows_clock_health, query_windows_clock,
)
from execution.test_paper_performance_ledger_v1 import T
from execution.test_paper_windows_clock_evidence_v1 import RAW, policy


def executable(tmp_path):
    path=tmp_path/"w32tm.exe";path.write_bytes(b"fixture");return path.resolve()


def runner(stdout=RAW,stderr=b"",code=0,observed=None):
    def run(args,**kwargs):
        if observed is not None: observed.append((args,kwargs))
        return SimpleNamespace(stdout=stdout,stderr=stderr,returncode=code)
    return run


def times(seconds=1):
    values=iter((T,T+timedelta(seconds=seconds)));return lambda:next(values)


def test_exact_read_only_command_and_decoder_binding(tmp_path):
    seen=[];path=executable(tmp_path)
    receipt=acquire_windows_clock_health(path,policy=policy(),run=runner(observed=seen),now=times())
    args,kwargs=seen[0]
    assert args==[str(path),"/query","/status","/verbose"]
    assert kwargs["shell"] is False and kwargs["check"] is False
    assert receipt.source=="time.windows.com,0x8" and receipt.health.synchronized
    assert receipt.trading_authority is False


@pytest.mark.parametrize("stdout,stderr,code",[(b"",b"",0),(b"x"*(MAXIMUM_OUTPUT_BYTES+1),b"",0),
    (RAW,b"error",0),(RAW,b"",1)])
def test_bad_process_results_reject(tmp_path,stdout,stderr,code):
    with pytest.raises(WindowsClockHealthSourceError,match="ineligible"):
        query_windows_clock(executable(tmp_path),run=runner(stdout,stderr,code),now=times())


def test_timeout_and_launch_failure_reject(tmp_path):
    def fail(*_,**__): raise OSError("failed")
    with pytest.raises(WindowsClockHealthSourceError,match="query failed"):
        query_windows_clock(executable(tmp_path),run=fail,now=times())


@pytest.mark.parametrize("name",["other.exe","w32tm.cmd"])
def test_only_absolute_w32tm_executable_is_accepted(tmp_path,name):
    path=tmp_path/name;path.write_bytes(b"x")
    with pytest.raises(WindowsClockHealthSourceError,match="absolute w32tm"):
        query_windows_clock(path.resolve(),run=runner(),now=times())
    with pytest.raises(WindowsClockHealthSourceError,match="absolute w32tm"):
        query_windows_clock(Path("w32tm.exe"),run=runner(),now=times())


def test_decoder_failure_is_fail_closed(tmp_path):
    with pytest.raises(WindowsClockHealthSourceError,match="evidence rejected"):
        acquire_windows_clock_health(executable(tmp_path),policy=policy(),
            run=runner(stdout=RAW.replace(b"Last Sync Error: 0",b"Last Sync Error: 1")),now=times())


def test_query_over_five_seconds_rejects_at_decoder(tmp_path):
    with pytest.raises(WindowsClockHealthSourceError,match="evidence rejected"):
        acquire_windows_clock_health(executable(tmp_path),policy=policy(),run=runner(),now=times(6))


def test_requires_typed_reviewed_policy(tmp_path):
    with pytest.raises(WindowsClockHealthSourceError,match="reviewed"):
        acquire_windows_clock_health(executable(tmp_path),policy=None,run=runner(),now=times())
