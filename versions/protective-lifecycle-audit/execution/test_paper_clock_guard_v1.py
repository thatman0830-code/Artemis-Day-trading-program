from dataclasses import replace
from datetime import timedelta

import pytest

from execution.paper_clock_guard_v1 import (
    PaperClockError, PaperClockGuardV1, PaperClockSampleV1, PaperClockHealthV1, capture_paper_clock,
)
from execution.test_paper_performance_ledger_v1 import T, H


def sample(seconds=0, wall=None):
    return PaperClockSampleV1(T+timedelta(seconds=seconds if wall is None else wall),
        1_000_000_000 + seconds*1_000_000_000)


def health(seconds=0):
    return PaperClockHealthV1(T+timedelta(seconds=seconds), True, 0, 0, H("clock"))


def test_aligned_clock_and_fresh_evidence_pass():
    guard = PaperClockGuardV1()
    assert guard.check(sample(), health()) == T
    assert guard.check(sample(5), health(5)) == T+timedelta(seconds=5)
    assert not guard.failed


@pytest.mark.parametrize("change", [dict(synchronized=False), dict(offset_ns=2_000_000_001),
    dict(offset_ns=-2_000_000_000, uncertainty_ns=1), dict(uncertainty_ns=2_000_000_001),
    dict(observed_at=T+timedelta(seconds=1)), dict(observed_at=T-timedelta(seconds=91))])
def test_bad_clock_health_latches(change):
    guard = PaperClockGuardV1()
    with pytest.raises(PaperClockError):
        guard.check(sample(), replace(health(), **change))
    with pytest.raises(PaperClockError, match="latched"):
        guard.check(sample(), health())


@pytest.mark.parametrize("reading,reason", [(sample(),"did not advance"),
    (sample(6),"loop gap"), (sample(1,wall=-1),"regressed"),
    (sample(1,wall=4),"divergence"), (sample(3,wall=0),"divergence")])
def test_regression_jump_freeze_and_stall_detected(reading, reason):
    guard = PaperClockGuardV1(); guard.check(sample(),health(-10))
    with pytest.raises(PaperClockError, match=reason):
        guard.check(reading, health(-1) if reason == "regressed" else health())
    assert guard.failed


def test_small_per_step_drift_cannot_evade_anchor_check():
    guard = PaperClockGuardV1(); guard.check(sample(),health())
    for sec in range(1,5):
        guard.check(sample(sec, wall=sec*1.5), health())
    with pytest.raises(PaperClockError, match="divergence"):
        guard.check(sample(5,wall=7.5),health())


def test_monotonic_deadline_cannot_be_extended_by_health_refresh():
    guard = PaperClockGuardV1()
    for sec in range(0,900,5):
        guard.check(sample(sec),health(sec))
    with pytest.raises(PaperClockError, match="deadline"):
        guard.check(sample(900),health(900))


def test_health_age_and_uncertainty_equality_boundaries():
    guard = PaperClockGuardV1()
    allowed = replace(health(-90), offset_ns=1_000_000_000, uncertainty_ns=1_000_000_000)
    guard.check(sample(),allowed)
    assert not guard.failed


@pytest.mark.parametrize("value", [True, 1.0, -1])
def test_invalid_monotonic_types_reject(value):
    with pytest.raises(PaperClockError):
        PaperClockSampleV1(T,value)


def test_naive_utc_and_missing_source_reject():
    with pytest.raises(PaperClockError):
        PaperClockSampleV1(T.replace(tzinfo=None),0)
    with pytest.raises(PaperClockError):
        replace(health(),source_sha256="")


def test_wrapper_stops_driver_before_forwarding_stalled_input(tmp_path):
    from execution.paper_clock_guard_v1 import ClockCheckedPaperSessionV1
    from execution.test_bounded_paper_session_v1 import driver, submit
    session = driver(tmp_path)
    wrapper = ClockCheckedPaperSessionV1(session)
    wrapper.start(sample(),health())
    wrapper.step(sample(1),health(1),input_observed_at=T+timedelta(seconds=1))
    command = submit(session)
    with pytest.raises(PaperClockError, match="loop gap"):
        wrapper.step(sample(7),health(7),input_observed_at=T+timedelta(seconds=7),command=command)
    assert not session.active
    assert not session.workflow.store.load().gateway.connected
    assert session.workflow.store.load().gateway.records == ()
    assert not session.workflow.lock_path.exists()


