from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import pytest

from backtesting.core_v1.capabilities import EngineCapabilities
from backtesting.core_v1.engine import CalculationEngine
from backtesting.core_v1.models import Action, ActionKind, EndPolicy, ExecutionConfig, OrderType, Side
from backtesting.core_v1.strategy import NoOpStrategy
from backtesting.test_core_v1 import T0, archive, bar, config, spec


def test_strategy_view_is_market_and_time_bounded(tmp_path):
    observed = []
    class Probe:
        requirements = NoOpStrategy(markets=("ES",)).requirements
        def evaluate(self, trigger, state):
            observed.append(state)
            assert all(row.market == "ES" for row in state.bars)
            assert all(row.close_time <= state.event_time for row in state.bars)
            return ()
    es = archive(tmp_path, market="ES", instrument="ESM6", contract="ESM6")
    btc = archive(tmp_path, market="BTC", instrument="BTC", contract=None,
                  bars=(bar(0, market="BTC", instrument="BTC", contract=None),))
    CalculationEngine().run(strategy=Probe(), archives=(es, btc), specs=(spec(), spec("BTC", "BTC")),
                            configuration=config())
    assert observed


def test_data_quality_halt_blocks_same_bar_action_and_fill(tmp_path):
    class Probe:
        requirements = NoOpStrategy().requirements
        def evaluate(self, trigger, state):
            return (Action("x", ActionKind.ENTER, "ESM6", Side.BUY, Decimal("1")),)
    rows = (bar(0), replace(bar(1), missing_before=1), bar(2))
    result = CalculationEngine().run(strategy=Probe(), archives=(archive(tmp_path, bars=rows),),
                                     specs=(spec(),), configuration=config())
    assert "DATA_QUALITY_HALT_ACTION_REJECTED" in result.rejections
    assert all(fill.bar_id != "b1" for fill in result.fills)


def test_strategy_cannot_mutate_snapshot(tmp_path):
    class Probe:
        requirements = NoOpStrategy().requirements
        def evaluate(self, trigger, state):
            with pytest.raises(FrozenInstanceError):
                state.equity = Decimal("0")
            return ()
    CalculationEngine().run(strategy=Probe(), archives=(archive(tmp_path),), specs=(spec(),),
                            configuration=config())


def test_result_identity_changes_for_economic_inputs(tmp_path):
    a = archive(tmp_path); engine = CalculationEngine()
    baseline = engine.run(strategy=NoOpStrategy(), archives=(a,), specs=(spec(),), configuration=config())
    changed_spec = replace(spec(), commission_rate=Decimal("0.0002"))
    changed = engine.run(strategy=NoOpStrategy(), archives=(a,), specs=(changed_spec,), configuration=config())
    changed_seed = engine.run(strategy=NoOpStrategy(), archives=(a,), specs=(spec(),),
                              configuration=replace(config(), random_seed=7))
    assert len({baseline.id, changed.id, changed_seed.id}) == 3


def test_wall_clock_does_not_change_machine_result(tmp_path):
    a = archive(tmp_path); engine = CalculationEngine()
    one = engine.run(strategy=NoOpStrategy(), archives=(a,), specs=(spec(),), configuration=config())
    two = engine.run(strategy=NoOpStrategy(), archives=(a,), specs=(spec(),), configuration=config())
    assert one.machine_json() == two.machine_json()


def test_capability_truthfully_rejects_unimplemented_behaviors(tmp_path):
    assert EngineCapabilities().supported_order_types == (OrderType.MARKET,)
    assert not EngineCapabilities().funding_supported
    assert not EngineCapabilities().rollover_supported
    with pytest.raises(ValueError, match="END_FLATTEN_UNSUPPORTED"):
        CalculationEngine().run(strategy=NoOpStrategy(), archives=(archive(tmp_path),), specs=(spec(),),
                                configuration=replace(config(), execution=ExecutionConfig(
                                    "1", Decimal("0.5"), EndPolicy.FLATTEN)))


def test_reversal_resets_average_to_residual_fill_price(tmp_path):
    class Reverse:
        requirements = NoOpStrategy().requirements
        def evaluate(self, trigger, state):
            if trigger.event.sequence == 0:
                return (Action("buy", ActionKind.ENTER, "ESM6", Side.BUY, Decimal("1")),)
            if trigger.event.sequence == 1:
                return (Action("sell", ActionKind.ENTER, "ESM6", Side.SELL, Decimal("2")),)
            return ()
    result = CalculationEngine().run(strategy=Reverse(), archives=(archive(tmp_path),), specs=(spec(),),
                                     configuration=config())
    assert result.positions[-1].quantity == Decimal("-1")
    assert result.positions[-1].average_price == result.fills[-1].price


def test_instrument_market_and_tick_grid_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="market/effective"):
        CalculationEngine().run(strategy=NoOpStrategy(), archives=(archive(tmp_path),),
            specs=(replace(spec(), market="NQ"),), configuration=config())
    bad = replace(bar(0), open=Decimal("100.1"), high=Decimal("102.1"))
    with pytest.raises(ValueError, match="tick grid"):
        CalculationEngine().run(strategy=NoOpStrategy(), archives=(archive(tmp_path, bars=(bad,)),),
            specs=(spec(),), configuration=config())


def test_cross_market_action_rejects_without_accounting_mutation(tmp_path):
    class CrossMarket:
        requirements = NoOpStrategy().requirements
        def evaluate(self, trigger, state):
            return (Action("cross",ActionKind.ENTER,"NQM6",Side.BUY,Decimal("1")),)
    result=CalculationEngine().run(strategy=CrossMarket(),archives=(archive(tmp_path),),specs=(spec(),),configuration=config())
    assert result.fills==() and result.positions==()
    assert "ACTION_SCOPE_OR_QUANTITY_INVALID" in result.rejections
    assert all(row.equity==config().starting_cash for row in result.accounting)


@pytest.mark.parametrize("order_type",[OrderType.LIMIT,OrderType.STOP])
def test_unsupported_price_order_rejected_before_replay(tmp_path,order_type):
    class Unsupported:
        requirements = replace(NoOpStrategy().requirements,order_types=(order_type,))
        def evaluate(self,trigger,state): return ()
    with pytest.raises(ValueError,match="UNSUPPORTED_ORDER_TYPE"):
        CalculationEngine().run(strategy=Unsupported(),archives=(archive(tmp_path),),specs=(spec(),),configuration=config())


def test_rollover_required_strategy_rejected_before_position(tmp_path):
    class Rollover:
        requirements = replace(NoOpStrategy().requirements,requires_rollover=True)
        def evaluate(self,trigger,state): return ()
    with pytest.raises(ValueError,match="MISSING_ROLLOVER"):
        CalculationEngine().run(strategy=Rollover(),archives=(archive(tmp_path),),specs=(spec(),),configuration=config())


def test_core_source_has_no_network_or_external_order_path():
    root = Path(__file__).parent / "core_v1"
    content = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py")).lower()
    for token in ("import requests", "import httpx", "import urllib", "import socket",
                  "import websocket", "submit_order", "private_key"):
        assert token not in content
