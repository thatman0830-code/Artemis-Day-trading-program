"""PaperSimulator fill policy, idempotency, fault injection and restart (hand-computed prices).

Config: tick 0.25, tick value $1.25, point value $5, commission $0.85/side,
stop slippage 1 tick, max drift 2 ticks.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from mes_pilot.simulator import Intent, PaperSimulator, Quote, modeled_quote
from mes_pilot.tests.helpers import DAY, bar, et

T = et(DAY, 10, 0)


def intent(iid="INT-1", side="LONG", qty=1, entry=5000.0, stop=4997.0, target=5006.0, created=T, life_s=60):
    return Intent(iid, "SIG-" + iid, "SET-" + iid, side, qty, entry, stop, target, created,
                  created + timedelta(seconds=life_s), 2, 20.0)


def q(bid, ask, ts=T, source="SYNTHETIC"):
    return Quote(ts, bid, ask, source)


@pytest.fixture
def sim(cfg, tmp_path):
    return PaperSimulator(cfg, tmp_path / "sim.json")


def filled_long(sim):
    res = sim.submit(intent(), q(4999.75, 5000.25))   # buys the ask 5000.25 (1 tick drift)
    assert res.status == "FILLED"
    return res.position


def test_entry_fills_at_ask_of_first_quote_after_decision(sim):
    pos = filled_long(sim)
    assert (pos.entry_price, pos.entry_time, pos.quantity) == (5000.25, T, 1)
    assert pos.initial_risk_usd == 16.25          # 13 ticks * $1.25
    assert pos.entry_fees == 0.85


def test_modeled_quote_is_bar_open_plus_minus_spread():
    qt = modeled_quote(bar(T, 5000, 5001, 4999, 5000.5), 0.25, 1)
    assert (qt.ts, qt.bid, qt.ask, qt.source) == (T, 4999.75, 5000.25, "MODELED_FROM_BAR_OPEN")


def test_same_bar_stop_and_target_resolves_stop_first_and_flags(sim):
    pos = filled_long(sim)
    closed = sim.on_bar(bar(T, 5000, 5006.5, 4996.5, 5000))
    assert closed == [pos]
    assert pos.exit_reason == "STOP" and "AMBIGUOUS_BAR_STOP_FIRST" in pos.flags
    assert pos.exit_price == 4996.75               # min(stop 4997, open 5000) - 1 tick
    assert pos.gross_pnl == -17.5 and pos.net_pnl == -19.2


def test_target_touch_without_trade_through_does_not_fill(sim):
    pos = filled_long(sim)
    assert sim.on_bar(bar(T, 5001, 5006.0, 5000, 5005)) == []
    assert pos.is_open
    assert sim.on_bar(bar(T + timedelta(minutes=1), 5005, 5006.25, 5004, 5006)) == [pos]
    assert (pos.exit_reason, pos.exit_price, pos.gross_pnl, pos.net_pnl) == ("TARGET", 5006.0, 28.75, 27.05)


def test_stop_gap_fills_at_the_worse_open(sim):
    pos = filled_long(sim)
    sim.on_bar(bar(T, 4995, 4996, 4994, 4995.5))
    assert (pos.exit_reason, pos.exit_price) == ("STOP", 4994.75)   # open 4995 - 1 tick


def test_short_mirror_stop_and_target(cfg, tmp_path):
    s = PaperSimulator(cfg, tmp_path / "s.json")
    res = s.submit(intent(side="SHORT", entry=5000, stop=5003, target=4994), q(4999.75, 5000.25))
    pos = res.position
    assert pos.entry_price == 4999.75
    assert s.on_bar(bar(T, 4995, 4995, 4994.0, 4994.5)) == []        # touch 4994: no fill
    s.on_bar(bar(T + timedelta(minutes=1), 4995, 5004, 4993.75, 5000))
    assert pos.exit_reason == "STOP" and pos.exit_price == 5003.25 and pos.flags == ["AMBIGUOUS_BAR_STOP_FIRST"]


def test_duplicate_submit_of_same_intent_creates_no_second_position(sim):
    filled_long(sim)
    again = sim.submit(intent(), q(4999.75, 5000.25, ts=T + timedelta(seconds=1)))
    assert again.status == "DUPLICATE" and again.position is None
    assert len(sim.positions) == 1


def test_late_fill_after_cancellation_is_refused(sim):
    assert sim.cancel("INT-1", "RESTART_PENDING_INTENT_CANCELLED") is True
    res = sim.submit(intent(), q(4999.75, 5000.25))
    assert res.status == "DUPLICATE" and "CANCELLED" in res.reason
    assert sim.positions == {}


def test_stale_intent_quote_after_expiry_cancelled(sim):
    res = sim.submit(intent(), q(4999.75, 5000.25, ts=T + timedelta(seconds=61)))
    assert (res.status, res.reason) == ("CANCELLED", "INTENT_EXPIRED_BEFORE_EXECUTABLE_QUOTE")
    assert sim.positions == {}


def test_quote_before_decision_rejected(sim):
    res = sim.submit(intent(), q(4999.75, 5000.25, ts=T - timedelta(seconds=1)))
    assert (res.status, res.reason) == ("REJECTED", "QUOTE_PRECEDES_DECISION")


@pytest.mark.parametrize("ask,status", [(5000.5, "FILLED"), (5000.75, "CANCELLED")])
def test_drift_beyond_two_ticks_cancelled(sim, ask, status):
    res = sim.submit(intent(), q(ask - 0.5, ask))
    assert res.status == status
    if status == "CANCELLED":
        assert res.reason == "PRICE_DRIFT_3_TICKS" and sim.positions == {}


def test_partial_fill_quantity_propagates(cfg, tmp_path):
    s = PaperSimulator(cfg, tmp_path / "s.json", faults={"partial_fill_qty": 1})
    res = s.submit(intent(qty=2), q(4999.75, 5000.25))
    assert res.status == "PARTIAL_FILLED"
    assert res.position.quantity == 1 and res.position.initial_risk_usd == 16.25 and res.position.entry_fees == 0.85
    order = s.orders["INT-1"]
    assert (order["requested_qty"], order["filled_qty"]) == (2, 1)
    s.on_bar(bar(T, 5005, 5006.25, 5004, 5006))
    assert res.position.gross_pnl == 28.75     # 1 contract, not 2


def test_partial_fill_never_exceeds_requested_quantity(cfg, tmp_path):
    """Regression: a fault/venue fill larger than requested used to create an oversized position."""
    s = PaperSimulator(cfg, tmp_path / "s.json", faults={"partial_fill_qty": 5})
    res = s.submit(intent(qty=2), q(4999.75, 5000.25))
    assert res.status == "FILLED" and res.position.quantity == 2


def test_zero_quantity_intent_rejected(sim):
    assert sim.submit(intent(qty=0), q(4999.75, 5000.25)).status == "REJECTED"


def test_rejected_protection_flattens_and_blocks_further_entries(cfg, tmp_path):
    path = tmp_path / "s.json"
    s = PaperSimulator(cfg, path, faults={"reject_protection": True})
    res = s.submit(intent(), q(4999.75, 5000.25))
    assert (res.status, res.reason) == ("EMERGENCY_FLATTENED", "PROTECTION_REJECTED")
    pos = res.position
    assert not pos.is_open and pos.exit_reason == "EMERGENCY_PROTECTION_REJECTED" and pos.exit_price == 4999.75
    assert pos.protection_status == "REJECTED" and s.emergency == "PROTECTION_REJECTED"
    nxt = s.submit(intent("INT-2"), q(4999.75, 5000.25, ts=T + timedelta(seconds=5)))
    assert (nxt.status, nxt.reason) == ("REJECTED", "EMERGENCY_STATE:PROTECTION_REJECTED")
    # The emergency survives a restart.
    s2 = PaperSimulator(cfg, path)
    assert s2.emergency == "PROTECTION_REJECTED"
    assert s2.submit(intent("INT-3"), q(4999.75, 5000.25)).status == "REJECTED"


def test_restart_preserves_open_position_and_terminal_orders(cfg, tmp_path):
    path = tmp_path / "s.json"
    s1 = PaperSimulator(cfg, path)
    s1.submit(intent("INT-STALE"), q(4999.75, 5000.25, ts=T + timedelta(minutes=5)))   # cancelled (expired)
    s1.submit(intent(), q(4999.75, 5000.25))
    s2 = PaperSimulator(cfg, path)
    (pos,) = s2.open_positions()
    assert (pos.position_id, pos.entry_price, pos.entry_time, pos.stop, pos.target) == \
        ("POS-INT-1", 5000.25, T, 4997.0, 5006.0)
    assert s2.orders["INT-1"]["status"] == "FILLED" and s2.orders["INT-STALE"]["status"] == "CANCELLED"
    assert s2.submit(intent(), q(4999.75, 5000.25)).status == "DUPLICATE"
    assert s2.submit(intent("INT-STALE"), q(4999.75, 5000.25)).status == "DUPLICATE"
    s2.on_bar(bar(T, 5005, 5006.25, 5004, 5006))
    s3 = PaperSimulator(cfg, path)
    assert s3.open_positions() == [] and s3.positions["POS-INT-1"].exit_reason == "TARGET"


def test_second_entry_rejected_while_position_open(sim):
    filled_long(sim)
    res = sim.submit(intent("INT-2"), q(4999.75, 5000.25))
    assert (res.status, res.reason) == ("REJECTED", "POSITION_ALREADY_OPEN")
