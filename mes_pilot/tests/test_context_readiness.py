"""Repair 2026-10-02 regressions: history bridge, coverage/readiness, partial buckets, context-replay safety,
durable evidence corrections. Synthetic data only (labelled SYNTHETIC_TEST); no network."""
from __future__ import annotations

import json
import random
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

import mes_pilot.history_bridge as hb
from mes_pilot.bars import ET, Bar, market_state
from mes_pilot.coverage import (CoverageTracker, bar_completeness, open_minute_starts, open_minutes,
                                previous_trading_date, session_bounds)
from mes_pilot.engine import PilotEngine, parse_contract, same_price_series
from mes_pilot.events import EventCalendar
from mes_pilot.ledger import EvidenceLedger
from mes_pilot.live_feed import LiveFeed, LiveFeedConfig, ReplayClock, SymbolMappingMsg, SystemMsg, mbp1, ohlcv
from mes_pilot.risk import PilotRiskManager
from mes_pilot.simulator import Quote

UTC = timezone.utc
ONE = timedelta(minutes=1)
REPO = Path(__file__).resolve().parents[2]


def et(day, hh, mm=0, ss=0) -> datetime:
    return datetime.combine(day, time(hh, mm, ss), ET).astimezone(UTC)


def m1(start, price, contract="MESZ6", vol=100.0) -> Bar:
    o = price
    c = price + 0.25 * ((int(start.timestamp() // 60) % 3) - 1)
    return Bar(start, start + ONE, o, max(o, c) + 0.25, min(o, c) - 0.25, c, vol, contract, 1)


def session_bars(day: date, *, start=None, end=None, seed=0, base=6500.0, contract="MESZ6"):
    """Every scheduled-open minute of trade date ``day`` (or [start, end)), deterministic random walk."""
    s, e = session_bounds(day)
    rnd = random.Random(seed + day.toordinal())
    price, out = base + rnd.randint(-40, 40), []
    for t in open_minute_starts(start or s, end or e):
        price = round((price + rnd.choice((-0.5, -0.25, 0, 0.25, 0.5))) * 4) / 4
        out.append(m1(t, price, contract))
    return out


# ============================================================ coverage: closures, gaps, watermark, evidence
def test_closures_are_not_gaps_and_dst_boundaries():
    # 14:00-18:00 ET H4 bucket = 180 open minutes (17:00-18:00 maintenance)
    d = date(2026, 9, 29)
    assert open_minutes(et(d, 14), et(d, 18)) == 180
    # Friday 17:00 -> Sunday 18:00 is entirely closed
    assert open_minutes(et(date(2026, 10, 2), 17), et(date(2026, 10, 4), 18)) == 0
    # DST fall-back weekend and spring-forward weekend: closed, no synthetic minutes
    assert open_minutes(et(date(2026, 10, 30), 17), et(date(2026, 11, 1), 18)) == 0
    assert open_minutes(et(date(2026, 3, 6), 17), et(date(2026, 3, 8), 18)) == 0
    # early halt 2026-11-27 13:15 ET: nothing open until 18:00
    assert open_minutes(et(date(2026, 11, 27), 13, 15), et(date(2026, 11, 27), 18)) == 0
    # Monday trade date's prior trading session is Friday
    assert previous_trading_date(date(2026, 10, 5)) == date(2026, 10, 2)


def test_oct2_gap_is_898_unexpected_minutes_and_partial_buckets_incomplete():
    tr = CoverageTracker()
    d1, d2 = date(2026, 10, 1), date(2026, 10, 2)
    for b in session_bars(d1):
        tr.observe(b, "ARCHIVE_SESSION", "ES_ARCHIVE_PROXY")
    assert tr.last_bar_end == et(d1, 17)
    gaps = tr.observe(m1(et(d2, 8, 58), 6600), None, "MES_LIVE")
    assert len(gaps) == 1 and gaps[0].open_minutes == 898
    tr.observe(m1(et(d2, 8, 59), 6600), "SAME_STREAM", "MES_LIVE")
    h1 = Bar(et(d2, 8), et(d2, 9), 1, 1, 1, 1, 1, "MESZ6", 60)
    h4 = Bar(et(d2, 6), et(d2, 10), 1, 1, 1, 1, 1, "MESZ6", 240)
    c1 = bar_completeness(tr, h1)
    assert c1["complete"] is False and c1["expected_open_minutes"] == 60 and c1["known_minutes"] == 2
    for t in open_minute_starts(et(d2, 9), et(d2, 10)):
        tr.observe(m1(t, 6600), "SAME_STREAM", "MES_LIVE")
    c4 = bar_completeness(tr, h4)
    assert c4["complete"] is False and c4["known_minutes"] == 62 and c4["expected_open_minutes"] == 240
    # a full bucket after the gap is complete
    assert tr.is_complete(et(d2, 9), et(d2, 10))


def test_watermark_rejects_unobserved_trailing_interval():
    tr = CoverageTracker()
    d = date(2026, 9, 29)
    for t in open_minute_starts(et(d, 9), et(d, 9, 30)):
        tr.observe(m1(t, 6500))
    assert tr.is_complete(et(d, 9), et(d, 9, 30))
    assert not tr.is_complete(et(d, 9), et(d, 10))          # beyond the watermark: unknown
    assert not tr.is_complete(et(d, 8, 30), et(d, 9, 30))   # before the first bar: unknown


def test_continuity_label_alone_never_certifies_missing_minutes():
    tr = CoverageTracker()
    d = date(2026, 9, 29)
    tr.observe(m1(et(d, 9), 6500), None, "MES_LIVE")
    gaps = tr.observe(m1(et(d, 9, 3), 6500), "SAME_STREAM", "MES_LIVE")   # 2 missing minutes, label only
    assert gaps and gaps[0].open_minutes == 2
    tr2 = CoverageTracker()
    tr2.observe(m1(et(d, 9), 6500), None, "MES_LIVE")
    tr2.attest_zero_trade(et(d, 9, 1), "LIVE_END_OF_INTERVAL")
    tr2.attest_zero_trade(et(d, 9, 2), "LIVE_END_OF_INTERVAL")
    assert tr2.observe(m1(et(d, 9, 3), 6500), "SAME_STREAM", "MES_LIVE") == []
    assert tr2.is_complete(et(d, 9), et(d, 9, 4))
    with pytest.raises(ValueError):
        tr2.attest_zero_trade(et(d, 9, 5), "SAME_STREAM")
    # evidence arriving after the gap was decided cannot retroactively clear it
    tr.attest_zero_trade(et(d, 9, 1), "LIVE_END_OF_INTERVAL")
    assert tr.unexpected_minutes(et(d, 9), et(d, 9, 5)) == 2


# ============================================================ engine: readiness, partial exclusion, recovery
def _engine(cfg, out, days):
    cal = EventCalendar([], set(days), "TEST")
    return PilotEngine(cfg, out_dir=out, evidence_label="SYNTHETIC_TEST", data_source="synthetic", calendar=cal)


def _warm(eng, bars):
    eng.warmup = True
    for b in bars:
        eng.process_bar(b, None, continuity="ARCHIVE_SESSION", source="SYNTHETIC_ARCHIVE")
    eng.end_warmup()


T = date(2026, 9, 29)   # Tuesday
PRIOR = [date(2026, 9, 22), date(2026, 9, 23), date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 28)]


def test_complete_context_becomes_ready(cfg_no_vol, tmp_path):
    eng = _engine(cfg_no_vol, tmp_path, PRIOR + [T])
    warm = [b for d in PRIOR for b in session_bars(d)] + session_bars(T, end=et(T, 9, 0))
    _warm(eng, warm)
    for b in session_bars(T, start=et(T, 9, 0), end=et(T, 10, 30)):
        eng.process_bar(b, None, source="MES_LIVE")
    assert eng.readiness.ready, eng.readiness.reasons
    eng.finish()
    s = eng.ledger.records("SESSION_SUMMARY")[-1]
    assert s["readiness"]["window_bars_not_ready"] == 0 and s["readiness"]["window_bars_ready"] == 60
    assert s["classification"] != "CONTEXT_INCOMPLETE"
    assert s["status_layers"]["strategy_ready"] == "READY" and s["status_layers"]["feed_connected"] is True


def test_oct2_like_gap_blocks_entries_marks_ineligible_then_recovers(cfg_no_vol, tmp_path):
    later = [date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5), date(2026, 10, 6)]
    eng = _engine(cfg_no_vol, tmp_path, PRIOR + [T] + later)
    _warm(eng, [b for d in PRIOR for b in session_bars(d)])          # ends T-1 17:00 ET
    for b in session_bars(T, start=et(T, 8, 58), end=et(T, 11, 45)):  # live starts 08:58 ET
        eng.process_bar(b, None, source="MES_LIVE")
    r = eng.readiness
    assert not r.ready
    assert {"CURRENT_OVERNIGHT_GAP", "ASIA_WINDOW_GAP", "LONDON_WINDOW_GAP"} <= set(r.reasons)
    gap = eng.ledger.records("CONTEXT_GAP")[0]
    assert gap["gap_open_minutes"] == 898 - 60 * 0 or gap["gap_open_minutes"] > 800   # whole overnight absent
    excluded = {(x["tf"], x["start"]) for x in eng.ledger.records("INCOMPLETE_BAR_EXCLUDED")}
    assert (60, et(T, 8).isoformat()) in excluded                      # 08:00 ET H1 with 2 minutes
    assert all(b.start != et(T, 8) for b in eng.tfs[60].bars)          # never reached structure
    # a confirmed setup would abstain: the decision envelope refuses incomplete context
    from mes_pilot.setups import Setup
    st = Setup("x", "CONTINUATION_C1", "LONG", et(T, 10), et(T, 10, 15))
    st.stop, st.target = 6000.0, 7000.0
    in_window_bar = m1(et(T, 10), 6600.0)        # an entry-window decision bar while context is incomplete
    decision, reason, _, extra = eng._evaluate(st, in_window_bar, 0.0, None, False)
    assert decision == "ABSTAIN" and reason.startswith("CONTEXT_INCOMPLETE:")
    for d in later:                                                   # complete data afterwards
        for b in session_bars(d):
            eng.process_bar(b, None, source="MES_LIVE")
    eng.finish()
    summaries = {s["session_date"]: s for s in eng.ledger.records("SESSION_SUMMARY")}
    assert summaries[T.isoformat()]["classification"] == "CONTEXT_INCOMPLETE"
    assert summaries["2026-10-06"]["classification"] != "CONTEXT_INCOMPLETE"   # recovered after rebuild
    assert summaries["2026-10-06"]["readiness"]["window_bars_not_ready"] == 0
    from mes_pilot.report import build_report
    q = build_report(eng.ledger.path, cfg_no_vol, corrections=[])["qualification"]
    assert T.isoformat() not in q["qualified_eligible_dates"] and "2026-10-06" in q["qualified_eligible_dates"]


@pytest.mark.parametrize("drop", ["first", "middle", "last"])
def test_partial_h1_bucket_excluded_before_structure(cfg_no_vol, tmp_path, drop):
    eng = _engine(cfg_no_vol, tmp_path, PRIOR + [T])
    bars = [b for d in PRIOR[-2:] for b in session_bars(d)] + session_bars(T, end=et(T, 12))
    hole = {"first": et(T, 10), "middle": et(T, 10, 30), "last": et(T, 10, 59)}[drop]
    bars = [b for b in bars if b.start != hole]
    for b in bars:
        eng.process_bar(b, None, source="TEST")
    assert all(b.start != et(T, 10) for b in eng.tfs[60].bars), "partial 10:00 ET H1 bucket reached structure"
    # excluded either explicitly (first/middle missing: emitted partial, then dropped) or by the gap reset
    # discarding the unfinished bucket before emission (last minute missing)
    explicit = any(x["tf"] == 60 and x["start"] == et(T, 10).isoformat()
                   for x in eng.ledger.records("INCOMPLETE_BAR_EXCLUDED"))
    assert explicit or drop == "last"
    assert eng.ledger.records("STRUCTURE_RESET")[-1]["reason"].startswith("CONTEXT_GAP")


def test_identical_overlap_dropped_conflict_is_fault(cfg_no_vol, tmp_path):
    eng = _engine(cfg_no_vol, tmp_path, [T])
    bars = session_bars(T, start=et(T, 9), end=et(T, 9, 10))
    for b in bars + bars[3:6]:
        eng.process_bar(b, None, source="TEST")
    assert eng.ledger.records("MARKET_FAULT") == []
    eng.process_bar(replace(bars[4], volume=bars[4].volume + 1), None, source="OTHER")
    assert [r["fault"] for r in eng.ledger.records("MARKET_FAULT")] == ["CONFLICTING_DUPLICATE_BAR"]


# ============================================================ context replay safety and persisted risk
def test_context_replay_never_executes_against_restored_position_fresh_quote_does(cfg_no_vol, tmp_path):
    from mes_pilot.tests.test_engine_failures import engine, feed, scenario
    from mes_pilot.tests.helpers import DAY, et as het
    eng = engine(cfg_no_vol, tmp_path)
    feed(eng, scenario(hold_minutes=1))
    (pos,) = eng.simulator.open_positions()
    risk_before = dict(eng.risk.state.__dict__)
    del eng
    eng2 = PilotEngine(cfg_no_vol, out_dir=tmp_path, evidence_label="SYNTHETIC_TEST", data_source="restart",
                       calendar=EventCalendar([], {DAY}, "TEST"))
    # replayed context bars trade far through the stop: no retrospective exit
    t0 = het(DAY, 9, 43)
    for i in range(3):
        b = Bar(t0 + i * ONE, t0 + (i + 1) * ONE, 4995.0, 4996.0, 4990.0, 4991.0, 50.0, "TEST-MESZ6", 1)
        eng2.process_bar(b, None, context=True, source="MES_LIVE_REPLAY")
    assert eng2.ledger.records("POSITION_CLOSED") == []
    assert eng2.simulator.open_positions()[0].position_id == pos.position_id
    assert eng2.risk.state.session_day == risk_before["session_day"]
    assert eng2.risk.state.entries_today == risk_before["entries_today"]
    # a genuinely fresh live quote through the stop: exactly one protective exit
    q = Quote(t0 + 3 * ONE + timedelta(seconds=1), 4990.0, 4990.25, "LIVE_MBP1", t0 + 3 * ONE + timedelta(seconds=1))
    eng2.process_quote(q)
    eng2.process_quote(replace(q, ts=q.ts + timedelta(seconds=1), receive_ts=q.ts + timedelta(seconds=1)))
    closed = eng2.ledger.records("POSITION_CLOSED")
    assert len(closed) == 1 and closed[0]["exit_reason"] == "STOP"


def test_risk_roll_session_never_rewinds(cfg, tmp_path):
    r = PilotRiskManager(cfg, tmp_path / "risk.json")
    r.roll_session(date(2026, 10, 2))
    r.state.entries_today, r.state.day_realized_net = 2, -40.0
    r.roll_session(date(2026, 9, 25))              # historical replay must not rewind / reset
    assert r.state.session_day == "2026-10-02" and r.state.entries_today == 2 and r.state.day_realized_net == -40.0
    r.roll_session(date(2026, 10, 5))
    assert r.state.entries_today == 0


def test_warmup_and_context_do_not_roll_persisted_risk(cfg_no_vol, tmp_path):
    eng = _engine(cfg_no_vol, tmp_path, PRIOR + [T])
    eng.risk.roll_session(T)
    eng.risk.state.entries_today, eng.risk.state.day_realized_net = 1, -25.0
    _warm(eng, [b for d in PRIOR[-2:] for b in session_bars(d)])
    for b in session_bars(T, end=et(T, 9)):
        eng.process_bar(b, None, context=True, source="MES_LIVE_REPLAY")
    assert eng.risk.state.session_day == T.isoformat()
    assert eng.risk.state.entries_today == 1 and eng.risk.state.day_realized_net == -25.0


# ============================================================ live feed bridge
class _Hb:
    """databento-style SystemMsg whose is_heartbeat is a METHOD (always truthy as an attribute)."""

    def __init__(self, code, ts):
        self.code, self.msg, self.ts_event = code, code, int(ts.timestamp() * 1e9)

    def is_heartbeat(self):
        return False


SystemMsg = type("SystemMsg", (_Hb,), {})


class _Client:
    def __init__(self, script, clock, end_at):
        self.script, self.clock, self.end_at, self.subscriptions = script, clock, end_at, []

    def subscribe(self, **kw):
        self.subscriptions.append(kw)

    def stop(self):
        pass

    def __iter__(self):
        for at, rec in self.script:
            self.clock.now = at
            yield rec
        if self.end_at:
            self.clock.now = self.end_at


def _feed(scripts, *, replay_start=None, seed_end=None, end_at=None):
    day = T
    clock = ReplayClock(et(day, 9))
    clients, got, events, attests = [], [], [], []
    scripts = list(scripts)

    def factory(key):
        c = _Client(scripts.pop(0) if scripts else [], clock, end_at)
        clients.append(c)
        return c

    cfg = LiveFeedConfig(replay_start=replay_start, window_start=time(9, 0), window_end=time(9, 30),
                         reconnect_max_attempts=2)
    feed = LiveFeed(lambda b, q, **kw: got.append((b, q, kw)), cfg, client_factory=factory,
                    key_provider=lambda: "db-FAKEKEYFORTESTS0123", clock=clock, sleep=lambda s: None,
                    use_stop_timer=False, extended_callback=True,
                    on_event=lambda kind, **f: events.append((kind, f)),
                    on_attest=lambda m, ev: attests.append((m, ev)), last_context_bar_end=seed_end)
    return feed, got, events, attests, clients


def _b(day, hh, mm, vol=100.0):
    return m1(et(day, hh, mm), 6500.0, "MESZ6", vol)


def test_feed_replay_phase_context_then_live_and_subscriptions():
    d = T
    MAP = (et(d, 9), SymbolMappingMsg(7, "MES.c.0", "MESZ6"))
    script = [MAP] + [(et(d, 9, 0, 1), ohlcv(7, _b(d, 8, m))) for m in range(0, 3)] + [
        (et(d, 9, 0, 2), SystemMsg("replay_completed", et(d, 9, 0, 2))),
        (et(d, 9, 0, 59), mbp1(7, et(d, 9, 0, 59), 6500.0, 6500.25, et(d, 9, 0, 59))),
        (et(d, 9, 1, 0), ohlcv(7, _b(d, 9, 0)))]
    feed, got, events, _, clients = _feed([script], replay_start=et(d, 8), seed_end=et(d, 8), end_at=et(d, 9, 30))
    summary = feed.run(session_day=d)
    subs = clients[0].subscriptions
    assert [s.get("start") for s in subs if s["schema"] == "mbp-1"] == [None]
    assert [s.get("start") for s in subs if s["schema"] == "ohlcv-1m"] == [et(d, 8)]
    ctx = [(b.start, q, kw["context"], kw["source"]) for b, q, kw in got]
    assert ctx[:3] == [(et(d, 8, m), None, True, "MES_LIVE_REPLAY") for m in range(3)]
    b, q, kw = got[-1]
    assert kw["context"] is False and kw["source"] == "MES_LIVE" and q is not None
    assert summary["replay"]["completion_signal"] == "PROVIDER_REPLAY_COMPLETED"
    assert ("REPLAY_COMPLETED", ) == (events[[e[0] for e in events].index("REPLAY_COMPLETED")][0],)
    assert summary["stats"]["heartbeats"] == 0 and summary["stats"]["replay_completed_msgs"] == 1


def test_feed_end_of_interval_evidence_dedupe_conflict_and_seeded_gap():
    d = T
    MAP = (et(d, 9), SymbolMappingMsg(7, "MES.c.0", "MESZ6"))
    late = et(d, 9, 0, 5)
    script = [MAP,
              (late, ohlcv(7, _b(d, 8, 30))),
              (late, SystemMsg("end_of_interval", et(d, 8, 32))),
              (late, SystemMsg("end_of_interval", et(d, 8, 31))),
              (late, ohlcv(7, _b(d, 8, 32))),      # 08:31 bracketed by eoi(08:31), eoi(08:32): attested
              (late, ohlcv(7, _b(d, 8, 35))),      # 08:33-08:34 no evidence: unexpected
              (late, ohlcv(7, _b(d, 8, 35))),      # identical duplicate
              (late, ohlcv(7, _b(d, 8, 35, vol=999.0))),   # conflicting duplicate
              (et(d, 9, 0, 6), SystemMsg("replay_completed", et(d, 9, 0, 6)))]
    feed, got, events, attests, _ = _feed([script], replay_start=et(d, 8, 30), seed_end=et(d, 8, 0),
                                          end_at=et(d, 9, 30))
    summary = feed.run(session_day=d)
    assert attests == [(et(d, 8, 31), "LIVE_END_OF_INTERVAL")]
    st = summary["stats"]
    assert st["duplicate_bars"] == 1 and st["conflicting_bars"] == 1
    assert any(k == "CONFLICTING_DUPLICATE" for k, _ in events)
    gap_logs = [e for e in feed.events if e["kind"] == "GAP"]
    assert gap_logs[0]["seeded"] is True and gap_logs[0]["unexpected_minutes"] == 30   # 08:00 -> 08:30
    assert st["unexpected_gap_minutes"] == 30 + 2


def test_feed_reconnect_resumes_replay_from_last_delivered_bar():
    d = T
    MAP = (et(d, 9), SymbolMappingMsg(7, "MES.c.0", "MESZ6"))
    first = [MAP, (et(d, 9, 0, 1), SystemMsg("replay_completed", et(d, 9, 0, 1)))] + \
            [(et(d, 9, m + 1, 0), ohlcv(7, _b(d, 9, m))) for m in range(5)]
    second = [MAP, (et(d, 9, 8, 0), ohlcv(7, _b(d, 9, 4))),     # identical overlap after resume
              (et(d, 9, 8, 0), ohlcv(7, _b(d, 9, 5))), (et(d, 9, 8, 0), ohlcv(7, _b(d, 9, 6))),
              (et(d, 9, 8, 1), SystemMsg("replay_completed", et(d, 9, 8, 1)))]
    feed, got, events, _, clients = _feed([first, second], replay_start=et(d, 9), end_at=None)
    clients_end = et(d, 9, 30)
    feed.cfg = replace(feed.cfg)
    summary = feed.run(session_day=d)
    assert len(clients) >= 2
    resub = [s.get("start") for s in clients[1].subscriptions if s["schema"] == "ohlcv-1m"]
    assert resub == [et(d, 9, 5)]                               # last delivered bar end
    starts = [b.start for b, _, _ in got]
    assert starts == sorted(set(starts))                        # no duplicate delivery
    assert summary["stats"]["duplicate_bars"] >= 1 and summary["stats"]["reconnects"] >= 1
    assert any(k == "RESUME_FROM" for k, _ in events)


# ============================================================ historical layer
class _Rec:
    def __init__(self, ts, px, iid=42001581, vol=10):
        self.ts_event, self.instrument_id = int(ts.timestamp() * 1e9), iid
        self.open = self.high = self.low = self.close = int(px * 1e9)
        self.high, self.low, self.volume = int((px + 0.25) * 1e9), int((px - 0.25) * 1e9), vol


OHLCVMsg = type("OHLCVMsg", (_Rec,), {})


class _Hist:
    def __init__(self, recs, cost=0.0, avail=None, error=None):
        self.recs, self.cost, self.avail, self.error, self.downloads = recs, cost, avail, error, 0
        outer = self

        class M:
            def get_dataset_range(self, dataset):
                return {"schema": {"ohlcv-1m": {"end": (outer.avail or datetime(2030, 1, 1, tzinfo=UTC)).isoformat()}}}

            def get_cost(self, **kw):
                if outer.error:
                    raise RuntimeError(outer.error)
                return outer.cost

        class S:
            def resolve(self, dataset, symbols, stype_in, stype_out, start_date, end_date):
                if stype_out == "instrument_id":
                    return {"result": {"MES.c.0": [{"s": "42001581"}]}}
                return {"result": {"42001581": [{"s": "MESZ6"}]}}

        class TS:
            def get_range(self, **kw):
                outer.downloads += 1
                return list(outer.recs)

        self.metadata, self.symbology, self.timeseries = M(), S(), TS()


def test_history_fetch_cost_guard_clamps_dedupe_conflicts_and_mapping():
    d = T
    now = et(d, 9, 10)
    recs = [OHLCVMsg(et(d, 9, m), 6500 + m) for m in range(12)]               # 09:10, 09:11 are future
    recs.insert(3, OHLCVMsg(et(d, 9, 2), 6502))                                 # identical duplicate
    recs.insert(5, OHLCVMsg(et(d, 9, 3), 6600))                                 # conflicting duplicate
    h = _Hist(recs)
    f = hb.fetch_mes_history(et(d, 9), et(d, 9, 30), client_factory=lambda k: h,
                             key_provider=lambda: "db-FAKEKEYFORTESTS0123", clock=lambda: now)
    assert f.status == "OK" and f.cost_usd == 0.0
    assert [b.start for b in f.bars] == [et(d, 9, m) for m in range(10)]       # nothing ends after 'now'
    assert f.duplicates_dropped == 1 and len(f.conflicts) == 1
    assert {b.contract for b in f.bars} == {"MESZ6"} and f.contracts == ["MESZ6"]
    assert any(c["kind"] == "AVAILABLE_OR_CLOCK_END" for c in f.clamps)
    costly = _Hist(recs, cost=0.42)
    g = hb.fetch_mes_history(et(d, 9), et(d, 9, 30), client_factory=lambda k: costly,
                             key_provider=lambda: "db-FAKEKEYFORTESTS0123", clock=lambda: now)
    assert g.status == "HISTORICAL_COST_NONZERO" and costly.downloads == 0 and g.bars == []
    denied = _Hist(recs, error="403 license not entitled for dataset")
    e = hb.fetch_mes_history(et(d, 9), et(d, 9, 30), client_factory=lambda k: denied,
                             key_provider=lambda: "db-FAKEKEYFORTESTS0123", clock=lambda: now)
    assert e.status == "ENTITLEMENT_DENIED" and denied.downloads == 0


# ============================================================ series identity
def test_same_price_series_requires_explicit_roots_and_expiry():
    assert parse_contract("MESZ6") == ("MES", "Z", "6") and parse_contract("ESZ6") == ("ES", "Z", "6")
    assert same_price_series("ESZ6", "MESZ6")
    assert not same_price_series("ESH7", "MESZ6")
    assert not same_price_series("MES.c.0", "MESZ6")          # continuous label is not a contract
    assert not same_price_series("NQZ6", "MESZ6")             # suffix equality alone is not enough


# ============================================================ durable evidence corrections
def _ledger_with_summary(tmp_path, cls="NO_VALID_SETUP"):
    led = EvidenceLedger(tmp_path, "AUTONOMOUS_PAPER", "run1")
    led.append("SESSION_SUMMARY", session_date="2026-10-02", classification=cls, window_bars=120,
               dedupe_key="SESSION:2026-10-02:run1")
    return led


def test_correction_survives_append_and_rejects_altered_records(cfg, tmp_path):
    from mes_pilot.evidence import append_correction, correction_for_summary, load_corrections
    from mes_pilot.report import build_report
    led = _ledger_with_summary(tmp_path)
    reg = tmp_path / "corrections.jsonl"
    row = correction_for_summary(led.path, "2026-10-02", original_classification="NO_VALID_SETUP",
                                 corrected_classification="CONTEXT_INCOMPLETE", reason_code="X", reason_detail="d",
                                 evidence_ref="test", author="test", repo_root=tmp_path)
    assert append_correction(row, reg) and not append_correction(row, reg)     # duplicate refused
    corr = load_corrections(reg)
    assert build_report(led.path, cfg, corrections=corr)["qualification"]["qualified_eligible_sessions"] == 0
    # a later session appends to the same ledger: the correction still applies, the new date still counts
    led.append("SESSION_SUMMARY", session_date="2026-10-05", classification="NO_VALID_SETUP", window_bars=120,
               dedupe_key="SESSION:2026-10-05:run1")
    q = build_report(led.path, cfg, corrections=corr)["qualification"]
    assert q["raw_eligible_sessions"] == 2 and q["qualified_eligible_dates"] == ["2026-10-05"]
    # altering the original record breaks the chain: nothing qualifies
    lines = led.path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0]); first["window_bars"] = 999
    led.path.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n", encoding="utf-8")
    q2 = build_report(led.path, cfg, corrections=corr)["qualification"]
    assert q2["ledger_chain_verified"] is False and q2["qualified_eligible_sessions"] == 0


