from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from .oos_evidence import (
    AuthorityEvidenceV1, EvidenceFileV1, FrozenPartitionV1, MissingIntervalV1,
    OOSReadinessError, OOSReadinessPlanV1, OOSReadinessReason,
)
from .reporting_validation import EvidencePartition

T = datetime(2025, 1, 1, tzinfo=timezone.utc)
H = "a" * 64


def evidence(path="btc.csv", start=T, end=T + timedelta(days=90)):
    return EvidenceFileV1(path, H, 100, 90, "1d", start, end)


def partitions():
    return (
        FrozenPartitionV1(EvidencePartition.TRAINING, T, T + timedelta(days=30)),
        FrozenPartitionV1(EvidencePartition.VALIDATION, T + timedelta(days=30), T + timedelta(days=60)),
        FrozenPartitionV1(EvidencePartition.UNTOUCHED_OOS, T + timedelta(days=60), T + timedelta(days=90)),
    )


def authority(kind="fees", start=T, end=T + timedelta(days=90)):
    return AuthorityEvidenceV1(kind, "official", H, start, end,
                               start - timedelta(days=1), T + timedelta(days=91))


def plan(**changes):
    values = dict(market="BTC", dataset_id="dataset", files=(evidence(),),
                  missing_intervals=(), authorities=(authority(),),
                  required_authority_kinds=("fees",), partitions=partitions(),
                  frozen_at=T + timedelta(days=92))
    values.update(changes)
    return OOSReadinessPlanV1.create(**values)


def test_ready_plan_is_deterministic_and_immutable():
    assert plan() == plan()
    assert plan().ready
    with pytest.raises(Exception):
        plan().market = "ES"


@pytest.mark.parametrize("market", ("BTC", "ES", "NQ"))
def test_supported_markets_are_independent(market):
    assert plan(market=market).market == market


def test_unknown_market_fails_closed():
    with pytest.raises(OOSReadinessError) as error:
        plan(market="ALL")
    assert error.value.reason is OOSReadinessReason.INVALID_MARKET


@pytest.mark.parametrize("path", ("C:/secret.csv", "../secret.csv", "/secret.csv"))
def test_paths_must_be_relative_and_non_traversing(path):
    with pytest.raises(OOSReadinessError):
        evidence(path=path)


def test_duplicate_file_rejected():
    with pytest.raises(OOSReadinessError) as error:
        plan(files=(evidence(), evidence()))
    assert error.value.reason is OOSReadinessReason.DUPLICATE_FILE


def test_partition_order_and_overlap_rejected():
    reversed_parts = tuple(reversed(partitions()))
    with pytest.raises(OOSReadinessError) as error:
        plan(partitions=reversed_parts)
    assert error.value.reason is OOSReadinessReason.PARTITION_ORDER
    overlapping = list(partitions())
    overlapping[1] = replace(overlapping[1], start_inclusive=T + timedelta(days=29))
    with pytest.raises(OOSReadinessError):
        plan(partitions=tuple(overlapping))


def test_partition_outside_file_coverage_rejected():
    with pytest.raises(OOSReadinessError) as error:
        plan(files=(evidence(start=T + timedelta(days=1)),))
    assert error.value.reason is OOSReadinessReason.COVERAGE_MISMATCH


def test_any_oos_gap_rejected_but_training_gap_is_retained():
    oos_gap = MissingIntervalV1("1d", T + timedelta(days=70),
                                T + timedelta(days=71), "source outage")
    with pytest.raises(OOSReadinessError) as error:
        plan(missing_intervals=(oos_gap,))
    assert error.value.reason is OOSReadinessReason.OOS_GAP
    training_gap = replace(oos_gap, start_inclusive=T + timedelta(days=2),
                           end_exclusive=T + timedelta(days=3))
    assert plan(missing_intervals=(training_gap,)).missing_intervals == (training_gap,)


def test_required_authority_must_exist_and_cover_all_oos():
    with pytest.raises(OOSReadinessError) as error:
        plan(required_authority_kinds=("fees", "instrument"))
    assert error.value.reason is OOSReadinessReason.MISSING_AUTHORITY
    short = authority(end=T + timedelta(days=80))
    with pytest.raises(OOSReadinessError) as error:
        plan(authorities=(short,))
    assert error.value.reason is OOSReadinessReason.AUTHORITY_GAP


def test_contiguous_authority_versions_cover_oos():
    first = authority(end=T + timedelta(days=75))
    second = authority(start=T + timedelta(days=75), end=T + timedelta(days=90))
    assert plan(authorities=(first, second)).ready


def test_late_published_or_post_freeze_authority_rejected():
    with pytest.raises(OOSReadinessError) as error:
        replace(authority(), published_at=T + timedelta(seconds=1))
    assert error.value.reason is OOSReadinessReason.LOOKAHEAD
    late_capture = replace(authority(), captured_at=T + timedelta(days=100))
    with pytest.raises(OOSReadinessError) as error:
        plan(authorities=(late_capture,))
    assert error.value.reason is OOSReadinessReason.LOOKAHEAD


def test_plan_fingerprint_tampering_rejected():
    with pytest.raises(OOSReadinessError):
        replace(plan(), plan_id="b" * 64)
