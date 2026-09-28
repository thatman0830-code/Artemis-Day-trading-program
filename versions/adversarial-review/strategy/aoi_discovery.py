from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from exchange.market_data import MarketDataEngine

from strategy.aoi import (
    AOICandidate,
    AOIEngine,
    AOIStatus,
)

from strategy.market_structure import (
    MarketStructureEngine,
)

from strategy.models import (
    MarketStructure,
    MarketTrend,
)


@dataclass(frozen=True)
class DiscoveredAOI:
    candidate: AOICandidate
    source_points: int


class AOIDiscoveryEngine:
    """
    Automatic AOI discovery engine.

    Improvements in this version:
    - Detect structural swing points
    - Restrict discovery to CURRENT structure
    - Ignore obsolete historical price zones
    - Cluster nearby structural prices
    - Validate through AOIEngine
    """

    def __init__(
        self,
        *,
        minimum_touches: int = 3,
        cluster_tolerance_pct: float = 0.25,
        zone_padding_pct: float = 0.05,
        maximum_zone_width_pct: float = 1.0,
        swing_window: int = 2,
    ):
        self.cluster_tolerance_pct = (
            cluster_tolerance_pct
        )

        self.zone_padding_pct = (
            zone_padding_pct
        )

        self.swing_window = (
            swing_window
        )

        self.aoi_engine = AOIEngine(
            minimum_touches=minimum_touches,
            zone_tolerance_pct=(
                cluster_tolerance_pct
            ),
            maximum_zone_width_pct=(
                maximum_zone_width_pct
            ),
        )

    # ==========================================================
    # SWING DETECTION
    # ==========================================================

    def _swing_high_prices(
        self,
        candles: pd.DataFrame,
    ) -> list[float]:

        highs = candles["h"].astype(float)

        points: list[float] = []

        w = self.swing_window

        for i in range(
            w,
            len(candles) - w,
        ):
            current = highs.iloc[i]

            left = highs.iloc[
                i - w:i
            ]

            right = highs.iloc[
                i + 1:i + w + 1
            ]

            if (
                current > left.max()
                and current > right.max()
            ):
                points.append(
                    float(current)
                )

        return points

    def _swing_low_prices(
        self,
        candles: pd.DataFrame,
    ) -> list[float]:

        lows = candles["l"].astype(float)

        points: list[float] = []

        w = self.swing_window

        for i in range(
            w,
            len(candles) - w,
        ):
            current = lows.iloc[i]

            left = lows.iloc[
                i - w:i
            ]

            right = lows.iloc[
                i + 1:i + w + 1
            ]

            if (
                current < left.min()
                and current < right.min()
            ):
                points.append(
                    float(current)
                )

        return points

    # ==========================================================
    # ACTIVE STRUCTURE RANGE
    # ==========================================================

    @staticmethod
    def _structure_bounds(
        structure: MarketStructure,
    ) -> tuple[float, float] | None:

        if (
            structure.trend
            == MarketTrend.BULLISH
        ):

            if (
                structure.higher_low is None
                or structure.higher_high is None
            ):
                return None

            return (
                float(structure.higher_low),
                float(structure.higher_high),
            )

        if (
            structure.trend
            == MarketTrend.BEARISH
        ):

            if (
                structure.lower_low is None
                or structure.lower_high is None
            ):
                return None

            return (
                float(structure.lower_low),
                float(structure.lower_high),
            )

        if (
            structure.swing_low is not None
            and structure.swing_high is not None
        ):

            return (
                float(structure.swing_low),
                float(structure.swing_high),
            )

        return None

    @staticmethod
    def _filter_structure_prices(
        prices: list[float],
        bounds: tuple[float, float] | None,
    ) -> list[float]:

        if bounds is None:
            return []

        lower, upper = bounds

        return [
            price
            for price in prices
            if lower <= price <= upper
        ]

    # ==========================================================
    # PRICE CLUSTERING
    # ==========================================================

    def _cluster_prices(
        self,
        prices: list[float],
    ) -> list[list[float]]:

        if not prices:
            return []

        sorted_prices = sorted(prices)

        clusters: list[
            list[float]
        ] = []

        for price in sorted_prices:

            placed = False

            for cluster in clusters:

                center = (
                    sum(cluster)
                    / len(cluster)
                )

                distance_pct = (
                    abs(price - center)
                    / center
                    * 100
                )

                if (
                    distance_pct
                    <= self.cluster_tolerance_pct
                ):
                    cluster.append(price)

                    placed = True

                    break

            if not placed:
                clusters.append(
                    [price]
                )

        return clusters

    # ==========================================================
    # CLUSTER -> ZONE
    # ==========================================================

    def _cluster_to_zone(
        self,
        cluster: list[float],
    ) -> tuple[float, float]:

        center = (
            sum(cluster)
            / len(cluster)
        )

        padding = (
            center
            * self.zone_padding_pct
            / 100
        )

        lower = (
            min(cluster)
            - padding
        )

        upper = (
            max(cluster)
            + padding
        )

        return (
            float(lower),
            float(upper),
        )

    # ==========================================================
    # DISCOVERY
    # ==========================================================

    def discover(
        self,
        *,
        candles: pd.DataFrame,
        structure: MarketStructure,
        timeframe: str,
    ) -> list[DiscoveredAOI]:

        if candles.empty:
            return []

        bounds = (
            self._structure_bounds(
                structure
            )
        )

        # --------------------------------------
        # Choose correct structural swing family
        # --------------------------------------

        if (
            structure.trend
            == MarketTrend.BULLISH
        ):

            swing_prices = (
                self._swing_low_prices(
                    candles
                )
            )

        elif (
            structure.trend
            == MarketTrend.BEARISH
        ):

            swing_prices = (
                self._swing_high_prices(
                    candles
                )
            )

        else:

            swing_prices = (
                self._swing_low_prices(
                    candles
                )
                +
                self._swing_high_prices(
                    candles
                )
            )

        # --------------------------------------
        # REMOVE OBSOLETE LEVELS
        # --------------------------------------

        swing_prices = (
            self._filter_structure_prices(
                swing_prices,
                bounds,
            )
        )

        clusters = (
            self._cluster_prices(
                swing_prices
            )
        )

        discovered: list[
            DiscoveredAOI
        ] = []

        for cluster in clusters:

            if len(cluster) < 2:
                continue

            lower, upper = (
                self._cluster_to_zone(
                    cluster
                )
            )

            if upper <= lower:
                continue

            try:

                candidate = (
                    self.aoi_engine
                    .evaluate_zone(
                        candles=candles,
                        structure=structure,
                        timeframe=timeframe,
                        lower_bound=lower,
                        upper_bound=upper,
                    )
                )

            except ValueError:
                continue

            discovered.append(
                DiscoveredAOI(
                    candidate=candidate,
                    source_points=(
                        len(cluster)
                    ),
                )
            )

        # ======================================
        # RANK RESULTS
        # ======================================

        def rank(
            item: DiscoveredAOI,
        ):

            status_rank = {
                AOIStatus.VALID: 0,
                AOIStatus.WAITING: 1,
                AOIStatus.INVALID: 2,
            }

            candidate = (
                item.candidate
            )

            return (
                status_rank[
                    candidate.status
                ],
                -candidate.touches,
                candidate.width_pct,
            )

        discovered.sort(
            key=rank
        )

        return discovered


