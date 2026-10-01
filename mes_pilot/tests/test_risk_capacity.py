"""Dollar-capacity risk manager: hand-computed boundaries (spec page 6 defaults).

Defaults: equity 50,000, floor 48,500, reserve 100 -> C = 1,400; budget =
min(100, 0.05*C=70, daily 150, C, 250) = 70. MES tick 0.25 = $1.25,
commission 0.85/side, stressed slippage 3 ticks.
unit_loss(20) = 25.00 + 1.70 + 3.75 = 30.45 -> floor(70/30.45)=2 -> cap 1.
unit_loss(51) = 63.75 + 5.45 = 69.20 -> qty 1; unit_loss(52) = 65.00 + 5.45 = 70.45 -> qty 0.
"""
from __future__ import annotations

from datetime import date
import json
import threading

import pytest

from mes_pilot.config import load_config
from mes_pilot.risk import PilotRiskManager, daily_loss_limit, effective_floor

D1, D2 = date(2026, 3, 2), date(2026, 3, 3)
ENTRY = 5000.00


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def mgr(cfg, path=None, day=D1):
    rm = PilotRiskManager(cfg, path)
    rm.roll_session(day)
    return rm


def ev(rm, intent="I1", side="LONG", stop=ENTRY - 5.0, kill=False, **kw):
    return rm.evaluate_and_reserve(intent_id=intent, side=side, entry=ENTRY, stop=stop, session_open=True,
                                   kill_switch=kill, **kw)


def trade(rm, pid, pnl, day=D1):
    """Reserve, fill and close one 20-tick position with the given net P&L."""
    d = ev(rm, intent="INT-" + pid)
    assert d.approved, d.reason
    rm.on_fill("INT-" + pid, pid, d.worst_case_loss)
    rm.on_close(pid, pnl, day)


def paused_check_failed(d):
    return not d.approved and any(x.name == "consecutive_loss_pause_clear" and not x.passed for x in d.limits)


def set_cash(rm, cash):
    rm.state.cash = cash
    rm.state.day_start_cash = cash


# ---------------------------------------------------------------- sizing
def test_initial_capacity_budget_and_20_tick_sizing(cfg):
    rm = mgr(cfg)
    assert rm.capacity() == pytest.approx(1400.00)
    assert rm.daily_headroom() == pytest.approx(150.00)
    d = ev(rm)
    assert d.approved and d.quantity == 1            # affordable 2, internal cap 1
    assert d.budget == pytest.approx(70.00)
    assert d.capacity_c == pytest.approx(1400.00)
    assert d.stop_ticks == 20 and d.unit_loss == pytest.approx(30.45) and d.worst_case_loss == pytest.approx(30.45)
    assert rm.capacity() == pytest.approx(1369.55)   # reservation consumed capacity
    assert rm.daily_headroom() == pytest.approx(119.55)


def test_51_tick_fits_and_52_tick_is_skipped_without_tightening(cfg):
    rm = mgr(cfg)
    ok = ev(rm, intent="A", stop=ENTRY - 12.75)       # 51 ticks
    assert ok.approved and ok.quantity == 1 and ok.unit_loss == pytest.approx(69.20)
    rm.release("A")
    wide = ev(rm, intent="B", stop=ENTRY - 13.00)     # 52 ticks
    assert not wide.approved and wide.quantity == 0
    assert wide.reason == "integer_quantity_at_least_one"
    assert wide.stop_ticks == 52 and wide.unit_loss == pytest.approx(70.45)   # stop not moved to fit
    assert rm.state.reservations == {}


def test_off_grid_stop_distance_rounds_up(cfg):
    rm = mgr(cfg)
    d = ev(rm, stop=ENTRY - 5.10)                     # 20.4 ticks -> 21
    assert d.stop_ticks == 21 and d.unit_loss == pytest.approx(31.70)
    rm.release("I1")
    d = ev(rm, intent="I2", side="SHORT", stop=ENTRY + 5.01)
    assert d.stop_ticks == 21


def test_short_side_and_wrong_side_stop(cfg):
    rm = mgr(cfg)
    assert ev(rm, side="SHORT", stop=ENTRY + 5.0).approved
    rm.release("I1")
    bad = ev(rm, intent="X", side="LONG", stop=ENTRY + 5.0)
    assert not bad.approved and bad.reason == "stop_on_correct_side"
    nan = ev(rm, intent="Y", stop=float("nan"))
    assert not nan.approved and nan.reason == "prices_finite_positive"


@pytest.mark.parametrize("cash, approved", [(49208.99, False), (49209.00, True), (49209.01, True)])
def test_capacity_fraction_boundary_for_20_tick_stop(cfg, cash, approved):
    # 0.05*C must cover 30.45 -> C >= 609.00 -> cash >= 48,500 + 100 + 609 = 49,209.00
    rm = mgr(cfg)
    set_cash(rm, cash)
    d = ev(rm)
    assert d.approved is approved
    if not approved:
        assert d.reason == "integer_quantity_at_least_one"


