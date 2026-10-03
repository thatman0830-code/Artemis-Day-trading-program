"""Coordinator integration regressions (engine/runner fixes after the agent reviews)."""
from __future__ import annotations

from datetime import timedelta

from mes_pilot.engine import _series
from mes_pilot.simulator import Quote
from mes_pilot.tests.helpers import DAY, FLAT, bar, c1_long_prefix, et
from mes_pilot.tests.test_engine_failures import engine, feed, scenario
from mes_pilot.tests.test_setups import only, run


def test_live_quote_between_bars_fills_pending_intent_within_lifetime(cfg_no_vol, tmp_path):
    # Without process_quote a live intent waited ~60.3 s for the next bar and expired (lifetime 60 s).
    eng = engine(cfg_no_vol, tmp_path)
    feed(eng, scenario(hold_minutes=0))           # ends with the confirming retest bar (decision at its close)
    assert len(eng.pending) == 1
    intent = eng.pending[0][0]
    q = Quote(intent.created_at + timedelta(seconds=1), 5001.25, 5001.5, "TEST_LIVE", intent.created_at + timedelta(seconds=1))
    eng.process_quote(q)
    assert eng.pending == []
    (fill,) = eng.ledger.records("FILL")
    assert fill["fill_price"] == 5001.5 and fill["latency_s"] == 1.0
    assert eng.ledger.records("ORDER")[0]["status"] == "FILLED"


def test_es_and_mes_same_expiry_is_one_series_no_structure_reset(cfg_no_vol, tmp_path):
    assert _series("ESZ6") == _series("MESZ6") == _series("TEST-MESZ6") == "Z6"
    assert _series("ESH7") != _series("MESZ6")
    eng = engine(cfg_no_vol, tmp_path)
    s = et(DAY, 8, 0)
    eng.process_bar(bar(s, *FLAT, contract="ESZ6"))
    eng.process_bar(bar(s + timedelta(minutes=1), *FLAT, contract="MESZ6"))
    assert eng.ledger.records("STRUCTURE_RESET") == []          # live MES after ES warmup keeps structure
    eng.process_bar(bar(s + timedelta(minutes=2), *FLAT, contract="ESH7"))
    assert len(eng.ledger.records("STRUCTURE_RESET")) == 1      # a real contract roll still resets


def test_c1_displacement_candle_before_window_is_rejected(cfg):
    # A 09:20, B (displacement) 09:25 premarket, C 09:30: the detecting bar is in-window but the
    # displacement is premarket structure -> rejected under the pilot policy.
    h = run(cfg, c1_long_prefix(a_at=(9, 20)))
    st = only(h, "CONTINUATION_C1")
    assert (st.state, st.reason) == ("REJECTED", "C1_DISPLACEMENT_BEFORE_ENTRY_WINDOW")


def test_exchange_holiday_session_abstains_and_is_classified(cfg_no_vol, tmp_path):
    from datetime import date
    from mes_pilot.bars import is_exchange_holiday
    from mes_pilot.tests.test_engine_failures import calendar

    holiday = date(2026, 11, 26)                   # Thanksgiving (in the CME table)
    assert is_exchange_holiday(holiday)
    eng = engine(cfg_no_vol, tmp_path, cal=calendar(holiday), day=holiday)
    feed(eng, scenario(day=holiday, hold_minutes=1))
    eng.finish()
    reasons = [r["reason"] for r in eng.ledger.records("CANDIDATE")]
    assert reasons == ["EXCHANGE_HOLIDAY_SESSION"]
    assert eng.ledger.records("SESSION_SUMMARY")[-1]["classification"] == "EXCHANGE_HOLIDAY_NO_ENTRIES"
