from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256

from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralRegime, StructuralStateSnapshot, StructuralSwing,
)
from strategy.trading_brain.p20_structural_state_producer import StructuralIngestionLedger
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p23_liquidity import (
    LiquidityInteractionResult, LiquidityReference, LiquiditySide,
    LiquidityState,
)


class ReferenceTransitionKind(str, Enum):
    ACTIVATED = "ACTIVATED"
    HISTORICAL = "HISTORICAL"
    CONSUMED = "CONSUMED"


@dataclass(frozen=True)
class StructuralLiquidityReferenceFact:
    id: str
    reference: LiquidityReference
    source_mechanical_swing_id: str
    source_structural_swing_id: str
    structural_state_id: str
    accepted_structural_event_id: str
    active_range_id: str
    symbol: str
    timeframe: str
    side: LiquiditySide
    occurrence_time: int
    available_at: datetime
    dataset_id: str
    run_id: str
    source_version: str
    calculation_version: str
    active: bool
    historical: bool
    consumed: bool
    transition_reason: str | None = None
    predecessor_fact_id: str | None = None


@dataclass(frozen=True)
class StructuralLiquidityReferenceTransition:
    id: str
    reference_id: str
    from_fact_id: str | None
    to_fact_id: str
    kind: ReferenceTransitionKind
    transition_time: datetime
    reason: str


@dataclass(frozen=True)
class StructuralLiquidityReferenceLedger:
    facts: tuple[StructuralLiquidityReferenceFact, ...] = ()
    transitions: tuple[StructuralLiquidityReferenceTransition, ...] = ()

    @property
    def active_references(self) -> tuple[LiquidityReference, ...]:
        latest: dict[str, StructuralLiquidityReferenceFact] = {}
        for fact in self.facts:
            latest[fact.reference.id] = fact
        return tuple(
            latest[key].reference for key in sorted(latest)
            if latest[key].active and not latest[key].historical and not latest[key].consumed
        )


