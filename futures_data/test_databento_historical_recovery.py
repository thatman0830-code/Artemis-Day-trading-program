import io,json
from datetime import date
from pathlib import Path
import pytest
from futures_data.databento_historical_recovery import RecoveryError,acquire
class Response:
 def __init__(self,payload):self.status=200;self.payload=payload
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,limit):return self.payload
def opener(request,timeout):
 if "metadata.get_cost" in request.full_url:return Response(b"0.001")
 symbol="MES.v.0" if "MES.v.0" in request.full_url else "MNQ.v.0"
 row={"hd":{"ts_event":"2026-09-10T00:00:00.000000000Z","instrument_id":1},"open":"1","high":"2","low":"1","close":"2","volume":"3","symbol":symbol}
 return Response(json.dumps(row).encode()+b"\n")
def test_acquire_retains_separate_immutable_nontrading_lanes(tmp_path:Path):
 result=acquire(key="db-"+"x"*29,day=date(2026,9,10),root=tmp_path,opener=opener)
 assert result["state"]=="RECOVERY_EVIDENCE_RETAINED" and result["trading_authority"]is False
 assert (tmp_path/"2026-09-10/ES.jsonl").exists()and(tmp_path/"2026-09-10/NQ.jsonl").exists()
 with pytest.raises(RecoveryError,match="already retained"):acquire(key="db-"+"x"*29,day=date(2026,9,10),root=tmp_path,opener=opener)
def test_cost_ceiling_fails_before_data(tmp_path:Path):
 calls=[]
 def costly(request,timeout):calls.append(request.full_url);return Response(b"0.20")
 with pytest.raises(RecoveryError,match="cost ceiling"):acquire(key="db-"+"x"*29,day=date(2026,9,10),root=tmp_path,opener=costly)
 assert all("metadata.get_cost" in call for call in calls)
def test_wrapper_uses_stdin_and_zeroes_secret():
 text=(Path(__file__).parents[1]/"scripts/run_databento_historical_recovery.ps1").read_text()
 assert "StandardInput.WriteLine($plain)"in text and "ZeroFreeBSTR"in text and "--api-key"not in text.lower()
