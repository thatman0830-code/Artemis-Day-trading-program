from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p21_active_dealing_range import StructuralRange


@dataclass(frozen=True)
class OTE:
    id: str
    timeframe: str
    direction: StructuralRegime
    range_id: str
    anchor_high: Decimal
    anchor_low: Decimal
    eq_50_price: Decimal
    ote_79_price: Decimal
    creation_time: int
    confirmation_time: int
    active: bool
    historical: bool
    terminated_by_event_id: str | None = None

    @property
    def zone_low(self) -> Decimal:
        return min(self.eq_50_price, self.ote_79_price)

    @property
    def zone_high(self) -> Decimal:
        return max(self.eq_50_price, self.ote_79_price)

    def contains(self, price: Decimal) -> bool:
        return self.zone_low <= price <= self.zone_high


@dataclass(frozen=True)
class OTEUpdateResult:
    active_ote: OTE | None
    terminated_ote: OTE | None
    preserved_previous_ote: OTE | None


class OTEEngine:
    """Canonical #22 OTE geometry and lifecycle over #21 ranges only."""

    HALF = Decimal("0.50")
    DEEP = Decimal("0.79")

    @staticmethod
    def _id(range_: StructuralRange) -> str:
        return str(uuid5(NAMESPACE_URL, f"trading-brain:#22:{range_.id}"))

    @staticmethod
    def _validate_range(range_: StructuralRange) -> None:
        if not range_.active or range_.historical:
            raise ValueError("Only an active #21 range may generate active OTE.")
        if range_.upper_boundary <= range_.lower_boundary:
            raise ValueError("OTE requires valid #21 range geometry.")
        if range_.regime not in {StructuralRegime.BULLISH, StructuralRegime.BEARISH}:
            raise ValueError("OTE requires a directional active range.")

    def create(self, *, active_range: StructuralRange) -> OTE:
        self._validate_range(active_range)
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            high = active_range.upper_boundary
            low = active_range.lower_boundary
            width = high - low
            eq = low + width * self.HALF
            if active_range.regime == StructuralRegime.BULLISH:
                # Owner-authorized implementation choice: discount-side retracement.
                ote_79 = high - width * self.DEEP
            else:
                # Owner-authorized implementation choice: premium-side retracement.
                ote_79 = low + width * self.DEEP

        return OTE(
            id=self._id(active_range),
            timeframe=active_range.timeframe,
            direction=active_range.regime,
            range_id=active_range.id,
            anchor_high=active_range.upper_boundary,
            anchor_low=active_range.lower_boundary,
            eq_50_price=eq,
            ote_79_price=ote_79,
            creation_time=active_range.creation_time,
            confirmation_time=active_range.confirmation_time,
            active=True,
            historical=False,
        )

    def update(
        self,
        *,
        active_range: StructuralRange | None,
        previous_active_ote: OTE | None = None,
        termination_event_id: str | None = None,
    ) -> OTEUpdateResult:
        if previous_active_ote is not None:
            if not previous_active_ote.active or previous_active_ote.historical:
                raise ValueError("previous_active_ote must be active.")

        if active_range is None:
            if previous_active_ote is None:
                return OTEUpdateResult(None, None, None)
            if termination_event_id is None:
                raise ValueError("OTE termination requires the accepted structural event ID.")
            terminated = replace(
                previous_active_ote,
                active=False,
                historical=True,
                terminated_by_event_id=termination_event_id,
            )
            return OTEUpdateResult(None, terminated, None)

        self._validate_range(active_range)
        if previous_active_ote is not None and previous_active_ote.range_id == active_range.id:
            return OTEUpdateResult(previous_active_ote, None, previous_active_ote)

        new_ote = self.create(active_range=active_range)
        terminated = None
        if previous_active_ote is not None:
            terminated = replace(
                previous_active_ote,
                active=False,
                historical=True,
                terminated_by_event_id=active_range.created_by_event_id,
            )
        return OTEUpdateResult(new_ote, terminated, None)
