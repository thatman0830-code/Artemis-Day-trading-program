import ast
from dataclasses import FrozenInstanceError, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest

from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.market_data import (
    CanonicalTimeframe, GapPolicy, normalize_historical_candle, validate_dataset,
)
from backtesting.replay import (
    AvailabilitySnapshot, ClockSnapshot, DeterministicReplay, ReplayBatch,
    ReplayCheckpoint, ReplayEvent, ReplayPublication, ReplayState, VisibleStream,
)
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION


UTC = timezone.utc
BASE = datetime(2026, 8, 20, tzinfo=UTC)
RUNTIME = RuntimeFacts("3.11.9", "CPython", "Windows", "repo-v1")
PACKAGE = Path(__file__).parent


def candle(*, minute=0, timeframe="1m", close="101"):
    tf = CanonicalTimeframe(timeframe)
    opened = BASE + timedelta(minutes=minute)
    return normalize_historical_candle({
        "symbol": "BTC", "timeframe": timeframe, "open_time": opened,
        "close_time": opened + tf.duration, "open": Decimal("100"),
        "high": Decimal("110"), "low": Decimal("90"), "close": Decimal(close),
        "volume": Decimal("10"), "is_closed": True,
    }, dataset_id="data-v1", schema_version="candles-v1",
       source="archive", exchange="hyperliquid")


def dataset(items, *, policy=GapPolicy.RECORD):
    return validate_dataset(tuple(items), dataset_id="data-v1", schema_version="candles-v1",
                            source="archive", exchange="hyperliquid", gap_policy=policy,
                            validation_time=BASE + timedelta(days=1))


def run(data, *, start=BASE, end=None, contract=INTERFACE_CONTRACT_VERSION):
    manifest = DatasetManifest.from_dataset(data, symbol="BTC",
                                            created_at=BASE + timedelta(days=1),
                                            configuration_id="import-v1")
    return BacktestRunManifest.create(
        dataset=manifest, trading_brain_contract_version=contract,
        strategy_configuration_version="strategy-v1", model_configuration_version="model-v1",
        replay_start_inclusive=start, replay_end_exclusive=end or manifest.interval_end_exclusive,
        starting_equity=Decimal("10000"), execution_cost_configuration_id="cost-v1",
        random_seed=0, runtime=RUNTIME,
    )


def replay(items, **run_changes):
    data = dataset(items)
    return DeterministicReplay(dataset=data, run=run(data, **run_changes))


def test_empty_in_range_replay_starts_completed_without_publication():
    engine = replay((candle(), candle(minute=1)), end=BASE + timedelta(seconds=30))
    state = engine.start()
    assert state.state is ReplayState.COMPLETED and state.total_batch_count == 0
    assert list(engine) == []
    with pytest.raises(RuntimeError, match="completed"):
        engine.advance()


def test_single_candle_progression_and_post_completion_behavior():
    engine = replay((candle(), candle(minute=1)), end=BASE + timedelta(minutes=1, seconds=1))
    assert engine.clock.state is ReplayState.READY
    engine.start()
    publication = engine.advance()
    assert publication.batch.event_time == BASE + timedelta(minutes=1)
    assert publication.clock.state is ReplayState.COMPLETED
    with pytest.raises(RuntimeError, match="completed"):
        engine.advance()
    with pytest.raises(RuntimeError, match="already started"):
        engine.start()


def test_strict_chronology_canonical_order_and_deterministic_identities():
    items = (candle(), candle(minute=1), candle(minute=2))
    first = replay(items); second = replay(items)
    left, right = tuple(first), tuple(second)
    assert left == right
    assert [item.batch.event_time for item in left] == [BASE + timedelta(minutes=n) for n in (1, 2, 3)]
    assert [item.batch.sequence for item in left] == [0, 1, 2]
    assert first.event_sequence_id == second.event_sequence_id


