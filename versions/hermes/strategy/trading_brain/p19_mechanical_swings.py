from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

import pandas as pd


class MechanicalSwingType(str, Enum):
    H = "H"
    L = "L"


@dataclass(frozen=True)
class MechanicalSwing:
    id: str
    timeframe: str
    type: MechanicalSwingType
    price: Decimal
    pivot_time: int
    confirmed: bool


@dataclass(frozen=True)
class MechanicalSwingResult:
    timeframe: str
    swings: tuple[MechanicalSwing, ...]

    @property
    def highs(self) -> tuple[MechanicalSwing, ...]:
        return tuple(s for s in self.swings if s.type == MechanicalSwingType.H)

    @property
    def lows(self) -> tuple[MechanicalSwing, ...]:
        return tuple(s for s in self.swings if s.type == MechanicalSwingType.L)


class MechanicalSwingEngine:
    """Canonical #19 strict 2-left/2-right observation detector only."""

    LEFT_BARS = 2
    RIGHT_BARS = 2

    @staticmethod
    def _decimal(value: object, *, column: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"Candle column {column!r} must contain exact numbers.") from error
        if not result.is_finite():
            raise ValueError(f"Candle column {column!r} must contain finite numbers.")
        return result

    @classmethod
    def _validate(cls, *, timeframe: str, candles: pd.DataFrame) -> None:
        if not timeframe.strip():
            raise ValueError("timeframe is required.")
        missing = {"t", "h", "l"} - set(candles.columns)
        if missing:
            raise ValueError(f"Missing candle columns: {sorted(missing)}")
        if "is_closed" in candles.columns and not bool(candles["is_closed"].all()):
            raise ValueError("Mechanical swings require closed candles only.")

        timestamps = pd.to_numeric(candles["t"], errors="coerce")
        if timestamps.isna().any():
            raise ValueError("Candle timestamps must be numeric.")
        if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
            raise ValueError("Candle timestamps must be unique and increasing.")

        for _, candle in candles.iterrows():
            high = cls._decimal(candle["h"], column="h")
            low = cls._decimal(candle["l"], column="l")
            if high <= 0 or low <= 0:
                raise ValueError("Candle prices must be positive.")
            if high < low:
                raise ValueError("Candle high cannot be below candle low.")

    @staticmethod
    def _identity(*, timeframe: str, type_: MechanicalSwingType, pivot_time: int) -> str:
        key = f"trading-brain:#19:{timeframe}:{type_.value}:{pivot_time}"
        return str(uuid5(NAMESPACE_URL, key))

    @classmethod
    def _build(
        cls, *, timeframe: str, candles: pd.DataFrame,
        type_: MechanicalSwingType, index: int, price: Decimal,
    ) -> MechanicalSwing:
        pivot_time = int(candles.iloc[index]["t"])
        return MechanicalSwing(
            id=cls._identity(timeframe=timeframe, type_=type_, pivot_time=pivot_time),
            timeframe=timeframe,
            type=type_,
            price=price,
            pivot_time=pivot_time,
            confirmed=True,
        )

    def detect(self, *, timeframe: str, candles: pd.DataFrame) -> MechanicalSwingResult:
        self._validate(timeframe=timeframe, candles=candles)
        if len(candles) < self.LEFT_BARS + 1 + self.RIGHT_BARS:
            return MechanicalSwingResult(timeframe, ())

        highs = tuple(self._decimal(v, column="h") for v in candles["h"])
        lows = tuple(self._decimal(v, column="l") for v in candles["l"])
        swings: list[MechanicalSwing] = []

        for i in range(self.LEFT_BARS, len(candles) - self.RIGHT_BARS):
            neighbors_h = (highs[i - 2], highs[i - 1], highs[i + 1], highs[i + 2])
            if all(highs[i] > value for value in neighbors_h):
                swings.append(self._build(
                    timeframe=timeframe, candles=candles,
                    type_=MechanicalSwingType.H, index=i, price=highs[i],
                ))

            neighbors_l = (lows[i - 2], lows[i - 1], lows[i + 1], lows[i + 2])
            if all(lows[i] < value for value in neighbors_l):
                swings.append(self._build(
                    timeframe=timeframe, candles=candles,
                    type_=MechanicalSwingType.L, index=i, price=lows[i],
                ))

        swings.sort(key=lambda swing: (swing.pivot_time, swing.type.value))
        return MechanicalSwingResult(timeframe, tuple(swings))

