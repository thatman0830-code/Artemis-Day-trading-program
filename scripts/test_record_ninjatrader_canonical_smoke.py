from pathlib import Path

def test_recorder_is_advisory_and_writes_both_isolated_histories():
    source=Path(__file__).with_name("record_ninjatrader_canonical_smoke.py").read_text("utf-8")
    assert "for market in FuturesCanonicalMarket" in source
    assert "assert_distinct_ninjatrader_smokes" in source
    assert "append_ninjatrader_canonical_smoke" in source
    assert '"trading_authority":False' in source
    for prohibited in ("SubmitOrder","CreateOrder","place_order","private_key"):
        assert prohibited not in source
