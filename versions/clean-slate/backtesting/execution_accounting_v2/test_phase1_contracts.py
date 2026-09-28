from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from backtesting.execution_accounting_v2 import (
    AccountingSnapshotV2, BacktestResultIdentityV2, CapabilityDeclarationV2,
    EvidenceRecord, FillV2, InstrumentProfile, InstrumentSpecificationV2,
    MissingSpecificationReason, OrderIntentV2, OrderSide, OrderState,
    OrderTransitionV2, OrderType, OwnerAssumptionV2, RiskDecision, RiskEventV2,
    RiskPhase, SpecificationRecord, SpecificationRepository, SpecificationType,
    TimeInForce, canonical_fingerprint, canonical_json_bytes, evaluate_production_interval,
    validate_evidence_checksum, validate_fill_against_order,
    validate_order_against_instrument, validate_specification_intervals,
)

UTC = timezone.utc
START = datetime(2025, 6, 1, tzinfo=UTC)
END = datetime(2025, 7, 1, tzinfo=UTC)
H = lambda c: c * 64


def instrument(**changes):
    values = dict(schema_version="instrument-spec-v2-1", specification_id=H("a"), market="ES",
                  instrument_id="ES", contract_id="ESM5", profile=InstrumentProfile.ES_FUTURE,
                  currency="USD", tick_size=Decimal("0.25"), quantity_step=Decimal("1"),
                  contract_multiplier=Decimal("50"), point_value=Decimal("50"),
                  effective_from=START, effective_to=END, evidence_ids=("cme-358",))
    values.update(changes)
    return InstrumentSpecificationV2(**values)


def order(**changes):
    values = dict(schema_version="order-intent-v2-1", order_id=H("b"), run_id=H("c"),
                  action_id=H("d"), market="ES", instrument_id="ES", contract_id="ESM5",
                  side=OrderSide.BUY, quantity=Decimal("2"), order_type=OrderType.LIMIT,
                  time_in_force=TimeInForce.DAY, limit_price=Decimal("6000.25"), stop_price=None,
                  submitted_at=START, activation_at=START + timedelta(minutes=1),
                  expires_at=START + timedelta(hours=20), parent_order_id=None,
                  replaces_order_id=None, configuration_version="config-v2",
                  execution_policy_version="CONSERVATIVE_OHLC_1M_V1")
    values.update(changes)
    return OrderIntentV2(**values)


def fill(**changes):
    values = dict(schema_version="fill-v2-1", fill_id=H("e"), order_id=H("b"),
                  market_event_id=H("f"), market="ES", instrument_id="ES", contract_id="ESM5",
                  fill_time=START + timedelta(minutes=2), side=OrderSide.BUY,
                  quantity=Decimal("1"), economic_price=Decimal("6000.25"),
                  reference_price=Decimal("6000.25"), friction=Decimal("0"),
                  fee_total=Decimal("0"), currency="USD", execution_rule_code="RECORD_ONLY",
                  execution_policy_version="CONSERVATIVE_OHLC_1M_V1")
    values.update(changes)
    return FillV2(**values)


def economic(kind, sid, start=START, end=END, *, owner=True, synthetic=False, evidence=("ev",)):
    return SpecificationRecord(sid, "economic-specification-v2-1", kind, "ES", "ES",
                               start, end, (("value", "1"),), () if synthetic else evidence,
                               owner, synthetic)


def test_all_phase1_records_are_immutable():
    records = [instrument(), order(), fill(),
        OrderTransitionV2("order-transition-v2-1", H("1"), H("b"), START,
                          OrderState.ACTIVE, OrderState.CANCELLED, "OWNER_CANCEL", ()),
        AccountingSnapshotV2("accounting-snapshot-v2-1", H("2"), H("c"), START, "USD",
                             *(Decimal("0") for _ in range(9)), (), "accounting-v2"),
        RiskEventV2("risk-event-v2-1", H("3"), H("c"), START, "ES", "ES",
                    RiskPhase.PRE_TRADE, RiskDecision.REJECT, ("MISSING_RISK_LIMIT_SPEC",), (), "risk-v2"),
        BacktestResultIdentityV2("backtest-result-v2-1", H("4"), H("c"), H("5"), H("6"), H("7"),
                                 "strategy-v1", "execution-v2", "accounting-v2", "risk-v2",
                                 START, END, (), True)]
    for record in records:
        with pytest.raises(FrozenInstanceError):
            record.schema_version = "changed"


