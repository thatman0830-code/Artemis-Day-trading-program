from strategy.aoi import AOICandidate, AOIStatus, AOIType
from strategy.liquidity import LiquiditySweep, LiquiditySweepStatus, LiquiditySweepType
from strategy.models import MarketStructure, MarketTrend, SetupStatus, TradeDirection
from strategy.multi_timeframe import ConsensusTrend, MultiTimeframeResult
from strategy.setup_engine import SetupEngine, SetupOutcome


def structure(trend=MarketTrend.BULLISH, price=102.0):
    return MarketStructure(
        symbol="BTC", timeframe="15m", trend=trend, current_price=price,
        swing_high=108.0, swing_low=96.0, higher_high=108.0,
        higher_low=100.0, lower_high=104.0, lower_low=96.0,
    )


def mtf(consensus=ConsensusTrend.BULLISH):
    return MultiTimeframeResult(
        symbol="BTC", structures=[], bullish_score=6.0,
        bearish_score=1.0, range_score=0.0, consensus=consensus,
    )


def aoi(status=AOIStatus.VALID):
    return AOICandidate(
        lower_bound=100.0, upper_bound=103.0, touches=3,
        timeframe="15m", aoi_type=AOIType.DEMAND, status=status,
        reason="test", midpoint=101.5, width=3.0,
        width_pct=2.9557, inside_structure_range=True,
    )


def sweep(kind=LiquiditySweepType.SELL_SIDE, confirmed=True):
    return LiquiditySweep(
        sweep_type=kind,
        status=(LiquiditySweepStatus.CONFIRMED if confirmed else LiquiditySweepStatus.NOT_CONFIRMED),
        reference_level=100.0, candle_high=103.0, candle_low=99.0,
        candle_close=102.0, penetration=1.0, penetration_pct=1.0,
        reason="test",
    )


def assert_outcome(signal, outcome):
    assert signal.metadata["outcome"] == outcome.value


def test_no_setup_for_mixed_consensus():
    signal = SetupEngine().evaluate(
        structure=structure(), multi_timeframe=mtf(ConsensusTrend.MIXED),
        aoi_candidate=aoi(), sweep=sweep(),
    )
    assert signal.status == SetupStatus.INVALID
    assert signal.direction == TradeDirection.NONE
    assert_outcome(signal, SetupOutcome.NO_SETUP)


def test_no_setup_without_aoi():
    signal = SetupEngine().evaluate(
        structure=structure(), multi_timeframe=mtf(),
        aoi_candidate=None, sweep=sweep(),
    )
    assert_outcome(signal, SetupOutcome.NO_SETUP)


def test_waiting_for_aoi_validation():
    signal = SetupEngine().evaluate(
        structure=structure(), multi_timeframe=mtf(),
        aoi_candidate=aoi(AOIStatus.WAITING), sweep=sweep(),
    )
    assert signal.status == SetupStatus.WAITING
    assert_outcome(signal, SetupOutcome.WAITING)


def test_waiting_when_price_is_outside_aoi():
    signal = SetupEngine().evaluate(
        structure=structure(price=105.0), multi_timeframe=mtf(),
        aoi_candidate=aoi(), sweep=sweep(),
    )
    assert_outcome(signal, SetupOutcome.WAITING)


def test_waiting_for_liquidity_trigger():
    signal = SetupEngine().evaluate(
        structure=structure(), multi_timeframe=mtf(),
        aoi_candidate=aoi(), sweep=sweep(confirmed=False),
    )
    assert_outcome(signal, SetupOutcome.WAITING)


def test_valid_long_candidate():
    signal = SetupEngine().evaluate(
        structure=structure(), multi_timeframe=mtf(),
        aoi_candidate=aoi(), sweep=sweep(),
    )
    assert signal.status == SetupStatus.VALID
    assert signal.direction == TradeDirection.LONG
    assert signal.entry_price == 102.0
    assert signal.stop_price == 99.0
    assert signal.target_price == 108.0
    assert signal.risk_reward == 2.0
    assert_outcome(signal, SetupOutcome.VALID_TRADE_CANDIDATE)


def test_valid_short_candidate():
    signal = SetupEngine().evaluate(
        structure=structure(MarketTrend.BEARISH, 102.0),
        multi_timeframe=mtf(ConsensusTrend.BEARISH),
        aoi_candidate=aoi(), sweep=sweep(LiquiditySweepType.BUY_SIDE),
    )
    assert signal.status == SetupStatus.VALID
    assert signal.direction == TradeDirection.SHORT
    assert signal.stop_price == 103.0
    assert signal.target_price == 96.0
    assert signal.risk_reward == 6.0
    assert_outcome(signal, SetupOutcome.VALID_TRADE_CANDIDATE)


def test_rejects_wrong_sweep_direction_and_low_rr():
    wrong = SetupEngine().evaluate(
        structure=structure(), multi_timeframe=mtf(),
        aoi_candidate=aoi(), sweep=sweep(LiquiditySweepType.BUY_SIDE),
    )
    assert_outcome(wrong, SetupOutcome.NO_SETUP)

    low_rr = SetupEngine(minimum_risk_reward=3.0).evaluate(
        structure=structure(), multi_timeframe=mtf(),
        aoi_candidate=aoi(), sweep=sweep(),
    )
    assert low_rr.risk_reward == 2.0
    assert_outcome(low_rr, SetupOutcome.NO_SETUP)


def test_symbol_mismatch_fails_fast():
    mismatched = mtf()
    mismatched = MultiTimeframeResult(
        symbol="ETH", structures=[], bullish_score=mismatched.bullish_score,
        bearish_score=mismatched.bearish_score, range_score=mismatched.range_score,
        consensus=mismatched.consensus,
    )
    try:
        SetupEngine().evaluate(
            structure=structure(), multi_timeframe=mismatched,
            aoi_candidate=aoi(), sweep=sweep(),
        )
    except ValueError:
        return
    raise AssertionError("Expected symbol mismatch to raise ValueError")


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"SETUP ENGINE TESTS PASSED ({len(tests)} cases)")
