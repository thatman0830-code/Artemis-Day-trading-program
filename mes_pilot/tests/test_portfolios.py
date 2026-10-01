"""Paper portfolio isolation, trailing-floor persistence and quote exits."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from mes_pilot.config import parse_config
from mes_pilot.portfolios import NAMES, PortfolioGroup, load_portfolio_configs
from mes_pilot.risk import PilotRiskManager
from mes_pilot.simulator import Quote
from mes_pilot.tests.helpers import DAY, preset_levels, et
from mes_pilot.tests.test_engine_failures import calendar, scenario


def test_three_profiles_share_strategy_but_have_separate_100k_trailing_books(tmp_path):
    configs = load_portfolio_configs()
    assert tuple(configs) == NAMES
    assert {cfg.risk.starting_equity for cfg in configs.values()} == {100000}
    assert {cfg.risk.floor_model for cfg in configs.values()} == {"INTRADAY_TRAILING"}
    assert {cfg.risk.drawdown_allowance for cfg in configs.values()} == {3000}
    assert {cfg.risk.execution_reserve for cfg in configs.values()} == {200}
    assert [configs[n].risk.max_contracts for n in NAMES] == [1, 2, 3]

    # One hand-built, causally identical qualifying setup reaches each book.
    for name, cfg in list(configs.items()):
        raw = deepcopy(cfg.raw)
        raw["strategy"]["volatility_filter_enabled"] = False
        configs[name] = parse_config(raw)
    group = PortfolioGroup(configs, out_dir=tmp_path, calendar=calendar(DAY),
                           data_source="TEST", quote_mode="MODELED")
    for eng in group.engines.values():
        eng.tfs[60].bias = eng.tfs[240].bias = "BULLISH"
        preset_levels(eng.book, et(DAY, 9, 30) - timedelta(hours=2))
    for bar in scenario(hold_minutes=2):
        group.process_bar(bar)
    (tmp_path / "group-kill-switch.json").write_text('{"active": true}', encoding="utf-8")
    group.process_quote(Quote(et(DAY, 9, 43) + timedelta(seconds=1), 5002.0, 5002.25,
                              "TEST_LIVE", et(DAY, 9, 43) + timedelta(seconds=1)))
    group.finish()
    comparison = group.comparison()
    assert comparison["same_signal_ids"] is True
    assert comparison["shared_signal_count"] == 1
    assert [group.engines[n].ledger.records("FILL")[0]["filled_qty"] for n in NAMES] == [1, 2, 3]
    assert all(group.engines[n].ledger.records("POSITION_CLOSED")[0]["exit_reason"] == "KILL_SWITCH_FLATTEN"
               for n in NAMES)
    assert len({group.engines[n].cfg.config_hash for n in NAMES}) == 3
    assert all(group.engines[n].ledger.verify_chain() for n in NAMES)


def test_intraday_open_profit_raises_persisted_floor_then_breach_latches(tmp_path):
    cfg = load_portfolio_configs()["MODERATE"]
    state = tmp_path / "risk-state.json"
    risk = PilotRiskManager(cfg, state)
    assert risk.state.floor_usd == 97000
    mark = risk.mark_equity(101000)
    assert (mark["peak"], mark["floor"], mark["breached"]) == (101000, 98000, False)
    risk = PilotRiskManager(cfg, state)
    assert risk.state.floor_usd == 98000
    assert risk.mark_equity(99000)["floor"] == 98000  # never moves down
    breach = risk.mark_equity(98000)
    assert breach["new_breach"] is True
    assert PilotRiskManager(cfg, state).state.floor_breached is True
    decision = risk.evaluate_and_reserve(intent_id="after-breach", side="LONG", entry=5000,
                                         stop=4999, session_open=True, kill_switch=False)
    assert not decision.approved
    assert any(x.name == "synthetic_floor_not_breached" and not x.passed for x in decision.limits)


def test_live_quote_hits_protective_stop_without_waiting_for_next_bar(cfg_no_vol, tmp_path):
    from mes_pilot.tests.test_engine_failures import engine, feed

    eng = engine(cfg_no_vol, tmp_path)
    feed(eng, scenario(hold_minutes=0))
    assert len(eng.pending) == 1
    decision_time = eng.pending[0][0].created_at
    eng.process_quote(Quote(decision_time + timedelta(seconds=1), 5001.25, 5001.5, "TEST_LIVE",
                            decision_time + timedelta(seconds=1)))
    assert len(eng.simulator.open_positions()) == 1
    eng.process_quote(Quote(decision_time + timedelta(seconds=2), 4998.0, 4998.25, "TEST_LIVE",
                            decision_time + timedelta(seconds=2)))
    closed = eng.ledger.records("POSITION_CLOSED")
    assert len(closed) == 1 and closed[0]["exit_reason"] == "STOP"
    assert eng.simulator.open_positions() == []
