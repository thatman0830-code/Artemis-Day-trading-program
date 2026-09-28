from dataclasses import dataclass
from enum import Enum


class RiskDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class TradeProposal:
    symbol: str
    side: str

    entry_price: float
    stop_price: float

    account_value: float


@dataclass(frozen=True)
class RiskResult:
    decision: RiskDecision
    reason: str

    symbol: str
    side: str

    account_value: float

    risk_pct: float
    risk_dollars: float

    stop_distance: float
    stop_distance_pct: float

    position_size: float
    notional_value: float


class RiskEngine:
    """
    Deterministic position-sizing and
    pre-trade risk engine.

    This component does NOT place orders.

    Strategy components may propose trades,
    but this engine independently decides
    whether the proposal is structurally
    valid and calculates maximum size.
    """

    def __init__(
        self,
        max_risk_per_trade_pct: float = 0.25,
        max_notional_pct: float = 100.0,
        minimum_stop_distance_pct: float = 0.05,
        maximum_stop_distance_pct: float = 5.0,
    ):
        self.max_risk_per_trade_pct = (
            max_risk_per_trade_pct
        )

        self.max_notional_pct = (
            max_notional_pct
        )

        self.minimum_stop_distance_pct = (
            minimum_stop_distance_pct
        )

        self.maximum_stop_distance_pct = (
            maximum_stop_distance_pct
        )

    def reject(
        self,
        proposal: TradeProposal,
        reason: str,
    ) -> RiskResult:

        return RiskResult(
            decision=RiskDecision.REJECTED,
            reason=reason,

            symbol=proposal.symbol,
            side=proposal.side,

            account_value=(
                proposal.account_value
            ),

            risk_pct=0.0,
            risk_dollars=0.0,

            stop_distance=0.0,
            stop_distance_pct=0.0,

            position_size=0.0,
            notional_value=0.0,
        )

    def evaluate(
        self,
        proposal: TradeProposal,
    ) -> RiskResult:

        side = (
            proposal.side
            .strip()
            .upper()
        )

        if side not in {
            "LONG",
            "SHORT",
        }:
            return self.reject(
                proposal,
                "Side must be LONG or SHORT.",
            )

        if proposal.account_value <= 0:
            return self.reject(
                proposal,
                "Account value must be greater than zero.",
            )

        if proposal.entry_price <= 0:
            return self.reject(
                proposal,
                "Entry price must be greater than zero.",
            )

        if proposal.stop_price <= 0:
            return self.reject(
                proposal,
                "Stop price must be greater than zero.",
            )

        if (
            proposal.entry_price
            == proposal.stop_price
        ):
            return self.reject(
                proposal,
                "Entry and stop cannot be equal.",
            )

        if (
            side == "LONG"
            and proposal.stop_price
            >= proposal.entry_price
        ):
            return self.reject(
                proposal,
                "LONG stop must be below entry.",
            )

        if (
            side == "SHORT"
            and proposal.stop_price
            <= proposal.entry_price
        ):
            return self.reject(
                proposal,
                "SHORT stop must be above entry.",
            )

        stop_distance = abs(
            proposal.entry_price
            - proposal.stop_price
        )

        stop_distance_pct = (
            stop_distance
            / proposal.entry_price
            * 100
        )

        if (
            stop_distance_pct
            < self.minimum_stop_distance_pct
        ):
            return self.reject(
                proposal,
                "Stop distance is below minimum risk threshold.",
            )

        if (
            stop_distance_pct
            > self.maximum_stop_distance_pct
        ):
            return self.reject(
                proposal,
                "Stop distance exceeds maximum risk threshold.",
            )

        risk_pct = (
            self.max_risk_per_trade_pct
        )

        risk_dollars = (
            proposal.account_value
            * risk_pct
            / 100
        )

        raw_position_size = (
            risk_dollars
            / stop_distance
        )

        raw_notional = (
            raw_position_size
            * proposal.entry_price
        )

        maximum_notional = (
            proposal.account_value
            * self.max_notional_pct
            / 100
        )

        if raw_notional > maximum_notional:

            position_size = (
                maximum_notional
                / proposal.entry_price
            )

            notional_value = (
                maximum_notional
            )

        else:

            position_size = (
                raw_position_size
            )

            notional_value = (
                raw_notional
            )

        if position_size <= 0:
            return self.reject(
                proposal,
                "Calculated position size is invalid.",
            )

        return RiskResult(
            decision=RiskDecision.APPROVED,

            reason=(
                "Trade passed structural "
                "risk validation."
            ),

            symbol=proposal.symbol,
            side=side,

            account_value=(
                proposal.account_value
            ),

            risk_pct=risk_pct,
            risk_dollars=risk_dollars,

            stop_distance=stop_distance,
            stop_distance_pct=(
                stop_distance_pct
            ),

            position_size=position_size,
            notional_value=notional_value,
        )


if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " RISK ENGINE TEST"
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

    engine = RiskEngine(
        max_risk_per_trade_pct=0.25,
        max_notional_pct=100.0,
        minimum_stop_distance_pct=0.05,
        maximum_stop_distance_pct=5.0,
    )

    tests = [
        (
            "VALID LONG",
            TradeProposal(
                symbol="BTC",
                side="LONG",
                entry_price=80_000,
                stop_price=79_600,
                account_value=10_000,
            ),
        ),
        (
            "VALID SHORT",
            TradeProposal(
                symbol="BTC",
                side="SHORT",
                entry_price=80_000,
                stop_price=80_400,
                account_value=10_000,
            ),
        ),
        (
            "INVALID LONG STOP",
            TradeProposal(
                symbol="BTC",
                side="LONG",
                entry_price=80_000,
                stop_price=80_500,
                account_value=10_000,
            ),
        ),
        (
            "ZERO ACCOUNT",
            TradeProposal(
                symbol="BTC",
                side="LONG",
                entry_price=80_000,
                stop_price=79_600,
                account_value=0,
            ),
        ),
    ]

    for name, proposal in tests:

        result = engine.evaluate(
            proposal
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

        if (
            result.decision
            == RiskDecision.APPROVED
        ):

            print(
                "Risk %:",
                round(
                    result.risk_pct,
                    4,
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
                "Stop Distance:",
                round(
                    result.stop_distance,
                    4,
                )
            )

            print(
                "Stop Distance %:",
                round(
                    result.stop_distance_pct,
                    4,
                )
            )

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
            "--------------------------------------"
        )

    print(
        "======================================"
    )
    print()