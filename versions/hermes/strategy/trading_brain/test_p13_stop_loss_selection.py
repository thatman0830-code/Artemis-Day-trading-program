from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p11_cisd_confirmation import CISDDirection
from strategy.trading_brain.p13_stop_loss_selection import (
    StopLossSelectionEngine, StopSelectionErrorCode,
)
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p23_liquidity import (
    LiquiditySide, LiquidityState, LiquiditySweep,
)
from strategy.trading_brain.p28_entry_zone_selection import (
    EntryZoneSelectionEngine, EntryZoneSelectionState,
)
from strategy.trading_brain.test_p27_setup_qualification import (
    confirmed_cisd, continuation, protected, reversal,
)
from strategy.trading_brain.test_p28_entry_zone_selection import (
    continuation_setup, zone,
)


def continuation_inputs(direction=StructuralRegime.BULLISH, *, tick="0.25"):
    candidate = zone(
        "entry", "100", "101", direction=direction,
    )
    if direction == StructuralRegime.BULLISH:
        setup = continuation_setup(candidate)
    else:
        setup = replace(
            continuation(direction=direction).setup,
            eligible_zone_ids=(candidate.id,),
        )
    entry_zone = EntryZoneSelectionEngine(minimum_tick=Decimal(tick)).select(
        setup=setup, candidates=(candidate,), selection_time=3,
    )
    return setup, entry_zone, protected(direction)


def sweep(direction=StructuralRegime.BULLISH, *, id_="sweep", extreme=None,
          side=None, outcome=LiquidityState.SWEPT):
    bullish = direction == StructuralRegime.BULLISH
    side = side or (LiquiditySide.LSL if bullish else LiquiditySide.BSL)
    level = Decimal("90" if bullish else "110")
    if extreme is None:
        extreme = Decimal("89" if bullish else "111")
    return LiquiditySweep(
        id=id_, pool_id="pool", pool_timeframe="15m", event_timeframe="1m",
        side=side, level=level, event_time=5,
        candle_extreme=Decimal(str(extreme)), candle_close=Decimal("91" if bullish else "109"),
        penetration=Decimal("1"), outcome=outcome,
        final_state=LiquidityState.CONSUMED,
    )


def reversal_inputs(direction=StructuralRegime.BULLISH):
    process = confirmed_cisd(
        direction=(CISDDirection.BULLISH
                   if direction == StructuralRegime.BULLISH
                   else CISDDirection.BEARISH)
    )
    setup = reversal(direction=direction, cisd_process=process).setup
    candidate = zone(
        "reversal-entry", "100", "101", direction=direction,
        time=11, timeframe="1m",
    )
    entry_zone = EntryZoneSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, candidates=(candidate,), selection_time=12,
        cisd_process=process,
    )
    return setup, entry_zone, sweep(direction)


def test_continuation_long_stop_is_one_tick_below_protected_low():
    setup, entry_zone, reference = continuation_inputs()
    result = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone, protected_swing=reference,
        selection_time=4,
    )
    assert result.valid
    assert result.stop.reference_price == Decimal("90")
    assert result.stop.stop_price == Decimal("89.75")
    assert result.stop.stop_price < result.stop.frozen_entry_price


def test_continuation_short_stop_is_one_tick_above_protected_high():
    setup, entry_zone, reference = continuation_inputs(StructuralRegime.BEARISH)
    result = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone, protected_swing=reference,
        selection_time=4,
    )
    assert result.valid
    assert result.stop.reference_price == Decimal("110")
    assert result.stop.stop_price == Decimal("110.25")
    assert result.stop.stop_price > result.stop.frozen_entry_price


def test_reversal_long_uses_lsl_sweep_low_minus_one_tick():
    setup, entry_zone, event = reversal_inputs()
    result = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone, qualifying_sweep=event,
        selection_time=13,
    )
    assert result.valid
    assert result.stop.reference_type == "QUALIFYING_SWEEP_EXTREME"
    assert result.stop.reference_price == Decimal("89")
    assert result.stop.stop_price == Decimal("88.75")


def test_reversal_short_uses_bsl_sweep_high_plus_one_tick():
    setup, entry_zone, event = reversal_inputs(StructuralRegime.BEARISH)
    result = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone, qualifying_sweep=event,
        selection_time=13,
    )
    assert result.valid
    assert result.stop.reference_price == Decimal("111")
    assert result.stop.stop_price == Decimal("111.25")


@pytest.mark.parametrize("model", ["continuation", "reversal"])
def test_missing_required_reference_emits_stop_selection_invalid(model):
    if model == "continuation":
        setup, entry_zone, _ = continuation_inputs()
    else:
        setup, entry_zone, _ = reversal_inputs()
    result = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone, selection_time=13,
    )
    assert not result.valid and result.stop is None
    assert result.error.code == StopSelectionErrorCode.STOP_SELECTION_INVALID


