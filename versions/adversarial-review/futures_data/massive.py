from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Callable, Mapping

from .contracts import (ContractSpec, FuturesBar, FuturesRoot, InstrumentKind, Page,
                        RequestManifest, SCHEMA_VERSION, decimal, identity, utc)


MONTH_CODES = {"F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
               "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12}


def parse_outright_ticker(ticker: str, *, contract_year_hint: int | None = None) -> tuple[FuturesRoot, int, int]:
    if not isinstance(ticker, str):
        raise TypeError("ticker must be text")
    text = ticker.strip().upper()
    for root in FuturesRoot:
        if text.startswith(root.value):
            suffix = text[len(root.value):]
            if len(suffix) not in (2, 3, 5) or suffix[0] not in MONTH_CODES or not suffix[1:].isdigit():
                break
            year_digits = suffix[1:]
            if len(year_digits) == 1:
                if contract_year_hint is None or contract_year_hint % 10 != int(year_digits):
                    raise ValueError("one-digit contract year requires matching point-in-time year lineage")
                year = contract_year_hint
            else:
                year = int(year_digits); year = 2000 + year if len(year_digits) == 2 else year
            return root, MONTH_CODES[suffix[0]], year
    raise ValueError("ambiguous, continuous, micro, option, spread, or wrong-root ticker")


@dataclass(frozen=True)
class RetryPolicy:
    calls_per_minute: int = 4
    max_attempts: int = 4
    base_delay_seconds: Decimal = Decimal("1")
    max_delay_seconds: Decimal = Decimal("30")

    def __post_init__(self) -> None:
        if not 1 <= self.calls_per_minute <= 4 or not 1 <= self.max_attempts <= 8:
            raise ValueError("retry/rate budget exceeds Phase 1 limits")


class MassiveFuturesProvider:
    """Provider adapter over an injected transport. It never owns credentials."""
    provider_id = "massive-futures"
    supports_trades = False
    supports_quotes = False

    def __init__(self, transport: Callable[[str, Mapping[str, str]], Page], *,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 sleep: Callable[[float], None] = time.sleep,
                 policy: RetryPolicy = RetryPolicy(), random_seed: int = 0):
        self._transport, self._now, self._sleep, self.policy = transport, now, sleep, policy
        self._random = random.Random(random_seed); self._last_call: float | None = None

    def _call(self, operation: str, params: Mapping[str, str]) -> Page:
        if any("key" in k.lower() or "token" in k.lower() for k in params):
            raise ValueError("credentials must not enter request manifests")
        interval = 60 / self.policy.calls_per_minute
        for attempt in range(self.policy.max_attempts):
            if self._last_call is not None:
                self._sleep(max(0.0, interval - (time.monotonic() - self._last_call)))
            try:
                page = self._transport(operation, dict(params)); self._last_call = time.monotonic()
                if page.status_code == 429 or 500 <= page.status_code < 600:
                    raise TransientResponse(page)
                if page.status_code >= 400:
                    raise ValueError(f"permanent provider response {page.status_code}")
                return page
            except TransientResponse as error:
                if attempt + 1 == self.policy.max_attempts: raise RuntimeError("provider retry budget exhausted")
                retry = error.page.retry_after_seconds
                delay = retry if retry is not None else min(self.policy.max_delay_seconds,
                    self.policy.base_delay_seconds * (Decimal(2) ** attempt))
                jitter = Decimal(str(self._random.random())) * Decimal("0.25")
                self._sleep(float(delay + jitter))
        raise AssertionError("unreachable")

    def _manifest(self, operation: str, params: Mapping[str, str], page: Page, cursor: str | None) -> RequestManifest:
        ordered = tuple(sorted((str(k), str(v)) for k, v in params.items()))
        requested = utc(self._now(), "requested_at"); digest = sha256(page.raw_bytes).hexdigest()
        ident = identity(SCHEMA_VERSION, self.provider_id, operation, ordered, requested.isoformat(), digest)
        return RequestManifest(ident, self.provider_id, operation, ordered, requested, digest,
                               cursor, page.next_cursor, page.status_code,
                               page.rate_limit_remaining, page.retry_after_seconds)

    def _contract(self, row: Mapping[str, object]) -> ContractSpec:
        root, month, year = parse_outright_ticker(str(row.get("ticker", "")))
        if row.get("instrument_type") != "future" or row.get("is_continuous") is not False:
            raise ValueError("only individual outright futures are accepted")
        retrieved = utc(self._now(), "retrieved_at"); ticker = str(row["ticker"]).upper()
        ident = identity(SCHEMA_VERSION, self.provider_id, ticker, root.value, month, year,
                         row["exchange"], row["source_version"])
        return ContractSpec(ident, self.provider_id, ticker, root, month, year, str(row["exchange"]),
            date.fromisoformat(str(row["first_trade_date"])), date.fromisoformat(str(row["last_trade_date"])),
            date.fromisoformat(str(row["expiration_date"])), date.fromisoformat(str(row["settlement_date"])),
            _exact(row["tick_size"], "tick_size"), _exact(row["tick_value"], "tick_value"),
            _exact(row["multiplier"], "multiplier"), str(row["source_version"]), retrieved)

    def discover_contracts(self, root: FuturesRoot, *, as_of: datetime) -> tuple[ContractSpec, ...]:
        utc(as_of, "as_of"); page = self._call("contracts", {"root": root.value, "as_of": as_of.isoformat()})
        result = tuple(self._contract(x) for x in page.records)
        if any(x.root is not root for x in result) or len({x.id for x in result}) != len(result):
            raise ValueError("wrong-root or duplicate contract discovery result")
        return tuple(sorted(result, key=lambda x: (x.expiration_date, x.provider_ticker)))

    def get_contract(self, ticker: str, *, as_of: datetime) -> ContractSpec:
        utc(as_of, "as_of"); parse_outright_ticker(ticker)
        page = self._call("contract", {"ticker": ticker, "as_of": as_of.isoformat()})
        if len(page.records) != 1: raise ValueError("contract identity is ambiguous")
        return self._contract(page.records[0])

    def get_schedule(self, contract: ContractSpec, *, start: date, end: date) -> object:
        if start >= end: raise ValueError("schedule interval must be nonempty")
        return self._call("schedule", {"ticker": contract.provider_ticker, "start": start.isoformat(), "end": end.isoformat()})

    def get_minute_bars(self, contract: ContractSpec, *, start: datetime, end: datetime,
                        cursor: str | None = None) -> tuple[tuple[FuturesBar, ...], RequestManifest]:
        start, end = utc(start, "start"), utc(end, "end")
        if start >= end: raise ValueError("bar request must be [start,end)")
        params = {"ticker": contract.provider_ticker, "start": start.isoformat(), "end": end.isoformat(), "timespan": "minute", "multiplier": "1"}
        if cursor: params["cursor"] = cursor
        page = self._call("minute-bars", params); bars = []
        for row in page.records:
            opened = _epoch_ms(row["timestamp"]); closed = opened + timedelta(minutes=1)
            if not start <= opened < end or closed > end:
                raise ValueError("provider bar outside requested half-open interval")
            finalized = bool(row.get("finalized", False))
            bar_id = identity(SCHEMA_VERSION, contract.id, opened.isoformat(), closed.isoformat())
            bars.append(FuturesBar(bar_id, contract.id, contract.provider_ticker, contract.root,
                opened, closed, _epoch_ms(row.get("provider_timestamp", row["timestamp"])),
                _exact(row["open"], "open"), _exact(row["high"], "high"),
                _exact(row["low"], "low"), _exact(row["close"], "close"),
                _exact(row.get("volume", "0"), "volume"), finalized, contract.source_version))
        ordered = tuple(sorted(bars, key=lambda x: (x.open_time, x.id)))
        if ordered != tuple(bars) or len({x.id for x in ordered}) != len(ordered):
            raise ValueError("provider bars are duplicated or out of order")
        return ordered, self._manifest("minute-bars", params, page, cursor)


class TransientResponse(Exception):
    def __init__(self, page: Page): self.page = page


def _exact(value: object, field: str) -> Decimal:
    if isinstance(value, float): raise TypeError(f"{field} cannot be binary float")
    try: result = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as error: raise ValueError(f"invalid exact {field}") from error
    return decimal(result, field, nonnegative=field == "volume", positive=field != "volume")


def _epoch_ms(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int): raise TypeError("timestamp must be integer epoch milliseconds")
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
