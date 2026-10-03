"""PilotEngine failure handling on a hand-built REVERSAL_R1 session (engine.py is not edited here).

Shortcuts (documented):
- cfg_no_vol: the volatility-percentile filter needs 60 prior sessions, so it is
  disabled via load_config(overrides=...) (changes config_hash; recorded).
- H1/H4 bias is preset BULLISH and the swept/target levels are premarked in
  engine.book right after construction (see tests/helpers.py for the hand-derived
  geometry: zone [5000.25, 5001.00], stop 4998.25, target 5005.00).
- The calendar is an EventCalendar built directly with the test day covered.

Hand-derived decision at the retest close S+11: entry_ref = 5001.25 + 1 tick = 5001.50,
risk 13 ticks, reward 3.50 pts -> RR 1.077 >= 1.0; budget min($100, 5% x $1400) = $70,
unit loss 13x1.25 + 1.70 + 3x1.25 = $21.70 -> 1 contract (internal cap). Fill at the S+11
bar open 5001.25 + 1 tick = 5001.50 (modeled ask).
"""
from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from mes_pilot.bars import ET
from mes_pilot.engine import PilotEngine
from mes_pilot.events import Event, EventCalendar
from mes_pilot.risk import PilotRiskManager
from mes_pilot.tests.helpers import DAY, HOLD, RETEST, assume_complete_context, bar, et, preset_levels, r1_long_prefix

UTC_S = (9, 30)
# 09:42 bar trading 1 tick through the 5005 target (entry 5001.50 -> +3.50 pts = $17.50 gross, $15.80 net).
TARGET_BAR = bar(et(DAY, 9, 42), 5004.0, 5005.25, 5003.75, 5005.0)


def scenario(day=DAY, sweep_at=UTC_S, hold_minutes=10):
    s = et(day, *sweep_at)
    bars = r1_long_prefix(day, sweep_at) + [bar(s + timedelta(minutes=10), *RETEST)]
    bars += [bar(s + timedelta(minutes=11 + i), *HOLD) for i in range(hold_minutes)]
    return bars


def calendar(*days, events=()):
    return EventCalendar(list(events), set(days) or {DAY}, "TEST")


def engine(cfg, out, cal=None, day=DAY, sweep_at=UTC_S, **kw):
    eng = PilotEngine(cfg, out_dir=out, evidence_label="SYNTHETIC_TEST", data_source="test-hand-built",
                      calendar=cal or calendar(day), **kw)
    assume_complete_context(eng)
    eng.tfs[60].bias = eng.tfs[240].bias = "BULLISH"
    preset_levels(eng.book, et(day, *sweep_at) - timedelta(hours=2))
    return eng


def feed(eng, bars):
    for b in bars:
        eng.process_bar(b)


def candidates(eng):
    return [(r["setup_family"], r["decision_state"], r["reason"]) for r in eng.ledger.records("CANDIDATE")]


def summary(eng):
    return eng.ledger.records("SESSION_SUMMARY")[-1]


