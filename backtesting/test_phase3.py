import ast
from dataclasses import FrozenInstanceError, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.market_data import CanonicalTimeframe, GapPolicy, normalize_historical_candle, validate_dataset
from backtesting.orchestrator import (
    BatchEvaluationResult, ContinuationEvaluationRequest, EvaluationContext,
    EvaluationOutcome, EvaluationTrace, MissingPrerequisite,
    OrchestrationCheckpoint, OrchestrationCommit, OrchestrationState,
    PrimitiveResultReference, RequestEvaluationState, ReversalEvaluationRequest,
    SetupStateFact, TradingBrainEvaluationOrchestrator,
)
from backtesting.replay import DeterministicReplay
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION
from strategy.trading_brain.p11_cisd_confirmation import (
    CISDDirection, DeliveryCandle, DeliveryLeg, ReversalConfirmationSequence,
)
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralClassification, StructuralRegime, StructuralStateSnapshot, StructuralSwing,
)
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p23_liquidity import (
    LiquidityReference, LiquiditySide, LiquidityState, LiquiditySweep,
)
from strategy.trading_brain.p27_setup_qualification import (
    ContinuationSetupState, ReversalSetupState,
)


UTC = timezone.utc
BASE = datetime(2026, 8, 20, tzinfo=UTC)
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
PACKAGE = Path(__file__).parent


def ms(value):
    delta = value - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def candle(*, minute, timeframe, open_, high, low, close):
    tf = CanonicalTimeframe(timeframe)
    opened = BASE + timedelta(minutes=minute)
    return normalize_historical_candle({
        "symbol": "BTC", "timeframe": timeframe, "open_time": opened,
        "close_time": opened + tf.duration, "open": Decimal(open_),
        "high": Decimal(high), "low": Decimal(low), "close": Decimal(close),
        "volume": Decimal("10"), "is_closed": True,
    }, dataset_id="data-v1", schema_version="candles-v1",
       source="archive", exchange="hyperliquid")


def build(items):
    ordered = tuple(sorted(items, key=lambda c: (c.open_time, c.symbol, c.timeframe.value, c.id)))
    data = validate_dataset(ordered, dataset_id="data-v1", schema_version="candles-v1",
                            source="archive", exchange="hyperliquid",
                            gap_policy=GapPolicy.RECORD,
                            validation_time=BASE + timedelta(days=1))
    manifest = DatasetManifest.from_dataset(data, symbol="BTC",
                                            created_at=BASE + timedelta(days=1),
                                            configuration_id="import-v1")
    run = BacktestRunManifest.create(
        dataset=manifest, trading_brain_contract_version=INTERFACE_CONTRACT_VERSION,
        strategy_configuration_version="strategy-v1", model_configuration_version="model-v1",
        replay_start_inclusive=manifest.interval_start_inclusive,
        replay_end_exclusive=manifest.interval_end_exclusive,
        starting_equity=Decimal("10000"), execution_cost_configuration_id="cost-v1",
        random_seed=0, runtime=RuntimeFacts("3.11", "CPython", "Windows", "repo-v1"),
    )
    return data, run


def structure(direction=StructuralRegime.BULLISH):
    high = StructuralSwing("high", "mh", "5m", MechanicalSwingType.H,
                           StructuralClassification.HH, Decimal("110"), ms(BASE), False, "regime")
    low = StructuralSwing("low", "ml", "5m", MechanicalSwingType.L,
                          StructuralClassification.HL, Decimal("90"), ms(BASE), True, "regime")
    return StructuralStateSnapshot(
        "state", "5m", direction, high, low,
        protected_high=high if direction == StructuralRegime.BEARISH else None,
        protected_low=low if direction == StructuralRegime.BULLISH else None,
        as_of_timestamp=ms(BASE),
    )


def active_range(direction=StructuralRegime.BULLISH):
    return StructuralRange(
        "range", "5m", Decimal("110"), Decimal("90"), "high", "low",
        Decimal("110"), Decimal("90"), direction, ms(BASE), ms(BASE),
        True, False, "accepted-bos",
    )


def references(level="122"):
    return (
        LiquidityReference("target-a", "5m", LiquiditySide.BSL, Decimal(level), ms(BASE), "PDH", True),
        LiquidityReference("target-b", "5m", LiquiditySide.BSL, Decimal(level), ms(BASE), "PDH", True),
    )


