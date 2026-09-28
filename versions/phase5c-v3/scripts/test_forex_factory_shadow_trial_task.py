from pathlib import Path
def test_trial_task_is_bounded_low_frequency_limited_and_non_authoritative():
 root=Path(__file__).parent;runner=(root/'run_forex_factory_shadow_trial.ps1').read_text().lower();install=(root/'install_forex_factory_shadow_trial_task.ps1').read_text().lower()
 assert 'record_forex_factory_shadow_trial.py' in runner and "state='source_unavailable'" in runner
 assert 'evaluate_forex_factory_trial_health.py' in runner and "state-ne'healthy'" in runner
 assert '$healthresult=@(' in runner
 assert 'new-timespan -minutes 30' in install and 'new-timespan -days 7' in install
 assert '-multipleinstances ignorenew' in install and '-runlevel limited' in install
 for source in(runner,install):
  for prohibited in('submitorder','createorder','place_order','private_key'):assert prohibited not in source
