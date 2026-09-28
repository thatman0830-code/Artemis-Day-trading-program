"""Pure decoder for English W32Time status bytes; never queries or sets a clock."""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_UP
import hashlib
import json
import re

from execution.paper_clock_guard_v1 import PaperClockError, PaperClockHealthV1, _utc


@dataclass(frozen=True, slots=True)
class WindowsClockPolicyV1:
    # These are reviewed deployment assumptions, NOT measurements or approval flags.
    allowed_sources: tuple[str, ...]
    local_uncertainty_ns: int
    drift_ns_per_second: int
    evidence_sha256: str

    def __post_init__(self):
        if (type(self.allowed_sources) is not tuple or not self.allowed_sources
                or any(type(s) is not str or not s.strip() or s != s.strip()
                       for s in self.allowed_sources)
                or len(set(self.allowed_sources)) != len(self.allowed_sources)):
            raise PaperClockError("explicit unique clock source allowlist required")
        if (type(self.local_uncertainty_ns) is not int or self.local_uncertainty_ns <= 0
                or type(self.drift_ns_per_second) is not int or self.drift_ns_per_second < 15_000):
            raise PaperClockError("explicit positive local uncertainty and drift allowance required")
        _sha(self.evidence_sha256)


def _sha(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise PaperClockError("canonical SHA-256 required")


@dataclass(frozen=True, slots=True)
class WindowsClockReceiptV1:
    health: PaperClockHealthV1
    raw_sha256: str
    policy_sha256: str
    source: str
    root_distance_ns: int
    precision_ns: int
    age_allowance_ns: int
    trading_authority: bool = False

    def __post_init__(self):
        if self.trading_authority is not False:
            raise PaperClockError("clock evidence grants no trading authority")


def decode_windows_clock_status(payload, *, expected_sha256, query_started_at,
                                query_completed_at, as_of, policy):
    """Map a trusted, bounded query capture into health with explicit assumptions.

    Hashes bind bytes and policy; they do not authenticate the source or approve
    assumptions. Root distance is an estimate, not a certified accuracy bound.
    """
    _sha(expected_sha256)
    if type(payload) is not bytes or not 0 < len(payload) <= 16_384:
        raise PaperClockError("bounded raw status bytes required")
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise PaperClockError("clock status hash mismatch")
    if not isinstance(policy, WindowsClockPolicyV1):
        raise PaperClockError("reviewed clock policy required")
    for value in (query_started_at, query_completed_at, as_of):
        _utc(value)
    duration = query_completed_at - query_started_at
    if not timedelta(0) <= duration <= timedelta(seconds=5):
        raise PaperClockError("invalid clock query duration")
    if not timedelta(0) <= as_of-query_completed_at <= timedelta(seconds=90):
        raise PaperClockError("stale or future clock query")
    try:
        raw = payload.decode("utf-8")
    except UnicodeError as exc:
        raise PaperClockError("unsupported clock status encoding") from exc

    def field(name):
        matches = re.findall(r"^" + re.escape(name) + r":[ \t]*(.*?)[ \t]*\r?$", raw, re.M)
        if len(matches) != 1 or not matches[0]:
            raise PaperClockError("missing or duplicate clock field: " + name)
        return matches[0]

    def code(name):
        match = re.fullmatch(r"([0-9]+)(?:\s*\([^\r\n]*\))?", field(name))
        if match is None:
            raise PaperClockError("invalid clock code: " + name)
        return int(match[1])

    def seconds(name, signed=False):
        value = field(name)
        pattern = r"[+-]?[0-9]{1,10}(?:\.[0-9]{1,9})?s" if signed else r"[0-9]{1,10}(?:\.[0-9]{1,9})?s"
        if re.fullmatch(pattern, value) is None:
            raise PaperClockError("invalid clock seconds: " + name)
        return Decimal(value[:-1])

    source = field("Source")
    if (source not in policy.allowed_sources or re.search(r"local cmos|free-running", source, re.I)
            or code("Leap Indicator") != 0 or not 1 <= code("Stratum") <= 15
            or code("Last Sync Error") != 0):
        raise PaperClockError("ineligible or unsynchronized clock source")
    # Use the numeric age instead of guessing locale/timezone of the display date.
    if field("Last Successful Sync Time").lower() in {"unspecified", "unknown", "none"}:
        raise PaperClockError("missing successful synchronization")
    age = seconds("Time since Last Good Sync Time")
    if age > 86400:
        raise PaperClockError("stale synchronization")
    precision = re.fullmatch(r"(-?[0-9]{1,2})(?:\s*\([^\r\n]*\))?", field("Precision"))
    if precision is None or not -63 <= int(precision[1]) <= 0:
        raise PaperClockError("unsupported clock precision")
    ceil = lambda x: int(x.to_integral_value(rounding=ROUND_CEILING))
    precision_ns = ceil((Decimal(2) ** int(precision[1])) * 1_000_000_000)
    root_distance = ceil((seconds("Root Delay")/2 + seconds("Root Dispersion"))*1_000_000_000)
    phase_ns = int((seconds("Phase Offset", True)*1_000_000_000).to_integral_value(rounding=ROUND_UP))
    def delta_seconds(value):
        return Decimal(value.days*86400 + value.seconds) + Decimal(value.microseconds)/1_000_000
    # Intentionally conservative: age from last sync, including capture and full
    # permitted 90s health lifetime. A later health refresh cannot erase this cost.
    age_allowance = ceil((age+delta_seconds(duration)+90)*policy.drift_ns_per_second)
    uncertainty = (root_distance + precision_ns + age_allowance
                   + policy.local_uncertainty_ns + ceil(delta_seconds(duration)*1_000_000_000))
    binding = dict(version="windows-paper-clock-evidence-v1", raw_sha256=expected_sha256,
        policy_evidence=policy.evidence_sha256, allowed_sources=policy.allowed_sources,
        local_uncertainty_ns=policy.local_uncertainty_ns, drift_ns_per_second=policy.drift_ns_per_second,
        started=query_started_at.isoformat(), completed=query_completed_at.isoformat(),
        offset_ns=phase_ns, uncertainty_ns=uncertainty)
    identity = hashlib.sha256(json.dumps(binding,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
    health = PaperClockHealthV1(query_completed_at, True, phase_ns, uncertainty, identity)
    return WindowsClockReceiptV1(health, expected_sha256, policy.evidence_sha256,
                                source, root_distance, precision_ns, age_allowance)
