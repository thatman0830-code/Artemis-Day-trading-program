"""Minimal official-IBAPI installation and TWS handshake preflight."""
from __future__ import annotations
from dataclasses import dataclass
import importlib

VERSION="ibkr-official-client-preflight-v1"
EXPECTED_IBAPI_VERSION="10.50.1"
class IBKROfficialClientPreflightError(RuntimeError):pass
@dataclass(frozen=True,slots=True)
class IBKROfficialClientPreflightV1:
 ibapi_version:str;host:str;port:int;client_id:int;connected:bool;server_version:int
 read_only_intent:bool=True;account_data_requested:bool=False
 market_data_requested:bool=False;orders_requested:bool=False
 trading_authority:bool=False
def verify_installation(*,module_loader=importlib.import_module)->str:
 try:module=module_loader("ibapi")
 except (ImportError,ModuleNotFoundError)as exc:raise IBKROfficialClientPreflightError("official ibapi is not installed")from exc
 version=module.get_version_string()
 if version!=EXPECTED_IBAPI_VERSION:raise IBKROfficialClientPreflightError("official ibapi version mismatch")
 return version
def handshake(*,client_factory=None,host="127.0.0.1",port=7497,client_id=71)->IBKROfficialClientPreflightV1:
 if host!="127.0.0.1"or port!=7497 or isinstance(client_id,bool)or not isinstance(client_id,int)or not 1<=client_id<=999:raise IBKROfficialClientPreflightError("connection escapes local paper boundary")
 version=verify_installation()
 if client_factory is None:
  from ibapi.client import EClient
  from ibapi.wrapper import EWrapper
  class Connection(EWrapper,EClient):
   def __init__(self):EClient.__init__(self,self)
  client_factory=Connection
 client=client_factory()
 try:
  client.connect(host,port,clientId=client_id)
  connected=client.isConnected();server=client.serverVersion()
 finally:client.disconnect()
 if connected is not True or isinstance(server,bool)or not isinstance(server,int)or server<=0:raise IBKROfficialClientPreflightError("TWS protocol handshake failed")
 return IBKROfficialClientPreflightV1(version,host,port,client_id,True,server)
