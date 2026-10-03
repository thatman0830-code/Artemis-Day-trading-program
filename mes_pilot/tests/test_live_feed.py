"""live_feed.py with a fake Databento client: subscriptions, quote freshness, bar
completion, gaps, reconnect/backoff, window guard, key handling, no order
capability, dry-run replay. No network, no real API key."""
from __future__ import annotations

import inspect
import importlib.util
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import mes_pilot.live_feed as lf
from mes_pilot.bars import Bar, ET, load_archive_sessions
from mes_pilot.live_feed import (FatalFeedError, LiveFeed, LiveFeedConfig, ReadOnlyViolation, ReplayClock,
                                 SymbolMappingMsg, ErrorMsg, assert_read_only, mbp1, ohlcv, run_replay, trade)

UTC = timezone.utc
ONE = timedelta(minutes=1)
REPO = Path(__file__).resolve().parents[2]
FORWARD = REPO / "data" / "futures_forward" / "ES"
DAY = date(2026, 9, 29)  # Tuesday
FAKE_KEY = "db-FAKEKEYFORTESTS0123"


def et(hh, mm=0, ss=0, ms=0, day=DAY) -> datetime:
    return datetime.combine(day, time(hh, mm, ss, ms * 1000), ET).astimezone(UTC)


def bar(start, o=6500.0, h=6501.0, low=6499.0, c=6500.5, contract="MESZ6") -> Bar:
    return Bar(start, start + ONE, o, h, low, c, 100.0, contract, 1)


class FakeClient:
    """Yields (receive_time, record) pairs, advancing the shared clock."""

    def __init__(self, script, clock: ReplayClock, end_at=None):
        self.script, self.clock, self.end_at = script, clock, end_at
        self.subscriptions, self.stopped = [], False

    def subscribe(self, **kw):
        self.subscriptions.append(kw)

    def stop(self):
        self.stopped = True

    def __iter__(self):
        for at, rec in self.script:
            self.clock.now = at
            yield rec
        if self.end_at:
            self.clock.now = self.end_at


def make_feed(script=(), *, config=None, start=None, end_at=None, **kw):
    clock = ReplayClock(start or et(9, 0))
    got, clients = [], []

    def factory(key):
        assert key == FAKE_KEY
        c = FakeClient(list(script), clock, end_at)
        clients.append(c)
        return c

    feed = LiveFeed(lambda b, q: got.append((b, q)), config or LiveFeedConfig(), client_factory=factory,
                    key_provider=lambda: FAKE_KEY, clock=clock, sleep=lambda s: None, use_stop_timer=False, **kw)
    return feed, got, clients, clock


MAP = (et(9, 0), SymbolMappingMsg(7, "MES.c.0", "MESZ6"))


# ----------------------------------------------------------------------------- read-only rule
def test_no_order_capability():
    assert_read_only(LiveFeed)
    names = [n for n, _ in inspect.getmembers(LiveFeed) if not n.startswith("_")]
    for bad in ("order", "submit", "buy", "sell", "cancel", "flatten", "position"):
        assert not any(bad in n.lower() for n in names), names
    source = Path(lf.__file__).read_text(encoding="utf-8")
    assert "Historical(" not in source and "requests" not in source

    class OrderClient(FakeClient):
        def submit_order(self, *a):
            raise AssertionError("must never be called")

    with pytest.raises(ReadOnlyViolation):
        assert_read_only(OrderClient([], ReplayClock(et(9))))
    clock = ReplayClock(et(9, 0))
    feed = LiveFeed(lambda b, q: None, client_factory=lambda k: OrderClient([], clock), key_provider=lambda: FAKE_KEY,
                    clock=clock, sleep=lambda s: None, use_stop_timer=False)
    assert feed.run()["status"] == "ABORTED_ReadOnlyViolation"


def test_databento_imported_lazily():
    code = "import sys, mes_pilot.live_feed; print('databento' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "False", out.stderr


