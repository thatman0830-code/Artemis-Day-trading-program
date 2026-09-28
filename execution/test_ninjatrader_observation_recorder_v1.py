from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib,json,pytest
from execution.ninjatrader_observation_recorder_v1 import *
from execution.ninjatrader_quote_bridge_v1 import SCHEMA

NOW=datetime(2026,9,7,7,tzinfo=timezone.utc)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def quote(root,seq,now=NOW):
 instrument={"MES":"MES SEP26","MNQ":"MNQ SEP26"}[root]
 body={"ask":101.25,"bid":101.0,"captured_at_utc":now.isoformat(),"instrument":instrument,"last":101.0,"last_volume":2,"paper_only":True,"schema_version":SCHEMA,"sequence":seq,"source":"NINJATRADER_SIMULATION","trading_authority":False}
 return {**body,"payload_sha256":hashlib.sha256(canonical(body)).hexdigest()}
def put(root:Path,name,seq,now=NOW):root.mkdir(parents=True,exist_ok=True);(root/(name+".quote.json")).write_bytes(canonical(quote(name,seq,now)))
def test_pair_appends_hash_chains_and_skips_duplicates(tmp_path):
 q=tmp_path/"q";a=tmp_path/"a";put(q,"MES",3);put(q,"MNQ",7)
 assert record_cycle(quote_root=q,archive_root=a,as_of=NOW)=={"MES":True,"MNQ":True}
 assert record_cycle(quote_root=q,archive_root=a,as_of=NOW)=={"MES":False,"MNQ":False}
 put(q,"MES",8,NOW+timedelta(milliseconds=100));put(q,"MNQ",11,NOW+timedelta(milliseconds=100))
 record_cycle(quote_root=q,archive_root=a,as_of=NOW+timedelta(milliseconds=100))
 for lane in("ES","NQ"):
  lines=(a/lane/"2026-09-07.jsonl").read_text().splitlines();assert len(lines)==2
  assert json.loads(lines[1])["previous_record_sha256"]==json.loads(lines[0])["record_sha256"]
  assert json.loads((a/lane/"manifest.json").read_text())["record_count"]==2
def test_tampering_and_regression_fail_closed(tmp_path):
 q=tmp_path/"q";a=tmp_path/"a";put(q,"MES",3);record_one(quote_path=q/"MES.quote.json",archive_root=a,as_of=NOW)
 chain=a/"ES"/"2026-09-07.jsonl";chain.write_text(chain.read_text().replace('"bid":"101.0"','"bid":"1"'))
 put(q,"MES",4,NOW+timedelta(milliseconds=100))
 with pytest.raises(ValueError,match="hash"):record_one(quote_path=q/"MES.quote.json",archive_root=a,as_of=NOW+timedelta(milliseconds=100))
def test_missing_or_stale_provider_evidence_waits_without_writing(tmp_path):
 q=tmp_path/"q";a=tmp_path/"a";put(q,"MES",3,NOW-timedelta(seconds=2))
 assert record_cycle(quote_root=q,archive_root=a,as_of=NOW)=={"MES":None,"MNQ":None}
 assert not a.exists()
def test_recorder_has_no_order_or_account_surface():
 source=(Path(__file__).with_name("ninjatrader_observation_recorder_v1.py")).read_text()
 for prohibited in("SubmitOrder","CreateOrder","Account.","private_key","wallet"):
  assert prohibited not in source
