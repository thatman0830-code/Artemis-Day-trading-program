from datetime import datetime,timezone,timedelta
import hashlib,json,pytest
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_closed_bar_dataset_v1 import *
NOW=datetime(2026,9,8,7,tzinfo=timezone.utc)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def build(root,market=FuturesCanonicalMarket.ES,gap=False):
 lane=root/market.value;lane.mkdir(parents=True);inst="MES SEP26"if market is FuturesCanonicalMarket.ES else"MNQ SEP26";previous="0"*64;docs=[]
 for i in range(3):
  close=NOW+timedelta(minutes=i+(1 if gap and i==2 else 0));body={"close":"101.25","close_time_utc":close.isoformat(),"high":"102","instrument":inst,"low":"100","market":market.value,"open":"101","open_time_utc":(close-timedelta(minutes=1)).isoformat(),"paper_only":True,"previous_record_sha256":previous,"schema_version":RECORD_VERSION,"source_payload_sha256":hashlib.sha256(str(i).encode()).hexdigest(),"trading_authority":False,"volume":str(10+i)};previous=hashlib.sha256(canonical(body)).hexdigest();docs.append({**body,"record_sha256":previous})
 (lane/"2026-09-08.jsonl").write_text("\n".join(json.dumps(x,sort_keys=True,separators=(",",":"))for x in docs)+"\n");meta={"archive_file":"2026-09-08.jsonl","head_record_sha256":previous,"instrument":inst,"last_close_time_utc":docs[-1]["close_time_utc"],"market":market.value,"record_count":3,"schema_version":RECORD_VERSION,"state":"RECORDING","trading_authority":False,"unresolved_gap_count":1 if gap else 0};(lane/"manifest.json").write_text(json.dumps(meta));return lane
@pytest.mark.parametrize("market",list(FuturesCanonicalMarket))
def test_promotes_exact_gap_free_chain_to_smoke_dataset(tmp_path,market):
 build(tmp_path,market);value=read_closed_bar_dataset(tmp_path,market=market,day="2026-09-08",as_of=NOW+timedelta(minutes=4));assert len(value.dataset.candles)==3 and value.dataset.symbol==market.value;assert value.smoke_replay_eligible is True and value.training_validation_eligible is value.untouched_oos_eligible is False;assert value.paper_execution_permitted is value.trading_authority is False
def test_gap_tamper_and_cross_market_fail_closed(tmp_path):
 build(tmp_path,gap=True)
 with pytest.raises(ValueError,match="manifest"):read_closed_bar_dataset(tmp_path,market=FuturesCanonicalMarket.ES,day="2026-09-08",as_of=NOW+timedelta(minutes=5))
def test_backtesting_source_has_no_execution_dependency_or_authority():
 source=__import__('pathlib').Path(__file__).with_name('ninjatrader_closed_bar_dataset_v1.py').read_text();assert "from execution"not in source
 for text in("paper_execution_permitted:bool=True","trading_authority:bool=True","SubmitOrder","CreateOrder"):assert text not in source
