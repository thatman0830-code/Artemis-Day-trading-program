from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakCandidate, StructuralEventType, StructuralRegime,
    StructuralStateSnapshot,
)


class SuppressionReason(str, Enum):
    OPPOSING_MSS_STATE_PRIORITY = "OPPOSING_MSS_STATE_PRIORITY"


class ConflictType(str, Enum):
    NO_STRUCTURAL_CANDIDATE = "NO_STRUCTURAL_CANDIDATE"
    SINGLE_STRUCTURAL_CANDIDATE = "SINGLE_STRUCTURAL_CANDIDATE"
    OPPOSING_MSS_VS_SAME_DIRECTION_BOS = "OPPOSING_MSS_VS_SAME_DIRECTION_BOS"


class ResolutionRule(str, Enum):
    NO_ACTION = "NO_ACTION"
    PASS_THROUGH_SINGLE_CANDIDATE = "PASS_THROUGH_SINGLE_CANDIDATE"
    OPPOSING_MSS_OVER_SAME_DIRECTION_BOS = "OPPOSING_MSS_OVER_SAME_DIRECTION_BOS"


@dataclass(frozen=True)
class CandidateEvent:
    id: str
    source_candidate: StructuralBreakCandidate
    qualified_conditions: tuple[str, ...]
    accepted: bool
    suppression_reason: SuppressionReason | None
    suppressing_event_id: str | None


@dataclass(frozen=True)
class StructuralResolutionDecision:
    id: str
    timeframe: str
    processing_timestamp: int
    pre_state_id: str
    candidate_events: tuple[CandidateEvent, ...]
    primary_structural_event_id: str | None
    conflict_type: ConflictType
    resolution_rule: ResolutionRule

    @property
    def accepted_events(self) -> tuple[CandidateEvent, ...]:
        return tuple(event for event in self.candidate_events if event.accepted)

    @property
    def suppressed_events(self) -> tuple[CandidateEvent, ...]:
        return tuple(event for event in self.candidate_events if not event.accepted)


@dataclass(frozen=True)
class ConflictResolution:
    id: str
    timeframe: str
    processing_timestamp: int
    pre_state_id: str
    post_state_id: str
    candidate_event_ids: tuple[str, ...]
    accepted_event_ids: tuple[str, ...]
    suppressed_event_ids: tuple[str, ...]
    primary_structural_event_id: str | None
    conflict_type: ConflictType
    resolution_rule: ResolutionRule
    chronology_source: str
    chronology_resolution: str
    created_time: int
    immutable: bool = True


