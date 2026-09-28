import json
from datetime import datetime,timezone
from hashlib import sha256

import pytest

from futures_data.aggregate_probe import ProbeError,credential_free_mock_opener
from futures_data.raw_probe import DESTINATIONS,run_raw_probe

NOW=datetime(2026,8,26,tzinfo=timezone.utc)
def metadata(tmp_path):
 p=tmp_path/"metadata.json";p.write_text(json.dumps({"as_of_utc":"2026-08-26T00:00:00Z","contracts":{"ES":[{"ticker":"ESU6"}],"NQ":[{"ticker":"NQU6"}]}}));return p

def test_raw_responses_retained_byte_exact_and_separate(tmp_path):
 captured=[]
 def opener(request,timeout):
  status,raw=credential_free_mock_opener(request,timeout);captured.append(raw);return status,raw
 result=run_raw_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=opener,sleep=lambda _:None)
 assert result["raw_retained"] is True and len(captured)==6
 found=[]
 for root in ("ES","NQ"):
  market=tmp_path/"data/backtests"/DESTINATIONS[root];raw_files=sorted((market/"raw").glob("*.json"));assert len(raw_files)==3
  found.extend(x.read_bytes() for x in raw_files)
  for manifest in sorted((market/"manifests").glob("*.json")):
   item=json.loads(manifest.read_text());raw=(market/item["raw_relative_path"]).read_bytes()
   assert item["raw_retained"] is True and sha256(raw).hexdigest()==item["raw_response_sha256"]
   text=manifest.read_text()+ (market/"reports/validation.json").read_text();assert "synthetic-offline-only" not in text and "Authorization" not in text
 assert sorted(found)==sorted(captured)

def test_existing_destination_fails_without_overwrite(tmp_path):
 target=tmp_path/"data/backtests"/DESTINATIONS["ES"];target.mkdir(parents=True);sentinel=target/"keep";sentinel.write_text("owner")
 with pytest.raises(ProbeError) as caught:run_raw_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=credential_free_mock_opener,sleep=lambda _:None)
 assert caught.value.safe["rejection_category"]=="OUTPUT_EXISTS" and sentinel.read_text()=="owner"

def test_no_path_collision_and_raw_true_is_mandatory():
 assert DESTINATIONS["ES"]!=DESTINATIONS["NQ"] and "es_" in DESTINATIONS["ES"] and "nq_" in DESTINATIONS["NQ"]

def test_failure_preserves_raw_as_rejected_evidence_without_secret(tmp_path):
 calls=0
 def opener(request,timeout):
  nonlocal calls;calls+=1
  if calls==3:return 500,b'{"status":"ERROR","message":"synthetic-offline-only"}'
  return credential_free_mock_opener(request,timeout)
 with pytest.raises(ProbeError):run_raw_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=opener,sleep=lambda _:None)
 rejected=list((tmp_path/"data/backtests/rejected_probes").glob("raw_probe_*"));assert len(rejected)==1
 report=(rejected[0]/"sanitized_failure.json").read_text();assert "synthetic-offline-only" not in report and "Authorization" not in report
 assert any(rejected[0].rglob("*.json"))

def test_mock_never_uses_network_and_key_not_in_url_or_arguments(tmp_path):
 calls=[]
 def opener(request,timeout):
  calls.append(request);return credential_free_mock_opener(request,timeout)
 run_raw_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=opener,sleep=lambda _:None)
 assert len(calls)==6 and all("synthetic-offline-only" not in x.full_url and "apiKey" not in x.full_url for x in calls)

