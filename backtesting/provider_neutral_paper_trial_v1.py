"""Provider-neutral, non-executable 15-session ES/NQ paper-trial accounting."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import json

from backtesting.ninjatrader_micro_paper_policy_proposal_v1 import RiskProfile
from backtesting.ninjatrader_shadow_profile_comparison_v1 import CompletedShadowTradeV1
from backtesting.ninjatrader_three_profile_shadow_ledger_v1 import build_three_profile_shadow_ledgers

VERSION = "provider-neutral-paper-trial-v1"


@dataclass(frozen=True, slots=True)
class PaperTrialConfigV1:
    starting_equity_usd: Decimal = Decimal("50000")
    maximum_sessions: int = 15
    comparison_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False

    def __post_init__(self):
        if self.starting_equity_usd != Decimal("50000"):
            raise ValueError("three profiles must start at exactly 50,000 USD")
        if self.maximum_sessions != 15:
            raise ValueError("trial must be bounded to exactly 15 sessions")
        if not self.comparison_only or self.paper_execution_permitted or self.live_trading_permitted or self.trading_authority:
            raise ValueError("provider-neutral trial cannot carry execution authority")


@dataclass(frozen=True, slots=True)
class PaperTradeJournalRowV1:
    sequence: int
    signal_id: str
    source_report_id: str
    market: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    stop_price: Decimal
    exit_price: Decimal
    outcome: str
    session_number: int
    trading_authority: bool = False


@dataclass(frozen=True, slots=True)
class PaperTrialSnapshotV1:
    schema_version: str
    trial_id: str
    evaluated_at: datetime
    session_dates: tuple[str, ...]
    completed_sessions: int
    configured_sessions: int
    journal_rows: tuple[PaperTradeJournalRowV1, ...]
    ledgers: tuple[object, ...]
    comparison_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False


def _utc(value: datetime, name: str):
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be UTC")


def _identity(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, default=str, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_provider_neutral_trial(*, trades: tuple[CompletedShadowTradeV1, ...], evaluated_at: datetime,
                                 config: PaperTrialConfigV1 | None = None) -> PaperTrialSnapshotV1:
    config = config or PaperTrialConfigV1()
    _utc(evaluated_at, "evaluated_at")
    if not isinstance(trades, tuple) or len({x.signal_id for x in trades}) != len(trades):
        raise ValueError("unique immutable completed trades are required")
    if any(not isinstance(x, CompletedShadowTradeV1) or x.trading_authority or x.exit_time > evaluated_at for x in trades):
        raise ValueError("non-authoritative completed trades required")
    ordered = tuple(sorted(trades, key=lambda x: (x.entry_time, x.signal_id)))
    dates = tuple(sorted({x.entry_time.date().isoformat() for x in ordered}))[:config.maximum_sessions]
    allowed = set(dates)
    retained = tuple(x for x in ordered if x.entry_time.date().isoformat() in allowed)
    rows = tuple(PaperTradeJournalRowV1(i, x.signal_id, x.source_report_id, x.market.value,
        x.side.value, x.entry_time, x.exit_time, x.entry_price, x.stop_price, x.exit_price,
        "COMPLETED", dates.index(x.entry_time.date().isoformat()) + 1, False)
        for i, x in enumerate(retained, 1))
    ledgers = build_three_profile_shadow_ledgers(trades=retained, evaluated_at=evaluated_at)
    body = {"version": VERSION, "evaluated_at": evaluated_at.isoformat(),
            "dates": dates, "signals": [x.signal_id for x in rows], "profiles": [x.profile.value for x in ledgers]}
    return PaperTrialSnapshotV1(VERSION, _identity(body), evaluated_at, dates, len(dates),
        config.maximum_sessions, rows, ledgers)


def snapshot_document(snapshot: PaperTrialSnapshotV1) -> dict:
    def clean(value):
        if isinstance(value, Decimal): return format(value, "f")
        if isinstance(value, datetime): return value.isoformat()
        if isinstance(value, Enum): return value.value
        if isinstance(value, tuple): return [clean(item) for item in value]
        if isinstance(value, dict): return {key: clean(item) for key, item in value.items()}
        return value
    return {"schema_version": snapshot.schema_version, "trial_id": snapshot.trial_id,
        "evaluated_at": snapshot.evaluated_at.isoformat(), "session_dates": list(snapshot.session_dates),
        "completed_sessions": snapshot.completed_sessions, "configured_sessions": snapshot.configured_sessions,
        "journal_rows": [{k: (v.isoformat() if isinstance(v, datetime) else format(v, "f") if isinstance(v, Decimal) else v)
                          for k, v in asdict(row).items()} for row in snapshot.journal_rows],
        "ledgers": [clean(asdict(ledger)) for ledger in snapshot.ledgers], "comparison_only": True,
        "paper_execution_permitted": False, "live_trading_permitted": False, "trading_authority": False}