def continuation_data():
    return (
        candle(minute=0, timeframe="5m", open_="94", high="95", low="90", close="94"),
        candle(minute=5, timeframe="5m", open_="96", high="100", low="94", close="98"),
        candle(minute=10, timeframe="5m", open_="100", high="105", low="99", close="100"),
    )


def continuation_request(level="122"):
    return ContinuationEvaluationRequest(
        "request-cont", "setup-cont", StructuralRegime.BULLISH,
        structure(), active_range(), references(level),
    )


def reversal_data():
    return (
        candle(minute=0, timeframe="1m", open_="100", high="101", low="98", close="99"),
        candle(minute=1, timeframe="1m", open_="99", high="102", low="98", close="101"),
        candle(minute=2, timeframe="1m", open_="94", high="95", low="90", close="94"),
        candle(minute=3, timeframe="1m", open_="96", high="100", low="94", close="98"),
        candle(minute=4, timeframe="1m", open_="100", high="105", low="99", close="100"),
    )


def reversal_request():
    first = reversal_data()[0]
    delivery = DeliveryCandle(first.id, "1m", first.open, first.high, first.low, first.close, ms(first.close_time))
    sequence = ReversalConfirmationSequence(
        "setup-rev", CISDDirection.BULLISH, StructuralRegime.BEARISH,
        "sweep-rev", LiquiditySide.LSL, ms(BASE + timedelta(minutes=1)),
        "mss-rev", ms(BASE + timedelta(minutes=2)), True,
    )
    leg = DeliveryLeg("delivery-leg", "setup-rev", "1m", CISDDirection.BEARISH,
                      (delivery,), True)
    sweep = LiquiditySweep(
        "sweep-rev", "sweep-pool", "5m", "1m", LiquiditySide.LSL,
        Decimal("90"), ms(BASE + timedelta(minutes=1)), Decimal("88"),
        Decimal("91"), Decimal("2"), LiquidityState.SWEPT, LiquidityState.CONSUMED,
    )
    return ReversalEvaluationRequest(
        "request-rev", "setup-rev", StructuralRegime.BULLISH,
        structure(), active_range(), references(), sequence, (leg,), sweep,
    )


def execute(items, request=None):
    data, run = build(items)
    replay = DeterministicReplay(dataset=data, run=run)
    orchestrator = TradingBrainEvaluationOrchestrator(
        dataset=data, run=run, minimum_tick=Decimal("0.25"),
        calculation_version="phase3-v1",
    )
    state = orchestrator.initial_state()
    commits = []
    for publication in replay:
        commit = orchestrator.evaluate(publication=publication, state=state, request=request)
        state = commit.state; commits.append(commit)
    return data, run, replay, orchestrator, state, tuple(commits)


def test_initial_state_is_empty_and_single_bar_is_insufficient_but_no_setup():
    data, run = build((continuation_data()[0],))
    orchestrator = TradingBrainEvaluationOrchestrator(dataset=data, run=run,
                                                      minimum_tick=Decimal("0.25"), calculation_version="v1")
    assert orchestrator.initial_state().batch_results == ()
    *_, commits = execute((continuation_data()[0],))
    assert commits[0].result.outcome is EvaluationOutcome.NO_SETUP
    assert any(item.owner == "#20" for item in commits[0].result.trace.missing_prerequisites)


def test_waiting_then_deterministic_continuation_arms_through_actual_primitives():
    *_, state, commits = execute(continuation_data(), continuation_request())
    assert commits[0].result.outcome is EvaluationOutcome.CANDIDATE
    final = commits[-1].result.setup_fact
    assert final.outcome is EvaluationOutcome.ARMED_CONTINUATION
    assert final.canonical_state is ContinuationSetupState.ARMED
    owners = tuple(item.owner for item in commits[-1].result.trace.primitive_results)
    for owner in ("#19", "#21", "#22", "#23", "#24", "#25", "#26", "#27", "#28", "#13"):
        assert owner in owners
    assert state.batch_results[-1] == commits[-1].result


