import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.adapter import TradingBrainMarketDataAdapter
from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.market_data import (
    CanonicalTimeframe, Gap, GapPolicy, HistoricalCandle, HistoricalDataset, MultiTimeframeView,
    ValidationStatus, candle_identity, normalize_historical_candle,
    normalize_hyperliquid_candle, validate_dataset,
)
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingEngine


UTC = timezone.utc
BASE = datetime(2026, 8, 20, tzinfo=UTC)
PACKAGE = Path(__file__).parent


def raw(*, minute=0, timeframe="1m", open_="100", high="105", low="95",
        close="101", volume="10", closed=True, symbol="BTC"):
    tf = CanonicalTimeframe(timeframe)
    opened = BASE + timedelta(minutes=minute)
    return {
        "symbol": symbol, "timeframe": timeframe, "open_time": opened,
        "close_time": opened + tf.duration, "open": Decimal(open_),
        "high": Decimal(high), "low": Decimal(low), "close": Decimal(close),
        "volume": None if volume is None else Decimal(volume), "is_closed": closed,
    }


def candle(**changes):
    values = raw(**changes)
    return normalize_historical_candle(values, dataset_id="dataset-v1",
                                       schema_version="candles-v1",
                                       source="archive", exchange="hyperliquid")


def dataset(candles=None, *, policy=GapPolicy.REJECT, validation_time=None):
    items = tuple(candles if candles is not None else (candle(), candle(minute=1)))
    return validate_dataset(items, dataset_id="dataset-v1", schema_version="candles-v1",
                            source="archive", exchange="hyperliquid", gap_policy=policy,
                            validation_time=validation_time or BASE + timedelta(days=1))


def manifest(data=None):
    return DatasetManifest.from_dataset(data or dataset(), symbol="BTC",
                                        created_at=BASE + timedelta(days=1),
                                        configuration_id="import-config-v1")


def test_valid_exact_closed_candle_has_deterministic_identity_and_is_frozen():
    first = candle(); replay = candle()
    assert first == replay and first.id == replay.id
    assert all(isinstance(getattr(first, name), Decimal) for name in ("open", "high", "low", "close", "volume"))
    with pytest.raises(FrozenInstanceError):
        first.close = Decimal("1")


@pytest.mark.parametrize("updates", [
    {"high": "99"}, {"low": "102"}, {"high": "90", "low": "95"},
    {"open_": "0"}, {"low": "-1"}, {"volume": "-1"},
    {"high": "NaN"}, {"low": "Infinity"},
])
def test_invalid_geometry_nonpositive_volume_and_nonfinite_values_fail(updates):
    with pytest.raises(ValueError):
        candle(**updates)


def test_decimal_is_mandatory_and_no_float_is_implicitly_converted():
    values = raw(); values["open"] = 100.0
    with pytest.raises(TypeError, match="Decimal"):
        normalize_historical_candle(values, dataset_id="dataset-v1",
                                    schema_version="candles-v1", source="archive",
                                    exchange="hyperliquid")


def test_existing_hyperliquid_shape_normalizes_exact_strings_without_float_coercion():
    source = {
        "s": "BTC", "i": "1m", "t": int(BASE.timestamp()) * 1000,
        "T": int((BASE + timedelta(minutes=1)).timestamp()) * 1000,
        "o": "100.00", "h": "105", "l": "95", "c": "101.5", "v": "10.25",
        "is_closed": True,
    }
    normalized = normalize_hyperliquid_candle(source, dataset_id="dataset-v1", schema_version="candles-v1")
    assert normalized.open == Decimal("100.00") and normalized.volume == Decimal("10.25")
    with pytest.raises(TypeError, match="binary float"):
        normalize_hyperliquid_candle({**source, "o": 100.0}, dataset_id="dataset-v1", schema_version="candles-v1")


