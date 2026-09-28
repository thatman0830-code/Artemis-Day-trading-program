from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd

from strategy.models import (
    AreaOfInterest,
    MarketStructure,
    MarketTrend,
)


class AOIType(str, Enum):
    SUPPORT = "SUPPORT"
    RESISTANCE = "RESISTANCE"
    DEMAND = "DEMAND"
    SUPPLY = "SUPPLY"
    UNKNOWN = "UNKNOWN"


class AOIStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    WAITING = "WAITING"


@dataclass(frozen=True)
class AOICandidate:
    lower_bound: float
    upper_bound: float

    touches: int

    timeframe: str

    aoi_type: AOIType

    status: AOIStatus

    reason: str

    midpoint: float

    width: float
    width_pct: float

    inside_structure_range: bool


class AOIEngine:
    """
    Deterministic Area-of-Interest engine.

    Responsibilities:
    - Validate candidate support/resistance zones
    - Count meaningful zone interactions
    - Enforce a minimum touch requirement
    - Reject zones that are too wide
    - Verify structural location
    - Convert validated zones into strategy AOIs

    This engine does NOT place trades.
    """

    def __init__(
        self,
        minimum_touches: int = 3,
        zone_tolerance_pct: float = 0.15,
        maximum_zone_width_pct: float = 1.0,
    ):
        if minimum_touches < 1:
            raise ValueError(
                "minimum_touches must be at least 1."
            )

        if zone_tolerance_pct <= 0:
            raise ValueError(
                "zone_tolerance_pct must be positive."
            )

        if maximum_zone_width_pct <= 0:
            raise ValueError(
                "maximum_zone_width_pct must be positive."
            )

        self.minimum_touches = minimum_touches

        self.zone_tolerance_pct = (
            zone_tolerance_pct
        )

        self.maximum_zone_width_pct = (
            maximum_zone_width_pct
        )

    # ==========================================================
    # VALIDATION
    # ==========================================================

    @staticmethod
    def _validate_candles(
        candles: pd.DataFrame,
    ) -> None:

        required = {
            "h",
            "l",
            "c",
        }

        missing = (
            required
            - set(candles.columns)
        )

        if missing:
            raise ValueError(
                f"Missing candle columns: {sorted(missing)}"
            )

        if candles.empty:
            raise ValueError(
                "Candle DataFrame is empty."
            )

    # ==========================================================
    # ZONE GEOMETRY
    # ==========================================================

    @staticmethod
    def _zone_midpoint(
        lower: float,
        upper: float,
    ) -> float:

        return (
            lower + upper
        ) / 2

    @staticmethod
    def _zone_width(
        lower: float,
        upper: float,
    ) -> float:

        return (
            upper - lower
        )

    @staticmethod
    def _zone_width_pct(
        lower: float,
        upper: float,
    ) -> float:

        midpoint = (
            lower + upper
        ) / 2

        if midpoint <= 0:
            return 0.0

        return (
            (upper - lower)
            / midpoint
            * 100
        )

    # ==========================================================
    # TOUCH COUNTING
    # ==========================================================

    def _count_touches(
        self,
        *,
        candles: pd.DataFrame,
        lower_bound: float,
        upper_bound: float,
    ) -> int:
        """
        Count distinct visits into the AOI.

        Consecutive candles inside the same zone
        count as one interaction rather than
        artificially inflating the touch count.
        """

        touches = 0

        inside_previous = False

        for _, row in candles.iterrows():

            candle_high = float(
                row["h"]
            )

            candle_low = float(
                row["l"]
            )

            intersects = (
                candle_high >= lower_bound
                and candle_low <= upper_bound
            )

            if (
                intersects
                and not inside_previous
            ):
                touches += 1

            inside_previous = intersects

        return touches

    # ==========================================================
    # STRUCTURAL LOCATION
    # ==========================================================

    @staticmethod
    def _inside_structure_range(
        *,
        structure: MarketStructure,
        lower_bound: float,
        upper_bound: float,
    ) -> bool:

        midpoint = (
            lower_bound + upper_bound
        ) / 2

        # --------------------------------------
        # Bullish structure:
        # valid AOI should exist between
        # higher low and higher high.
        # --------------------------------------

        if (
            structure.trend
            == MarketTrend.BULLISH
        ):

            if (
                structure.higher_low is None
                or structure.higher_high is None
            ):
                return False

            return (
                structure.higher_low
                <= midpoint
                <= structure.higher_high
            )

        # --------------------------------------
        # Bearish structure:
        # valid AOI should exist between
        # lower low and lower high.
        # --------------------------------------

        if (
            structure.trend
            == MarketTrend.BEARISH
        ):

            if (
                structure.lower_low is None
                or structure.lower_high is None
            ):
                return False

            return (
                structure.lower_low
                <= midpoint
                <= structure.lower_high
            )

        # --------------------------------------
        # Range / unknown fallback
        # --------------------------------------

        if (
            structure.swing_low is not None
            and structure.swing_high is not None
        ):

            return (
                structure.swing_low
                <= midpoint
                <= structure.swing_high
            )

        return False

    # ==========================================================
    # AOI TYPE
    # ==========================================================

    @staticmethod
    def _classify_aoi_type(
        *,
        structure: MarketStructure,
        midpoint: float,
    ) -> AOIType:

        if (
            structure.trend
            == MarketTrend.BULLISH
        ):
            return AOIType.DEMAND

        if (
            structure.trend
            == MarketTrend.BEARISH
        ):
            return AOIType.SUPPLY

        if (
            structure.swing_high is not None
            and midpoint
            >= structure.swing_high
        ):
            return AOIType.RESISTANCE

        if (
            structure.swing_low is not None
            and midpoint
            <= structure.swing_low
        ):
            return AOIType.SUPPORT

        return AOIType.UNKNOWN

    # ==========================================================
    # EVALUATE ONE ZONE
    # ==========================================================

    def evaluate_zone(
        self,
        *,
        candles: pd.DataFrame,
        structure: MarketStructure,
        timeframe: str,
        lower_bound: float,
        upper_bound: float,
    ) -> AOICandidate:

        self._validate_candles(
            candles
        )

        if lower_bound <= 0:
            raise ValueError(
                "AOI lower bound must be positive."
            )

        if upper_bound <= 0:
            raise ValueError(
                "AOI upper bound must be positive."
            )

        if upper_bound <= lower_bound:
            raise ValueError(
                "AOI upper bound must be above lower bound."
            )

        midpoint = (
            self._zone_midpoint(
                lower_bound,
                upper_bound,
            )
        )

        width = (
            self._zone_width(
                lower_bound,
                upper_bound,
            )
        )

        width_pct = (
            self._zone_width_pct(
                lower_bound,
                upper_bound,
            )
        )

        touches = (
            self._count_touches(
                candles=candles,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            )
        )

        inside_structure_range = (
            self._inside_structure_range(
                structure=structure,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            )
        )

        aoi_type = (
            self._classify_aoi_type(
                structure=structure,
                midpoint=midpoint,
            )
        )

        # --------------------------------------
        # Zone-width validation
        # --------------------------------------

        if (
            width_pct
            > self.maximum_zone_width_pct
        ):

            status = AOIStatus.INVALID

            reason = (
                "AOI zone is too wide."
            )

        # --------------------------------------
        # Three-touch validation
        # --------------------------------------

        elif (
            touches
            < self.minimum_touches
        ):

            status = AOIStatus.WAITING

            reason = (
                "AOI does not yet meet "
                "minimum touch requirement."
            )

        # --------------------------------------
        # Structural-location validation
        # --------------------------------------

        elif not inside_structure_range:

            status = AOIStatus.INVALID

            reason = (
                "AOI is outside valid "
                "market-structure range."
            )

        else:

            status = AOIStatus.VALID

            reason = (
                "AOI passed width, touch, "
                "and structure validation."
            )

        return AOICandidate(
            lower_bound=lower_bound,
            upper_bound=upper_bound,

            touches=touches,

            timeframe=timeframe,

            aoi_type=aoi_type,

            status=status,

            reason=reason,

            midpoint=midpoint,

            width=width,
            width_pct=width_pct,

            inside_structure_range=(
                inside_structure_range
            ),
        )

    # ==========================================================
    # CONVERT TO SHARED STRATEGY MODEL
    # ==========================================================

    @staticmethod
    def to_area_of_interest(
        candidate: AOICandidate,
    ) -> Optional[AreaOfInterest]:

        if (
            candidate.status
            != AOIStatus.VALID
        ):
            return None

        return AreaOfInterest(
            lower_bound=(
                candidate.lower_bound
            ),

            upper_bound=(
                candidate.upper_bound
            ),

            touches=(
                candidate.touches
            ),

            timeframe=(
                candidate.timeframe
            ),

            label=(
                candidate.aoi_type.value
            ),
        )


