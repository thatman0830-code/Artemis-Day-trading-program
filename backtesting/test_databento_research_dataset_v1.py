import json
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from backtesting.databento_research_dataset_v1 import canonical,derive_complete_m5,read_databento_research_dataset,read_databento_research_days
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe,normalize_historical_candle
def test_normalized_lane_is_separate_and_nonexecuting(tmp_path):
 day=tmp_path/'2026-09-10';day.mkdir();row={"hd":{"ts_event":"2026-09-10T00:00:00Z","instrument_id":1},"open":"1","high":"2","low":"1","close":"2","volume":"3"};raw=canonical(row)+b'\n';(day/'ES.jsonl').write_bytes(raw);body={"state":"RECOVERY_EVIDENCE_RETAINED","trading_authority":False,"lanes":{"ES":{"sha256":sha256(raw).hexdigest(),"row_count":1}}};body["manifest_sha256"]=sha256(canonical(body)).hexdigest();(day/'manifest.json').write_bytes(canonical(body)+b'\n')
 result=read_databento_research_dataset(tmp_path,market=FuturesCanonicalMarket.ES,day='2026-09-10',as_of=datetime(2026,9,11,tzinfo=timezone.utc));assert result.record_count==1 and result.dataset.source=='databento-historical-recovery' and result.paper_execution_permitted is False and result.trading_authority is False
def test_evaluator_declares_no_execution_authority():
 text=(Path(__file__).parents[1]/'scripts/evaluate_databento_research_day.py').read_text();assert 'paper_execution_permitted":False'in text and 'trading_authority":False'in text and 'compare_shadow_profiles(trades=()'in text


def test_two_days_remain_one_provider_consistent_lane(tmp_path):
 for day_name,stamp in (("2026-09-09","2026-09-09T00:00:00Z"),("2026-09-10","2026-09-10T00:00:00Z")):
  day=tmp_path/day_name;day.mkdir();row={"hd":{"ts_event":stamp,"instrument_id":1},"open":"1","high":"2","low":"1","close":"2","volume":"3"};raw=canonical(row)+b'\n';(day/'ES.jsonl').write_bytes(raw);body={"state":"RECOVERY_EVIDENCE_RETAINED","trading_authority":False,"lanes":{"ES":{"sha256":sha256(raw).hexdigest(),"row_count":1}}};body["manifest_sha256"]=sha256(canonical(body)).hexdigest();(day/'manifest.json').write_bytes(canonical(body)+b'\n')
 result=read_databento_research_days(tmp_path,market=FuturesCanonicalMarket.ES,days=("2026-09-09","2026-09-10"),as_of=datetime(2026,9,11,tzinfo=timezone.utc))
 assert result.record_count==2 and result.dataset.source=="databento-historical-recovery" and result.trading_authority is False


def test_complete_aligned_five_minute_bucket_is_derived_without_fill():
 opened=datetime(2026,9,10,tzinfo=timezone.utc);dataset_id='d'*64;candles=[]
 for i in range(5):
  start=opened.replace(minute=i);candles.append(normalize_historical_candle({'symbol':'ES','timeframe':'1m','open_time':start,'close_time':start.replace(minute=i+1),'open':Decimal(str(10+i)),'high':Decimal(str(12+i)),'low':Decimal(str(9+i)),'close':Decimal(str(11+i)),'volume':Decimal('2'),'is_closed':True},dataset_id=dataset_id,schema_version='historical-candle-v1',source='databento-historical-recovery',exchange='XCME'))
 result=derive_complete_m5(tuple(candles),dataset_id=dataset_id)
 assert len(result)==1 and result[0].timeframe is CanonicalTimeframe.M5 and result[0].open==candles[0].open and result[0].close==candles[-1].close and result[0].volume==Decimal('10')
 assert derive_complete_m5(tuple(candles[:-1]),dataset_id=dataset_id)==()
