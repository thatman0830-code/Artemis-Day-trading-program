from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
import json
import hashlib
from pathlib import Path

import pytest

from backtesting.execution_accounting_v2 import (
    EvidenceRecord, InstrumentProfile, MissingSpecificationReason,
    SpecificationRecord, SpecificationRepository, SpecificationType,
    canonical_fingerprint, evaluate_production_eligibility,
)

UTC = timezone.utc
T0 = datetime(2025, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 1, tzinfo=UTC)


def evidence(eid="e1"):
    return EvidenceRecord(eid, "CME Group", "chapter", "https://example.invalid/doc",
                          "snapshots/doc.md", "a" * 64, T0, T0, None, "ES", "ES",
                          ("point_value",), ())


def spec(kind, sid=None, *, owner=True, synthetic=False, start=T0, end=None):
    return SpecificationRecord(sid or kind.value, "economic-specification-v2-1", kind,
                               "ES", "ES", start, end, (("value", "1"),),
                               () if synthetic else ("e1",), owner, synthetic)


def test_records_are_immutable_and_require_utc():
    item = evidence()
    with pytest.raises(FrozenInstanceError):
        item.market = "NQ"
    with pytest.raises(ValueError, match="UTC"):
        EvidenceRecord("e", "CME", "doc", None, "x", "a" * 64,
                       datetime(2025, 1, 1), T0, None, "ES", "ES", ("x",))


def test_repository_rejects_duplicate_and_missing_lineage():
    with pytest.raises(ValueError, match="duplicate"):
        SpecificationRepository((evidence(), evidence()), ())
    orphan = spec(SpecificationType.INSTRUMENT)
    with pytest.raises(ValueError, match="lineage"):
        SpecificationRepository((), (orphan,))


def test_effective_date_resolution_is_half_open_and_deterministic():
    old = spec(SpecificationType.INSTRUMENT, "old", start=T0, end=T1)
    new = spec(SpecificationType.INSTRUMENT, "new", start=T1)
    repo = SpecificationRepository((evidence(),), (old, new))
    assert repo.resolve(SpecificationType.INSTRUMENT, "ES", "ES", T0).specification_id == "old"
    assert repo.resolve(SpecificationType.INSTRUMENT, "ES", "ES", T1).specification_id == "new"


def test_overlapping_effective_records_fail_closed():
    a = spec(SpecificationType.INSTRUMENT, "a")
    b = spec(SpecificationType.INSTRUMENT, "b")
    repo = SpecificationRepository((evidence(),), (a, b))
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        repo.resolve(SpecificationType.INSTRUMENT, "ES", "ES", T1)


def test_fingerprint_is_deterministic_decimal_safe_and_float_rejecting():
    assert canonical_fingerprint(Decimal("1.00"), T0) == canonical_fingerprint(Decimal("1.00"), T0)
    assert canonical_fingerprint(Decimal("1.0")) == canonical_fingerprint(Decimal("1.00"))
    with pytest.raises(ValueError, match="float"):
        canonical_fingerprint(1.0)


def test_es_production_gate_enumerates_all_missing_specs_including_broker_commission():
    report = evaluate_production_eligibility(SpecificationRepository((), ()),
        InstrumentProfile.ES_FUTURE, "ES", "ES", T1)
    reasons = {issue.reason for issue in report.issues}
    assert MissingSpecificationReason.MISSING_BROKER_COMMISSION_SPEC in reasons
    assert MissingSpecificationReason.MISSING_CLEARING_MARGIN_SPEC in reasons
    assert not report.eligible


def test_synthetic_fixture_is_never_production_eligible():
    records = tuple(spec(kind, synthetic=True, owner=False) for kind in (
        SpecificationType.INSTRUMENT, SpecificationType.SESSION, SpecificationType.SETTLEMENT,
        SpecificationType.CLEARING_MARGIN, SpecificationType.EXCHANGE_FEE,
        SpecificationType.OWNER_BROKER_COMMISSION, SpecificationType.SLIPPAGE,
        SpecificationType.PARTICIPATION, SpecificationType.RISK_LIMITS))
    report = evaluate_production_eligibility(SpecificationRepository((), records),
        InstrumentProfile.ES_FUTURE, "ES", "ES", T1)
    assert not report.eligible
    assert all(issue.reason == MissingSpecificationReason.OWNER_APPROVAL_REQUIRED for issue in report.issues)


def test_complete_owner_approved_records_are_eligible():
    records = tuple(spec(kind) for kind in (
        SpecificationType.INSTRUMENT, SpecificationType.SESSION, SpecificationType.SETTLEMENT,
        SpecificationType.CLEARING_MARGIN, SpecificationType.EXCHANGE_FEE,
        SpecificationType.OWNER_BROKER_COMMISSION, SpecificationType.SLIPPAGE,
        SpecificationType.PARTICIPATION, SpecificationType.RISK_LIMITS))
    report = evaluate_production_eligibility(SpecificationRepository((evidence(),), records),
        InstrumentProfile.ES_FUTURE, "ES", "ES", T1)
    assert report.eligible and len(report.specification_ids) == 9


def test_unknown_btc_and_missing_perpetual_history_fail_closed():
    repo = SpecificationRepository((), ())
    unknown = evaluate_production_eligibility(repo, InstrumentProfile.BTC_UNKNOWN_UNSUPPORTED,
                                               "BTC", "BTC", T1)
    assert unknown.issues[0].reason == MissingSpecificationReason.INSTRUMENT_PROFILE_UNPROVEN
    perp = evaluate_production_eligibility(repo, InstrumentProfile.BTC_LINEAR_PERPETUAL,
                                            "BTC", "BTC", T1)
    reasons = {item.reason for item in perp.issues}
    assert MissingSpecificationReason.MISSING_MARK_PRICE_HISTORY in reasons
    assert MissingSpecificationReason.MISSING_FUNDING_HISTORY in reasons


def test_mixed_v1_v2_ledger_rejected():
    report = evaluate_production_eligibility(SpecificationRepository((), ()),
        InstrumentProfile.ES_FUTURE, "ES", "ES", T1, ledger_schema_version="core-v1")
    assert MissingSpecificationReason.MIXED_LEDGER_VERSION in {i.reason for i in report.issues}


def test_all_machine_schemas_parse_offline():
    root = Path(__file__).parent / "schemas"
    files = sorted(root.glob("*.json"))
    assert len(files) == 11
    assert root / "ohlc-execution-v2.schema.json" in files
    for path in files:
        assert json.loads(path.read_text(encoding="utf-8"))["$schema"].endswith("2020-12/schema")


def test_source_inventory_checksums_and_btc_evidence_are_read_only_verifiable():
    root = Path(__file__).parent
    inventory = json.loads((root / "SOURCE_INVENTORY.json").read_text(encoding="utf-8"))
    assert inventory["network_scope"].startswith("public first-party documentation")
    for source in inventory["sources"]:
        path = (root / source["local_path"]).resolve()
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    evidence = json.loads((root / "MACHINE_READABLE_SPECIFICATION_EVIDENCE.json").read_text(encoding="utf-8"))
    assert evidence["instruments"]["BTC"]["profile"] == "BTC_UNKNOWN_UNSUPPORTED"
    assert not evidence["owner_decisions"]["accounting_only_liquidation"]
