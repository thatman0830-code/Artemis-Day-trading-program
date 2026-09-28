from pathlib import Path
def test_export_replay_has_no_execution_surface():
 source=Path(__file__).with_name("replay_ninjatrader_gap_recovery_exports.py").read_text().lower()
 assert "evaluate_ninjatrader_export" in source and '"cross_source_equivalence_claimed":false' in source
 assert '"paper_execution_permitted":false' in source and '"trading_authority":false' in source
 for prohibited in("place_order","submitorder","private_key"):assert prohibited not in source