def test_wrapper_never_claims_stop_success_after_write_failure(tmp_path, monkeypatch):
    from execution.paper_clock_guard_v1 import ClockCheckedPaperSessionV1
    from execution.test_bounded_paper_session_v1 import driver
    session = driver(tmp_path); wrapper = ClockCheckedPaperSessionV1(session)
    wrapper.start(sample(),health())
    def cannot_stop(now):
        raise OSError("injected stop failure")
    with monkeypatch.context() as scoped:
        scoped.setattr(session,"stop",cannot_stop)
        with pytest.raises(PaperClockError, match="stop unconfirmed"):
            wrapper.step(sample(6),health(6),input_observed_at=T)
        assert session.active
        assert wrapper.guard.failed
    session.stop(T)


def test_capture_brackets_utc_read_and_retains_span():
    calls = []
    numbers = iter([1_000_000_000, 1_000_000_010])
    def mono():
        calls.append("mono"); return next(numbers)
    def utc():
        calls.append("utc"); return T
    captured = capture_paper_clock(utc_reader=utc,monotonic_reader=mono)
    assert calls == ["mono","utc","mono"]
    assert captured.utc == T
    assert captured.monotonic_ns == 1_000_000_005
    assert captured.capture_span_ns == 10


@pytest.mark.parametrize("pair", [(10,9), (-1,0), (0,100_000_001), (True,2), (0,1.0)])
def test_invalid_capture_rejected(pair):
    numbers = iter(pair)
    with pytest.raises(PaperClockError):
        capture_paper_clock(utc_reader=lambda:T,monotonic_reader=lambda:next(numbers))


def test_capture_latency_consumes_uncertainty_budget():
    numbers = iter([0,100_000_000])
    reading = capture_paper_clock(utc_reader=lambda:T,monotonic_reader=lambda:next(numbers))
    assert reading.capture_span_ns == 100_000_000
    guard = PaperClockGuardV1()
    with pytest.raises(PaperClockError,match="uncertainty"):
        guard.check(reading,replace(health(),offset_ns=1_950_000_000))


def test_capture_exception_stops_session_before_input(tmp_path):
    from execution.paper_clock_guard_v1 import ClockCheckedPaperSessionV1
    from execution.test_bounded_paper_session_v1 import driver
    session=driver(tmp_path); wrapper=ClockCheckedPaperSessionV1(session)
    numbers=iter([0,10])
    wrapper.sample_and_start(health(),utc_reader=lambda:T,monotonic_reader=lambda:next(numbers))
    def fail():
        raise OSError("reader failed")
    with pytest.raises(PaperClockError,match="capture failed") as error:
        wrapper.sample_and_step(health(),input_observed_at=T,utc_reader=fail,monotonic_reader=lambda:100)
    assert isinstance(error.value.__cause__,OSError)
    assert not session.active
    assert wrapper.guard.failed
    assert not session.workflow.store.load().gateway.connected


def test_sampled_wrapper_forwards_healthy_input(tmp_path):
    from execution.paper_clock_guard_v1 import ClockCheckedPaperSessionV1
    from execution.test_bounded_paper_session_v1 import driver
    session=driver(tmp_path); wrapper=ClockCheckedPaperSessionV1(session)
    readings=iter([0,0,1_000_000_000,1_000_000_010])
    mono=lambda:next(readings)
    wrapper.sample_and_start(health(),utc_reader=lambda:T,monotonic_reader=mono)
    now=T+timedelta(seconds=1)
    _,_,status,_=wrapper.sample_and_step(health(1),input_observed_at=now,
        utc_reader=lambda:now,monotonic_reader=mono)
    assert status.state.value == "HEALTHY"
    session.stop(now)