@pytest.mark.parametrize("cash, reason", [(48600.01, "integer_quantity_at_least_one"),
                                          (48600.00, "usable_capacity_positive"),
                                          (48599.99, "usable_capacity_positive")])
def test_floor_plus_reserve_boundary(cfg, cash, reason):
    rm = mgr(cfg)
    set_cash(rm, cash)
    d = ev(rm)
    assert not d.approved and d.reason == reason


def test_outer_drawdown_cap_tightens_floor_when_stricter(cfg):
    tight = load_config(overrides={"risk": {"outer_caps": {"max_drawdown_pct": 2.0}}})
    assert effective_floor(tight) == pytest.approx(49000.0)
    assert effective_floor(cfg) == pytest.approx(48500.0)
    rm = mgr(tight)
    assert rm.capacity() == pytest.approx(900.0)
    assert ev(rm).budget == pytest.approx(45.0)


def test_firm_caps_bind(cfg):
    rm = mgr(cfg)
    assert ev(rm, intent="A", firm_contract_cap=0).reason == "integer_quantity_at_least_one"
    assert ev(rm, intent="B", firm_trade_limit=30.44).reason == "integer_quantity_at_least_one"
    assert ev(rm, intent="C", firm_trade_limit=30.45).approved


# ---------------------------------------------------------------- daily stop
def test_daily_limit_is_strictest_ceiling(cfg):
    # min(150 pilot, 500 = 1% nominal, 375 = 25% of 1,500, 750 = 1.5% outer) = 150
    assert daily_loss_limit(cfg) == pytest.approx(150.0)


@pytest.mark.parametrize("day_net, reason", [(-149.99, "integer_quantity_at_least_one"),
                                             (-150.00, "daily_net_stop_not_hit"),
                                             (-150.01, "daily_net_stop_not_hit")])
def test_daily_stop_boundaries(cfg, day_net, reason):
    rm = mgr(cfg)
    trade(rm, "P1", day_net)
    assert rm.state.day_realized_net == pytest.approx(day_net)
    d = ev(rm, intent="next")
    assert not d.approved and d.reason == reason
    assert d.budget == pytest.approx(max(0.0, 150.0 + day_net))


def test_daily_headroom_counts_open_risk_and_reservations(cfg):
    rm = mgr(cfg)
    trade(rm, "W", 40.0)
    d = ev(rm, intent="R")
    rm.on_fill("R", "P2", d.worst_case_loss)
    assert rm.daily_headroom() == pytest.approx(150 + 40 - 30.45)
    assert rm.capacity() == pytest.approx(50040 - 48500 - 100 - 30.45)


# ---------------------------------------------------------------- session caps / pause
def test_three_entries_per_session_then_next_session(cfg):
    rm = mgr(cfg)
    for i in range(3):
        trade(rm, f"P{i}", 10.0)
    assert ev(rm, intent="fourth").reason == "entries_this_session"
    rm.roll_session(D1)                     # restart within the same day does not reset the count
    assert ev(rm, intent="fourth").reason == "entries_this_session"
    rm.roll_session(D2)
    assert ev(rm, intent="fourth").approved


def test_three_losses_pause_review_and_next_session(cfg):
    rm = mgr(cfg)
    for i in range(3):
        trade(rm, f"L{i}", -10.0)
    assert rm.is_paused() and rm.state.pause_requires_review
    assert paused_check_failed(ev(rm, intent="X"))
    out = rm.log_review("reviewed three losses")
    assert out["review_cleared_pause"] and out["still_paused_until_next_session"]
    assert paused_check_failed(ev(rm, intent="X"))     # review alone: same day stays paused
    rm.roll_session(D2)
    assert ev(rm, intent="X").approved


def test_next_session_without_review_stays_paused(cfg):
    rm = mgr(cfg)
    for i in range(3):
        trade(rm, f"L{i}", -10.0)
    rm.roll_session(D2)
    assert ev(rm, intent="X").reason == "consecutive_loss_pause_clear"     # next session alone: still paused
    rm.log_review("ok")
    assert ev(rm, intent="X").approved


def test_review_without_active_pause_cannot_reset_streak(cfg):
    rm = mgr(cfg)
    trade(rm, "L1", -10.0)
    trade(rm, "L2", -10.0)
    out = rm.log_review("premature review")
    assert out["review_cleared_pause"] is False and rm.state.consecutive_losses == 2
    rm.roll_session(D2)
    trade(rm, "L3", -10.0, day=D2)
    assert rm.is_paused()


@pytest.mark.parametrize("seq, paused", [((-5, -5, 0.0, -5), True),     # breakeven does not reset
                                         ((-5, 0.0, 0.0), False),        # breakeven does not extend
                                         ((-5, -5, 5, -5), False)])      # a win resets
def test_breakeven_neither_extends_nor_resets(cfg, seq, paused):
    rm = mgr(cfg)
    for i, pnl in enumerate(seq):
        if i == 3:
            rm.roll_session(D2)          # keep the 3-entries cap out of the way
        trade(rm, f"P{i}", pnl, day=D2 if i == 3 else D1)
    assert rm.is_paused() is paused