def test_correction_for_other_ledger_is_ignored(cfg, tmp_path):
    from mes_pilot.evidence import correction_for_summary
    from mes_pilot.report import build_report
    a, b = tmp_path / "a", tmp_path / "b"
    la, lb = _ledger_with_summary(a), EvidenceLedger(b, "AUTONOMOUS_PAPER", "run2")
    lb.append("SESSION_SUMMARY", session_date="2026-10-02", classification="NO_VALID_SETUP", window_bars=60,
              dedupe_key="SESSION:2026-10-02:run2")
    row = correction_for_summary(la.path, "2026-10-02", original_classification="NO_VALID_SETUP",
                                 corrected_classification="CONTEXT_INCOMPLETE", reason_code="X", reason_detail="d",
                                 evidence_ref="t", author="t", repo_root=tmp_path)
    assert build_report(lb.path, cfg, corrections=[row])["qualification"]["qualified_eligible_sessions"] == 1


def test_real_oct2_ledgers_qualify_zero_sessions():
    from mes_pilot.portfolios import load_portfolio_configs
    from mes_pilot.report import build_report
    root = REPO / "outputs" / "mes_pilot" / "evidence_snapshots" / "2026-10-02"
    if not root.exists():
        pytest.skip("Oct 2 snapshot not present on this machine")
    cfgs = load_portfolio_configs()
    for book in ("conservative", "moderate", "aggressive"):
        rep = build_report(root / book / "autonomous_paper-ledger.jsonl", cfgs[book.upper()])
        q = rep["qualification"]
        assert q["raw_eligible_sessions"] == 1 and q["qualified_eligible_sessions"] == 0
        assert q["corrections_applied"][0]["reason_code"] == "CONTEXT_INCOMPLETE_HISTORY_GAP"


