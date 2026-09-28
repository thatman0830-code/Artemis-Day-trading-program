from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import dataclasses
import json
import pytest

from backtesting.core_v1.adapters import ActiveContractWindow, VerifiedArchiveSlice
from backtesting.core_v1.capabilities import EngineCapabilities, validate_capabilities
from backtesting.core_v1.engine import CalculationEngine, EngineRunConfiguration
from backtesting.core_v1.models import (CoreBar, CoreEvent, EndPolicy, EventType,
    ExecutionConfig, InstrumentSpec, OrderType, RiskConfig, StrategyRequirements,
    TriggerKind, fingerprint)
from backtesting.core_v1.splits import PartitionRole, TimePartition, build_split_plan
from backtesting.core_v1.strategy import DeterministicFixtureStrategy, NoOpStrategy

UTC = timezone.utc
T0 = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def bar(n, *, market="ES", instrument="ESM6", contract="ESM6", volume="10", tradable=True):
    opened = T0 + timedelta(minutes=n)
    return CoreBar(f"b{n}", market, instrument, contract, opened, opened + timedelta(minutes=1),
        Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), Decimal(volume),
        "2026-01-05", "fixture", "1", "a" * 64, n, tradable)


def archive(tmp_path, *, market="ES", instrument="ESM6", contract="ESM6", bars=None):
    path = tmp_path / f"{market}.jsonl"; path.write_bytes(b"fixture\n")
    rows = tuple(bars or (bar(0, market=market, instrument=instrument, contract=contract),
                          bar(1, market=market, instrument=instrument, contract=contract),
                          bar(2, market=market, instrument=instrument, contract=contract)))
    windows = () if market == "BTC" else (ActiveContractWindow(contract, T0, T0+timedelta(days=1), "roll-1"),)
    return VerifiedArchiveSlice(market, instrument, path, sha256(path.read_bytes()).hexdigest(),
                                f"fp-{market}", rows, windows)


def spec(market="ES", instrument="ESM6"):
    return InstrumentSpec("spec", instrument, market, Decimal("0.25"), Decimal("1"), Decimal("50"),
        Decimal("0.1"), Decimal("0.0001"), Decimal("1"), T0-timedelta(days=1), None, "official", "1")


def config(end_policy=EndPolicy.REJECT_OPEN):
    return EngineRunConfiguration("run", "1", Decimal("100000"),
        ExecutionConfig("1", Decimal("0.5"), end_policy),
        RiskConfig("1", Decimal("1000000"), Decimal("500000"), Decimal("1")),
        T0, T0+timedelta(hours=1))


def test_immutable_decimal_utc_contract():
    row = bar(0)
    with pytest.raises(dataclasses.FrozenInstanceError): row.close = Decimal("1")
    with pytest.raises(TypeError):
        dataclasses.replace(row, open=100.0)
    with pytest.raises(ValueError):
        dataclasses.replace(row, close_time=datetime(2026, 1, 1))


def test_event_priority_is_stable():
    events = [CoreEvent(str(i), kind, T0, "ES", "ESM6", "ESM6", "s", "x", "y", i)
              for i, kind in enumerate(reversed(tuple(EventType)))]
    assert [e.event_type for e in sorted(events, key=lambda e: e.ordering_key)] == list(EventType)


def test_point_in_time_adapter_and_checksum(tmp_path):
    a = archive(tmp_path)
    assert [x.id for x in a.visible_at(T0+timedelta(minutes=2))] == ["b0", "b1"]
    a.path.write_text("changed")
    with pytest.raises(ValueError, match="checksum"): a.validate()


def test_futures_requires_one_active_contract_window(tmp_path):
    a = archive(tmp_path)
    broken = dataclasses.replace(a, active_windows=())
    with pytest.raises(ValueError, match="active-contract"): broken.validate()


def test_capability_rejects_missing_funding_rollover_and_volume():
    req = StrategyRequirements("x", "1", ("BTC", "ES"), (), (TriggerKind.MARKET,),
                               (OrderType.MARKET,), True, True, True)
    report = validate_capabilities(req, capabilities=EngineCapabilities(), has_volume=False,
                                   has_funding=False, has_rollover=False)
    assert not report.accepted
    assert {x.code for x in report.issues} == {"MISSING_VOLUME", "MISSING_FUNDING", "MISSING_ROLLOVER"}


