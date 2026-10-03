"""Historical warmup outcomes must not become live-session rejection evidence."""
from datetime import timedelta

import pytest

from mes_pilot.setups import Setup
from mes_pilot.tests.helpers import DAY, FLAT, bar, et
from mes_pilot.tests.test_engine_failures import engine


@pytest.mark.parametrize("state", ["REJECTED", "INVALIDATED", "EXPIRED", "CANCELLED", "CLOSED"])
def test_terminal_warmup_outcomes_do_not_leak_but_live_transitions_still_log(cfg_no_vol, tmp_path, state):
    eng = engine(cfg_no_vol, tmp_path)
    eng.warmup = True
    historical_at = et(DAY, 8, 0)
    historical = Setup("historical", "CONTINUATION_C1", "LONG", historical_at,
                       historical_at + timedelta(minutes=15))
    historical.move(state, historical_at + timedelta(minutes=1), "HISTORICAL_REASON")
    live_at = et(DAY, 9, 31)
    active = Setup("still-active", "CONTINUATION_C1", "LONG", live_at,
                   live_at + timedelta(minutes=15), state="ARMED")
    eng.detector.setups.update({historical.setup_id: historical, active.setup_id: active})
    structure, levels, volatility, accumulation = eng.tfs, eng.book, eng.vol, eng.accum

    eng.end_warmup()
    eng._log_terminal_setups(bar(live_at, *FLAT))
    assert eng.ledger.records("SETUP_TERMINAL") == []
    assert dict(eng._session_stats["reasons"]) == {}
    assert eng.detector.setups[active.setup_id] is active
    assert (eng.tfs, eng.book, eng.vol, eng.accum) == (structure, levels, volatility, accumulation)

    active.move("REJECTED", live_at + timedelta(minutes=1), "LIVE_REASON")
    eng._log_terminal_setups(bar(live_at + timedelta(minutes=1), *FLAT))
    eng._log_terminal_setups(bar(live_at + timedelta(minutes=2), *FLAT))
    assert [r["setup_id"] for r in eng.ledger.records("SETUP_TERMINAL")] == [active.setup_id]
    assert dict(eng._session_stats["reasons"]) == {"CONTINUATION_C1:LIVE_REASON": 1}
    assert eng.ledger.verify_chain()
