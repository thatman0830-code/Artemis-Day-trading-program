from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = Path("database") / "trading_bot.db"


@dataclass
class TradeRecord:
    trade_id: int
    position_id: int
    symbol: str
    side: str

    quantity: float

    requested_entry: float
    filled_entry: float

    stop_price: float
    target_price: float

    entry_fee: float

    status: str

    opened_at: str

    requested_exit: Optional[float] = None
    filled_exit: Optional[float] = None

    exit_fee: float = 0.0

    gross_pnl: float = 0.0
    net_pnl: float = 0.0

    exit_reason: Optional[str] = None
    closed_at: Optional[str] = None


class TradeLedger:
    """
    Persistent SQLite trade ledger.

    This database is the permanent execution record
    for the trading bot.

    It does NOT place orders.

    It records what the execution engine did.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
    ):
        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_database()

    # ==========================================================
    # DATABASE CONNECTION
    # ==========================================================

    def _connect(self) -> sqlite3.Connection:

        connection = sqlite3.connect(
            self.db_path
        )

        connection.row_factory = sqlite3.Row

        return connection

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def _initialize_database(self):

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (

                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    position_id INTEGER NOT NULL,

                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,

                    quantity REAL NOT NULL,

                    requested_entry REAL NOT NULL,
                    filled_entry REAL NOT NULL,

                    stop_price REAL NOT NULL,
                    target_price REAL NOT NULL,

                    entry_fee REAL NOT NULL DEFAULT 0,

                    status TEXT NOT NULL,

                    opened_at TEXT NOT NULL,

                    requested_exit REAL,
                    filled_exit REAL,

                    exit_fee REAL NOT NULL DEFAULT 0,

                    gross_pnl REAL NOT NULL DEFAULT 0,
                    net_pnl REAL NOT NULL DEFAULT 0,

                    exit_reason TEXT,
                    closed_at TEXT,

                    UNIQUE(position_id)
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_trades_symbol
                ON trades(symbol)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_trades_status
                ON trades(status)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_trades_opened_at
                ON trades(opened_at)
                """
            )

            connection.commit()

    # ==========================================================
    # TIME
    # ==========================================================

    @staticmethod
    def _utc_now() -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()

    # ==========================================================
    # RECORD ENTRY
    # ==========================================================

    def record_entry(
        self,
        *,
        position_id: int,
        symbol: str,
        side: str,
        quantity: float,
        requested_entry: float,
        filled_entry: float,
        stop_price: float,
        target_price: float,
        entry_fee: float,
    ) -> int:

        opened_at = self._utc_now()

        with self._connect() as connection:

            cursor = connection.execute(
                """
                INSERT INTO trades (

                    position_id,

                    symbol,
                    side,

                    quantity,

                    requested_entry,
                    filled_entry,

                    stop_price,
                    target_price,

                    entry_fee,

                    status,

                    opened_at

                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position_id,

                    symbol.upper(),
                    side.upper(),

                    float(quantity),

                    float(requested_entry),
                    float(filled_entry),

                    float(stop_price),
                    float(target_price),

                    float(entry_fee),

                    "OPEN",

                    opened_at,
                ),
            )

            connection.commit()

            return int(cursor.lastrowid)

    # ==========================================================
    # RECORD EXIT
    # ==========================================================

    def record_exit(
        self,
        *,
        position_id: int,
        requested_exit: float,
        filled_exit: float,
        exit_fee: float,
        gross_pnl: float,
        net_pnl: float,
        exit_reason: str,
    ):

        closed_at = self._utc_now()

        with self._connect() as connection:

            cursor = connection.execute(
                """
                UPDATE trades

                SET
                    requested_exit = ?,
                    filled_exit = ?,

                    exit_fee = ?,

                    gross_pnl = ?,
                    net_pnl = ?,

                    exit_reason = ?,

                    status = ?,

                    closed_at = ?

                WHERE
                    position_id = ?
                    AND status = 'OPEN'
                """,
                (
                    float(requested_exit),
                    float(filled_exit),

                    float(exit_fee),

                    float(gross_pnl),
                    float(net_pnl),

                    exit_reason.upper(),

                    "CLOSED",

                    closed_at,

                    position_id,
                ),
            )

            if cursor.rowcount != 1:

                raise ValueError(
                    "Trade exit could not be recorded. "
                    "Position does not exist or is already closed."
                )

            connection.commit()

    # ==========================================================
    # FETCH ONE TRADE
    # ==========================================================

    def get_trade(
        self,
        position_id: int,
    ) -> Optional[TradeRecord]:

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE position_id = ?
                """,
                (position_id,),
            ).fetchone()

        if row is None:
            return None

        return TradeRecord(
            **dict(row)
        )

    # ==========================================================
    # FETCH OPEN TRADES
    # ==========================================================

    def get_open_trades(
        self,
    ) -> list[TradeRecord]:

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM trades
                WHERE status = 'OPEN'
                ORDER BY opened_at ASC
                """
            ).fetchall()

        return [
            TradeRecord(**dict(row))
            for row in rows
        ]

    # ==========================================================
    # FETCH RECENT TRADES
    # ==========================================================

    def get_recent_trades(
        self,
        limit: int = 20,
    ) -> list[TradeRecord]:

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM trades
                ORDER BY trade_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            TradeRecord(**dict(row))
            for row in rows
        ]

    # ==========================================================
    # PERFORMANCE SUMMARY
    # ==========================================================

    def performance_summary(
        self,
    ) -> dict:

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT

                    COUNT(*) AS total_trades,

                    SUM(
                        CASE
                            WHEN status = 'CLOSED'
                            THEN 1
                            ELSE 0
                        END
                    ) AS closed_trades,

                    SUM(
                        CASE
                            WHEN status = 'OPEN'
                            THEN 1
                            ELSE 0
                        END
                    ) AS open_trades,

                    SUM(
                        CASE
                            WHEN status = 'CLOSED'
                            AND net_pnl > 0
                            THEN 1
                            ELSE 0
                        END
                    ) AS winners,

                    SUM(
                        CASE
                            WHEN status = 'CLOSED'
                            AND net_pnl < 0
                            THEN 1
                            ELSE 0
                        END
                    ) AS losers,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN status = 'CLOSED'
                                THEN net_pnl
                                ELSE 0
                            END
                        ),
                        0
                    ) AS total_net_pnl,

                    COALESCE(
                        SUM(entry_fee + exit_fee),
                        0
                    ) AS total_fees

                FROM trades
                """
            ).fetchone()

        result = dict(row)

        closed = result["closed_trades"] or 0
        winners = result["winners"] or 0

        if closed > 0:
            win_rate = (
                winners / closed
            ) * 100
        else:
            win_rate = 0.0

        result["win_rate"] = win_rate

        return result