def test_simultaneous_multi_timeframe_batch_is_atomic_and_higher_timeframe_closes_once():
    items = (candle(timeframe="5m"), candle(minute=4), candle(minute=5))
    engine = replay(items, end=BASE + timedelta(minutes=6))
    engine.start()
    with pytest.raises(ValueError, match="future"):
        engine.history(symbol="BTC", timeframe=CanonicalTimeframe.M5,
                       as_of=BASE + timedelta(minutes=5))
    publication = engine.advance()
    assert publication.batch.event_time == BASE + timedelta(minutes=5)
    assert tuple(event.timeframe for event in publication.batch.events) == (
        CanonicalTimeframe.M1, CanonicalTimeframe.M5,
    )
    streams = {stream.timeframe: stream for stream in publication.availability.streams}
    assert len(streams[CanonicalTimeframe.M1].candles) == 1
    assert len(streams[CanonicalTimeframe.M5].candles) == 1
    assert engine.latest(symbol="BTC", timeframe=CanonicalTimeframe.M5,
                         as_of=BASE + timedelta(minutes=5)).id == items[0].id


def test_half_open_replay_boundaries_use_close_timestamp():
    items = (candle(), candle(minute=1), candle(minute=2))
    engine = replay(items, start=BASE + timedelta(minutes=1),
                    end=BASE + timedelta(minutes=3))
    publications = tuple(engine)
    assert tuple(item.batch.event_time for item in publications) == (
        BASE + timedelta(minutes=1), BASE + timedelta(minutes=2),
    )
    assert all(item.batch.event_time < BASE + timedelta(minutes=3) for item in publications)


def test_gaps_are_preserved_and_never_forward_filled():
    engine = replay((candle(), candle(minute=2)))
    publications = tuple(engine)
    assert [p.batch.event_time for p in publications] == [BASE + timedelta(minutes=1), BASE + timedelta(minutes=3)]
    assert len(engine.history(symbol="BTC", timeframe=CanonicalTimeframe.M1,
                              as_of=BASE + timedelta(minutes=3))) == 2
    assert engine._dataset.gaps[0].missing_count == 1


def test_latest_history_and_bounded_lookback_are_read_only_and_idempotent():
    engine = replay((candle(), candle(minute=1), candle(minute=2)))
    publications = tuple(engine)
    timestamp = publications[-1].batch.event_time
    history = engine.history(symbol="BTC", timeframe=CanonicalTimeframe.M1, as_of=timestamp)
    assert history == engine.history(symbol="BTC", timeframe=CanonicalTimeframe.M1, as_of=timestamp)
    assert engine.latest(symbol="BTC", timeframe=CanonicalTimeframe.M1, as_of=timestamp) == history[-1]
    assert engine.lookback(symbol="BTC", timeframe=CanonicalTimeframe.M1, as_of=timestamp, count=2) == history[-2:]
    assert engine.lookback(symbol="BTC", timeframe=CanonicalTimeframe.M1, as_of=timestamp, count=0) == ()
    with pytest.raises(FrozenInstanceError):
        history[0].close = Decimal("1")


@pytest.mark.parametrize("operation", ["negative", "unknown", "naive", "future", "outside"])
def test_invalid_visibility_queries_fail_closed(operation):
    engine = replay((candle(), candle(minute=1)))
    engine.start(); publication = engine.advance(); timestamp = publication.batch.event_time
    kwargs = {"symbol": "BTC", "timeframe": CanonicalTimeframe.M1, "as_of": timestamp}
    with pytest.raises(ValueError):
        if operation == "negative":
            engine.lookback(**kwargs, count=-1)
        elif operation == "unknown":
            engine.history(**{**kwargs, "timeframe": CanonicalTimeframe.H1})
        elif operation == "naive":
            engine.history(**{**kwargs, "as_of": timestamp.replace(tzinfo=None)})
        elif operation == "future":
            engine.history(**{**kwargs, "as_of": timestamp + timedelta(seconds=1)})
        else:
            engine.history(**{**kwargs, "as_of": BASE - timedelta(seconds=1)})


