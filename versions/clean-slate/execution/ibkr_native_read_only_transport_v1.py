"""Official IBAPI read-only transport for MES/MNQ evidence collection."""
from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import threading
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket

class IBKRNativeReadOnlyTransportError(RuntimeError):pass
_ROOT={FuturesCanonicalMarket.ES:"MES",FuturesCanonicalMarket.NQ:"MNQ"}
_BENIGN={2104,2106,2107,2108,2158}

def _amount(value):
 try:return Decimal(value)
 except(InvalidOperation,TypeError)as exc:raise IBKRNativeReadOnlyTransportError("account margin is invalid")from exc

class IBKRNativeReadOnlyTransportV1:
 """Exposes only the collector protocol; no order-submission method exists."""
 def __init__(self,*,client_class=None,contract_class=None,clock=None):
  self.client_class=client_class;self.contract_class=contract_class;self.clock=clock or(lambda:datetime.now(timezone.utc))
 def capture_read_only(self,*,host,port,client_id,timeout_seconds,market):
  if host!="127.0.0.1"or port!=7497 or not isinstance(market,FuturesCanonicalMarket):raise IBKRNativeReadOnlyTransportError("request boundary violation")
  if self.client_class is None:
   from ibapi.client import EClient
   from ibapi.wrapper import EWrapper
   base_client,base_wrapper=EClient,EWrapper
  else:base_client,base_wrapper=self.client_class
  if self.contract_class is None:
   from ibapi.contract import Contract
   contract_class=Contract
  else:contract_class=self.contract_class
  done={name:threading.Event()for name in("accounts","summary","positions","orders","contracts","market")};state={"accounts":[],"summary":{},"positions":0,"orders":0,"contracts":[],"market_type":None,"bid":None,"ask":None,"errors":[]}
  class Client(base_wrapper,base_client):
   def __init__(self):base_client.__init__(self,self)
   def managedAccounts(self,accountsList):state["accounts"]=[x for x in accountsList.split(",")if x];done["accounts"].set()
   def accountSummary(self,reqId,account,tag,value,currency):
    if tag in("InitMarginReq","MaintMarginReq")and currency in("USD",""):state["summary"][tag]=value
   def accountSummaryEnd(self,reqId):done["summary"].set()
   def position(self,account,contract,position,avgCost):
    if getattr(contract,"secType",None)=="FUT"and Decimal(str(position))!=0:state["positions"]+=1
   def positionEnd(self):done["positions"].set()
   def openOrder(self,orderId,contract,order,orderState):state["orders"]+=1
   def openOrderEnd(self):done["orders"].set()
   def contractDetails(self,reqId,details):state["contracts"].append(details)
   def contractDetailsEnd(self,reqId):done["contracts"].set()
   def marketDataType(self,reqId,marketDataType):state["market_type"]=marketDataType
   def tickPrice(self,reqId,tickType,price,attrib):
    if price is not None and price>0 and tickType in(1,2):state["bid"if tickType==1 else"ask"]=Decimal(str(price))
   def tickSnapshotEnd(self,reqId):done["market"].set()
   def error(self,reqId,*args):
    if len(args)==4:_,errorCode,errorString,_=args
    elif len(args)==3:errorCode,errorString,_=args
    else:state["errors"].append((-1,"malformed error callback"));return
    if errorCode not in _BENIGN:state["errors"].append((errorCode,errorString))
  client=Client();thread=None
  try:
   client.connect(host,port,clientId=client_id);thread=threading.Thread(target=client.run,daemon=True);thread.start()
   if not done["accounts"].wait(timeout_seconds):raise IBKRNativeReadOnlyTransportError("managed account timeout")
   client.reqAccountSummary(9101,"All","InitMarginReq,MaintMarginReq");client.reqPositions();client.reqAllOpenOrders()
   probe=contract_class();probe.symbol=_ROOT[market];probe.secType="FUT";probe.exchange="CME";probe.currency="USD";client.reqContractDetails(9102,probe)
   for name in("summary","positions","orders","contracts"):
    if not done[name].wait(timeout_seconds):raise IBKRNativeReadOnlyTransportError(f"{name} timeout")
   selection_at=self.clock();candidates=[]
   for details in state["contracts"]:
    contract=details.contract;expiry=str(getattr(contract,"lastTradeDateOrContractMonth",""))[:6]
    if len(expiry)==6 and expiry.isdigit()and expiry>=selection_at.strftime("%Y%m"):candidates.append((expiry,contract))
   if not candidates:raise IBKRNativeReadOnlyTransportError("no current exact micro contract")
   expiry,contract=min(candidates,key=lambda x:(x[0],x[1].conId))
   client.reqMarketDataType(1);client.reqMktData(9103,contract,"",True,False,[])
   done["market"].wait(timeout_seconds)
   if len(state["accounts"])!=1:raise IBKRNativeReadOnlyTransportError("exactly one managed paper account required")
   quote_complete=state["bid"]is not None and state["ask"]is not None
   captured_at=self.clock()
   return {"captured_at":captured_at,"account_id":state["accounts"][0],"connected":client.isConnected(),"api_read_only":True,"order_placement_available":False,"open_order_count":state["orders"],"futures_position_count":state["positions"],"market_data_type":state["market_type"],"market_data_live":state["market_type"]==1 and quote_complete,"bid":state["bid"],"ask":state["ask"],"local_symbol":contract.localSymbol,"expiry_yyyymm":expiry,"ibkr_contract_id":contract.conId,"initial_margin_usd":_amount(state["summary"].get("InitMarginReq","0")),"maintenance_margin_usd":_amount(state["summary"].get("MaintMarginReq","0"))}
  finally:
   try:client.cancelAccountSummary(9101);client.cancelPositions();client.cancelMktData(9103)
   except Exception:pass
   client.disconnect()
   if thread is not None:thread.join(timeout=1)
