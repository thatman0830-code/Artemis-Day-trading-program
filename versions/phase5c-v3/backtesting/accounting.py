from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from hashlib import sha256

from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting


def _hash(*parts: object) -> str:
    return sha256("\x1f".join(map(str, parts)).encode()).hexdigest()


class EquitySizingPolicy(str, Enum):
    COMPOUNDED = "COMPOUNDED"


@dataclass(frozen=True)
class EquitySnapshot:
    id: str
    run_id: str
    sequence: int
    previous_snapshot_id: str | None
    trade_accounting_id: str | None
    trade_id: str | None
    equity_change: Decimal
    equity: Decimal
    effective_time: int
    input_version: str
    immutable: bool = True


@dataclass(frozen=True)
class SimulatedEquityLedger:
    id: str
    run_id: str
    policy: EquitySizingPolicy
    input_version: str
    snapshots: tuple[EquitySnapshot, ...]
    immutable: bool = True

    @property
    def latest(self) -> EquitySnapshot:
        return self.snapshots[-1]


class SimulatedEquityLedgerEngine:
    """Immutable lineage over canonical #29.7.1 equity-change facts only."""

    def initial(self, *, run_id: str, starting_equity: Decimal,
                effective_time: int, input_version: str) -> SimulatedEquityLedger:
        if not run_id or not input_version or not isinstance(starting_equity, Decimal):
            raise TypeError("exact run identity, version, and Decimal equity are required")
        if not starting_equity.is_finite() or starting_equity <= 0:
            raise ValueError("initial equity must be finite and positive")
        sid = _hash("phase5a-equity-initial-v1", run_id, starting_equity, effective_time, input_version)
        snapshot = EquitySnapshot(sid, run_id, 0, None, None, None, Decimal("0"),
                                  starting_equity, int(effective_time), input_version)
        lid = _hash("phase5a-ledger-v1", run_id, EquitySizingPolicy.COMPOUNDED.value,
                    input_version, sid)
        return SimulatedEquityLedger(lid, run_id, EquitySizingPolicy.COMPOUNDED,
                                     input_version, (snapshot,))

    def apply(self, *, ledger: SimulatedEquityLedger,
              accounting: TradeAccounting) -> SimulatedEquityLedger:
        if not isinstance(ledger, SimulatedEquityLedger) or not isinstance(accounting, TradeAccounting):
            raise TypeError("immutable ledger and canonical TradeAccounting are required")
        existing = next((s for s in ledger.snapshots if s.trade_accounting_id == accounting.id), None)
        if existing:
            return ledger
        if any(s.trade_id == accounting.trade_id for s in ledger.snapshots if s.trade_id is not None):
            raise ValueError("conflicting duplicate trade accounting application")
        prior = ledger.latest
        if accounting.input_version != ledger.input_version:
            raise ValueError("accounting/ledger version mismatch")
        if accounting.pre_trade_equity != prior.equity:
            raise ValueError("accounting pre-trade equity forks ledger lineage")
        if accounting.account_equity_change != accounting.net_pnl:
            raise ValueError("canonical equity change mismatch")
        expected = prior.equity + accounting.account_equity_change
        if accounting.post_trade_equity != expected:
            raise ValueError("canonical post-trade equity mismatch")
        if accounting.closed_time < prior.effective_time:
            raise ValueError("retroactive accounting application")
        if (accounting.closed_time == prior.effective_time and prior.trade_id is not None
                and accounting.trade_id <= prior.trade_id):
            raise ValueError("same-time accounting order must use trade_id ASC")
        sid = _hash("phase5a-equity-v1", ledger.id, prior.id, accounting.id,
                    len(ledger.snapshots), expected, accounting.closed_time)
        snapshot = EquitySnapshot(sid, ledger.run_id, len(ledger.snapshots), prior.id,
            accounting.id, accounting.trade_id, accounting.account_equity_change,
            expected, accounting.closed_time, ledger.input_version)
        lid = _hash("phase5a-ledger-v1", ledger.run_id, ledger.policy.value,
                    ledger.input_version, *(s.id for s in ledger.snapshots + (snapshot,)))
        return SimulatedEquityLedger(lid, ledger.run_id, ledger.policy,
                                     ledger.input_version, ledger.snapshots + (snapshot,))