def test_incompatible_dataset_run_and_contract_are_rejected():
    data = dataset((candle(), candle(minute=1)))
    other_data = dataset((candle(close="102"), candle(minute=1)))
    other_run = run(other_data)
    with pytest.raises(ValueError, match="fingerprint"):
        DeterministicReplay(dataset=data, run=other_run)
    # A deterministically valid manifest for another contract still fails the replay boundary.
    incompatible = run(data, contract="future-contract")
    with pytest.raises(ValueError, match="contract"):
        DeterministicReplay(dataset=data, run=incompatible)


def test_checkpoint_round_trip_resume_does_not_duplicate_or_skip():
    items = (candle(), candle(minute=1), candle(minute=2), candle(minute=3))
    baseline = replay(items); expected = tuple(baseline)
    interrupted = replay(items); interrupted.start(); first = interrupted.advance()
    serialized = json.loads(json.dumps(interrupted.checkpoint().to_dict(), sort_keys=True))
    checkpoint = ReplayCheckpoint.from_dict(serialized)
    resumed = DeterministicReplay.resume(dataset=interrupted._dataset, run=interrupted._run,
                                         checkpoint=checkpoint)
    remaining = tuple(resumed)
    assert (first,) + remaining == expected
    assert resumed.checkpoint().state is ReplayState.COMPLETED


@pytest.mark.parametrize("field,value", [
    ("dataset_id", "other"), ("dataset_fingerprint", "other"),
    ("run_id", "other"), ("trading_brain_contract_version", "other"),
    ("event_sequence_id", "other"), ("last_published_batch_id", "other"),
])
def test_checkpoint_identity_and_sequence_mismatches_fail(field, value):
    engine = replay((candle(), candle(minute=1), candle(minute=2)))
    engine.start(); engine.advance()
    bad = replace(engine.checkpoint(), **{field: value})
    with pytest.raises(ValueError, match="mismatch|conflicts"):
        DeterministicReplay.resume(dataset=engine._dataset, run=engine._run, checkpoint=bad)


def test_checkpoint_cursor_and_clock_conflicts_fail():
    engine = replay((candle(), candle(minute=1), candle(minute=2)))
    checkpoint = engine.checkpoint()
    with pytest.raises(ValueError, match="clock"):
        DeterministicReplay.resume(dataset=engine._dataset, run=engine._run,
                                   checkpoint=replace(checkpoint, current_time=BASE + timedelta(seconds=1)))
    with pytest.raises(ValueError, match="cursor"):
        DeterministicReplay.resume(dataset=engine._dataset, run=engine._run,
                                   checkpoint=replace(checkpoint, next_batch_sequence=99))


def test_all_phase2_records_are_immutable_and_logically_serializable():
    engine = replay((candle(), candle(minute=1)))
    publication = tuple(engine)[0]
    records = (ReplayEvent, ReplayBatch, VisibleStream, AvailabilitySnapshot,
               ClockSnapshot, ReplayPublication, ReplayCheckpoint)
    assert all(is_dataclass(record) and record.__dataclass_params__.frozen for record in records)
    with pytest.raises(FrozenInstanceError):
        publication.batch.sequence = 99
    assert ReplayCheckpoint.from_dict(engine.checkpoint().to_dict()) == engine.checkpoint()


def test_phase2_has_no_forbidden_dependencies_or_trading_brain_calls():
    path = PACKAGE / "replay.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {"exchange", "execution", "risk", "database", "hyperliquid", "websocket", "eth_account"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {alias.name.split(".")[0] for alias in node.names} & forbidden
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden
    source = path.read_text(encoding="utf-8").lower()
    for token in ("private_key", "signing", "mainnet", "submit_order", "place_order", "sleep(", "random."):
        assert token not in source
    assert "public_engine_entry_points" not in source
