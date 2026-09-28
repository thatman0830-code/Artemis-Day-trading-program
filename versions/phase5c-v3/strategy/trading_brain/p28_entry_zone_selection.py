from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p11_cisd_confirmation import CISDEngine, CISDProcess
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p25_fvg_ifvg import FVG, IFVG, FVGState
from strategy.trading_brain.p27_setup_qualification import (
    ContinuationSetupState, ReversalSetupState, Setup, SetupModel,
)


class EntryZoneType(str, Enum):
    FVG = "FVG"
    IFVG = "IFVG"


class EntryZoneSelectionState(str, Enum):
    SELECTED = "SELECTED"
    NO_ELIGIBLE_ZONE = "NO_ELIGIBLE_ZONE"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class FrozenEntryZoneCandidate:
    zone_id: str
    zone_type: EntryZoneType
    timeframe: str
    direction: StructuralRegime
    zone_low: Decimal
    zone_high: Decimal
    confirmation_time: int
    raw_midpoint: Decimal


@dataclass(frozen=True)
class EntryZoneSelection:
    id: str
    setup_id: str
    setup_candidate_id: str
    model: SetupModel
    direction: StructuralRegime
    state: EntryZoneSelectionState
    eligibility_time: int
    candidate_set_frozen_time: int
    frozen_candidates: tuple[FrozenEntryZoneCandidate, ...]
    selected_zone_id: str | None
    selected_zone_type: EntryZoneType | None
    zone_low: Decimal | None
    zone_high: Decimal | None
    eq_raw: Decimal | None
    eq_normalized: Decimal | None
    minimum_tick: Decimal
    invalidated_zone_ids: tuple[str, ...]
    previous_selection_id: str | None = None
    selection_time: int | None = None
    invalidation_time: int | None = None
    immutable: bool = True