def test_subscriptions_are_mes_continuous_market_data_only():
    feed, got, clients, _ = make_feed([MAP], end_at=et(11, 45))
    assert feed.run()["status"] == "COMPLETED"
    assert clients[0].subscriptions == [
        {"dataset": "GLBX.MDP3", "schema": "mbp-1", "stype_in": "continuous", "symbols": ["MES.c.0"]},
        {"dataset": "GLBX.MDP3", "schema": "ohlcv-1m", "stype_in": "continuous", "symbols": ["MES.c.0"]}]
    assert clients[0].stopped


# ----------------------------------------------------------------------------- key handling
def test_missing_key_is_fatal_and_key_never_logged(tmp_path):
    clock = ReplayClock(et(9, 0))
    feed = LiveFeed(lambda b, q: None, key_provider=lambda: None, clock=clock, sleep=lambda s: None,
                    use_stop_timer=False)
    assert feed.run()["status"] == "ABORTED_FatalFeedError"

    def leaky_factory(key):
        raise ConnectionError(f"auth failed for {key}")

    log = tmp_path / "feed.jsonl"
    feed = LiveFeed(lambda b, q: None, LiveFeedConfig(reconnect_max_attempts=1), client_factory=leaky_factory,
                    key_provider=lambda: FAKE_KEY, clock=clock, sleep=lambda s: None, log_path=log,
                    use_stop_timer=False)
    feed.run()
    text = log.read_text(encoding="utf-8")
    assert FAKE_KEY not in text and "db-***" in text
    assert FAKE_KEY not in repr(feed.__dict__)


# ----------------------------------------------------------------------------- quotes
def test_quote_uses_exchange_ts_and_local_receipt_and_goes_stale():
    feed, got, _, clock = make_feed()
    feed.handle_record(MAP[1], MAP[0])
    q_ts, q_recv = et(9, 59, 59, 500), et(9, 59, 59, 700)
    clock.now = q_recv
    feed.handle_record(mbp1(7, q_ts, 6500.0, 6500.25, q_recv), q_recv)
    q = feed.last_quote
    assert (q.ts, q.receive_ts, q.source, q.bid, q.ask) == (q_ts, q_recv, "LIVE_MBP1", 6500.0, 6500.25)
    clock.now = et(10, 0, 1, 700)                 # exactly 2.0 s after receipt -> still fresh
    assert feed.quote_status()[0] == "FRESH"
    clock.now = et(10, 0, 1, 701)
    assert feed.quote_status()[0] == "STALE" and feed.executable_quote() is None
    # bar delivered with a stale quote -> engine gets None (abstains, no fills at stale prices)
    feed.handle_record(ohlcv(7, bar(et(9, 59))), clock.now)
    assert got[-1][1] is None and feed.stats["stale_quote_bars"] == 1


def test_quote_with_old_exchange_timestamp_is_stale_and_crossed_is_rejected():
    feed, got, _, clock = make_feed()
    feed.handle_record(MAP[1], MAP[0])
    clock.now = et(10, 0, 0)
    feed.handle_record(mbp1(7, et(9, 59, 55), 6500.0, 6500.25, clock.now), clock.now)  # 5 s exchange->receipt
    assert feed.quote_status()[0] == "STALE"
    feed.handle_record(mbp1(7, et(10, 0, 0), 6500.5, 6500.25, clock.now), clock.now)   # crossed
    assert feed.stats["invalid_quotes"] == 1
    feed.handle_record(mbp1(7, et(10, 0, 0), 6500.0, 6501.0, clock.now), clock.now)    # 4 ticks wide
    assert feed.quote_status()[0] == "WIDE_SPREAD" and feed.executable_quote() is not None