@pytest.mark.parametrize("field,value", [("tick_size", 1), ("quantity_step", 1.0),
                                           ("contract_multiplier", Decimal("NaN"))])
def test_decimal_fields_reject_integer_float_and_nonfinite(field, value):
    with pytest.raises(ValueError):
        instrument(**{field: value})


def test_owner_assumptions_reject_numeric_leakage_and_synthetic_approval():
    base = dict(schema_version="owner-assumption-v2-1", assumption_id=H("8"),
                assumption_type="SLIPPAGE", market="ES", instrument_id="ES",
                effective_from=START, effective_to=END, decision_reference="owner-decision")
    with pytest.raises(ValueError):
        OwnerAssumptionV2(**base, decimal_values=(("ticks", 1),), owner_approved=False,
                          synthetic_test_only=True)
    with pytest.raises(ValueError, match="synthetic"):
        OwnerAssumptionV2(**base, decimal_values=(("ticks", Decimal("1")),), owner_approved=True,
                          synthetic_test_only=True)


def test_timezone_naive_and_invalid_schema_versions_reject():
    with pytest.raises(ValueError, match="UTC"):
        order(submitted_at=datetime(2025, 6, 1), activation_at=START)
    with pytest.raises(ValueError, match="schema_version"):
        order(schema_version="order-intent-v1")


def test_order_and_fill_grid_identity_and_chronology_validation_collects_issues():
    bad_order = order(contract_id="NQM5", quantity=Decimal("1.5"), limit_price=Decimal("6000.10"))
    report = validate_order_against_instrument(bad_order, instrument())
    reasons = [item.reason for item in report.issues]
    assert MissingSpecificationReason.INSTRUMENT_IDENTITY_MISMATCH in reasons
    assert reasons.count(MissingSpecificationReason.OFF_TICK_ECONOMICS) == 2
    bad_fill = fill(fill_time=START, economic_price=Decimal("6000.10"),
                    reference_price=Decimal("6000.10"), quantity=Decimal("3"))
    fill_report = validate_fill_against_order(bad_fill, order(), instrument())
    assert len(fill_report.issues) == 4


def test_effective_interval_gap_and_overlap_are_precise():
    a = economic(SpecificationType.SESSION, "a", START, START + timedelta(days=10))
    b = economic(SpecificationType.SESSION, "b", START + timedelta(days=12), END)
    gap = validate_specification_intervals((a, b), SpecificationType.SESSION, "ES", "ES", START, END)
    assert gap.issues[0].reason == MissingSpecificationReason.SPEC_EFFECTIVE_DATE_GAP
    assert gap.issues[0].effective_from == START + timedelta(days=10)
    overlap_b = replace(b, effective_from=START + timedelta(days=9))
    overlap = validate_specification_intervals((a, overlap_b), SpecificationType.SESSION,
                                               "ES", "ES", START, END)
    assert overlap.issues[0].reason == MissingSpecificationReason.SPEC_EFFECTIVE_DATE_OVERLAP


def test_evidence_checksum_success_change_and_path_escape(tmp_path):
    snapshot = tmp_path / "source.md"
    snapshot.write_bytes(b"first-party fact")
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    ev = EvidenceRecord("ev", "CME", "chapter", "https://example.invalid", "source.md", digest,
                        START, START, END, "ES", "ES", ("tick",))
    assert validate_evidence_checksum(ev, tmp_path).valid
    snapshot.write_bytes(b"changed")
    assert validate_evidence_checksum(ev, tmp_path).issues[0].reason == MissingSpecificationReason.SPEC_CHECKSUM_MISMATCH
    escaped = replace(ev, local_snapshot_path="../outside")
    assert validate_evidence_checksum(escaped, tmp_path).issues[0].reason == MissingSpecificationReason.SPEC_PROVENANCE_INVALID


