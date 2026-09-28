from dataclasses import dataclass
from enum import Enum

from risk.risk_engine import (
    RiskDecision,
    RiskEngine,
    RiskResult,
    TradeProposal,
)

from risk.portfolio_guard import (
    PortfolioDecision,
    PortfolioRiskGuard,
    PortfolioState,
    PortfolioResult,
)


class AuthorizationDecision(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class MarketHealthState:
    """
    Simplified market-health snapshot supplied
    by the realtime market-data health layer.
    """

    connected: bool
    fresh: bool
    healthy: bool
    age_ms: int


@dataclass(frozen=True)
class PreTradeRequest:
    """
    Everything required to evaluate a proposed trade.
    """

    trade: TradeProposal

    session_start_value: float
    current_total_notional: float
    open_positions: int
    consecutive_losses: int

    market_health: MarketHealthState

    kill_switch_active: bool = False


@dataclass(frozen=True)
class AuthorizationResult:
    decision: AuthorizationDecision
    reason: str

    market_approved: bool
    trade_risk_approved: bool
    portfolio_approved: bool

    position_size: float
    notional_value: float
    risk_dollars: float

    risk_result: RiskResult | None
    portfolio_result: PortfolioResult | None


class PreTradeAuthorization:
    """
    Master fail-closed pre-trade authorization system.

    This module DOES NOT place orders.

    A trade must pass:

        1. Market-data health
        2. Individual trade risk
        3. Portfolio risk

    Any failure results in REJECTED.
    """

    def __init__(
        self,
        risk_engine: RiskEngine | None = None,
        portfolio_guard: PortfolioRiskGuard | None = None,
        maximum_market_data_age_ms: int = 10_000,
    ):

        self.risk_engine = (
            risk_engine
            if risk_engine is not None
            else RiskEngine()
        )

        self.portfolio_guard = (
            portfolio_guard
            if portfolio_guard is not None
            else PortfolioRiskGuard()
        )

        self.maximum_market_data_age_ms = (
            maximum_market_data_age_ms
        )

    def _reject(
        self,
        reason: str,
        market_approved: bool = False,
        trade_risk_approved: bool = False,
        portfolio_approved: bool = False,
        risk_result: RiskResult | None = None,
        portfolio_result: PortfolioResult | None = None,
    ) -> AuthorizationResult:

        return AuthorizationResult(
            decision=AuthorizationDecision.REJECTED,
            reason=reason,

            market_approved=market_approved,
            trade_risk_approved=trade_risk_approved,
            portfolio_approved=portfolio_approved,

            position_size=0.0,
            notional_value=0.0,
            risk_dollars=0.0,

            risk_result=risk_result,
            portfolio_result=portfolio_result,
        )

    def evaluate(
        self,
        request: PreTradeRequest,
    ) -> AuthorizationResult:

        # ==========================================
        # GATE 0 — EMERGENCY KILL SWITCH
        # ==========================================

        if request.kill_switch_active:

            return self._reject(
                reason=(
                    "Emergency kill switch is active."
                )
            )

        # ==========================================
        # GATE 1 — MARKET DATA HEALTH
        # ==========================================

        health = request.market_health

        if not health.connected:

            return self._reject(
                reason=(
                    "Market data is disconnected."
                )
            )

        if not health.fresh:

            return self._reject(
                reason=(
                    "Market data is not fresh."
                )
            )

        if not health.healthy:

            return self._reject(
                reason=(
                    "Market data health gate rejected trading."
                )
            )

        if health.age_ms < 0:

            return self._reject(
                reason=(
                    "Market data age is invalid."
                )
            )

        if (
            health.age_ms
            > self.maximum_market_data_age_ms
        ):

            return self._reject(
                reason=(
                    "Market data exceeds maximum age."
                )
            )

        market_approved = True

        # ==========================================
        # GATE 2 — INDIVIDUAL TRADE RISK
        # ==========================================

        risk_result = self.risk_engine.evaluate(
            request.trade
        )

        if (
            risk_result.decision
            != RiskDecision.APPROVED
        ):

            return self._reject(
                reason=(
                    "Trade risk rejected: "
                    + risk_result.reason
                ),
                market_approved=True,
                risk_result=risk_result,
            )

        trade_risk_approved = True

        # ==========================================
        # GATE 3 — PORTFOLIO RISK
        # ==========================================

        portfolio_state = PortfolioState(
            account_value=(
                request.trade.account_value
            ),

            session_start_value=(
                request.session_start_value
            ),

            current_total_notional=(
                request.current_total_notional
            ),

            proposed_trade_notional=(
                risk_result.notional_value
            ),

            open_positions=(
                request.open_positions
            ),

            consecutive_losses=(
                request.consecutive_losses
            ),

            kill_switch_active=(
                request.kill_switch_active
            ),
        )

        portfolio_result = (
            self.portfolio_guard.evaluate(
                portfolio_state
            )
        )

        if (
            portfolio_result.decision
            != PortfolioDecision.APPROVED
        ):

            return self._reject(
                reason=(
                    "Portfolio risk rejected: "
                    + portfolio_result.reason
                ),

                market_approved=True,
                trade_risk_approved=True,

                risk_result=risk_result,
                portfolio_result=portfolio_result,
            )

        # ==========================================
        # ALL GATES PASSED
        # ==========================================

        return AuthorizationResult(
            decision=(
                AuthorizationDecision.AUTHORIZED
            ),

            reason=(
                "Trade passed all pre-trade "
                "authorization gates."
            ),

            market_approved=True,
            trade_risk_approved=True,
            portfolio_approved=True,

            position_size=(
                risk_result.position_size
            ),

            notional_value=(
                risk_result.notional_value
            ),

            risk_dollars=(
                risk_result.risk_dollars
            ),

            risk_result=risk_result,
            portfolio_result=portfolio_result,
        )


if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " MASTER PRE-TRADE AUTHORIZATION TEST"
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
        "Policy: FAIL CLOSED"
    )
    print(
        "--------------------------------------"
    )

    risk_engine = RiskEngine(
        max_risk_per_trade_pct=0.25,
        max_notional_pct=100.0,
        minimum_stop_distance_pct=0.05,
        maximum_stop_distance_pct=5.0,
    )

    portfolio_guard = PortfolioRiskGuard(
        max_daily_loss_pct=1.0,
        max_consecutive_losses=3,
        max_total_exposure_pct=100.0,
        max_open_positions=3,
    )

    authorizer = PreTradeAuthorization(
        risk_engine=risk_engine,
        portfolio_guard=portfolio_guard,
        maximum_market_data_age_ms=10_000,
    )

    healthy_market = MarketHealthState(
        connected=True,
        fresh=True,
        healthy=True,
        age_ms=500,
    )

    tests = [
        (
            "VALID TRADE",
            PreTradeRequest(
                trade=TradeProposal(
                    symbol="BTC",
                    side="LONG",
                    entry_price=80_000,
                    stop_price=79_600,
                    account_value=10_000,
                ),
                session_start_value=10_000,
                current_total_notional=2_000,
                open_positions=1,
                consecutive_losses=0,
                market_health=healthy_market,
            ),
        ),

        (
            "STALE MARKET DATA",
            PreTradeRequest(
                trade=TradeProposal(
                    symbol="BTC",
                    side="LONG",
                    entry_price=80_000,
                    stop_price=79_600,
                    account_value=10_000,
                ),
                session_start_value=10_000,
                current_total_notional=0,
                open_positions=0,
                consecutive_losses=0,
                market_health=MarketHealthState(
                    connected=True,
                    fresh=False,
                    healthy=False,
                    age_ms=15_000,
                ),
            ),
        ),

        (
            "INVALID TRADE RISK",
            PreTradeRequest(
                trade=TradeProposal(
                    symbol="BTC",
                    side="LONG",
                    entry_price=80_000,
                    stop_price=80_500,
                    account_value=10_000,
                ),
                session_start_value=10_000,
                current_total_notional=0,
                open_positions=0,
                consecutive_losses=0,
                market_health=healthy_market,
            ),
        ),

        (
            "PORTFOLIO LOSS LIMIT",
            PreTradeRequest(
                trade=TradeProposal(
                    symbol="BTC",
                    side="LONG",
                    entry_price=80_000,
                    stop_price=79_600,
                    account_value=9_900,
                ),
                session_start_value=10_000,
                current_total_notional=0,
                open_positions=0,
                consecutive_losses=0,
                market_health=healthy_market,
            ),
        ),

        (
            "KILL SWITCH",
            PreTradeRequest(
                trade=TradeProposal(
                    symbol="BTC",
                    side="LONG",
                    entry_price=80_000,
                    stop_price=79_600,
                    account_value=10_000,
                ),
                session_start_value=10_000,
                current_total_notional=0,
                open_positions=0,
                consecutive_losses=0,
                market_health=healthy_market,
                kill_switch_active=True,
            ),
        ),
    ]

    for name, request in tests:

        result = authorizer.evaluate(
            request
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
            "Market Gate:",
            result.market_approved
        )

        print(
            "Trade Risk Gate:",
            result.trade_risk_approved
        )

        print(
            "Portfolio Gate:",
            result.portfolio_approved
        )

        if (
            result.decision
            == AuthorizationDecision.AUTHORIZED
        ):

            print(
                "Position Size:",
                round(
                    result.position_size,
                    8,
                )
            )

            print(
                "Notional:",
                round(
                    result.notional_value,
                    2,
                )
            )

            print(
                "Risk $:",
                round(
                    result.risk_dollars,
                    2,
                )
            )

        print(
            "--------------------------------------"
        )

    print(
        "======================================"
    )
    print()