def test_delayed_quote_burst_is_blocked_and_logged_once_per_episode():
    feed, _, _, clock = make_feed()
    feed.handle_record(MAP[1], MAP[0])
    start = et(10, 0)
    for n in range(5):
        clock.now = start + timedelta(milliseconds=n)
        feed.handle_record(mbp1(7, clock.now - timedelta(seconds=10), 6500.0, 6500.25), clock.now)
        assert feed.executable_quote(clock.now) is None
        feed.tick(clock.now)
    stale = [e for e in feed.events if e["kind"] == "QUOTE_STALE"]
    assert len(stale) == 1
    assert stale[0]["cause"] == "TRANSPORT_DELAY" and stale[0]["exchange_to_receipt_s"] == 10.0
    assert feed.stats["delayed_quotes"] == 5 and feed.stats["max_quote_transport_delay_s"] == 10.0

    clock.now = start + timedelta(seconds=1)
    feed.handle_record(mbp1(7, clock.now, 6500.0, 6500.25), clock.now)
    assert feed.executable_quote(clock.now) is not None
    clock.now += timedelta(seconds=1)
    feed.handle_record(mbp1(7, clock.now - timedelta(seconds=10), 6500.0, 6500.25), clock.now)
    feed.tick(clock.now)
    assert len([e for e in feed.events if e["kind"] == "QUOTE_STALE"]) == 2


def test_records_for_unmapped_instruments_ignored():
    feed, got, _, clock = make_feed()
    feed.handle_record(SymbolMappingMsg(9, "ES.c.0", "ESZ6"), et(9))
    feed.handle_record(mbp1(9, et(9), 6500.0, 6500.25), et(9))
    assert feed.last_quote is None and feed.contract is None


# ----------------------------------------------------------------------------- bars
def test_ohlcv_bar_delivered_once_complete_with_fresh_quote():
    feed, got, _, clock = make_feed()
    feed.handle_record(MAP[1], MAP[0])
    clock.now = et(10, 0, 59, 900)
    feed.handle_record(mbp1(7, et(10, 0, 59, 800), 6500.25, 6500.5, clock.now), clock.now)
    clock.now = et(10, 1, 0, 300)
    feed.handle_record(ohlcv(7, bar(et(10, 0))), clock.now)
    b, q = got[-1]
    assert b.start == et(10, 0) and b.end == et(10, 1) and b.contract == "MESZ6" and b.tf == 1
    assert (b.open, b.high, b.low, b.close) == (6500.0, 6501.0, 6499.0, 6500.5)
    assert q is not None and q.ts <= clock.now
    d = feed.deliveries[-1]
    assert d["bar_close_ts"] == et(10, 1).isoformat() and d["decision_ts"] == clock.now.isoformat()
    # duplicate is dropped, and a bar "received" well before its close is refused
    feed.handle_record(ohlcv(7, bar(et(10, 0))), clock.now)
    feed.handle_record(ohlcv(7, bar(et(10, 1))), et(10, 1, 30))
    assert len(got) == 1 and feed.stats["duplicate_bars"] == 1 and feed.stats["bars_rejected"] == 1


def test_slightly_early_ohlcv_bar_waits_until_its_stated_close():
    feed, got, _, clock = make_feed()
    feed.handle_record(MAP[1], MAP[0])
    clock.now = et(10, 0, 59, 800)
    feed.handle_record(ohlcv(7, bar(et(10, 0))), clock.now)
    feed.tick(clock.now)
    assert got == [] and feed.stats["bars_held_until_close"] == 1
    assert any(e["kind"] == "BAR_HELD_UNTIL_CLOSE" for e in feed.events)

    clock.now = et(10, 0, 59, 999)
    feed.tick(clock.now)
    assert got == []
    clock.now = et(10, 1, 0, 50)
    feed.tick(clock.now)
    assert len(got) == 1 and feed.deliveries[-1]["decision_ts"] == clock.now.isoformat()
    assert feed.deliveries[-1]["bar_close_ts"] <= feed.deliveries[-1]["decision_ts"]


def test_late_bar_delivered_without_quote():
    feed, got, _, clock = make_feed()
    feed.handle_record(MAP[1], MAP[0])
    clock.now = et(10, 1, 10)
    feed.handle_record(mbp1(7, et(10, 1, 10), 6500.0, 6500.25, clock.now), clock.now)
    feed.handle_record(ohlcv(7, bar(et(10, 0))), clock.now)   # 10 s after close
    assert got[-1][1] is None and feed.stats["bars_late"] == 1