def test_continuation_exact_frozen_entry_stop_target_r_and_rejection_are_preserved():
    *_, armed = execute(continuation_data(), continuation_request())
    fact = armed[-1].result.setup_fact
    final = fact.final_qualification
    assert (fact.entry_zone.eq_normalized, fact.stop.stop_price, fact.target.level) == (
        Decimal("97.00"), Decimal("89.75"), Decimal("122.00"),
    )
    assert (final.entry, final.stop, final.target) == (
        fact.entry_zone.eq_normalized, fact.stop.stop_price, fact.target.level,
    )
    assert final.risk == Decimal("7.25") and final.reward == Decimal("25.00")
    *_, rejected = execute(continuation_data(), continuation_request("105"))
    assert rejected[-1].result.outcome is EvaluationOutcome.REJECTED
    assert rejected[-1].result.setup_fact.canonical_state is ContinuationSetupState.REJECTED


def test_reversal_cisd_mss_waits_then_entry_zone_arms_deterministically():
    *_, commits = execute(reversal_data(), reversal_request())
    assert any(item.result.outcome is EvaluationOutcome.MSS_CISD_CONFIRMED
               for item in commits[:-1])
    final = commits[-1].result.setup_fact
    assert final.outcome is EvaluationOutcome.ENTRY_ZONE_ARMED_REVERSAL
    assert final.canonical_state is ReversalSetupState.ENTRY_ZONE_ARMED
    assert any(item.owner == "#11" for commit in commits for item in commit.result.trace.primitive_results)
    assert final.stop.reference_id == "sweep-rev"


def test_same_timestamp_atomic_visibility_and_higher_timeframe_no_lookahead():
    items = (
        candle(minute=0, timeframe="5m", open_="100", high="105", low="95", close="101"),
        candle(minute=4, timeframe="1m", open_="100", high="102", low="99", close="101"),
    )
    *_, commits = execute(items)
    assert len(commits) == 1 and len(commits[0].result.source_candle_ids) == 2
    market = [ref for ref in commits[0].result.trace.primitive_results if ref.owner == "#19"]
    assert {ref.result.timeframe for ref in market} == {"1m", "5m"}


def test_earlier_batch_cannot_see_forming_higher_timeframe():
    items = (
        candle(minute=0, timeframe="5m", open_="100", high="105", low="95", close="101"),
        candle(minute=0, timeframe="1m", open_="100", high="102", low="99", close="101"),
    )
    *_, commits = execute(items)
    first_5m = next(ref for ref in commits[0].result.trace.primitive_results
                    if ref.owner == "#19" and ref.result.timeframe == "5m")
    assert first_5m.input_ids == ()


def test_gaps_are_not_forward_filled_into_strategy_inputs():
    items = (
        candle(minute=0, timeframe="1m", open_="100", high="102", low="99", close="101"),
        candle(minute=2, timeframe="1m", open_="101", high="103", low="100", close="102"),
    )
    data, *_, commits = execute(items)
    final_19 = next(ref for ref in commits[-1].result.trace.primitive_results if ref.owner == "#19")
    assert len(data.gaps) == 1 and len(final_19.input_ids) == 2


def test_duplicate_is_idempotent_but_conflicting_request_and_chronology_fail():
    data, run = build(continuation_data())
    replay = DeterministicReplay(dataset=data, run=run); publications = tuple(replay)
    engine = TradingBrainEvaluationOrchestrator(dataset=data, run=run,
                                                minimum_tick=Decimal("0.25"), calculation_version="v1")
    state = engine.initial_state()
    first = engine.evaluate(publication=publications[0], state=state, request=continuation_request())
    assert engine.evaluate(publication=publications[0], state=first.state,
                           request=continuation_request()) == first
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        engine.evaluate(publication=publications[0], state=first.state,
                        request=continuation_request("105"))
    second = engine.evaluate(publication=publications[1], state=first.state, request=continuation_request())
    with pytest.raises(ValueError, match="later timestamp"):
        engine.evaluate(publication=publications[0], state=second.state, request=continuation_request())


def test_identity_version_and_skipped_batch_mismatches_fail_closed():
    data, run = build(continuation_data()); publications = tuple(DeterministicReplay(dataset=data, run=run))
    engine = TradingBrainEvaluationOrchestrator(dataset=data, run=run,
                                                minimum_tick=Decimal("0.25"), calculation_version="v1")
    state = engine.initial_state()
    with pytest.raises(ValueError, match="identity/version"):
        engine.evaluate(publication=publications[0], state=replace(state, calculation_version="other"))
    with pytest.raises(ValueError, match="batch zero"):
        engine.evaluate(publication=publications[1], state=state)
    forged_batch = replace(publications[0].batch, event_time=publications[1].batch.event_time)
    with pytest.raises(ValueError, match="canonical Phase 2"):
        engine.evaluate(publication=replace(publications[0], batch=forged_batch), state=state)