def test_conflicting_source_claims_produce_overlap_not_silent_selection(tmp_path):
    snap = tmp_path / "source.md"; snap.write_text("fact", encoding="utf-8")
    ev = EvidenceRecord("ev", "CME", "chapter", None, "source.md",
                        hashlib.sha256(snap.read_bytes()).hexdigest(), START, START, END,
                        "ES", "ES", ("margin",))
    records = (economic(SpecificationType.CLEARING_MARGIN, "a"),
               replace(economic(SpecificationType.CLEARING_MARGIN, "b"), values=(("value", "2"),)))
    report = evaluate_production_interval(repository=SpecificationRepository((ev,), records),
        profile=InstrumentProfile.ES_FUTURE, market="ES", instrument_id="ES",
        required_from=START, required_to=END, dataset_fingerprint=H("9"), repository_root=tmp_path)
    assert "SPEC_EFFECTIVE_DATE_OVERLAP" in {item.reason_code for item in report.issues}


def test_complete_multi_reason_report_identifies_classes_fields_and_interval(tmp_path):
    report = evaluate_production_interval(repository=SpecificationRepository((), ()),
        profile=InstrumentProfile.ES_FUTURE, market="ES", instrument_id="ES",
        required_from=START, required_to=END, dataset_fingerprint=H("9"), repository_root=tmp_path)
    reasons = {item.reason_code for item in report.issues}
    assert {"MISSING_INSTRUMENT_SPEC", "MISSING_BROKER_COMMISSION_SPEC",
            "MISSING_EXECUTION_COST_SPEC", "MISSING_PARTICIPATION_SPEC",
            "MISSING_RISK_LIMIT_SPEC", "MISSING_SESSION_SPEC", "MISSING_MARGIN_SPEC",
            "MISSING_SETTLEMENT_SPEC"}.issubset(reasons)
    assert len(report.issues) == 9
    assert all(item.market == "ES" and item.required_from == START and item.required_to == END
               for item in report.issues)
    assert {item.evidence_class for item in report.issues} == {"AUTHORITATIVE_FACT", "OWNER_ASSUMPTION"}


def test_generic_btc_and_perpetual_without_history_are_disabled(tmp_path):
    unknown = evaluate_production_interval(repository=SpecificationRepository((), ()),
        profile=InstrumentProfile.BTC_UNKNOWN_UNSUPPORTED, market="BTC", instrument_id="BTC",
        required_from=START, required_to=END, dataset_fingerprint=H("9"), repository_root=tmp_path)
    assert "UNSUPPORTED_INSTRUMENT_PROFILE" in {i.reason_code for i in unknown.issues}
    perp = evaluate_production_interval(repository=SpecificationRepository((), ()),
        profile=InstrumentProfile.BTC_LINEAR_PERPETUAL, market="BTC", instrument_id="BTC",
        required_from=START, required_to=END, dataset_fingerprint=H("9"), repository_root=tmp_path)
    reasons = {i.reason_code for i in perp.issues}
    assert {"MISSING_MARK_PRICE_EVIDENCE", "MISSING_FUNDING_SPEC",
            "MISSING_ORACLE_PRICE_HISTORY", "MISSING_MARGIN_SPEC"}.issubset(reasons)