class EntryZoneSelectionEngine:
    """Canonical #28 frozen candidate selection and EQ only.

    It does not select a stop, calculate R, arm/reject a setup, authorize risk,
    size, place orders, or execute.
    """

    def __init__(self, *, minimum_tick: Decimal):
        self.minimum_tick = self._decimal(minimum_tick, field="minimum_tick")
        if self.minimum_tick <= 0:
            raise ValueError("minimum_tick must be positive.")

    @staticmethod
    def _decimal(value: object, *, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{field} must be an exact finite number.") from error
        if not result.is_finite():
            raise ValueError(f"{field} must be an exact finite number.")
        return result

    @staticmethod
    def _zone_type(zone: FVG | IFVG) -> EntryZoneType:
        return EntryZoneType.IFVG if isinstance(zone, IFVG) else EntryZoneType.FVG

    @staticmethod
    def _active(zone: FVG | IFVG) -> bool:
        if isinstance(zone, IFVG):
            return zone.state == FVGState.INVERTED
        return (
            zone.state == FVGState.ACTIVE
            and not zone.fully_mitigated
            and not zone.converted_once
        )

    @staticmethod
    def _direction(zone: FVG | IFVG) -> StructuralRegime:
        return StructuralRegime(zone.direction.value)

    @classmethod
    def _snapshot(cls, zone: FVG | IFVG) -> FrozenEntryZoneCandidate:
        low = cls._decimal(zone.lower_boundary, field="zone_low")
        high = cls._decimal(zone.upper_boundary, field="zone_high")
        if low <= 0 or high <= low:
            raise ValueError("Entry-zone candidates require positive non-zero geometry.")
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            midpoint = (high + low) / Decimal("2")
        return FrozenEntryZoneCandidate(
            zone_id=zone.id, zone_type=cls._zone_type(zone),
            timeframe=zone.timeframe, direction=cls._direction(zone),
            zone_low=low, zone_high=high,
            confirmation_time=zone.confirmation_time,
            raw_midpoint=midpoint,
        )

    @staticmethod
    def _rank(
        candidate: FrozenEntryZoneCandidate, direction: StructuralRegime,
    ) -> tuple:
        type_rank = 0 if candidate.zone_type == EntryZoneType.IFVG else 1
        directional_depth = (
            candidate.raw_midpoint
            if direction == StructuralRegime.BULLISH
            else -candidate.raw_midpoint
        )
        return (
            type_rank,
            -candidate.confirmation_time,
            directional_depth,
            candidate.zone_id,
        )

    def _normalize_eq(self, raw: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            ticks = (raw / self.minimum_tick).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP,
            )
            return ticks * self.minimum_tick

    @staticmethod
    def _validate_setup(setup: Setup) -> None:
        if not setup.entry_zone_selection_eligible:
            raise ValueError("#28 requires #27 entry-zone-selection eligibility.")
        if setup.model == SetupModel.CONTINUATION:
            if setup.state != ContinuationSetupState.CANDIDATE:
                raise ValueError("#28 continuation consumes CANDIDATE, not ARMED.")
        elif setup.model == SetupModel.REVERSAL_1:
            if setup.state != ReversalSetupState.MSS_CONFIRMED:
                raise ValueError("#28 reversal consumes MSS_CONFIRMED, not ENTRY_ZONE_ARMED.")
        else:
            raise ValueError("Unsupported canonical setup model.")

    @staticmethod
    def _selection_id(
        *, setup: Setup, frozen: tuple[FrozenEntryZoneCandidate, ...],
        invalidated_ids: tuple[str, ...], selection_time: int,
    ) -> str:
        candidates = ":".join(candidate.zone_id for candidate in frozen)
        invalidated = ":".join(invalidated_ids)
        key = (
            f"trading-brain:#28:{setup.id}:{setup.qualification_time}:"
            f"{candidates}:{invalidated}:{selection_time}"
        )
        return str(uuid5(NAMESPACE_URL, key))

    def _record(
        self, *, setup: Setup,
        frozen: tuple[FrozenEntryZoneCandidate, ...],
        invalidated_ids: tuple[str, ...], selection_time: int,
        previous_selection_id: str | None = None,
        exhausted_by_invalidation: bool = False,
    ) -> EntryZoneSelection:
        available = [
            candidate for candidate in frozen
            if candidate.zone_id not in set(invalidated_ids)
        ]
        selected = min(
            available,
            key=lambda candidate: self._rank(candidate, setup.direction),
            default=None,
        )
        if selected is None:
            state = (
                EntryZoneSelectionState.INVALIDATED
                if exhausted_by_invalidation else EntryZoneSelectionState.NO_ELIGIBLE_ZONE
            )
            return EntryZoneSelection(
                id=self._selection_id(
                    setup=setup, frozen=frozen,
                    invalidated_ids=invalidated_ids,
                    selection_time=selection_time,
                ),
                setup_id=setup.id, setup_candidate_id=setup.setup_candidate_id,
                model=setup.model, direction=setup.direction, state=state,
                eligibility_time=setup.qualification_time,
                candidate_set_frozen_time=setup.qualification_time,
                frozen_candidates=frozen,
                selected_zone_id=None, selected_zone_type=None,
                zone_low=None, zone_high=None, eq_raw=None, eq_normalized=None,
                minimum_tick=self.minimum_tick,
                invalidated_zone_ids=invalidated_ids,
                previous_selection_id=previous_selection_id,
                selection_time=None,
                invalidation_time=selection_time if exhausted_by_invalidation else None,
            )
        raw = selected.raw_midpoint
        return EntryZoneSelection(
            id=self._selection_id(
                setup=setup, frozen=frozen,
                invalidated_ids=invalidated_ids,
                selection_time=selection_time,
            ),
            setup_id=setup.id, setup_candidate_id=setup.setup_candidate_id,
            model=setup.model, direction=setup.direction,
            state=EntryZoneSelectionState.SELECTED,
            eligibility_time=setup.qualification_time,
            candidate_set_frozen_time=setup.qualification_time,
            frozen_candidates=frozen,
            selected_zone_id=selected.zone_id,
            selected_zone_type=selected.zone_type,
            zone_low=selected.zone_low, zone_high=selected.zone_high,
            eq_raw=raw, eq_normalized=self._normalize_eq(raw),
            minimum_tick=self.minimum_tick,
            invalidated_zone_ids=invalidated_ids,
            previous_selection_id=previous_selection_id,
            selection_time=selection_time,
            invalidation_time=None,
        )

    def select(
        self, *, setup: Setup, candidates: tuple[FVG | IFVG, ...],
        selection_time: int, cisd_process: CISDProcess | None = None,
    ) -> EntryZoneSelection:
        self._validate_setup(setup)
        if selection_time < setup.qualification_time:
            raise ValueError("Selection cannot precede the canonical eligibility timestamp.")
        ids = [zone.id for zone in candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate entry-zone candidate identity.")

        eligible: list[FrozenEntryZoneCandidate] = []
        for zone in candidates:
            snapshot = self._snapshot(zone)
            if (
                not self._active(zone)
                or snapshot.direction != setup.direction
                or snapshot.confirmation_time > setup.qualification_time
            ):
                continue
            if setup.model == SetupModel.CONTINUATION:
                if snapshot.timeframe.lower() != "5m":
                    continue
                if snapshot.zone_id not in set(setup.eligible_zone_ids):
                    continue
            else:
                if cisd_process is None:
                    raise ValueError("Reversal #1 selection requires its #11 CISD process.")
                if setup.cisd_confirmation_id != getattr(cisd_process.confirmation, "id", None):
                    raise ValueError("Reversal setup and CISD confirmation identity do not match.")
                if not CISDEngine.zone_is_temporally_eligible(
                    process=cisd_process, zone=zone,
                ):
                    continue
            eligible.append(snapshot)

        frozen = tuple(sorted(
            eligible,
            key=lambda candidate: self._rank(candidate, setup.direction),
        ))
        return self._record(
            setup=setup, frozen=frozen, invalidated_ids=(),
            selection_time=selection_time,
        )

    def invalidate_and_fallback(
        self, *, setup: Setup, selection: EntryZoneSelection,
        invalidated_zone_id: str, invalidation_time: int,
    ) -> EntryZoneSelection:
        self._validate_setup(setup)
        if selection.setup_id != setup.id:
            raise ValueError("Selection does not belong to the supplied setup.")
        if selection.state != EntryZoneSelectionState.SELECTED:
            raise ValueError("Only an active selected zone can be invalidated.")
        if invalidated_zone_id != selection.selected_zone_id:
            raise ValueError("Only the currently selected zone may trigger fallback.")
        if invalidation_time < (selection.selection_time or selection.eligibility_time):
            raise ValueError("Zone invalidation cannot precede selection.")
        invalidated = tuple(sorted(set(
            selection.invalidated_zone_ids + (invalidated_zone_id,)
        )))
        return self._record(
            setup=setup, frozen=selection.frozen_candidates,
            invalidated_ids=invalidated,
            selection_time=invalidation_time,
            previous_selection_id=selection.id,
            exhausted_by_invalidation=True,
        )
