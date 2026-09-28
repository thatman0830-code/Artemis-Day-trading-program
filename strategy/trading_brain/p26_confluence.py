from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p22_ote import OTE
from strategy.trading_brain.p24_lrl_selection import LRL
from strategy.trading_brain.p25_fvg_ifvg import FVG, IFVG, FVGDirection, FVGState


class ConfluenceType(str, Enum):
    OTE_FVG = "OTE_FVG"
    OTE_IFVG = "OTE_IFVG"
    LRL_FVG = "LRL_FVG"
    LRL_IFVG = "LRL_IFVG"
    SWEEP_FVG = "SWEEP_FVG"
    SWEEP_IFVG = "SWEEP_IFVG"
    DISPLACEMENT_FVG = "DISPLACEMENT_FVG"
    DISPLACEMENT_IFVG = "DISPLACEMENT_IFVG"
    MSS_FVG = "MSS_FVG"
    MSS_IFVG = "MSS_IFVG"


class ConfluenceCategory(str, Enum):
    OVERLAP = "OVERLAP"
    POSITIONAL = "POSITIONAL"
    COINCIDENCE = "COINCIDENCE"


class ConfluenceResult(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"


@dataclass(frozen=True)
class ConfirmedEventFact:
    """Read-only adapter for a confirmed sweep, displacement, or MSS fact."""

    id: str
    event_type: str
    timeframe: str
    event_time: int
    lower_boundary: Decimal
    upper_boundary: Decimal
    direction: FVGDirection | None
    confirmed: bool = True
    active: bool = True
    setup_eligible: bool = True


@dataclass(frozen=True)
class Confluence:
    id: str
    type: ConfluenceType
    category: ConfluenceCategory
    primary_object_id: str
    secondary_object_id: str
    primary_type: str
    secondary_type: str
    primary_timeframe: str
    secondary_timeframe: str
    overlap_low: Decimal | None
    overlap_high: Decimal | None
    overlap_width: Decimal
    directional_compatibility: bool
    temporal_relationship: bool
    positional_relationship: bool
    causal_relationship: bool
    created_time: int
    terminated_time: int | None
    active: bool
    historical: bool


@dataclass(frozen=True)
class ConfluenceEvaluation:
    type: ConfluenceType
    category: ConfluenceCategory
    result: ConfluenceResult
    confluence: Confluence | None

    @property
    def is_confluent(self) -> bool:
        return self.result == ConfluenceResult.TRUE


@dataclass(frozen=True)
class ConfluenceUpdateResult:
    active_confluence: Confluence | None
    terminated_confluence: Confluence | None


class ConfluenceEngine:
    """Canonical #26 facts/relationships layer only.

    This engine records spatial or temporal relationships. It has no setup,
    order, sizing, risk, authorization, trigger, or execution behavior.
    """

    _EVENT_PREFIX = {
        "SWEEP": "SWEEP",
        "DISPLACEMENT": "DISPLACEMENT",
        "MSS": "MSS",
    }

    @staticmethod
    def _imbalance_kind(imbalance: FVG | IFVG) -> str:
        return "IFVG" if isinstance(imbalance, IFVG) else "FVG"

    @staticmethod
    def _imbalance_active(imbalance: FVG | IFVG) -> bool:
        if isinstance(imbalance, IFVG):
            return imbalance.state == FVGState.INVERTED
        return (
            imbalance.state == FVGState.ACTIVE
            and not imbalance.fully_mitigated
            and not imbalance.converted_once
        )

    @staticmethod
    def _positive_overlap(
        first_low: Decimal, first_high: Decimal,
        second_low: Decimal, second_high: Decimal,
    ) -> tuple[Decimal | None, Decimal | None, Decimal]:
        low = max(first_low, second_low)
        high = min(first_high, second_high)
        width = high - low
        if width <= 0:
            return None, None, Decimal("0")
        return low, high, width

    @staticmethod
    def _direction_compatible(first: object, second: FVG | IFVG) -> bool:
        direction = getattr(first, "direction", None)
        if direction is None:
            return True
        first_value = direction.value if isinstance(direction, Enum) else str(direction)
        return first_value == second.direction.value

    @staticmethod
    def _identity(
        *, type_: ConfluenceType, primary_id: str, secondary_id: str,
        created_time: int,
    ) -> str:
        key = (
            f"trading-brain:#26:{type_.value}:{primary_id}:"
            f"{secondary_id}:{created_time}"
        )
        return str(uuid5(NAMESPACE_URL, key))

    @classmethod
    def _true(
        cls, *, type_: ConfluenceType, category: ConfluenceCategory,
        primary_id: str, secondary: FVG | IFVG,
        primary_type: str, primary_timeframe: str,
        overlap_low: Decimal | None, overlap_high: Decimal | None,
        overlap_width: Decimal, directional_compatibility: bool,
        temporal_relationship: bool, positional_relationship: bool,
        causal_relationship: bool, created_time: int,
    ) -> ConfluenceEvaluation:
        record = Confluence(
            id=cls._identity(
                type_=type_, primary_id=primary_id,
                secondary_id=secondary.id, created_time=created_time,
            ),
            type=type_, category=category,
            primary_object_id=primary_id, secondary_object_id=secondary.id,
            primary_type=primary_type,
            secondary_type=cls._imbalance_kind(secondary),
            primary_timeframe=primary_timeframe,
            secondary_timeframe=secondary.timeframe,
            overlap_low=overlap_low, overlap_high=overlap_high,
            overlap_width=overlap_width,
            directional_compatibility=directional_compatibility,
            temporal_relationship=temporal_relationship,
            positional_relationship=positional_relationship,
            causal_relationship=causal_relationship,
            created_time=created_time, terminated_time=None,
            active=True, historical=False,
        )
        return ConfluenceEvaluation(type_, category, ConfluenceResult.TRUE, record)

    @staticmethod
    def _false(
        type_: ConfluenceType, category: ConfluenceCategory,
    ) -> ConfluenceEvaluation:
        return ConfluenceEvaluation(type_, category, ConfluenceResult.FALSE, None)

    def evaluate_ote(
        self, *, ote: OTE, imbalance: FVG | IFVG, evaluation_time: int,
        setup_eligible: bool = True,
    ) -> ConfluenceEvaluation:
        kind = self._imbalance_kind(imbalance)
        type_ = ConfluenceType[f"OTE_{kind}"]
        category = ConfluenceCategory.OVERLAP
        if evaluation_time < max(ote.confirmation_time, imbalance.confirmation_time):
            return self._false(type_, category)
        eligible = (
            ote.active and not ote.historical
            and self._imbalance_active(imbalance) and setup_eligible
        )
        low, high, width = self._positive_overlap(
            ote.zone_low, ote.zone_high,
            imbalance.lower_boundary, imbalance.upper_boundary,
        )
        if not eligible or width == 0:
            return self._false(type_, category)
        return self._true(
            type_=type_, category=category, primary_id=ote.id,
            secondary=imbalance, primary_type="OTE",
            primary_timeframe=ote.timeframe, overlap_low=low,
            overlap_high=high, overlap_width=width,
            directional_compatibility=self._direction_compatible(ote, imbalance),
            temporal_relationship=True, positional_relationship=True,
            causal_relationship=False, created_time=evaluation_time,
        )

    def evaluate_lrl(
        self, *, lrl: LRL, imbalance: FVG | IFVG,
        current_price: Decimal, evaluation_time: int,
        setup_eligible: bool = True,
    ) -> ConfluenceEvaluation:
        kind = self._imbalance_kind(imbalance)
        type_ = ConfluenceType[f"LRL_{kind}"]
        category = ConfluenceCategory.POSITIONAL
        price = Decimal(str(current_price))
        if price <= 0:
            raise ValueError("current_price must be positive.")
        if evaluation_time < max(lrl.selected_time, imbalance.confirmation_time):
            return self._false(type_, category)
        eligible = (
            lrl.active and not lrl.historical
            and self._imbalance_active(imbalance) and setup_eligible
        )
        low, high, width = self._positive_overlap(
            min(price, lrl.level), max(price, lrl.level),
            imbalance.lower_boundary, imbalance.upper_boundary,
        )
        if not eligible or width == 0:
            return self._false(type_, category)
        return self._true(
            type_=type_, category=category, primary_id=lrl.id,
            secondary=imbalance, primary_type="LRL",
            primary_timeframe=lrl.pool_timeframe,
            overlap_low=low, overlap_high=high, overlap_width=width,
            directional_compatibility=self._direction_compatible(lrl, imbalance),
            temporal_relationship=True, positional_relationship=True,
            causal_relationship=False, created_time=evaluation_time,
        )

    def evaluate_event(
        self, *, event: ConfirmedEventFact, imbalance: FVG | IFVG,
        evaluation_time: int,
    ) -> ConfluenceEvaluation:
        event_type = event.event_type.upper()
        if event_type not in self._EVENT_PREFIX:
            raise ValueError("event_type must be SWEEP, DISPLACEMENT, or MSS.")
        if event.upper_boundary < event.lower_boundary:
            raise ValueError("Event fact has invalid interval geometry.")
        kind = self._imbalance_kind(imbalance)
        type_ = ConfluenceType[f"{self._EVENT_PREFIX[event_type]}_{kind}"]
        category = ConfluenceCategory.COINCIDENCE
        if evaluation_time < max(event.event_time, imbalance.confirmation_time):
            return self._false(type_, category)
        low, high, width = self._positive_overlap(
            event.lower_boundary, event.upper_boundary,
            imbalance.lower_boundary, imbalance.upper_boundary,
        )
        coincident = event.event_time == imbalance.confirmation_time
        eligible = (
            event.confirmed and event.active and event.setup_eligible
            and self._imbalance_active(imbalance)
        )
        if not eligible or not coincident or width == 0:
            return self._false(type_, category)
        return self._true(
            type_=type_, category=category, primary_id=event.id,
            secondary=imbalance, primary_type=event_type,
            primary_timeframe=event.timeframe,
            overlap_low=low, overlap_high=high, overlap_width=width,
            directional_compatibility=self._direction_compatible(event, imbalance),
            temporal_relationship=True, positional_relationship=True,
            causal_relationship=True, created_time=evaluation_time,
        )

    @staticmethod
    def reconcile(
        *, previous: Confluence, evaluation: ConfluenceEvaluation,
        evaluation_time: int,
    ) -> ConfluenceUpdateResult:
        if not previous.active or previous.historical:
            raise ValueError("previous confluence must be active.")
        if evaluation.is_confluent:
            current = evaluation.confluence
            if (
                current.type == previous.type
                and current.primary_object_id == previous.primary_object_id
                and current.secondary_object_id == previous.secondary_object_id
            ):
                return ConfluenceUpdateResult(previous, None)
            raise ValueError("A different relationship cannot replace active confluence implicitly.")
        terminated = replace(
            previous, active=False, historical=True,
            terminated_time=int(evaluation_time),
        )
        return ConfluenceUpdateResult(None, terminated)
