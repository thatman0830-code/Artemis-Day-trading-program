from datetime import datetime,timedelta,timezone
from research.forex_factory_trial_health_v1 import *
T=datetime(2026,9,9,tzinfo=timezone.utc);D=('2026-09-09','2026-09-10','2026-09-11','2026-09-14','2026-09-15')
def test_health_requires_fresh_hash_verified_complete_coverage():
 g=evaluate_trial_health(observed_at=T,source_observed_at=T-timedelta(minutes=1),source_hash_verified=True,trial_days=D,expected_decision_ids=('a','b'),covered_decision_ids=('a','b'));assert g.state=='HEALTHY'and g.coverage_percent==100 and g.trading_authority is False
def test_health_rejects_stale_hash_boundary_and_coverage():
 g=evaluate_trial_health(observed_at=T,source_observed_at=T-timedelta(hours=1),source_hash_verified=False,trial_days=D[:-1],expected_decision_ids=('a','b'),covered_decision_ids=('a',));assert g.state=='REJECTED'and set(g.reasons)=={'SOURCE_STALE','SOURCE_HASH_INVALID','TRIAL_BOUNDARY_INVALID','DECISION_COVERAGE_INCOMPLETE'}