def test_warmup_history_never_executes_against_restored_position(cfg_no_vol, tmp_path):
    """Found by the synthetic lifecycle run: warmup bars (not only context bars) are history."""
    from mes_pilot.tests.test_engine_failures import engine, feed, scenario
    from mes_pilot.tests.helpers import CONTRACT, DAY, et as het
    eng = engine(cfg_no_vol, tmp_path)
    feed(eng, scenario(hold_minutes=1))
    (pos,) = eng.simulator.open_positions()
    del eng
    eng2 = PilotEngine(cfg_no_vol, out_dir=tmp_path, evidence_label="SYNTHETIC_TEST", data_source="restart",
                       calendar=EventCalendar([], {DAY}, "TEST"))
    prev = date(2026, 9, 14)
    eng2.warmup = True   # previous day's history, including an 11:30 ET cutoff and prices far below the stop
    for t in open_minute_starts(et(prev, 9), et(prev, 12)):
        eng2.process_bar(Bar(t, t + ONE, 4990.0, 4991.0, 4980.0, 4985.0, 10.0, CONTRACT, 1), None,
                         continuity="ARCHIVE_SESSION", source="ES_ARCHIVE_PROXY")
    eng2.end_warmup()
    assert eng2.ledger.records("POSITION_CLOSED") == [] and eng2.ledger.records("EXIT_PENDING") == []
    assert [p.position_id for p in eng2.simulator.open_positions()] == [pos.position_id]
    q = Quote(het(DAY, 9, 43), 4990.0, 4990.25, "LIVE_MBP1", het(DAY, 9, 43))
    eng2.process_quote(q)
    assert len(eng2.ledger.records("POSITION_CLOSED")) == 1


