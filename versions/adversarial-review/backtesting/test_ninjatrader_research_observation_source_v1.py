from datetime import datetime,timezone,timedelta
import hashlib,json,pytest
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_research_observation_source_v1 import *
from execution.ninjatrader_observation_recorder_v1 import VERSION as RV,_canonical
NOW=datetime(2026,9,8,tzinfo=timezone.utc)
def build(root,market=FuturesCanonicalMarket.ES):
 lane=root/market.value;lane.mkdir(parents=True);inst="MES SEP26" if market is FuturesCanonicalMarket.ES else "MNQ SEP26";previous="0"*64;rows=[]
 for i in range(2):
  body={"ask":"101.25","bid":"101.0","captured_at_utc":(NOW+timedelta(seconds=i)).isoformat(),"instrument":inst,"last":"101.0","last_volume":2,"market":market.value,"paper_only":True,"previous_record_sha256":previous,"recorded_at_utc":(NOW+timedelta(seconds=i)).isoformat(),"schema_version":RV,"source":"NINJATRADER_SIMULATION","source_sequence":i+1,"source_sequence_delta":None if i==0 else 1,"trading_authority":False};previous=hashlib.sha256(_canonical(body)).hexdigest();rows.append({**body,"record_sha256":previous})
 (lane/"2026-09-08.jsonl").write_text("\n".join(json.dumps(x,sort_keys=True,separators=(",",":")) for x in rows)+"\n")
 manifest={"archive_file":"2026-09-08.jsonl","head_record_sha256":previous,"instrument":inst,"last_captured_at_utc":rows[-1]["captured_at_utc"],"last_source_sequence":2,"market":market.value,"record_count":2,"schema_version":RV,"state":"RECORDING","trading_authority":False};(lane/"manifest.json").write_text(json.dumps(manifest));return lane
@pytest.mark.parametrize("market",list(FuturesCanonicalMarket))
def test_verified_chain_binds_to_isolated_advisory_market(tmp_path,market):
 build(tmp_path,market);value=read_futures_research_observations(tmp_path,market=market,day="2026-09-08",as_of=NOW+timedelta(seconds=2))
 assert value.market is market and len(value.observations)==2 and value.maximum_observation_gap_seconds==1
 assert value.complete_market_bars is value.backtest_eligible is value.signal_eligible is False
 assert value.paper_execution_permitted is value.live_trading_permitted is value.trading_authority is False
def test_tamper_cross_market_and_manifest_conflict_reject(tmp_path):
 lane=build(tmp_path);path=lane/"2026-09-08.jsonl";path.write_text(path.read_text().replace('"bid":"101.0"','"bid":"1"',1))
 with pytest.raises(ValueError,match="chain"):read_futures_research_observations(tmp_path,market=FuturesCanonicalMarket.ES,day="2026-09-08",as_of=NOW+timedelta(seconds=2))
def test_source_has_no_execution_surface():
 source=__import__("pathlib").Path(__file__).with_name("ninjatrader_research_observation_source_v1.py").read_text()
 for prohibited in("SubmitOrder","CreateOrder","Account.","paper_execution_permitted: bool = True","trading_authority: bool = True"):
  assert prohibited not in source
