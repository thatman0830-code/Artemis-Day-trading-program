from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, uuid5


class FVGDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class FVGState(str, Enum):
    ACTIVE = "ACTIVE"
    MITIGATED = "MITIGATED"
    VIOLATED = "VIOLATED"
    INVERTED = "INVERTED"


@dataclass(frozen=True)
class FVG:
    id: str
    timeframe: str
    direction: FVGDirection
    candle1_id: str
    candle2_id: str
    candle3_id: str
    lower_boundary: Decimal
    upper_boundary: Decimal
    gap_size: Decimal
    creation_time: int
    confirmation_time: int
    displacement_qualified: bool
    state: FVGState = FVGState.ACTIVE
    deepest_penetration: Decimal = Decimal("0")
    fully_mitigated: bool = False
    converted_once: bool = False
    last_interaction_time: int | None = None
    conversion_time: int | None = None


@dataclass(frozen=True)
class IFVG:
    id: str
    source_fvg_id: str
    timeframe: str
    direction: FVGDirection
    lower_boundary: Decimal
    upper_boundary: Decimal
    creation_time: int
    confirmation_time: int
    state: FVGState = FVGState.INVERTED


@dataclass(frozen=True)
class FVGInteractionResult:
    fvg: FVG
    ifvg: IFVG | None = None