def test_live_portfolios_command_builds_context_then_replays_from_its_end(tmp_path, monkeypatch):
    """The scheduled entry point (start_mes_paper_pilot.ps1 -> live-portfolios) must bridge history first."""
    import importlib.util
    import mes_pilot.history_bridge as hbm
    import mes_pilot.live_feed as lfm
    spec = importlib.util.spec_from_file_location("cli_lp", REPO / "scripts" / "run_mes_paper_pilot.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    calls = {}
    end = datetime(2026, 10, 5, 12, 40, tzinfo=UTC)

    def fake_build(group, *, cfg, archives, now):
        calls["build"] = {"group": type(group).__name__, "archives": archives}
        return {"last_context_bar_end": end.isoformat(), "mes_historical": {"status": "OK"},
                "fallback_to_archive": False}

    def fake_run(group, cfg, *, replay_start=None, last_context_bar_end=None, **kw):
        calls["run"] = {"replay_start": replay_start, "seed": last_context_bar_end}
        return {"status": "COMPLETED", "stats": {}}

    monkeypatch.setattr(hbm, "build_context", fake_build)
    monkeypatch.setattr(lfm, "run_session", fake_run)
    monkeypatch.setattr(cli, "OUT", tmp_path)
    monkeypatch.setattr(cli, "CAL_DIR", tmp_path / "no-calendar")
    cli.cmd_live_portfolios(None)
    assert calls["build"]["group"] == "PortfolioGroup"
    assert calls["run"] == {"replay_start": end, "seed": end}
    assert list((tmp_path / "autonomous_paper_portfolios" / "context-bridge").glob("bridge-*.json"))
