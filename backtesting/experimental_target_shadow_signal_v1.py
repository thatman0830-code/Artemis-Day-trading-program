"""Fail-closed adapter from target A/B research into a shadow-only signal fact."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import json

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_shadow_profile_comparison_v1 import ShadowSide
from backtesting.target_liquidity_ab_research_v1 import TargetCandidateV1, evaluate_ab

VERSION = "experimental-target-shadow-signal-v1"


class ExperimentalShadowState(str, Enum):
    NO_EXPERIMENTAL_TARGET = "NO_EXPERIMENTAL_TARGET"
    CANONICAL_TARGET_ALREADY_AVAILABLE = "CANONICAL_TARGET_ALREADY_AVAILABLE"
    INVALID_PRICE_ORDER = "INVALID_PRICE_ORDER"
    SHADOW_SIGNAL_AVAILABLE = "SHADOW_SIGNAL_AVAILABLE"


@dataclass(frozen=True)
class ExperimentalTargetShadowSignalV1:
    signal_id: str | None
    source_candidate_id: str
    market: FuturesCanonicalMarket
    side: ShadowSide
    signal_time: datetime
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal | None
    state: ExperimentalShadowState
    baseline_target_id: str | None
    experimental_target_id: str | None
    comparison_only: bool = True
    canonical_policy_changed: bool = False
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


def build_experimental_target_shadow_signal(*, source_candidate_id: str,
        market: FuturesCanonicalMarket, side: ShadowSide, signal_time: datetime,
        entry_price: Decimal, stop_price: Decimal,
        candidates: tuple[TargetCandidateV1, ...]) -> ExperimentalTargetShadowSignalV1:
    if (not source_candidate_id or not isinstance(market, FuturesCanonicalMarket)
            or not isinstance(side, ShadowSide) or signal_time.tzinfo is None
            or signal_time.utcoffset() != timedelta(0)):
        raise ValueError("identified UTC shadow candidate required")
    entry, stop = Decimal(str(entry_price)), Decimal(str(stop_price))
    if not entry.is_finite() or not stop.is_finite() or entry <= 0 or stop <= 0:
        raise ValueError("positive finite entry and stop required")
    required_side = "BSL" if side is ShadowSide.LONG else "LSL"
    baseline, experimental = evaluate_ab(
        candidates=candidates, current_price=entry, required_side=required_side)
    baseline_id = baseline.selected.candidate_id if baseline.selected else None
    experimental_id = experimental.selected.candidate_id if experimental.selected else None
    target = experimental.selected.level if experimental.selected else None
    if baseline.selected is not None:
        state = ExperimentalShadowState.CANONICAL_TARGET_ALREADY_AVAILABLE
    elif target is None:
        state = ExperimentalShadowState.NO_EXPERIMENTAL_TARGET
    elif not ((stop < entry < target) if side is ShadowSide.LONG else (target < entry < stop)):
        state = ExperimentalShadowState.INVALID_PRICE_ORDER
    else:
        state = ExperimentalShadowState.SHADOW_SIGNAL_AVAILABLE
    signal_id = None
    if state is ExperimentalShadowState.SHADOW_SIGNAL_AVAILABLE:
        body = {"version": VERSION, "source": source_candidate_id,
                "market": market.value, "side": side.value,
                "time": signal_time.isoformat(), "entry": format(entry, "f"),
                "stop": format(stop, "f"), "target": format(target, "f"),
                "candidate": experimental_id, "authority": False}
        signal_id = hashlib.sha256(json.dumps(body, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
    return ExperimentalTargetShadowSignalV1(
        signal_id, source_candidate_id, market, side, signal_time, entry, stop,
        target if state is ExperimentalShadowState.SHADOW_SIGNAL_AVAILABLE else None,
        state, baseline_id, experimental_id)
