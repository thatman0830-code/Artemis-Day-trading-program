from pathlib import Path
def test_scanner_uses_retained_signals_verified_bars_and_no_execution():
 source=Path(__file__).with_name('record_ninjatrader_completed_signal_lifecycles.py').read_text().lower()
 for required in('read_ninjatrader_canonical_smoke_history','read_closed_bar_dataset','resolve_signal_lifecycle','append_completed_shadow_trade','compare_shadow_profiles'):assert required in source
 assert 'ninjatrader-signal-lifecycle-status.json' in source
 assert 'evidence_rejected' in source and 'evidence_rejection_count' in source
 assert '"paper_execution_permitted": false' in source
 assert '"trading_authority": false' in source
 for prohibited in('submitorder','createorder','place_order','private_key'):assert prohibited not in source
