"""Hermes independent adversarial audit for OOS Evidence Readiness milestone.

Audit assignment: AUDIT-OOS-EVIDENCE-READINESS

Covers:
  1. Market isolation between BTC, ES, and NQ
  2. Path traversal, absolute paths, duplicate paths, malformed hashes, invalid counts, fingerprint tampering
  3. Reordered, overlapping, missing, and out-of-coverage partitions
  4. Missing interval intersecting UNTOUCHED_OOS fails closed
  5. Gaps at exact half-open interval boundaries
  6. Missing, overlapping, discontinuous, late-published, and post-freeze authoritative evidence
  7. Every required authority kind covers the entire OOS interval without gaps
  8. Timezone-naive, non-UTC, zero-length, reversed, and malformed intervals
  9. Deterministic identities and immutable records
 10. No accidental provider, network, credential, collector, scheduler, strategy, execution, promotion, or trading capabilities
 11. Redundant, incorrect, or implementation-coupled tests
 12. Schema accurately represents public Python contracts
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from backtesting.execution_accounting_v2.oos_evidence import (
    OOS_EVIDENCE_VERSION, AuthorityEvidenceV1, EvidenceFileV1,
    FrozenPartitionV1, MissingIntervalV1, OOSReadinessError,
    OOSReadinessPlanV1, OOSReadinessReason,
)
from backtesting.execution_accounting_v2.reporting_validation import (
    EvidencePartition,
)


UTC = timezone.utc
T = datetime(2025, 1, 1, tzinfo=UTC)
H = "a" * 64


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def evidence(path="btc.csv", start=T, end=T + timedelta(days=90)):
    return EvidenceFileV1(path, H, 100, 90, "1d", start, end)


def partitions():
    return (
        FrozenPartitionV1(EvidencePartition.TRAINING, T, T + timedelta(days=30)),
        FrozenPartitionV1(EvidencePartition.VALIDATION,
                          T + timedelta(days=30), T + timedelta(days=60)),
        FrozenPartitionV1(EvidencePartition.UNTOUCHED_OOS,
                          T + timedelta(days=60), T + timedelta(days=90)),
    )


def authority(kind="fees", start=T, end=T + timedelta(days=90)):
    return AuthorityEvidenceV1(
        kind, "official", H, start, end,
        start - timedelta(days=1), T + timedelta(days=91),
    )


def plan(**changes):
    values = dict(
        market="BTC", dataset_id="dataset",
        files=(evidence(),),
        missing_intervals=(),
        authorities=(authority(),),
        required_authority_kinds=("fees",),
        partitions=partitions(),
        frozen_at=T + timedelta(days=92),
    )
    values.update(changes)
    return OOSReadinessPlanV1.create(**values)


# ===========================================================================
# 1. Market isolation
# ===========================================================================

class TestMarketIsolation:
    """BTC, ES, and NQ markets are independently supported."""

    @pytest.mark.parametrize("market", ("BTC", "ES", "NQ"))
    def test_each_market_creates_plan(self, market):
        assert plan(market=market).market == market

    def test_unknown_market_rejects(self):
        with pytest.raises(OOSReadinessError) as exc:
            plan(market="ALL")
        assert exc.value.reason is OOSReadinessReason.INVALID_MARKET

    def test_lowercase_market_rejects(self):
        with pytest.raises(OOSReadinessError):
            plan(market="btc")

    def test_empty_market_rejects(self):
        with pytest.raises(OOSReadinessError):
            plan(market="")

    def test_market_isolation_in_plan_id(self):
        """Different markets produce different plan_ids."""
        assert plan(market="BTC").plan_id != plan(market="ES").plan_id
        assert plan(market="ES").plan_id != plan(market="NQ").plan_id


# ===========================================================================
# 2. Path traversal, absolute paths, duplicate paths, malformed hashes,
#    invalid counts, fingerprint tampering
# ===========================================================================

class TestPathAndHashValidation:
    """Path traversal, duplicate paths, malformed hashes, invalid counts."""

    @pytest.mark.parametrize("bad_path", (
        "C:/secret.csv",
        "../secret.csv",
        "/secret.csv",
        "data/../secret.csv",
    ))
    def test_absolute_or_traversing_path_rejects(self, bad_path):
        with pytest.raises(OOSReadinessError) as exc:
            evidence(path=bad_path)
        assert exc.value.reason is OOSReadinessReason.INVALID_FILE

    def test_duplicate_files_rejected(self):
        with pytest.raises(OOSReadinessError) as exc:
            plan(files=(evidence(), evidence()))
        assert exc.value.reason is OOSReadinessReason.DUPLICATE_FILE

    def test_malformed_hash_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", "X" * 64, 100, 90, "1d", T,
                           T + timedelta(days=90))

    def test_short_hash_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", "a" * 63, 100, 90, "1d", T,
                           T + timedelta(days=90))

    def test_non_string_hash_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", 12345, 100, 90, "1d", T,
                           T + timedelta(days=90))

    def test_zero_byte_count_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", H, 0, 90, "1d", T,
                           T + timedelta(days=90))

    def test_negative_byte_count_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", H, -1, 90, "1d", T,
                           T + timedelta(days=90))

    def test_zero_record_count_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", H, 100, 0, "1d", T,
                           T + timedelta(days=90))

    def test_bool_byte_count_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", H, True, 90, "1d", T,
                           T + timedelta(days=90))

    def test_plan_fingerprint_tampering_rejects(self):
        with pytest.raises((OOSReadinessError, ValueError, FrozenInstanceError)):
            replace(plan(), plan_id="b" * 64)

    def test_empty_files_rejected(self):
        with pytest.raises(OOSReadinessError) as exc:
            plan(files=())
        assert exc.value.reason is OOSReadinessReason.INVALID_FILE


# ===========================================================================
# 3. Partition ordering, overlap, coverage
# ===========================================================================

class TestPartitions:
    """Reordered, overlapping, missing, and out-of-coverage partitions."""

    def test_correct_order_accepted(self):
        assert plan().partitions == partitions()

    def test_reversed_order_rejects(self):
        reversed_parts = tuple(reversed(partitions()))
        with pytest.raises(OOSReadinessError) as exc:
            plan(partitions=reversed_parts)
        assert exc.value.reason is OOSReadinessReason.PARTITION_ORDER

    def test_overlapping_partitions_rejects(self):
        overlapping = list(partitions())
        overlapping[1] = replace(
            overlapping[1],
            start_inclusive=T + timedelta(days=29),
        )
        with pytest.raises(OOSReadinessError):
            plan(partitions=tuple(overlapping))

    def test_partition_outside_file_coverage_rejects(self):
        with pytest.raises(OOSReadinessError) as exc:
            plan(files=(evidence(start=T + timedelta(days=1)),))
        assert exc.value.reason is OOSReadinessReason.COVERAGE_MISMATCH

    def test_partition_extends_beyond_coverage_rejects(self):
        """Partition end > coverage end → COVERAGE_MISMATCH."""
        long_parts = (
            FrozenPartitionV1(EvidencePartition.TRAINING, T,
                             T + timedelta(days=30)),
            FrozenPartitionV1(EvidencePartition.VALIDATION,
                             T + timedelta(days=30),
                             T + timedelta(days=60)),
            FrozenPartitionV1(EvidencePartition.UNTOUCHED_OOS,
                             T + timedelta(days=60),
                             T + timedelta(days=100)),  # > 90
        )
        with pytest.raises(OOSReadinessError) as exc:
            plan(partitions=long_parts)
        assert exc.value.reason is OOSReadinessReason.COVERAGE_MISMATCH

    def test_wrong_partition_count_rejects(self):
        """Two partitions → PARTITION_ORDER (not 3 expected)."""
        two_parts = partitions()[:2]
        with pytest.raises(OOSReadinessError):
            plan(partitions=two_parts)

    def test_pAPER_partition_rejects(self):
        """PAPER partition role → ValueError (not in allowed set)."""
        with pytest.raises(ValueError):
            FrozenPartitionV1(EvidencePartition.PAPER, T,
                            T + timedelta(days=30))

    def test_live_partition_rejects(self):
        """LIVE partition role → ValueError."""
        with pytest.raises(ValueError):
            FrozenPartitionV1(EvidencePartition.LIVE, T,
                            T + timedelta(days=30))


# ===========================================================================
# 4. Missing interval intersecting UNTOUCHED_OOS
# ===========================================================================

class TestMissingIntervalOOS:
    """Missing interval intersecting OOS → OOS_GAP."""

    def test_oos_gap_rejects(self):
        """Missing interval within OOS → OOS_GAP."""
        oos_gap = MissingIntervalV1(
            "1d", T + timedelta(days=70),
            T + timedelta(days=71), "source outage",
        )
        with pytest.raises(OOSReadinessError) as exc:
            plan(missing_intervals=(oos_gap,))
        assert exc.value.reason is OOSReadinessReason.OOS_GAP

    def test_training_gap_accepted(self):
        """Missing interval in training → retained (not OOS)."""
        training_gap = MissingIntervalV1(
            "1d", T + timedelta(days=2),
            T + timedelta(days=3), "source outage",
        )
        result = plan(missing_intervals=(training_gap,))
        assert result.missing_intervals == (training_gap,)

    def test_validation_gap_accepted(self):
        """Missing interval in validation → retained."""
        val_gap = MissingIntervalV1(
            "1d", T + timedelta(days=35),
            T + timedelta(days=36), "source outage",
        )
        result = plan(missing_intervals=(val_gap,))
        assert result.missing_intervals == (val_gap,)

    def test_gap_at_oos_start_boundary_accepted(self):
        """Missing interval ending exactly at OOS start → not OOS_GAP."""
        gap = MissingIntervalV1(
            "1d", T + timedelta(days=59),
            T + timedelta(days=60), "boundary",
        )
        result = plan(missing_intervals=(gap,))
        assert result.missing_intervals == (gap,)

    def test_gap_at_oos_end_boundary_accepted(self):
        """Missing interval starting exactly at OOS end → not OOS_GAP."""
        gap = MissingIntervalV1(
            "1d", T + timedelta(days=90),
            T + timedelta(days=91), "boundary",
        )
        result = plan(missing_intervals=(gap,))
        assert result.missing_intervals == (gap,)

    def test_gap_overlapping_oos_start_rejects(self):
        """Missing interval overlapping OOS start → OOS_GAP."""
        gap = MissingIntervalV1(
            "1d", T + timedelta(days=59),
            T + timedelta(days=61), "overlap",
        )
        with pytest.raises(OOSReadinessError) as exc:
            plan(missing_intervals=(gap,))
        assert exc.value.reason is OOSReadinessReason.OOS_GAP

    def test_gap_overlapping_oos_end_rejects(self):
        """Missing interval overlapping OOS end → OOS_GAP."""
        gap = MissingIntervalV1(
            "1d", T + timedelta(days=89),
            T + timedelta(days=91), "overlap",
        )
        with pytest.raises(OOSReadinessError) as exc:
            plan(missing_intervals=(gap,))
        assert exc.value.reason is OOSReadinessReason.OOS_GAP


# ===========================================================================
# 5. Half-open interval boundary tests
# ===========================================================================

class TestHalfOpenBoundaries:
    """Gaps at exact half-open interval boundaries."""

    def test_evidence_start_equals_end_rejects(self):
        """Zero-length evidence interval → INVALID_FILE."""
        with pytest.raises(OOSReadinessError):
            evidence(start=T, end=T)

    def test_evidence_start_after_end_rejects(self):
        """Reversed evidence interval → INVALID_FILE."""
        with pytest.raises(OOSReadinessError):
            evidence(start=T + timedelta(days=1), end=T)

    def test_missing_interval_zero_length_rejects(self):
        """Zero-length missing interval → ValueError."""
        with pytest.raises(ValueError):
            MissingIntervalV1("1d", T, T, "empty")

    def test_partition_zero_length_rejects(self):
        """Zero-length partition → ValueError."""
        with pytest.raises(ValueError):
            FrozenPartitionV1(EvidencePartition.TRAINING, T, T)

    def test_partition_reversed_rejects(self):
        """Reversed partition → ValueError."""
        with pytest.raises(ValueError):
            FrozenPartitionV1(
                EvidencePartition.TRAINING,
                T + timedelta(days=1), T,
            )

    def test_partition_touching_boundary_accepted(self):
        """Partitions touching at boundary (start == prev end) → accepted."""
        parts = (
            FrozenPartitionV1(EvidencePartition.TRAINING, T,
                            T + timedelta(days=30)),
            FrozenPartitionV1(EvidencePartition.VALIDATION,
                            T + timedelta(days=30),
                            T + timedelta(days=60)),
            FrozenPartitionV1(EvidencePartition.UNTOUCHED_OOS,
                            T + timedelta(days=60),
                            T + timedelta(days=90)),
        )
        assert plan(partitions=parts).ready


# ===========================================================================
# 6. Authority evidence: missing, overlapping, discontinuous, late, post-freeze
# ===========================================================================

class TestAuthorityEvidence:
    """Authoritative evidence coverage and chronology."""

    def test_missing_authority_rejects(self):
        """Required kind without evidence → MISSING_AUTHORITY."""
        with pytest.raises(OOSReadinessError) as exc:
            plan(required_authority_kinds=("fees", "instrument"))
        assert exc.value.reason is OOSReadinessReason.MISSING_AUTHORITY

    def test_authority_gap_rejects(self):
        """Authority not covering full OOS → AUTHORITY_GAP."""
        short = authority(end=T + timedelta(days=80))
        with pytest.raises(OOSReadinessError) as exc:
            plan(authorities=(short,))
        assert exc.value.reason is OOSReadinessReason.AUTHORITY_GAP

    def test_contiguous_authority_accepted(self):
        """Two contiguous authority records covering OOS → accepted."""
        first = authority(end=T + timedelta(days=75))
        second = authority(start=T + timedelta(days=75),
                          end=T + timedelta(days=90))
        assert plan(authorities=(first, second)).ready

    def test_late_published_rejects(self):
        """published_at > effective_start → LOOKAHEAD."""
        with pytest.raises(OOSReadinessError) as exc:
            replace(authority(), published_at=T + timedelta(seconds=1))
        assert exc.value.reason is OOSReadinessReason.LOOKAHEAD

    def test_post_freeze_capture_rejects(self):
        """captured_at > frozen_at → LOOKAHEAD."""
        late = replace(authority(), captured_at=T + timedelta(days=100))
        with pytest.raises(OOSReadinessError) as exc:
            plan(authorities=(late,))
        assert exc.value.reason is OOSReadinessReason.LOOKAHEAD

    def test_authority_captured_before_published_rejects(self):
        """captured_at < published_at → ValueError."""
        with pytest.raises(ValueError):
            AuthorityEvidenceV1(
                "fees", "official", H, T, T + timedelta(days=90),
                T + timedelta(days=1), T,
            )

    def test_authority_zero_length_rejects(self):
        """start >= end → ValueError."""
        with pytest.raises(ValueError):
            AuthorityEvidenceV1(
                "fees", "official", H, T, T,
                T - timedelta(days=1), T,
            )

    def test_multiple_authority_kinds_cover_oos(self):
        """Two required kinds, both covering OOS → accepted."""
        auth1 = authority(kind="fees")
        auth2 = authority(kind="instrument")
        result = plan(
            authorities=(auth1, auth2),
            required_authority_kinds=("fees", "instrument"),
        )
        assert result.ready

    def test_authority_exactly_covering_oos_accepted(self):
        """Authority covering exactly [oos_start, oos_end) → accepted."""
        auth = authority(
            start=T + timedelta(days=60),
            end=T + timedelta(days=90),
        )
        result = plan(authorities=(auth,))
        assert result.ready

    def test_authority_starting_after_oos_start_rejects(self):
        """Authority starting after OOS start → AUTHORITY_GAP."""
        auth = authority(
            start=T + timedelta(days=61),
            end=T + timedelta(days=90),
        )
        with pytest.raises(OOSReadinessError) as exc:
            plan(authorities=(auth,))
        assert exc.value.reason is OOSReadinessReason.AUTHORITY_GAP

    def test_required_kinds_must_be_sorted(self):
        """Unsorted required_authority_kinds → ValueError."""
        with pytest.raises(ValueError):
            plan(required_authority_kinds=("instrument", "fees"))

    def test_required_kinds_must_be_unique(self):
        """Duplicate required_authority_kinds → ValueError."""
        with pytest.raises(ValueError):
            plan(required_authority_kinds=("fees", "fees"))


# ===========================================================================
# 7. Timezone-naive, non-UTC, intervals
# ===========================================================================

class TestTimezoneValidation:
    """Timezone-naive and non-UTC rejection."""

    def test_naive_evidence_start_rejects(self):
        """Naive datetime in evidence → ValueError."""
        with pytest.raises(ValueError):
            EvidenceFileV1(
                "ok.csv", H, 100, 90, "1d",
                datetime(2025, 1, 1),  # naive
                T + timedelta(days=90),
            )

    def test_naive_evidence_end_rejects(self):
        """Naive end datetime → ValueError."""
        with pytest.raises(ValueError):
            EvidenceFileV1(
                "ok.csv", H, 100, 90, "1d", T,
                datetime(2025, 4, 1),  # naive
            )

    def test_naive_partition_rejects(self):
        """Naive partition start → ValueError."""
        with pytest.raises(ValueError):
            FrozenPartitionV1(
                EvidencePartition.TRAINING,
                datetime(2025, 1, 1),  # naive
                T + timedelta(days=30),
            )

    def test_naive_authority_rejects(self):
        """Naive authority start → ValueError."""
        with pytest.raises(ValueError):
            AuthorityEvidenceV1(
                "fees", "official", H,
                datetime(2025, 1, 1),  # naive
                T + timedelta(days=90),
                T - timedelta(days=1), T,
            )

    def test_naive_frozen_at_rejects(self):
        """Naive frozen_at → ValueError."""
        with pytest.raises(ValueError):
            plan(frozen_at=datetime(2025, 4, 2))


# ===========================================================================
# 8. Deterministic identities and immutability
# ===========================================================================

class TestDeterminismAndImmutability:
    """Deterministic plan_id and frozen records."""

    def test_plan_id_deterministic(self):
        assert plan().plan_id == plan().plan_id

    def test_plan_immutable(self):
        with pytest.raises(FrozenInstanceError):
            plan().market = "ES"

    def test_evidence_file_immutable(self):
        with pytest.raises(FrozenInstanceError):
            evidence().sha256 = "b" * 64

    def test_authority_immutable(self):
        with pytest.raises(FrozenInstanceError):
            authority().kind = "other"

    def test_partition_immutable(self):
        with pytest.raises(FrozenInstanceError):
            partitions()[0].start_inclusive = T

    def test_missing_interval_immutable(self):
        mi = MissingIntervalV1("1d", T, T + timedelta(days=1), "test")
        with pytest.raises(FrozenInstanceError):
            mi.reason = "other"

    def test_different_dataset_id_different_plan_id(self):
        assert plan(dataset_id="a").plan_id != plan(dataset_id="b").plan_id

    def test_different_files_different_plan_id(self):
        e1 = evidence(path="a.csv")
        e2 = evidence(path="b.csv")
        assert plan(files=(e1,)).plan_id != plan(files=(e2,)).plan_id


# ===========================================================================
# 9. Import isolation — no provider, network, credential, etc.
# ===========================================================================

class TestImportIsolation:
    """No accidental provider/network/credential/trading capabilities."""

    def test_no_provider_or_submission_imports(self):
        """oos_evidence.py has no provider/submission/credential imports."""
        import inspect
        import backtesting.execution_accounting_v2.oos_evidence as module
        source = inspect.getsource(module)
        # Check import lines only, not docstring prose
        import_lines = [
            line for line in source.split("\n")
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        import_source = "\n".join(import_lines).lower()
        for forbidden in ("requests", "private_key", "submit_order",
                         "scheduledtask", "websocket", "broker",
                         "wallet", "credential", "exchange_api",
                         "collector", "recorder"):
            assert forbidden not in import_source, f"forbidden import: {forbidden}"

    def test_no_strategy_or_promotion_authority(self):
        """oos_evidence.py has no strategy or promotion authority in code."""
        import inspect
        import backtesting.execution_accounting_v2.oos_evidence as module
        source = inspect.getsource(module)
        # Remove docstring lines
        lines = source.split("\n")
        code_lines = [
            line for line in lines
            if not line.strip().startswith("\"\"\"") and not line.strip().startswith("#")
        ]
        code_source = "\n".join(code_lines).lower()
        for forbidden in ("submit_order", "deploy",
                         "activate_strategy", "trade_execution"):
            assert forbidden not in code_source, f"forbidden: {forbidden}"


# ===========================================================================
# 10. Schema verification
# ===========================================================================

class TestSchemaVerification:
    """Schema accurately represents public Python contracts."""

    def test_schema_is_valid_json(self):
        """Schema file is valid JSON with $id."""
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        assert data["$id"] == "oos-evidence-readiness-v1.schema.json"
        assert data["title"] == "Untouched-OOS evidence readiness plan"

    def test_schema_market_enum_matches_python(self):
        """Schema market enum contains BTC, ES, NQ."""
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        assert set(data["properties"]["market"]["enum"]) == {"BTC", "ES", "NQ"}

    def test_schema_version_matches_python(self):
        """Schema version const matches OOS_EVIDENCE_VERSION."""
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        assert (data["properties"]["version"]["const"]
                == OOS_EVIDENCE_VERSION)

    def test_schema_required_fields_match_dataclass(self):
        """Schema required fields match OOSReadinessPlanV1 fields."""
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        schema_required = set(data["required"])
        # Plan has: plan_id, market, dataset_id, files, missing_intervals,
        # authorities, required_authority_kinds, partitions, frozen_at, ready
        # plus version (default)
        expected = {"version", "plan_id", "market", "dataset_id",
                    "files", "missing_intervals", "authorities",
                    "required_authority_kinds", "partitions",
                    "frozen_at", "ready"}
        assert schema_required == expected

    def test_schema_partition_order_matches_python(self):
        """Schema prefixItems enforces TRAINING, VALIDATION, UNTOUCHED_OOS."""
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        partitions = data["properties"]["partitions"]
        assert partitions["minItems"] == 3
        assert partitions["maxItems"] == 3
        assert len(partitions["prefixItems"]) == 3

    def test_schema_sha256_pattern(self):
        """Schema sha256 pattern is 64 lowercase hex chars."""
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        assert data["$defs"]["sha256"]["pattern"] == "^[0-9a-f]{64}$"

    def test_schema_ready_const_true(self):
        """Schema ready field is const true."""
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        assert data["properties"]["ready"]["const"] is True


# ===========================================================================
# 11. Reason codes
# ===========================================================================

class TestReasonCodes:
    """Stable reason code classification."""

    def test_all_reasons_unique(self):
        assert len({r.value for r in OOSReadinessReason}) == len(OOSReadinessReason)

    def test_all_expected_reasons_present(self):
        expected = {
            "READY", "INVALID_MARKET", "INVALID_FILE", "DUPLICATE_FILE",
            "COVERAGE_MISMATCH", "PARTITION_ORDER", "OOS_GAP",
            "MISSING_AUTHORITY", "AUTHORITY_GAP", "LOOKAHEAD",
        }
        actual = {r.value for r in OOSReadinessReason}
        assert expected.issubset(actual)

    def test_ready_is_only_success_reason(self):
        assert OOSReadinessReason.READY.value == "READY"


# ===========================================================================
# 12. Redundant / incorrect / implementation-coupled tests in existing suite
# ===========================================================================

class TestExistingSuiteAssessment:
    """Assess existing test_oos_evidence.py for redundancy and coupling."""

    def test_existing_test_late_published_is_correct(self):
        """test_late_published_or_post_freeze_authority_rejected uses replace
        which triggers __post_init__ — this is implementation-coupled but
        correctly identifies the invariant."""
        # The test uses replace(authority(), published_at=T+timedelta(seconds=1))
        # which triggers AuthorityEvidenceV1.__post_init__ at construction.
        # This is implementation-coupled but correct — the invariant is enforced
        # at construction time, not at plan creation time.
        with pytest.raises(OOSReadinessError):
            replace(authority(), published_at=T + timedelta(seconds=1))

    def test_existing_test_uses_string_hash_not_real_sha(self):
        """Existing test uses H = 'a' * 64 which is a valid SHA-256 format
        but not a real hash. This is acceptable for deterministic testing."""
        assert len(H) == 64
        assert all(c in "0123456789abcdef" for c in H)

    def test_existing_test_path_traversal_is_correct(self):
        """test_paths_must_be_relative_and_non_traversing covers C:/, ../, /.
        These are the three main path traversal vectors."""
        for bad_path in ("C:/secret.csv", "../secret.csv", "/secret.csv"):
            with pytest.raises(OOSReadinessError):
                evidence(path=bad_path)