class ConflictResolver:
    """Canonical #16 arbitration only; never re-qualifies candidate facts."""

    @staticmethod
    def _event(candidate: StructuralBreakCandidate, *, accepted: bool,
               reason: SuppressionReason | None = None,
               suppressor: str | None = None) -> CandidateEvent:
        return CandidateEvent(
            id=candidate.id,
            source_candidate=candidate,
            qualified_conditions=(
                "CLOSED_CANDLE_BODY_CLOSE_STRICTLY_BEYOND_GOVERNING_REFERENCE",
                "QUALIFYING_DISPLACEMENT_ASSOCIATED",
                "EVALUATED_AGAINST_FROZEN_PRE_STATE",
            ),
            accepted=accepted,
            suppression_reason=reason,
            suppressing_event_id=suppressor,
        )

    @staticmethod
    def _validate(state: StructuralStateSnapshot,
                  candidates: tuple[StructuralBreakCandidate, ...]) -> int:
        ids = [candidate.id for candidate in candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate candidate identity is a data-integrity failure.")
        if not candidates:
            return 0
        timestamp = candidates[0].processing_timestamp
        for candidate in candidates:
            if not candidate.qualified:
                raise ValueError("#16 consumes qualified candidate facts only.")
            if candidate.timeframe != state.timeframe:
                raise ValueError("Conflict resolution is timeframe-isolated.")
            if candidate.processing_timestamp != timestamp:
                raise ValueError("One resolution cycle requires one processing timestamp.")
            if candidate.state_before_id != state.id:
                raise ValueError("Candidate was not evaluated against the supplied frozen pre-state.")
        return timestamp

    @staticmethod
    def _decision_id(state: StructuralStateSnapshot, timestamp: int,
                     candidates: tuple[StructuralBreakCandidate, ...]) -> str:
        ids = ":".join(sorted(candidate.id for candidate in candidates))
        return str(uuid5(NAMESPACE_URL, f"trading-brain:#16:{state.id}:{timestamp}:{ids}"))

    def resolve(self, *, state_before: StructuralStateSnapshot,
                candidates: tuple[StructuralBreakCandidate, ...],
                processing_timestamp: int | None = None) -> StructuralResolutionDecision:
        timestamp = self._validate(state_before, candidates)
        if not candidates:
            if processing_timestamp is None:
                raise ValueError("processing_timestamp is required when no candidates exist.")
            timestamp = int(processing_timestamp)
            return StructuralResolutionDecision(
                id=self._decision_id(state_before, timestamp, ()),
                timeframe=state_before.timeframe, processing_timestamp=timestamp,
                pre_state_id=state_before.id, candidate_events=(),
                primary_structural_event_id=None,
                conflict_type=ConflictType.NO_STRUCTURAL_CANDIDATE,
                resolution_rule=ResolutionRule.NO_ACTION,
            )

        if len(candidates) == 1:
            event = self._event(candidates[0], accepted=True)
            return StructuralResolutionDecision(
                id=self._decision_id(state_before, timestamp, candidates),
                timeframe=state_before.timeframe, processing_timestamp=timestamp,
                pre_state_id=state_before.id, candidate_events=(event,),
                primary_structural_event_id=event.id,
                conflict_type=ConflictType.SINGLE_STRUCTURAL_CANDIDATE,
                resolution_rule=ResolutionRule.PASS_THROUGH_SINGLE_CANDIDATE,
            )

        regime = state_before.regime
        if regime not in {StructuralRegime.BULLISH, StructuralRegime.BEARISH}:
            raise ValueError("Multiple structural candidates lack a canonical resolution in this pre-state.")
        same_direction = regime
        opposing = (
            StructuralRegime.BEARISH
            if regime == StructuralRegime.BULLISH else StructuralRegime.BULLISH
        )
        bos = [c for c in candidates if c.event_type == StructuralEventType.BOS and c.direction == same_direction]
        mss = [c for c in candidates if c.event_type == StructuralEventType.MSS and c.direction == opposing]
        if len(candidates) != 2 or len(bos) != 1 or len(mss) != 1:
            raise ValueError("Candidate collision is not covered by the canonical #16 priority rule.")

        accepted = self._event(mss[0], accepted=True)
        suppressed = self._event(
            bos[0], accepted=False,
            reason=SuppressionReason.OPPOSING_MSS_STATE_PRIORITY,
            suppressor=accepted.id,
        )
        events = tuple(sorted((accepted, suppressed), key=lambda event: event.id))
        return StructuralResolutionDecision(
            id=self._decision_id(state_before, timestamp, candidates),
            timeframe=state_before.timeframe, processing_timestamp=timestamp,
            pre_state_id=state_before.id, candidate_events=events,
            primary_structural_event_id=accepted.id,
            conflict_type=ConflictType.OPPOSING_MSS_VS_SAME_DIRECTION_BOS,
            resolution_rule=ResolutionRule.OPPOSING_MSS_OVER_SAME_DIRECTION_BOS,
        )

    @staticmethod
    def finalize(*, decision: StructuralResolutionDecision, post_state_id: str,
                 chronology_source: str, chronology_resolution: str,
                 created_time: int) -> ConflictResolution:
        if not post_state_id or not chronology_source or not chronology_resolution:
            raise ValueError("Final resolution requires post-state and chronology provenance.")
        accepted = tuple(event.id for event in decision.accepted_events)
        suppressed = tuple(event.id for event in decision.suppressed_events)
        return ConflictResolution(
            id=decision.id, timeframe=decision.timeframe,
            processing_timestamp=decision.processing_timestamp,
            pre_state_id=decision.pre_state_id, post_state_id=post_state_id,
            candidate_event_ids=tuple(event.id for event in decision.candidate_events),
            accepted_event_ids=accepted, suppressed_event_ids=suppressed,
            primary_structural_event_id=decision.primary_structural_event_id,
            conflict_type=decision.conflict_type, resolution_rule=decision.resolution_rule,
            chronology_source=chronology_source,
            chronology_resolution=chronology_resolution,
            created_time=int(created_time), immutable=True,
        )
