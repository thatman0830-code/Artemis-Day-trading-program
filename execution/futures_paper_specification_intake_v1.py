"""Fail-closed ES/NQ paper specification intake over retained evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket


VERSION = "futures-paper-specification-intake-v1"
EVIDENCE_SCHEMA = "authoritative-specification-evidence-v2-1"
EXPECTED = {
    FuturesCanonicalMarket.ES: {"profile": "ES_FUTURE", "exchange": "CME",
        "rulebook_chapter": "358", "currency": "USD", "point_value": "50",
        "minimum_price_increment": "0.25", "tick_value": "12.50", "quantity_step": "1"},
    FuturesCanonicalMarket.NQ: {"profile": "NQ_FUTURE", "exchange": "CME",
        "rulebook_chapter": "359", "currency": "USD", "point_value": "20",
        "minimum_price_increment": "0.25", "tick_value": "5.00", "quantity_step": "1"},
}
REQUIRED_MISSING = {
    FuturesCanonicalMarket.ES: ("ES_CLEARING_INITIAL_AND_MAINTENANCE_MARGIN_HISTORY",),
    FuturesCanonicalMarket.NQ: ("NQ_CLEARING_INITIAL_AND_MAINTENANCE_MARGIN_HISTORY",),
}
SHARED_MISSING = ("ES_NQ_COMPLETE_EXCHANGE_CLEARING_REGULATORY_FEE_HISTORY",
    "OWNER_BROKER_COMMISSION", "OWNER_EXECUTION_ASSUMPTIONS", "OWNER_RISK_LIMITS")


class FuturesPaperSpecificationIntakeError(RuntimeError):
    pass


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True)
class FuturesPaperSpecificationIntakeV1:
    intake_id: str
    market: FuturesCanonicalMarket
    evidence_sha256: str
    evidence_audit_as_of: datetime
    instrument_terms: tuple[tuple[str, str], ...]
    verified_requirements: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    paper_specification_ready: bool = False
    owner_approved: bool = False
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION

    def as_dict(self, *, include_id: bool = True) -> dict:
        value = {"schema_version": VERSION, "market": self.market.value,
            "evidence_sha256": self.evidence_sha256,
            "evidence_audit_as_of": self.evidence_audit_as_of.isoformat(
                timespec="microseconds").replace("+00:00", "Z"),
            "instrument_terms": dict(self.instrument_terms),
            "verified_requirements": list(self.verified_requirements),
            "missing_requirements": list(self.missing_requirements),
            "paper_specification_ready": False, "owner_approved": False,
            "advisory_only": True, "paper_execution_permitted": False,
            "live_trading_permitted": False, "trading_authority": False}
        if include_id:
            value["intake_id"] = self.intake_id
        return value


def create_futures_paper_specification_intake(
    evidence_path, *, market: FuturesCanonicalMarket
) -> FuturesPaperSpecificationIntakeV1:
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("explicit ES or NQ intake market required")
    path = Path(evidence_path).absolute()
    if not path.is_file() or path.is_symlink():
        raise FuturesPaperSpecificationIntakeError("evidence path is unsafe or missing")
    raw = path.read_bytes()
    try:
        evidence = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FuturesPaperSpecificationIntakeError("evidence is unreadable") from exc
    if not isinstance(evidence, dict) or evidence.get("schema_version") != EVIDENCE_SCHEMA:
        raise FuturesPaperSpecificationIntakeError("evidence schema is invalid")
    if evidence.get("production_policy") != "FAIL_CLOSED" \
            or evidence.get("economic_values_are_defaults") is not False:
        raise FuturesPaperSpecificationIntakeError("evidence fail-closed policy is invalid")
    try:
        audited_at = datetime.fromisoformat(evidence["audit_as_of"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise FuturesPaperSpecificationIntakeError("evidence audit time is invalid") from exc
    if audited_at.tzinfo is None or audited_at.utcoffset() != timedelta(0):
        raise FuturesPaperSpecificationIntakeError("evidence audit time is not UTC")
    instrument = (evidence.get("instruments") or {}).get(market.value)
    expected = EXPECTED[market]
    if (not isinstance(instrument, dict)
            or any(instrument.get(key) != value for key, value in expected.items())
            or instrument.get("facts_status") != "CURRENT_AUTHORITATIVE_TERMS"
            or instrument.get("production_eligible") is not False):
        raise FuturesPaperSpecificationIntakeError("retained instrument terms are invalid")
    unavailable = evidence.get("unavailable_effective_dated_facts")
    if not isinstance(unavailable, list) or len(unavailable) != len(set(unavailable)):
        raise FuturesPaperSpecificationIntakeError("missing-fact inventory is invalid")
    required_missing = REQUIRED_MISSING[market] + SHARED_MISSING
    if any(item not in unavailable for item in required_missing):
        raise FuturesPaperSpecificationIntakeError("evidence overstates economic readiness")
    evidence_sha = hashlib.sha256(raw).hexdigest()
    terms = tuple(sorted(expected.items()))
    verified = ("CURRENCY", "EXCHANGE", "MINIMUM_PRICE_INCREMENT", "POINT_VALUE",
                "QUANTITY_STEP", "RULEBOOK_CHAPTER", "TICK_VALUE")
    values = {"schema_version": VERSION, "market": market.value,
        "evidence_sha256": evidence_sha,
        "evidence_audit_as_of": audited_at.astimezone(timezone.utc).isoformat(
            timespec="microseconds").replace("+00:00", "Z"),
        "instrument_terms": dict(terms), "verified_requirements": list(verified),
        "missing_requirements": list(required_missing),
        "paper_specification_ready": False, "owner_approved": False,
        "advisory_only": True, "paper_execution_permitted": False,
        "live_trading_permitted": False, "trading_authority": False}
    identity = hashlib.sha256(_canonical(values)).hexdigest()
    return FuturesPaperSpecificationIntakeV1(identity, market, evidence_sha,
        audited_at.astimezone(timezone.utc), terms, verified, required_missing)


def write_futures_paper_specification_intake(intake, output_root) -> Path:
    if not isinstance(intake, FuturesPaperSpecificationIntakeV1):
        raise TypeError("futures paper specification intake required")
    root = Path(output_root).absolute() / intake.market.value
    if root.exists() and (not root.is_dir() or root.is_symlink()):
        raise FuturesPaperSpecificationIntakeError("intake output root is unsafe")
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{intake.intake_id}.json"
    raw = _canonical(intake.as_dict()) + b"\n"
    if target.exists():
        if not target.is_file() or target.is_symlink() or target.read_bytes() != raw:
            raise FuturesPaperSpecificationIntakeError("intake identity collision")
        return target
    with target.open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return target

