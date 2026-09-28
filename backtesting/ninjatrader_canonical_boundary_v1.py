"""Immutable prior-day boundary for a clean MES/MNQ paper-evaluation day."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_clean_day_gate_v1 import evaluate_ninjatrader_clean_day_gate

VERSION = "ninjatrader-canonical-boundary-v1"


@dataclass(frozen=True)
class QuarantinedArchiveV1:
    market: str
    archive_file: str
    archive_sha256: str
    manifest_sha256: str
    inherited_unresolved_gap_count: int


@dataclass(frozen=True)
class CanonicalBoundaryV1:
    target_day_utc: str
    established_at: datetime
    prior_archives: tuple[QuarantinedArchiveV1, ...]
    state: str = "ESTABLISHED_PRIOR_ARCHIVES_QUARANTINED"
    paper_execution_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


@dataclass(frozen=True)
class CanonicalPaperReadinessV1:
    target_day_utc: str
    state: str
    es_bar_count: int
    nq_bar_count: int
    latest_close_time_utc: datetime | None
    reasons: tuple[str, ...]
    inherited_gaps_quarantined: bool
    owner_confirmation_required: bool = True
    paper_execution_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = "ninjatrader-canonical-paper-readiness-v1"


def establish_boundary(*, archive_root: Path, target_day: date,
                       as_of: datetime) -> CanonicalBoundaryV1:
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("UTC as_of required")
    if target_day < as_of.date():
        raise ValueError("canonical target day cannot be in the past")
    rows = []
    for market in FuturesCanonicalMarket:
        manifest_path = Path(archive_root) / market.value / "manifest.json"
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        archive_file = manifest.get("archive_file")
        chain_path = manifest_path.parent / str(archive_file)
        if (manifest.get("market") != market.value
                or manifest.get("trading_authority") is not False
                or not chain_path.is_file()):
            raise ValueError(f"{market.value} prior archive identity rejected")
        rows.append(QuarantinedArchiveV1(
            market.value, str(archive_file), hashlib.sha256(chain_path.read_bytes()).hexdigest(),
            hashlib.sha256(raw).hexdigest(), int(manifest.get("unresolved_gap_count", -1))))
    return CanonicalBoundaryV1(target_day.isoformat(), as_of, tuple(rows))


def evaluate_canonical_paper_readiness(*, boundary: CanonicalBoundaryV1,
                                       archive_root: Path, as_of: datetime,
                                       minimum_bars_per_market: int = 30) -> CanonicalPaperReadinessV1:
    reasons = []
    if boundary.schema_version != VERSION or boundary.trading_authority is not False:
        raise ValueError("canonical boundary rejected")
    target = date.fromisoformat(boundary.target_day_utc)
    if as_of.date() < target:
        reasons.append("TARGET_DAY_NOT_STARTED")
    elif as_of.date() > target:
        reasons.append("TARGET_DAY_EXPIRED")
    if reasons:
        return CanonicalPaperReadinessV1(boundary.target_day_utc, "WAITING", 0, 0, None,
                                         tuple(reasons), True)
    gate = evaluate_ninjatrader_clean_day_gate(
        archive_root=archive_root, as_of=as_of,
        minimum_bars_per_market=minimum_bars_per_market)
    reasons.extend(gate.reasons)
    state = "READY_FOR_OWNER_CONFIRMATION" if gate.state == "READY" else gate.state
    return CanonicalPaperReadinessV1(
        boundary.target_day_utc, state, gate.es_bar_count, gate.nq_bar_count,
        gate.latest_close_time_utc, tuple(reasons), True)