def test_protective_close_still_processed_while_paused(cfg):
    rm = mgr(cfg)
    for i in range(2):
        trade(rm, f"L{i}", -10.0)
    d = ev(rm, intent="INT-L2")
    rm.on_fill("INT-L2", "L2", d.worst_case_loss)
    rm.on_close("L2", -10.0, D1)                       # third loss -> pause
    assert rm.is_paused() and rm.state.open_risk == {}
    assert rm.state.cash == pytest.approx(49970.0)


# ---------------------------------------------------------------- reservations
def test_idempotent_rereserve_same_intent(cfg):
    rm = mgr(cfg)
    first = ev(rm)
    again = ev(rm)
    assert again.approved and again.reason == "ALREADY_RESERVED"
    assert (again.quantity, again.stop_ticks, again.unit_loss) == (first.quantity, first.stop_ticks, first.unit_loss)
    assert rm.state.reservations == {"I1": pytest.approx(30.45)}
    changed = ev(rm, stop=ENTRY - 6.0)
    assert not changed.approved and changed.reason == "duplicate_intent_parameters_match"
    assert "I1" in rm.state.reservations


def test_filled_intent_cannot_be_reserved_again(cfg):
    rm = mgr(cfg)
    d = ev(rm)
    rm.on_fill("I1", "P1", d.worst_case_loss)
    rm.on_close("P1", 5.0, D1)
    again = ev(rm)
    assert not again.approved and again.reason == "intent_not_already_filled"


def test_release_restores_capacity(cfg):
    rm = mgr(cfg)
    ev(rm)
    rm.release("I1")
    assert rm.capacity() == pytest.approx(1400.0) and rm.state.reservations == {}


def _race(rm, n, intents):
    barrier = threading.Barrier(n)
    results = [None] * n

    def worker(i):
        barrier.wait()
        results[i] = ev(rm, intent=intents[i])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_reservations_respect_max_open_positions(cfg):
    rm = mgr(cfg)
    res = _race(rm, 16, [f"I{i}" for i in range(16)])
    assert sum(r.approved for r in res) == 1
    assert len(rm.state.reservations) == 1
    assert rm.capacity() == pytest.approx(1400 - 30.45)


def test_concurrent_reservations_cannot_overshoot_session_entry_cap(cfg):
    # With 5 open slots the daily budget alone would admit 4 (150, 119.55, 89.10, 58.65 >= 30.45);
    # pending reservations must count toward the 3-entry session cap.
    wide = load_config(overrides={"risk": {"max_open_positions": 5}})
    rm = mgr(wide)
    res = _race(rm, 12, [f"I{i}" for i in range(12)])
    assert sum(r.approved for r in res) == 3
    assert sum(rm.state.reservations.values()) == pytest.approx(3 * 30.45)
    assert rm.daily_headroom() >= 0 and rm.capacity() > 0


def test_concurrent_same_intent_reserves_once(cfg):
    rm = mgr(cfg)
    res = _race(rm, 8, ["SAME"] * 8)
    assert all(r.approved for r in res)
    assert rm.state.reservations == {"SAME": pytest.approx(30.45)}


# ---------------------------------------------------------------- kill switch / persistence
def test_kill_switch_rejects_and_keeps_existing_reservation(cfg):
    rm = mgr(cfg)
    assert ev(rm, intent="K", kill=True).reason == "kill_switch_inactive"
    assert rm.state.reservations == {}
    ev(rm)
    dup = ev(rm, kill=True)
    assert not dup.approved and dup.reason == "kill_switch_inactive"
    assert "I1" in rm.state.reservations       # released only on confirmed cancel


def test_restart_round_trip_preserves_pause_reservation_and_kill_latch(cfg, tmp_path):
    path = tmp_path / "risk-state.json"
    rm = mgr(cfg, path)
    for i in range(3):
        trade(rm, f"L{i}", -12.5)
    rm.engage_kill_switch("operator")
    before = json.loads(path.read_text(encoding="utf-8"))

    back = PilotRiskManager(cfg, path)
    assert json.loads(path.read_text(encoding="utf-8")) == before
    assert back.state.cash == pytest.approx(49962.5) and back.state.day_realized_net == pytest.approx(-37.5)
    assert back.is_paused() and back.state.entries_today == 3
    back.roll_session(D2)
    back.log_review("reviewed")
    assert ev(back, intent="X").reason == "kill_switch_inactive"      # latch survived restart
    back.clear_kill_switch("cleared by operator")
    first = ev(back, intent="X")
    assert first.approved

    again = PilotRiskManager(cfg, path)
    dup = ev(again, intent="X")
    assert dup.reason == "ALREADY_RESERVED" and dup.quantity == 1 and dup.unit_loss == pytest.approx(30.45)
    assert len(again.state.reservations) == 1


def test_corrupt_state_file_fails_closed(cfg, tmp_path):
    path = tmp_path / "risk-state.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        PilotRiskManager(cfg, path)
