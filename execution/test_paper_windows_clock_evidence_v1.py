from dataclasses import replace, FrozenInstanceError
from datetime import timedelta
import hashlib

import pytest

from execution.paper_windows_clock_evidence_v1 import WindowsClockPolicyV1, decode_windows_clock_status
from execution.paper_clock_guard_v1 import PaperClockError, PaperClockGuardV1, ClockCheckedPaperSessionV1
from execution.test_paper_clock_guard_v1 import sample
from execution.test_paper_performance_ledger_v1 import T, H


# Synthetic decoder fixture, NOT retained operational evidence or approved policy.
RAW = b'''Leap Indicator: 0(no warning)
Stratum: 5 (secondary reference)
Precision: -23 (119.209ns per tick)
Root Delay: 0.1000000s
Root Dispersion: 0.0100000s
Last Successful Sync Time: 9/1/2026 12:00:00 AM
Source: time.windows.com,0x8
Phase Offset: -0.0000107s
Last Sync Error: 0 (The command completed successfully.)
Time since Last Good Sync Time: 10.0000000s
'''


def policy():
    return WindowsClockPolicyV1(("time.windows.com,0x8",), 100_000_000, 15_000, H("synthetic policy"))


def decode(payload=RAW, **kwargs):
    args = dict(expected_sha256=hashlib.sha256(payload).hexdigest(),
                query_started_at=T, query_completed_at=T, as_of=T, policy=policy())
    args.update(kwargs)
    return decode_windows_clock_status(payload, **args)


def test_exact_mapping_immutable_and_deterministic():
    receipt = decode()
    assert receipt == decode()
    assert receipt.health.offset_ns == -10700
    assert receipt.root_distance_ns == 60_000_000
    assert receipt.precision_ns == 120
    assert receipt.age_allowance_ns == 1_500_000
    assert receipt.health.uncertainty_ns == 161_500_120
    assert receipt.trading_authority is False
    assert PaperClockGuardV1().check(sample(), receipt.health) == T
    with pytest.raises(FrozenInstanceError):
        receipt.source = "changed"
    with pytest.raises(PaperClockError):
        replace(receipt,trading_authority=True)


@pytest.mark.parametrize("old,new", [
    (b"Leap Indicator: 0",b"Leap Indicator: 3"),
    (b"Stratum: 5",b"Stratum: 0"),
    (b"Last Sync Error: 0",b"Last Sync Error: 1"),
    (b"time.windows.com,0x8",b"Free-running System Clock"),
    (b"time.windows.com,0x8",b"unapproved.example"),
    (b"0.1000000s",b"-0.1000000s"),
    (b"0.0100000s",b"NaNs"),
    (b"0.0100000s",b"0,0100000s"),
    (b"10.0000000s",b"86401s"),
    (b"9/1/2026 12:00:00 AM",b"unspecified"),
    (b"Precision: -23",b"Precision: -99"),
    (b"Root Delay:",b"Localized Delay:"),
])
def test_bad_or_unsupported_status_rejects(old,new):
    with pytest.raises(PaperClockError):
        decode(RAW.replace(old,new))


def test_duplicate_missing_hash_encoding_and_size_reject():
    for payload in (RAW+b"Root Delay: 0.1s\n", RAW.replace(b"Source:",b"Missing:"),
                    b"\xff", b"x"*16385, b""):
        with pytest.raises(PaperClockError):
            decode(payload)
    with pytest.raises(PaperClockError,match="hash mismatch"):
        decode(expected_sha256="a"*64)


@pytest.mark.parametrize("kwargs", [dict(as_of=T-timedelta(seconds=1)),
    dict(as_of=T+timedelta(seconds=91)), dict(query_started_at=T+timedelta(seconds=1)),
    dict(query_started_at=T-timedelta(seconds=6)), dict(query_started_at=T.replace(tzinfo=None))])
def test_capture_chronology_and_freshness(kwargs):
    with pytest.raises(PaperClockError):
        decode(**kwargs)


def test_uncertainty_and_capture_latency_reach_existing_guard():
    receipt = decode(RAW.replace(b"0.0100000s",b"7.7701956s"))
    with pytest.raises(PaperClockError,match="uncertainty"):
        PaperClockGuardV1().check(sample(),receipt.health)
    delayed = decode(query_started_at=T-timedelta(seconds=2))
    with pytest.raises(PaperClockError,match="uncertainty"):
        PaperClockGuardV1().check(sample(),delayed.health)


def test_health_lifetime_reserved_and_policy_bound_in_identity():
    first = decode()
    assert decode(as_of=T+timedelta(seconds=90)) == first
    assert decode(policy=replace(policy(),local_uncertainty_ns=100_000_001)).health.source_sha256 != first.health.source_sha256
    assert decode(policy=replace(policy(),evidence_sha256=H("different"))).health.source_sha256 != first.health.source_sha256
    assert decode(RAW.replace(b"\n",b"\r\n")).health.source_sha256 != first.health.source_sha256


@pytest.mark.parametrize("kwargs", [dict(local_uncertainty_ns=0),dict(local_uncertainty_ns=True),
    dict(drift_ns_per_second=14999),dict(drift_ns_per_second=15000.0),
    dict(allowed_sources=()),dict(allowed_sources=["time.windows.com,0x8"]),dict(evidence_sha256="")])
def test_no_silent_policy_defaults(kwargs):
    with pytest.raises(PaperClockError):
        replace(policy(),**kwargs)


def test_decoder_failure_stops_active_session_before_command(tmp_path):
    from execution.test_bounded_paper_session_v1 import driver, submit
    session = driver(tmp_path)
    wrapper = ClockCheckedPaperSessionV1(session)
    wrapper.read_and_start(lambda:decode().health,utc_reader=lambda:T,monotonic_reader=lambda:0)
    def invalid():
        return decode(RAW+b"Source: conflict\n").health
    with pytest.raises(PaperClockError,match="acquisition failed"):
        wrapper.read_and_step(invalid,input_observed_at=T,command=submit(session))
    assert not session.active
    assert wrapper.guard.failed
    adapter = session.workflow.store.load()
    assert not adapter.gateway.connected
    assert adapter.gateway.records == ()


def test_reader_failure_before_start_does_not_create_checkpoint(tmp_path):
    from execution.test_bounded_paper_session_v1 import driver
    session = driver(tmp_path)
    wrapper = ClockCheckedPaperSessionV1(session)
    with pytest.raises(PaperClockError,match="acquisition failed"):
        wrapper.read_and_start(lambda:None)
    assert not session.active
    assert not session.workflow.lock_path.exists()
