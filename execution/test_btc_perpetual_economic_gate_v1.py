from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2.contracts import InstrumentSpecificationV2
from backtesting.execution_accounting_v2.specifications import (
    EvidenceRecord, InstrumentProfile, SpecificationRecord, SpecificationRepository,
    SpecificationType,
)
from execution.btc_perpetual_economic_gate_v1 import (
    BTCPerpetualEconomicGateError, REQUIRED_TYPES, evaluate_btc_perpetual_economics,
)
from execution.hyperliquid_perpetual_precision_v1 import HyperliquidBTCPerpetualPrecisionV1


T = datetime(2026, 9, 3, tzinfo=timezone.utc)


def build(root, *, approved=True, at=T):
    evidence=[]; specs=[]
    for index, kind in enumerate(REQUIRED_TYPES):
        payload=(kind.value+"\n").encode(); name=f"evidence/{kind.value}.txt"
        path=root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(payload)
        eid=hashlib.sha256(("evidence"+kind.value).encode()).hexdigest()
        evidence.append(EvidenceRecord(eid,"Hyperliquid","official-"+kind.value,
            "https://hyperliquid.gitbook.io/hyperliquid-docs",name,hashlib.sha256(payload).hexdigest(),
            at,at,None,"BTC-PERP","BTC",(kind.value,),()))
        values=(("value","verified"),)
        sid=hashlib.sha256(("spec"+kind.value).encode()).hexdigest()
        if kind is SpecificationType.INSTRUMENT:
            values=(("contract_id","BTC-PERP"),("contract_multiplier","1"),("currency","USDC"),
                ("profile","BTC_LINEAR_PERPETUAL"),("quantity_step","0.00001"),("tick_size","1"))
        specs.append(SpecificationRecord(sid,"economic-specification-v2-1",kind,
            "BTC-PERP","BTC",at,None,values,(eid,),approved,False))
    repo=SpecificationRepository(tuple(evidence),tuple(specs))
    first=specs[0]
    instrument=InstrumentSpecificationV2("instrument-spec-v2-1",first.specification_id,
        "BTC-PERP","BTC","BTC-PERP",InstrumentProfile.BTC_LINEAR_PERPETUAL,"USDC",
        Decimal("1"),Decimal("0.00001"),Decimal("1"),None,at,None,first.evidence_ids)
    precision=HyperliquidBTCPerpetualPrecisionV1.create(size_decimals=5,
        source_evidence_ids=(evidence[0].evidence_id,))
    return repo,instrument,precision


def test_complete_approved_checksum_verified_bundle_passes_advisory_only(tmp_path):
    repo,instrument,precision=build(tmp_path)
    result=evaluate_btc_perpetual_economics(repository=repo,repository_root=tmp_path,
        instrument=instrument,precision=precision,as_of=T)
    assert result.eligibility.eligible and len(result.specification_ids)==9
    assert result.advisory_only is True
    assert result.live_trading_permitted is result.trading_authority is False
    assert result==evaluate_btc_perpetual_economics(repository=repo,repository_root=tmp_path,
        instrument=instrument,precision=precision,as_of=T)


def test_missing_unapproved_tampered_and_conflicting_instrument_fail_closed(tmp_path):
    repo,instrument,precision=build(tmp_path)
    with pytest.raises(BTCPerpetualEconomicGateError,match="eligibility"):
        evaluate_btc_perpetual_economics(repository=SpecificationRepository(repo.evidence,repo.specifications[:-1]),
            repository_root=tmp_path,instrument=instrument,precision=precision,as_of=T)
    unapproved=tuple(replace(item,owner_approved=False) for item in repo.specifications)
    with pytest.raises(BTCPerpetualEconomicGateError,match="eligibility"):
        evaluate_btc_perpetual_economics(repository=SpecificationRepository(repo.evidence,unapproved),
            repository_root=tmp_path,instrument=instrument,precision=precision,as_of=T)
    (tmp_path/repo.evidence[0].local_snapshot_path).write_text("tampered")
    with pytest.raises(BTCPerpetualEconomicGateError,match="provenance"):
        evaluate_btc_perpetual_economics(repository=repo,repository_root=tmp_path,
            instrument=instrument,precision=precision,as_of=T)
    repo,instrument,precision=build(tmp_path)
    with pytest.raises(BTCPerpetualEconomicGateError,match="quantity step"):
        evaluate_btc_perpetual_economics(repository=repo,repository_root=tmp_path,
            instrument=replace(instrument,quantity_step=Decimal("0.001")),precision=precision,as_of=T)
