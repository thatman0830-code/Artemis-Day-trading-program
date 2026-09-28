from datetime import datetime,timezone,timedelta
import hashlib,json,pytest
from execution.ninjatrader_closed_bar_recorder_v1 import *
from execution.ninjatrader_closed_bar_bridge_v1 import SCHEMA
NOW=datetime(2026,9,8,6,42,tzinfo=timezone.utc)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def put(root,name,close):
 inst={"MES":"MES SEP26","MNQ":"MNQ SEP26"}[name];body={"close":101,"close_time_utc":close.isoformat(),"exchange":"XCME","high":102,"instrument":inst,"is_closed":True,"low":100,"open":100,"open_time_utc":(close-timedelta(minutes=1)).isoformat(),"paper_only":True,"schema_version":SCHEMA,"source":"NINJATRADER_SIMULATION","timeframe":"1m","trading_authority":False,"volume":8};body["payload_sha256"]=hashlib.sha256(canonical(body)).hexdigest();root.mkdir(exist_ok=True);(root/(name+".bar.json")).write_bytes(canonical(body))
def test_pair_is_append_only_duplicate_safe_and_gap_explicit(tmp_path):
 b=tmp_path/"b";a=tmp_path/"a";put(b,"MES",NOW);put(b,"MNQ",NOW);assert cycle(bar_root=b,archive_root=a,as_of=NOW)=={"MES":True,"MNQ":True};assert cycle(bar_root=b,archive_root=a,as_of=NOW)=={"MES":False,"MNQ":False}
 put(b,"MES",NOW+timedelta(minutes=2));record_one(bar_path=b/"MES.bar.json",archive_root=a,as_of=NOW+timedelta(minutes=2));m=json.loads((a/"ES"/"manifest.json").read_text());assert m["record_count"]==2 and m["unresolved_gap_count"]==1
def test_chain_tampering_fails_closed(tmp_path):
 b=tmp_path/"b";a=tmp_path/"a";put(b,"MES",NOW);record_one(bar_path=b/"MES.bar.json",archive_root=a,as_of=NOW);p=a/"ES"/"2026-09-08.jsonl";p.write_text(p.read_text().replace('"volume":8','"volume":9'));put(b,"MES",NOW+timedelta(minutes=1))
 with pytest.raises(ValueError,match="chain"):record_one(bar_path=b/"MES.bar.json",archive_root=a,as_of=NOW+timedelta(minutes=1))
def test_cme_maintenance_is_counted_but_not_unresolved(tmp_path):
 b=tmp_path/"b";a=tmp_path/"a";left=datetime(2026,9,8,21,0,tzinfo=timezone.utc);right=datetime(2026,9,8,22,1,tzinfo=timezone.utc)
 put(b,"MES",left);record_one(bar_path=b/"MES.bar.json",archive_root=a,as_of=left);put(b,"MES",right);record_one(bar_path=b/"MES.bar.json",archive_root=a,as_of=right)
 manifest=json.loads((a/"ES"/"manifest.json").read_text());assert manifest["unresolved_gap_count"]==0 and manifest["scheduled_non_trading_minute_count"]==60