# ==============================================================
# SELF TEST
# ==============================================================


if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " AOI / THREE-TOUCH ENGINE TEST"
    )
    print(
        "======================================"
    )

    # ----------------------------------------------------------
    # Synthetic bullish structure
    # ----------------------------------------------------------

    structure = MarketStructure(
        symbol="BTC",
        timeframe="15m",

        trend=MarketTrend.BULLISH,

        current_price=108.0,

        swing_high=110.0,
        swing_low=100.0,

        higher_high=110.0,
        higher_low=100.0,
    )

    # ----------------------------------------------------------
    # Synthetic market interaction
    #
    # Price repeatedly revisits approximately
    # 101.8 - 102.8 three distinct times.
    # ----------------------------------------------------------

    candles = pd.DataFrame(
        {
            "h": [
                106.0,
                103.0,
                107.0,
                102.8,
                108.0,
                103.1,
                109.0,
                105.0,
                110.0,
            ],

            "l": [
                104.0,
                101.5,
                104.0,
                101.8,
                105.0,
                101.9,
                106.0,
                103.5,
                107.0,
            ],

            "c": [
                105.0,
                102.4,
                106.0,
                102.5,
                107.0,
                102.7,
                108.0,
                104.5,
                109.0,
            ],
        }
    )

    engine = AOIEngine(
        minimum_touches=3,

        zone_tolerance_pct=0.15,

        maximum_zone_width_pct=1.0,
    )

    # Important:
    #
    # Previous test used:
    #
    # 101.8 - 103.0
    #
    # which was 1.1719% wide and therefore
    # correctly failed our 1.0% width rule.
    #
    # This corrected test zone is narrower
    # while preserving three distinct touches.

    candidate = (
        engine.evaluate_zone(
            candles=candles,

            structure=structure,

            timeframe="15m",

            lower_bound=101.8,
            upper_bound=102.8,
        )
    )

    print(
        "AOI Type:",
        candidate.aoi_type.value
    )

    print(
        "Status:",
        candidate.status.value
    )

    print(
        "Touches:",
        candidate.touches
    )

    print(
        "Lower:",
        candidate.lower_bound
    )

    print(
        "Upper:",
        candidate.upper_bound
    )

    print(
        "Midpoint:",
        round(
            candidate.midpoint,
            4,
        )
    )

    print(
        "Width %:",
        round(
            candidate.width_pct,
            4,
        )
    )

    print(
        "Maximum Width %:",
        engine.maximum_zone_width_pct
    )

    print(
        "Inside Structure:",
        candidate.inside_structure_range
    )

    print(
        "Reason:",
        candidate.reason
    )

    assert (
        candidate.width_pct
        <= engine.maximum_zone_width_pct
    )

    assert (
        candidate.status
        == AOIStatus.VALID
    )

    assert (
        candidate.touches
        >= 3
    )

    assert (
        candidate.inside_structure_range
        is True
    )

    aoi = (
        engine.to_area_of_interest(
            candidate
        )
    )

    assert aoi is not None

    assert (
        aoi.touches >= 3
    )

    print(
        "--------------------------------------"
    )
    print(
        "AOI / THREE-TOUCH ENGINE TEST PASSED"
    )
    print(
        "======================================"
    )
    print()