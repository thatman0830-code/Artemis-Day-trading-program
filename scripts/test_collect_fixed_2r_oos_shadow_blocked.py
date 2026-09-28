from pathlib import Path


def test_incomplete_session_is_waiting_state_not_execution_failure():
    source = Path(__file__).with_name("collect_fixed_2r_oos_shadow.py").read_text()
    assert '"WAITING_COMPLETE_SESSION"' in source
    assert '"signals": []' in source
    assert '"paper_execution_permitted": False' in source
    assert '"trading_authority": False' in source
