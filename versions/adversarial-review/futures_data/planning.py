from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from .archive import archive_path
from .contracts import ContractSpec, FuturesRoot, identity, utc


class CollectorHealth(str, Enum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    GAPPED = "GAPPED"
    STOPPED = "STOPPED"


@dataclass(frozen=True)
class PlannedRequest:
    contract_id: str
    ticker: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class BackfillPlan:
    id: str
    roots: tuple[FuturesRoot, ...]
    start: datetime
    end: datetime
    contracts: tuple[ContractSpec, ...]
    requests: tuple[PlannedRequest, ...]
    expected_calls: int
    estimated_rows: int
    estimated_bytes: int
    minimum_duration_minutes: int
    archive_paths: tuple[str, ...]
    abort_failure_limit: int
    licensing_confirmation_required: bool
    dry_run_only: bool


def create_backfill_plan(*, repository: Path, contracts: tuple[ContractSpec, ...],
                         start: datetime, end: datetime, window_days: int = 7,
                         abort_failure_limit: int = 4) -> BackfillPlan:
    start, end = utc(start, "start"), utc(end, "end")
    if start >= end or end - start > timedelta(days=366 * 2):
        raise ValueError("backfill must be nonempty and at most two years")
    if not contracts or any(x.root not in (FuturesRoot.ES, FuturesRoot.NQ) for x in contracts):
        raise ValueError("only a resolved ES/NQ contract list is allowed")
    if len({x.id for x in contracts}) != len(contracts): raise ValueError("duplicate contract plan")
    requests = []
    for contract in contracts:
        cursor = max(start, datetime.combine(contract.first_trade_date, datetime.min.time(), tzinfo=start.tzinfo))
        contract_end = min(end, datetime.combine(contract.expiration_date + timedelta(days=1), datetime.min.time(), tzinfo=end.tzinfo))
        while cursor < contract_end:
            right = min(contract_end, cursor + timedelta(days=window_days))
            requests.append(PlannedRequest(contract.id, contract.provider_ticker, cursor, right)); cursor = right
    roots = tuple(sorted({x.root for x in contracts}, key=lambda x: x.value))
    calls = len(requests); rows = sum(int((x.end-x.start).total_seconds()/60) for x in requests)
    paths = tuple(str(archive_path(repository, x)) for x in roots)
    ident = identity("futures-backfill-plan-v1", *(x.id for x in contracts), start.isoformat(), end.isoformat(), window_days)
    return BackfillPlan(ident, roots, start, end, contracts, tuple(requests), calls, rows,
                        rows * 240, (calls + 3)//4, paths, abort_failure_limit, True, True)


@dataclass(frozen=True)
class ForwardCollectorPolicy:
    availability_delay: timedelta
    safety_buffer: timedelta
    max_failures: int = 4
    schedule_enabled: bool = False
    research_only: bool = True

    def __post_init__(self) -> None:
        if self.availability_delay < timedelta(0) or self.safety_buffer <= timedelta(0):
            raise ValueError("delay and safety buffer must be explicit")
        if self.max_failures < 1 or self.schedule_enabled or not self.research_only:
            raise ValueError("Phase 1 collector must be bounded, unscheduled, and research-only")

    def finalized_cutoff(self, now: datetime) -> datetime:
        return utc(now, "now") - self.availability_delay - self.safety_buffer


PROHIBITED_CAPABILITIES = frozenset({"orders", "positions", "accounts", "wallets", "signing", "execution"})

