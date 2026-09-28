from datetime import date,datetime,timezone
import json,pytest
from research.forex_factory_shadow_trial_v1 import *
NOW=datetime(2026,9,8,22,tzinfo=timezone.utc)
def raw():return json.dumps([{"title":"CPI","country":"USD","date":"2026-09-10T08:30:00-04:00","impact":"High","forecast":"0.3%","previous":"0.2%"}]).encode()
def test_trial_is_five_weekdays_and_non_authoritative():
 value=parse_snapshot(raw(),observed_at=NOW,start_day=date(2026,9,9));assert value.trial_days==("2026-09-09","2026-09-10","2026-09-11","2026-09-14","2026-09-15");assert value.high_impact_usd_count==1;assert value.directional_signal_permitted is value.order_influence_permitted is value.trading_authority is False
def test_malformed_or_unknown_impact_fails_closed():
 with pytest.raises(ValueError):parse_snapshot(b'{}',observed_at=NOW,start_day=date(2026,9,9))
 value=json.loads(raw());value[0]["impact"]="Certain Moon" 
 with pytest.raises(ValueError):parse_snapshot(json.dumps(value).encode(),observed_at=NOW,start_day=date(2026,9,9))
def test_source_contains_no_execution_surface():
 source=__import__('pathlib').Path(__file__).with_name('forex_factory_shadow_trial_v1.py').read_text()
 for prohibited in('SubmitOrder','CreateOrder','place_order','directional_signal_permitted:bool=True','trading_authority:bool=True'):assert prohibited not in source
def test_three_profiles_create_counterfactual_event_protection_and_regimes():
 snap=parse_snapshot(raw(),observed_at=NOW,start_day=date(2026,9,9));event=snap.events[0]
 before=classify_news_context(events=snap.events,as_of=event.scheduled_at-__import__('datetime').timedelta(minutes=8),policy=POLICIES[0]);assert before.regime=='PRE_ANNOUNCEMENT'and before.new_entry_recommendation=='SHADOW_BLOCK'and before.price_volume_confirmation_required
 aggressive=classify_news_context(events=snap.events,as_of=event.scheduled_at-__import__('datetime').timedelta(minutes=8),policy=POLICIES[2]);assert aggressive.regime=='NORMAL_SESSION'and aggressive.new_entry_recommendation=='SHADOW_ALLOW'
 assert all(x.directional_signal is None and x.order_influence_permitted is False for x in(before,aggressive))
def test_daily_risk_map_is_non_directional_and_auditable():
 risk=daily_risk_map(parse_snapshot(raw(),observed_at=NOW,start_day=date(2026,9,9)));row=next(x for x in risk['days']if x['day']=='2026-09-10');assert row['high_impact_count']==1 and risk['directional_signal_permitted']is False and risk['trading_authority']is False
