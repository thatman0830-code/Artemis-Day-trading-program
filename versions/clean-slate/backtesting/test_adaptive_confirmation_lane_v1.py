from backtesting.adaptive_confirmation_lane_v1 import detect_candidate, evaluate

def test_partial_lane_requires_fvg_and_one_independent_confirmation():
    bars=[{"open":100,"high":101,"low":99,"close":100},
          {"open":100,"high":102,"low":100,"close":101.5},
          {"open":102,"high":104,"low":102,"close":103.5,"close_time":"t"}]
    candidate=detect_candidate("ESU6",bars)
    assert candidate is not None
    assert candidate.fvg is True and candidate.comparison_only is True
    assert candidate.paper_execution_permitted is False

def test_lane_stays_quiet_without_fvg():
    bars=[{"open":100,"high":101,"low":99,"close":100}]*3
    report=evaluate("NQU6",bars)
    assert report["candidate"] is None and report["trading_authority"] is False

def test_future_close_is_quarantined():
    bars=[{"open":100,"high":101,"low":99,"close":100},
          {"open":100,"high":102,"low":100,"close":101.5},
          {"open":102,"high":104,"low":102,"close":103.5,"close_time":"2099-09-15T22:08:00+00:00"}]
    report=evaluate("ESU6",bars)
    assert report["candidate"] is None
