from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from backtesting.experimental_major_single_orchestrator_v1 import ExperimentalMajorSingleTargetOrchestratorV1
from backtesting.market_data import CanonicalTimeframe
from backtesting.orchestrator import TradingBrainEvaluationOrchestrator
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p23_liquidity import LiquidityInventory, LiquidityReference, LiquiditySide


def active_range():
    return StructuralRange("range", "5m", Decimal("110"), Decimal("90"), "h", "l",
        Decimal("110"), Decimal("90"), StructuralRegime.BULLISH, 1, 1, True, False, "event")


def select(engine, inventory):
    if isinstance(engine, ExperimentalMajorSingleTargetOrchestratorV1):
        engine.dataset = SimpleNamespace(dataset_id="empty", candles=())
    return engine._select_target(inventory=inventory, current_price=Decimal("100"),
        active_range=active_range(), regime=StructuralRegime.BULLISH,
        selection_time=10, previous_active_lrl=None, setup_invalidated=False)


def test_research_subclass_selects_external_pdh_single_only():
    pdh = LiquidityReference("pdh", "1m", LiquiditySide.BSL, Decimal("105"), 5, "PDH", True)
    minor = LiquidityReference("minor", "1m", LiquiditySide.BSL, Decimal("103"), 5, "SESSION_HIGH", False)
    inventory = LiquidityInventory((), (minor, pdh))
    result = select(object.__new__(ExperimentalMajorSingleTargetOrchestratorV1), inventory)
    assert result.active_lrl is not None and result.active_lrl.pool_id == "pdh"
    assert result.active_lrl.level == Decimal("105")


def test_default_canonical_selector_still_rejects_all_singles():
    pdh = LiquidityReference("pdh", "1m", LiquiditySide.BSL, Decimal("105"), 5, "PDH", True)
    result = select(object.__new__(TradingBrainEvaluationOrchestrator), LiquidityInventory((), (pdh,)))
    assert result.active_lrl is None


def test_research_orchestrator_has_no_authority_surface():
    assert ExperimentalMajorSingleTargetOrchestratorV1.comparison_only
    assert not ExperimentalMajorSingleTargetOrchestratorV1.canonical_policy_changed
    assert not ExperimentalMajorSingleTargetOrchestratorV1.paper_execution_permitted
    source = __import__("pathlib").Path(__file__).with_name(
        "experimental_major_single_orchestrator_v1.py").read_text()
    for forbidden in ("SubmitOrder", "CreateOrder", "from execution", "trading_authority = True"):
        assert forbidden not in source


def test_globex_session_reference_requires_exact_complete_1700_to_1600_window():
    start = datetime(2026, 9, 8, 22, tzinfo=timezone.utc)
    candles = tuple(SimpleNamespace(id=str(i), timeframe=CanonicalTimeframe.M1,
        open_time=start + timedelta(minutes=i), close_time=start + timedelta(minutes=i + 1),
        high=Decimal("105") if i == 100 else Decimal("101"),
        low=Decimal("95") if i == 200 else Decimal("99")) for i in range(1380))
    engine = object.__new__(ExperimentalMajorSingleTargetOrchestratorV1)
    engine.dataset = SimpleNamespace(dataset_id="dataset", candles=candles)
    at = int(datetime(2026, 9, 9, 22, tzinfo=timezone.utc).timestamp() * 1000)
    high = engine._prior_completed_session_candidates(
        selection_time=at, required_side=LiquiditySide.BSL)
    assert len(high) == 1 and high[0].source_type == "PDH" and high[0].level == Decimal("105")
    engine.dataset = SimpleNamespace(dataset_id="dataset", candles=candles[:-1])
    assert engine._prior_completed_session_candidates(
        selection_time=at, required_side=LiquiditySide.BSL) == ()


def test_monday_uses_latest_complete_friday_session_not_weekend():
    start = datetime(2026, 9, 10, 22, tzinfo=timezone.utc)
    candles = tuple(SimpleNamespace(id=f"f{i}", timeframe=CanonicalTimeframe.M1,
        open_time=start + timedelta(minutes=i), close_time=start + timedelta(minutes=i + 1),
        high=Decimal("106") if i == 20 else Decimal("101"), low=Decimal("99"))
        for i in range(1380))
    engine = object.__new__(ExperimentalMajorSingleTargetOrchestratorV1)
    engine.dataset = SimpleNamespace(dataset_id="weekend", candles=candles)
    monday = int(datetime(2026, 9, 14, 7, tzinfo=timezone.utc).timestamp() * 1000)
    result = engine._prior_completed_session_candidates(
        selection_time=monday, required_side=LiquiditySide.BSL)
    assert len(result) == 1 and result[0].level == Decimal("106")
