"""Non-authoritative A/B target-candidate research lane.

Baseline admits clustered liquidity pools only.  Experimental adds eligible
single major references without changing canonical #23/#24 policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


VERSION = "target-liquidity-ab-research-v1"


class TargetLane(str, Enum):
    BASELINE_CLUSTERED = "BASELINE_CLUSTERED"
    EXPERIMENTAL_MAJOR_SINGLE = "EXPERIMENTAL_MAJOR_SINGLE"


@dataclass(frozen=True)
class TargetCandidateV1:
    candidate_id: str
    side: str
    level: Decimal
    source_type: str
    clustered: bool
    external: bool
    active: bool = True


@dataclass(frozen=True)
class TargetLaneResultV1:
    lane: TargetLane
    selected: TargetCandidateV1 | None
    eligible_candidate_ids: tuple[str, ...]
    comparison_only: bool = True
    canonical_policy_changed: bool = False
    paper_execution_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


MAJOR_SINGLE_TYPES = frozenset({"PDH", "PDL", "EXTERNAL_STRUCTURAL_SWING"})


def evaluate_target_lane(*, candidates: tuple[TargetCandidateV1, ...], current_price: Decimal,
                         required_side: str, lane: TargetLane) -> TargetLaneResultV1:
    price = Decimal(str(current_price))
    if price <= 0 or required_side not in {"BSL", "LSL"}:
        raise ValueError("positive price and BSL/LSL side required")
    if not isinstance(candidates, tuple) or len({x.candidate_id for x in candidates}) != len(candidates):
        raise ValueError("unique immutable candidate tuple required")
    eligible = []
    for item in candidates:
        if (not isinstance(item, TargetCandidateV1) or not item.active
                or item.side != required_side or not item.level.is_finite()
                or item.level <= 0):
            continue
        directional = item.level > price if required_side == "BSL" else item.level < price
        baseline = item.clustered
        experimental = item.clustered or (item.external and item.source_type in MAJOR_SINGLE_TYPES)
        if directional and (baseline if lane is TargetLane.BASELINE_CLUSTERED else experimental):
            eligible.append(item)
    ordered = tuple(sorted(eligible, key=lambda x: (abs(x.level-price), x.source_type, x.candidate_id)))
    return TargetLaneResultV1(lane, ordered[0] if ordered else None,
                              tuple(x.candidate_id for x in ordered))


def evaluate_ab(*, candidates: tuple[TargetCandidateV1, ...], current_price: Decimal,
                required_side: str) -> tuple[TargetLaneResultV1, TargetLaneResultV1]:
    return tuple(evaluate_target_lane(candidates=candidates, current_price=current_price,
                                      required_side=required_side, lane=lane)
                 for lane in TargetLane)
