from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p23_liquidity import (
    LiquidityPool, LiquiditySide, LiquidityState,
)


class LRLRole(str, Enum):
    CONTINUATION_TARGET = "CONTINUATION_TARGET"
    REVERSAL_SWEEP_REFERENCE = "REVERSAL_SWEEP_REFERENCE"


class LRLTerminationReason(str, Enum):
    CONSUMED = "CONSUMED"
    SETUP_INVALIDATED = "SETUP_INVALIDATED"
    MSS = "MSS"
    RANGE_REPLACED = "RANGE_REPLACED"
    TRANSITION = "TRANSITION"


@dataclass(frozen=True)
class LRL:
    id: str
    role: LRLRole
    pool_id: str
    pool_timeframe: str
    side: LiquiditySide
    level: Decimal
    external: bool
    active_range_id: str
    regime: StructuralRegime
    selected_time: int
    active: bool = True
    historical: bool = False
    termination_time: int | None = None
    termination_reason: LRLTerminationReason | None = None


@dataclass(frozen=True)
class LRLSelectionResult:
    active_lrl: LRL | None
    terminated_lrl: LRL | None = None


class LRLSelectionEngine:
    """Canonical #24 deterministic selection and persistence.

    Reward/risk qualification deliberately remains outside this primitive.  The
    selected nearest structural target is handed to #27 unchanged.
    """

    _REFERENCE_PRIORITY = {
        "PREVIOUS_WEEK_HIGH": 0, "PREVIOUS_WEEK_LOW": 0,
        "PWH": 0, "PWL": 0,
        "PREVIOUS_DAY_HIGH": 1, "PREVIOUS_DAY_LOW": 1,
        "PDH": 1, "PDL": 1,
        "SESSION_HIGH": 2, "SESSION_LOW": 2,
        "EXTERNAL_STRUCTURAL_SWING": 3,
        "EQUAL_HIGH": 4, "EQUAL_LOW": 4,
        "INTERNAL_STRUCTURAL_SWING": 5,
    }

    @staticmethod
    def required_side(*, regime: StructuralRegime, role: LRLRole) -> LiquiditySide | None:
        if regime not in {StructuralRegime.BULLISH, StructuralRegime.BEARISH}:
            return None
        if role == LRLRole.CONTINUATION_TARGET:
            return LiquiditySide.BSL if regime == StructuralRegime.BULLISH else LiquiditySide.LSL
        # Amendment 005A: reference the existing regime's extension-side sweep.
        return LiquiditySide.BSL if regime == StructuralRegime.BULLISH else LiquiditySide.LSL

    @classmethod
    def _reference_rank(cls, pool: LiquidityPool) -> int:
        ranks: list[int] = []
        for source in pool.component_source_types:
            normalized = source.upper().replace("-", "_").replace(" ", "_")
            if normalized in {"STRUCTURAL_SWING", "MECHANICAL_SWING"}:
                normalized = (
                    "EXTERNAL_STRUCTURAL_SWING" if pool.external
                    else "INTERNAL_STRUCTURAL_SWING"
                )
            ranks.append(cls._REFERENCE_PRIORITY.get(normalized, 6))
        return min(ranks, default=6)

    @staticmethod
    def _eligible(pool: LiquidityPool, *, side: LiquiditySide, price: Decimal) -> bool:
        if pool.state != LiquidityState.ACTIVE or pool.side != side:
            return False
        if side == LiquiditySide.BSL:
            return pool.consolidated_level > price
        return pool.consolidated_level < price

    @classmethod
    def _candidate_key(cls, pool: LiquidityPool, price: Decimal) -> tuple:
        return (
            abs(pool.consolidated_level - price),
            cls._reference_rank(pool),
            pool.confirmation_time,
            pool.id,
        )

    @staticmethod
    def _terminate(
        lrl: LRL, *, timestamp: int, reason: LRLTerminationReason,
    ) -> LRL:
        return replace(
            lrl, active=False, historical=True,
            termination_time=timestamp, termination_reason=reason,
        )

    @staticmethod
    def _termination_reason(
        *, previous: LRL, pools_by_id: dict[str, LiquidityPool],
        active_range: StructuralRange | None, regime: StructuralRegime,
        setup_invalidated: bool, mss_confirmed: bool,
    ) -> LRLTerminationReason | None:
        if regime == StructuralRegime.TRANSITION or active_range is None:
            return LRLTerminationReason.TRANSITION
        if setup_invalidated:
            return LRLTerminationReason.SETUP_INVALIDATED
        if mss_confirmed:
            return LRLTerminationReason.MSS
        if previous.active_range_id != active_range.id:
            return LRLTerminationReason.RANGE_REPLACED
        pool = pools_by_id.get(previous.pool_id)
        if pool is None or pool.state == LiquidityState.CONSUMED:
            return LRLTerminationReason.CONSUMED
        return None

    def select(
        self, *, pools: tuple[LiquidityPool, ...], current_price: Decimal,
        active_range: StructuralRange | None, regime: StructuralRegime,
        role: LRLRole, selection_time: int,
        previous_active_lrl: LRL | None = None,
        setup_invalidated: bool = False, mss_confirmed: bool = False,
    ) -> LRLSelectionResult:
        price = Decimal(str(current_price))
        if price <= 0:
            raise ValueError("current_price must be positive.")
        ids = [pool.id for pool in pools]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate liquidity pool identity.")
        if active_range is not None and (not active_range.active or active_range.historical):
            raise ValueError("#24 requires the active #21 range.")

        pools_by_id = {pool.id: pool for pool in pools}
        terminated = None
        if previous_active_lrl is not None:
            if not previous_active_lrl.active or previous_active_lrl.historical:
                raise ValueError("previous_active_lrl must be active.")
            reason = self._termination_reason(
                previous=previous_active_lrl, pools_by_id=pools_by_id,
                active_range=active_range, regime=regime,
                setup_invalidated=setup_invalidated, mss_confirmed=mss_confirmed,
            )
            if reason is None:
                return LRLSelectionResult(previous_active_lrl)
            terminated = self._terminate(
                previous_active_lrl, timestamp=selection_time, reason=reason,
            )
            if reason in {
                LRLTerminationReason.CONSUMED,
                LRLTerminationReason.SETUP_INVALIDATED,
                LRLTerminationReason.MSS,
                LRLTerminationReason.TRANSITION,
            }:
                return LRLSelectionResult(None, terminated)

        side = self.required_side(regime=regime, role=role)
        if side is None or active_range is None:
            return LRLSelectionResult(None, terminated)
        candidates = [
            pool for pool in pools if self._eligible(pool, side=side, price=price)
        ]
        if not candidates:
            return LRLSelectionResult(None, terminated)
        external = [pool for pool in candidates if pool.external]
        selected = min(external or candidates, key=lambda pool: self._candidate_key(pool, price))
        key = (
            f"trading-brain:#24:{role.value}:{selected.id}:"
            f"{active_range.id}:{regime.value}:{selection_time}"
        )
        lrl = LRL(
            id=str(uuid5(NAMESPACE_URL, key)), role=role,
            pool_id=selected.id, pool_timeframe=selected.timeframe,
            side=selected.side, level=selected.consolidated_level,
            external=selected.external, active_range_id=active_range.id,
            regime=regime, selected_time=selection_time,
        )
        return LRLSelectionResult(lrl, terminated)
