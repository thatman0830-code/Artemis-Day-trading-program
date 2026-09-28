from execution.paper_engine import (
    PaperExecutionEngine,
    PaperOrderStatus,
    ExitReason,
)

from risk.risk_engine import (
    RiskEngine,
    TradeProposal,
)

from risk.portfolio_guard import (
    PortfolioRiskGuard,
)

from risk.pretrade import (
    AuthorizationDecision,
    MarketHealthState,
    PreTradeAuthorization,
    PreTradeRequest,
)


def build_authorization(
    side="LONG",
    entry=80_000,
    stop=79_600,
    account_value=10_000,
    kill_switch=False,
):
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

    request = PreTradeRequest(
        trade=TradeProposal(
            symbol="BTC",
            side=side,
            entry_price=entry,
            stop_price=stop,
            account_value=account_value,
        ),

        session_start_value=10_000,
        current_total_notional=0,
        open_positions=0,
        consecutive_losses=0,

        market_health=MarketHealthState(
            connected=True,
            fresh=True,
            healthy=True,
            age_ms=500,
        ),

        kill_switch_active=kill_switch,
    )

    return authorizer.evaluate(request)


def print_position(position):
    print("Position ID:", position.position_id)
    print("Side:", position.side)
    print("Quantity:", round(position.quantity, 8))
    print("Entry:", round(position.entry_price, 4))
    print("Exit:", round(position.exit_price, 4))
    print("Exit Reason:", position.exit_reason.value)
    print("Gross PnL:", round(position.gross_pnl, 4))
    print("Entry Fee:", round(position.entry_fee, 4))
    print("Exit Fee:", round(position.exit_fee, 4))
    print("Net PnL:", round(position.net_pnl, 4))
    print("Position Open:", position.is_open)


if __name__ == "__main__":

    print()
    print("======================================")
    print(" PAPER EXECUTION SAFETY TEST")
    print("======================================")
    print("Mode: PAPER ONLY")
    print("Hyperliquid Orders: DISABLED")
    print("--------------------------------------")

    engine = PaperExecutionEngine(
        slippage_bps=2.0,
        fee_bps=3.5,
    )

    # ======================================
    # TEST 1 — LONG STOP LOSS
    # ======================================

    print("TEST 1: LONG STOP LOSS")

    authorization = build_authorization(
        side="LONG",
        entry=80_000,
        stop=79_600,
    )

    entry = engine.submit(
        authorization=authorization,
        symbol="BTC",
        side="LONG",
        requested_entry=80_000,
        stop_price=79_600,
        target_price=80_800,
    )

    assert entry.status == PaperOrderStatus.FILLED
    assert entry.position is not None

    result = engine.update_price(
        position_id=entry.position.position_id,
        market_price=79_500,
    )

    assert result is not None
    assert result.status == PaperOrderStatus.CLOSED
    assert result.position.exit_reason == ExitReason.STOP
    assert result.position.net_pnl < 0
    assert result.position.is_open is False

    print_position(result.position)

    print("PASS: LONG stop closed at a loss.")
    print("--------------------------------------")

    # ======================================
    # TEST 2 — SHORT TARGET
    # ======================================

    print("TEST 2: SHORT TARGET")

    authorization = build_authorization(
        side="SHORT",
        entry=80_000,
        stop=80_400,
    )

    entry = engine.submit(
        authorization=authorization,
        symbol="BTC",
        side="SHORT",
        requested_entry=80_000,
        stop_price=80_400,
        target_price=79_200,
    )

    assert entry.status == PaperOrderStatus.FILLED
    assert entry.position is not None

    result = engine.update_price(
        position_id=entry.position.position_id,
        market_price=79_100,
    )

    assert result is not None
    assert result.status == PaperOrderStatus.CLOSED
    assert result.position.exit_reason == ExitReason.TARGET
    assert result.position.net_pnl > 0

    print_position(result.position)

    print("PASS: SHORT target closed profitably.")
    print("--------------------------------------")

    # ======================================
    # TEST 3 — KILL SWITCH REJECTION
    # ======================================

    print("TEST 3: KILL SWITCH")

    authorization = build_authorization(
        side="LONG",
        entry=80_000,
        stop=79_600,
        kill_switch=True,
    )

    assert (
        authorization.decision
        == AuthorizationDecision.REJECTED
    )

    result = engine.submit(
        authorization=authorization,
        symbol="BTC",
        side="LONG",
        requested_entry=80_000,
        stop_price=79_600,
        target_price=80_800,
    )

    assert result.status == PaperOrderStatus.REJECTED
    assert result.position is None

    print("Authorization:", authorization.decision.value)
    print("Execution:", result.status.value)
    print("PASS: Rejected authorization cannot execute.")
    print("--------------------------------------")

    # ======================================
    # TEST 4 — DOUBLE CLOSE PROTECTION
    # ======================================

    print("TEST 4: DOUBLE CLOSE PROTECTION")

    authorization = build_authorization(
        side="LONG",
        entry=80_000,
        stop=79_600,
    )

    entry = engine.submit(
        authorization=authorization,
        symbol="BTC",
        side="LONG",
        requested_entry=80_000,
        stop_price=79_600,
        target_price=80_800,
    )

    assert entry.position is not None

    first_close = engine.close_position(
        position_id=entry.position.position_id,
        requested_exit_price=80_500,
        reason=ExitReason.MANUAL,
    )

    second_close = engine.close_position(
        position_id=entry.position.position_id,
        requested_exit_price=80_600,
        reason=ExitReason.MANUAL,
    )

    assert first_close.status == PaperOrderStatus.CLOSED
    assert second_close.status == PaperOrderStatus.REJECTED

    print("First Close:", first_close.status.value)
    print("Second Close:", second_close.status.value)
    print("Reason:", second_close.reason)

    print("PASS: Position cannot be closed twice.")
    print("--------------------------------------")

    print("ALL PAPER EXECUTION SAFETY TESTS PASSED")
    print("======================================")
    print()