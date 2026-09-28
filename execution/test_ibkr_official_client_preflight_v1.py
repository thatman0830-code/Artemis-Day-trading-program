import pytest
from execution.ibkr_official_client_preflight_v1 import *
class Module:
 @staticmethod
 def get_version_string():return EXPECTED_IBAPI_VERSION
class Client:
 def __init__(self):self.connected=False;self.disconnected=False
 def connect(self,host,port,clientId):assert(host,port,clientId)==("127.0.0.1",7497,71);self.connected=True
 def isConnected(self):return self.connected
 def serverVersion(self):return 187
 def disconnect(self):self.disconnected=True
def test_installation_and_handshake_are_connection_only():
 assert verify_installation(module_loader=lambda name:Module)==EXPECTED_IBAPI_VERSION
 value=handshake(client_factory=Client)
 assert value.connected and value.server_version==187 and value.read_only_intent
 assert value.account_data_requested is False and value.market_data_requested is False
 assert value.orders_requested is False and value.trading_authority is False
def test_version_and_connection_boundaries_fail_closed():
 class Bad: get_version_string=lambda self:"0"
 with pytest.raises(IBKROfficialClientPreflightError,match="version"):verify_installation(module_loader=lambda name:Bad())
 for kwargs in ({"host":"localhost"},{"port":7496},{"client_id":True}):
  with pytest.raises(IBKROfficialClientPreflightError,match="boundary"):handshake(client_factory=Client,**kwargs)
def test_failed_protocol_state_rejects_and_disconnects():
 class Failed(Client):
  def isConnected(self):return False
 with pytest.raises(IBKROfficialClientPreflightError,match="handshake"):handshake(client_factory=Failed)