def test_trades_mode_completes_bar_only_after_minute_end():
    cfg = LiveFeedConfig(bar_schema="trades")
    feed, got, _, clock = make_feed(config=cfg)
    feed.handle_record(MAP[1], MAP[0])
    for sec, px in ((5, 6500.0), (20, 6502.0), (40, 6499.5), (59, 6501.0)):
        clock.now = et(10, 0, sec)
        feed.handle_record(trade(7, clock.now, px, 2), clock.now)
        feed.tick()
    assert got == []                                        # never emitted before 10:01
    clock.now = et(10, 1, 1)
    feed.tick()                                             # within grace: still waiting
    assert got == []
    clock.now = et(10, 1, 2)
    feed.tick()
    b, _ = got[-1]
    assert (b.start, b.open, b.high, b.low, b.close, b.volume) == (et(10, 0), 6500.0, 6502.0, 6499.5, 6501.0, 8.0)
    feed.handle_record(trade(7, et(10, 0, 59, 999), 6600.0), clock.now)   # late trade: never reopens
    assert feed.stats["late_trades"] == 1
    # a quote with exchange ts in the next minute also completes the open bar
    feed.handle_record(trade(7, et(10, 1, 3), 6501.25), et(10, 1, 3))
    feed.handle_record(mbp1(7, et(10, 2, 0, 5), 6501.0, 6501.25), et(10, 2, 0, 50))
    assert got[-1][0].start == et(10, 1) and len(got) == 2


def test_gap_detection_and_stale_bar_feed():
    feed, got, _, clock = make_feed()
    feed.handle_record(MAP[1], MAP[0])
    feed.handle_record(ohlcv(7, bar(et(10, 0))), et(10, 1, 0, 200))
    feed.handle_record(ohlcv(7, bar(et(10, 3))), et(10, 4, 0, 200))
    gap = [e for e in feed.events if e["kind"] == "GAP"][-1]
    assert gap["unexpected_minutes"] == 2 and feed.stats["unexpected_gap_minutes"] == 2
    clock.now = et(10, 6, 31)
    feed.tick()
    assert any(e["kind"] == "BAR_FEED_STALE" for e in feed.events)


def test_entitlement_error_aborts_without_retry():
    script = [MAP, (et(9, 0, 1), ErrorMsg(err="User is not entitled to dataset GLBX.MDP3 schema mbp-1"))]
    feed, got, clients, _ = make_feed(script)
    assert feed.run()["status"] == "ABORTED_FatalFeedError" and len(clients) == 1


def test_engine_callback_error_is_not_retried():
    script = [MAP, (et(9, 1, 0, 200), ohlcv(7, bar(et(9, 0))))]
    clock = ReplayClock(et(9, 0))
    clients = []

    def boom(b, q):
        raise RuntimeError("engine fault")

    def factory(key):
        clients.append(FakeClient(script, clock))
        return clients[-1]

    feed = LiveFeed(boom, client_factory=factory, key_provider=lambda: FAKE_KEY, clock=clock,
                    sleep=lambda s: None, use_stop_timer=False)
    assert feed.run()["status"] == "ABORTED_EngineCallbackError" and len(clients) == 1


# ----------------------------------------------------------------------------- reconnect / window guard
def test_reconnect_with_exponential_backoff_then_success():
    clock = ReplayClock(et(9, 0))
    sleeps, attempts = [], []
    cfg = LiveFeedConfig(backoff_initial_s=1.0, backoff_max_s=4.0, reconnect_max_attempts=5)

    def factory(key):
        attempts.append(1)
        if len(attempts) <= 3:
            raise ConnectionError("gateway down")
        return FakeClient([MAP, (et(9, 1, 0, 200), ohlcv(7, bar(et(9, 0))))], clock, end_at=et(11, 45))

    feed = LiveFeed(lambda b, q: None, cfg, client_factory=factory, key_provider=lambda: FAKE_KEY, clock=clock,
                    sleep=sleeps.append, use_stop_timer=False)
    summary = feed.run()
    assert summary["status"] == "COMPLETED" and sleeps == [1.0, 2.0, 4.0]
    assert summary["stats"]["reconnects"] == 3 and summary["stats"]["bars_delivered"] == 1


