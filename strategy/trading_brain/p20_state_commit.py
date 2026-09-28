from __future__ import annotations

from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p16_conflict_resolution import (
    CandidateEvent, StructuralResolutionDecision,
)
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralClassification, StructuralEventType, StructuralRegime,
    StructuralStateSnapshot, StructuralSwing,
)


class StructuralStateCommitter:
    """#20 Phase C: apply only the accepted #16 structural decision."""

    @staticmethod
    def _state_id(state: StructuralStateSnapshot,
                  decision: StructuralResolutionDecision) -> str:
        return str(uuid5(
            NAMESPACE_URL,
            f"trading-brain:#20-state:{state.id}:{decision.id}:{decision.processing_timestamp}",
        ))

    @staticmethod
    def _protected_version(swing: StructuralSwing, *, state_id: str) -> StructuralSwing:
        return replace(
            swing,
            id=str(uuid5(NAMESPACE_URL, f"trading-brain:#20-protected:{swing.id}:{state_id}")),
            protected=True,
            regime_ref=state_id,
        )

    @staticmethod
    def _validate_candidate_protection(state: StructuralStateSnapshot) -> None:
        low = state.candidate_protected_low
        if low is not None:
            if low.timeframe != state.timeframe or low.type != MechanicalSwingType.L:
                raise ValueError("Candidate protected low must be a same-timeframe structural low.")
            if low.classification != StructuralClassification.HL:
                raise ValueError("Bullish candidate protection must be classified HL.")
        high = state.candidate_protected_high
        if high is not None:
            if high.timeframe != state.timeframe or high.type != MechanicalSwingType.H:
                raise ValueError("Candidate protected high must be a same-timeframe structural high.")
            if high.classification != StructuralClassification.LH:
                raise ValueError("Bearish candidate protection must be classified LH.")

    @staticmethod
    def _accepted(decision: StructuralResolutionDecision) -> CandidateEvent | None:
        accepted = decision.accepted_events
        if len(accepted) > 1:
            raise ValueError("A structural commit requires at most one primary accepted event.")
        if not accepted:
            if decision.primary_structural_event_id is not None:
                raise ValueError("Primary event cannot exist without an accepted event.")
            return None
        if decision.primary_structural_event_id != accepted[0].id:
            raise ValueError("Accepted event must match the primary structural event.")
        return accepted[0]

    def commit(self, *, state_before: StructuralStateSnapshot,
               decision: StructuralResolutionDecision) -> StructuralStateSnapshot:
        if decision.pre_state_id != state_before.id:
            raise ValueError("Decision does not belong to the supplied frozen pre-state.")
        if decision.timeframe != state_before.timeframe:
            raise ValueError("Structural commit is timeframe-isolated.")
        self._validate_candidate_protection(state_before)
        accepted = self._accepted(decision)
        state_id = self._state_id(state_before, decision)

        common = dict(
            id=state_id,
            timeframe=state_before.timeframe,
            governing_high=state_before.governing_high,
            governing_low=state_before.governing_low,
            predecessor_state_id=state_before.id,
            as_of_timestamp=decision.processing_timestamp,
        )

        if accepted is None:
            return StructuralStateSnapshot(
                regime=state_before.regime,
                protected_high=state_before.protected_high,
                protected_low=state_before.protected_low,
                candidate_protected_high=state_before.candidate_protected_high,
                candidate_protected_low=state_before.candidate_protected_low,
                **common,
            )

        event = accepted.source_candidate
        if event.state_before_id != state_before.id:
            raise ValueError("Accepted event was not qualified against this pre-state.")

        if event.event_type == StructuralEventType.MSS:
            return StructuralStateSnapshot(
                regime=StructuralRegime.TRANSITION,
                protected_high=None, protected_low=None,
                candidate_protected_high=None, candidate_protected_low=None,
                **common,
            )

        if event.event_type != StructuralEventType.BOS:
            raise ValueError("Unsupported accepted structural event.")

        if event.direction == StructuralRegime.BULLISH:
            source = (
                state_before.governing_low
                if state_before.regime == StructuralRegime.INITIALIZING
                else state_before.candidate_protected_low
            )
            protected_low = (
                self._protected_version(source, state_id=state_id)
                if source is not None else state_before.protected_low
            )
            return StructuralStateSnapshot(
                regime=StructuralRegime.BULLISH,
                protected_high=None,
                protected_low=protected_low,
                candidate_protected_high=None,
                candidate_protected_low=None,
                **common,
            )

        if event.direction == StructuralRegime.BEARISH:
            source = (
                state_before.governing_high
                if state_before.regime == StructuralRegime.INITIALIZING
                else state_before.candidate_protected_high
            )
            protected_high = (
                self._protected_version(source, state_id=state_id)
                if source is not None else state_before.protected_high
            )
            return StructuralStateSnapshot(
                regime=StructuralRegime.BEARISH,
                protected_high=protected_high,
                protected_low=None,
                candidate_protected_high=None,
                candidate_protected_low=None,
                **common,
            )

        raise ValueError("BOS direction must be BULLISH or BEARISH.")
