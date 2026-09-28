from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from execution.ibkr_native_read_only_transport_v1 import *
NOW=datetime(2026,9,6,18,tzinfo=timezone.utc)
class Wrapper:pass
class Contract:pass
class Client:
 def __init__(self,wrapper):self.ok=False
 def connect(self,*args,**kwargs):
  self.ok=True;self.error(-1,1757200000,2104,"farm connected","");self.error(-1,2106,"historical farm connected","");self.managedAccounts("DU123456")
 def run(self):pass
 def disconnect(self):self.ok=False
 def isConnected(self):return self.ok
 def reqAccountSummary(self,*args):self.accountSummary(9101,"DU123456","InitMarginReq","3000","USD");self.accountSummary(9101,"DU123456","MaintMarginReq","2700","USD");self.accountSummaryEnd(9101)
 def cancelAccountSummary(self,*args):pass
 def reqPositions(self):self.positionEnd()
 def cancelPositions(self):pass
 def reqAllOpenOrders(self):self.openOrderEnd()
 def reqContractDetails(self,req,probe):
  old=SimpleNamespace(symbol=probe.symbol,secType="FUT",exchange="CME",currency="USD",lastTradeDateOrContractMonth="20260619",localSymbol=probe.symbol+"M6",conId=1)
  current=SimpleNamespace(symbol=probe.symbol,secType="FUT",exchange="CME",currency="USD",lastTradeDateOrContractMonth="20260918",localSymbol=probe.symbol+"U6",conId=2)
  self.contractDetails(req,SimpleNamespace(contract=old));self.contractDetails(req,SimpleNamespace(contract=current));self.contractDetailsEnd(req)
 def reqMarketDataType(self,value):self.marketDataType(9103,1)
 def reqMktData(self,*args):self.tickPrice(9103,1,25000,SimpleNamespace());self.tickPrice(9103,2,25000.25,SimpleNamespace());self.tickSnapshotEnd(9103)
 def cancelMktData(self,*args):pass
def transport(client=Client):return IBKRNativeReadOnlyTransportV1(client_class=(client,Wrapper),contract_class=Contract,clock=lambda:NOW)
def test_native_transport_selects_nearest_current_micro_and_sanitized_schema():
 value=transport().capture_read_only(host="127.0.0.1",port=7497,client_id=71,timeout_seconds=1,market=FuturesCanonicalMarket.NQ)
 assert value["account_id"]=="DU123456"and value["local_symbol"]=="MNQU6"and value["expiry_yyyymm"]=="202609"
 assert value["ibkr_contract_id"]==2 and value["market_data_live"]is True
 assert value["market_data_type"]==1 and value["bid"]==Decimal("25000")and value["ask"]==Decimal("25000.25")
 assert value["initial_margin_usd"]==Decimal("3000")and value["maintenance_margin_usd"]==Decimal("2700")
 assert not hasattr(IBKRNativeReadOnlyTransportV1,"placeOrder")
def test_delayed_data_is_explicitly_not_live():
 class Delayed(Client):
  def reqMarketDataType(self,value):self.marketDataType(9103,3)
 value=transport(Delayed).capture_read_only(host="127.0.0.1",port=7497,client_id=71,timeout_seconds=1,market=FuturesCanonicalMarket.ES)
 assert value["market_data_live"]is False
def test_live_type_without_two_sided_quote_is_not_live_evidence():
 class OneSided(Client):
  def reqMktData(self,*args):self.tickPrice(9103,1,25000,SimpleNamespace());self.tickSnapshotEnd(9103)
 value=transport(OneSided).capture_read_only(host="127.0.0.1",port=7497,client_id=71,timeout_seconds=1,market=FuturesCanonicalMarket.NQ)
 assert value["market_data_type"]==1 and value["market_data_live"]is False and value["ask"]is None
def test_wrong_port_and_missing_current_contract_fail_closed():
 with pytest.raises(IBKRNativeReadOnlyTransportError,match="boundary"):transport().capture_read_only(host="127.0.0.1",port=7496,client_id=71,timeout_seconds=1,market=FuturesCanonicalMarket.NQ)
 class NoneCurrent(Client):
  def reqContractDetails(self,req,probe):self.contractDetailsEnd(req)
 with pytest.raises(IBKRNativeReadOnlyTransportError,match="contract"):transport(NoneCurrent).capture_read_only(host="127.0.0.1",port=7497,client_id=71,timeout_seconds=1,market=FuturesCanonicalMarket.NQ)
