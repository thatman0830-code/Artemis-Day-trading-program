from dataclasses import dataclass
from enum import Enum


class PortfolioDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class PortfolioState:
    account_value: float
    session_start_value: float

    current_total_notional: float
    proposed_trade_notional: float

    open_positions: int
    consecutive_losses: int

    kill_switch_active: bool = False


@dataclass(frozen=True)
class PortfolioResult:
    decision: PortfolioDecision
    reason: str

    daily_pnl: float
    daily_pnl_pct: float

    current_total_notional: float
    proposed_trade_notional: float
    projected_total_notional: float

    projected_exposure_pct: float


class PortfolioRiskGuard:
    """
    Portfolio-level pre-trade safety gate.

    This module does NOT place orders.

    It determines whether new exposure
    may be added to the portfolio.
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 1.0,
        max_consecutive_losses: int = 3,
        max_total_exposure_pct: float = 100.0,
        max_open_positions: int = 3,
    ):
        self.max_daily_loss_pct = (
            max_daily_loss_pct
        )

        self.max_consecutive_losses = (
            max_consecutive_losses
        )

        self.max_total_exposure_pct = (
            max_total_exposure_pct
        )

        self.max_open_positions = (
            max_open_positions
        )

    def _result(
        self,
        state: PortfolioState,
        decision: PortfolioDecision,
        reason: str,
    ) -> PortfolioResult:

        if state.session_start_value > 0:

            daily_pnl = (
                state.account_value
                - state.session_start_value
            )

            daily_pnl_pct = (
                daily_pnl
                / state.session_start_value
                * 100
            )

        else:

            daily_pnl = 0.0
            daily_pnl_pct = 0.0

        projected_total_notional = (
            state.current_total_notional
            + state.proposed_trade_notional
        )

        if state.account_value > 0:

            projected_exposure_pct = (
                projected_total_notional
                / state.account_value
                * 100
            )

        else:

            projected_exposure_pct = 0.0

        return PortfolioResult(
            decision=decision,
            reason=reason,

            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,

            current_total_notional=(
                state.current_total_notional
            ),

            proposed_trade_notional=(
                state.proposed_trade_notional
            ),

            projected_total_notional=(
                projected_total_notional
            ),

            projected_exposure_pct=(
                projected_exposure_pct
            ),
        )

    def reject(
        self,
        state: PortfolioState,
        reason: str,
    ) -> PortfolioResult:

        return self._result(
            state=state,
            decision=PortfolioDecision.REJECTED,
            reason=reason,
        )

    def approve(
        self,
        state: PortfolioState,
    ) -> PortfolioResult:

        return self._result(
            state=state,
            decision=PortfolioDecision.APPROVED,
            reason=(
                "Portfolio passed all "
                "pre-trade safety checks."
            ),
        )

    def evaluate(
        self,
        state: PortfolioState,
    ) -> PortfolioResult:

        # --------------------------------
        # Emergency kill switch
        # --------------------------------

        if state.kill_switch_active:

            return self.reject(
                state,
                "Emergency kill switch is active.",
            )

        # --------------------------------
        # Basic validation
        # --------------------------------

        if state.account_value <= 0:

            return self.reject(
                state,
                "Account value must be greater than zero.",
            )

        if state.session_start_value <= 0:

            return self.reject(
                state,
                "Session start value must be greater than zero.",
            )

        if state.current_total_notional < 0:

            return self.reject(
                state,
                "Current total notional cannot be negative.",
            )

        if state.proposed_trade_notional <= 0:

            return self.reject(
                state,
                "Proposed trade notional must be greater than zero.",
            )

        if state.open_positions < 0:

            return self.reject(
                state,
                "Open position count cannot be negative.",
            )

        if state.consecutive_losses < 0:

            return self.reject(
                state,
                "Consecutive losses cannot be negative.",
            )

        # --------------------------------
        # Daily loss calculation
        # --------------------------------

        daily_pnl = (
            state.account_value
            - state.session_start_value
        )

        daily_pnl_pct = (
            daily_pnl
            / state.session_start_value
            * 100
        )

        if (
            daily_pnl_pct
            <= -self.max_daily_loss_pct
        ):

            return self.reject(
                state,
                "Maximum daily loss limit reached.",
            )

        # --------------------------------
        # Consecutive-loss circuit breaker
        # --------------------------------

        if (
            state.consecutive_losses
            >= self.max_consecutive_losses
        ):

            return self.reject(
                state,
                "Maximum consecutive loss limit reached.",
            )

        # --------------------------------
        # Open-position limit
        # --------------------------------

        if (
            state.open_positions
            >= self.max_open_positions
        ):

            return self.reject(
                state,
                "Maximum open position limit reached.",
            )

        # --------------------------------
        # Portfolio exposure limit
        # --------------------------------

        projected_total_notional = (
            state.current_total_notional
            + state.proposed_trade_notional
        )

        projected_exposure_pct = (
            projected_total_notional
            / state.account_value
            * 100
        )

        if (
            projected_exposure_pct
            > self.max_total_exposure_pct
        ):

            return self.reject(
                state,
                "Maximum portfolio exposure would be exceeded.",
            )

        return self.approve(
            state
        )


if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " PORTFOLIO RISK GUARD TEST"
    )
    print(
        "======================================"
    )
    print(
        "Mode: SIMULATION ONLY"
    )
    print(
        "Orders: DISABLED"
    )
    print(
        "--------------------------------------"
    )

    guard = PortfolioRiskGuard(
        max_daily_loss_pct=1.0,
        max_consecutive_losses=3,
        max_total_exposure_pct=100.0,
        max_open_positions=3,
    )

    tests = [
        (
            "HEALTHY PORTFOLIO",
            PortfolioState(
                account_value=10_050,
                session_start_value=10_000,
                current_total_notional=2_000,
                proposed_trade_notional=3_000,
                open_positions=1,
                consecutive_losses=0,
            ),
        ),

        (
            "DAILY LOSS LIMIT",
            PortfolioState(
                account_value=9_900,
                session_start_value=10_000,
                current_total_notional=0,
                proposed_trade_notional=2_000,
                open_positions=0,
                consecutive_losses=1,
            ),
        ),

        (
            "CONSECUTIVE LOSSES",
            PortfolioState(
                account_value=10_000,
                session_start_value=10_000,
                current_total_notional=0,
                proposed_trade_notional=2_000,
                open_positions=0,
                consecutive_losses=3,
            ),
        ),

        (
            "EXPOSURE LIMIT",
            PortfolioState(
                account_value=10_000,
                session_start_value=10_000,
                current_total_notional=8_000,
                proposed_trade_notional=3_000,
                open_positions=1,
                consecutive_losses=0,
            ),
        ),

        (
            "POSITION LIMIT",
            PortfolioState(
                account_value=10_000,
                session_start_value=10_000,
                current_total_notional=5_000,
                proposed_trade_notional=1_000,
                open_positions=3,
                consecutive_losses=0,
            ),
        ),

        (
            "KILL SWITCH",
            PortfolioState(
                account_value=10_000,
                session_start_value=10_000,
                current_total_notional=0,
                proposed_trade_notional=1_000,
                open_positions=0,
                consecutive_losses=0,
                kill_switch_active=True,
            ),
        ),
    ]

    for name, state in tests:

        result = guard.evaluate(
            state
        )

        print(name)

        print(
            "Decision:",
            result.decision.value
        )

        print(
            "Reason:",
            result.reason
        )

        print(
            "Daily PnL $:",
            round(
                result.daily_pnl,
                2,
            )
        )

        print(
            "Daily PnL %:",
            round(
                result.daily_pnl_pct,
                4,
            )
        )

        print(
            "Projected Notional:",
            round(
                result.projected_total_notional,
                2,
            )
        )

        print(
            "Projected Exposure %:",
            round(
                result.projected_exposure_pct,
                4,
            )
        )

        print(
            "--------------------------------------"
        )

    print(
        "======================================"
    )
    print()