from datetime import datetime,timezone
from decimal import Decimal
import json
import pytest
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from execution.futures_micro_paper_scope_v1 import VerifiedMicroContractV1
from execution.futures_micro_margin_evidence_v1 import *

C=VerifiedMicroContractV1(FuturesCanonicalMarket.NQ,"MNQU6","202609",793356225)
NOW=datetime(2026,9,7,tzinfo=timezone.utc)
def retain(tmp_path):
 image=tmp_path/"long.png";image.write_bytes(b"long screenshot bytes");short=tmp_path/"short.png";short.write_bytes(b"short screenshot bytes")
 root=tmp_path/"evidence"
 receipt=retain_margin_preview(evidence_root=root,long_screenshot_path=image,short_screenshot_path=short,contract=C,long_captured_at=NOW,short_captured_at=NOW,
  long_initial_margin_usd="3000",short_initial_margin_usd="3200",long_maintenance_margin_usd="2700",short_maintenance_margin_usd="2900")
 return root,receipt
def test_retains_content_addressed_sanitized_evidence(tmp_path):
 root,receipt=retain(tmp_path);doc=json.loads(receipt.read_text());loaded=read_margin_preview(evidence_root=root,receipt_path=receipt)
 assert loaded.contract==C and loaded.quantity==1 and loaded.transmitted is False
 assert doc["trading_authority"]is False and doc["paper_only"]is True
 assert "account"not in receipt.read_text().lower()
 assert (root/doc["long_screenshot_relative_path"]).read_bytes()==b"long screenshot bytes"
 assert (root/doc["short_screenshot_relative_path"]).read_bytes()==b"short screenshot bytes"
def test_tampered_screenshot_or_receipt_rejects(tmp_path):
 root,receipt=retain(tmp_path);doc=json.loads(receipt.read_text());(root/doc["short_screenshot_relative_path"]).write_bytes(b"tampered")
 with pytest.raises(FuturesMicroMarginEvidenceError):read_margin_preview(evidence_root=root,receipt_path=receipt)
 root,receipt=retain(tmp_path);doc=json.loads(receipt.read_text());doc["quantity"]=2;receipt.write_text(json.dumps(doc))
 with pytest.raises(FuturesMicroMarginEvidenceError):read_margin_preview(evidence_root=root,receipt_path=receipt)
def test_path_escape_and_invalid_values_reject(tmp_path):
 root,receipt=retain(tmp_path)
 with pytest.raises(FuturesMicroMarginEvidenceError):read_margin_preview(evidence_root=root,receipt_path=tmp_path/"outside.json")
 image=tmp_path/"preview2.png";image.write_bytes(b"x")
 with pytest.raises(FuturesMicroMarginEvidenceError):retain_margin_preview(evidence_root=root,long_screenshot_path=image,short_screenshot_path=image,contract=C,long_captured_at=NOW,short_captured_at=NOW,
  long_initial_margin_usd="0",short_initial_margin_usd="1",long_maintenance_margin_usd="1",short_maintenance_margin_usd="1")