# ---------------------------------------------------------------- baseline
def test_baseline_accepts_and_fills_at_next_modeled_ask(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    feed(eng, scenario(hold_minutes=2))
    assert candidates(eng) == [("REVERSAL_R1", "ACCEPT", None)]
    cand = eng.ledger.records("CANDIDATE")[0]
    assert cand["entry_ref"] == 5001.5 and cand["stop"] == 4998.25 and cand["target"] == 5005.0
    assert cand["risk"]["quantity"] == 1 and cand["risk"]["unit_loss"] == pytest.approx(21.7)
    (fill,) = eng.ledger.records("FILL")
    assert fill["fill_price"] == 5001.5 and fill["fill_time"] == et(DAY, 9, 41).isoformat()
    assert len(eng.simulator.open_positions()) == 1
    assert eng.ledger.verify_chain()


def test_volatility_filter_without_history_abstains(cfg, tmp_path):
    eng = engine(cfg, tmp_path)
    feed(eng, scenario(hold_minutes=1))
    assert candidates(eng) == [("REVERSAL_R1", "ABSTAIN", "VOLATILITY_UNAVAILABLE")]


# ---------------------------------------------------------------- calendar / events
def test_missing_calendar_abstains_and_classifies_operational_limitation(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path, cal=EventCalendar([], set(), "TEST-EMPTY"))
    feed(eng, scenario(hold_minutes=2))
    eng.finish()
    assert candidates(eng) == [("REVERSAL_R1", "ABSTAIN", "CALENDAR_UNAVAILABLE")]
    assert eng.ledger.records("FILL") == []
    s = summary(eng)
    assert s["classification"] == "CALENDAR_UNAVAILABLE_OPERATIONAL_LIMITATION"
    assert s["classification"] != "NO_VALID_SETUP" and s["calendar_available"] is False


def test_event_blackout_abstains(cfg_no_vol, tmp_path):
    cpi = Event("CPI m/m", "USD", "High", et(DAY, 9, 45))   # decision 09:41 is within -10/+15 min
    eng = engine(cfg_no_vol, tmp_path, cal=calendar(DAY, events=[cpi]))
    feed(eng, scenario(hold_minutes=2))
    assert candidates(eng) == [("REVERSAL_R1", "ABSTAIN", "EVENT_BLACKOUT")]
    assert eng.ledger.records("CANDIDATE")[0]["event_status"]["events"] == ["CPI m/m"]
    assert eng.ledger.records("FILL") == []


def test_low_impact_or_other_currency_events_do_not_block(cfg_no_vol, tmp_path):
    t = et(DAY, 9, 45)
    eng = engine(cfg_no_vol, tmp_path, cal=calendar(DAY, events=[Event("x", "EUR", "High", t), Event("y", "USD", "Low", t)]))
    feed(eng, scenario(hold_minutes=1))
    assert candidates(eng) == [("REVERSAL_R1", "ACCEPT", None)]


# ---------------------------------------------------------------- kill switch
def test_kill_switch_blocks_new_entries(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    bars = scenario(hold_minutes=2)
    feed(eng, bars[:-3])                      # through the M1 bar before the retest
    eng.set_kill_switch(True, "operator test")
    feed(eng, bars[-3:])
    assert candidates(eng) == [("REVERSAL_R1", "ABSTAIN", "KILL_SWITCH_ACTIVE")]
    assert eng.ledger.records("FILL") == []


def test_kill_switch_flattens_open_position_at_next_quote(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    bars = scenario(hold_minutes=4)
    feed(eng, bars[:-3])                      # fill happened on the 09:41 bar
    assert len(eng.simulator.open_positions()) == 1
    eng.set_kill_switch(True, "operator test")
    feed(eng, bars[-3:-2])                    # 09:42 bar: exit decided
    (pending,) = eng.ledger.records("EXIT_PENDING")
    assert pending["reason"] == "KILL_SWITCH_FLATTEN"
    feed(eng, bars[-2:-1])                    # 09:43 bar open: flattened at the bid
    (closed,) = eng.ledger.records("POSITION_CLOSED")
    assert closed["exit_reason"] == "KILL_SWITCH_FLATTEN" and closed["exit_price"] == HOLD[0] - 0.25
    assert closed["exit_time"] == et(DAY, 9, 43).isoformat()
    assert eng.simulator.open_positions() == [] and eng.risk.state.open_risk == {}


# ---------------------------------------------------------------- restart
def test_restart_with_open_position_reconciles_and_keeps_managing(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    bars = scenario(hold_minutes=1)
    feed(eng, bars)
    (pos,) = eng.simulator.open_positions()
    del eng                                    # "crash"
    eng2 = assume_complete_context(PilotEngine(cfg_no_vol, out_dir=tmp_path, evidence_label="SYNTHETIC_TEST",
                                               data_source="restart", calendar=calendar(DAY)))
    rec = eng2.ledger.records("RECONCILIATION")[-1]
    assert rec["simulator_open"] == [pos.position_id] and rec["risk_open"] == [pos.position_id]
    assert rec["entries_blocked"] is None and eng2.blocked is None
    # Next bar trades 1 tick through the 5005 target.
    eng2.process_bar(TARGET_BAR)
    (closed,) = eng2.ledger.records("POSITION_CLOSED")
    assert closed["exit_reason"] == "TARGET" and closed["exit_price"] == 5005.0
    assert closed["gross_pnl"] == 17.5            # (5005 - 5001.5) x $5
    assert eng2.risk.state.open_risk == {} and eng2.risk.state.cash == pytest.approx(50000 + 17.5 - 1.7)
    assert eng2.ledger.verify_chain()


def test_restart_with_mismatched_state_blocks_entries(cfg_no_vol, tmp_path):
    rm = PilotRiskManager(cfg_no_vol, tmp_path / "risk-state.json")
    rm.state.open_risk["POS-GHOST"] = 21.7          # risk thinks a position is open; simulator has none
    rm.save()
    eng = engine(cfg_no_vol, tmp_path)
    assert eng.blocked == "RECONCILIATION_MISMATCH"
    feed(eng, scenario(hold_minutes=2))
    assert candidates(eng) == [("REVERSAL_R1", "ABSTAIN", "ENTRIES_BLOCKED:RECONCILIATION_MISMATCH")]
    assert eng.ledger.records("FILL") == []


def test_restart_releases_stale_reservation_and_refuses_its_late_fill(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    bars = scenario(hold_minutes=1)
    feed(eng, bars[:-1])                            # decision made, intent pending, not yet filled
    (intent,) = eng.ledger.records("INTENT")
    assert intent["intent_id"] in eng.risk.state.reservations
    eng2 = engine(cfg_no_vol, tmp_path)
    assert eng2.risk.state.reservations == {}
    assert eng2.simulator.orders[intent["intent_id"]]["status"] == "CANCELLED"
    # A replayed submit of the same intent (late fill) is refused.
    pending_intent, _ = eng.pending[0]
    from mes_pilot.simulator import modeled_quote
    res = eng2.simulator.submit(pending_intent, modeled_quote(bars[-1], 0.25, 1))
    assert res.status == "DUPLICATE" and eng2.simulator.open_positions() == []


# ---------------------------------------------------------------- data faults
@pytest.mark.parametrize("bad,fault", [
    (dict(close=math.nan), "NON_POSITIVE_OR_NAN_PRICE"),
    (dict(high=4999.0), "OHLC_INCONSISTENT"),            # high below open/close
])
def test_malformed_bar_recorded_as_market_fault_and_skipped(cfg_no_vol, tmp_path, bad, fault):
    eng = engine(cfg_no_vol, tmp_path)
    bars = scenario(hold_minutes=1)
    feed(eng, bars[:30])
    m1_count = len(eng.tfs[1].bars)
    eng.process_bar(replace(bars[30], **bad))
    (rec,) = eng.ledger.records("MARKET_FAULT")
    assert rec["fault"] == fault
    assert len(eng.tfs[1].bars) == m1_count
    feed(eng, bars[31:])                            # the session continues and even trades
    eng.finish()
    s = summary(eng)
    assert s["classification"] == "OPERATIONAL_FAULT" and s["faults"][0]["fault"] == fault


def test_malformed_first_bar_of_session_counts_in_that_session(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    bars = scenario(hold_minutes=1)
    eng.process_bar(replace(bars[0], close=math.nan))
    feed(eng, bars[1:] + [TARGET_BAR])
    eng.finish()
    assert summary(eng)["classification"] == "OPERATIONAL_FAULT"


def test_session_with_open_position_at_finish_is_classified_traded(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    feed(eng, scenario(hold_minutes=1))
    assert len(eng.simulator.open_positions()) == 1
    eng.finish()
    assert summary(eng)["classification"] == "TRADED"


def test_session_with_closed_trade_is_classified_traded(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    feed(eng, scenario(hold_minutes=1) + [TARGET_BAR])
    eng.finish()
    s = summary(eng)
    assert s["classification"] == "TRADED" and s["positions"] == 1 and s["net_pnl"] == pytest.approx(15.8)


def test_duplicate_and_out_of_order_bars_ignored(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    bars = scenario(hold_minutes=2)
    feed(eng, bars[:50])
    n = len(eng.tfs[1].bars)
    eng.process_bar(bars[49])                       # identical duplicate (overlap): dropped, counted
    eng.process_bar(bars[10])                       # identical, out of order: dropped, counted
    assert eng.ledger.records("MARKET_FAULT") == []
    assert eng._session_stats["duplicate_bars_ignored"] == 2
    from dataclasses import replace as _replace
    eng.process_bar(_replace(bars[49], volume=bars[49].volume + 7))   # same minute, different values
    faults = [r["fault"] for r in eng.ledger.records("MARKET_FAULT")]
    assert faults == ["CONFLICTING_DUPLICATE_BAR"]
    assert len(eng.tfs[1].bars) == n
    feed(eng, bars[50:])
    assert candidates(eng) == [("REVERSAL_R1", "ACCEPT", None)]   # outcome unaffected
    assert len(eng.ledger.records("FILL")) == 1


# ---------------------------------------------------------------- session cutoff
@pytest.mark.parametrize("day", [
    date(2026, 3, 9),     # first Monday after US DST starts (EDT, UTC-4)
    date(2026, 11, 2),    # first Monday after US DST ends (EST, UTC-5)
    date(2026, 11, 27),   # day after Thanksgiving (CME equity early close later in the day)
])
def test_flat_by_1130_et_across_dst_and_holiday(cfg_no_vol, tmp_path, day):
    eng = engine(cfg_no_vol, tmp_path, cal=calendar(day), day=day, sweep_at=(11, 10))
    feed(eng, scenario(day, (11, 10), hold_minutes=12))      # bars through 11:32 ET
    (fill,) = eng.ledger.records("FILL")
    assert fill["fill_time"] == et(day, 11, 21).isoformat()
    (closed,) = eng.ledger.records("POSITION_CLOSED")
    exit_et = datetime.fromisoformat(closed["exit_time"]).astimezone(ET)
    assert closed["exit_reason"] == "SESSION_CUTOFF"
    assert (exit_et.hour, exit_et.minute) == (11, 29) and exit_et.date() == day
    assert eng.simulator.open_positions() == []


def test_no_entry_decided_at_or_after_cutoff(cfg_no_vol, tmp_path):
    # Sweep 11:20, displacement 11:25, retest bar 11:30 -> decision at 11:31 ET.
    eng = engine(cfg_no_vol, tmp_path, sweep_at=(11, 20))
    feed(eng, scenario(DAY, (11, 20), hold_minutes=2))
    assert candidates(eng) == [("REVERSAL_R1", "ABSTAIN", "OUTSIDE_ENTRY_WINDOW")]
    assert eng.ledger.records("FILL") == []


def test_ledger_kill_switch_file_is_local_json(cfg_no_vol, tmp_path):
    eng = engine(cfg_no_vol, tmp_path)
    eng.set_kill_switch(True, "x")
    assert json.loads((tmp_path / "kill-switch.json").read_text(encoding="utf-8"))["active"] is True
    assert eng.kill_switch_active()
