from datetime import datetime,timezone
import hashlib,json
import pytest
from execution.futures_micro_official_docs_v1 import *
from execution.futures_micro_official_docs_v1 import _OfficialRedirect

def test_acquire_retains_exact_bounded_sources(tmp_path):
 def transport(url):return ("<html>"+url+" MES MNQ</html>").encode()
 clock=lambda tz:datetime(2026,9,6,tzinfo=timezone.utc)
 result=acquire(output_root=tmp_path,transport=transport,clock=clock)
 assert [x["name"]for x in result["records"]]==list(SOURCES)
 assert result["credentials_used"]is False and result["trading_authority"]is False
 assert result["paper_execution_permitted"]is False
 for record in result["records"]:
  raw=(tmp_path/record["relative_path"]).read_bytes()
  assert hashlib.sha256(raw).hexdigest()==record["sha256"]
 manifest=tmp_path/f"ibkr_micro_{result['evidence_id']}.json"
 assert json.loads(manifest.read_bytes())["evidence_id"]==result["evidence_id"]

def test_replay_is_idempotent_but_conflicts_fail(tmp_path):
 transport=lambda url:url.encode();clock=lambda tz:datetime(2026,9,6,tzinfo=timezone.utc)
 first=acquire(output_root=tmp_path,transport=transport,clock=clock)
 assert acquire(output_root=tmp_path,transport=transport,clock=clock)==first
 path=tmp_path/first["records"][0]["relative_path"];path.write_bytes(b"tampered")
 with pytest.raises(FuturesMicroOfficialDocsError,match="conflict"):acquire(output_root=tmp_path,transport=transport,clock=clock)

def test_request_and_output_boundaries_fail_closed(tmp_path):
 with pytest.raises(FuturesMicroOfficialDocsError):https_get("https://example.com")
 with pytest.raises(FuturesMicroOfficialDocsError):acquire(output_root=tmp_path/"missing",transport=lambda u:b"x")
 bad=lambda tz:datetime(2026,9,6)
 with pytest.raises(FuturesMicroOfficialDocsError,match="clock"):acquire(output_root=tmp_path,transport=lambda u:b"x",clock=bad)

def test_redirects_cannot_escape_official_host_or_original_path():
 handler=_OfficialRedirect()
 request=__import__("urllib.request").request.Request(SOURCES["commissions"])
 with pytest.raises(FuturesMicroOfficialDocsError,match="redirect"):
  handler.redirect_request(request,None,302,"",{},"https://evil.example/en/pricing/commissions-futures.php")
 with pytest.raises(FuturesMicroOfficialDocsError,match="redirect"):
  handler.redirect_request(request,None,302,"",{},"https://www.interactivebrokers.com/en/accounts/fees/CME.php")