def test_signal_bar_cannot_fill_itself_and_next_open_is_used(tmp_path):
    a = archive(tmp_path)
    result = CalculationEngine().run(strategy=DeterministicFixtureStrategy("ESM6", "ES", Decimal("1"), 0, 9),
                                     archives=(a,), specs=(spec(),), configuration=config())
    assert len(result.fills) == 1
    assert result.fills[0].bar_id == "b1"
    assert result.fills[0].price == Decimal("100.25")
    assert result.fills[0].event_time >= result.orders[0].submitted_at


def test_nontradable_bar_does_not_fill(tmp_path):
    a = archive(tmp_path, bars=(bar(0), bar(1, tradable=False), bar(2)))
    result = CalculationEngine().run(strategy=DeterministicFixtureStrategy("ESM6", "ES", Decimal("1"), 0, 9),
                                     archives=(a,), specs=(spec(),), configuration=config())
    assert result.fills[0].bar_id == "b2"


def test_volume_participation_creates_partial_fill(tmp_path):
    a = archive(tmp_path, bars=(bar(0), bar(1, volume="1"), bar(2, volume="1")))
    cfg = dataclasses.replace(config(), execution=ExecutionConfig("1", Decimal("1"), EndPolicy.REJECT_OPEN))
    result = CalculationEngine().run(strategy=DeterministicFixtureStrategy("ESM6", "ES", Decimal("2"), 0, 9),
                                     archives=(a,), specs=(spec(),), configuration=cfg)
    assert result.fills and result.fills[0].partial


def test_deterministic_machine_output_excludes_runtime(tmp_path):
    a = archive(tmp_path); engine = CalculationEngine(); strategy = NoOpStrategy()
    one = engine.run(strategy=strategy, archives=(a,), specs=(spec(),), configuration=config())
    two = engine.run(strategy=strategy, archives=(a,), specs=(spec(),), configuration=config())
    assert one.id == two.id
    assert one.machine_json() == two.machine_json()
    assert "elapsed_seconds" not in one.machine_json()


def test_limit_and_stop_ambiguity_fails_closed(tmp_path):
    class LimitStrategy:
        requirements = StrategyRequirements("limit", "1", ("ES",), (), (TriggerKind.MARKET,), (OrderType.LIMIT,))
        def evaluate(self, trigger, state):
            from backtesting.core_v1.models import Action, ActionKind, Side
            return (Action("a", ActionKind.ENTER, "ESM6", Side.BUY, Decimal("1"), OrderType.LIMIT,
                           Decimal("100")),)
    with pytest.raises(ValueError, match="UNSUPPORTED_ORDER_TYPE"):
        CalculationEngine().run(strategy=LimitStrategy(), archives=(archive(tmp_path),),
                                specs=(spec(),), configuration=config())


def test_chronological_partitions_and_embargo():
    rows = tuple(TimePartition(str(i), "BTC", role, T0+timedelta(days=i*10),
        T0+timedelta(days=i*10+8), timedelta(days=1), timedelta(days=1))
        for i, role in enumerate(PartitionRole))
    assert build_split_plan(version="1", partitions=rows).partitions == rows
    bad = (rows[0], dataclasses.replace(rows[1], start_inclusive=rows[0].end_exclusive), rows[2])
    with pytest.raises(ValueError, match="overlap"): build_split_plan(version="1", partitions=bad)


def test_result_is_advisory_and_requires_200_oos(tmp_path):
    result = CalculationEngine().run(strategy=NoOpStrategy(), archives=(archive(tmp_path),),
                                     specs=(spec(),), configuration=config())
    assert result.advisory_acceptance == "INSUFFICIENT_EVIDENCE"


def test_core_has_no_exchange_or_credentials_imports():
    root = Path(__file__).parent / "core_v1"
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
    for prohibited in ("private_key", "wallet", "signing", "exchange_order", "websocket"):
        assert prohibited not in text.lower()
