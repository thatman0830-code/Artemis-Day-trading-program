import json
from hashlib import sha256
from pathlib import Path
import pytest
from futures_data.databento_recovery_policy import PolicyError,canonical,evaluate
def save(path,body):body["report_sha256"]=sha256(canonical(body)).hexdigest();path.write_bytes(canonical(body)+b'\n')
def fixtures(tmp):
 paths=[]
 for lane,price in (("ES",3),("NQ",8)):
  p=tmp/(lane+'.json');save(p,{"lane":lane,"missing_databento_count":0,"databento_minute_count":1380,"ninjatrader_minute_count":1147,"price_conflict_count":price});paths.append(p)
 lineage=tmp/'lineage.json';save(lineage,{"state":"LINEAGE_RESOLVED","instrument_mappings":{"42003239":{"s":"MESU6"},"42004800":{"s":"MNQU6"}}});return *paths,lineage
def test_only_separate_nonexecuting_lane_is_eligible(tmp_path):
 es,nq,lineage=fixtures(tmp_path);result=evaluate(es_path=es,nq_path=nq,lineage_path=lineage)
 assert result["decision"]=="SEPARATE_SOURCE_RESEARCH_ELIGIBLE" and result["cross_source_merge_permitted"]is False and result["execution_permitted"]is False
def test_lineage_or_price_divergence_fails_closed(tmp_path):
 es,nq,lineage=fixtures(tmp_path);doc=json.loads(lineage.read_text());doc["instrument_mappings"]["42003239"]["s"]="MESZ6";save(lineage,{k:v for k,v in doc.items()if k!="report_sha256"})
 with pytest.raises(PolicyError,match="lineage"):evaluate(es_path=es,nq_path=nq,lineage_path=lineage)