def test_reconnect_exhaustion():
    clock = ReplayClock(et(9, 0))
    sleeps = []

    def factory(key):
        raise ConnectionError("down")

    feed = LiveFeed(lambda b, q: None, LiveFeedConfig(reconnect_max_attempts=3, backoff_max_s=30.0),
                    client_factory=factory, key_provider=lambda: FAKE_KEY, clock=clock, sleep=sleeps.append,
                    use_stop_timer=False)
    assert feed.run()["status"] == "FAILED_RECONNECT_EXHAUSTED" and sleeps == [1.0, 2.0, 4.0]


@pytest.mark.parametrize("now,day,status", [
    (et(12, 0), None, "REFUSED_WINDOW_CLOSED"),
    (et(7, 0), None, "REFUSED_BEFORE_WINDOW"),
    (et(9, 0, day=date(2026, 10, 3)), None, "REFUSED_WEEKEND"),
    (et(9, 0, day=date(2026, 9, 7)), None, "REFUSED_EXCHANGE_HOLIDAY"),          # Labor Day
    (et(9, 0, day=date(2026, 12, 25)), None, "REFUSED_EXCHANGE_CLOSED"),
])
def test_window_guard(now, day, status):
    feed, _, clients, clock = make_feed(start=now)
    assert feed.run(session_day=day)["status"] == status
    assert clients == []


def test_window_config_is_bounded():
    with pytest.raises(ValueError):
        LiveFeedConfig(window_start=time(9, 0), window_end=time(16, 0))
    with pytest.raises(ValueError):
        LiveFeedConfig(window_start=time(11, 0), window_end=time(10, 0))
    with pytest.raises(ValueError):
        LiveFeedConfig(bar_schema="mbp-10")


def test_wait_for_window_sleeps_until_connect_lead():
    sleeps = []
    clock = ReplayClock(et(8, 0))
    feed = LiveFeed(lambda b, q: None, client_factory=lambda k: FakeClient([MAP], clock, end_at=et(11, 45)),
                    key_provider=lambda: FAKE_KEY, clock=clock, sleep=sleeps.append, use_stop_timer=False)
    assert feed.run(wait_for_window=True)["status"] == "COMPLETED"
    assert sleeps == [(et(8, 58) - et(8, 0)).total_seconds()]


# ----------------------------------------------------------------------------- dry-run replay
def test_replay_feeds_only_window_bars_with_causal_modeled_quotes():
    start = et(8, 55)
    bars = [bar(start + i * ONE, o=6500 + i, h=6501 + i, low=6499 + i, c=6500.5 + i, contract="ESZ6")
            for i in range(60)]
    got = []
    feed, summary = run_replay(bars, lambda b, q: got.append((b, q)))
    assert summary["status"] == "COMPLETED"
    assert got[0][0].start == et(9, 0) and len(got) == 55          # 09:00..09:54 starts
    for b, q in got:
        assert q is not None and q.source == "MODELED_REPLAY_FROM_BAR" and q.receive_ts is None
        assert q.ts <= b.end                                       # quote known by the decision time
        assert q.bid == b.close - 0.25 and q.ask == b.close + 0.25
    assert all(d["received_at"] > d["bar_close_ts"] for d in feed.deliveries)


@pytest.mark.skipif(not FORWARD.exists(), reason="forward archive not present")
def test_replay_real_forward_session():
    sess = load_archive_sessions([FORWARD], start=date(2026, 9, 29))[0]
    got = []
    feed, summary = run_replay(sess.bars, lambda b, q: got.append((b, q)))
    assert summary["status"] == "COMPLETED" and summary["contract"] == "ESZ6"
    assert got[0][0].start == et(9, 0) and got[-1][0].end <= et(11, 45)
    assert summary["stats"]["unexpected_gap_minutes"] == 0


