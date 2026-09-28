from datetime import datetime,timedelta,timezone
from research.forex_factory_shadow_trial_v1 import NewsEventV1
from research.news_decision_diagnostics_v1 import *
T=datetime(2026,9,10,12,30,tzinfo=timezone.utc);E=NewsEventV1('e','CPI','USD',T,'High','1','0','')
def test_all_profiles_are_associated_without_changing_baseline():
 d=DecisionFactV1('d','ES',T-timedelta(minutes=8),'NO_SETUP');x=associate(decision=d,events=(E,),source_snapshot_id='s');assert len(x.contexts)==3 and x.contexts[0]['new_entry_recommendation']=='SHADOW_BLOCK'and x.contexts[2]['new_entry_recommendation']=='SHADOW_ALLOW';assert x.baseline_preserved and x.order_influence_permitted is x.trading_authority is False
def test_scorecard_never_selects_or_changes_policy_automatically():
 x=associate(decision=DecisionFactV1('d','NQ',T,'LOSS'),events=(E,),source_snapshot_id='s');s=scorecard(diagnostics=(x,),trial_days=('2026-09-09','2026-09-10','2026-09-11','2026-09-14','2026-09-15'),as_of=datetime(2026,9,16,tzinfo=timezone.utc));assert s['state']=='COMPLETE_PENDING_REVIEW'and s['winner']is None and s['automatic_policy_change_permitted']is False
