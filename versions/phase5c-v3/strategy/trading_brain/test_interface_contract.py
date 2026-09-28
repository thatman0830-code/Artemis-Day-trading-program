import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
from decimal import Decimal
import importlib
import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import strategy.trading_brain as trading_brain
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingEngine
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_4_exit_resolution import (
    OpenPositionBoundary,
    PositionState as ExitPositionState,
)
from strategy.trading_brain.p29_6_position_lifecycle import PositionState
from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccounting, TradeAccountingEngine
from strategy.trading_brain.p29_7_2_1_trade_classification_count import TradeClassificationCountEngine, TradeCountScope
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodDefinition, PeriodStatisticsEngine, PeriodType
from strategy.trading_brain.test_p29_7_1_trade_accounting import completed
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


PACKAGE = Path(__file__).parent
PRODUCTION_FILES = tuple(sorted(path for path in PACKAGE.glob("*.py") if not path.name.startswith("test_") and path.name != "__init__.py"))
FORBIDDEN_ROOTS = {"exchange", "execution", "risk", "database", "config", "engine", "web3", "eth_account"}
ECONOMIC_TOKENS = ("price", "quantity", "risk", "pnl", "equity", "cost", "fee", "tick", "step", "reward", "return", "variance", "covariance", "correlation", "drawdown", "commission", "spread", "slippage", "multiplier")


def production_modules():
    return tuple(importlib.import_module(f"strategy.trading_brain.{path.stem}") for path in PRODUCTION_FILES)


def test_public_manifest_imports_every_frozen_entry_point():
    assert trading_brain.INTERFACE_CONTRACT_VERSION == "trading-brain-interface-v1"
    assert set(trading_brain.PUBLIC_ENGINE_ENTRY_POINTS) == {
        "#11", "#13", "#16", "#19", "#20", "#21", "#22", "#23", "#24", "#25", "#26", "#27", "#28",
        "#29.1", "#29.2", "#29.3", "#29.4", "#29.5", "#29.6", "#29.7.1",
            *(f"#29.7.2.{number}" for number in range(1, 21)),
            "OWNER_MIN_RR_V1", "OWNER_WIN_RATE_OBJECTIVE_V1",
        }
    for entries in trading_brain.PUBLIC_ENGINE_ENTRY_POINTS.values():
        for entry in entries:
            module_name, class_name, method_name = entry.split(".")
            module = importlib.import_module(f"strategy.trading_brain.{module_name}")
            owner = getattr(module, class_name)
            assert inspect.isclass(owner) and callable(getattr(owner, method_name))


def test_production_import_graph_is_acyclic_and_has_no_reverse_exit_lifecycle_dependency():
    module_names = {path.stem for path in PRODUCTION_FILES}
    graph = {name: set() for name in module_names}
    for path in PRODUCTION_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("strategy.trading_brain."):
                dependency = node.module.rsplit(".", 1)[-1]
                if dependency in graph:
                    graph[path.stem].add(dependency)
    assert "p29_6_position_lifecycle" not in graph["p29_4_exit_resolution"]
    visiting, visited = set(), set()

    def visit(module):
        assert module not in visiting, f"circular Trading Brain imports at {module}"
        if module in visited:
            return
        visiting.add(module)
        for dependency in graph[module]:
            visit(dependency)
        visiting.remove(module)
        visited.add(module)

    for module in graph:
        visit(module)


def test_all_public_domain_records_are_frozen_and_histories_are_tuple_based():
    found = 0
    for module in production_modules():
        for value in vars(module).values():
            if inspect.isclass(value) and value.__module__ == module.__name__ and is_dataclass(value):
                found += 1
                assert value.__dataclass_params__.frozen, f"{value.__module__}.{value.__name__} is mutable"
                for field in fields(value):
                    if value.__name__.endswith("History"):
                        assert "tuple" in str(field.type), f"history field {value.__name__}.{field.name} is not append-only"
    assert found > 100


def test_no_binary_float_or_forbidden_external_import_boundary_in_production_package():
    for path in PRODUCTION_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
                assert not roots & FORBIDDEN_ROOTS
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in FORBIDDEN_ROOTS
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "float", f"binary float conversion in {path.name}:{node.lineno}"
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                assert node.id != "float", f"float annotation/use in {path.name}:{node.lineno}"


def test_market_data_contract_emits_decimal_immutable_deterministic_swings():
    candles = pd.DataFrame([
        {"t": 1, "h": "10", "l": "5", "is_closed": True},
        {"t": 2, "h": "11", "l": "4", "is_closed": True},
        {"t": 3, "h": "15", "l": "3", "is_closed": True},
        {"t": 4, "h": "12", "l": "4", "is_closed": True},
        {"t": 5, "h": "11", "l": "5", "is_closed": True},
    ])
    first = MechanicalSwingEngine().detect(timeframe="5m", candles=candles)
    replay = MechanicalSwingEngine().detect(timeframe="5m", candles=candles.copy())
    assert replay == first and first.swings
    assert all(isinstance(item.price, Decimal) for item in first.swings)
    with pytest.raises(FrozenInstanceError):
        first.swings[0].price = Decimal("99")
    future = candles.iloc[:-1]
    assert MechanicalSwingEngine().detect(timeframe="5m", candles=future).swings == ()


