"""Read-only Databento live market-data adapter for the MES PAPER pilot.

* Subscribes to the MES front month (``MES.c.0``, ``stype_in="continuous"``,
  dataset ``GLBX.MDP3``) with two schemas:
    - ``mbp-1``    top of book -> ``simulator.Quote(ts=exchange ts_event,
                   receive_ts=local receipt time, source="LIVE_MBP1")``
    - ``ohlcv-1m`` completed one-minute bars (default), or ``trades``
                   aggregated here into completed M1 bars.
  Bars carry the raw contract symbol (e.g. ``MESZ6``) from the symbol mapping.
* On each COMPLETED M1 bar it calls ``on_bar(bar, quote)`` -- typically
  ``engine.process_bar(bar, live_quote=quote)``. ``quote`` is the latest
  top-of-book only when it is fresh (<= ``max_quote_age_s`` since local
  receipt and since its exchange timestamp) and not crossed; otherwise None,
  so the engine abstains from new entries and executes nothing at a stale
  price. Bars that arrive late (> ``max_bar_delay_s`` after their close) are
  delivered for structure/protective updates with ``quote=None``.
* Optional ``on_quote(quote)`` fires on every fresh top-of-book update so an
  engine can execute pending paper intents on the first executable quote
  after its decision (``run_session`` wires ``engine.process_quote`` if the
  engine defines it).
* Gap detection classifies missing minutes against the CME schedule
  (maintenance, weekend, holiday halts are not faults); stale-quote and
  stale-bar-feed conditions are logged.
* Reconnection with exponential backoff; the session is bounded by an explicit
  ET time window (default 09:00-11:45 ET, hard cap 4 h) on exchange trading
  days only.
* HARD RULE: market data only. This module has no order, submit, cancel or
  position methods and refuses a client object that exposes any.
* The API key is read from ``DATABENTO_API_KEY`` at connect time, passed only
  to the client constructor and never stored, printed or logged.
* ``databento`` is imported lazily, so tests and replay run without it and
  without network. ``run_replay`` feeds archive bars through the same code
  path with modeled quotes (dry run).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable
import json
import os
import re
import threading

from mes_pilot.bars import (Bar, ET, classify_gap, is_exchange_holiday, market_state, validate_bar,
                            CME_EQUITY_EARLY_HALTS_ET, CME_EQUITY_FULL_CLOSURES, UNEXPECTED)
from mes_pilot.simulator import Quote

UTC = timezone.utc
ONE_MIN = timedelta(minutes=1)
UNDEF_PRICE = 2 ** 63 - 1
FIXED_PRICE_SCALE = 1_000_000_000
KEY_ENV = "DATABENTO_API_KEY"
LIVE_QUOTE_SOURCE = "LIVE_MBP1"
REPLAY_QUOTE_SOURCE = "MODELED_REPLAY_FROM_BAR"

_KEY_PATTERN = re.compile(r"db-[A-Za-z0-9]{6,}")
_FORBIDDEN = re.compile(r"(order|submit|place|buy|sell|execute|flatten|liquidat|withdraw|transfer|"
                        r"cancel_all|close_position|open_position|modify)", re.IGNORECASE)


class LiveFeedError(RuntimeError):
    pass


class FatalFeedError(LiveFeedError):
    """Not retryable (entitlement/auth/configuration)."""


class ReadOnlyViolation(LiveFeedError):
    pass


class EngineCallbackError(LiveFeedError):
    pass


def assert_read_only(obj) -> None:
    """Refuse any object exposing order-capable public methods."""
    names = [n for n in dir(obj) if not n.startswith("_")]
    bad = sorted(n for n in names if _FORBIDDEN.search(n) and callable(getattr(obj, n, None)))
    if bad:
        raise ReadOnlyViolation(f"{type(obj).__name__} exposes order-capable methods: {bad}")


@dataclass(frozen=True)
class LiveFeedConfig:
    dataset: str = "GLBX.MDP3"
    symbol: str = "MES.c.0"
    stype_in: str = "continuous"
    quote_schema: str = "mbp-1"
    bar_schema: str = "ohlcv-1m"          # or "trades" (aggregated here)
    tick_size: float = 0.25
    max_quote_age_s: float = 2.0
    max_spread_ticks: int = 2
    window_start: time = time(9, 0)
    window_end: time = time(11, 45)
    max_window_minutes: int = 240
    connect_lead_s: float = 120.0         # may connect this long before window_start
    bar_grace_s: float = 2.0              # trades mode: close a minute this long after its end
    max_bar_delay_s: float = 5.0          # a bar received later than this after its close is LATE
    bar_stale_after_s: float = 90.0       # no completed bar this long after the expected one -> stale
    reconnect_max_attempts: int = 6
    backoff_initial_s: float = 1.0
    backoff_max_s: float = 30.0

    def __post_init__(self):
        if self.bar_schema not in ("ohlcv-1m", "trades"):
            raise ValueError("bar_schema must be 'ohlcv-1m' or 'trades'")
        if self.quote_schema != "mbp-1":
            raise ValueError("quote_schema must be 'mbp-1'")
        minutes = (datetime.combine(date(2000, 1, 3), self.window_end)
                   - datetime.combine(date(2000, 1, 3), self.window_start)).total_seconds() / 60
        if minutes <= 0 or minutes > self.max_window_minutes or self.max_window_minutes > 240:
            raise ValueError("session window must be positive and at most 240 minutes")

    @classmethod
    def from_pilot_config(cls, cfg, **overrides) -> "LiveFeedConfig":
        base = dict(tick_size=cfg.instrument.tick_size, max_quote_age_s=cfg.max_quote_age_s,
                    max_spread_ticks=cfg.max_spread_ticks)
        base.update(overrides)
        return cls(**base)


# --------------------------------------------------------------------------- helpers
def _ns_to_dt(ns: int) -> datetime:
    sec, rem = divmod(int(ns), 1_000_000_000)
    return datetime.fromtimestamp(sec, UTC) + timedelta(microseconds=rem // 1000)


def _dt_to_ns(ts: datetime) -> int:
    delta = ts.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1000


def _px(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, int):
        return None if value >= UNDEF_PRICE else value / FIXED_PRICE_SCALE
    return float(value)


def _top_of_book(rec) -> tuple[float | None, float | None]:
    levels = getattr(rec, "levels", None)
    if levels:
        return _px(levels[0].bid_px), _px(levels[0].ask_px)
    return _px(getattr(rec, "bid_px_00", None)), _px(getattr(rec, "ask_px_00", None))


def session_window(day: date, cfg: LiveFeedConfig) -> tuple[datetime, datetime]:
    return (datetime.combine(day, cfg.window_start, ET).astimezone(UTC),
            datetime.combine(day, cfg.window_end, ET).astimezone(UTC))


def trading_day_problem(day: date, cfg: LiveFeedConfig) -> str | None:
    """Reason the bounded window cannot run on ``day``, or None."""
    if day.weekday() >= 5:
        return "WEEKEND"
    if day in CME_EQUITY_FULL_CLOSURES:
        return "EXCHANGE_CLOSED"
    if is_exchange_holiday(day):
        return "EXCHANGE_HOLIDAY"
    halt = CME_EQUITY_EARLY_HALTS_ET.get(day)
    if halt is not None and halt < cfg.window_end:
        return "EARLY_HALT_INSIDE_WINDOW"
    return None


class _M1Builder:
    """Aggregates trades into M1 bars; a bar completes only after its minute ends."""

    def __init__(self):
        self.start: datetime | None = None
        self.o = self.h = self.l = self.c = None
        self.v = 0.0
        self.contract = ""
        self.last_completed_start: datetime | None = None

    def add(self, ts: datetime, price: float, size: float, contract: str) -> tuple[list[Bar], bool]:
        """Returns (completed bars, accepted?)."""
        minute = ts.replace(second=0, microsecond=0)
        out = self.advance(ts)
        if self.last_completed_start is not None and minute <= self.last_completed_start:
            return out, False  # late trade for a bar already completed -> never reopen it
        if self.start is None:
            self.start, self.o, self.h, self.l, self.v, self.contract = minute, price, price, price, 0.0, contract
        self.h, self.l, self.c = max(self.h, price), min(self.l, price), price
        self.v += size
        return out, True

    def advance(self, exchange_ts: datetime) -> list[Bar]:
        if self.start is not None and exchange_ts >= self.start + ONE_MIN:
            return [self._complete()]
        return []

    def due(self, now: datetime, grace_s: float) -> list[Bar]:
        if self.start is not None and now >= self.start + ONE_MIN + timedelta(seconds=grace_s):
            return [self._complete()]
        return []

    def _complete(self) -> Bar:
        bar = Bar(self.start, self.start + ONE_MIN, self.o, self.h, self.l, self.c, self.v, self.contract, 1)
        self.last_completed_start = self.start
        self.start = None
        return bar


# --------------------------------------------------------------------------- feed
class LiveFeed:
    """Read-only market-data feed. Has no order capability by construction."""

    def __init__(self, on_bar: Callable[[Bar, Quote | None], None], config: LiveFeedConfig | None = None, *,
                 client_factory: Callable[[str], object] | None = None,
                 key_provider: Callable[[], str | None] | None = None,
                 clock: Callable[[], datetime] | None = None, sleep: Callable[[float], None] | None = None,
                 log_path: Path | None = None, pass_receive_ts: bool = True, use_stop_timer: bool = True,
                 on_quote: Callable[[Quote], None] | None = None):
        self.on_bar = on_bar
        self.on_quote = on_quote  # optional: execute pending paper intents on the first fresh quote
        self.cfg = config or LiveFeedConfig()
        self._client_factory = client_factory or _databento_client_factory
        self._key_provider = key_provider or (lambda: os.environ.get(KEY_ENV))
        self.clock = clock or (lambda: datetime.now(UTC))
        self.sleep = sleep or __import__("time").sleep
        self.log_path = Path(log_path) if log_path else None
        self.pass_receive_ts = pass_receive_ts
        self.use_stop_timer = use_stop_timer
        self.instruments: dict[int, str] = {}      # instrument_id -> raw symbol (ours only)
        self.contract: str | None = None
        self.last_quote: Quote | None = None
        self.last_bar: Bar | None = None
        self._builder = _M1Builder()
        self._stale_quote_logged = False
        self._bar_stale_logged_for: datetime | None = None
        self.events: deque = deque(maxlen=2000)
        self.deliveries: deque = deque(maxlen=2000)
        self.stats = {"quotes": 0, "invalid_quotes": 0, "bars_delivered": 0, "bars_late": 0, "bars_rejected": 0,
                      "duplicate_bars": 0, "late_trades": 0, "gaps": 0, "unexpected_gap_minutes": 0,
                      "stale_quote_bars": 0, "reconnects": 0, "heartbeats": 0, "errors": 0}

    # ------------------------------------------------------------------ logging
    @staticmethod
    def _redact(text: str) -> str:
        """Mask anything shaped like a Databento key (the key itself is never kept)."""
        return _KEY_PATTERN.sub("db-***", text)

    def _log(self, kind: str, **fields):
        rec = {"kind": kind, "at": self.clock().isoformat(), **fields}
        rec = json.loads(self._redact(json.dumps(rec, default=str)))
        self.events.append(rec)
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")

    # ------------------------------------------------------------------ quotes
    def quote_status(self, now: datetime | None = None) -> tuple[str, float | None]:
        """FRESH | STALE | NO_QUOTE | INVALID | WIDE_SPREAD, with age in seconds."""
        q = self.last_quote
        if q is None:
            return "NO_QUOTE", None
        now = now or self.clock()
        received = q.receive_ts or q.ts
        age = (now - received).total_seconds()
        latency = (received - q.ts).total_seconds()
        if age > self.cfg.max_quote_age_s or latency > self.cfg.max_quote_age_s:
            return "STALE", age
        if q.bid <= 0 or q.ask < q.bid:
            return "INVALID", age
        if q.spread / self.cfg.tick_size > self.cfg.max_spread_ticks + 1e-9:
            return "WIDE_SPREAD", age
        return "FRESH", age

    def executable_quote(self, now: datetime | None = None) -> Quote | None:
        """Latest quote if fresh and not crossed (a wide spread is still passed;
        the engine refuses new entries on it but may need it to exit)."""
        state, _ = self.quote_status(now)
        if state in ("FRESH", "WIDE_SPREAD"):
            q = self.last_quote
            return q if self.pass_receive_ts else replace(q, receive_ts=None)
        return None

    # ------------------------------------------------------------------ records
    def handle_record(self, rec, received_at: datetime | None = None):
        """Process one Databento (or synthetic) record."""
        received_at = received_at or self.clock()
        name = type(rec).__name__
        if name == "SymbolMappingMsg":
            requested = str(getattr(rec, "stype_in_symbol", ""))
            raw = str(getattr(rec, "stype_out_symbol", ""))
            if requested == self.cfg.symbol:
                iid = getattr(rec, "instrument_id", None)
                if self.contract is not None and raw != self.contract:
                    self._log("CONTRACT_CHANGED", previous=self.contract, current=raw)
                self.instruments = {iid: raw}
                self.contract = raw
                self._log("SYMBOL_MAPPING", requested=requested, raw_symbol=raw, instrument_id=iid)
            return
        if name == "SystemMsg":
            if getattr(rec, "is_heartbeat", False) or "heartbeat" in str(getattr(rec, "code", "")).lower():
                self.stats["heartbeats"] += 1
            else:
                self._log("SYSTEM", code=str(getattr(rec, "code", "")), msg=str(getattr(rec, "msg", "")))
            return
        if name == "ErrorMsg":
            text = str(getattr(rec, "err", "")) or str(getattr(rec, "msg", ""))
            self.stats["errors"] += 1
            self._log("GATEWAY_ERROR", code=str(getattr(rec, "code", "")), err=text)
            if re.search(r"entitle|auth|permission|license|subscription", text, re.IGNORECASE):
                raise FatalFeedError(self._redact(f"gateway refused subscription: {text}"))
            return
        iid = getattr(rec, "instrument_id", None)
        if iid not in self.instruments:
            return
        contract = self.instruments[iid]
        ts_event = _ns_to_dt(getattr(rec, "ts_event"))
        if name == "MBP1Msg":
            bid, ask = _top_of_book(rec)
            if bid is None or ask is None or bid <= 0 or ask < bid:
                self.stats["invalid_quotes"] += 1
            else:
                self.last_quote = Quote(ts_event, bid, ask, LIVE_QUOTE_SOURCE, receive_ts=received_at)
                self.stats["quotes"] += 1
                self._stale_quote_logged = False
                if self.on_quote is not None and self.quote_status(received_at)[0] in ("FRESH", "WIDE_SPREAD"):
                    q = self.last_quote if self.pass_receive_ts else replace(self.last_quote, receive_ts=None)
                    try:
                        self.on_quote(q)
                    except Exception as exc:
                        self._log("ENGINE_CALLBACK_ERROR", error=f"{type(exc).__name__}: {exc}")
                        raise EngineCallbackError(str(exc)) from exc
            if self.cfg.bar_schema == "trades":
                for bar in self._builder.advance(ts_event):
                    self._deliver(bar, received_at)
        elif name == "OHLCVMsg" and self.cfg.bar_schema == "ohlcv-1m":
            start = ts_event
            bar = Bar(start, start + ONE_MIN, _px(rec.open), _px(rec.high), _px(rec.low), _px(rec.close),
                      float(getattr(rec, "volume", 0)), contract, 1)
            early_s = (bar.end - received_at).total_seconds()
            if early_s > 1.0:
                # A bar cannot be complete before its close: partial bar or a badly skewed clock.
                self.stats["bars_rejected"] += 1
                self._log("BAR_RECEIVED_BEFORE_CLOSE", bar_start=bar.start, received_at=received_at)
                return
            if early_s > 0:
                self._log("CLOCK_SKEW_SUSPECTED", bar_end=bar.end, received_at=received_at)
            self._deliver(bar, received_at)
        elif name == "TradeMsg" and self.cfg.bar_schema == "trades":
            done, accepted = self._builder.add(ts_event, _px(rec.price), float(getattr(rec, "size", 0)), contract)
            if not accepted:
                self.stats["late_trades"] += 1
            for bar in done:
                self._deliver(bar, received_at)

    def tick(self, now: datetime | None = None):
        """Clock-driven checks: close a due trades-bar, flag stale bar feed / quotes."""
        now = now or self.clock()
        if self.cfg.bar_schema == "trades":
            for bar in self._builder.due(now, self.cfg.bar_grace_s):
                self._deliver(bar, now)
        if self.last_bar is not None and market_state(self.last_bar.end) == "OPEN":
            overdue = (now - (self.last_bar.end + ONE_MIN)).total_seconds()
            if overdue > self.cfg.bar_stale_after_s and self._bar_stale_logged_for != self.last_bar.end:
                self._bar_stale_logged_for = self.last_bar.end
                self._log("BAR_FEED_STALE", last_bar_end=self.last_bar.end, overdue_s=round(overdue, 3))
        state, age = self.quote_status(now)
        if state == "STALE" and not self._stale_quote_logged:
            self._stale_quote_logged = True
            self._log("QUOTE_STALE", age_s=round(age, 3))

    # ------------------------------------------------------------------ delivery
    def _deliver(self, bar: Bar, received_at: datetime):
        fault = validate_bar(bar)
        if fault:
            self.stats["bars_rejected"] += 1
            self._log("BAR_FAULT", fault=fault, bar_start=bar.start)
            return
        if self.last_bar is not None and bar.start <= self.last_bar.start:
            self.stats["duplicate_bars"] += 1
            return
        if self.last_bar is not None and bar.start > self.last_bar.end:
            segments = classify_gap(self.last_bar.end, bar.start)
            unexpected = sum(s.minutes for s in segments if s.kind == UNEXPECTED)
            self.stats["gaps"] += 1
            self.stats["unexpected_gap_minutes"] += unexpected
            self._log("GAP", start=self.last_bar.end, end=bar.start, unexpected_minutes=unexpected,
                      segments=[{"kind": s.kind, "minutes": s.minutes} for s in segments])
        now = self.clock()
        late = (received_at - bar.end).total_seconds() > self.cfg.max_bar_delay_s
        quote = None if late else self.executable_quote(now)
        q_state, q_age = self.quote_status(now)
        if late:
            self.stats["bars_late"] += 1
            self._log("LATE_BAR", bar_end=bar.end, received_at=received_at)
        elif quote is None:
            self.stats["stale_quote_bars"] += 1
        self.last_bar = bar
        self.deliveries.append({"bar_start": bar.start.isoformat(), "bar_close_ts": bar.end.isoformat(),
                                "received_at": received_at.isoformat(), "decision_ts": now.isoformat(),
                                "contract": bar.contract, "quote_state": q_state,
                                "quote_age_s": None if q_age is None else round(q_age, 4),
                                "quote_exchange_ts": quote.ts.isoformat() if quote else None,
                                "late": late})
        self.stats["bars_delivered"] += 1
        try:
            self.on_bar(bar, quote)
        except Exception as exc:  # engine faults are not feed faults: never retried
            self._log("ENGINE_CALLBACK_ERROR", error=f"{type(exc).__name__}: {exc}")
            raise EngineCallbackError(str(exc)) from exc

    # ------------------------------------------------------------------ session
    def _connect(self):
        key = self._key_provider()
        if not key:
            raise FatalFeedError(f"{KEY_ENV} is not configured")
        try:
            client = self._client_factory(key)
        except Exception as exc:
            raise LiveFeedError(self._redact(f"client construction failed: {type(exc).__name__}: {exc}")) from None
        finally:
            del key
        assert_read_only(client)
        client.subscribe(dataset=self.cfg.dataset, schema=self.cfg.quote_schema,
                         stype_in=self.cfg.stype_in, symbols=[self.cfg.symbol])
        client.subscribe(dataset=self.cfg.dataset, schema=self.cfg.bar_schema,
                         stype_in=self.cfg.stype_in, symbols=[self.cfg.symbol])
        return client

    def run(self, *, session_day: date | None = None, wait_for_window: bool = False) -> dict:
        """Run one bounded session window. Returns a summary dict."""
        now = self.clock()
        day = session_day or now.astimezone(ET).date()
        problem = trading_day_problem(day, self.cfg)
        if problem:
            self._log("REFUSED", reason=problem, session_day=day)
            return self.summary(status=f"REFUSED_{problem}")
        start, end = session_window(day, self.cfg)
        if now >= end:
            self._log("REFUSED", reason="WINDOW_CLOSED", window_end=end)
            return self.summary(status="REFUSED_WINDOW_CLOSED")
        lead = start - timedelta(seconds=self.cfg.connect_lead_s)
        if now < lead:
            if not wait_for_window:
                self._log("REFUSED", reason="BEFORE_WINDOW", window_start=start)
                return self.summary(status="REFUSED_BEFORE_WINDOW")
            self.sleep((lead - now).total_seconds())
        self._log("SESSION_START", session_day=day, window_start=start, window_end=end,
                  symbol=self.cfg.symbol, schemas=[self.cfg.quote_schema, self.cfg.bar_schema])
        failures = 0
        status = "COMPLETED"
        while self.clock() < end:
            client, timer, received_any = None, None, False
            try:
                client = self._connect()
                if self.use_stop_timer:
                    timer = threading.Timer(max(0.0, (end - self.clock()).total_seconds()), _safe_stop, (client,))
                    timer.daemon = True
                    timer.start()
                for rec in client:
                    received_any = True
                    self.handle_record(rec)
                    self.tick()
                    if self.clock() >= end:
                        break
                if self.clock() < end:
                    raise LiveFeedError("stream ended before window end")
            except (FatalFeedError, EngineCallbackError, ReadOnlyViolation) as exc:
                self._log("SESSION_ABORTED", error=f"{type(exc).__name__}: {exc}")
                status = f"ABORTED_{type(exc).__name__}"
                break
            except Exception as exc:  # network / gateway: retry with backoff
                self._log("DISCONNECTED", error=f"{type(exc).__name__}: {exc}")
            finally:
                if timer is not None:
                    timer.cancel()
                if client is not None:
                    _safe_stop(client)
            if self.clock() >= end:
                break
            failures = 1 if received_any else failures + 1
            if failures > self.cfg.reconnect_max_attempts:
                status = "FAILED_RECONNECT_EXHAUSTED"
                self._log("RECONNECT_EXHAUSTED", attempts=failures - 1)
                break
            delay = min(self.cfg.backoff_max_s, self.cfg.backoff_initial_s * 2 ** (failures - 1))
            self.stats["reconnects"] += 1
            self._log("RECONNECTING", attempt=failures, delay_s=delay)
            self.sleep(delay)
        self.tick()
        self._log("SESSION_END", status=status)
        return self.summary(status=status)

    def summary(self, status: str) -> dict:
        return {"status": status, "symbol": self.cfg.symbol, "contract": self.contract,
                "stats": dict(self.stats), "last_bar_end": self.last_bar.end.isoformat() if self.last_bar else None,
                "read_only": True, "order_capability": False}


def _safe_stop(client):
    try:
        client.stop()
    except Exception:
        pass


def _databento_client_factory(key: str):
    try:
        import databento as db  # lazy: only for a real live session
    except ImportError as exc:  # pragma: no cover
        raise FatalFeedError("databento package is not installed") from exc
    return db.Live(key=key)


assert_read_only(LiveFeed)


def run_session(engine, cfg, *, config: LiveFeedConfig | None = None, wait_for_window: bool = True,
                log_path: Path | None = None, **feed_kwargs) -> dict:
    """Run one bounded live PAPER session into ``engine.process_bar(bar, live_quote=quote)``.

    Enforces the live calendar rule on a file-backed engine calendar
    (point-in-time + snapshot retrieved within 7 days). The feed log goes to
    ``<engine.out_dir>/live-feed.jsonl`` unless ``log_path`` is given.
    """
    from mes_pilot.events import LIVE_MAX_SNAPSHOT_AGE

    calendar = getattr(engine, "calendar", None)
    if calendar is not None and getattr(calendar, "snapshots", None):
        calendar.point_in_time = True
        if calendar.max_snapshot_age is None or calendar.max_snapshot_age > LIVE_MAX_SNAPSHOT_AGE:
            calendar.max_snapshot_age = LIVE_MAX_SNAPSHOT_AGE
    feed_cfg = config or LiveFeedConfig.from_pilot_config(cfg)
    if log_path is None and getattr(engine, "out_dir", None) is not None:
        log_path = Path(engine.out_dir) / "live-feed.jsonl"
    on_quote = getattr(engine, "process_quote", None)  # engine hook, if/when it exists
    feed = LiveFeed(lambda bar, quote: engine.process_bar(bar, live_quote=quote), feed_cfg,
                    log_path=log_path, on_quote=on_quote if callable(on_quote) else None, **feed_kwargs)
    return feed.run(wait_for_window=wait_for_window)


# --------------------------------------------------------------------------- synthetic records
# Same class names / fields as databento_dbn records so they share the code path.
@dataclass
class SymbolMappingMsg:
    instrument_id: int
    stype_in_symbol: str
    stype_out_symbol: str
    ts_event: int = 0


@dataclass
class SystemMsg:
    msg: str = ""
    code: str = ""
    is_heartbeat: bool = False
    ts_event: int = 0


@dataclass
class ErrorMsg:
    err: str = ""
    code: str = ""
    ts_event: int = 0


@dataclass
class _Level:
    bid_px: int
    ask_px: int


@dataclass
class MBP1Msg:
    instrument_id: int
    ts_event: int
    ts_recv: int
    levels: list


@dataclass
class OHLCVMsg:
    instrument_id: int
    ts_event: int
    open: int
    high: int
    low: int
    close: int
    volume: int


@dataclass
class TradeMsg:
    instrument_id: int
    ts_event: int
    ts_recv: int
    price: int
    size: int


def mbp1(iid: int, ts: datetime, bid: float, ask: float, recv: datetime | None = None) -> MBP1Msg:
    return MBP1Msg(iid, _dt_to_ns(ts), _dt_to_ns(recv or ts),
                   [_Level(int(round(bid * FIXED_PRICE_SCALE)), int(round(ask * FIXED_PRICE_SCALE)))])


def ohlcv(iid: int, bar: Bar) -> OHLCVMsg:
    s = FIXED_PRICE_SCALE
    return OHLCVMsg(iid, _dt_to_ns(bar.start), int(round(bar.open * s)), int(round(bar.high * s)),
                    int(round(bar.low * s)), int(round(bar.close * s)), int(bar.volume))


def trade(iid: int, ts: datetime, price: float, size: int = 1) -> TradeMsg:
    return TradeMsg(iid, _dt_to_ns(ts), _dt_to_ns(ts), int(round(price * FIXED_PRICE_SCALE)), size)


class ReplayClock:
    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now


class ReplayClient:
    """Dry-run client: yields synthetic Databento-like records for archive bars.

    Per bar: a modeled quote at the bar open (exchange ts = bar start) and one
    at the close (ts = bar end - 1 ms), each ``spread_ticks`` ticks either side
    of the price, then the OHLCV record received ``latency_s`` after the bar
    closes. The replay clock advances to each record's receive time, so the
    feed sees exactly what was knowable when. No network.
    """

    def __init__(self, bars: Iterable[Bar], clock: ReplayClock, *, symbol: str, tick: float = 0.25,
                 spread_ticks: int = 1, latency_s: float = 0.25, instrument_id: int = 1,
                 end_at: datetime | None = None):
        self.bars = list(bars)
        self.clock = clock
        self.symbol = symbol
        self.edge = spread_ticks * tick
        self.latency = timedelta(seconds=latency_s)
        self.iid = instrument_id
        self.end_at = end_at
        self.subscriptions: list[dict] = []
        self.stopped = False

    def subscribe(self, **kwargs):
        self.subscriptions.append(kwargs)

    def stop(self):
        self.stopped = True

    def __iter__(self):
        if self.bars:
            yield SymbolMappingMsg(self.iid, self.symbol, self.bars[0].contract)
        for bar in self.bars:
            if self.stopped:
                return
            for ts, px in ((bar.start, bar.open), (bar.end - timedelta(milliseconds=1), bar.close)):
                self.clock.now = max(self.clock.now, ts + self.latency / 5)
                yield mbp1(self.iid, ts, px - self.edge, px + self.edge, self.clock.now)
            self.clock.now = max(self.clock.now, bar.end + self.latency)
            yield ohlcv(self.iid, bar)
        if self.end_at is not None:
            self.clock.now = max(self.clock.now, self.end_at)  # stream exhausted == window over


def run_replay(bars: Iterable[Bar], on_bar: Callable[[Bar, Quote | None], None], *,
               config: LiveFeedConfig | None = None, spread_ticks: int = 1, latency_s: float = 0.25,
               log_path: Path | None = None) -> tuple[LiveFeed, dict]:
    """Dry run: feed archive M1 bars of ONE session through the live code path.

    Only bars inside the configured ET window are replayed. Quotes are modeled
    (source ``MODELED_REPLAY_FROM_BAR``) and handed to ``on_bar`` with
    ``receive_ts=None`` so the engine measures their age against bar time,
    not the wall clock. Historical bars cannot validate spread.
    """
    cfg = config or LiveFeedConfig()
    bars = sorted(bars, key=lambda b: b.start)
    if not bars:
        raise ValueError("no bars to replay")
    day = bars[-1].start.astimezone(ET).date()
    start, end = session_window(day, cfg)
    window_bars = [b for b in bars if start <= b.start and b.end <= end]
    clock = ReplayClock(start - timedelta(seconds=1))
    client = ReplayClient(window_bars, clock, symbol=cfg.symbol, tick=cfg.tick_size,
                          spread_ticks=spread_ticks, latency_s=latency_s, end_at=end)
    sources = {"n": 0}

    def factory(_key):
        sources["n"] += 1
        if sources["n"] > 1:
            raise FatalFeedError("replay stream exhausted")
        return client

    def relabel(bar, quote):
        on_bar(bar, replace(quote, source=REPLAY_QUOTE_SOURCE) if quote else None)

    feed = LiveFeed(relabel, cfg, client_factory=factory, key_provider=lambda: "REPLAY-NO-KEY",
                    clock=clock, sleep=lambda s: None, log_path=log_path, pass_receive_ts=False,
                    use_stop_timer=False)
    summary = feed.run(session_day=day)
    return feed, summary
