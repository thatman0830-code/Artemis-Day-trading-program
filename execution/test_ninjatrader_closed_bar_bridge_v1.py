from datetime import datetime,timezone,timedelta
import hashlib,json,pytest
from execution.ninjatrader_closed_bar_bridge_v1 import *
NOW=datetime(2026,9,8,6,31,tzinfo=timezone.utc)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def write(tmp_path,mutate=None):
 body={"close":101,"close_time_utc":"2026-09-08T06:30:00+00:00","exchange":"XCME","high":102,"instrument":"MES SEP26","is_closed":True,"low":99,"open":100,"open_time_utc":"2026-09-08T06:29:00+00:00","paper_only":True,"schema_version":SCHEMA,"source":"NINJATRADER_SIMULATION","timeframe":"1m","trading_authority":False,"volume":7}
 if mutate:mutate(body)
 doc={**body,"payload_sha256":hashlib.sha256(canonical(body)).hexdigest()};path=tmp_path/"MES.bar.json";path.write_text(json.dumps(doc));return path
def test_valid_complete_bar_maps_to_es_but_not_signal_authority(tmp_path):
 value=read_closed_bar(path=write(tmp_path),as_of=NOW)
 assert value.market is FuturesCanonicalMarket.ES and value.complete_market_bar and value.backtest_eligible
 assert value.signal_eligible is value.trading_authority is False
@pytest.mark.parametrize("mutate",[lambda x:x.update(instrument="ES SEP26"),lambda x:x.update(is_closed=False),lambda x:x.update(high=100),lambda x:x.update(volume=-1),lambda x:x.update(trading_authority=True),lambda x:x.update(close_time_utc="2026-09-08T06:29:30+00:00")])
def test_wrong_identity_forming_geometry_volume_authority_or_interval_reject(tmp_path,mutate):
 with pytest.raises(NinjaTraderClosedBarError):read_closed_bar(path=write(tmp_path,mutate),as_of=NOW)
def test_tamper_and_stale_reject(tmp_path):
 path=write(tmp_path);doc=json.loads(path.read_text());doc["close"]=1;path.write_text(json.dumps(doc))
 with pytest.raises(NinjaTraderClosedBarError):read_closed_bar(path=path,as_of=NOW)
 with pytest.raises(NinjaTraderClosedBarError):read_closed_bar(path=write(tmp_path),as_of=NOW+timedelta(minutes=3))
