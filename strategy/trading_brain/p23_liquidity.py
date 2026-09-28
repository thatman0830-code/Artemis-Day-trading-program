from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p21_active_dealing_range import StructuralRange


class LiquidityState(str, Enum):
    ACTIVE = "ACTIVE"
    VIOLATED = "VIOLATED"
    SWEPT = "SWEPT"
    BROKEN = "BROKEN"
    CONSUMED = "CONSUMED"


class LiquiditySide(str, Enum):
    BSL = "BSL"
    LSL = "LSL"


@dataclass(frozen=True)
class LiquidityReference:
    id: str
    timeframe: str
    side: LiquiditySide
    price: Decimal
    confirmation_time: int
    source_type: str
    major_reference: bool = False


@dataclass(frozen=True)
class LiquidityPool:
    id: str
    timeframe: str
    side: LiquiditySide
    component_reference_ids: tuple[str, ...]
    component_prices: tuple[Decimal, ...]
    component_source_types: tuple[str, ...]
    consolidated_level: Decimal
    tolerance_ticks: int
    touch_count: int
    created_time: int
    confirmation_time: int
    state: LiquidityState
    external: bool
    deepest_penetration: Decimal = Decimal("0")


@dataclass(frozen=True)
class LiquidityInventory:
    pools: tuple[LiquidityPool, ...]
    single_references: tuple[LiquidityReference, ...]


@dataclass(frozen=True)
class LiquiditySweep:
    id: str
    pool_id: str
    pool_timeframe: str
    event_timeframe: str
    side: LiquiditySide
    level: Decimal
    event_time: int
    candle_extreme: Decimal
    candle_close: Decimal
    penetration: Decimal
    outcome: LiquidityState
    final_state: LiquidityState


@dataclass(frozen=True)
class LiquidityInteractionResult:
    pool: LiquidityPool
    event: LiquiditySweep | None


class LiquidityPoolEngine:
    """Canonical #23 pool construction from qualifying references."""

    def __init__(self, *, minimum_tick: Decimal):
        self.minimum_tick = Decimal(str(minimum_tick))
        if self.minimum_tick <= 0:
            raise ValueError("minimum_tick must be positive.")

    def _normalize(self, price: Decimal) -> Decimal:
        ticks = (price / self.minimum_tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return ticks * self.minimum_tick

    @staticmethod
    def _pool_id(references: tuple[LiquidityReference, ...]) -> str:
        key = ":".join(sorted(reference.id for reference in references))
        return str(uuid5(NAMESPACE_URL, f"trading-brain:#23-pool:{key}"))

    def _build_pool(
        self, references: tuple[LiquidityReference, ...],
        active_range: StructuralRange | None,
    ) -> LiquidityPool:
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            mean = sum((reference.price for reference in references), Decimal("0")) / Decimal(len(references))
            level = self._normalize(mean)
        major = any(reference.major_reference for reference in references)
        external = (
            major
            or active_range is None
            or level <= active_range.lower_boundary
            or level >= active_range.upper_boundary
        )
        return LiquidityPool(
            id=self._pool_id(references), timeframe=references[0].timeframe,
            side=references[0].side,
            component_reference_ids=tuple(reference.id for reference in references),
            component_prices=tuple(reference.price for reference in references),
            component_source_types=tuple(reference.source_type for reference in references),
            consolidated_level=level, tolerance_ticks=1,
            touch_count=len(references),
            created_time=min(reference.confirmation_time for reference in references),
            confirmation_time=max(reference.confirmation_time for reference in references),
            state=LiquidityState.ACTIVE, external=external,
        )

    def build_inventory(
        self, *, references: tuple[LiquidityReference, ...],
        active_range: StructuralRange | None,
    ) -> LiquidityInventory:
        ids = [reference.id for reference in references]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate liquidity reference identity.")
        if active_range is not None and not active_range.active:
            raise ValueError("Liquidity classification requires the active #21 range.")

        groups: dict[tuple[str, LiquiditySide], list[LiquidityReference]] = {}
        for reference in references:
            if reference.price <= 0:
                raise ValueError("Liquidity reference prices must be positive.")
            groups.setdefault((reference.timeframe, reference.side), []).append(reference)

        pools: list[LiquidityPool] = []
        singles: list[LiquidityReference] = []
        for _, group in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1].value)):
            ordered = sorted(group, key=lambda ref: (ref.price, ref.confirmation_time, ref.id))
            clusters: list[list[LiquidityReference]] = []
            for reference in ordered:
                if not clusters or reference.price - clusters[-1][0].price > self.minimum_tick:
                    clusters.append([reference])
                else:
                    clusters[-1].append(reference)
            for cluster in clusters:
                if len(cluster) >= 2:
                    pools.append(self._build_pool(tuple(cluster), active_range))
                else:
                    singles.append(cluster[0])

        pools.sort(key=lambda pool: (pool.timeframe, pool.side.value, pool.consolidated_level, pool.id))
        singles.sort(key=lambda ref: (ref.timeframe, ref.side.value, ref.price, ref.id))
        return LiquidityInventory(tuple(pools), tuple(singles))


class LiquidityInteractionEngine:
    """Canonical #23 touch/violation/sweep/break lifecycle."""

    @staticmethod
    def evaluate(
        *, pool: LiquidityPool, candle: dict, event_timeframe: str,
    ) -> LiquidityInteractionResult:
        if pool.state == LiquidityState.CONSUMED:
            return LiquidityInteractionResult(pool, None)
        missing = {"t", "h", "l", "c"} - set(candle)
        if missing:
            raise ValueError(f"Missing candle fields: {sorted(missing)}")
        if candle.get("is_closed") is not True:
            raise ValueError("Liquidity interaction requires a closed candle.")
        high = Decimal(str(candle["h"]))
        low = Decimal(str(candle["l"]))
        close = Decimal(str(candle["c"]))
        if high < low or not (low <= close <= high):
            raise ValueError("Invalid closed-candle OHLC geometry.")

        level = pool.consolidated_level
        if pool.side == LiquiditySide.BSL:
            penetration = max(Decimal("0"), high - level)
            swept = penetration > 0 and close < level
            broken = penetration > 0 and close > level
            extreme = high
        else:
            penetration = max(Decimal("0"), level - low)
            swept = penetration > 0 and close > level
            broken = penetration > 0 and close < level
            extreme = low

        deepest = max(pool.deepest_penetration, penetration)
        if penetration == 0:
            return LiquidityInteractionResult(pool, None)
        if not swept and not broken:
            return LiquidityInteractionResult(
                replace(pool, state=LiquidityState.VIOLATED, deepest_penetration=deepest), None,
            )

        outcome = LiquidityState.SWEPT if swept else LiquidityState.BROKEN
        key = f"trading-brain:#23-event:{pool.id}:{candle['t']}:{event_timeframe}:{outcome.value}"
        event = LiquiditySweep(
            id=str(uuid5(NAMESPACE_URL, key)), pool_id=pool.id,
            pool_timeframe=pool.timeframe, event_timeframe=event_timeframe,
            side=pool.side, level=level, event_time=int(candle["t"]),
            candle_extreme=extreme, candle_close=close,
            penetration=penetration, outcome=outcome,
            final_state=LiquidityState.CONSUMED,
        )
        consumed = replace(pool, state=LiquidityState.CONSUMED, deepest_penetration=deepest)
        return LiquidityInteractionResult(consumed, event)
