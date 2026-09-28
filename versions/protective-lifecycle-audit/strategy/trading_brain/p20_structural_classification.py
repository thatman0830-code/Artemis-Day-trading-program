from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p19_mechanical_swings import (
    MechanicalSwing, MechanicalSwingEngine, MechanicalSwingType,
)


class StructuralClassification(str, Enum):
    HH = "HH"
    LH = "LH"
    HL = "HL"
    LL = "LL"
    EQUAL_HIGH = "EQUAL_HIGH"
    EQUAL_LOW = "EQUAL_LOW"
    UNCLASSIFIED = "UNCLASSIFIED"


class StructuralRegime(str, Enum):
    INITIALIZING = "INITIALIZING"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    TRANSITION = "TRANSITION"


class StructuralEventType(str, Enum):
    BOS = "BOS"
    MSS = "MSS"


@dataclass(frozen=True)
class StructuralSwing:
    id: str
    mechanical_swing_id: str
    timeframe: str
    type: MechanicalSwingType
    classification: StructuralClassification
    price: Decimal
    pivot_time: int
    protected: bool
    regime_ref: str | None


@dataclass(frozen=True)
class StructuralSelectionResult:
    timeframe: str
    swings: tuple[StructuralSwing, ...]
    regime: StructuralRegime = StructuralRegime.INITIALIZING

    @property
    def highs(self) -> tuple[StructuralSwing, ...]:
        return tuple(s for s in self.swings if s.type == MechanicalSwingType.H)

    @property
    def lows(self) -> tuple[StructuralSwing, ...]:
        return tuple(s for s in self.swings if s.type == MechanicalSwingType.L)


@dataclass(frozen=True)
class StructuralStateSnapshot:
    id: str
    timeframe: str
    regime: StructuralRegime
    governing_high: StructuralSwing | None
    governing_low: StructuralSwing | None
    protected_high: StructuralSwing | None = None
    protected_low: StructuralSwing | None = None
    candidate_protected_high: StructuralSwing | None = None
    candidate_protected_low: StructuralSwing | None = None
    predecessor_state_id: str | None = None
    as_of_timestamp: int | None = None


@dataclass(frozen=True)
class StructuralBreakCandidate:
    id: str
    timeframe: str
    processing_timestamp: int
    event_type: StructuralEventType
    direction: StructuralRegime
    reference_swing_id: str
    reference_price: Decimal
    close_price: Decimal
    qualifying_displacement: bool
    qualified: bool
    state_before_id: str


