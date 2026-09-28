import json
from pathlib import Path
from futures_data.databento_lineage_probe import IDS,resolve
class R:
 status=200
 def __init__(self,b):self.b=b
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self,n):return self.b
def test_lineage_is_bounded_free_and_nontrading(tmp_path):
 payload={"status":0,"partial":[],"not_found":[],"result":{IDS[0]:[{"d0":"2026-09-10","d1":"2026-09-11","s":"MESU6"}],IDS[1]:[{"d0":"2026-09-10","d1":"2026-09-11","s":"MNQU6"}]}}
 result=resolve(key='db-'+'x'*29,day='2026-09-10',output=tmp_path/'x.json',opener=lambda req,timeout:R(json.dumps(payload).encode()))
 assert result['state']=='LINEAGE_RESOLVED' and result['metadata_cost_usd']=='0' and result['trading_authority']is False
def test_wrapper_keeps_key_on_stdin():
 text=(Path(__file__).parents[1]/'scripts/run_databento_lineage_probe.ps1').read_text();assert 'StandardInput.WriteLine($plain)'in text and 'ZeroFreeBSTR'in text and '--api-key'not in text.lower()
