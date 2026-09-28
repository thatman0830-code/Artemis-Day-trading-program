from pathlib import Path
def test_recovery_is_logon_limited_and_non_authoritative():
 root=Path(__file__).parent;run=(root/'run_trading_reboot_recovery.ps1').read_text().lower();install=(root/'install_trading_reboot_recovery_task.ps1').read_text().lower()
 assert 'ninjatrader.exe' in run and 'mes.bar.json' in run and 'mnq.bar.json' in run
 assert '$env:onedrive' in run and "'onedrive\\documents'" in run and '$barroot' in run
 for name in ('btc public candle research recorder','ninjatrader mes-nq closed bar recorder','forex factory five-day shadow trial','trading brain obsidian continuity backup','ninjatrader es-nq canonical smoke evidence'):assert name in run
 assert 'user_action_required' in run and 'msg.exe' in run and 'paper_execution_permitted=$false' in run and 'trading_authority=$false' in run
 assert "if($state-eq'user_action_required'){try{" in run
 assert '-atlogon' in install and '-runlevel limited' in install and '-startwhenavailable' in install and '-multipleinstances ignorenew' in install
 for source in(run,install):
  for prohibited in('submitorder','createorder','place_order','private_key'):assert prohibited not in source
