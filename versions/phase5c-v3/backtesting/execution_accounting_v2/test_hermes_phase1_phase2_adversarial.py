"""Hermes independent adversarial audit tests for V2 Phase 1 contracts/validation
and Phase 2 order ledger.

These tests are independent of the existing test suite and exercise edge cases,
boundary conditions, and invariant violations that the existing tests may not
cover.  They are offline and deterministic.

Audit assignment: AUDIT-V2-PHASE1-PHASE2
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2 import (
    AccountingSnapshotV2,
    BacktestResultIdentityV2,
    CapabilityDeclarationV2,
    Capability,
    EligibilityReport,
    EvidenceRecord,
    FillV2,
    InstrumentProfile,
    InstrumentSpecificationV2,
    LedgerCheckpointV2,
    LedgerEventKind,
    MissingSpecificationReason,
    OrderIntentV2,
    OrderLedgerError,
    OrderLedgerEventV2,
    OrderLedgerReason,
    OrderLedgerSnapshotV2,
    OrderLedgerTransitionV2,
    OrderLedgerV2,
    OrderSide,
    OrderState,
    OrderTransitionV2,
    OrderType,
    OwnerAssumptionV2,
    RiskDecision,
    RiskEventV2,
    RiskPhase,
    SpecificationRecord,
    SpecificationRepository,
    SpecificationType,
    TimeInForce,
    canonical_fingerprint,
    canonical_json_bytes,
    evaluate_production_eligibility,
    evaluate_production_interval,
    validate_evidence_checksum,
    validate_fill_against_order,
    validate_order_against_instrument,
    validate_repository_provenance,
    validate_specification_intervals,
)

UTC = timezone.utc
T0 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2025, 6, 2, 12, 0, 0, tzinfo=UTC)
T2 = datetime(2025, 7, 1, 12, 0, 0, tzinfo=UTC)
H = lambda s: hashlib.sha256(s.encode()).hexdigest()
H64 = "a" * 64


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def instrument_spec(**changes):
    vals = dict(
        schema_version="instrument-spec-v2-1",
        specification_id=H("ispec"),
        market="ES",
        instrument_id="ES",
        contract_id="ESM5",
        profile=InstrumentProfile.ES_FUTURE,
        currency="USD",
        tick_size=Decimal("0.25"),
        quantity_step=Decimal("1"),
        contract_multiplier=Decimal("50"),
        point_value=Decimal("50"),
        effective_from=T0,
        effective_to=T2,
        evidence_ids=("cme-358",),
    )
    vals.update(changes)
    return InstrumentSpecificationV2(**vals)


def order_intent(**changes):
    vals = dict(
        schema_version="order-intent-v2-1",
        order_id=H("order"),
        run_id=H("run"),
        action_id=H("action"),
        market="ES",
        instrument_id="ES",
        contract_id="ESM5",
        side=OrderSide.BUY,
        quantity=Decimal("3"),
        order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.GTC,
        limit_price=Decimal("6000.25"),
        stop_price=None,
        submitted_at=T0,
        activation_at=T0 + timedelta(minutes=1),
        expires_at=None,
        parent_order_id=None,
        replaces_order_id=None,
        configuration_version="config-v2",
        execution_policy_version="CONSERVATIVE_OHLC_1M_V1",
    )
    vals.update(changes)
    return OrderIntentV2(**vals)


def fill_v2(**changes):
    vals = dict(
        schema_version="fill-v2-1",
        fill_id=H("fill"),
        order_id=H("order"),
        market_event_id=H("mevt"),
        market="ES",
        instrument_id="ES",
        contract_id="ESM5",
        fill_time=T0 + timedelta(minutes=5),
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        economic_price=Decimal("6000.25"),
        reference_price=Decimal("6000.25"),
        friction=Decimal("0"),
        fee_total=Decimal("0"),
        currency="USD",
        execution_rule_code="RECORD_ONLY",
        execution_policy_version="CONSERVATIVE_OHLC_1M_V1",
    )
    vals.update(changes)
    return FillV2(**vals)


def evidence_record(eid="ev1", snapshot_path="snap.md", sha=None, **changes):
    return EvidenceRecord(
        eid, "CME", "chapter-358", None, snapshot_path,
        sha or H("snapshot-content"),
        T0, T0, T2, "ES", "ES", ("tick_size",), (), "evidence-record-v2-1",
        **changes,
    )


def econ_spec(kind, sid=None, *, owner=True, synthetic=False, start=T0, end=T2,
               evidence=("ev1",)):
    return SpecificationRecord(
        sid or kind.value, "economic-specification-v2-1", kind,
        "ES", "ES", start, end, (("value", "1"),),
        () if synthetic else evidence, owner, synthetic,
    )


def ledger_event(ledger, kind, *, at=None, order_id=None, expected=None,
                 event_id=None, **changes):
    target = ledger.order(order_id or H("order"))
    seq = len(ledger.events) + 1
    vals = dict(
        schema_version="order-ledger-event-v2-1",
        event_id=event_id or H(f"evt-{seq}-{kind.value}"),
        order_id=target.intent.order_id,
        kind=kind,
        event_time=at or (T0 + timedelta(minutes=seq + 10)),
        sequence_number=seq,
        expected_order_version=target.order_version,
        market=target.intent.market,
        instrument_id=target.intent.instrument_id,
        contract_id=target.intent.contract_id,
        source_event_id=H(f"src-{seq}"),
        reason_code=kind.value,
        contract_eligibility_verified=True,
    )
    if expected is not None:
        vals["expected_order_version"] = expected
    vals.update(changes)
    return OrderLedgerEventV2(**vals)


def active_ledger(selected=None):
    ledger = OrderLedgerV2.create((selected or order_intent(),))
    for kind in (LedgerEventKind.SUBMIT, LedgerEventKind.ACCEPT,
                 LedgerEventKind.ACTIVATE):
        ledger = ledger.apply(ledger_event(ledger, kind))
    return ledger


# ===========================================================================
# Phase 1 — Contract Immutability
# ===========================================================================

class TestPhase1ContractImmutability:
    """Every Phase 1 contract must be frozen with slots."""

    @pytest.mark.parametrize("name,factory", [
        ("InstrumentSpecificationV2", instrument_spec),
        ("OrderIntentV2", order_intent),
        ("OwnerAssumptionV2", lambda: OwnerAssumptionV2(
            "owner-assumption-v2-1", H("oa"), "SLIPPAGE", "ES", "ES",
            T0, T2, (("ticks", Decimal("1")),), False, False, "owner-dec")),
        ("CapabilityDeclarationV2", lambda: CapabilityDeclarationV2(
            "capability-declaration-v2-1", H("cd"), InstrumentProfile.ES_FUTURE,
            "ES", "ES", (OrderType.MARKET,), ("ohlcv",), (H("spec"),),
            False, ())),
        ("OrderTransitionV2", lambda: OrderTransitionV2(
            "order-transition-v2-1", H("t"), H("order"), T0,
            OrderState.ACTIVE, OrderState.FILLED, "FILL", ())),
        ("FillV2", lambda: fill_v2()),
        ("AccountingSnapshotV2", lambda: AccountingSnapshotV2(
            "accounting-snapshot-v2-1", H("as"), H("run"), T0, "USD",
            *(Decimal("0") for _ in range(9)), (), "accounting-v2")),
        ("RiskEventV2", lambda: RiskEventV2(
            "risk-event-v2-1", H("re"), H("run"), T0, "ES", "ES",
            RiskPhase.PRE_TRADE, RiskDecision.ALLOW, ("OK",), (), "risk-v2")),
        ("BacktestResultIdentityV2", lambda: BacktestResultIdentityV2(
            "backtest-result-v2-1", H("ri"), H("run"), H("cf"), H("df"),
            H("ef"), "s", "e", "a", "r", T0, T1, (), True)),
    ])
    def test_frozen_and_slots(self, name, factory):
        record = factory()
        with pytest.raises(FrozenInstanceError):
            record.schema_version = "mutated"
        assert hasattr(record, "__slots__")

    def test_specification_record_immutable(self):
        rec = econ_spec(SpecificationType.INSTRUMENT)
        with pytest.raises(FrozenInstanceError):
            rec.market = "NQ"

    def test_evidence_record_immutable(self):
        ev = evidence_record()
        with pytest.raises(FrozenInstanceError):
            ev.market = "NQ"


# ===========================================================================
# Phase 1 — Decimal-Only Economic Fields (float/integer leakage)
# ===========================================================================

class TestPhase1DecimalOnlyEnforcement:
    """Every economic field must reject float and int leakage."""

    @pytest.mark.parametrize("field,vals", [
        ("tick_size", [1, 1.0, float("inf"), "0.25"]),
        ("quantity_step", [1, 1.0, float("nan"), "1"]),
        ("contract_multiplier", [1, 1.0, float("inf"), "50"]),
        ("point_value", [1, 1.0, float("nan"), "50"]),
    ])
    def test_instrument_spec_rejects_non_decimal(self, field, vals):
        for v in vals:
            with pytest.raises(ValueError):
                instrument_spec(**{field: v})

    @pytest.mark.parametrize("field,vals", [
        ("quantity", [1, 1.0, float("0"), "3"]),
        ("limit_price", [1, 1.0, float("6000.25"), "6000.25"]),
        ("stop_price", [1, 1.0, float("6001"), "6001"]),
    ])
    def test_order_intent_rejects_non_decimal(self, field, vals):
        for v in vals:
            kwargs = {field: v}
            if field == "stop_price":
                kwargs["order_type"] = OrderType.STOP_LIMIT
                kwargs["limit_price"] = Decimal("6001.25")
            elif field == "limit_price":
                pass
            with pytest.raises(ValueError):
                order_intent(**kwargs)

    @pytest.mark.parametrize("field,vals", [
        ("economic_price", [1, 1.0, float("6000.25")]),
        ("reference_price", [1, 1.0, float("6000.25")]),
        ("friction", [1, 1.0, float("0")]),
        ("fee_total", [1, 1.0, float("0")]),
    ])
    def test_fill_rejects_non_decimal(self, field, vals):
        for v in vals:
            with pytest.raises(ValueError):
                fill_v2(**{field: v})

    def test_accounting_snapshot_rejects_non_decimal(self):
        for v in [1, 1.0, float("0")]:
            with pytest.raises(ValueError):
                AccountingSnapshotV2(
                    "accounting-snapshot-v2-1", H("as"), H("run"), T0, "USD",
                    v, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
                    Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
                    (), "accounting-v2")

    def test_owner_assumption_rejects_non_decimal_in_decimal_values(self):
        with pytest.raises(ValueError):
            OwnerAssumptionV2(
                "owner-assumption-v2-1", H("oa"), "SLIPPAGE", "ES", "ES",
                T0, T2, (("ticks", 1),), False, False, "owner-dec")

    @pytest.mark.parametrize("bad", [
        Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
    def test_public_contracts_reject_nonfinite_decimals(self, bad):
        with pytest.raises(ValueError):
            instrument_spec(tick_size=bad)
        with pytest.raises(ValueError):
            fill_v2(friction=bad)
        with pytest.raises(ValueError):
            OwnerAssumptionV2(
                "owner-assumption-v2-1", H("oa"), "SLIPPAGE", "ES", "ES",
                T0, T2, (("ticks", bad),), False, False, "owner-dec")

    def test_canonical_fingerprint_rejects_float(self):
        with pytest.raises(ValueError, match="float"):
            canonical_fingerprint(1.0)
        with pytest.raises(ValueError, match="float"):
            canonical_fingerprint([1.0])
        with pytest.raises(ValueError, match="float"):
            canonical_fingerprint({"a": 1.0})


# ===========================================================================
# Phase 1 — Timezone-Naive Timestamp Rejection
# ===========================================================================

class TestPhase1TimezoneNaiveRejection:
    """Every datetime field must reject timezone-naive or non-UTC timestamps."""

    NAIVE = datetime(2025, 6, 1, 12, 0, 0)
    EST = timezone(timedelta(hours=-5))

    def test_instrument_spec_rejects_naive_effective_from(self):
        with pytest.raises(ValueError, match="UTC"):
            instrument_spec(effective_from=self.NAIVE)

    def test_instrument_spec_rejects_naive_effective_to(self):
        with pytest.raises(ValueError, match="UTC"):
            instrument_spec(effective_to=self.NAIVE)

    def test_order_rejects_naive_submitted_at(self):
        with pytest.raises(ValueError, match="UTC"):
            order_intent(submitted_at=self.NAIVE,
                         activation_at=self.NAIVE + timedelta(minutes=1))

    def test_order_rejects_naive_activation_at(self):
        with pytest.raises(ValueError, match="UTC"):
            order_intent(activation_at=self.NAIVE)

    def test_order_rejects_naive_expires_at(self):
        with pytest.raises(ValueError, match="UTC"):
            order_intent(expires_at=self.NAIVE)

    def test_fill_rejects_naive_fill_time(self):
        with pytest.raises(ValueError, match="UTC"):
            fill_v2(fill_time=self.NAIVE)

    def test_evidence_rejects_naive_retrieved_at(self):
        with pytest.raises(ValueError, match="UTC"):
            EvidenceRecord("e2", "CME", "doc", None, "snap.md", H64,
                           self.NAIVE, T0, T2, "ES", "ES", ("tick",))

    def test_evidence_rejects_non_utc_offset(self):
        with pytest.raises(ValueError, match="UTC"):
            EvidenceRecord("e3", "CME", "doc", None, "s.md", H64,
                           datetime(2025, 6, 1, tzinfo=self.EST),
                           T0, T2, "ES", "ES", ("tick",))

    def test_spec_record_rejects_naive_effective_from(self):
        with pytest.raises(ValueError, match="UTC"):
            SpecificationRecord(H("sr"), "economic-specification-v2-1",
                                SpecificationType.INSTRUMENT, "ES", "ES",
                                self.NAIVE, T2, (("v", "1"),),
                                ("ev1",), True)

    def test_accounting_snapshot_rejects_naive_as_of(self):
        with pytest.raises(ValueError, match="UTC"):
            AccountingSnapshotV2(
                "accounting-snapshot-v2-1", H("x"), H("r"), self.NAIVE, "USD",
                *(Decimal("0") for _ in range(9)), (), "a")

    def test_risk_event_rejects_naive_event_time(self):
        with pytest.raises(ValueError, match="UTC"):
            RiskEventV2("risk-event-v2-1", H("x"), H("r"), self.NAIVE,
                        "ES", "ES", RiskPhase.PRE_TRADE, RiskDecision.ALLOW,
                        ("ok",), (), "r-v2")

    def test_backtest_result_rejects_naive_timestamps(self):
        with pytest.raises(ValueError, match="UTC"):
            BacktestResultIdentityV2(
                "backtest-result-v2-1", H("x"), H("r"), H("c"), H("d"), H("e"),
                "s", "e", "a", "r", self.NAIVE, T1, (), True)


# ===========================================================================
# Phase 1 — Schema Version Validation
# ===========================================================================

class TestPhase1SchemaVersionValidation:

    @pytest.mark.parametrize("bad_version", ["v1", "instrument-spec-v1", "", 1])
    def test_instrument_rejects_wrong_schema(self, bad_version):
        with pytest.raises(ValueError, match="schema"):
            instrument_spec(schema_version=bad_version)

    @pytest.mark.parametrize("bad_version", ["v1", "order-intent-v1", ""])
    def test_order_rejects_wrong_schema(self, bad_version):
        with pytest.raises(ValueError, match="schema"):
            order_intent(schema_version=bad_version)

    def test_fill_rejects_wrong_schema(self):
        with pytest.raises(ValueError, match="schema"):
            fill_v2(schema_version="fill-v1")

    def test_evidence_rejects_wrong_schema(self):
        with pytest.raises(ValueError, match="schema"):
            EvidenceRecord("e", "CME", "doc", None, "s", H64,
                           T0, T0, T2, "ES", "ES", ("tick",),
                           schema_version="evidence-v1")

    def test_spec_record_rejects_wrong_schema(self):
        with pytest.raises(ValueError, match="schema"):
            SpecificationRecord(H("s"), "wrong", SpecificationType.INSTRUMENT,
                                 "ES", "ES", T0, T2, (("v", "1"),),
                                 ("ev1",), True)


# ===========================================================================
# Phase 1 — Specification Interval Gaps and Overlaps
# ===========================================================================

class TestPhase1SpecificationIntervals:

    def test_exact_adjacent_half_open_no_gap(self):
        """Half-open intervals [T0, T1) and [T1, T2) should not produce a gap."""
        a = econ_spec(SpecificationType.SESSION, "a", start=T0, end=T1)
        b = econ_spec(SpecificationType.SESSION, "b", start=T1, end=T2)
        report = validate_specification_intervals(
            (a, b), SpecificationType.SESSION, "ES", "ES", T0, T2)
        assert report.valid
        assert len(report.issues) == 0

    def test_gap_between_two_specs(self):
        a = econ_spec(SpecificationType.SESSION, "a", start=T0, end=T0 + timedelta(days=5))
        b = econ_spec(SpecificationType.SESSION, "b", start=T0 + timedelta(days=7), end=T2)
        report = validate_specification_intervals(
            (a, b), SpecificationType.SESSION, "ES", "ES", T0, T2)
        assert not report.valid
        assert any(i.reason == MissingSpecificationReason.SPEC_EFFECTIVE_DATE_GAP
                   for i in report.issues)

    def test_overlap_detected(self):
        a = econ_spec(SpecificationType.SESSION, "a", start=T0, end=T0 + timedelta(days=6))
        b = econ_spec(SpecificationType.SESSION, "b", start=T0 + timedelta(days=5), end=T2)
        report = validate_specification_intervals(
            (a, b), SpecificationType.SESSION, "ES", "ES", T0, T2)
        assert not report.valid
        assert any(i.reason == MissingSpecificationReason.SPEC_EFFECTIVE_DATE_OVERLAP
                   for i in report.issues)

    def test_spec_entirely_before_required_interval_is_skipped(self):
        a = econ_spec(SpecificationType.SESSION, "a",
                      start=T0 - timedelta(days=10), end=T0 - timedelta(days=1))
        report = validate_specification_intervals(
            (a,), SpecificationType.SESSION, "ES", "ES", T0, T2)
        assert not report.valid
        assert report.issues[0].reason == MissingSpecificationReason.SPEC_EFFECTIVE_DATE_GAP

    def test_open_ended_spec_covers_to_required_end(self):
        a = econ_spec(SpecificationType.SESSION, "a", start=T0, end=None)
        report = validate_specification_intervals(
            (a,), SpecificationType.SESSION, "ES", "ES", T0, T2)
        assert report.valid

    def test_spec_starting_at_required_end_is_skipped(self):
        a = econ_spec(SpecificationType.SESSION, "a", start=T2, end=T2 + timedelta(days=10))
        report = validate_specification_intervals(
            (a,), SpecificationType.SESSION, "ES", "ES", T0, T2)
        assert not report.valid
        assert report.issues[0].reason == MissingSpecificationReason.SPEC_EFFECTIVE_DATE_GAP

    def test_triple_contiguous_no_gap(self):
        a = econ_spec(SpecificationType.SESSION, "a", start=T0, end=T0 + timedelta(days=10))
        b = econ_spec(SpecificationType.SESSION, "b",
                      start=T0 + timedelta(days=10), end=T0 + timedelta(days=20))
        c = econ_spec(SpecificationType.SESSION, "c",
                      start=T0 + timedelta(days=20), end=T2)
        report = validate_specification_intervals(
            (a, b, c), SpecificationType.SESSION, "ES", "ES", T0, T2)
        assert report.valid


# ===========================================================================
# Phase 1 — Evidence Checksum Validation
# ===========================================================================

class TestPhase1EvidenceChecksum:

    def test_valid_checksum(self, tmp_path):
        snap = tmp_path / "snap.md"
        snap.write_bytes(b"evidence content")
        sha = hashlib.sha256(b"evidence content").hexdigest()
        ev = EvidenceRecord("ev", "CME", "doc", None, "snap.md", sha,
                            T0, T0, T2, "ES", "ES", ("tick",))
        report = validate_evidence_checksum(ev, tmp_path)
        assert report.valid

    def test_stale_checksum_detected(self, tmp_path):
        snap = tmp_path / "snap.md"
        snap.write_bytes(b"original content")
        sha = hashlib.sha256(b"original content").hexdigest()
        ev = EvidenceRecord("ev", "CME", "doc", None, "snap.md", sha,
                            T0, T0, T2, "ES", "ES", ("tick",))
        snap.write_bytes(b"tampered content")
        report = validate_evidence_checksum(ev, tmp_path)
        assert not report.valid
        assert report.issues[0].reason == MissingSpecificationReason.SPEC_CHECKSUM_MISMATCH

    def test_missing_file_detected(self, tmp_path):
        ev = EvidenceRecord("ev", "CME", "doc", None, "nonexistent.md", H("x"),
                            T0, T0, T2, "ES", "ES", ("tick",))
        report = validate_evidence_checksum(ev, tmp_path)
        assert not report.valid
        assert report.issues[0].reason == MissingSpecificationReason.SPEC_PROVENANCE_INVALID

    def test_path_escape_detected(self, tmp_path):
        ev = EvidenceRecord("ev", "CME", "doc", None, "../../escape.md", H("x"),
                            T0, T0, T2, "ES", "ES", ("tick",))
        report = validate_evidence_checksum(ev, tmp_path)
        assert not report.valid
        assert report.issues[0].reason == MissingSpecificationReason.SPEC_PROVENANCE_INVALID


# ===========================================================================
# Phase 1 — Mixed Schema / Ledger Versions
# ===========================================================================

class TestPhase1MixedSchemaLedgerVersions:

    def test_mixed_ledger_version_in_eligibility(self):
        report = evaluate_production_eligibility(
            SpecificationRepository((), ()),
            InstrumentProfile.ES_FUTURE, "ES", "ES", T0,
            ledger_schema_version="core-v1")
        assert not report.eligible
        assert MissingSpecificationReason.MIXED_LEDGER_VERSION in {
            i.reason for i in report.issues}

    def test_mixed_ledger_version_in_interval_eligibility(self, tmp_path):
        report = evaluate_production_interval(
            repository=SpecificationRepository((), ()),
            profile=InstrumentProfile.ES_FUTURE, market="ES", instrument_id="ES",
            required_from=T0, required_to=T2, dataset_fingerprint=H("ds"),
            repository_root=tmp_path, ledger_schema_version="backtest-result-v1")
        assert not report.eligible
        assert "MIXED_LEDGER_VERSION" in {i.reason_code for i in report.issues}


# ===========================================================================
# Phase 1 — Synthetic-Fixture Leakage into Production Eligibility
# ===========================================================================

class TestPhase1SyntheticFixtureLeakage:

    def test_synthetic_specs_cannot_be_production_eligible(self):
        kinds = (SpecificationType.INSTRUMENT, SpecificationType.SESSION,
                 SpecificationType.SETTLEMENT, SpecificationType.CLEARING_MARGIN,
                 SpecificationType.EXCHANGE_FEE,
                 SpecificationType.OWNER_BROKER_COMMISSION,
                 SpecificationType.SLIPPAGE, SpecificationType.PARTICIPATION,
                 SpecificationType.RISK_LIMITS)
        records = tuple(econ_spec(k, k.value, owner=False, synthetic=True)
                        for k in kinds)
        report = evaluate_production_eligibility(
            SpecificationRepository((), records),
            InstrumentProfile.ES_FUTURE, "ES", "ES", T0)
        assert not report.eligible
        assert all(i.reason == MissingSpecificationReason.OWNER_APPROVAL_REQUIRED
                   for i in report.issues)

    def test_synthetic_specs_leakage_in_interval_eligibility(self, tmp_path):
        kinds = (SpecificationType.INSTRUMENT, SpecificationType.SESSION,
                 SpecificationType.SETTLEMENT, SpecificationType.CLEARING_MARGIN,
                 SpecificationType.EXCHANGE_FEE,
                 SpecificationType.OWNER_BROKER_COMMISSION,
                 SpecificationType.SLIPPAGE, SpecificationType.PARTICIPATION,
                 SpecificationType.RISK_LIMITS)
        records = tuple(econ_spec(k, k.value, owner=False, synthetic=True)
                        for k in kinds)
        report = evaluate_production_interval(
            repository=SpecificationRepository((), records),
            profile=InstrumentProfile.ES_FUTURE, market="ES", instrument_id="ES",
            required_from=T0, required_to=T2, dataset_fingerprint=H("ds"),
            repository_root=tmp_path)
        assert not report.eligible
        assert all(i.reason_code == "OWNER_APPROVAL_REQUIRED" for i in report.issues
                   if i.reason_code != "SPEC_PROVENANCE_INVALID")


# ===========================================================================
# Phase 1 — Eligibility Reports Return All Applicable Blockers
# ===========================================================================

class TestPhase1EligibilityBlockerCoverage:

    def test_empty_repo_es_returns_nine_blockers(self):
        report = evaluate_production_eligibility(
            SpecificationRepository((), ()),
            InstrumentProfile.ES_FUTURE, "ES", "ES", T0)
        assert not report.eligible
        assert len(report.issues) == 9

    def test_empty_repo_nq_returns_nine_blockers(self):
        report = evaluate_production_eligibility(
            SpecificationRepository((), ()),
            InstrumentProfile.NQ_FUTURE, "NQ", "NQ", T0)
        assert not report.eligible
        assert len(report.issues) == 9

    def test_empty_repo_btc_perp_returns_all_perp_blockers(self):
        report = evaluate_production_eligibility(
            SpecificationRepository((), ()),
            InstrumentProfile.BTC_LINEAR_PERPETUAL, "BTC", "BTC", T0)
        assert not report.eligible
        reasons = {i.reason for i in report.issues}
        assert MissingSpecificationReason.MISSING_MARK_PRICE_HISTORY in reasons
        assert MissingSpecificationReason.MISSING_ORACLE_PRICE_HISTORY in reasons
        assert MissingSpecificationReason.MISSING_FUNDING_HISTORY in reasons
        assert MissingSpecificationReason.MISSING_MARGIN_TIER_HISTORY in reasons
        assert MissingSpecificationReason.MISSING_FEE_TIER_HISTORY in reasons

    def test_empty_repo_btc_spot_returns_spot_blockers(self):
        report = evaluate_production_eligibility(
            SpecificationRepository((), ()),
            InstrumentProfile.BTC_SPOT, "BTC", "BTC", T0)
        assert not report.eligible
        reasons = {i.reason for i in report.issues}
        assert MissingSpecificationReason.MISSING_FEE_TIER_HISTORY in reasons
        assert MissingSpecificationReason.MISSING_SLIPPAGE_SPEC in reasons
        assert MissingSpecificationReason.MISSING_PARTICIPATION_SPEC in reasons
        assert MissingSpecificationReason.MISSING_RISK_LIMIT_SPEC in reasons

    def test_btc_unknown_returns_single_unsupported_blocker(self):
        report = evaluate_production_eligibility(
            SpecificationRepository((), ()),
            InstrumentProfile.BTC_UNKNOWN_UNSUPPORTED, "BTC", "BTC", T0)
        assert not report.eligible
        assert len(report.issues) == 1
        assert report.issues[0].reason == MissingSpecificationReason.INSTRUMENT_PROFILE_UNPROVEN

    def test_interval_eligibility_returns_all_blockers(self, tmp_path):
        report = evaluate_production_interval(
            repository=SpecificationRepository((), ()),
            profile=InstrumentProfile.ES_FUTURE, market="ES", instrument_id="ES",
            required_from=T0, required_to=T2, dataset_fingerprint=H("ds"),
            repository_root=tmp_path)
        assert not report.eligible
        reason_codes = {i.reason_code for i in report.issues}
        # Note: _precise_reason remaps SLIPPAGE→MISSING_EXECUTION_COST_SPEC
        # and CLEARING_MARGIN→MISSING_MARGIN_SPEC
        assert {"MISSING_INSTRUMENT_SPEC", "MISSING_SESSION_SPEC",
                "MISSING_SETTLEMENT_SPEC", "MISSING_MARGIN_SPEC",
                "MISSING_EXECUTION_COST_SPEC", "MISSING_BROKER_COMMISSION_SPEC",
                "MISSING_PARTICIPATION_SPEC", "MISSING_RISK_LIMIT_SPEC"}.issubset(reason_codes)
        assert len(report.issues) == 9


# ===========================================================================
# Phase 1 — Deterministic Serialization and Fingerprints
# ===========================================================================

class TestPhase1DeterministicSerialization:

    def test_equal_fingerprints_for_equal_records(self):
        a = instrument_spec()
        b = instrument_spec()
        assert canonical_fingerprint(a) == canonical_fingerprint(b)
        assert canonical_json_bytes(a) == canonical_json_bytes(b)

    def test_decimal_normalization_in_fingerprint(self):
        assert canonical_fingerprint(Decimal("1.0")) == canonical_fingerprint(Decimal("1.00"))
        assert canonical_fingerprint(Decimal("1.10")) == canonical_fingerprint(Decimal("1.1"))

    def test_order_fingerprint_stable_across_construction(self):
        a = order_intent()
        b = order_intent()
        assert canonical_fingerprint(a) == canonical_fingerprint(b)
        assert canonical_json_bytes(a) == canonical_json_bytes(b)

    def test_serialization_does_not_contain_float(self):
        serialized = canonical_json_bytes(order_intent())
        assert b"6000.25" in serialized
        # No float representation like 6000.25e+03
        assert b"e+" not in serialized

    def test_eligibility_report_deterministic(self, tmp_path):
        a = evaluate_production_interval(
            repository=SpecificationRepository((), ()),
            profile=InstrumentProfile.ES_FUTURE, market="ES", instrument_id="ES",
            required_from=T0, required_to=T2, dataset_fingerprint=H("ds"),
            repository_root=tmp_path)
        b = evaluate_production_interval(
            repository=SpecificationRepository((), ()),
            profile=InstrumentProfile.ES_FUTURE, market="ES", instrument_id="ES",
            required_from=T0, required_to=T2, dataset_fingerprint=H("ds"),
            repository_root=tmp_path)
        assert a == b
        import json
        assert json.dumps(a.as_machine_dict(), sort_keys=True,
                          separators=(",", ":")) == json.dumps(
            b.as_machine_dict(), sort_keys=True, separators=(",", ":"))


# ===========================================================================
# Phase 1 — SHA-256 Identity Validation
# ===========================================================================

class TestPhase1Sha256Identity:

    def test_short_sha_rejected(self):
        with pytest.raises(ValueError, match="SHA-256"):
            instrument_spec(specification_id="abc")

    def test_uppercase_sha_rejected(self):
        with pytest.raises(ValueError, match="SHA-256"):
            instrument_spec(specification_id="A" * 64)

    def test_non_hex_sha_rejected(self):
        with pytest.raises(ValueError, match="SHA-256"):
            instrument_spec(specification_id="g" * 64)

    def test_order_self_reference_rejected(self):
        with pytest.raises(ValueError, match="self-reference"):
            order_intent(parent_order_id=H("order"))
        with pytest.raises(ValueError, match="self-reference"):
            order_intent(replaces_order_id=H("order"))


# ===========================================================================
# Phase 1 — Order Type / TIF Validation
# ===========================================================================

class TestPhase1OrderTypeValidation:

    def test_market_order_rejects_limit_and_stop_prices(self):
        with pytest.raises(ValueError, match="market"):
            order_intent(order_type=OrderType.MARKET,
                         limit_price=Decimal("6000.25"))

    def test_limit_order_requires_limit_price(self):
        with pytest.raises(ValueError, match="limit_price"):
            order_intent(order_type=OrderType.LIMIT, limit_price=None)

    def test_stop_market_requires_stop_price(self):
        with pytest.raises(ValueError, match="stop_price"):
            order_intent(order_type=OrderType.STOP_MARKET, stop_price=None)

    def test_stop_limit_requires_both_prices(self):
        with pytest.raises(ValueError, match="stop_price"):
            order_intent(order_type=OrderType.STOP_LIMIT,
                         limit_price=Decimal("6001.25"), stop_price=None)
        with pytest.raises(ValueError, match="limit_price"):
            order_intent(order_type=OrderType.STOP_LIMIT,
                         limit_price=None, stop_price=Decimal("6001"))

    def test_activation_before_submission_rejected(self):
        with pytest.raises(ValueError, match="activation"):
            order_intent(submitted_at=T0 + timedelta(minutes=1),
                         activation_at=T0)

    def test_expiry_before_activation_rejected(self):
        with pytest.raises(ValueError, match="expiry"):
            order_intent(expires_at=T0,
                         activation_at=T0 + timedelta(minutes=1))


# ===========================================================================
# Phase 1 — Grid Validation
# ===========================================================================

class TestPhase1GridValidation:

    def test_off_grid_quantity_detected(self):
        bad = order_intent(quantity=Decimal("1.5"))
        report = validate_order_against_instrument(bad, instrument_spec())
        assert any(i.reason == MissingSpecificationReason.OFF_TICK_ECONOMICS
                   for i in report.issues)

    def test_off_grid_limit_price_detected(self):
        bad = order_intent(limit_price=Decimal("6000.10"))
        report = validate_order_against_instrument(bad, instrument_spec())
        assert any(i.reason == MissingSpecificationReason.OFF_TICK_ECONOMICS
                   for i in report.issues)

    def test_on_grid_quantities_pass(self):
        good = order_intent(quantity=Decimal("3"), limit_price=Decimal("6000.25"))
        report = validate_order_against_instrument(good, instrument_spec())
        assert report.valid

    def test_fill_off_grid_quantity_detected(self):
        f = fill_v2(quantity=Decimal("1.5"))
        report = validate_fill_against_order(f, order_intent(), instrument_spec())
        assert any(i.reason == MissingSpecificationReason.OFF_TICK_ECONOMICS
                   for i in report.issues)

    def test_fill_exceeds_order_quantity_detected(self):
        f = fill_v2(quantity=Decimal("4"))
        report = validate_fill_against_order(f, order_intent(), instrument_spec())
        assert any(i.reason == MissingSpecificationReason.OFF_TICK_ECONOMICS
                   for i in report.issues)

    def test_fill_side_mismatch_detected(self):
        f = fill_v2(side=OrderSide.SELL)
        report = validate_fill_against_order(f, order_intent(), instrument_spec())
        assert any(i.reason == MissingSpecificationReason.INSTRUMENT_IDENTITY_MISMATCH
                   for i in report.issues)


# ===========================================================================
# Phase 1 — Repository Provenance
# ===========================================================================

class TestPhase1RepositoryProvenance:

    def test_valid_provenance(self, tmp_path):
        snap = tmp_path / "snap.md"
        snap.write_bytes(b"content")
        sha = hashlib.sha256(b"content").hexdigest()
        ev = EvidenceRecord("ev1", "CME", "doc", None, "snap.md", sha,
                            T0, T0, T2, "ES", "ES", ("tick",))
        spec = econ_spec(SpecificationType.INSTRUMENT, "s1", evidence=("ev1",))
        repo = SpecificationRepository((ev,), (spec,))
        report = validate_repository_provenance(repo, tmp_path)
        assert report.valid

    def test_missing_evidence_id_in_spec(self, tmp_path):
        ev = evidence_record("ev1")
        spec = econ_spec(SpecificationType.INSTRUMENT, "s1", evidence=("ev2",))
        with pytest.raises(ValueError, match="lineage"):
            SpecificationRepository((ev,), (spec,))

    def test_duplicate_evidence_rejected(self):
        ev = evidence_record("ev1")
        with pytest.raises(ValueError, match="duplicate"):
            SpecificationRepository((ev, ev), ())

    def test_duplicate_spec_rejected(self):
        s1 = econ_spec(SpecificationType.INSTRUMENT, "dup")
        with pytest.raises(ValueError, match="duplicate"):
            SpecificationRepository((), (s1, s1))


# ===========================================================================
# Phase 2 — State Transition Graph: Implementation vs. Frozen Matrix
# ===========================================================================

class TestPhase2StateTransitionGraph:
    """Derive the state-transition graph from the implementation and verify
    it matches the frozen matrix in ORDER_LEDGER_TRANSITION_MATRIX.md."""

    EXPECTED_TRANSITIONS = {
        OrderState.CREATED: frozenset({
            LedgerEventKind.SUBMIT, LedgerEventKind.FORCED_CLOSE_INTENT}),
        OrderState.SUBMITTED: frozenset({
            LedgerEventKind.ACCEPT, LedgerEventKind.REJECT}),
        OrderState.ACCEPTED: frozenset({
            LedgerEventKind.ACTIVATE, LedgerEventKind.REJECT,
            LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL}),
        OrderState.ACTIVE: frozenset({
            LedgerEventKind.TRIGGER, LedgerEventKind.FILL,
            LedgerEventKind.EXECUTION_EVALUATED,
            LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL,
            LedgerEventKind.EXPIRE, LedgerEventKind.REPLACE}),
        OrderState.TRIGGERED: frozenset({
            LedgerEventKind.FILL, LedgerEventKind.EXECUTION_EVALUATED,
            LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL,
            LedgerEventKind.EXPIRE, LedgerEventKind.REPLACE}),
        OrderState.PARTIALLY_FILLED: frozenset({
            LedgerEventKind.FILL, LedgerEventKind.CANCEL_REQUEST,
            LedgerEventKind.CANCEL, LedgerEventKind.EXPIRE,
            LedgerEventKind.REPLACE}),
        OrderState.CANCEL_REQUESTED: frozenset({
            LedgerEventKind.FILL, LedgerEventKind.CANCEL,
            LedgerEventKind.EXPIRE}),
    }

    def test_allowed_transitions_match_expected(self):
        from backtesting.execution_accounting_v2.order_ledger import ALLOWED_TRANSITIONS
        assert ALLOWED_TRANSITIONS == self.EXPECTED_TRANSITIONS

    def test_all_nonterminal_states_have_transitions(self):
        from backtesting.execution_accounting_v2.order_ledger import ALLOWED_TRANSITIONS
        nonterminal = set(OrderState) - {
            OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED,
            OrderState.EXPIRED, OrderState.REPLACED}
        assert set(ALLOWED_TRANSITIONS) == nonterminal

    def test_terminal_states_have_no_outgoing_edges(self):
        from backtesting.execution_accounting_v2.order_ledger import ALLOWED_TRANSITIONS
        for terminal in (OrderState.FILLED, OrderState.REJECTED,
                         OrderState.CANCELLED, OrderState.EXPIRED,
                         OrderState.REPLACED):
            assert terminal not in ALLOWED_TRANSITIONS

    def test_every_state_kind_combination_has_boolean_answer(self):
        from backtesting.execution_accounting_v2.order_ledger import ALLOWED_TRANSITIONS
        for state in OrderState:
            for kind in LedgerEventKind:
                allowed = kind in ALLOWED_TRANSITIONS.get(state, frozenset())
                assert isinstance(allowed, bool)


# ===========================================================================
# Phase 2 — Terminal State Immutability
# ===========================================================================

class TestPhase2TerminalStateImmutability:

    def test_filled_state_rejects_all_events(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("3")))
        assert ledger.order(H("order")).state == OrderState.FILLED
        for kind in LedgerEventKind:
            with pytest.raises(OrderLedgerError) as exc:
                evt = ledger_event(ledger, kind)
                if kind == LedgerEventKind.FILL:
                    evt = replace(evt, fill_quantity=Decimal("1"))
                ledger.apply(evt)
            assert exc.value.reason == OrderLedgerReason.TERMINAL_ORDER_MUTATION

    def test_cancelled_state_rejects_fill_with_specific_reason(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.CANCEL_REQUEST))
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.CANCEL))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("1")))
        assert exc.value.reason == OrderLedgerReason.CANCELLED_ORDER_FILL

    def test_replaced_state_rejects_fill_with_specific_reason(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        child = order_intent(order_id=H("child"), action_id=H("ca"),
                             quantity=Decimal("2"),
                             parent_order_id=H("order"),
                             replaces_order_id=H("order"))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.REPLACE,
                         replacement_intent=child))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("1")))
        assert exc.value.reason == OrderLedgerReason.REPLACED_ORDER_FILL

    def test_rejected_state_rejects_all_events(self):
        ledger = OrderLedgerV2.create((order_intent(),))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.SUBMIT))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.REJECT))
        assert ledger.order(H("order")).state == OrderState.REJECTED
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.ACCEPT))
        assert exc.value.reason == OrderLedgerReason.TERMINAL_ORDER_MUTATION

    def test_expired_state_rejects_all_events(self):
        ledger = active_ledger(
            order_intent(time_in_force=TimeInForce.DAY,
                         expires_at=T0 + timedelta(hours=20)))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.EXPIRE,
                         session_boundary_verified=True))
        assert ledger.order(H("order")).state == OrderState.EXPIRED
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.CANCEL))
        assert exc.value.reason == OrderLedgerReason.TERMINAL_ORDER_MUTATION


# ===========================================================================
# Phase 2 — Zero Fills, Overfills, and Quantity Conservation
# ===========================================================================

class TestPhase2QuantityConservation:

    @pytest.mark.parametrize("bad_qty", [Decimal("0"), Decimal("-1"),
                                          Decimal("-0.0001")])
    def test_zero_and_negative_fill_rejected(self, bad_qty):
        ledger = active_ledger()
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=bad_qty))
        assert exc.value.reason == OrderLedgerReason.ZERO_FILL_QUANTITY

    def test_overfill_rejected(self):
        ledger = active_ledger()
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("3.01")))
        assert exc.value.reason == OrderLedgerReason.ORDER_OVERFILL

    def test_exact_fill_allowed(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("3")))
        snap = ledger.order(H("order"))
        assert snap.state == OrderState.FILLED
        assert snap.filled_quantity == Decimal("3")
        assert snap.remaining_quantity == Decimal("0")

    def test_multiple_partial_fills_and_completion(self):
        ledger = active_ledger()
        for _ in range(3):
            ledger = ledger.apply(
                ledger_event(ledger, LedgerEventKind.FILL,
                             fill_quantity=Decimal("1")))
        snap = ledger.order(H("order"))
        assert snap.state == OrderState.FILLED
        assert snap.filled_quantity == Decimal("3")
        assert snap.remaining_quantity == Decimal("0")
        assert snap.accepted_quantity == Decimal("3")
        # Conservation: accepted == filled + remaining
        assert snap.accepted_quantity == snap.filled_quantity + snap.remaining_quantity

    def test_overfill_after_partial_rejected(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("3")))
        assert exc.value.reason == OrderLedgerReason.ORDER_OVERFILL

    def test_every_transition_conserves_quantity(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        for t in ledger.transitions:
            assert t.accepted_quantity == t.filled_quantity + t.remaining_quantity

    def test_snapshot_conservation_after_each_event(self):
        ledger = active_ledger()
        for qty in (Decimal("1"), Decimal("1"), Decimal("1")):
            ledger = ledger.apply(
                ledger_event(ledger, LedgerEventKind.FILL,
                             fill_quantity=qty))
            snap = ledger.order(H("order"))
            assert snap.accepted_quantity == snap.filled_quantity + snap.remaining_quantity


# ===========================================================================
# Phase 2 — Cancellation / Fill Ordering
# ===========================================================================

class TestPhase2CancellationFillOrdering:

    def test_fill_then_cancel_preserves_filled_quantity(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.CANCEL_REQUEST))
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.CANCEL))
        snap = ledger.order(H("order"))
        assert snap.state == OrderState.CANCELLED
        assert snap.filled_quantity == Decimal("1")

    def test_cancel_then_fill_after_cancel_rejected(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.CANCEL_REQUEST))
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.CANCEL))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("1")))
        assert exc.value.reason == OrderLedgerReason.CANCELLED_ORDER_FILL

    def test_fill_in_cancel_requested_allowed(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.CANCEL_REQUEST))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        snap = ledger.order(H("order"))
        assert snap.state == OrderState.PARTIALLY_FILLED
        assert snap.filled_quantity == Decimal("1")


# ===========================================================================
# Phase 2 — Replacement Lineage After Partial Fill
# ===========================================================================

class TestPhase2ReplacementLineage:

    def test_replacement_after_partial_fill(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        child = order_intent(order_id=H("child"), action_id=H("ca"),
                             quantity=Decimal("2"),
                             parent_order_id=H("order"),
                             replaces_order_id=H("order"))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.REPLACE,
                         replacement_intent=child))
        parent = ledger.order(H("order"))
        child_snap = ledger.order(H("child"))
        assert parent.state == OrderState.REPLACED
        assert parent.filled_quantity == Decimal("1")
        assert parent.replacement_child_order_id == H("child")
        assert child_snap.state == OrderState.CREATED
        assert child_snap.intent.parent_order_id == H("order")
        assert child_snap.intent.replaces_order_id == H("order")

    def test_replacement_quantity_exceeds_residual_rejected(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        oversized = order_intent(order_id=H("child"), action_id=H("ca"),
                                 quantity=Decimal("4"),
                                 parent_order_id=H("order"),
                                 replaces_order_id=H("order"))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.REPLACE,
                                      replacement_intent=oversized))
        assert exc.value.reason == OrderLedgerReason.INVALID_REPLACEMENT

    def test_replacement_without_parent_link_rejected(self):
        ledger = active_ledger()
        bad = order_intent(order_id=H("child"), parent_order_id=None)
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.REPLACE,
                                      replacement_intent=bad))
        assert exc.value.reason == OrderLedgerReason.INVALID_REPLACEMENT

    def test_replaced_parent_preserves_transition_history(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        parent_before = ledger.order(H("order"))
        child = order_intent(order_id=H("child"), action_id=H("ca"),
                             quantity=Decimal("2"),
                             parent_order_id=H("order"),
                             replaces_order_id=H("order"))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.REPLACE,
                         replacement_intent=child))
        parent = ledger.order(H("order"))
        assert parent.transition_ids[:len(parent_before.transition_ids)] == \
            parent_before.transition_ids


# ===========================================================================
# Phase 2 — Duplicate and Conflicting Event Identities
# ===========================================================================

class TestPhase2DuplicateConflictingEvents:

    def test_exact_duplicate_is_idempotent(self):
        ledger = active_ledger()
        evt = ledger_event(ledger, LedgerEventKind.CANCEL_REQUEST)
        updated = ledger.apply(evt)
        assert updated.apply(evt) is updated

    def test_conflicting_same_event_id_rejected(self):
        ledger = active_ledger()
        evt = ledger_event(ledger, LedgerEventKind.CANCEL_REQUEST)
        updated = ledger.apply(evt)
        conflicting = replace(evt, reason_code="different")
        with pytest.raises(OrderLedgerError) as exc:
            updated.apply(conflicting)
        assert exc.value.reason == OrderLedgerReason.DUPLICATE_EVENT_CONFLICT


# ===========================================================================
# Phase 2 — Stale Expected Versions
# ===========================================================================

class TestPhase2StaleVersions:

    def test_stale_version_rejected(self):
        ledger = OrderLedgerV2.create((order_intent(),))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.SUBMIT,
                                      expected=1))
        assert exc.value.reason == OrderLedgerReason.STALE_ORDER_VERSION

    def test_wrong_identity_rejected(self):
        ledger = OrderLedgerV2.create((order_intent(),))
        wrong = ledger_event(ledger, LedgerEventKind.SUBMIT, market="NQ")
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(wrong)
        assert exc.value.reason == OrderLedgerReason.ORDER_IDENTITY_MISMATCH


# ===========================================================================
# Phase 2 — Equal-Timestamp Deterministic Ordering
# ===========================================================================

class TestPhase2EqualTimestampOrdering:

    def test_equal_timestamp_priority_then_identity(self):
        ledger = OrderLedgerV2.create((order_intent(),))
        at = T0 + timedelta(minutes=1)
        submit = ledger_event(ledger, LedgerEventKind.SUBMIT, at=at,
                              event_id=H("a"))
        ledger = ledger.apply(submit)
        accept = ledger_event(ledger, LedgerEventKind.ACCEPT, at=at,
                              event_id=H("b"))
        ledger = ledger.apply(accept)
        assert ledger.order(H("order")).state == OrderState.ACCEPTED

    def test_equal_timestamp_wrong_order_rejected(self):
        ledger = OrderLedgerV2.create((order_intent(),))
        at = T0 + timedelta(minutes=1)
        submit = ledger_event(ledger, LedgerEventKind.SUBMIT, at=at,
                              event_id=H("z"))
        ledger = ledger.apply(submit)
        # Same priority, but event_id "0"*64 < H("z") — should reject
        bad = ledger_event(ledger, LedgerEventKind.SUBMIT, at=at,
                           event_id="0" * 64)
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(bad)
        assert exc.value.reason == OrderLedgerReason.EVENT_SEQUENCE_REGRESSION

    def test_time_regression_rejected(self):
        ledger = active_ledger()
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("1"),
                                      at=T0 - timedelta(hours=1)))
        assert exc.value.reason == OrderLedgerReason.EVENT_TIME_REGRESSION

    def test_sequence_regression_rejected(self):
        ledger = OrderLedgerV2.create((order_intent(),))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.SUBMIT))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.ACCEPT,
                                      sequence_number=5))
        assert exc.value.reason == OrderLedgerReason.EVENT_SEQUENCE_REGRESSION


# ===========================================================================
# Phase 2 — DAY, GTC, and IOC Constraints
# ===========================================================================

class TestPhase2TIFConstraints:

    def test_day_expire_requires_session_boundary(self):
        ledger = active_ledger(
            order_intent(time_in_force=TimeInForce.DAY,
                         expires_at=T0 + timedelta(hours=20)))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.EXPIRE,
                                      session_boundary_verified=False))
        assert exc.value.reason == OrderLedgerReason.SESSION_BOUNDARY_UNPROVEN

    def test_day_expire_with_boundary_succeeds(self):
        ledger = active_ledger(
            order_intent(time_in_force=TimeInForce.DAY,
                         expires_at=T0 + timedelta(hours=20)))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.EXPIRE,
                         session_boundary_verified=True))
        assert ledger.order(H("order")).state == OrderState.EXPIRED

    def test_gtc_expire_requires_contract_eligibility(self):
        ledger = active_ledger()
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.EXPIRE,
                                      contract_eligibility_verified=False))
        assert exc.value.reason == OrderLedgerReason.CONTRACT_ELIGIBILITY_UNPROVEN

    def test_gtc_fill_requires_contract_eligibility(self):
        ledger = active_ledger()
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("1"),
                                      contract_eligibility_verified=False))
        assert exc.value.reason == OrderLedgerReason.CONTRACT_ELIGIBILITY_UNPROVEN

    def test_ioc_partial_fill_cancels_residual(self):
        ledger = active_ledger(
            order_intent(time_in_force=TimeInForce.IOC))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        snap = ledger.order(H("order"))
        assert snap.state == OrderState.CANCELLED
        assert snap.filled_quantity == Decimal("1")
        assert snap.ioc_evaluated

    def test_ioc_full_fill_no_cancel(self):
        ledger = active_ledger(
            order_intent(time_in_force=TimeInForce.IOC))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("3")))
        snap = ledger.order(H("order"))
        assert snap.state == OrderState.FILLED
        # IOC flag is set even on full fill (evaluation happened)
        assert snap.ioc_evaluated

    def test_ioc_no_fill_evaluation_cancels(self):
        ledger = active_ledger(
            order_intent(time_in_force=TimeInForce.IOC))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.EXECUTION_EVALUATED))
        assert ledger.order(H("order")).state == OrderState.CANCELLED
        assert ledger.order(H("order")).ioc_evaluated

    def test_ioc_double_evaluation_rejected(self):
        ledger = active_ledger(
            order_intent(time_in_force=TimeInForce.IOC))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.EXECUTION_EVALUATED))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(
                ledger_event(ledger, LedgerEventKind.EXECUTION_EVALUATED))
        assert exc.value.reason == OrderLedgerReason.IOC_ALREADY_EVALUATED

    def test_day_fill_does_not_require_contract_eligibility(self):
        """DAY orders should NOT be gated by GTC contract eligibility for fills."""
        ledger = active_ledger(
            order_intent(time_in_force=TimeInForce.DAY,
                         expires_at=T0 + timedelta(hours=20)))
        # Should not raise CONTRACT_ELIGIBILITY_UNPROVEN for DAY fill
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1"),
                         contract_eligibility_verified=False))
        assert ledger.order(H("order")).state == OrderState.PARTIALLY_FILLED


# ===========================================================================
# Phase 2 — Stop-Limit Trigger/Fill Separation
# ===========================================================================

class TestPhase2StopLimitTriggerFill:

    def test_stop_market_requires_trigger_before_fill(self):
        selected = order_intent(order_type=OrderType.STOP_MARKET,
                                stop_price=Decimal("6001"),
                                limit_price=None)
        ledger = active_ledger(selected)
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("1")))
        assert exc.value.reason == OrderLedgerReason.STOP_NOT_TRIGGERED

    def test_stop_limit_requires_trigger_before_fill(self):
        selected = order_intent(order_type=OrderType.STOP_LIMIT,
                                stop_price=Decimal("6001"),
                                limit_price=Decimal("6001.25"))
        ledger = active_ledger(selected)
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      fill_quantity=Decimal("1")))
        assert exc.value.reason == OrderLedgerReason.STOP_NOT_TRIGGERED

    def test_stop_limit_fill_at_trigger_time_rejected(self):
        selected = order_intent(order_type=OrderType.STOP_LIMIT,
                                stop_price=Decimal("6001"),
                                limit_price=Decimal("6001.25"))
        ledger = active_ledger(selected)
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.TRIGGER))
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                      at=ledger.events[-1].event_time,
                                      fill_quantity=Decimal("1")))
        assert exc.value.reason == OrderLedgerReason.INVALID_ORDER_TRANSITION

    def test_stop_limit_fill_after_trigger_succeeds(self):
        selected = order_intent(order_type=OrderType.STOP_LIMIT,
                                stop_price=Decimal("6001"),
                                limit_price=Decimal("6001.25"))
        ledger = active_ledger(selected)
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.TRIGGER))
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.FILL,
                                            fill_quantity=Decimal("1")))
        assert ledger.order(H("order")).state == OrderState.PARTIALLY_FILLED

    def test_non_stop_trigger_rejected(self):
        ledger = active_ledger()
        with pytest.raises(OrderLedgerError) as exc:
            ledger.apply(ledger_event(ledger, LedgerEventKind.TRIGGER))
        assert exc.value.reason == OrderLedgerReason.INVALID_ORDER_TRANSITION


# ===========================================================================
# Phase 2 — Checkpoint / Replay Equivalence and Tamper Detection
# ===========================================================================

class TestPhase2CheckpointReplay:

    def test_checkpoint_resume_equals_replay(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1")))
        checkpoint = ledger.checkpoint()
        next_evt = ledger_event(ledger, LedgerEventKind.FILL,
                                fill_quantity=Decimal("1"))
        resumed = OrderLedgerV2.resume(checkpoint, (next_evt,))
        replayed = OrderLedgerV2.replay((order_intent(),), resumed.events)
        assert resumed == replayed
        assert resumed.serialize() == replayed.serialize()

    def test_tampered_fingerprint_detected(self):
        ledger = active_ledger()
        tampered = replace(ledger, ledger_fingerprint="0" * 64)
        with pytest.raises(OrderLedgerError) as exc:
            tampered.verify_integrity()
        assert exc.value.reason == OrderLedgerReason.DUPLICATE_EVENT_CONFLICT

    def test_reordered_events_rejected(self):
        ledger = active_ledger()
        reordered = tuple(reversed(ledger.events))
        with pytest.raises(OrderLedgerError):
            OrderLedgerV2.replay((order_intent(),), reordered)

    def test_repeated_replay_is_identical(self):
        """Run replay N times; all must produce the same serialization."""
        events = active_ledger().events
        results = []
        for _ in range(5):
            ledger = OrderLedgerV2.replay((order_intent(),), events)
            results.append(ledger.serialize())
        assert all(r == results[0] for r in results)

    def test_checkpoint_fingerprint_matches_ledger(self):
        ledger = active_ledger()
        checkpoint = ledger.checkpoint()
        assert checkpoint.ledger_fingerprint == ledger.ledger_fingerprint


# ===========================================================================
# Phase 2 — Mixed v1/v2 Rejection
# ===========================================================================

class TestPhase2MixedVersionRejection:

    def test_create_with_v1_version_rejected(self):
        with pytest.raises(OrderLedgerError) as exc:
            OrderLedgerV2.create((order_intent(),),
                                 ledger_version="order-ledger-v1")
        assert exc.value.reason == OrderLedgerReason.MIXED_LEDGER_VERSION

    def test_event_with_wrong_schema_rejected(self):
        ledger = active_ledger()
        # The event construction itself should reject the wrong schema
        with pytest.raises(ValueError, match="schema"):
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("1"),
                         schema_version="order-ledger-event-v1")


# ===========================================================================
# Phase 2 — Forced Close Intent
# ===========================================================================

class TestPhase2ForcedCloseIntent:

    def test_forced_close_intent_sets_flag(self):
        ledger = OrderLedgerV2.create((order_intent(),))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FORCED_CLOSE_INTENT))
        assert ledger.order(H("order")).forced_close_intent
        assert ledger.order(H("order")).state == OrderState.SUBMITTED

    def test_forced_close_preserved_through_lifecycle(self):
        ledger = OrderLedgerV2.create((order_intent(),))
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FORCED_CLOSE_INTENT))
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.ACCEPT))
        assert ledger.order(H("order")).forced_close_intent
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.ACTIVATE))
        assert ledger.order(H("order")).forced_close_intent


# ===========================================================================
# Phase 2 — End-of-Data Validation
# ===========================================================================

class TestPhase2EndOfData:

    def test_nonterminal_residual_rejected(self):
        ledger = active_ledger()
        with pytest.raises(OrderLedgerError) as exc:
            ledger.validate_end_of_data()
        assert exc.value.reason == OrderLedgerReason.END_OF_DATA_RESIDUAL

    def test_terminal_state_passes_end_of_data(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.FILL,
                         fill_quantity=Decimal("3")))
        ledger.validate_end_of_data()

    def test_cancelled_passes_end_of_data(self):
        ledger = active_ledger()
        ledger = ledger.apply(
            ledger_event(ledger, LedgerEventKind.CANCEL_REQUEST))
        ledger = ledger.apply(ledger_event(ledger, LedgerEventKind.CANCEL))
        ledger.validate_end_of_data()


# ===========================================================================
# Phase 2 — Deterministic Output Comparison (Repeated)
# ===========================================================================

class TestPhase2DeterministicOutput:

    def test_repeated_full_lifecycle_identical(self):
        """Run a complete order lifecycle 10 times; all outputs must match."""
        results = []
        for i in range(10):
            ledger = OrderLedgerV2.create((order_intent(),))
            for kind in (LedgerEventKind.SUBMIT, LedgerEventKind.ACCEPT,
                         LedgerEventKind.ACTIVATE):
                ledger = ledger.apply(ledger_event(ledger, kind))
            ledger = ledger.apply(
                ledger_event(ledger, LedgerEventKind.FILL,
                             fill_quantity=Decimal("1")))
            ledger = ledger.apply(
                ledger_event(ledger, LedgerEventKind.FILL,
                             fill_quantity=Decimal("2")))
            results.append(ledger.serialize())
        assert all(r == results[0] for r in results)

    def test_repeated_ioc_lifecycle_identical(self):
        results = []
        for i in range(10):
            ledger = active_ledger(
                order_intent(time_in_force=TimeInForce.IOC))
            ledger = ledger.apply(
                ledger_event(ledger, LedgerEventKind.FILL,
                             fill_quantity=Decimal("1")))
            results.append(ledger.serialize())
        assert all(r == results[0] for r in results)

    def test_fingerprint_stable_across_construction(self):
        a = active_ledger()
        b = active_ledger()
        assert a.ledger_fingerprint == b.ledger_fingerprint
        assert a.serialize() == b.serialize()
