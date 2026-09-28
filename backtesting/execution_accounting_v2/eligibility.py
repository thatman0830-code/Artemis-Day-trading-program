"""Collecting, interval-aware production eligibility reports for v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from .specifications import (
    Capability, InstrumentProfile, MissingSpecificationReason, SpecificationRepository,
    SpecificationType, _MISSING_REASON, _REQUIRED, _utc, canonical_fingerprint,
)
from .validation import validate_repository_provenance, validate_specification_intervals


@dataclass(frozen=True, slots=True)
class ProductionEligibilityIssueV2:
    reason_code: str
    evidence_class: str
    market: str
    instrument_id: str
    field: str
    required_from: datetime
    required_to: datetime
    detail: str


@dataclass(frozen=True, slots=True)
class ProductionEligibilityReportV2:
    schema_version: str
    report_id: str
    profile: InstrumentProfile
    market: str
    instrument_id: str
    required_from: datetime
    required_to: datetime
    eligible: bool
    issues: tuple[ProductionEligibilityIssueV2, ...]
    specification_ids: tuple[str, ...]
    dataset_fingerprint: str
    economic_fingerprint: str

    def as_machine_dict(self) -> dict:
        def dt(value: datetime) -> str:
            return value.isoformat().replace("+00:00", "Z")
        return {
            "schema_version": self.schema_version, "report_id": self.report_id,
            "profile": self.profile.value, "market": self.market,
            "instrument_id": self.instrument_id, "required_from": dt(self.required_from),
            "required_to": dt(self.required_to), "eligible": self.eligible,
            "issues": [{"reason_code": issue.reason_code, "evidence_class": issue.evidence_class,
                        "market": issue.market, "instrument_id": issue.instrument_id,
                        "field": issue.field, "required_from": dt(issue.required_from),
                        "required_to": dt(issue.required_to), "detail": issue.detail}
                       for issue in self.issues],
            "specification_ids": list(self.specification_ids),
            "dataset_fingerprint": self.dataset_fingerprint,
            "economic_fingerprint": self.economic_fingerprint,
        }


_CLASS = {
    SpecificationType.INSTRUMENT: "AUTHORITATIVE_FACT",
    SpecificationType.SESSION: "AUTHORITATIVE_FACT",
    SpecificationType.SETTLEMENT: "AUTHORITATIVE_FACT",
    SpecificationType.CLEARING_MARGIN: "AUTHORITATIVE_FACT",
    SpecificationType.EXCHANGE_FEE: "AUTHORITATIVE_FACT",
    SpecificationType.OWNER_BROKER_COMMISSION: "OWNER_ASSUMPTION",
    SpecificationType.SLIPPAGE: "OWNER_ASSUMPTION",
    SpecificationType.PARTICIPATION: "OWNER_ASSUMPTION",
    SpecificationType.RISK_LIMITS: "OWNER_ASSUMPTION",
    SpecificationType.MARK_PRICE: "HISTORICAL_OBSERVATION",
    SpecificationType.ORACLE_PRICE: "HISTORICAL_OBSERVATION",
    SpecificationType.FUNDING: "HISTORICAL_OBSERVATION",
    SpecificationType.MARGIN_TIER: "HISTORICAL_OBSERVATION",
    SpecificationType.FEE_TIER: "HISTORICAL_OBSERVATION",
}


def _precise_reason(kind: SpecificationType) -> MissingSpecificationReason:
    if kind in (SpecificationType.SLIPPAGE, SpecificationType.EXCHANGE_FEE):
        return MissingSpecificationReason.MISSING_EXECUTION_COST_SPEC
    if kind in (SpecificationType.CLEARING_MARGIN, SpecificationType.MARGIN_TIER):
        return MissingSpecificationReason.MISSING_MARGIN_SPEC
    if kind == SpecificationType.FUNDING:
        return MissingSpecificationReason.MISSING_FUNDING_SPEC
    if kind == SpecificationType.MARK_PRICE:
        return MissingSpecificationReason.MISSING_MARK_PRICE_EVIDENCE
    return _MISSING_REASON[kind]


def evaluate_production_interval(*, repository: SpecificationRepository,
                                 profile: InstrumentProfile, market: str,
                                 instrument_id: str, required_from: datetime,
                                 required_to: datetime, dataset_fingerprint: str,
                                 repository_root, ledger_schema_version: str = "backtest-result-v2-1") -> ProductionEligibilityReportV2:
    _utc(required_from, "required_from")
    _utc(required_to, "required_to")
    if required_to <= required_from:
        raise ValueError("required interval must be non-empty")
    if len(dataset_fingerprint) != 64 or any(c not in "0123456789abcdef" for c in dataset_fingerprint):
        raise ValueError("dataset_fingerprint must be lowercase SHA-256")
    issues: list[ProductionEligibilityIssueV2] = []
    selected = []

    def add(reason, evidence_class, field, detail, start=required_from, end=required_to):
        issues.append(ProductionEligibilityIssueV2(reason.value, evidence_class, market,
                                                    instrument_id, field, start, end, detail))

    if ledger_schema_version != "backtest-result-v2-1":
        add(MissingSpecificationReason.MIXED_LEDGER_VERSION, "VERSION", "ledger_schema_version",
            "v2 production eligibility rejects non-v2 or mixed ledgers")
    if profile == InstrumentProfile.BTC_UNKNOWN_UNSUPPORTED:
        add(MissingSpecificationReason.UNSUPPORTED_INSTRUMENT_PROFILE, "AUTHORITATIVE_FACT",
            "profile", "generic BTC identity does not prove spot or perpetual economics")
        required = ()
    else:
        required = _REQUIRED.get(profile)
    if required is None:
        add(MissingSpecificationReason.UNSUPPORTED_INSTRUMENT_PROFILE, "AUTHORITATIVE_FACT",
            "profile", "instrument profile is unsupported")
        required = ()
    for kind in required:
        relevant = tuple(item for item in repository.specifications if
                         item.specification_type == kind and item.market == market and
                         item.instrument_id == instrument_id)
        interval_report = validate_specification_intervals(repository.specifications, kind, market,
                                                            instrument_id, required_from, required_to)
        if not relevant:
            add(_precise_reason(kind), _CLASS[kind], kind.value,
                "required specification is absent")
            continue
        for item in interval_report.issues:
            add(item.reason, _CLASS[kind], kind.value, item.detail,
                item.effective_from or required_from, item.effective_to or required_to)
        if interval_report.valid:
            covering = tuple(item for item in relevant if item.effective_from < required_to and
                             (item.effective_to is None or item.effective_to > required_from))
            for item in covering:
                if item.synthetic_test_only or not item.owner_approved:
                    add(MissingSpecificationReason.OWNER_APPROVAL_REQUIRED, _CLASS[kind], kind.value,
                        f"{item.specification_id} is synthetic or not owner-approved",
                        max(required_from, item.effective_from),
                        min(required_to, item.effective_to) if item.effective_to else required_to)
                else:
                    selected.append(item)
    provenance = validate_repository_provenance(repository, repository_root)
    for item in provenance.issues:
        add(item.reason, "PROVENANCE", item.field, item.detail,
            item.effective_from or required_from, item.effective_to or required_to)
    selected_ids = tuple(sorted({item.specification_id for item in selected}))
    issues_sorted = tuple(sorted(issues, key=lambda item: (
        item.reason_code, item.evidence_class, item.field, item.required_from,
        item.required_to, item.detail)))
    economic = canonical_fingerprint(profile, market, instrument_id, required_from, required_to,
                                     tuple(sorted(selected, key=lambda item: item.specification_id)))
    report_id = canonical_fingerprint("production-eligibility-v2-1", profile, market, instrument_id,
                                      required_from, required_to, dataset_fingerprint, economic,
                                      issues_sorted, selected_ids)
    return ProductionEligibilityReportV2("production-eligibility-v2-1", report_id, profile, market,
                                         instrument_id, required_from, required_to, not issues_sorted,
                                         issues_sorted, selected_ids, dataset_fingerprint, economic)