def test_utc_timezone_duration_alignment_and_closed_status_are_enforced():
    values = raw(); values["open_time"] = values["open_time"].replace(tzinfo=None)
    with pytest.raises(ValueError, match="UTC"):
        normalize_historical_candle(values, dataset_id="dataset-v1", schema_version="candles-v1", source="archive", exchange="hyperliquid")
    with pytest.raises(ValueError, match="completed"):
        candle(closed=False)
    with pytest.raises(ValueError, match="aligned"):
        candle(minute=1, timeframe="5m")
    values = raw(); values["close_time"] = values["open_time"]
    with pytest.raises(ValueError, match="before"):
        normalize_historical_candle(values, dataset_id="dataset-v1", schema_version="candles-v1", source="archive", exchange="hyperliquid")


def test_duplicate_identity_and_coordinate_fail_closed():
    item = candle()
    with pytest.raises(ValueError, match="Duplicate candle identity"):
        dataset((item, item))
    with pytest.raises(ValueError, match="identity"):
        replace(item, id="different")


def test_order_gaps_and_explicit_gap_policy():
    with pytest.raises(ValueError, match="ordering"):
        dataset((candle(minute=1), candle()))
    separated = (candle(), candle(minute=2))
    with pytest.raises(ValueError, match="gaps"):
        dataset(separated)
    accepted = dataset(separated, policy=GapPolicy.RECORD)
    assert accepted.validation_status is ValidationStatus.VALID_WITH_GAPS
    assert accepted.gaps[0].missing_count == 1


def test_overlap_and_wrong_interval_duration_are_rejected_at_record_boundary():
    values = raw(timeframe="5m")
    values["close_time"] = values["open_time"] + timedelta(minutes=6)
    with pytest.raises(ValueError, match="duration"):
        normalize_historical_candle(values, dataset_id="dataset-v1", schema_version="candles-v1", source="archive", exchange="hyperliquid")


def test_validation_cutoff_rejects_current_or_future_close():
    with pytest.raises(ValueError, match="Future"):
        dataset(validation_time=BASE + timedelta(seconds=30))


def test_fingerprint_is_exact_order_deterministic_and_value_sensitive():
    first = dataset(); replay = dataset()
    changed = dataset((candle(), candle(minute=1, close="102")))
    assert first.fingerprint == replay.fingerprint
    assert first.fingerprint != changed.fingerprint


def test_dataset_manifest_has_half_open_counts_gaps_versions_and_provenance():
    data = dataset((candle(), candle(minute=2)), policy=GapPolicy.RECORD)
    first = manifest(data); replay = manifest(data)
    assert first == replay and first.id == replay.id
    assert first.interval_start_inclusive == BASE
    assert first.interval_end_exclusive == BASE + timedelta(minutes=3, microseconds=1)
    assert first.candle_counts == ((CanonicalTimeframe.M1, 2),)
    assert first.gaps == data.gaps and first.timezone == "UTC"
    with pytest.raises(ValueError, match="does not match"):
        DatasetManifest.from_dataset(data, symbol="ETH", created_at=BASE, configuration_id="v1")


def test_run_manifest_is_deterministic_explicitly_simulated_and_never_submits():
    data_manifest = manifest()
    runtime = RuntimeFacts("3.11.9", "CPython", "Windows", "repo-v1")
    kwargs = dict(dataset=data_manifest, trading_brain_contract_version=INTERFACE_CONTRACT_VERSION,
                  strategy_configuration_version="strategy-v1", model_configuration_version="model-v1",
                  replay_start_inclusive=BASE, replay_end_exclusive=BASE + timedelta(minutes=2),
                  starting_equity=Decimal("10000"), execution_cost_configuration_id="cost-v1",
                  random_seed=0, runtime=runtime)
    first = BacktestRunManifest.create(**kwargs); replay = BacktestRunManifest.create(**kwargs)
    assert first == replay and first.mode == "PAPER_SIMULATION"
    assert first.exchange_submission_enabled is False
    with pytest.raises(ValueError, match="exchange submission disabled"):
        replace(first, exchange_submission_enabled=True)
    with pytest.raises(TypeError, match="Decimal"):
        BacktestRunManifest.create(**{**kwargs, "starting_equity": 10000.0})
    with pytest.raises(ValueError, match="outside"):
        BacktestRunManifest.create(**{**kwargs, "replay_end_exclusive": BASE + timedelta(days=1)})


