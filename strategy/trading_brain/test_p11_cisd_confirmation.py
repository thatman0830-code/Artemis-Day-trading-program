from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p11_cisd_confirmation import (
    CISDDirection, CISDEngine, CISDNonConfirmationOutcome, CISDState,
    DeliveryCandle, DeliveryLeg, ReversalConfirmationSequence,
)
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p23_liquidity import LiquiditySide
from strategy.trading_brain.p25_fvg_ifvg import FVG, FVGDirection


def candle(id_, t, open_, high, low, close, *, timeframe="1m", closed=True):
    return DeliveryCandle(
        id=id_, timeframe=timeframe, open=Decimal(open_), high=Decimal(high),
        low=Decimal(low), close=Decimal(close), close_time=t, is_closed=closed,
    )


def sequence(direction=CISDDirection.BULLISH, *, sweep_time=5, mss_time=10):
    bullish = direction == CISDDirection.BULLISH
    return ReversalConfirmationSequence(
        setup_candidate_id="setup-a", intended_direction=direction,
        prior_regime=StructuralRegime.BEARISH if bullish else StructuralRegime.BULLISH,
        sweep_id="sweep-a", sweep_side=LiquiditySide.LSL if bullish else LiquiditySide.BSL,
        sweep_time=sweep_time, mss_id="mss-a", mss_confirmation_time=mss_time,
        mss_accepted=True,
    )


def leg(direction=CISDDirection.BEARISH, *, id_="leg", setup="setup-a",
        direct=True, end=9, initiating=None):
    if initiating is None:
        initiating = (
            candle("delivery", end - 1, "100", "101", "98", "99")
            if direction == CISDDirection.BEARISH
            else candle("delivery", end - 1, "100", "102", "99", "101")
        )
    continuation = (
        candle("delivery-2", end, "99", "100", "97", "98")
        if direction == CISDDirection.BEARISH
        else candle("delivery-2", end, "101", "103", "100", "102")
    )
    return DeliveryLeg(
        id=id_, setup_candidate_id=setup, timeframe="1m", direction=direction,
        candles=(initiating, continuation),
        directly_precedes_reversal_delivery=direct,
    )


def waiting(direction=CISDDirection.BULLISH):
    engine = CISDEngine()
    process = engine.start(sequence=sequence(direction))
    opposing = CISDDirection.BEARISH if direction == CISDDirection.BULLISH else CISDDirection.BULLISH
    process = engine.identify_reference(
        process=process, delivery_legs=(leg(opposing),), as_of_time=10,
    )
    return engine, engine.wait_for_body_close(process=process)


def test_canonical_state_machine_reaches_waiting_for_body_close():
    engine = CISDEngine()
    started = engine.start(sequence=sequence())
    assert started.state == CISDState.WAITING_FOR_1M_CONFIRMATION
    identified = engine.identify_reference(
        process=started, delivery_legs=(leg(),), as_of_time=10,
    )
    assert identified.state == CISDState.CISD_REFERENCE_IDENTIFIED
    assert identified.reference.delivery_candle_id == "delivery"
    assert identified.reference.reference_price == Decimal("100")
    assert engine.wait_for_body_close(process=identified).state == CISDState.WAITING_FOR_BODY_CLOSE


def test_bullish_strict_body_close_confirms():
    engine, process = waiting()
    result = engine.evaluate(
        process=process, candle=candle("confirm", 11, "99", "102", "98", "101"),
    )
    assert result.confirmed and result.process.state == CISDState.CISD_CONFIRMED
    assert result.process.confirmation.confirmation_close == Decimal("101")
    assert result.process.confirmation.reference_price == Decimal("100")


def test_bearish_strict_body_close_confirms_symmetrically():
    engine, process = waiting(CISDDirection.BEARISH)
    result = engine.evaluate(
        process=process, candle=candle("confirm", 11, "101", "102", "98", "99"),
    )
    assert result.confirmed
    assert result.process.confirmation.direction == CISDDirection.BEARISH


@pytest.mark.parametrize(
    "confirming",
    [
        candle("equal", 11, "99", "102", "98", "100"),
        candle("wick", 11, "99", "102", "98", "99.5"),
    ],
)
def test_bullish_equality_and_wick_only_are_rejected(confirming):
    engine, process = waiting()
    result = engine.evaluate(process=process, candle=confirming)
    assert not result.confirmed
    assert result.process.state == CISDState.WAITING_FOR_BODY_CLOSE


