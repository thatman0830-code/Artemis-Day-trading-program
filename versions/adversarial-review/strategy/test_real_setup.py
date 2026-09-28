from strategy.real_setup import RealSetupEvaluator


def test_rejects_too_few_candles_before_network_access():
    evaluator = RealSetupEvaluator(testnet=True)
    try:
        evaluator.evaluate(candle_limit=9)
    except ValueError as error:
        assert "at least 10" in str(error)
        return
    raise AssertionError("Expected candle_limit validation failure")


def test_rejects_unsupported_timeframe_before_network_access():
    evaluator = RealSetupEvaluator(testnet=True)
    try:
        evaluator.evaluate(timeframe="2m")
    except ValueError as error:
        assert "Unsupported timeframe" in str(error)
        return
    raise AssertionError("Expected timeframe validation failure")


if __name__ == "__main__":
    test_rejects_too_few_candles_before_network_access()
    test_rejects_unsupported_timeframe_before_network_access()
    print("REAL SETUP COORDINATOR TESTS PASSED (2 cases)")