def test_run_session_wires_engine_and_enforces_live_calendar(tmp_path):
    from datetime import timedelta as td
    from mes_pilot.events import CalendarSnapshot, EventCalendar

    class FakeEngine:
        def __init__(self):
            self.out_dir = tmp_path
            self.calls = []
            self.calendar = EventCalendar([], set(), "x", snapshots=[
                CalendarSnapshot(date(2026, 9, 27), date(2026, 10, 3), et(9, 0, day=date(2026, 9, 28)), "s", ())])

        def process_bar(self, bar, live_quote=None, **kw):
            self.calls.append((bar, live_quote))
            self.kw = kw

    class Cfg:  # minimal PilotConfig surface used by LiveFeedConfig.from_pilot_config
        class instrument:
            tick_size = 0.25
        max_quote_age_s = 2.0
        max_spread_ticks = 2

    eng = FakeEngine()
    clock = ReplayClock(et(9, 0))
    script = [MAP, (et(9, 0, 59, 900), mbp1(7, et(9, 0, 59, 800), 6500.0, 6500.25, et(9, 0, 59, 900))),
              (et(9, 1, 0, 200), ohlcv(7, bar(et(9, 0))))]
    summary = lf.run_session(eng, Cfg, client_factory=lambda k: FakeClient(script, clock, end_at=et(11, 45)),
                             key_provider=lambda: FAKE_KEY, clock=clock, sleep=lambda s: None, use_stop_timer=False)
    assert summary["status"] == "COMPLETED" and len(eng.calls) == 1
    b, q = eng.calls[0]
    assert b.contract == "MESZ6" and q.source == "LIVE_MBP1" and q.receive_ts == et(9, 0, 59, 900)
    assert eng.calendar.point_in_time and eng.calendar.max_snapshot_age == td(days=7)
    assert eng.kw == {"context": False, "continuity": None, "source": "MES_LIVE"}
    assert (tmp_path / "live-feed.jsonl").exists()


def test_on_quote_hook_receives_only_fresh_quotes():
    seen = []
    feed, got, _, clock = make_feed(on_quote=seen.append)
    feed.handle_record(MAP[1], MAP[0])
    feed.handle_record(mbp1(7, et(10, 0, 0), 6500.0, 6500.25), et(10, 0, 0, 100))
    feed.handle_record(mbp1(7, et(10, 0, 1), 6500.0, 6500.25), et(10, 0, 4))      # 3 s in transit: stale
    assert [q.ts for q in seen] == [et(10, 0, 0)] and seen[0].source == "LIVE_MBP1"


def test_live_cli_reports_feed_failure_after_finalizing_ledger(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mes_pilot_cli_test", REPO / "scripts" / "run_mes_paper_pilot.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    finished = []

    class Engine:
        def __init__(self, *_args, **_kwargs):
            self.warmup = False
            _kwargs["out_dir"].mkdir(parents=True, exist_ok=True)

        def end_warmup(self):
            pass

        def finish(self):
            finished.append(True)

    cfg = SimpleNamespace(splits=SimpleNamespace(protected_oos=(date(2026, 6, 1), date(2026, 8, 26))),
                          strategy=SimpleNamespace(volatility_sessions=60))
    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "PilotEngine", Engine)
    monkeypatch.setattr(cli, "load_archive_sessions", lambda *_a, **_kw: [])
    monkeypatch.setattr(cli, "_print_report", lambda *_a: None)
    monkeypatch.setattr(cli, "OUT", tmp_path)
    monkeypatch.setattr(cli, "CAL_DIR", tmp_path / "missing-calendar")
    monkeypatch.setattr(lf, "run_session", lambda *_a, **_kw: {"status": "ABORTED_FatalFeedError", "stats": {}})

    with pytest.raises(RuntimeError, match="ABORTED_FatalFeedError"):
        cli.cmd_live(SimpleNamespace(mode="PAPER_AUTO", prop_dry_run=False))
    assert finished == [True]
    assert (tmp_path / "autonomous_paper" / "live-feed-summary.json").exists()
