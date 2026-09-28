from __future__ import annotations

from enum import Enum
from typing import Optional

from strategy.aoi import AOICandidate, AOIEngine, AOIStatus
from strategy.liquidity import (
    LiquiditySweep,
    LiquiditySweepStatus,
    LiquiditySweepType,
)
from strategy.models import (
    MarketStructure,
    MarketTrend,
    SetupStatus,
    SetupType,
    StrategySignal,
    TradeDirection,
    calculate_risk_reward,
)
from strategy.multi_timeframe import ConsensusTrend, MultiTimeframeResult


class SetupOutcome(str, Enum):
    NO_SETUP = "NO_SETUP"
    WAITING = "WAITING"
    VALID_TRADE_CANDIDATE = "VALID_TRADE_CANDIDATE"


class SetupEngine:
    """Combine completed strategy analysis into a trade proposal.

    This engine is deliberately pure: it does not fetch market data, authorize
    risk, size positions, access credentials, or execute orders.
    """

    def __init__(self, minimum_risk_reward: float = 2.0):
        if minimum_risk_reward <= 0:
            raise ValueError("minimum_risk_reward must be positive.")
        self.minimum_risk_reward = float(minimum_risk_reward)

    @staticmethod
    def _signal(
        *,
        structure: MarketStructure,
        outcome: SetupOutcome,
        reason: str,
        direction: TradeDirection = TradeDirection.NONE,
        status: SetupStatus = SetupStatus.INVALID,
        aoi_candidate: Optional[AOICandidate] = None,
        sweep: Optional[LiquiditySweep] = None,
        entry_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        risk_reward: Optional[float] = None,
    ) -> StrategySignal:
        aoi = None
        if aoi_candidate is not None:
            aoi = AOIEngine.to_area_of_interest(aoi_candidate)

        metadata = {"outcome": outcome.value}
        if sweep is not None:
            metadata.update(
                sweep_status=sweep.status.value,
                sweep_type=sweep.sweep_type.value,
                sweep_reference=sweep.reference_level,
            )

        return StrategySignal(
            symbol=structure.symbol.upper(),
            direction=direction,
            setup_type=(
                SetupType.PULLBACK
                if direction != TradeDirection.NONE
                else SetupType.NONE
            ),
            status=status,
            timeframe=structure.timeframe,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            risk_reward=risk_reward,
            confidence=0.0 if status != SetupStatus.VALID else 1.0,
            reason=reason,
            market_trend=structure.trend,
            aoi=aoi,
            metadata=metadata,
        )

    def evaluate(
        self,
        *,
        structure: MarketStructure,
        multi_timeframe: MultiTimeframeResult,
        aoi_candidate: Optional[AOICandidate],
        sweep: Optional[LiquiditySweep],
    ) -> StrategySignal:
        """Return a fail-closed signal from already-computed strategy state."""
        if structure.symbol.upper() != multi_timeframe.symbol.upper():
            raise ValueError("Structure and multi-timeframe symbols must match.")

        if multi_timeframe.consensus in {
            ConsensusTrend.MIXED,
            ConsensusTrend.UNKNOWN,
        }:
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.NO_SETUP,
                reason="Multi-timeframe structure has no directional consensus.",
            )

        expected_trend = (
            MarketTrend.BULLISH
            if multi_timeframe.consensus == ConsensusTrend.BULLISH
            else MarketTrend.BEARISH
        )
        if structure.trend != expected_trend:
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.NO_SETUP,
                reason="Setup structure conflicts with multi-timeframe consensus.",
            )

        if aoi_candidate is None or aoi_candidate.status == AOIStatus.INVALID:
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.NO_SETUP,
                reason="No valid current-structure AOI is available.",
                aoi_candidate=aoi_candidate,
            )

        direction = (
            TradeDirection.LONG
            if expected_trend == MarketTrend.BULLISH
            else TradeDirection.SHORT
        )

        if aoi_candidate.status == AOIStatus.WAITING:
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.WAITING,
                status=SetupStatus.WAITING,
                direction=direction,
                reason="AOI exists but is still waiting for validation.",
                aoi_candidate=aoi_candidate,
            )

        if not (
            aoi_candidate.lower_bound
            <= structure.current_price
            <= aoi_candidate.upper_bound
        ):
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.WAITING,
                status=SetupStatus.WAITING,
                direction=direction,
                reason="Validated AOI exists; price has not entered it.",
                aoi_candidate=aoi_candidate,
                sweep=sweep,
            )

        expected_sweep = (
            LiquiditySweepType.SELL_SIDE
            if direction == TradeDirection.LONG
            else LiquiditySweepType.BUY_SIDE
        )
        if (
            sweep is None
            or sweep.status != LiquiditySweepStatus.CONFIRMED
        ):
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.WAITING,
                status=SetupStatus.WAITING,
                direction=direction,
                reason="Setup exists but is waiting for a liquidity trigger.",
                aoi_candidate=aoi_candidate,
                sweep=sweep,
            )

        if sweep.sweep_type != expected_sweep:
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.NO_SETUP,
                reason="Confirmed liquidity sweep conflicts with setup direction.",
                aoi_candidate=aoi_candidate,
                sweep=sweep,
            )

        entry = float(structure.current_price)
        if direction == TradeDirection.LONG:
            stop = float(sweep.candle_low)
            target = structure.swing_high
        else:
            stop = float(sweep.candle_high)
            target = structure.swing_low

        if target is None:
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.NO_SETUP,
                reason="Required structural target is unavailable.",
                aoi_candidate=aoi_candidate,
                sweep=sweep,
            )

        target = float(target)
        risk_reward = calculate_risk_reward(
            direction=direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
        )
        if risk_reward < self.minimum_risk_reward:
            return self._signal(
                structure=structure,
                outcome=SetupOutcome.NO_SETUP,
                reason=(
                    "Candidate risk-reward is below the configured minimum "
                    "or its price geometry is invalid."
                ),
                aoi_candidate=aoi_candidate,
                sweep=sweep,
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                risk_reward=risk_reward,
            )

        return self._signal(
            structure=structure,
            outcome=SetupOutcome.VALID_TRADE_CANDIDATE,
            status=SetupStatus.VALID,
            direction=direction,
            reason="Structure, AOI, liquidity trigger, and risk-reward align.",
            aoi_candidate=aoi_candidate,
            sweep=sweep,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            risk_reward=risk_reward,
        )