def test_consecutive_execution_lifecycle_accounting_handoff_preserves_identity_versions_and_decimals():
    source = completed()
    record = TradeAccountingEngine().calculate(**source).record
    assert isinstance(record, TradeAccounting)
    position = source["position"]
    fill = source["entry_fill"]
    sizing = source["sizing"]
    execution = source["exit_execution"]
    costs = source["costs"]
    assert record.position_id == position.id
    assert record.entry_fill_id == fill.id == sizing.entry_fill_id == costs.entry_fill_id
    assert record.sizing_id == sizing.id == costs.position_sizing_id
    assert record.exit_execution_id == execution.id == costs.exit_execution_id == position.exit_execution_id
    assert record.input_version == position.input_version == sizing.input_version == execution.input_version == costs.input_version
    for field in fields(record):
        name_parts = set(field.name.lower().split("_"))
        if not field.name.endswith("_id") and (name_parts & set(ECONOMIC_TOKENS) or field.name.endswith("_r")):
            value = getattr(record, field.name)
            if value is not None:
                assert isinstance(value, Decimal), field.name


def test_open_position_compatibility_boundary_accepts_lifecycle_enum_without_reverse_import():
    assert ExitPositionState is PositionState
    boundary = OpenPositionBoundary("open", "setup", "fill", "protective", "BTC", "1m", "v1", PositionState.OPEN, 10)
    assert getattr(boundary.state, "value", boundary.state) == "OPEN"
    module_source = (PACKAGE / "p29_4_exit_resolution.py").read_text(encoding="utf-8")
    assert "p29_6_position_lifecycle import" not in module_source


def test_timezone_period_identity_is_explicit_half_open_and_fail_closed():
    start, end = 1786320000, 1786406400
    assert ZoneInfo("UTC") is not None
    scope = TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1")
    period = PeriodDefinition(PeriodType.DAILY, "UTC", start, end, "source-v1", "history-v1")
    result = PeriodStatisticsEngine().calculate(scope=scope, period=period, trades=(), as_of_time=end)
    assert result.valid and result.snapshot.period_start == start and result.snapshot.period_end == end
    assert result.snapshot.account_timezone == "UTC"
    invalid = PeriodStatisticsEngine().calculate(scope=scope, period=PeriodDefinition(PeriodType.DAILY, "Invalid/Zone", start, end, "source-v1", "history-v1"), trades=(), as_of_time=end)
    assert invalid.error.reason == "ACCOUNT_TIMEZONE_INVALID"


def test_no_lookahead_and_fail_closed_missing_or_incompatible_inputs():
    scope = TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1")
    past = accounting(suffix="past", closed=29)
    future = accounting(suffix="future", closed=31)
    result = TradeClassificationCountEngine().calculate(scope=scope, trades=(future, past), as_of_time=30)
    assert result.snapshot.source_trade_ids == ("trade-past",)
    assert result.snapshot.future_excluded_trade_ids == ("trade-future",)
    assert TradeClassificationCountEngine().calculate(scope=scope, trades=None, as_of_time=30).error is not None
    mismatch = TradeClassificationCountEngine().calculate(scope=scope, trades=(accounting(suffix="x", closed=29),), as_of_time=30)
    assert mismatch.valid
    wrong = accounting(suffix="wrong", closed=29)
    wrong = wrong.__class__(**{**wrong.__dict__, "strategy_id": "other"})
    assert TradeClassificationCountEngine().calculate(scope=scope, trades=(wrong,), as_of_time=30).error is not None


def test_strategy_execution_authority_and_analytics_feedback_are_absent():
    analytics_prefix = "p29_7_2_"
    pre_analytics = {path.stem for path in PRODUCTION_FILES if not path.stem.startswith(analytics_prefix)}
    for path in PRODUCTION_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {node.module.rsplit(".", 1)[-1] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("strategy.trading_brain.")}
        if path.stem in pre_analytics:
            assert not any(name.startswith(analytics_prefix) for name in imported)
        if path.stem.startswith(analytics_prefix):
            public_methods = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
            assert not public_methods & {"arm", "authorize", "size", "submit", "open", "close"}
    entry_module = importlib.import_module("strategy.trading_brain.p29_1_entry_execution")
    assert set(name for name, _ in inspect.getmembers(entry_module.EntryExecutionEngine, inspect.isfunction)).isdisjoint({"submit", "sign", "place_order", "authorize"})


def test_idempotent_accounting_replay_and_missing_contract_documentation():
    source = completed()
    engine = TradeAccountingEngine()
    first = engine.calculate(**source)
    replay = engine.calculate(**source, history=first.history)
    assert replay.record == first.record and replay.history == first.history
    text = (PACKAGE / "INTERFACE_CONTRACT.md").read_text(encoding="utf-8")
    for heading in ("Confirmed stable interfaces", "Compatibility adapters needed later", "Unresolved canonical ambiguities", "Non-blocking technical debt", "Backtesting blockers"):
        assert heading in text
    for forbidden in ("private keys", "mainnet", "exchange submission", "does not authorize"):
        assert forbidden.lower() in text.lower()
