from pathlib import Path

def test_periodic_task_is_limited_single_instance_and_non_authoritative():
    root=Path(__file__).parent
    runner=(root/"run_ninjatrader_canonical_smoke_task.ps1").read_text("utf-8").lower()
    install=(root/"install_ninjatrader_canonical_smoke_task.ps1").read_text("utf-8").lower()
    audit=(root/"audit_ninjatrader_canonical_smoke_task.ps1").read_text("utf-8").lower()
    assert "record_ninjatrader_canonical_smoke.py" in runner
    assert "evaluate_ninjatrader_clean_day_gate.py" in runner
    assert "clean_day_gate=$cleangate" in runner
    assert "evaluate_ninjatrader_smoke_gate.py" in runner
    assert "record_ninjatrader_completed_signal_lifecycles.py" in runner
    assert "lifecycle=$lifecyclepayload" in runner
    assert "evidence_rejection_count-ne 0" in runner
    assert "trading_authority=$false" in runner
    assert "-multipleinstances ignorenew" in install
    assert "-runlevel limited" in install
    assert "new-timespan -minutes 5" in install
    assert "new-timespan -minutes 2" in install
    assert "interval='pt5m'" in audit and "limit=([string]$task.settings.executiontimelimit-eq'pt2m')" in audit
    assert "last_result=[int64]$info.lasttaskresult" in audit
    for source in (runner,install,audit):
        for prohibited in ("submitorder","createorder","place_order","private_key"):
            assert prohibited not in source
