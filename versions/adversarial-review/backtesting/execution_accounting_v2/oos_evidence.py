"""Immutable, fail-closed evidence controls for untouched-OOS research.

This module describes evidence; it does not read providers, choose partitions,
run strategies, promote models, or authorize trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .reporting_validation import EvidencePartition
from .specifications import _text as _validate_text, _utc as _validate_utc, canonical_fingerprint

OOS_EVIDENCE_VERSION = "OOS_EVIDENCE_READINESS_V1"


def _text(value: str, field: str) -> str:
    _validate_text(value, field)
    return value


def _utc(value: datetime, field: str) -> datetime:
    _validate_utc(value, field)
    return value


class OOSReadinessReason(str, Enum):
    READY = "READY"
    INVALID_MARKET = "INVALID_MARKET"
    INVALID_FILE = "INVALID_FILE"
    DUPLICATE_FILE = "DUPLICATE_FILE"
    COVERAGE_MISMATCH = "COVERAGE_MISMATCH"
    PARTITION_ORDER = "PARTITION_ORDER"
    OOS_GAP = "OOS_GAP"
    MISSING_AUTHORITY = "MISSING_AUTHORITY"
    AUTHORITY_GAP = "AUTHORITY_GAP"
    LOOKAHEAD = "LOOKAHEAD"


class OOSReadinessError(ValueError):
    def __init__(self, reason: OOSReadinessReason, detail: str):
        self.reason, self.detail = reason, detail
        super().__init__(f"{reason.value}: {detail}")


def _sha(value: str, field: str) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        raise OOSReadinessError(OOSReadinessReason.INVALID_FILE,
                                f"{field} must be lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class EvidenceFileV1:
    relative_path: str
    sha256: str
    byte_count: int
    record_count: int
    timeframe: str
    start_inclusive: datetime
    end_exclusive: datetime

    def __post_init__(self) -> None:
        path = _text(self.relative_path, "relative_path").replace("\\", "/")
        if path.startswith("/") or ":" in path or ".." in path.split("/"):
            raise OOSReadinessError(OOSReadinessReason.INVALID_FILE,
                                    "evidence path must be repository-relative")
        _sha(self.sha256, "sha256")
        if (isinstance(self.byte_count, bool) or not isinstance(self.byte_count, int)
                or self.byte_count <= 0 or isinstance(self.record_count, bool)
                or not isinstance(self.record_count, int) or self.record_count <= 0):
            raise OOSReadinessError(OOSReadinessReason.INVALID_FILE,
                                    "evidence counts must be positive integers")
        _text(self.timeframe, "timeframe")
        if _utc(self.start_inclusive, "start_inclusive") >= _utc(self.end_exclusive, "end_exclusive"):
            raise OOSReadinessError(OOSReadinessReason.INVALID_FILE,
                                    "evidence interval must be nonempty")


@dataclass(frozen=True, slots=True)
class MissingIntervalV1:
    timeframe: str
    start_inclusive: datetime
    end_exclusive: datetime
    reason: str

    def __post_init__(self) -> None:
        _text(self.timeframe, "timeframe"); _text(self.reason, "reason")
        if _utc(self.start_inclusive, "start_inclusive") >= _utc(self.end_exclusive, "end_exclusive"):
            raise ValueError("missing interval must be nonempty")


@dataclass(frozen=True, slots=True)
class AuthorityEvidenceV1:
    kind: str
    authority_name: str
    source_sha256: str
    effective_start_inclusive: datetime
    effective_end_exclusive: datetime
    published_at: datetime
    captured_at: datetime

    def __post_init__(self) -> None:
        _text(self.kind, "kind"); _text(self.authority_name, "authority_name")
        _sha(self.source_sha256, "source_sha256")
        start = _utc(self.effective_start_inclusive, "effective_start_inclusive")
        end = _utc(self.effective_end_exclusive, "effective_end_exclusive")
        published = _utc(self.published_at, "published_at")
        captured = _utc(self.captured_at, "captured_at")
        if start >= end:
            raise ValueError("authority interval must be nonempty")
        if published > start:
            raise OOSReadinessError(OOSReadinessReason.LOOKAHEAD,
                                    "authority evidence was published after it became effective")
        if captured < published:
            raise ValueError("authority evidence cannot be captured before publication")


@dataclass(frozen=True, slots=True)
class FrozenPartitionV1:
    role: EvidencePartition
    start_inclusive: datetime
    end_exclusive: datetime

    def __post_init__(self) -> None:
        if self.role not in (EvidencePartition.TRAINING, EvidencePartition.VALIDATION,
                             EvidencePartition.UNTOUCHED_OOS):
            raise ValueError("readiness plans accept TRAINING, VALIDATION and UNTOUCHED_OOS only")
        if _utc(self.start_inclusive, "start_inclusive") >= _utc(self.end_exclusive, "end_exclusive"):
            raise ValueError("partition interval must be nonempty")


@dataclass(frozen=True, slots=True)
class OOSReadinessPlanV1:
    plan_id: str
    market: str
    dataset_id: str
    files: tuple[EvidenceFileV1, ...]
    missing_intervals: tuple[MissingIntervalV1, ...]
    authorities: tuple[AuthorityEvidenceV1, ...]
    required_authority_kinds: tuple[str, ...]
    partitions: tuple[FrozenPartitionV1, ...]
    frozen_at: datetime
    ready: bool
    version: str = OOS_EVIDENCE_VERSION

    @classmethod
    def create(cls, *, market: str, dataset_id: str,
               files: tuple[EvidenceFileV1, ...],
               missing_intervals: tuple[MissingIntervalV1, ...],
               authorities: tuple[AuthorityEvidenceV1, ...],
               required_authority_kinds: tuple[str, ...],
               partitions: tuple[FrozenPartitionV1, ...],
               frozen_at: datetime) -> "OOSReadinessPlanV1":
        if market not in ("BTC", "ES", "NQ"):
            raise OOSReadinessError(OOSReadinessReason.INVALID_MARKET, market)
        _text(dataset_id, "dataset_id"); frozen = _utc(frozen_at, "frozen_at")
        if not files:
            raise OOSReadinessError(OOSReadinessReason.INVALID_FILE, "files are required")
        paths = tuple(item.relative_path.replace("\\", "/") for item in files)
        if len(set(paths)) != len(paths):
            raise OOSReadinessError(OOSReadinessReason.DUPLICATE_FILE, "duplicate evidence path")
        expected_roles = (EvidencePartition.TRAINING, EvidencePartition.VALIDATION,
                          EvidencePartition.UNTOUCHED_OOS)
        if tuple(item.role for item in partitions) != expected_roles:
            raise OOSReadinessError(OOSReadinessReason.PARTITION_ORDER,
                                    "partitions must be TRAINING, VALIDATION, UNTOUCHED_OOS")
        if any(left.end_exclusive > right.start_inclusive
               for left, right in zip(partitions, partitions[1:])):
            raise OOSReadinessError(OOSReadinessReason.PARTITION_ORDER,
                                    "partition intervals overlap")
        coverage_start = min(item.start_inclusive for item in files)
        coverage_end = max(item.end_exclusive for item in files)
        if partitions[0].start_inclusive < coverage_start or partitions[-1].end_exclusive > coverage_end:
            raise OOSReadinessError(OOSReadinessReason.COVERAGE_MISMATCH,
                                    "partition interval exceeds declared file coverage")
        oos = partitions[-1]
        if any(item.start_inclusive < oos.end_exclusive and item.end_exclusive > oos.start_inclusive
               for item in missing_intervals):
            raise OOSReadinessError(OOSReadinessReason.OOS_GAP,
                                    "untouched-OOS interval contains missing evidence")
        required = tuple(sorted(set(_text(item, "required authority kind")
                                    for item in required_authority_kinds)))
        if required != required_authority_kinds:
            raise ValueError("required authority kinds must be unique and sorted")
        by_kind = {kind: tuple(item for item in authorities if item.kind == kind) for kind in required}
        if any(not values for values in by_kind.values()):
            raise OOSReadinessError(OOSReadinessReason.MISSING_AUTHORITY,
                                    "every required authority kind needs evidence")
        if any(item.captured_at > frozen for item in authorities):
            raise OOSReadinessError(OOSReadinessReason.LOOKAHEAD,
                                    "authority evidence was captured after the plan freeze")
        for kind, values in by_kind.items():
            ordered = tuple(sorted(values, key=lambda item: item.effective_start_inclusive))
            cursor = oos.start_inclusive
            for item in ordered:
                if item.effective_end_exclusive <= cursor: continue
                if item.effective_start_inclusive > cursor: break
                cursor = max(cursor, item.effective_end_exclusive)
                if cursor >= oos.end_exclusive: break
            if cursor < oos.end_exclusive:
                raise OOSReadinessError(OOSReadinessReason.AUTHORITY_GAP,
                                        f"{kind} does not cover untouched-OOS")
        plan_id = canonical_fingerprint(*cls._identity_parts(
            market, dataset_id, files, missing_intervals, authorities, required,
            partitions, frozen))
        return cls(plan_id, market, dataset_id, files, missing_intervals, authorities,
                   required, partitions, frozen, True)

    def __post_init__(self) -> None:
        if self.version != OOS_EVIDENCE_VERSION or self.ready is not True:
            raise ValueError("readiness plan version/state is invalid")
        expected = canonical_fingerprint(*self._identity_parts(
            self.market, self.dataset_id, self.files, self.missing_intervals,
            self.authorities, self.required_authority_kinds, self.partitions,
            self.frozen_at))
        if expected != self.plan_id:
            raise OOSReadinessError(OOSReadinessReason.INVALID_FILE, "plan fingerprint mismatch")

    @staticmethod
    def _identity_parts(market: str, dataset_id: str,
                        files: tuple[EvidenceFileV1, ...],
                        missing_intervals: tuple[MissingIntervalV1, ...],
                        authorities: tuple[AuthorityEvidenceV1, ...],
                        required: tuple[str, ...],
                        partitions: tuple[FrozenPartitionV1, ...],
                        frozen: datetime) -> tuple[object, ...]:
        return (OOS_EVIDENCE_VERSION, market, dataset_id, frozen,
                tuple((x.relative_path.replace("\\", "/"), x.sha256, x.byte_count,
                       x.record_count, x.timeframe, x.start_inclusive, x.end_exclusive)
                      for x in files),
                missing_intervals, authorities, required, partitions)
