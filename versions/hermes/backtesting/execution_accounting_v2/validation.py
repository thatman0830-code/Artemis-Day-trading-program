"""Strict, collecting validators for immutable v2 Phase 1 contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
from pathlib import Path

from .contracts import FillV2, InstrumentSpecificationV2, OrderIntentV2
from .specifications import (
    EvidenceRecord, MissingSpecificationReason, SpecificationRecord,
    SpecificationRepository, SpecificationType, _utc,
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    reason: MissingSpecificationReason
    market: str
    instrument_id: str
    contract_id: str | None
    field: str
    effective_from: datetime | None
    effective_to: datetime | None
    detail: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    valid: bool
    issues: tuple[ValidationIssue, ...]


def _issue(reason, market, instrument, field, detail, start=None, end=None, contract=None):
    return ValidationIssue(reason, market, instrument, contract, field, start, end, detail)


def is_on_grid(value: Decimal, step: Decimal) -> bool:
    if not isinstance(value, Decimal) or not isinstance(step, Decimal):
        raise ValueError("grid validation requires Decimal values")
    if not value.is_finite() or not step.is_finite() or step <= 0:
        raise ValueError("grid validation requires finite value and positive step")
    return value % step == 0


def validate_order_against_instrument(order: OrderIntentV2,
                                      instrument: InstrumentSpecificationV2) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if (order.market, order.instrument_id, order.contract_id) != (
            instrument.market, instrument.instrument_id, instrument.contract_id):
        issues.append(_issue(MissingSpecificationReason.INSTRUMENT_IDENTITY_MISMATCH,
                             order.market, order.instrument_id, "identity",
                             "order and instrument market/instrument/contract differ",
                             order.activation_at, order.expires_at, order.contract_id))
    if order.activation_at < instrument.effective_from or (
            instrument.effective_to is not None and order.activation_at >= instrument.effective_to):
        issues.append(_issue(MissingSpecificationReason.SPEC_EFFECTIVE_DATE_GAP,
                             order.market, order.instrument_id, "activation_at",
                             "instrument specification is not effective at activation",
                             order.activation_at, order.expires_at, order.contract_id))
    if not is_on_grid(order.quantity, instrument.quantity_step):
        issues.append(_issue(MissingSpecificationReason.OFF_TICK_ECONOMICS,
                             order.market, order.instrument_id, "quantity",
                             "quantity is off the configured quantity step",
                             order.activation_at, order.expires_at, order.contract_id))
    for name in ("limit_price", "stop_price"):
        value = getattr(order, name)
        if value is not None and not is_on_grid(value, instrument.tick_size):
            issues.append(_issue(MissingSpecificationReason.OFF_TICK_ECONOMICS,
                                 order.market, order.instrument_id, name,
                                 f"{name} is off the configured tick grid",
                                 order.activation_at, order.expires_at, order.contract_id))
    return ValidationReport(not issues, tuple(issues))


def validate_fill_against_order(fill: FillV2, order: OrderIntentV2,
                                instrument: InstrumentSpecificationV2) -> ValidationReport:
    issues = list(validate_order_against_instrument(order, instrument).issues)
    if (fill.order_id != order.order_id or fill.market != order.market or
            fill.instrument_id != order.instrument_id or fill.contract_id != order.contract_id or
            fill.side != order.side):
        issues.append(_issue(MissingSpecificationReason.INSTRUMENT_IDENTITY_MISMATCH,
                             fill.market, fill.instrument_id, "fill_identity",
                             "fill is incompatible with order identity or side",
                             fill.fill_time, None, fill.contract_id))
    if fill.fill_time < order.activation_at:
        issues.append(_issue(MissingSpecificationReason.SPEC_EFFECTIVE_DATE_GAP,
                             fill.market, fill.instrument_id, "fill_time",
                             "fill precedes order activation", fill.fill_time, None, fill.contract_id))
    for name in ("economic_price", "reference_price"):
        if not is_on_grid(getattr(fill, name), instrument.tick_size):
            issues.append(_issue(MissingSpecificationReason.OFF_TICK_ECONOMICS,
                                 fill.market, fill.instrument_id, name,
                                 f"{name} is off the configured tick grid",
                                 fill.fill_time, None, fill.contract_id))
    if not is_on_grid(fill.quantity, instrument.quantity_step) or fill.quantity > order.quantity:
        issues.append(_issue(MissingSpecificationReason.OFF_TICK_ECONOMICS,
                             fill.market, fill.instrument_id, "quantity",
                             "fill quantity is off step or exceeds order quantity",
                             fill.fill_time, None, fill.contract_id))
    return ValidationReport(not issues, tuple(issues))


def validate_evidence_checksum(evidence: EvidenceRecord, repository_root: Path) -> ValidationReport:
    root = repository_root.resolve()
    candidate = (root / evidence.local_snapshot_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return ValidationReport(False, (_issue(MissingSpecificationReason.SPEC_PROVENANCE_INVALID,
            evidence.market, evidence.instrument_id, "local_snapshot_path",
            "evidence path escapes repository root", evidence.effective_from, evidence.effective_to),))
    if not candidate.is_file():
        return ValidationReport(False, (_issue(MissingSpecificationReason.SPEC_PROVENANCE_INVALID,
            evidence.market, evidence.instrument_id, "local_snapshot_path",
            "evidence snapshot is missing", evidence.effective_from, evidence.effective_to),))
    actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if actual != evidence.snapshot_sha256:
        return ValidationReport(False, (_issue(MissingSpecificationReason.SPEC_CHECKSUM_MISMATCH,
            evidence.market, evidence.instrument_id, "snapshot_sha256",
            "evidence checksum does not match immutable snapshot", evidence.effective_from,
            evidence.effective_to),))
    return ValidationReport(True, ())


def validate_specification_intervals(records: tuple[SpecificationRecord, ...],
                                     specification_type: SpecificationType, market: str,
                                     instrument_id: str, required_from: datetime,
                                     required_to: datetime) -> ValidationReport:
    _utc(required_from, "required_from")
    _utc(required_to, "required_to")
    if required_to <= required_from:
        raise ValueError("required interval must be non-empty")
    relevant = sorted((item for item in records if item.specification_type == specification_type and
                       item.market == market and item.instrument_id == instrument_id),
                      key=lambda item: (item.effective_from, item.effective_to or datetime.max.replace(tzinfo=required_from.tzinfo), item.specification_id))
    issues: list[ValidationIssue] = []
    cursor = required_from
    for item in relevant:
        end = item.effective_to or required_to
        if end <= required_from or item.effective_from >= required_to:
            continue
        start = max(item.effective_from, required_from)
        clipped_end = min(end, required_to)
        if start > cursor:
            issues.append(_issue(MissingSpecificationReason.SPEC_EFFECTIVE_DATE_GAP, market,
                                 instrument_id, specification_type.value,
                                 "required interval has no effective specification", cursor, start))
        elif start < cursor:
            issues.append(_issue(MissingSpecificationReason.SPEC_EFFECTIVE_DATE_OVERLAP, market,
                                 instrument_id, specification_type.value,
                                 "effective specifications overlap", start, min(cursor, clipped_end)))
        cursor = max(cursor, clipped_end)
    if cursor < required_to:
        issues.append(_issue(MissingSpecificationReason.SPEC_EFFECTIVE_DATE_GAP, market,
                             instrument_id, specification_type.value,
                             "required interval has no effective specification", cursor, required_to))
    return ValidationReport(not issues, tuple(issues))


def validate_repository_provenance(repository: SpecificationRepository,
                                   repository_root: Path) -> ValidationReport:
    issues: list[ValidationIssue] = []
    by_id = {item.evidence_id: item for item in repository.evidence}
    for evidence in repository.evidence:
        issues.extend(validate_evidence_checksum(evidence, repository_root).issues)
    for spec in repository.specifications:
        for evidence_id in spec.evidence_ids:
            evidence = by_id.get(evidence_id)
            if evidence is None or evidence.market != spec.market or evidence.instrument_id != spec.instrument_id:
                issues.append(_issue(MissingSpecificationReason.SPEC_PROVENANCE_INVALID,
                    spec.market, spec.instrument_id, "evidence_ids",
                    f"evidence {evidence_id} does not match specification identity",
                    spec.effective_from, spec.effective_to))
    return ValidationReport(not issues, tuple(issues))