class FVGEngine:
    """Canonical #25 geometry and one-time FVG/IFVG lifecycle.

    This primitive records imbalance facts only. It does not select entry zones,
    determine confluence, alter LRL selection, or make setup/execution decisions.
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

    @classmethod
    def _candle(cls, candle: dict) -> tuple[int, Decimal, Decimal, Decimal]:
        missing = {"t", "h", "l", "c"} - set(candle)
        if missing:
            raise ValueError(f"Missing candle fields: {sorted(missing)}")
        if candle.get("is_closed") is not True:
            raise ValueError("#25 requires closed candles only.")
        try:
            timestamp = int(candle["t"])
        except (TypeError, ValueError) as error:
            raise ValueError("Candle timestamp must be an integer.") from error
        high = cls._decimal(candle["h"], field="h")
        low = cls._decimal(candle["l"], field="l")
        close = cls._decimal(candle["c"], field="c")
        if low <= 0 or high < low or not low <= close <= high:
            raise ValueError("Invalid closed-candle OHLC geometry.")
        return timestamp, high, low, close

    @staticmethod
    def _candle_id(candle: dict, *, timeframe: str, timestamp: int) -> str:
        supplied = candle.get("id")
        if supplied is not None:
            if not str(supplied).strip():
                raise ValueError("Candle id cannot be blank.")
            return str(supplied)
        return str(uuid5(NAMESPACE_URL, f"trading-brain:candle:{timeframe}:{timestamp}"))

    @staticmethod
    def _fvg_id(
        *, timeframe: str, direction: FVGDirection,
        candle1_id: str, candle2_id: str, candle3_id: str,
    ) -> str:
        key = (
            f"trading-brain:#25:FVG:{timeframe}:{direction.value}:"
            f"{candle1_id}:{candle2_id}:{candle3_id}"
        )
        return str(uuid5(NAMESPACE_URL, key))

    def detect(self, *, timeframe: str, candles: tuple[dict, ...]) -> tuple[FVG, ...]:
        if not timeframe.strip():
            raise ValueError("timeframe is required.")
        parsed = [self._candle(candle) for candle in candles]
        times = [record[0] for record in parsed]
        if len(times) != len(set(times)) or times != sorted(times):
            raise ValueError("Candle timestamps must be unique and increasing.")
        if len(candles) < 3:
            return ()

        found: list[FVG] = []
        for index in range(2, len(candles)):
            c1, c2, c3 = candles[index - 2:index + 1]
            t1, h1, l1, _ = parsed[index - 2]
            t2, _, _, _ = parsed[index - 1]
            t3, h3, l3, _ = parsed[index]
            ids = (
                self._candle_id(c1, timeframe=timeframe, timestamp=t1),
                self._candle_id(c2, timeframe=timeframe, timestamp=t2),
                self._candle_id(c3, timeframe=timeframe, timestamp=t3),
            )
            if len(set(ids)) != 3:
                raise ValueError("The three-candle FVG sequence requires unique candle identities.")

            direction: FVGDirection | None = None
            lower = upper = Decimal("0")
            if l3 > h1:
                direction = FVGDirection.BULLISH
                lower, upper = h1, l3
            elif h3 < l1:
                direction = FVGDirection.BEARISH
                lower, upper = h3, l1
            if direction is None or upper - lower < self.minimum_tick:
                continue

            found.append(FVG(
                id=self._fvg_id(
                    timeframe=timeframe, direction=direction,
                    candle1_id=ids[0], candle2_id=ids[1], candle3_id=ids[2],
                ),
                timeframe=timeframe, direction=direction,
                candle1_id=ids[0], candle2_id=ids[1], candle3_id=ids[2],
                lower_boundary=lower, upper_boundary=upper,
                gap_size=upper - lower, creation_time=t3, confirmation_time=t3,
                displacement_qualified=bool(c2.get("qualifying_displacement", False)),
            ))
        return tuple(found)

    @staticmethod
    def _ifvg(fvg: FVG, *, timestamp: int) -> IFVG:
        direction = (
            FVGDirection.BEARISH
            if fvg.direction == FVGDirection.BULLISH
            else FVGDirection.BULLISH
        )
        key = f"trading-brain:#25:IFVG:{fvg.id}:{direction.value}:{timestamp}"
        return IFVG(
            id=str(uuid5(NAMESPACE_URL, key)), source_fvg_id=fvg.id,
            timeframe=fvg.timeframe, direction=direction,
            lower_boundary=fvg.lower_boundary, upper_boundary=fvg.upper_boundary,
            creation_time=timestamp, confirmation_time=timestamp,
        )

    def interact(
        self, *, fvg: FVG, candle: dict, event_timeframe: str,
        qualifying_opposing_displacement: bool = False,
    ) -> FVGInteractionResult:
        if not event_timeframe.strip():
            raise ValueError("event_timeframe is required.")
        timestamp, high, low, close = self._candle(candle)
        if timestamp <= fvg.confirmation_time:
            # A just-confirmed FVG cannot be retroactively interacted with or
            # converted by its own Candle 3.
            return FVGInteractionResult(fvg)
        if fvg.converted_once or fvg.state == FVGState.INVERTED:
            return FVGInteractionResult(fvg)
        if fvg.lower_boundary <= 0 or fvg.upper_boundary <= fvg.lower_boundary:
            raise ValueError("Invalid immutable FVG geometry.")

        if fvg.direction == FVGDirection.BULLISH:
            penetration = max(
                Decimal("0"),
                min(fvg.gap_size, fvg.upper_boundary - low),
            )
            fully_mitigated = low <= fvg.lower_boundary
            violated = close < fvg.lower_boundary
        else:
            penetration = max(
                Decimal("0"),
                min(fvg.gap_size, high - fvg.lower_boundary),
            )
            fully_mitigated = high >= fvg.upper_boundary
            violated = close > fvg.upper_boundary

        deepest = max(fvg.deepest_penetration, penetration)
        interacted = penetration > 0 or fully_mitigated or violated
        state = fvg.state
        if fully_mitigated:
            state = FVGState.MITIGATED
        if violated:
            state = FVGState.VIOLATED

        if violated and qualifying_opposing_displacement:
            converted = replace(
                fvg, state=FVGState.INVERTED,
                deepest_penetration=deepest,
                fully_mitigated=True, converted_once=True,
                last_interaction_time=timestamp, conversion_time=timestamp,
            )
            return FVGInteractionResult(converted, self._ifvg(fvg, timestamp=timestamp))

        updated = replace(
            fvg, state=state, deepest_penetration=deepest,
            fully_mitigated=fvg.fully_mitigated or fully_mitigated,
            last_interaction_time=timestamp if interacted else fvg.last_interaction_time,
        )
        return FVGInteractionResult(updated)