def test_continuation_requires_exact_setup_protected_swing_identity_and_side():
    setup, entry_zone, reference = continuation_inputs()
    engine = StopLossSelectionEngine(minimum_tick=Decimal("0.25"))
    wrong_id = engine.select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=replace(reference, id="other"), selection_time=4,
    )
    not_protected = engine.select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=replace(reference, protected=False), selection_time=4,
    )
    assert wrong_id.error.code == StopSelectionErrorCode.STOP_SELECTION_INVALID
    assert not_protected.error.code == StopSelectionErrorCode.STOP_SELECTION_INVALID


def test_reversal_requires_amendment_005a_side_swept_outcome_and_association():
    setup, entry_zone, _ = reversal_inputs()
    engine = StopLossSelectionEngine(minimum_tick=Decimal("0.25"))
    wrong_side = engine.select(
        setup=setup, entry_zone=entry_zone,
        qualifying_sweep=sweep(side=LiquiditySide.BSL, extreme="111"),
        selection_time=13,
    )
    wrong_id = engine.select(
        setup=setup, entry_zone=entry_zone,
        qualifying_sweep=sweep(id_="other"), selection_time=13,
    )
    broken = engine.select(
        setup=setup, entry_zone=entry_zone,
        qualifying_sweep=sweep(outcome=LiquidityState.BROKEN), selection_time=13,
    )
    assert all(
        item.error.code == StopSelectionErrorCode.STOP_SELECTION_INVALID
        for item in (wrong_side, wrong_id, broken)
    )


def test_wrong_side_stop_geometry_against_frozen_entry_is_invalid():
    setup, entry_zone, reference = continuation_inputs()
    result = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=replace(reference, price=Decimal("101")),
        selection_time=4,
    )
    assert result.error.reason == "STOP_GEOMETRY_INVALID_AGAINST_FROZEN_ENTRY"


def test_reference_and_frozen_entry_must_be_on_configured_tick_grid():
    setup, entry_zone, reference = continuation_inputs()
    engine = StopLossSelectionEngine(minimum_tick=Decimal("0.25"))
    bad_reference = engine.select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=replace(reference, price=Decimal("90.10")),
        selection_time=4,
    )
    bad_entry = engine.select(
        setup=setup,
        entry_zone=replace(entry_zone, eq_normalized=Decimal("100.10")),
        protected_swing=reference, selection_time=4,
    )
    assert bad_reference.error.reason == "STOP_REFERENCE_OFF_TICK_GRID"
    assert bad_entry.error.reason == "FROZEN_ENTRY_OFF_TICK_GRID"


def test_invalid_or_mismatched_frozen_selection_emits_error():
    setup, entry_zone, reference = continuation_inputs()
    engine = StopLossSelectionEngine(minimum_tick=Decimal("0.25"))
    no_selection = engine.select(
        setup=setup,
        entry_zone=replace(
            entry_zone, state=EntryZoneSelectionState.NO_ELIGIBLE_ZONE,
            selected_zone_id=None, eq_normalized=None,
        ),
        protected_swing=reference, selection_time=4,
    )
    mismatch = engine.select(
        setup=setup,
        entry_zone=replace(entry_zone, setup_id="other"),
        protected_swing=reference, selection_time=4,
    )
    assert no_selection.error.code == StopSelectionErrorCode.STOP_SELECTION_INVALID
    assert mismatch.error.code == StopSelectionErrorCode.STOP_SELECTION_INVALID


def test_stop_selection_cannot_precede_frozen_entry():
    setup, entry_zone, reference = continuation_inputs()
    result = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=reference, selection_time=2,
    )
    assert result.error.reason == "STOP_SELECTION_PRECEDES_FROZEN_ENTRY"


def test_stop_and_error_records_are_deterministic_and_immutable():
    setup, entry_zone, reference = continuation_inputs()
    engine = StopLossSelectionEngine(minimum_tick=Decimal("0.25"))
    first = engine.select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=reference, selection_time=4,
    )
    second = engine.select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=reference, selection_time=4,
    )
    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.stop.stop_price = Decimal("90")
    error = engine.select(
        setup=setup, entry_zone=entry_zone, selection_time=4,
    ).error
    with pytest.raises(FrozenInstanceError):
        error.reason = "changed"


def test_stop_price_is_distinct_from_eventual_exit_price_schema():
    setup, entry_zone, reference = continuation_inputs()
    stop = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=reference, selection_time=4,
    ).stop
    assert "stop_price" in stop.__dataclass_fields__
    assert "exit_price" not in stop.__dataclass_fields__


def test_minimum_tick_must_be_positive_exact_decimal():
    with pytest.raises(ValueError, match="positive"):
        StopLossSelectionEngine(minimum_tick=Decimal("0"))
    setup, entry_zone, reference = continuation_inputs(tick="0.00000001")
    result = StopLossSelectionEngine(minimum_tick=Decimal("0.00000001")).select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=reference, selection_time=4,
    )
    assert result.stop.stop_price == Decimal("89.99999999")


def test_schema_has_no_r_multiple_arming_risk_sizing_order_fill_or_execution():
    setup, entry_zone, reference = continuation_inputs()
    stop = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=reference, selection_time=4,
    ).stop
    forbidden = {
        "r_multiple", "armed", "rejected", "risk_amount", "quantity",
        "protective_order", "order", "fill", "execution",
    }
    assert forbidden.isdisjoint(stop.__dataclass_fields__)