def _hash(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC timezone-aware.")
    return value.astimezone(timezone.utc)


def _milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = value - epoch
    return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000


class StructuralLiquidityReferenceProducer:
    """#23 input producer for active #20/#21 structural boundaries only."""

    @staticmethod
    def _boundaries(state: StructuralStateSnapshot) -> tuple[StructuralSwing, StructuralSwing]:
        if state.regime == StructuralRegime.BULLISH:
            high, low = state.governing_high, state.protected_low
        elif state.regime == StructuralRegime.BEARISH:
            high, low = state.protected_high, state.governing_low
        else:
            raise ValueError("Directional accepted structural state is required.")
        if high is None or low is None:
            raise ValueError("Both active governing/protected boundaries are required.")
        return high, low

    @staticmethod
    def _latest(ledger: StructuralLiquidityReferenceLedger) -> dict[str, StructuralLiquidityReferenceFact]:
        result: dict[str, StructuralLiquidityReferenceFact] = {}
        for fact in ledger.facts:
            result[fact.reference.id] = fact
        return result

    @staticmethod
    def _transition(
        *, prior: StructuralLiquidityReferenceFact,
        kind: ReferenceTransitionKind, when: datetime, reason: str,
    ) -> tuple[StructuralLiquidityReferenceFact, StructuralLiquidityReferenceTransition]:
        consumed = kind == ReferenceTransitionKind.CONSUMED
        fact_id = _hash((prior.id, kind.value, _utc(when, "transition_time").isoformat(), reason))
        fact = StructuralLiquidityReferenceFact(
            **{**prior.__dict__, "id": fact_id, "active": False,
               "historical": True, "consumed": consumed or prior.consumed,
               "transition_reason": reason, "predecessor_fact_id": prior.id}
        )
        transition = StructuralLiquidityReferenceTransition(
            _hash(("#23-reference-transition-v1", prior.reference.id, prior.id,
                   fact.id, kind.value, reason)), prior.reference.id, prior.id,
            fact.id, kind, when, reason,
        )
        return fact, transition

    def derive(
        self, *, structural_ledger: StructuralIngestionLedger,
        state_after: StructuralStateSnapshot,
        accepted_structural_event_id: str,
        active_range: StructuralRange,
        symbol: str, dataset_id: str, run_id: str,
        source_version: str, calculation_version: str,
        evaluation_time: datetime,
        ledger: StructuralLiquidityReferenceLedger | None = None,
    ) -> StructuralLiquidityReferenceLedger:
        ledger = ledger or StructuralLiquidityReferenceLedger()
        evaluation_time = _utc(evaluation_time, "evaluation_time")
        if not all(isinstance(value, str) and value.strip() for value in (
            accepted_structural_event_id, symbol, dataset_id, run_id,
            source_version, calculation_version,
        )):
            raise ValueError("Complete structural-reference lineage is required.")
        if (structural_ledger.symbol, structural_ledger.timeframe,
            structural_ledger.source_version, structural_ledger.calculation_version) != (
                symbol, state_after.timeframe, source_version, calculation_version):
            raise ValueError("#19/#20 symbol/timeframe/version lineage mismatch.")
        if (
            structural_ledger.current_snapshot is None
            or state_after.predecessor_state_id != structural_ledger.current_snapshot.id
        ):
            raise ValueError("Accepted #20 state must descend from the supplied ingestion ledger.")
        if not active_range.active or active_range.historical:
            raise ValueError("An active #21 dealing range is required.")
        if (
            active_range.timeframe != state_after.timeframe
            or active_range.regime != state_after.regime
            or active_range.created_by_event_id != accepted_structural_event_id
            or state_after.as_of_timestamp is None
            or active_range.confirmation_time != state_after.as_of_timestamp
        ):
            raise ValueError("#20 state/event and #21 range identities mismatch.")
        high, low = self._boundaries(state_after)
        if (
            active_range.defining_high_swing_id != high.id
            or active_range.defining_low_swing_id != low.id
            or active_range.defining_high_price != high.price
            or active_range.defining_low_price != low.price
            or active_range.upper_boundary != high.price
            or active_range.lower_boundary != low.price
        ):
            raise ValueError("Active structural boundaries do not exactly define the #21 range.")

        availability = {
            fact.source_swing.id: fact for fact in structural_ledger.availability_facts
        }
        latest = self._latest(ledger)
        desired_ids: set[str] = set()
        facts = list(ledger.facts)
        transitions = list(ledger.transitions)
        for structural, side in ((high, LiquiditySide.BSL), (low, LiquiditySide.LSL)):
            if structural.type != (
                MechanicalSwingType.H if side == LiquiditySide.BSL else MechanicalSwingType.L
            ):
                raise ValueError("Structural boundary side/type mismatch.")
            source = availability.get(structural.mechanical_swing_id)
            if source is None or source.available_at > evaluation_time:
                raise ValueError("Replay-safe #19 source availability is required.")
            reference_id = _hash((
                "#23-structural-reference-v1", structural.mechanical_swing_id,
                state_after.id, accepted_structural_event_id, active_range.id,
                symbol, state_after.timeframe, side.value, source_version,
                calculation_version,
            ))
            desired_ids.add(reference_id)
            prior = latest.get(reference_id)
            if prior is not None:
                # Historical/consumed references never reactivate.
                continue
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            range_available = epoch + timedelta(milliseconds=active_range.confirmation_time)
            available_at = max(source.available_at, range_available)
            if available_at > evaluation_time:
                raise ValueError("Structural range is not yet available at evaluation time.")
            reference = LiquidityReference(
                reference_id, state_after.timeframe, side, structural.price,
                _milliseconds(available_at), "STRUCTURAL_SWING", True,
            )
            fact_id = _hash(("#23-structural-reference-fact-v1", reference_id,
                             structural.id, _stamp(available_at)))
            fact = StructuralLiquidityReferenceFact(
                fact_id, reference, structural.mechanical_swing_id, structural.id,
                state_after.id, accepted_structural_event_id, active_range.id,
                symbol, state_after.timeframe, side, structural.pivot_time,
                available_at, dataset_id, run_id, source_version,
                calculation_version, True, False, False,
            )
            transition = StructuralLiquidityReferenceTransition(
                _hash(("#23-reference-transition-v1", reference_id, fact.id,
                       ReferenceTransitionKind.ACTIVATED.value)),
                reference_id, None, fact.id, ReferenceTransitionKind.ACTIVATED,
                available_at, "ACTIVE_CONFIRMED_STRUCTURAL_RANGE_BOUNDARY",
            )
            facts.append(fact); transitions.append(transition); latest[reference_id] = fact

        # A previously historicized or consumed exact context is terminal.  In
        # particular, replaying that stale context must not historicize a newer
        # active boundary pair as a side effect.
        if any(
            reference_id in self._latest(ledger)
            and not self._latest(ledger)[reference_id].active
            for reference_id in desired_ids
        ):
            raise ValueError("Historical structural reference context cannot reactivate.")

        # Replacement prospectively historicizes every active reference in the
        # same symbol/timeframe that is not part of the new exact boundary pair.
        for reference_id, prior in tuple(latest.items()):
            if (
                prior.symbol == symbol and prior.timeframe == state_after.timeframe
                and prior.active and reference_id not in desired_ids
            ):
                historical, transition = self._transition(
                    prior=prior, kind=ReferenceTransitionKind.HISTORICAL,
                    when=evaluation_time, reason="STRUCTURAL_RANGE_REPLACED",
                )
                facts.append(historical); transitions.append(transition)
                latest[reference_id] = historical
        result = StructuralLiquidityReferenceLedger(tuple(facts), tuple(transitions))
        return ledger if result == ledger else result

    def consume(
        self, *, reference_id: str,
        interaction: LiquidityInteractionResult,
        consumption_time: datetime,
        ledger: StructuralLiquidityReferenceLedger,
    ) -> StructuralLiquidityReferenceLedger:
        consumption_time = _utc(consumption_time, "consumption_time")
        latest = self._latest(ledger)
        prior = latest.get(reference_id)
        if prior is None:
            raise ValueError("Reference is absent from the structural-reference ledger.")
        if not prior.active:
            return ledger
        if (
            interaction.event is None
            or interaction.pool.state != LiquidityState.CONSUMED
            or interaction.event.final_state != LiquidityState.CONSUMED
            or reference_id not in interaction.pool.component_reference_ids
        ):
            return ledger
        historical, transition = self._transition(
            prior=prior, kind=ReferenceTransitionKind.CONSUMED,
            when=consumption_time, reason=f"POOL_{interaction.event.outcome.value}",
        )
        return StructuralLiquidityReferenceLedger(
            ledger.facts + (historical,), ledger.transitions + (transition,),
        )


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
