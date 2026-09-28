from pathlib import Path

from database.trade_ledger import TradeLedger

from execution.paper_engine import (
    ExitReason,
    PaperExecutionEngine,
    PaperOrderStatus,
)

from risk.risk_engine import (
    RiskEngine,
    TradeProposal,
)

from risk.portfolio_guard import PortfolioRiskGuard

from risk.pretrade import (
    AuthorizationDecision,
    MarketHealthState,
    PreTradeAuthorization,
    PreTradeRequest,
)


# ==============================================================
# AUTHORIZATION HELPER
# ==============================================================

def build_authorization(
    side="LONG",
    entry=80_000,
    stop=79_600,
    account_value=10_000,
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

        session_start_value=account_value,
        current_total_notional=0,
        open_positions=0,
        consecutive_losses=0,

        market_health=MarketHealthState(
            connected=True,
            fresh=True,
            healthy=True,
            age_ms=500,
        ),

        kill_switch_active=False,
    )

    return authorizer.evaluate(request)


# ==============================================================
# TEST
# ==============================================================

if __name__ == "__main__":

    print()
    print("======================================")
    print(" PAPER EXECUTION + SQLITE TEST")
    print("======================================")
    print("Mode: PAPER ONLY")
    print("Hyperliquid Orders: DISABLED")
    print("Private Key: NOT USED")
    print("--------------------------------------")

    # ----------------------------------------------------------
    # CREATE CLEAN TEST DATABASE
    # ----------------------------------------------------------

    test_db = (
        Path("database")
        / "execution_integration_test.db"
    )

    if test_db.exists():
        test_db.unlink()

    ledger = TradeLedger(
        db_path=test_db
    )

    engine = PaperExecutionEngine(
        slippage_bps=2.0,
        fee_bps=3.5,
        ledger=ledger,
    )

    # ----------------------------------------------------------
    # AUTHORIZATION
    # ----------------------------------------------------------

    authorization = build_authorization()

    assert (
        authorization.decision
        == AuthorizationDecision.AUTHORIZED
    )

    print("Authorization: AUTHORIZED")

    # ----------------------------------------------------------
    # EXECUTE ENTRY
    # ----------------------------------------------------------

    result = engine.submit(
        authorization=authorization,
        symbol="BTC",
        side="LONG",
        requested_entry=80_000,
        stop_price=79_600,
        target_price=80_800,
    )

    assert result.status == PaperOrderStatus.FILLED
    assert result.position is not None

    position = result.position

    print("Execution Entry:", result.status.value)
    print("Position ID:", position.position_id)
    print("Filled Entry:", round(position.entry_price, 4))

    # ----------------------------------------------------------
    # VERIFY DATABASE OPEN
    # ----------------------------------------------------------

    db_trade = ledger.get_trade(
        position_id=position.position_id
    )

    assert db_trade is not None
    assert db_trade.status == "OPEN"

    assert (
        db_trade.filled_entry
        == position.entry_price
    )

    assert (
        db_trade.quantity
        == position.quantity
    )

    print("SQLite Entry:", db_trade.status)
    print(
        "SQLite Entry Price:",
        round(db_trade.filled_entry, 4),
    )

    open_trades = ledger.get_open_trades()

    assert len(open_trades) == 1

    print(
        "SQLite Open Trades:",
        len(open_trades),
    )

    print("--------------------------------------")

    # ----------------------------------------------------------
    # SIMULATE TARGET
    # ----------------------------------------------------------

    print("Simulating target hit...")

    exit_result = engine.update_price(
        position_id=position.position_id,
        market_price=80_900,
    )

    assert exit_result is not None
    assert (
        exit_result.status
        == PaperOrderStatus.CLOSED
    )

    assert exit_result.position is not None

    closed_position = exit_result.position

    assert (
        closed_position.exit_reason
        == ExitReason.TARGET
    )

    print(
        "Execution Exit:",
        exit_result.status.value,
    )

    print(
        "Exit Reason:",
        closed_position.exit_reason.value,
    )

    print(
        "Filled Exit:",
        round(
            closed_position.exit_price,
            4,
        ),
    )

    print(
        "Net PnL:",
        round(
            closed_position.net_pnl,
            4,
        ),
    )

    # ----------------------------------------------------------
    # VERIFY DATABASE CLOSED
    # ----------------------------------------------------------

    db_trade = ledger.get_trade(
        position_id=position.position_id
    )

    assert db_trade is not None

    assert db_trade.status == "CLOSED"

    assert db_trade.exit_reason == "TARGET"

    assert (
        db_trade.filled_exit
        == closed_position.exit_price
    )

    assert (
        db_trade.net_pnl
        == closed_position.net_pnl
    )

    print("--------------------------------------")
    print("SQLite Status:", db_trade.status)
    print("SQLite Exit Reason:", db_trade.exit_reason)

    print(
        "SQLite Filled Exit:",
        round(db_trade.filled_exit, 4),
    )

    print(
        "SQLite Net PnL:",
        round(db_trade.net_pnl, 4),
    )

    # ----------------------------------------------------------
    # VERIFY NO OPEN TRADE REMAINS
    # ----------------------------------------------------------

    open_trades = ledger.get_open_trades()

    assert len(open_trades) == 0

    print(
        "SQLite Open Trades:",
        len(open_trades),
    )

    # ----------------------------------------------------------
    # PERFORMANCE
    # ----------------------------------------------------------

    summary = ledger.performance_summary()

    assert summary["total_trades"] == 1
    assert summary["closed_trades"] == 1
    assert summary["open_trades"] == 0
    assert summary["winners"] == 1

    print("--------------------------------------")
    print("PERFORMANCE SUMMARY")

    print(
        "Total Trades:",
        summary["total_trades"],
    )

    print(
        "Closed Trades:",
        summary["closed_trades"],
    )

    print(
        "Winners:",
        summary["winners"],
    )

    print(
        "Losers:",
        summary["losers"],
    )

    print(
        "Win Rate:",
        round(summary["win_rate"], 2),
        "%",
    )

    print(
        "Total Net PnL:",
        round(
            summary["total_net_pnl"],
            4,
        ),
    )

    print(
        "Total Fees:",
        round(
            summary["total_fees"],
            4,
        ),
    )

    print("--------------------------------------")
    print("EXECUTION -> SQLITE INTEGRATION PASSED")
    print("======================================")
    print()