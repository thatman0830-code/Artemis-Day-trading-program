from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from .models import fingerprint, require_utc


class PartitionRole(str, Enum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


@dataclass(frozen=True)
class TimePartition:
    id: str
    market: str
    role: PartitionRole
    start_inclusive: datetime
    end_exclusive: datetime
    purge_before: timedelta = timedelta(0)
    embargo_after: timedelta = timedelta(0)


@dataclass(frozen=True)
class SplitPlan:
    id: str
    version: str
    partitions: tuple[TimePartition, ...]


def build_split_plan(*, version: str, partitions: tuple[TimePartition, ...]) -> SplitPlan:
    by_market: dict[str, list[TimePartition]] = {}
    for row in partitions:
        require_utc(row.start_inclusive); require_utc(row.end_exclusive)
        if row.start_inclusive >= row.end_exclusive or row.purge_before < timedelta(0) or row.embargo_after < timedelta(0):
            raise ValueError("invalid chronological partition")
        by_market.setdefault(row.market, []).append(row)
    for rows in by_market.values():
        rows.sort(key=lambda r: r.start_inclusive)
        if [r.role for r in rows] != [PartitionRole.TRAIN, PartitionRole.VALIDATION, PartitionRole.TEST]:
            raise ValueError("each market requires chronological train/validation/test partitions")
        for left, right in zip(rows, rows[1:]):
            if left.end_exclusive + left.embargo_after > right.start_inclusive - right.purge_before:
                raise ValueError("partition purge/embargo boundaries overlap")
    return SplitPlan(fingerprint((version, partitions)), version, partitions)