@pytest.mark.parametrize(
    "confirming",
    [
        candle("equal", 11, "101", "102", "98", "100"),
        candle("wick", 11, "101", "102", "98", "100.5"),
    ],
)
def test_bearish_equality_and_wick_only_are_rejected(confirming):
    engine, process = waiting(CISDDirection.BEARISH)
    result = engine.evaluate(process=process, candle=confirming)
    assert not result.confirmed


def test_candle_color_does_not_replace_reference_close_test():
    engine, process = waiting()
    # Bearish candle color, but it still closes strictly above the reference.
    result = engine.evaluate(
        process=process, candle=candle("confirm", 11, "102", "103", "100", "101"),
    )
    assert result.confirmed


def test_latest_directly_preceding_leg_initiating_candle_is_selected():
    engine = CISDEngine()
    started = engine.start(sequence=sequence())
    old = leg(id_="old", end=7, initiating=candle("old-first", 6, "90", "91", "88", "89"))
    latest = leg(id_="latest", end=9)
    result = engine.identify_reference(
        process=started, delivery_legs=(latest, old), as_of_time=10,
    )
    assert result.reference.delivery_leg_id == "latest"
    assert result.reference.reference_price == Decimal("100")


def test_missing_reference_is_not_confirmable_non_error_outcome():
    process = CISDEngine().start(sequence=sequence())
    result = CISDEngine().identify_reference(
        process=process, delivery_legs=(), as_of_time=10,
    )
    assert result.non_confirmation_outcome == CISDNonConfirmationOutcome.NOT_CONFIRMABLE
    assert result.state == CISDState.WAITING_FOR_1M_CONFIRMATION


def test_wrong_direction_is_invalid_reference_without_older_fallback():
    engine = CISDEngine()
    process = engine.start(sequence=sequence())
    old_valid = leg(id_="old", end=7)
    latest_wrong = leg(CISDDirection.BULLISH, id_="latest", end=9)
    result = engine.identify_reference(
        process=process, delivery_legs=(old_valid, latest_wrong), as_of_time=10,
    )
    assert result.non_confirmation_outcome == CISDNonConfirmationOutcome.INVALID_CISD_REFERENCE
    assert result.reference is None


def test_unrelated_or_nonpreceding_leg_cannot_substitute():
    engine = CISDEngine()
    process = engine.start(sequence=sequence())
    result = engine.identify_reference(
        process=process,
        delivery_legs=(leg(setup="other"), leg(id_="not-direct", direct=False)),
        as_of_time=10,
    )
    assert result.non_confirmation_outcome == CISDNonConfirmationOutcome.NOT_CONFIRMABLE


def test_same_candle_mss_and_cisd_is_permitted_from_frozen_reference():
    engine, process = waiting()
    result = engine.evaluate(
        process=process, candle=candle("same", 10, "99", "102", "98", "101"),
    )
    assert result.confirmed and result.process.confirmation.same_candle_as_mss


def test_pre_mss_and_pre_sweep_body_closes_cannot_confirm_or_be_reused():
    engine = CISDEngine()
    process = engine.start(sequence=sequence(sweep_time=8, mss_time=10))
    process = engine.identify_reference(
        process=process, delivery_legs=(leg(end=6),), as_of_time=7,
    )
    process = engine.wait_for_body_close(process=process)
    old = engine.evaluate(
        process=process, candle=candle("old-cisd", 7, "99", "102", "98", "101"),
    )
    assert old.body_close_observed and not old.chronology_eligible and not old.confirmed
    later = engine.evaluate(
        process=old.process, candle=candle("later", 10, "99", "100", "98", "99.5"),
    )
    assert not later.confirmed


def test_reference_must_exist_before_evaluating_candle_frozen_prestate():
    engine = CISDEngine()
    process = engine.start(sequence=sequence())
    same_time_reference = leg(
        end=10, initiating=candle("new-ref", 10, "100", "101", "98", "99"),
    )
    result = engine.identify_reference(
        process=process, delivery_legs=(same_time_reference,), as_of_time=10,
    )
    assert result.non_confirmation_outcome == CISDNonConfirmationOutcome.NOT_CONFIRMABLE


def test_confirmation_is_setup_specific_and_records_upstream_associations():
    engine, process = waiting()
    confirmation = engine.evaluate(
        process=process, candle=candle("confirm", 11, "99", "102", "98", "101"),
    ).process.confirmation
    assert confirmation.setup_candidate_id == "setup-a"
    assert confirmation.associated_mss_id == "mss-a"
    assert confirmation.associated_sweep_id == "sweep-a"


