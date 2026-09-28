"""Offline clock-health and elapsed-time guard; not an OS time synchronizer."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time

MAX_GAP_NS = 5_000_000_000
MAX_DRIFT_NS = 2_000_000_000
MAX_SESSION_NS = 900_000_000_000
MAX_HEALTH_AGE = timedelta(seconds=90)
MAX_CAPTURE_NS = 100_000_000


class PaperClockError(RuntimeError):
    pass


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise PaperClockError("UTC timestamp required")


def _int(value):
    if type(value) is not int:
        raise PaperClockError("exact integer nanoseconds required")


def _ns(delta):
    return ((delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds) * 1000


@dataclass(frozen=True, slots=True)
class PaperClockSampleV1:
    utc: datetime
    monotonic_ns: int
    capture_span_ns: int = 0

    def __post_init__(self):
        _utc(self.utc); _int(self.monotonic_ns); _int(self.capture_span_ns)
        if self.monotonic_ns < 0:
            raise PaperClockError("negative monotonic clock")
        if not 0 <= self.capture_span_ns <= MAX_CAPTURE_NS:
            raise PaperClockError("clock capture span exceeded")


def capture_paper_clock(*, utc_reader=None, monotonic_reader=None):
    """Bracket one UTC read; midpoint is a pairing estimate, not time attestation."""
    utc_reader = utc_reader if utc_reader is not None else lambda: datetime.now(timezone.utc)
    monotonic_reader = monotonic_reader if monotonic_reader is not None else time.monotonic_ns
    try:
        before = monotonic_reader()
        utc = utc_reader()
        after = monotonic_reader()
        _int(before); _int(after)
        if before < 0 or after < before:
            raise PaperClockError("monotonic clock regressed during capture")
        return PaperClockSampleV1(utc, (before+after)//2, after-before)
    except PaperClockError:
        raise
    except Exception as exc:
        raise PaperClockError("local clock capture failed") from exc


@dataclass(frozen=True, slots=True)
class PaperClockHealthV1:
    observed_at: datetime
    synchronized: bool
    offset_ns: int
    uncertainty_ns: int
    source_sha256: str

    def __post_init__(self):
        _utc(self.observed_at); _int(self.offset_ns); _int(self.uncertainty_ns)
        if type(self.synchronized) is not bool or self.uncertainty_ns < 0:
            raise PaperClockError("invalid clock health fields")
        if not isinstance(self.source_sha256, str) or len(self.source_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.source_sha256):
            raise PaperClockError("clock health source SHA-256 required")


class PaperClockGuardV1:
    """Single-use, in-memory guard for caller-supplied clock observations.

    Source hashes identify evidence; they do not authenticate synchronization.
    UTC and monotonic samples must originate from a trusted local sampler.
    """
    def __init__(self):
        self.first = None
        self.last = None
        self.last_health_at = None
        self.failed = False

    def check(self, sample: PaperClockSampleV1, health: PaperClockHealthV1):
        if self.failed:
            raise PaperClockError("clock guard latched")
        try:
            if not isinstance(sample, PaperClockSampleV1) or not isinstance(health, PaperClockHealthV1):
                raise PaperClockError("typed clock sample and health required")
            if not health.synchronized or abs(health.offset_ns) + health.uncertainty_ns + sample.capture_span_ns > MAX_DRIFT_NS:
                raise PaperClockError("unsynchronized or excessive clock uncertainty")
            if not timedelta(0) <= sample.utc - health.observed_at <= MAX_HEALTH_AGE:
                raise PaperClockError("stale or future clock health")
            if self.last_health_at is not None and health.observed_at < self.last_health_at:
                raise PaperClockError("clock health chronology regressed")
            if self.last is not None:
                elapsed = sample.monotonic_ns - self.last.monotonic_ns
                if elapsed <= 0:
                    raise PaperClockError("monotonic clock did not advance")
                if elapsed > MAX_GAP_NS:
                    raise PaperClockError("loop gap exceeded")
                if sample.utc < self.last.utc:
                    raise PaperClockError("UTC clock regressed")
                total = sample.monotonic_ns - self.first.monotonic_ns
                if total >= MAX_SESSION_NS:
                    raise PaperClockError("monotonic session deadline reached")
                if abs(_ns(sample.utc-self.first.utc)-total) + sample.capture_span_ns + self.first.capture_span_ns > MAX_DRIFT_NS:
                    raise PaperClockError("UTC/monotonic divergence")
            if self.first is None:
                self.first = sample
            self.last = sample
            self.last_health_at = health.observed_at
            return sample.utc
        except Exception:
            self.failed = True
            raise


class ClockCheckedPaperSessionV1:
    """Apply the guard before driver inputs; stop on a detected clock fault.

    No independent watchdog runs here. On fault, stopping uses the last accepted
    UTC reading and is not presented as a fresh timestamp observation.
    """
    def __init__(self, session):
        self.session = session
        self.guard = PaperClockGuardV1()

    def _checked(self, sample, health):
        try:
            return self.guard.check(sample, health)
        except PaperClockError:
            self._stop_on_fault()
            raise

    def _stop_on_fault(self):
        if self.session.active:
            try:
                self.session.stop(self.guard.last.utc)
            except Exception as exc:
                raise PaperClockError("clock fault; session stop unconfirmed") from exc

    def _capture(self, utc_reader, monotonic_reader):
        try:
            return capture_paper_clock(utc_reader=utc_reader, monotonic_reader=monotonic_reader)
        except PaperClockError:
            self.guard.failed = True
            self._stop_on_fault()
            raise

    def sample_and_start(self, health, *, utc_reader=None, monotonic_reader=None):
        return self.start(self._capture(utc_reader, monotonic_reader), health)

    def _read_health(self, health_reader):
        try:
            health = health_reader()
            if not isinstance(health, PaperClockHealthV1):
                raise PaperClockError("typed clock health required")
            return health
        except Exception as exc:
            self.guard.failed = True
            self._stop_on_fault()
            raise PaperClockError("clock health acquisition failed") from exc

    def read_and_start(self, health_reader, *, utc_reader=None, monotonic_reader=None):
        return self.sample_and_start(self._read_health(health_reader),
            utc_reader=utc_reader, monotonic_reader=monotonic_reader)

    def read_and_step(self, health_reader, *, input_observed_at, command=None,
                      verified_fill=None, closed_mark=None,
                      utc_reader=None, monotonic_reader=None):
        return self.sample_and_step(self._read_health(health_reader),
            input_observed_at=input_observed_at, command=command,
            verified_fill=verified_fill, closed_mark=closed_mark,
            utc_reader=utc_reader, monotonic_reader=monotonic_reader)

    def sample_and_step(self, health, *, input_observed_at, command=None,
                        verified_fill=None, closed_mark=None,
                        utc_reader=None, monotonic_reader=None):
        reading = self._capture(utc_reader, monotonic_reader)
        return self.step(reading, health, input_observed_at=input_observed_at,
            command=command, verified_fill=verified_fill, closed_mark=closed_mark)

    def start(self, sample, health):
        return self.session.start(self._checked(sample, health))

    def step(self, sample, health, *, input_observed_at, command=None,
             verified_fill=None, closed_mark=None):
        from execution.supervised_paper_workflow_v1 import SupervisedPaperCycleV1
        now = self._checked(sample, health)
        return self.session.step(SupervisedPaperCycleV1(now, input_observed_at, command),
            verified_fill=verified_fill, closed_mark=closed_mark)
