"""Shadow-only orchestrator permitting external PDH/PDL singles as target research."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from backtesting.orchestrator import TradingBrainEvaluationOrchestrator
from backtesting.market_data import CanonicalTimeframe
from backtesting.target_liquidity_ab_research_v1 import TargetCandidateV1, evaluate_ab
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p23_liquidity import LiquidityInventory, LiquiditySide
from strategy.trading_brain.p24_lrl_selection import (
    LRL, LRLRole, LRLSelectionEngine, LRLSelectionResult)

VERSION = "experimental-major-single-orchestrator-v1"
SESSION_POLICY = "CME_GLOBEX_1700_1600_AMERICA_CHICAGO_V1"


class ExperimentalMajorSingleTargetOrchestratorV1(TradingBrainEvaluationOrchestrator):
    """Uses canonical pools first, then an isolated eligible-major-single fallback."""

    comparison_only = True
    canonical_policy_changed = False
    paper_execution_permitted = False
    live_trading_permitted = False
    trading_authority = False

    def _prior_completed_session_candidates(self, *, selection_time: int,
                                            required_side: LiquiditySide):
        evaluated = datetime.fromtimestamp(selection_time / 1000, tz=timezone.utc)
        zone = ZoneInfo("America/Chicago")
        local = evaluated.astimezone(zone)
        latest_end_day = (local.date() if local.time() >= time(16)
                          else local.date() - timedelta(days=1))
        candles = (); session_start = session_end = None
        for offset in range(5):
            end_day = latest_end_day - timedelta(days=offset)
            candidate_end = datetime.combine(end_day, time(16), tzinfo=zone).astimezone(timezone.utc)
            candidate_start = datetime.combine(end_day - timedelta(days=1), time(17),
                                               tzinfo=zone).astimezone(timezone.utc)
            selected = tuple(x for x in self.dataset.candles
                if x.timeframe is CanonicalTimeframe.M1
                and candidate_start <= x.open_time and x.close_time <= candidate_end)
            expected_count = int((candidate_end - candidate_start).total_seconds() // 60)
            complete = bool(candidate_end <= evaluated and len(selected) == expected_count
                and selected and selected[0].open_time == candidate_start
                and selected[-1].close_time == candidate_end
                and all(selected[i].close_time == selected[i + 1].open_time
                        for i in range(len(selected) - 1)))
            if complete:
                candles, session_start, session_end = selected, candidate_start, candidate_end
                break
        if not candles:
            return ()
        high = max(x.high for x in candles); low = min(x.low for x in candles)
        values = (("PDH", LiquiditySide.BSL, high), ("PDL", LiquiditySide.LSL, low))
        result = []
        for source, side, level in values:
            if side is not required_side:
                continue
            ties = tuple(x.id for x in candles if (x.high if side is LiquiditySide.BSL else x.low) == level)
            identity = sha256("\x1f".join((SESSION_POLICY, self.dataset.dataset_id,
                session_start.isoformat(), session_end.isoformat(), source,
                format(level, "f"), *ties)).encode()).hexdigest()
            result.append(TargetCandidateV1(identity, side.value, level, source,
                                             False, True, True))
        return tuple(result)

    def _select_target(self, *, inventory: LiquidityInventory, current_price: Decimal,
                       active_range: StructuralRange | None, regime: StructuralRegime,
                       selection_time: int, previous_active_lrl: LRL | None,
                       setup_invalidated: bool) -> LRLSelectionResult:
        canonical = super()._select_target(
            inventory=inventory, current_price=current_price, active_range=active_range,
            regime=regime, selection_time=selection_time,
            previous_active_lrl=previous_active_lrl,
            setup_invalidated=setup_invalidated)
        if canonical.active_lrl is not None or canonical.terminated_lrl is not None:
            return canonical
        required = LRLSelectionEngine.required_side(
            regime=regime, role=LRLRole.CONTINUATION_TARGET)
        if required is None or active_range is None or setup_invalidated:
            return canonical
        inventory_candidates = tuple(TargetCandidateV1(
            candidate_id=x.id, side=x.side.value, level=x.price,
            source_type=x.source_type, clustered=False,
            external=x.major_reference, active=True,
        ) for x in inventory.single_references)
        candidates = inventory_candidates + self._prior_completed_session_candidates(
            selection_time=selection_time, required_side=required)
        _, experimental = evaluate_ab(candidates=candidates,
            current_price=Decimal(str(current_price)), required_side=required.value)
        selected = experimental.selected
        if selected is None:
            return canonical
        reference = next((x for x in inventory.single_references
                          if x.id == selected.candidate_id), None)
        timeframe = reference.timeframe if reference is not None else "1m"
        level = reference.price if reference is not None else selected.level
        identity = str(uuid5(NAMESPACE_URL,
            f"{VERSION}:{selected.candidate_id}:{active_range.id}:{regime.value}:{selection_time}"))
        return LRLSelectionResult(LRL(
            id=identity, role=LRLRole.CONTINUATION_TARGET, pool_id=selected.candidate_id,
            pool_timeframe=timeframe, side=LiquiditySide(required.value),
            level=level, external=True, active_range_id=active_range.id,
            regime=regime, selected_time=selection_time))