def test_confirmation_is_not_reconfirmed_on_later_candles():
    engine, process = waiting()
    confirmed = engine.evaluate(
        process=process, candle=candle("first", 11, "99", "102", "98", "101"),
    ).process
    again = engine.evaluate(
        process=confirmed, candle=candle("second", 12, "99", "103", "98", "102"),
    )
    assert again.process is confirmed
    assert again.process.confirmation.confirmation_candle_id == "first"


def test_upstream_invalidation_terminates_but_preserves_historical_confirmation():
    engine, process = waiting()
    confirmed = engine.evaluate(
        process=process, candle=candle("confirm", 11, "99", "102", "98", "101"),
    ).process
    original = confirmed.confirmation
    terminated = engine.terminate(
        process=confirmed, invalidation_time=15,
        invalidation_reason="UPSTREAM_SETUP_INVALIDATED",
    )
    assert terminated.state == CISDState.CONFIRMATION_TERMINATED
    assert terminated.confirmation.historical
    assert not terminated.confirmation.active_for_setup
    assert original.active_for_setup and not original.historical


def test_no_look_ahead_requires_closed_1m_candles_in_increasing_order():
    engine, process = waiting()
    with pytest.raises(ValueError, match="completed"):
        engine.evaluate(
            process=process,
            candle=candle("open", 11, "99", "102", "98", "101", closed=False),
        )
    first = engine.evaluate(
        process=process, candle=candle("first", 11, "99", "100", "98", "99"),
    ).process
    with pytest.raises(ValueError, match="increasing"):
        engine.evaluate(
            process=first, candle=candle("repeat", 11, "99", "100", "98", "99"),
        )
    with pytest.raises(ValueError, match="1M"):
        engine.evaluate(
            process=first,
            candle=candle("wrong-tf", 12, "99", "102", "98", "101", timeframe="5m"),
        )


def test_confirmation_and_reference_are_immutable():
    engine, process = waiting()
    confirmed = engine.evaluate(
        process=process, candle=candle("confirm", 11, "99", "102", "98", "101"),
    ).process
    with pytest.raises(FrozenInstanceError):
        confirmed.reference.reference_price = Decimal("99")
    with pytest.raises(FrozenInstanceError):
        confirmed.confirmation.confirmation_close = Decimal("102")


def test_zone_boundary_allows_only_post_confirmation_compatible_1m_facts():
    engine, process = waiting()
    confirmed = engine.evaluate(
        process=process, candle=candle("confirm", 11, "99", "102", "98", "101"),
    ).process

    def zone(id_, time, direction=FVGDirection.BULLISH, timeframe="1m"):
        return FVG(
            id=id_, timeframe=timeframe, direction=direction,
            candle1_id="a", candle2_id="b", candle3_id="c",
            lower_boundary=Decimal("100"), upper_boundary=Decimal("101"),
            gap_size=Decimal("1"), creation_time=time, confirmation_time=time,
            displacement_qualified=True,
        )

    assert engine.zone_is_temporally_eligible(
        process=confirmed, zone=zone("same", 11),
    )
    assert not engine.zone_is_temporally_eligible(
        process=confirmed, zone=zone("old", 10),
    )
    assert not engine.zone_is_temporally_eligible(
        process=confirmed, zone=zone("wrong", 12, FVGDirection.BEARISH),
    )
    assert not engine.zone_is_temporally_eligible(
        process=confirmed, zone=zone("5m", 12, timeframe="5m"),
    )


def test_amendment_005a_mapping_and_accepted_mss_are_mandatory():
    engine = CISDEngine()
    with pytest.raises(ValueError, match="005A"):
        engine.start(sequence=replace(sequence(), sweep_side=LiquiditySide.BSL))
    with pytest.raises(ValueError, match="accepted"):
        engine.start(sequence=replace(sequence(), mss_accepted=False))


def test_cisd_does_not_require_or_infer_displacement():
    engine, process = waiting()
    result = engine.evaluate(
        process=process, candle=candle("confirm", 11, "99", "102", "98", "101"),
    )
    assert result.confirmed
    assert "displacement" not in result.process.confirmation.__dataclass_fields__


def test_schema_contains_no_entry_setup_arming_risk_order_or_execution_fields():
    engine, process = waiting()
    confirmation = engine.evaluate(
        process=process, candle=candle("confirm", 11, "99", "102", "98", "101"),
    ).process.confirmation
    forbidden = {
        "entry", "entry_zone", "armed", "risk", "quantity", "size",
        "order", "fill", "position", "execution",
    }
    assert forbidden.isdisjoint(confirmation.__dataclass_fields__)