# ==============================================================
# SELF TEST
# ==============================================================

if __name__ == "__main__":

    test_db = (
        Path("database")
        / "trade_ledger_test.db"
    )

    if test_db.exists():
        test_db.unlink()

    ledger = TradeLedger(
        db_path=test_db
    )

    print()
    print("======================================")
    print(" SQLITE TRADE LEDGER TEST")
    print("======================================")
    print("Database:", test_db)
    print("--------------------------------------")

    trade_id = ledger.record_entry(
        position_id=1001,
        symbol="BTC",
        side="LONG",
        quantity=0.0625,
        requested_entry=80_000,
        filled_entry=80_016,
        stop_price=79_600,
        target_price=80_800,
        entry_fee=1.7504,
    )

    print("Trade ID:", trade_id)

    trade = ledger.get_trade(
        position_id=1001
    )

    assert trade is not None
    assert trade.status == "OPEN"

    print("Entry recorded:", trade.status)
    print("Open trades:", len(
        ledger.get_open_trades()
    ))

    ledger.record_exit(
        position_id=1001,
        requested_exit=80_800,
        filled_exit=80_783.84,
        exit_fee=1.7671,
        gross_pnl=47.99,
        net_pnl=44.4725,
        exit_reason="TARGET",
    )

    trade = ledger.get_trade(
        position_id=1001
    )

    assert trade is not None
    assert trade.status == "CLOSED"
    assert trade.exit_reason == "TARGET"
    assert trade.net_pnl == 44.4725

    print("Exit recorded:", trade.status)
    print("Exit reason:", trade.exit_reason)
    print("Net PnL:", trade.net_pnl)

    open_trades = ledger.get_open_trades()

    assert len(open_trades) == 0

    print("Open trades:", len(open_trades))

    summary = ledger.performance_summary()

    print("--------------------------------------")
    print("PERFORMANCE SUMMARY")
    print("Total Trades:", summary["total_trades"])
    print("Closed Trades:", summary["closed_trades"])
    print("Open Trades:", summary["open_trades"])
    print("Winners:", summary["winners"])
    print("Losers:", summary["losers"])
    print(
        "Win Rate:",
        round(summary["win_rate"], 2),
        "%",
    )
    print(
        "Net PnL:",
        round(summary["total_net_pnl"], 4),
    )
    print(
        "Fees:",
        round(summary["total_fees"], 4),
    )

    print("--------------------------------------")
    print("SQLITE TRADE LEDGER TEST PASSED")
    print("======================================")
    print()