def test_future_upstream_references_are_excluded_not_used_as_targets():
    future = ms(BASE + timedelta(hours=1))
    request = continuation_request()
    request = replace(request, liquidity_references=tuple(
        replace(reference, confirmation_time=future) for reference in request.liquidity_references
    ))
    *_, commits = execute(continuation_data(), request)
    assert commits[-1].result.outcome is EvaluationOutcome.CANDIDATE
    assert any(item.prerequisite.startswith("FUTURE_LIQUIDITY_REFERENCE")
               for item in commits[-1].result.trace.missing_prerequisites)
    assert commits[-1].result.setup_fact.target is None


def test_checkpoint_matches_replay_cursor_and_exact_state_resume():
    data, run = build(continuation_data()); replay = DeterministicReplay(dataset=data, run=run)
    engine = TradingBrainEvaluationOrchestrator(dataset=data, run=run,
                                                minimum_tick=Decimal("0.25"), calculation_version="v1")
    state = engine.initial_state(); replay.start(); publication = replay.advance()
    state = engine.evaluate(publication=publication, state=state, request=continuation_request()).state
    replay_checkpoint = replay.checkpoint()
    checkpoint = engine.checkpoint(state=state, replay_checkpoint=replay_checkpoint)
    engine.validate_resume(state=state, checkpoint=checkpoint, replay_checkpoint=replay_checkpoint)
    with pytest.raises(ValueError, match="incompatible"):
        engine.validate_resume(state=replace(state, id="other"), checkpoint=checkpoint,
                               replay_checkpoint=replay_checkpoint)
    with pytest.raises(ValueError, match="cursor"):
        engine.checkpoint(state=engine.initial_state(), replay_checkpoint=replay_checkpoint)


def test_repeated_complete_replay_is_equivalent():
    first = execute(continuation_data(), continuation_request())[-1]
    second = execute(continuation_data(), continuation_request())[-1]
    assert first == second


def test_invalidation_preserves_historical_range_ote_lrl_and_cisd_facts():
    data, run = build(reversal_data()); publications = tuple(DeterministicReplay(dataset=data, run=run))
    engine = TradingBrainEvaluationOrchestrator(dataset=data, run=run,
                                                minimum_tick=Decimal("0.25"), calculation_version="v1")
    state = engine.initial_state(); request = reversal_request()
    for publication in publications[:-1]:
        state = engine.evaluate(publication=publication, state=state, request=request).state
    transition = replace(request.structural_state, regime=StructuralRegime.TRANSITION)
    invalidated = replace(request, structural_state=transition, invalidation_event_id="invalidated")
    commit = engine.evaluate(publication=publications[-1], state=state, request=invalidated)
    request_state = commit.state.request_states[0]
    assert request_state.historical_facts
    assert all(getattr(fact, "historical", True) for fact in request_state.historical_facts)


def test_records_are_immutable_and_no_29_or_security_dependencies_exist():
    records = (EvaluationContext, PrimitiveResultReference, MissingPrerequisite,
               EvaluationTrace, RequestEvaluationState, SetupStateFact,
               BatchEvaluationResult, OrchestrationState, OrchestrationCommit,
               OrchestrationCheckpoint)
    assert all(is_dataclass(record) and record.__dataclass_params__.frozen for record in records)
    result = execute((continuation_data()[0],))[-1][0].result
    with pytest.raises(FrozenInstanceError):
        result.outcome = EvaluationOutcome.INVALID_FAIL_CLOSED
    path = PACKAGE / "orchestrator.py"; tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_roots = {"exchange", "execution", "risk", "database", "hyperliquid", "websocket", "eth_account"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {alias.name.split(".")[0] for alias in node.names} & forbidden_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden_roots
            assert ".p29_" not in node.module
    source = path.read_text(encoding="utf-8").lower()
    for token in ("private_key", "wallet", "signing", "mainnet", "network", "#29.1", "p29_"):
        if token == "#29.1":
            assert source.count(token) == 1  # boundary docstring only
        else:
            assert token not in source
