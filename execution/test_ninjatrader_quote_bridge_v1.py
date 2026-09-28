from datetime import datetime,timedelta,timezone
import hashlib,json
import pytest
from execution.ninjatrader_quote_bridge_v1 import *
NOW=datetime(2026,9,7,6,tzinfo=timezone.utc)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def write(tmp_path,mutate=None):
 body={"ask":29600.25,"bid":29600.0,"captured_at_utc":NOW.isoformat(),"instrument":"MNQ SEP26","last":29600.0,"last_volume":7,"paper_only":True,"schema_version":SCHEMA,"sequence":4,"source":"NINJATRADER_SIMULATION","trading_authority":False}
 if mutate:mutate(body)
 doc={**body,"payload_sha256":hashlib.sha256(canonical(body)).hexdigest()};path=tmp_path/"MNQ.quote.json";path.write_text(json.dumps(doc));return path
def test_valid_snapshot_is_sanitized_but_not_self_entitled(tmp_path):
 value=read_quote_snapshot(path=write(tmp_path),as_of=NOW)
 assert value.market is FuturesCanonicalMarket.NQ and value.bid==Decimal("29600.0")and value.ask==Decimal("29600.25")
 assert value.entitlement_confirmed is False and value.decision_use_permitted is False and value.trading_authority is False
@pytest.mark.parametrize("mutate",[lambda x:x.update(instrument="NQ SEP26"),lambda x:x.update(instrument="MNQ MAY26"),lambda x:x.update(ask=29599),lambda x:x.update(captured_at_utc=(NOW-timedelta(seconds=2)).isoformat()),lambda x:x.update(source="UNKNOWN"),lambda x:x.update(trading_authority=True),lambda x:x.update(sequence=True)])
def test_wrong_contract_crossed_stale_source_authority_or_sequence_rejects(tmp_path,mutate):
 with pytest.raises(NinjaTraderQuoteBridgeError):read_quote_snapshot(path=write(tmp_path,mutate),as_of=NOW)
def test_tampering_and_symlink_reject(tmp_path):
 path=write(tmp_path);doc=json.loads(path.read_text());doc["bid"]=1;path.write_text(json.dumps(doc))
 with pytest.raises(NinjaTraderQuoteBridgeError):read_quote_snapshot(path=path,as_of=NOW)
def test_exporter_has_no_trading_or_network_surface():
 source=(Path(__file__).parents[1]/"integrations/ninjatrader/HermesReadOnlyQuoteExporter.cs").read_text()
 for prohibited in("SubmitOrder","CreateOrder","Account.","HttpClient","Socket","TcpClient","WebClient"):
  assert prohibited not in source
 assert "OnMarketData"in source and 'root != "MES" && root != "MNQ"'in source

def test_dual_addon_owns_both_read_only_subscriptions():
 source=(Path(__file__).parents[1]/"integrations/ninjatrader/HermesDualQuoteAddOn.cs").read_text()
 for prohibited in("SubmitOrder","CreateOrder","Account.","HttpClient","Socket","TcpClient","WebClient"):
  assert prohibited not in source
 assert 'Subscribe("MES", "MES SEP26", OnMesMarketData)' in source
 assert 'Subscribe("MNQ", "MNQ SEP26", OnMnqMarketData)' in source
 assert source.count(".MarketData.Update +=") == 1
 assert ".MarketData.Update -= handler" in source
 assert "State == State.Active" in source and "State == State.Terminated" in source
