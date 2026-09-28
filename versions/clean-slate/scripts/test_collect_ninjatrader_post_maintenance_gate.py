from pathlib import Path
def test_gate_requires_fresh_pair_single_process_and_no_authority():
 source=Path(__file__).with_name("collect_ninjatrader_post_maintenance_gate.ps1").read_text().lower()
 for required in("scheduled_non_trading_minute_count","unresolved_open_session_minute_count","expectedarchive","manifest.archive_file-ne$expectedarchive","launchers.count-ne 1","task.state-ne'running'","passed_with_quarantined_open_gaps","current_day_canonical_eligible=$false","trading_authority=$false"):assert required in source
 for prohibited in("place_order","submitorder","private_key"):assert prohibited not in source
