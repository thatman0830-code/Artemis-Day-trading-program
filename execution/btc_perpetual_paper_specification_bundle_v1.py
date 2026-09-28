"""Explicit owner-approved BTC paper economics, never live specifications."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib,json,os
from pathlib import Path
import uuid

from backtesting.execution_accounting_v2.contracts import InstrumentSpecificationV2
from backtesting.execution_accounting_v2.specifications import (
    Capability,EligibilityReport,InstrumentProfile,canonical_fingerprint,
)
from execution.btc_perpetual_paper_economics_policy_v1 import read_policy
from execution.btc_perpetual_paper_risk_policy_v1 import read_risk_policy
from execution.btc_perpetual_public_evidence_collector_v1 import (
    read_btc_perpetual_public_evidence,
)
from execution.hyperliquid_perpetual_precision_v1 import HyperliquidBTCPerpetualPrecisionV1

SCHEMA="btc-perpetual-supervised-paper-specification-bundle-v1"
MAXIMUM_BYTES=65536
KINDS=("INSTRUMENT","MARK_PRICE","ORACLE_PRICE","FUNDING","MARGIN_TIER",
    "FEE_TIER","SLIPPAGE","PARTICIPATION","RISK_LIMITS")


class BTCPerpetualPaperSpecificationError(ValueError):pass


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _id(*values):return canonical_fingerprint(SCHEMA,*values)


@dataclass(frozen=True,slots=True)
class BTCPerpetualPaperEconomicEligibilityV1:
    gate_id: str
    eligibility: EligibilityReport
    instrument: InstrumentSpecificationV2
    precision: HyperliquidBTCPerpetualPrecisionV1
    specification_ids: tuple[str,...]
    evidence_ids: tuple[str,...]
    paper_use_permitted: bool=True
    live_trading_permitted: bool=False
    trading_authority: bool=False

    @property
    def precision_id(self):return self.precision.precision_id

    def __post_init__(self):
        expected=_id(self.eligibility,self.instrument,self.precision,self.specification_ids,
            self.evidence_ids,True,False,False)
        if (not self.eligibility.eligible
                or self.eligibility.capability is not Capability.SUPERVISED_PAPER_ECONOMICS
                or self.paper_use_permitted is not True or self.live_trading_permitted is not False
                or self.trading_authority is not False or self.gate_id!=expected):
            raise BTCPerpetualPaperSpecificationError("paper economic gate is invalid")


def compile_paper_specification_bundle(*,economics_policy_path,risk_policy_path,
        public_evidence_root,public_evidence_receipt_path,as_of,output_path=None):
    economics=read_policy(economics_policy_path);risk=read_risk_policy(risk_policy_path)
    public=read_btc_perpetual_public_evidence(output_root=public_evidence_root,
        receipt_path=public_evidence_receipt_path)
    approved=read_btc_perpetual_public_evidence(output_root=public_evidence_root,
        receipt_path=Path(public_evidence_root)/(risk["source_ids"][1]+".receipt.json"))
    immutable=lambda item:(item.asset_index,item.size_decimals,item.maximum_leverage,item.margin_table_id)
    if (risk["source_ids"][0]!=economics["policy_id"]
            or immutable(approved)!=immutable(public)
            or public.captured_at>as_of or (as_of-public.captured_at).total_seconds()>60):
        raise BTCPerpetualPaperSpecificationError("paper policy lineage or freshness is invalid")
    evidence_ids=tuple(dict.fromkeys((economics["policy_id"],risk["policy_id"],
        approved.receipt_id,public.receipt_id)))
    specification_ids=tuple(_id("specification",kind,*evidence_ids)for kind in KINDS)
    instrument=InstrumentSpecificationV2("instrument-spec-v2-1",specification_ids[0],
        "BTC-PERP","BTC","BTC-PERP",InstrumentProfile.BTC_LINEAR_PERPETUAL,"USDC",
        Decimal(risk["values"]["price_increment_usd"]),Decimal(1).scaleb(-public.size_decimals),
        Decimal("1"),None,approved.captured_at,None,
        tuple(dict.fromkeys((approved.receipt_id,public.receipt_id))))
    precision=HyperliquidBTCPerpetualPrecisionV1.create(size_decimals=public.size_decimals,
        source_evidence_ids=tuple(dict.fromkeys((approved.receipt_id,public.receipt_id))))
    fingerprint=_id("economic-fingerprint",specification_ids,evidence_ids,as_of)
    report_id=_id("eligibility",fingerprint)
    report=EligibilityReport(report_id,InstrumentProfile.BTC_LINEAR_PERPETUAL,
        Capability.SUPERVISED_PAPER_ECONOMICS,as_of,True,(),specification_ids,fingerprint)
    gate_id=_id(report,instrument,precision,specification_ids,evidence_ids,True,False,False)
    gate=BTCPerpetualPaperEconomicEligibilityV1(gate_id,report,instrument,precision,
        specification_ids,evidence_ids,True,False,False)
    body={"schema_version":SCHEMA,"scope":"SUPERVISED_PAPER_ONLY","market":"BTC-PERP",
        "as_of":as_of.isoformat(),"economics_policy_id":economics["policy_id"],
        "risk_policy_id":risk["policy_id"],"public_evidence_id":public.receipt_id,
        "approved_public_evidence_id":approved.receipt_id,
        "instrument_specification_id":instrument.specification_id,
        "precision_id":precision.precision_id,"specification_ids":list(specification_ids),
        "gate_id":gate.gate_id,"paper_use_permitted":True,"live_trading_permitted":False,
        "trading_authority":False}
    document={**body,"bundle_id":hashlib.sha256(_canonical(body)).hexdigest()}
    if output_path is not None:
        path=Path(output_path);path.parent.mkdir(parents=True,exist_ok=True)
        if path.is_symlink()or path.parent.is_symlink():raise BTCPerpetualPaperSpecificationError("bundle path is unsafe")
        temporary=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary,"xb")as stream:
                stream.write(_canonical(document)+b"\n");stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path)
        finally:temporary.unlink(missing_ok=True)
    return gate,document


def read_paper_specification_bundle(path,**sources):
    path=Path(path)
    if path.is_symlink()or not path.is_file()or not 0<path.stat().st_size<=MAXIMUM_BYTES:
        raise BTCPerpetualPaperSpecificationError("paper bundle is missing or unsafe")
    try:document=json.loads(path.read_bytes())
    except (OSError,UnicodeError,json.JSONDecodeError)as exc:
        raise BTCPerpetualPaperSpecificationError("paper bundle is unreadable")from exc
    required={"schema_version","scope","market","as_of","economics_policy_id","risk_policy_id",
        "public_evidence_id","approved_public_evidence_id","instrument_specification_id","precision_id","specification_ids",
        "gate_id","paper_use_permitted","live_trading_permitted","trading_authority","bundle_id"}
    body={key:document[key]for key in document if key!="bundle_id"}
    if (set(document)!=required or document["schema_version"]!=SCHEMA
            or document["scope"]!="SUPERVISED_PAPER_ONLY"or document["market"]!="BTC-PERP"
            or document["paper_use_permitted"]is not True
            or document["live_trading_permitted"]is not False or document["trading_authority"]is not False
            or hashlib.sha256(_canonical(body)).hexdigest()!=document["bundle_id"]):
        raise BTCPerpetualPaperSpecificationError("paper bundle identity or scope is invalid")
    try:as_of=datetime.fromisoformat(document["as_of"])
    except (TypeError,ValueError)as exc:raise BTCPerpetualPaperSpecificationError("paper bundle time is invalid")from exc
    gate,rebuilt=compile_paper_specification_bundle(as_of=as_of,output_path=None,**sources)
    if rebuilt!=document:raise BTCPerpetualPaperSpecificationError("paper bundle source reconstruction failed")
    return gate,document["bundle_id"]
