from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from database.trade_ledger import TradeLedger
from risk.pretrade import (
    AuthorizationDecision,
    AuthorizationResult,
)


class PaperOrderStatus(str, Enum):
    FILLED = "FILLED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class ExitReason(str, Enum):
    STOP = "STOP"
    TARGET = "TARGET"
    MANUAL = "MANUAL"


@dataclass
class PaperPosition:
    position_id: int
    symbol: str
    side: str

    quantity: float

    requested_entry: float
    entry_price: float

    stop_price: float
    target_price: float

    entry_fee: float

    is_open: bool = True

    requested_exit: Optional[float] = None
    exit_price: Optional[float] = None

    exit_fee: float = 0.0

    gross_pnl: float = 0.0
    net_pnl: float = 0.0

    exit_reason: Optional[ExitReason] = None


@dataclass
class PaperExecutionResult:
    status: PaperOrderStatus
    reason: str
    position: Optional[PaperPosition] = None


class PaperExecutionEngine:
    """
    Paper-only execution engine.

    IMPORTANT:
    - Does NOT submit Hyperliquid orders.
    - Does NOT use a private key.
    - Simulates fills, slippage, and fees.
    - Optionally records executions into SQLite.
    """

    def __init__(
        self,
        slippage_bps: float = 2.0,
        fee_bps: float = 3.5,
        ledger: Optional[TradeLedger] = None,
    ):
        self.slippage_bps = float(slippage_bps)
        self.fee_bps = float(fee_bps)

        self.ledger = ledger

        self.positions: dict[int, PaperPosition] = {}

        self._next_position_id = 1

    # ==========================================================
    # INTERNAL HELPERS
    # ==========================================================

    def _apply_entry_slippage(
        self,
        side: str,
        price: float,
    ) -> float:

        slip = self.slippage_bps / 10_000

        if side.upper() == "LONG":
            return price * (1 + slip)

        if side.upper() == "SHORT":
            return price * (1 - slip)

        raise ValueError(
            f"Unsupported side: {side}"
        )

    def _apply_exit_slippage(
        self,
        side: str,
        price: float,
    ) -> float:

        slip = self.slippage_bps / 10_000

        if side.upper() == "LONG":
            return price * (1 - slip)

        if side.upper() == "SHORT":
            return price * (1 + slip)

        raise ValueError(
            f"Unsupported side: {side}"
        )

    def _calculate_fee(
        self,
        price: float,
        quantity: float,
    ) -> float:

        notional = price * quantity

        return (
            notional
            * self.fee_bps
            / 10_000
        )

    # ==========================================================
    # SUBMIT PAPER ENTRY
    # ==========================================================

    def submit(
        self,
        *,
        authorization: AuthorizationResult,
        symbol: str,
        side: str,
        requested_entry: float,
        stop_price: float,
        target_price: float,
    ) -> PaperExecutionResult:

        # ------------------------------------------------------
        # AUTHORIZATION MUST PASS
        # ------------------------------------------------------

        if (
            authorization.decision
            != AuthorizationDecision.AUTHORIZED
        ):
            return PaperExecutionResult(
                status=PaperOrderStatus.REJECTED,
                reason=(
                    "Execution rejected because "
                    "pre-trade authorization failed."
                ),
                position=None,
            )

        if authorization.risk_result is None:
            return PaperExecutionResult(
                status=PaperOrderStatus.REJECTED,
                reason=(
                    "Execution rejected because "
                    "risk result is missing."
                ),
                position=None,
            )

        quantity = (
            authorization
            .risk_result
            .position_size
        )

        if quantity <= 0:
            return PaperExecutionResult(
                status=PaperOrderStatus.REJECTED,
                reason="Position size must be positive.",
                position=None,
            )

        # ------------------------------------------------------
        # NORMALIZE SIDE
        # ------------------------------------------------------

        side = side.upper()

        if side not in {"LONG", "SHORT"}:
            return PaperExecutionResult(
                status=PaperOrderStatus.REJECTED,
                reason=f"Unsupported side: {side}",
                position=None,
            )

        # ------------------------------------------------------
        # SIMULATE ENTRY FILL
        # ------------------------------------------------------

        filled_entry = self._apply_entry_slippage(
            side=side,
            price=requested_entry,
        )

        entry_fee = self._calculate_fee(
            price=filled_entry,
            quantity=quantity,
        )

        position_id = self._next_position_id

        self._next_position_id += 1

        position = PaperPosition(
            position_id=position_id,
            symbol=symbol.upper(),
            side=side,
            quantity=quantity,
            requested_entry=float(requested_entry),
            entry_price=float(filled_entry),
            stop_price=float(stop_price),
            target_price=float(target_price),
            entry_fee=float(entry_fee),
        )

        self.positions[position_id] = position

        # ------------------------------------------------------
        # PERSIST ENTRY
        # ------------------------------------------------------

        if self.ledger is not None:

            try:
                self.ledger.record_entry(
                    position_id=position.position_id,
                    symbol=position.symbol,
                    side=position.side,
                    quantity=position.quantity,
                    requested_entry=position.requested_entry,
                    filled_entry=position.entry_price,
                    stop_price=position.stop_price,
                    target_price=position.target_price,
                    entry_fee=position.entry_fee,
                )

            except Exception as exc:

                # Fail closed.
                # If persistence fails, do not allow this
                # simulated execution to continue as valid.

                self.positions.pop(
                    position_id,
                    None,
                )

                return PaperExecutionResult(
                    status=PaperOrderStatus.REJECTED,
                    reason=(
                        "Execution persistence failed: "
                        f"{exc}"
                    ),
                    position=None,
                )

        return PaperExecutionResult(
            status=PaperOrderStatus.FILLED,
            reason=(
                "Paper order filled successfully."
            ),
            position=position,
        )

    # ==========================================================
    # UPDATE MARKET PRICE
    # ==========================================================

    def update_price(
        self,
        *,
        position_id: int,
        market_price: float,
    ) -> Optional[PaperExecutionResult]:

        position = self.positions.get(
            position_id
        )

        if position is None:
            return PaperExecutionResult(
                status=PaperOrderStatus.REJECTED,
                reason="Position does not exist.",
                position=None,
            )

        if not position.is_open:
            return None

        market_price = float(market_price)

        # ------------------------------------------------------
        # LONG
        # ------------------------------------------------------

        if position.side == "LONG":

            if market_price <= position.stop_price:

                return self.close_position(
                    position_id=position_id,
                    requested_exit_price=position.stop_price,
                    reason=ExitReason.STOP,
                )

            if market_price >= position.target_price:

                return self.close_position(
                    position_id=position_id,
                    requested_exit_price=position.target_price,
                    reason=ExitReason.TARGET,
                )

        # ------------------------------------------------------
        # SHORT
        # ------------------------------------------------------

        elif position.side == "SHORT":

            if market_price >= position.stop_price:

                return self.close_position(
                    position_id=position_id,
                    requested_exit_price=position.stop_price,
                    reason=ExitReason.STOP,
                )

            if market_price <= position.target_price:

                return self.close_position(
                    position_id=position_id,
                    requested_exit_price=position.target_price,
                    reason=ExitReason.TARGET,
                )

        return None

    # ==========================================================
    # CLOSE POSITION
    # ==========================================================

    def close_position(
        self,
        *,
        position_id: int,
        requested_exit_price: float,
        reason: ExitReason,
    ) -> PaperExecutionResult:

        position = self.positions.get(
            position_id
        )

        if position is None:

            return PaperExecutionResult(
                status=PaperOrderStatus.REJECTED,
                reason="Position does not exist.",
                position=None,
            )

        if not position.is_open:

            return PaperExecutionResult(
                status=PaperOrderStatus.REJECTED,
                reason="Position is already closed.",
                position=position,
            )

        # ------------------------------------------------------
        # SIMULATE EXIT
        # ------------------------------------------------------

        filled_exit = self._apply_exit_slippage(
            side=position.side,
            price=requested_exit_price,
        )

        exit_fee = self._calculate_fee(
            price=filled_exit,
            quantity=position.quantity,
        )

        # ------------------------------------------------------
        # PNL
        # ------------------------------------------------------

        if position.side == "LONG":

            gross_pnl = (
                filled_exit
                - position.entry_price
            ) * position.quantity

        else:

            gross_pnl = (
                position.entry_price
                - filled_exit
            ) * position.quantity

        net_pnl = (
            gross_pnl
            - position.entry_fee
            - exit_fee
        )

        # ------------------------------------------------------
        # PERSIST EXIT BEFORE FINAL STATE MUTATION
        # ------------------------------------------------------

        if self.ledger is not None:

            try:
                self.ledger.record_exit(
                    position_id=position.position_id,
                    requested_exit=float(
                        requested_exit_price
                    ),
                    filled_exit=float(
                        filled_exit
                    ),
                    exit_fee=float(
                        exit_fee
                    ),
                    gross_pnl=float(
                        gross_pnl
                    ),
                    net_pnl=float(
                        net_pnl
                    ),
                    exit_reason=reason.value,
                )

            except Exception as exc:

                # Fail closed.
                # Position remains open in memory because
                # persistent state was not successfully written.

                return PaperExecutionResult(
                    status=PaperOrderStatus.REJECTED,
                    reason=(
                        "Exit persistence failed: "
                        f"{exc}"
                    ),
                    position=position,
                )

        # ------------------------------------------------------
        # FINALIZE POSITION
        # ------------------------------------------------------

        position.requested_exit = float(
            requested_exit_price
        )

        position.exit_price = float(
            filled_exit
        )

        position.exit_fee = float(
            exit_fee
        )

        position.gross_pnl = float(
            gross_pnl
        )

        position.net_pnl = float(
            net_pnl
        )

        position.exit_reason = reason

        position.is_open = False

        return PaperExecutionResult(
            status=PaperOrderStatus.CLOSED,
            reason=(
                f"Paper position closed: "
                f"{reason.value}"
            ),
            position=position,
        )


# ==============================================================
# SELF TEST
# ==============================================================

if __name__ == "__main__":

    print()
    print("======================================")
    print(" PAPER EXECUTION ENGINE")
    print("======================================")
    print("Mode: PAPER ONLY")
    print("Hyperliquid Orders: DISABLED")
    print("Private Key: NOT USED")
    print("--------------------------------------")
    print(
        "Run:"
    )
    print(
        "python -m execution.test_paper_engine"
    )
    print(
        "for the full execution safety test."
    )
    print("======================================")
    print()