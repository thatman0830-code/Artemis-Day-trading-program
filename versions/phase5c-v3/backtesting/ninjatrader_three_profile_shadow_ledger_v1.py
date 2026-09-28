"""Independent, identical-signal ledgers for the three non-executable profiles."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
from enum import Enum
import hashlib
import json

from backtesting.ninjatrader_micro_instrument_specs_v1 import verified_micro_instrument_specifications
from backtesting.ninjatrader_micro_paper_policy_proposal_v1 import (
    RiskProfile, micro_paper_policy_proposals, verify_micro_paper_policy_proposals)
from backtesting.ninjatrader_shadow_profile_comparison_v1 import CompletedShadowTradeV1, ShadowSide

VERSION = "ninjatrader-three-profile-shadow-ledger-v1"


@dataclass(frozen=True)
class ShadowLedgerEntryV1:
    signal_id: str
    source_report_id: str
    market: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    stop_price: Decimal
    exit_price: Decimal
    quantity: int
    gross_pnl_usd: Decimal
    fees_usd: Decimal
    slippage_usd: Decimal
    net_pnl_usd: Decimal
    ending_equity_usd: Decimal


@dataclass(frozen=True)
class ShadowProfileLedgerV1:
    ledger_id: str
    profile: RiskProfile
    evaluated_at: datetime
    starting_equity_usd: Decimal
    ending_equity_usd: Decimal
    entries: tuple[ShadowLedgerEntryV1, ...]
    skipped_signal_ids: tuple[str, ...]
    session_limit_reached: bool
    comparison_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


def build_three_profile_shadow_ledgers(*, trades: tuple[CompletedShadowTradeV1, ...],
                                       evaluated_at: datetime) -> tuple[ShadowProfileLedgerV1, ...]:
    if (not isinstance(trades, tuple) or len({x.signal_id for x in trades}) != len(trades)
            or evaluated_at.tzinfo is None or evaluated_at.utcoffset() != timedelta(0)):
        raise ValueError("unique immutable trades and UTC evaluation time required")
    if any(not isinstance(x, CompletedShadowTradeV1) or x.trading_authority is not False
           or x.exit_time > evaluated_at for x in trades):
        raise ValueError("verified completed shadow trades required")
    ordered = tuple(sorted(trades, key=lambda x: (x.exit_time, x.signal_id)))
    specs = {x.market: x for x in verified_micro_instrument_specifications()}
    policies = verify_micro_paper_policy_proposals(micro_paper_policy_proposals())
    ledgers = []
    for policy in policies:
        equity = policy.shadow_equity_usd
        peak = equity
        session_start = equity
        session_day = None
        entries = []
        skipped = []
        stopped = False
        for trade in ordered:
            day = trade.entry_time.date()
            if day != session_day:
                session_day, session_start, peak, stopped = day, equity, equity, False
            if stopped:
                skipped.append(trade.signal_id)
                continue
            spec = specs[trade.market]
            risk = abs(trade.entry_price - trade.stop_price) * spec.contract_multiplier
            if risk <= 0:
                raise ValueError("positive stop distance required")
            quantity = min(policy.maximum_contracts_total,
                int((policy.maximum_initial_risk_usd / risk).to_integral_value(rounding=ROUND_FLOOR)))
            if quantity < 1:
                skipped.append(trade.signal_id)
                continue
            direction = Decimal(1) if trade.side is ShadowSide.LONG else Decimal(-1)
            gross = (trade.exit_price - trade.entry_price) * direction * spec.contract_multiplier * quantity
            fees = policy.modeled_fee_per_contract_per_side_usd * 2 * quantity
            slippage = spec.tick_value * policy.modeled_slippage_ticks_per_fill * 2 * quantity
            net = gross - fees - slippage
            equity += net
            peak = max(peak, equity)
            entries.append(ShadowLedgerEntryV1(
                trade.signal_id, trade.source_report_id, trade.market.value, trade.side.value,
                trade.entry_time, trade.exit_time, trade.entry_price, trade.stop_price,
                trade.exit_price, quantity, gross, fees, slippage, net, equity))
            stopped = ((session_start - equity) >= policy.maximum_session_loss_usd
                       or (peak - equity) >= policy.maximum_session_drawdown_usd)
        body = {"version": VERSION, "profile": policy.profile.value,
                "evaluated_at": evaluated_at.isoformat(),
                "signals": [x.signal_id for x in entries], "skipped": skipped,
                "ending_equity": format(equity, "f"), "authority": False}
        identity = hashlib.sha256(json.dumps(body, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
        ledgers.append(ShadowProfileLedgerV1(identity, policy.profile, evaluated_at,
            policy.shadow_equity_usd, equity, tuple(entries), tuple(skipped), stopped))
    if tuple(x.profile for x in ledgers) != tuple(RiskProfile):
        raise ValueError("three isolated profiles required")
    return tuple(ledgers)
