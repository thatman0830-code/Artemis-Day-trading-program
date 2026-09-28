from pathlib import Path
import importlib.util


def load_capture_module():
    path = Path(__file__).parents[1] / "scripts" / "capture_databento_live_es_nq.py"
    spec = importlib.util.spec_from_file_location("capture_databento_live_es_nq", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zero_records_with_ack_mapping_and_heartbeat_is_classified_as_no_flow():
    module = load_capture_module()
    result = module.diagnose_capture(
        {"ES.c.0": 0, "NQ.c.0": 0},
        [{"requested_symbol": "ES.c.0"}, {"requested_symbol": "NQ.c.0"}],
        [{"code": "subscription_ack"}, {"code": "heartbeat"}],
    )
    assert result["status"] == "NO_CURRENT_FLOW_OR_MARKET_CLOSED"


def test_missing_ack_is_not_mislabeled_as_market_closed():
    module = load_capture_module()
    result = module.diagnose_capture({"ES.c.0": 0, "NQ.c.0": 0}, [], [])
    assert result["status"] == "SUBSCRIPTION_OR_ENTITLEMENT_FAILURE"


def test_any_record_is_valid_samples():
    module = load_capture_module()
    result = module.diagnose_capture(
        {"ES.c.0": 1, "NQ.c.0": 0},
        [{"requested_symbol": "ES.c.0"}],
        [{"code": "subscription_ack"}],
    )
    assert result["status"] == "VALID_SAMPLES"
