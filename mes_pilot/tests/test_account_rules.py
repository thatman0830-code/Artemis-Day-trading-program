"""Account-rule boundaries on the SYNTHETIC fixture only (not an Apex rule set).

Fixture: start 50,000, allowance 2,500 -> initial floor 47,500; intraday
trailing; floor locks at 50,100 (reached when the peak hits 52,600); daily loss
limit 1,000; max 3 micros. Equality counts as a breach everywhere.
"""
from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from mes_pilot.account_rules import (ACTIVE_PROFILE_STATUS, ProfileError, TrailingFloor, active_profile, check_trade,
                                     profile_from_dict, synthetic_fixture)

FX = synthetic_fixture()
REAL_SHAPED = replace(FX, synthetic_fixture=False, profile_id="NON-SYNTHETIC-SHAPE")


def test_no_profile_selected_blocks_prop_alerts():
    assert active_profile() is None and ACTIVE_PROFILE_STATUS == "UNCONFIGURED"
    out = check_trade(None, contracts_micro=1, day_loss_after_worst=0.0, equity_after_worst=50000.0, floor=0.0)
    assert out["status"] == "UNCONFIGURED" and out["allowed_for_prop_alert"] is False


def test_synthetic_fixture_never_allows_prop_alerts():
    out = check_trade(FX, contracts_micro=1, day_loss_after_worst=10.0, equity_after_worst=49990.0, floor=47500.0)
    assert out["status"] == "SYNTHETIC_FIXTURE" and all(out["checks"].values())
    assert out["allowed_for_prop_alert"] is False


@pytest.mark.parametrize("equity, breached", [(47500.01, False), (47500.00, True), (47499.99, True)])
def test_initial_floor_boundary(equity, breached):
    tf = TrailingFloor(FX, 50000.0)
    assert tf.floor == pytest.approx(47500.0)
    assert tf.breached(equity) is breached


def test_intraday_high_then_retracement_keeps_raised_floor():
    tf = TrailingFloor(FX, 50000.0)
    assert tf.update(50800.0) == pytest.approx(48300.0)       # open-P&L high raises the floor
    assert tf.update(49000.0) == pytest.approx(48300.0)       # retracement never lowers it
    assert tf.breached(48300.01) is False
    assert tf.breached(48300.00) is True
    assert tf.breached(48299.99) is True


@pytest.mark.parametrize("peak, floor, locked", [(52599.99, 50099.99, False), (52600.00, 50100.00, True),
                                                 (52600.01, 50100.00, True)])
def test_floor_lock_boundary(peak, floor, locked):
    tf = TrailingFloor(FX, 50000.0)
    tf.update(peak)
    assert tf.floor == pytest.approx(floor) and tf.locked is locked
    tf.update(55000.0)
    if locked:
        assert tf.floor == pytest.approx(50100.0)              # stops trailing once locked
        assert tf.breached(50100.00) and not tf.breached(50100.01)


def test_eod_trailing_ignores_intraday_highs():
    eod = replace(FX, floor_type="EOD_TRAILING")
    tf = TrailingFloor(eod, 50000.0)
    assert tf.update(51000.0) == pytest.approx(47500.0)        # intraday high ignored
    assert tf.update(50500.0, end_of_day=True) == pytest.approx(48000.0)
    assert tf.breached(48000.0) and not tf.breached(48000.01)


def test_static_floor_never_trails():
    tf = TrailingFloor(replace(FX, floor_type="STATIC", floor_lock_at=None), 50000.0)
    assert tf.update(60000.0, end_of_day=True) == pytest.approx(47500.0)


def test_trailing_floor_restart_round_trip_keeps_raised_floor():
    tf = TrailingFloor(FX, 50000.0)
    tf.update(51234.5)
    back = TrailingFloor.from_dict(FX, tf.to_dict())
    assert back.floor == pytest.approx(48734.5) and back.peak == pytest.approx(51234.5)
    with pytest.raises(ProfileError):
        TrailingFloor.from_dict(replace(FX, rule_version="synthetic-2"), tf.to_dict())


@pytest.mark.parametrize("loss, ok", [(999.99, True), (1000.00, False), (1000.01, False)])
def test_daily_loss_limit_boundary(loss, ok):
    out = check_trade(REAL_SHAPED, contracts_micro=1, day_loss_after_worst=loss, equity_after_worst=49000.0,
                      floor=47500.0)
    assert out["checks"]["daily_loss"] is ok and out["allowed_for_prop_alert"] is ok


@pytest.mark.parametrize("equity, ok", [(47500.01, True), (47500.00, False), (47499.99, False)])
def test_floor_check_boundary(equity, ok):
    out = check_trade(REAL_SHAPED, contracts_micro=1, day_loss_after_worst=0.0, equity_after_worst=equity,
                      floor=47500.0)
    assert out["checks"]["floor"] is ok


@pytest.mark.parametrize("contracts, ok", [(2, True), (3, True), (4, False)])
def test_contract_limit_boundary(contracts, ok):
    out = check_trade(REAL_SHAPED, contracts_micro=contracts, day_loss_after_worst=0.0, equity_after_worst=49000.0,
                      floor=47500.0)
    assert out["checks"]["contracts"] is ok


def test_non_advisory_automation_is_refused():
    auto = replace(REAL_SHAPED, automation="FULL_AUTO")
    out = check_trade(auto, contracts_micro=1, day_loss_after_worst=0.0, equity_after_worst=49000.0, floor=47500.0)
    assert out["checks"]["automation_advisory_only"] is False and out["allowed_for_prop_alert"] is False


def test_profile_json_round_trip_and_validation():
    raw = asdict(FX)
    raw["effective_date"] = FX.effective_date.isoformat()
    raw["last_verified"] = FX.last_verified.isoformat()
    assert profile_from_dict(raw) == FX
    with pytest.raises(ProfileError):
        profile_from_dict({**raw, "surprise": 1})
    with pytest.raises(ProfileError):
        profile_from_dict({**raw, "floor_type": "WHATEVER"})
    with pytest.raises(ProfileError):
        profile_from_dict({**raw, "floor_lock_at": 47000.0})
