"""Immutable, value-neutral economic specification infrastructure.

This module resolves and gates owner/authoritative facts.  It deliberately does
not execute orders, calculate PnL, access providers, or supply economic defaults.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json


class SpecificationType(str, Enum):
    INSTRUMENT = "INSTRUMENT"
    SESSION = "SESSION"
    SETTLEMENT = "SETTLEMENT"
    CLEARING_MARGIN = "CLEARING_MARGIN"
    EXCHANGE_FEE = "EXCHANGE_FEE"
    OWNER_BROKER_COMMISSION = "OWNER_BROKER_COMMISSION"
    SLIPPAGE = "SLIPPAGE"
    PARTICIPATION = "PARTICIPATION"
    RISK_LIMITS = "RISK_LIMITS"
    MARK_PRICE = "MARK_PRICE"
    ORACLE_PRICE = "ORACLE_PRICE"
    FUNDING = "FUNDING"
    MARGIN_TIER = "MARGIN_TIER"
    FEE_TIER = "FEE_TIER"


class InstrumentProfile(str, Enum):
    ES_FUTURE = "ES_FUTURE"
    NQ_FUTURE = "NQ_FUTURE"
    BTC_SPOT = "BTC_SPOT"
    BTC_LINEAR_PERPETUAL = "BTC_LINEAR_PERPETUAL"
    BTC_UNKNOWN_UNSUPPORTED = "BTC_UNKNOWN_UNSUPPORTED"


class Capability(str, Enum):
    PRODUCTION_ECONOMIC_REPLAY = "PRODUCTION_ECONOMIC_REPLAY"
    SYNTHETIC_CONTRACT_TEST = "SYNTHETIC_CONTRACT_TEST"


class MissingSpecificationReason(str, Enum):
    MISSING_INSTRUMENT_SPEC = "MISSING_INSTRUMENT_SPEC"
    MISSING_SESSION_SPEC = "MISSING_SESSION_SPEC"
    MISSING_SETTLEMENT_SPEC = "MISSING_SETTLEMENT_SPEC"
    MISSING_CLEARING_MARGIN_SPEC = "MISSING_CLEARING_MARGIN_SPEC"
    MISSING_EXCHANGE_FEE_SPEC = "MISSING_EXCHANGE_FEE_SPEC"
    MISSING_BROKER_COMMISSION_SPEC = "MISSING_BROKER_COMMISSION_SPEC"
    MISSING_SLIPPAGE_SPEC = "MISSING_SLIPPAGE_SPEC"
    MISSING_PARTICIPATION_SPEC = "MISSING_PARTICIPATION_SPEC"
    MISSING_RISK_LIMIT_SPEC = "MISSING_RISK_LIMIT_SPEC"
    MISSING_MARK_PRICE_HISTORY = "MISSING_MARK_PRICE_HISTORY"
    MISSING_ORACLE_PRICE_HISTORY = "MISSING_ORACLE_PRICE_HISTORY"
    MISSING_FUNDING_HISTORY = "MISSING_FUNDING_HISTORY"
    MISSING_MARGIN_TIER_HISTORY = "MISSING_MARGIN_TIER_HISTORY"
    MISSING_FEE_TIER_HISTORY = "MISSING_FEE_TIER_HISTORY"
    INSTRUMENT_PROFILE_UNPROVEN = "INSTRUMENT_PROFILE_UNPROVEN"
    AMBIGUOUS_EFFECTIVE_SPECIFICATION = "AMBIGUOUS_EFFECTIVE_SPECIFICATION"
    MIXED_LEDGER_VERSION = "MIXED_LEDGER_VERSION"
    OWNER_APPROVAL_REQUIRED = "OWNER_APPROVAL_REQUIRED"
    MISSING_EXECUTION_COST_SPEC = "MISSING_EXECUTION_COST_SPEC"
    MISSING_MARGIN_SPEC = "MISSING_MARGIN_SPEC"
    MISSING_FUNDING_SPEC = "MISSING_FUNDING_SPEC"
    MISSING_MARK_PRICE_EVIDENCE = "MISSING_MARK_PRICE_EVIDENCE"
    SPEC_EFFECTIVE_DATE_GAP = "SPEC_EFFECTIVE_DATE_GAP"
    SPEC_EFFECTIVE_DATE_OVERLAP = "SPEC_EFFECTIVE_DATE_OVERLAP"
    SPEC_PROVENANCE_INVALID = "SPEC_PROVENANCE_INVALID"
    SPEC_CHECKSUM_MISMATCH = "SPEC_CHECKSUM_MISMATCH"
    INSTRUMENT_IDENTITY_MISMATCH = "INSTRUMENT_IDENTITY_MISMATCH"
    OFF_TICK_ECONOMICS = "OFF_TICK_ECONOMICS"
    UNSUPPORTED_INSTRUMENT_PROFILE = "UNSUPPORTED_INSTRUMENT_PROFILE"


def _utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field} must be timezone-aware UTC")


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")


def _finite_decimal(value: Decimal, field: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{field} must be a finite Decimal")


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    source_organization: str
    document_identity: str
    canonical_url: str | None
    local_snapshot_path: str
    snapshot_sha256: str
    retrieved_at: datetime
    effective_from: datetime
    effective_to: datetime | None
    market: str
    instrument_id: str
    fact_names: tuple[str, ...]
    assumptions_and_gaps: tuple[str, ...] = ()
    schema_version: str = "evidence-record-v2-1"

    def __post_init__(self) -> None:
        if self.schema_version != "evidence-record-v2-1":
            raise ValueError("unsupported evidence schema_version")
        for field in ("evidence_id", "source_organization", "document_identity",
                      "local_snapshot_path", "market", "instrument_id"):
            _text(getattr(self, field), field)
        if len(self.snapshot_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.snapshot_sha256):
            raise ValueError("snapshot_sha256 must be lowercase SHA-256")
        _utc(self.retrieved_at, "retrieved_at")
        _utc(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _utc(self.effective_to, "effective_to")
            if self.effective_to <= self.effective_from:
                raise ValueError("effective interval must be non-empty")
        if not self.fact_names:
            raise ValueError("fact_names are required")


@dataclass(frozen=True, slots=True)
class SpecificationRecord:
    specification_id: str
    schema_version: str
    specification_type: SpecificationType
    market: str
    instrument_id: str
    effective_from: datetime
    effective_to: datetime | None
    values: tuple[tuple[str, str], ...]
    evidence_ids: tuple[str, ...]
    owner_approved: bool
    synthetic_test_only: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != "economic-specification-v2-1":
            raise ValueError("unsupported economic specification schema_version")
        for field in ("specification_id", "schema_version", "market", "instrument_id"):
            _text(getattr(self, field), field)
        _utc(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _utc(self.effective_to, "effective_to")
            if self.effective_to <= self.effective_from:
                raise ValueError("effective interval must be non-empty")
        names = tuple(name for name, _ in self.values)
        if not names or names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("values must be non-empty, uniquely named, and lexically ordered")
        if any(not isinstance(value, str) or not value for _, value in self.values):
            raise ValueError("specification values must use explicit non-empty string serialization")
        if not self.evidence_ids and not self.synthetic_test_only:
            raise ValueError("production specifications require evidence lineage")
        if self.synthetic_test_only and self.owner_approved:
            raise ValueError("synthetic test specifications cannot be production-approved")


def _canonical(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        _utc(value, "fingerprint datetime")
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        _finite_decimal(value, "fingerprint decimal")
        normalized = value.normalize()
        return "0" if normalized == 0 else format(normalized, "f")
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if hasattr(value, "__dataclass_fields__"):
        return _canonical(asdict(value))
    if isinstance(value, float):
        raise ValueError("float is prohibited from economic fingerprints")
    return value


def canonical_fingerprint(*records: object) -> str:
    return hashlib.sha256(canonical_json_bytes(*records)).hexdigest()


def canonical_json_bytes(*records: object) -> bytes:
    """Serialize immutable records deterministically without numeric float coercion."""
    encoded = json.dumps(_canonical(records), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return encoded.encode("utf-8")


@dataclass(frozen=True, slots=True)
class SpecificationRepository:
    evidence: tuple[EvidenceRecord, ...]
    specifications: tuple[SpecificationRecord, ...]

    def __post_init__(self) -> None:
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        spec_ids = tuple(item.specification_id for item in self.specifications)
        if len(evidence_ids) != len(set(evidence_ids)) or len(spec_ids) != len(set(spec_ids)):
            raise ValueError("duplicate evidence or specification identity")
        known = set(evidence_ids)
        if any(not set(item.evidence_ids).issubset(known) for item in self.specifications):
            raise ValueError("specification has missing evidence lineage")

    def resolve(self, specification_type: SpecificationType, market: str,
                instrument_id: str, as_of: datetime) -> SpecificationRecord | None:
        _utc(as_of, "as_of")
        found = tuple(item for item in self.specifications if
                      item.specification_type == specification_type and item.market == market and
                      item.instrument_id == instrument_id and item.effective_from <= as_of and
                      (item.effective_to is None or as_of < item.effective_to))
        if len(found) > 1:
            raise ValueError(MissingSpecificationReason.AMBIGUOUS_EFFECTIVE_SPECIFICATION.value)
        return found[0] if found else None


@dataclass(frozen=True, slots=True)
class EligibilityIssue:
    reason: MissingSpecificationReason
    specification_type: SpecificationType | None
    detail: str


@dataclass(frozen=True, slots=True)
class EligibilityReport:
    report_id: str
    profile: InstrumentProfile
    capability: Capability
    as_of: datetime
    eligible: bool
    issues: tuple[EligibilityIssue, ...]
    specification_ids: tuple[str, ...]
    economic_fingerprint: str


_REQUIRED = {
    InstrumentProfile.ES_FUTURE: (
        SpecificationType.INSTRUMENT, SpecificationType.SESSION, SpecificationType.SETTLEMENT,
        SpecificationType.CLEARING_MARGIN, SpecificationType.EXCHANGE_FEE,
        SpecificationType.OWNER_BROKER_COMMISSION, SpecificationType.SLIPPAGE,
        SpecificationType.PARTICIPATION, SpecificationType.RISK_LIMITS),
    InstrumentProfile.NQ_FUTURE: (
        SpecificationType.INSTRUMENT, SpecificationType.SESSION, SpecificationType.SETTLEMENT,
        SpecificationType.CLEARING_MARGIN, SpecificationType.EXCHANGE_FEE,
        SpecificationType.OWNER_BROKER_COMMISSION, SpecificationType.SLIPPAGE,
        SpecificationType.PARTICIPATION, SpecificationType.RISK_LIMITS),
    InstrumentProfile.BTC_SPOT: (
        SpecificationType.INSTRUMENT, SpecificationType.FEE_TIER, SpecificationType.SLIPPAGE,
        SpecificationType.PARTICIPATION, SpecificationType.RISK_LIMITS),
    InstrumentProfile.BTC_LINEAR_PERPETUAL: (
        SpecificationType.INSTRUMENT, SpecificationType.MARK_PRICE, SpecificationType.ORACLE_PRICE,
        SpecificationType.FUNDING, SpecificationType.MARGIN_TIER, SpecificationType.FEE_TIER,
        SpecificationType.SLIPPAGE, SpecificationType.PARTICIPATION, SpecificationType.RISK_LIMITS),
}

_MISSING_REASON = {
    SpecificationType.INSTRUMENT: MissingSpecificationReason.MISSING_INSTRUMENT_SPEC,
    SpecificationType.SESSION: MissingSpecificationReason.MISSING_SESSION_SPEC,
    SpecificationType.SETTLEMENT: MissingSpecificationReason.MISSING_SETTLEMENT_SPEC,
    SpecificationType.CLEARING_MARGIN: MissingSpecificationReason.MISSING_CLEARING_MARGIN_SPEC,
    SpecificationType.EXCHANGE_FEE: MissingSpecificationReason.MISSING_EXCHANGE_FEE_SPEC,
    SpecificationType.OWNER_BROKER_COMMISSION: MissingSpecificationReason.MISSING_BROKER_COMMISSION_SPEC,
    SpecificationType.SLIPPAGE: MissingSpecificationReason.MISSING_SLIPPAGE_SPEC,
    SpecificationType.PARTICIPATION: MissingSpecificationReason.MISSING_PARTICIPATION_SPEC,
    SpecificationType.RISK_LIMITS: MissingSpecificationReason.MISSING_RISK_LIMIT_SPEC,
    SpecificationType.MARK_PRICE: MissingSpecificationReason.MISSING_MARK_PRICE_HISTORY,
    SpecificationType.ORACLE_PRICE: MissingSpecificationReason.MISSING_ORACLE_PRICE_HISTORY,
    SpecificationType.FUNDING: MissingSpecificationReason.MISSING_FUNDING_HISTORY,
    SpecificationType.MARGIN_TIER: MissingSpecificationReason.MISSING_MARGIN_TIER_HISTORY,
    SpecificationType.FEE_TIER: MissingSpecificationReason.MISSING_FEE_TIER_HISTORY,
}


def evaluate_production_eligibility(repository: SpecificationRepository, profile: InstrumentProfile,
                                    market: str, instrument_id: str, as_of: datetime,
                                    ledger_schema_version: str = "backtest-result-v2-1") -> EligibilityReport:
    _utc(as_of, "as_of")
    issues: list[EligibilityIssue] = []
    selected: list[SpecificationRecord] = []
    if ledger_schema_version != "backtest-result-v2-1":
        issues.append(EligibilityIssue(MissingSpecificationReason.MIXED_LEDGER_VERSION, None,
                                       "production v2 requires backtest-result-v2-1"))
    if profile == InstrumentProfile.BTC_UNKNOWN_UNSUPPORTED:
        issues.append(EligibilityIssue(MissingSpecificationReason.INSTRUMENT_PROFILE_UNPROVEN, None,
                                       "BTC archive does not prove spot or perpetual economics"))
    for kind in _REQUIRED.get(profile, ()):
        try:
            item = repository.resolve(kind, market, instrument_id, as_of)
        except ValueError:
            issues.append(EligibilityIssue(MissingSpecificationReason.AMBIGUOUS_EFFECTIVE_SPECIFICATION,
                                           kind, "multiple effective specifications"))
            continue
        if item is None:
            issues.append(EligibilityIssue(_MISSING_REASON[kind], kind, "required specification absent"))
        elif item.synthetic_test_only or not item.owner_approved:
            issues.append(EligibilityIssue(MissingSpecificationReason.OWNER_APPROVAL_REQUIRED, kind,
                                           "specification is not owner-approved for production"))
        else:
            selected.append(item)
    selected_ids = tuple(sorted(item.specification_id for item in selected))
    fingerprint = canonical_fingerprint(profile, market, instrument_id, as_of, selected)
    report_id = canonical_fingerprint("eligibility", profile, market, instrument_id, as_of,
                                      tuple(issues), selected_ids, fingerprint)
    return EligibilityReport(report_id, profile, Capability.PRODUCTION_ECONOMIC_REPLAY, as_of,
                             not issues, tuple(issues), selected_ids, fingerprint)