# ==============================================================
# REAL HYPERLIQUID TEST
# ==============================================================


if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " CURRENT-STRUCTURE AOI DISCOVERY"
    )
    print(
        "======================================"
    )

    print(
        "Network: TESTNET"
    )

    print(
        "Symbol: BTC"
    )

    print(
        "Timeframe: 15m"
    )

    print(
        "Data: CLOSED CANDLES ONLY"
    )

    print(
        "Mode: CURRENT STRUCTURE ONLY"
    )

    print(
        "--------------------------------------"
    )

    market_data = MarketDataEngine(
        testnet=True
    )

    candles = (
        market_data
        .get_closed_candles(
            symbol="BTC",
            interval="15m",
            lookback_minutes=(
                15 * 300
            ),
        )
    )

    if candles.empty:

        raise RuntimeError(
            "No closed BTC candles returned."
        )

    structure_engine = (
        MarketStructureEngine(
            swing_window=2,
            minimum_swings=2,
        )
    )

    structure = (
        structure_engine.analyze(
            symbol="BTC",
            timeframe="15m",
            candles=candles,
        )
    )

    print(
        "Structure:",
        structure.trend.value
    )

    print(
        "Current Price:",
        structure.current_price
    )

    if (
        structure.trend
        == MarketTrend.BULLISH
    ):

        print(
            "Structure Low:",
            structure.higher_low
        )

        print(
            "Structure High:",
            structure.higher_high
        )

    elif (
        structure.trend
        == MarketTrend.BEARISH
    ):

        print(
            "Structure Low:",
            structure.lower_low
        )

        print(
            "Structure High:",
            structure.lower_high
        )

    else:

        print(
            "Structure Low:",
            structure.swing_low
        )

        print(
            "Structure High:",
            structure.swing_high
        )

    print(
        "--------------------------------------"
    )

    discovery = AOIDiscoveryEngine(
        minimum_touches=3,
        cluster_tolerance_pct=0.25,
        zone_padding_pct=0.05,
        maximum_zone_width_pct=1.0,
        swing_window=2,
    )

    results = discovery.discover(
        candles=candles,
        structure=structure,
        timeframe="15m",
    )

    print(
        "Relevant AOI Candidates:",
        len(results)
    )

    print(
        "--------------------------------------"
    )

    if not results:

        print(
            "No current-structure AOI qualifies."
        )

        print(
            "NO TRADE is a valid result."
        )

    else:

        for number, item in enumerate(
            results[:10],
            start=1,
        ):

            candidate = (
                item.candidate
            )

            print(
                "#",
                number
            )

            print(
                "Status:",
                candidate.status.value
            )

            print(
                "Type:",
                candidate.aoi_type.value
            )

            print(
                "Zone:",
                round(
                    candidate.lower_bound,
                    4,
                ),
                "-",
                round(
                    candidate.upper_bound,
                    4,
                ),
            )

            print(
                "Touches:",
                candidate.touches
            )

            print(
                "Source Swing Points:",
                item.source_points
            )

            print(
                "Width %:",
                round(
                    candidate.width_pct,
                    4,
                )
            )

            print(
                "Inside Structure:",
                candidate.inside_structure_range
            )

            print(
                "Reason:",
                candidate.reason
            )

            print(
                "--------------------------------------"
            )

    valid_count = sum(
        1
        for item in results
        if (
            item.candidate.status
            == AOIStatus.VALID
        )
    )

    waiting_count = sum(
        1
        for item in results
        if (
            item.candidate.status
            == AOIStatus.WAITING
        )
    )

    invalid_count = sum(
        1
        for item in results
        if (
            item.candidate.status
            == AOIStatus.INVALID
        )
    )

    print(
        "VALID:",
        valid_count
    )

    print(
        "WAITING:",
        waiting_count
    )

    print(
        "INVALID:",
        invalid_count
    )

    print(
        "--------------------------------------"
    )

    print(
        "CURRENT-STRUCTURE AOI TEST PASSED"
    )

    print(
        "======================================"
    )

    print()