class StructuralSwingSelector:
    """#20 Phase A: structural promotion and same-type classification only.

    This class does not qualify BOS/MSS, arbitrate candidates, transfer
    protection, construct ranges, or infer a directional persisted regime.
    """

    @staticmethod
    def _validate(swings: tuple[MechanicalSwing, ...]) -> str:
        if not swings:
            raise ValueError("At least one confirmed mechanical swing is required.")
        timeframe = swings[0].timeframe
        if any(not swing.confirmed for swing in swings):
            raise ValueError("#20 consumes confirmed #19 swings only.")
        if any(swing.timeframe != timeframe for swing in swings):
            raise ValueError("Structural classification is timeframe-isolated.")
        ids = [swing.id for swing in swings]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate mechanical swing identity.")
        return timeframe

    @staticmethod
    def _more_extreme(candidate: MechanicalSwing, current: MechanicalSwing) -> bool:
        if candidate.type == MechanicalSwingType.H:
            return candidate.price > current.price
        return candidate.price < current.price

    @classmethod
    def _survivors(cls, swings: tuple[MechanicalSwing, ...]) -> tuple[MechanicalSwing, ...]:
        ordered = sorted(swings, key=lambda s: (s.pivot_time, s.type.value, s.id))
        survivors: list[MechanicalSwing] = []
        current: MechanicalSwing | None = None

        for swing in ordered:
            if current is None:
                current = swing
                continue
            if swing.type == current.type:
                # Exact-price tie keeps the chronological first-confirmed identity.
                if cls._more_extreme(swing, current):
                    current = swing
                continue
            survivors.append(current)
            current = swing

        if current is not None:
            survivors.append(current)
        return tuple(survivors)

    @staticmethod
    def _classification(
        swing: MechanicalSwing, previous_same_type: StructuralSwing | None
    ) -> StructuralClassification:
        if previous_same_type is None:
            return StructuralClassification.UNCLASSIFIED
        if swing.type == MechanicalSwingType.H:
            if swing.price > previous_same_type.price:
                return StructuralClassification.HH
            if swing.price < previous_same_type.price:
                return StructuralClassification.LH
            return StructuralClassification.EQUAL_HIGH
        if swing.price > previous_same_type.price:
            return StructuralClassification.HL
        if swing.price < previous_same_type.price:
            return StructuralClassification.LL
        return StructuralClassification.EQUAL_LOW

    @staticmethod
    def _id(swing: MechanicalSwing) -> str:
        return str(uuid5(NAMESPACE_URL, f"trading-brain:#20:{swing.id}"))

    def select(self, *, swings: tuple[MechanicalSwing, ...]) -> StructuralSelectionResult:
        timeframe = self._validate(swings)
        survivors = self._survivors(swings)
        previous: dict[MechanicalSwingType, StructuralSwing] = {}
        structural: list[StructuralSwing] = []

        for swing in survivors:
            record = StructuralSwing(
                id=self._id(swing),
                mechanical_swing_id=swing.id,
                timeframe=timeframe,
                type=swing.type,
                classification=self._classification(swing, previous.get(swing.type)),
                price=swing.price,
                pivot_time=swing.pivot_time,
                protected=False,
                regime_ref=None,
            )
            structural.append(record)
            previous[swing.type] = record

        # Baseline formation is valid, but Amendment 006 forbids directional
        # regime creation before an accepted body-close structural event.
        return StructuralSelectionResult(
            timeframe=timeframe,
            swings=tuple(structural),
            regime=StructuralRegime.INITIALIZING,
        )