def test_higher_timeframe_visibility_occurs_only_at_close_and_never_forward_fills():
    candles = (candle(timeframe="1m"), candle(minute=0, timeframe="5m"))
    data = dataset(candles)
    view = MultiTimeframeView(data)
    assert view.latest(timeframe=CanonicalTimeframe.H5 if False else CanonicalTimeframe.M5,
                       as_of=BASE + timedelta(minutes=4, seconds=59)) is None
    assert view.latest(timeframe=CanonicalTimeframe.M5,
                       as_of=BASE + timedelta(minutes=5)).id == candles[1].id
    assert view.visible(timeframe=CanonicalTimeframe.M1,
                        as_of=BASE + timedelta(minutes=4)) == (candles[0],)


def test_adapter_preserves_exact_values_ids_order_and_no_lookahead():
    adapter = TradingBrainMarketDataAdapter(dataset())
    as_of = BASE + timedelta(minutes=1)
    frame = adapter.to_mechanical_swing_frame(symbol="BTC", timeframe=CanonicalTimeframe.M1, as_of=as_of)
    mappings = adapter.to_candle_mappings(symbol="BTC", timeframe=CanonicalTimeframe.M1, as_of=as_of)
    assert len(frame) == len(mappings) == 1
    assert frame.iloc[0]["id"] == mappings[0]["id"] == candle().id
    assert frame.iloc[0]["h"] == mappings[0]["h"] == Decimal("105")
    assert frame.iloc[0]["t"] == mappings[0]["t"] == int(BASE.timestamp() * 1000)
    assert all(isinstance(frame.iloc[0][name], Decimal) for name in ("o", "h", "l", "c", "v"))
    with pytest.raises(TypeError):
        mappings[0]["c"] = Decimal("1")
    with pytest.raises(ValueError, match="UTC"):
        adapter.to_candle_mappings(symbol="BTC", timeframe=CanonicalTimeframe.M1, as_of=BASE.replace(tzinfo=None))


def test_adapter_frame_is_accepted_by_frozen_trading_brain_market_entry_point():
    bars = tuple(candle(minute=index, high="120" if index == 2 else "110",
                        low="80" if index == 2 else "90") for index in range(5))
    adapter = TradingBrainMarketDataAdapter(dataset(bars))
    frame = adapter.to_mechanical_swing_frame(symbol="BTC", timeframe=CanonicalTimeframe.M1,
                                              as_of=BASE + timedelta(minutes=5))
    result = MechanicalSwingEngine().detect(timeframe="1m", candles=frame)
    assert result.timeframe == "1m"
    assert all(isinstance(swing.price, Decimal) for swing in result.swings)


def test_phase1_records_are_frozen_and_package_has_no_execution_security_dependencies():
    modules = tuple(path for path in PACKAGE.glob("*.py") if not path.name.startswith("test_"))
    forbidden = {"exchange", "execution", "risk", "database", "eth_account", "hyperliquid", "websocket"}
    forbidden_words = ("private_key", "signing", "place_order", "submit_order", "mainnet")
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {alias.name.split(".")[0] for alias in node.names} & forbidden
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden
        if path.suffix == ".py":
            lowered = path.read_text(encoding="utf-8").lower()
            assert not any(word in lowered for word in forbidden_words)
    for record in (HistoricalCandle, HistoricalDataset, Gap, DatasetManifest,
                   BacktestRunManifest, RuntimeFacts, MultiTimeframeView):
        assert is_dataclass(record) and record.__dataclass_params__.frozen


def test_architecture_explicitly_excludes_trade_simulation_and_live_runner():
    text = (PACKAGE / "ARCHITECTURE.md").read_text(encoding="utf-8").lower()
    assert "no orders, fills, positions" in text
    assert "24/7 paper/testnet" in text
    assert "nothing in" in text and "live/mainnet" in text