def test_synthetic_fixture_and_mixed_schema_cannot_leak_to_production(tmp_path):
    kinds = (SpecificationType.INSTRUMENT, SpecificationType.SESSION, SpecificationType.SETTLEMENT,
             SpecificationType.CLEARING_MARGIN, SpecificationType.EXCHANGE_FEE,
             SpecificationType.OWNER_BROKER_COMMISSION, SpecificationType.SLIPPAGE,
             SpecificationType.PARTICIPATION, SpecificationType.RISK_LIMITS)
    records = tuple(economic(kind, kind.value, owner=False, synthetic=True, evidence=()) for kind in kinds)
    report = evaluate_production_interval(repository=SpecificationRepository((), records),
        profile=InstrumentProfile.ES_FUTURE, market="ES", instrument_id="ES",
        required_from=START, required_to=END, dataset_fingerprint=H("9"), repository_root=tmp_path,
        ledger_schema_version="backtest-result-v1")
    reasons = [item.reason_code for item in report.issues]
    assert reasons.count("OWNER_APPROVAL_REQUIRED") == 9
    assert "MIXED_LEDGER_VERSION" in reasons
    assert not report.eligible


def test_deterministic_serialization_report_and_fingerprints(tmp_path):
    one = evaluate_production_interval(repository=SpecificationRepository((), ()),
        profile=InstrumentProfile.NQ_FUTURE, market="NQ", instrument_id="NQ",
        required_from=START, required_to=END, dataset_fingerprint=H("9"), repository_root=tmp_path)
    two = evaluate_production_interval(repository=SpecificationRepository((), ()),
        profile=InstrumentProfile.NQ_FUTURE, market="NQ", instrument_id="NQ",
        required_from=START, required_to=END, dataset_fingerprint=H("9"), repository_root=tmp_path)
    assert one == two
    assert json.dumps(one.as_machine_dict(), sort_keys=True, separators=(",", ":")) == json.dumps(
        two.as_machine_dict(), sort_keys=True, separators=(",", ":"))
    assert canonical_fingerprint(Decimal("1.0")) == canonical_fingerprint(Decimal("1.00"))
    assert canonical_json_bytes(order()) == canonical_json_bytes(order())
    assert b'6000.25' in canonical_json_bytes(order())


def test_capability_contract_rejects_reasons_on_eligible_declaration():
    with pytest.raises(ValueError, match="eligible"):
        CapabilityDeclarationV2("capability-declaration-v2-1", H("a"),
            InstrumentProfile.ES_FUTURE, "ES", "ES", (OrderType.MARKET,), ("ohlcv",),
            (H("b"),), True, ("MISSING_RISK_LIMIT_SPEC",))


def test_reason_catalog_and_union_schema_cover_phase1_public_contracts():
    root = Path(__file__).parent
    codes = json.loads((root / "REASON_CODES.json").read_text(encoding="utf-8"))["codes"]
    required = {"MISSING_INSTRUMENT_SPEC", "MISSING_BROKER_COMMISSION_SPEC",
                "MISSING_EXECUTION_COST_SPEC", "MISSING_PARTICIPATION_SPEC",
                "MISSING_RISK_LIMIT_SPEC", "MISSING_SESSION_SPEC", "MISSING_MARGIN_SPEC",
                "MISSING_SETTLEMENT_SPEC", "MISSING_FUNDING_SPEC", "MISSING_MARK_PRICE_EVIDENCE",
                "SPEC_EFFECTIVE_DATE_GAP", "SPEC_EFFECTIVE_DATE_OVERLAP", "SPEC_PROVENANCE_INVALID",
                "SPEC_CHECKSUM_MISMATCH", "INSTRUMENT_IDENTITY_MISMATCH", "OFF_TICK_ECONOMICS",
                "MIXED_LEDGER_VERSION", "UNSUPPORTED_INSTRUMENT_PROFILE"}
    assert required.issubset(codes) and len(codes) == len(set(codes))
    schema = json.loads((root / "schemas" / "phase1-records-v2.schema.json").read_text(encoding="utf-8"))
    assert {"instrument", "owner_assumption", "capability", "order_intent", "order_transition",
            "fill", "accounting_snapshot", "risk_event", "result_identity"}.issubset(schema["$defs"])