class StructuralBreakQualifier:
    """#20 Phase B candidate qualification against frozen StateBefore(t).

    The returned facts are unresolved candidates. This class never accepts,
    suppresses, commits, or mutates structural state; #16 owns arbitration.
    """

    @staticmethod
    def _validate_state(state: StructuralStateSnapshot) -> None:
        references = (
            state.governing_high, state.governing_low,
            state.protected_high, state.protected_low,
        )
        if any(ref is not None and ref.timeframe != state.timeframe for ref in references):
            raise ValueError("Structural state references must share one timeframe.")
        if state.governing_high is not None and state.governing_high.type != MechanicalSwingType.H:
            raise ValueError("governing_high must reference a structural high.")
        if state.governing_low is not None and state.governing_low.type != MechanicalSwingType.L:
            raise ValueError("governing_low must reference a structural low.")
        if state.protected_high is not None and state.protected_high.type != MechanicalSwingType.H:
            raise ValueError("protected_high must reference a structural high.")
        if state.protected_low is not None and state.protected_low.type != MechanicalSwingType.L:
            raise ValueError("protected_low must reference a structural low.")

    @staticmethod
    def _candidate(
        *, state: StructuralStateSnapshot, timestamp: int,
        event_type: StructuralEventType, direction: StructuralRegime,
        reference: StructuralSwing, close: Decimal,
    ) -> StructuralBreakCandidate:
        key = (
            f"trading-brain:#20:{state.id}:{timestamp}:{event_type.value}:"
            f"{direction.value}:{reference.id}"
        )
        return StructuralBreakCandidate(
            id=str(uuid5(NAMESPACE_URL, key)),
            timeframe=state.timeframe,
            processing_timestamp=timestamp,
            event_type=event_type,
            direction=direction,
            reference_swing_id=reference.id,
            reference_price=reference.price,
            close_price=close,
            qualifying_displacement=True,
            qualified=True,
            state_before_id=state.id,
        )

    def qualify(
        self, *, state_before: StructuralStateSnapshot,
        candle: dict, qualifying_displacement: object,
    ) -> tuple[StructuralBreakCandidate, ...]:
        self._validate_state(state_before)
        missing = {"t", "h", "l", "c"} - set(candle)
        if missing:
            raise ValueError(f"Missing candle fields: {sorted(missing)}")
        if candle.get("is_closed") is not True:
            raise ValueError("Structural break qualification requires a closed candle.")

        timestamp = int(candle["t"])
        close = MechanicalSwingEngine._decimal(candle["c"], column="c")
        high = MechanicalSwingEngine._decimal(candle["h"], column="h")
        low = MechanicalSwingEngine._decimal(candle["l"], column="l")
        if high < low or close > high or close < low:
            raise ValueError("Invalid closed-candle OHLC geometry.")
        displacement_direction = None
        displacement_candidate_id = None
        if isinstance(qualifying_displacement, bool):
            displacement_qualified = qualifying_displacement
        else:
            displacement_qualified = bool(
                getattr(qualifying_displacement, "qualified", False)
                and getattr(qualifying_displacement, "active", False)
                and getattr(getattr(qualifying_displacement, "outcome", None), "value", None)
                == "QUALIFIED"
            )
            if (
                getattr(qualifying_displacement, "structural_snapshot_id", None) != state_before.id
                or getattr(qualifying_displacement, "timeframe", None) != state_before.timeframe
                or getattr(qualifying_displacement, "evaluation_candle_id", None) != candle.get("id")
            ):
                raise ValueError("Displacement qualification is incompatible with #20 inputs.")
            displacement_direction = getattr(qualifying_displacement, "direction", None)
            displacement_candidate_id = getattr(
                qualifying_displacement, "structural_candidate_id", None
            )
        if not displacement_qualified:
            return ()

        candidates: list[StructuralBreakCandidate] = []

        def above(reference: StructuralSwing | None) -> bool:
            return (
                reference is not None and close > reference.price
                and (displacement_direction is None or displacement_direction == StructuralRegime.BULLISH)
            )

        def below(reference: StructuralSwing | None) -> bool:
            return (
                reference is not None and close < reference.price
                and (displacement_direction is None or displacement_direction == StructuralRegime.BEARISH)
            )

        regime = state_before.regime
        if regime == StructuralRegime.INITIALIZING:
            if above(state_before.governing_high):
                candidates.append(self._candidate(
                    state=state_before, timestamp=timestamp,
                    event_type=StructuralEventType.BOS,
                    direction=StructuralRegime.BULLISH,
                    reference=state_before.governing_high, close=close,
                ))
            if below(state_before.governing_low):
                candidates.append(self._candidate(
                    state=state_before, timestamp=timestamp,
                    event_type=StructuralEventType.BOS,
                    direction=StructuralRegime.BEARISH,
                    reference=state_before.governing_low, close=close,
                ))
        elif regime == StructuralRegime.BULLISH:
            if above(state_before.governing_high):
                candidates.append(self._candidate(
                    state=state_before, timestamp=timestamp,
                    event_type=StructuralEventType.BOS,
                    direction=StructuralRegime.BULLISH,
                    reference=state_before.governing_high, close=close,
                ))
            if below(state_before.protected_low):
                candidates.append(self._candidate(
                    state=state_before, timestamp=timestamp,
                    event_type=StructuralEventType.MSS,
                    direction=StructuralRegime.BEARISH,
                    reference=state_before.protected_low, close=close,
                ))
        elif regime == StructuralRegime.BEARISH:
            if below(state_before.governing_low):
                candidates.append(self._candidate(
                    state=state_before, timestamp=timestamp,
                    event_type=StructuralEventType.BOS,
                    direction=StructuralRegime.BEARISH,
                    reference=state_before.governing_low, close=close,
                ))
            if above(state_before.protected_high):
                candidates.append(self._candidate(
                    state=state_before, timestamp=timestamp,
                    event_type=StructuralEventType.MSS,
                    direction=StructuralRegime.BULLISH,
                    reference=state_before.protected_high, close=close,
                ))

        result = tuple(candidates)
        if displacement_candidate_id is not None and result:
            if len(result) != 1 or result[0].id != displacement_candidate_id:
                raise ValueError("Displacement qualification targets a different structural candidate.")
        return result
