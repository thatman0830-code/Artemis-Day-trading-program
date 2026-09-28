from pathlib import Path


def test_protocol_is_fixed_future_only_and_non_executable():
    source = Path(__file__).with_name("publish_fixed_2r_oos_protocol.py").read_text()
    for value in ('"r_multiple": "2.0"', '"maximum_holding_bars": 30',
                  '"2026-09-14"', '"2026-09-18"', '"approved": False',
                  '"paper_execution_permitted": False', '"trading_authority": False'):
        assert value in source
    for forbidden in ("SubmitOrder", "CreateOrder", "append_completed_shadow_trade"):
        assert forbidden not in source
