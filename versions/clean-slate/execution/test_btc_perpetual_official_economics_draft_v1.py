from datetime import datetime,timezone
import json,pytest
from execution.btc_perpetual_official_docs_v1 import acquire
from execution.btc_perpetual_official_economics_draft_v1 import *
T=datetime(2026,9,4,tzinfo=timezone.utc)
CONTENT={"fees":b"<p>0.045% 0.015% rolling 14 day volume</p>","funding":b"<p>paid every hour 4%/hour position_size * oracle_price * funding_rate</p>","contract_specifications":b"<p>Linear perpetual 1 unit of underlying spot asset 20000 USDC</p>"}
def setup(root):
 manifest=acquire(output_root=root,transport=lambda url:CONTENT[next(k for k,v in SOURCES.items()if v==url)],clock=lambda zone:T)
 return root/f"{manifest['evidence_id']}.json"
def test_exact_retained_sources_compile_unapproved(tmp_path):
 path=setup(tmp_path);result=compile_draft(evidence_root=tmp_path,evidence_path=path)
 assert result["facts"]["base_perpetual_taker_fee_bps"]=="4.5"
 assert result["owner_approved"]is result["paper_use_permitted"]is result["trading_authority"]is False
def test_tamper_and_missing_statement_reject(tmp_path):
 path=setup(tmp_path);doc=json.loads(path.read_bytes());raw=tmp_path/doc["records"][0]["relative_path"];raw.write_bytes(b"changed")
 with pytest.raises(BTCEconomicsDraftError,match="binding"):compile_draft(evidence_root=tmp_path,evidence_path=path)
