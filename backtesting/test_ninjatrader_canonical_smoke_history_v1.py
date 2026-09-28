from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import json
import pytest

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_history_v1 import (
    NinjaTraderCanonicalSmokeHistoryError, append_ninjatrader_canonical_smoke,
    read_ninjatrader_canonical_smoke_history,
)
from backtesting.ninjatrader_canonical_smoke_v1 import evaluate_ninjatrader_canonical_smoke
from backtesting.ninjatrader_closed_bar_dataset_v1 import read_closed_bar_dataset
from backtesting.test_ninjatrader_closed_bar_dataset_v1 import NOW,build

def report(root,market=FuturesCanonicalMarket.ES,offset=4):
    build(root,market);at=NOW+timedelta(minutes=offset)
    evidence=read_closed_bar_dataset(root,market=market,day="2026-09-08",as_of=at)
    return evaluate_ninjatrader_canonical_smoke(evidence=evidence,
        minimum_tick=Decimal("0.25"),instrument_specification_id=("a"if market is FuturesCanonicalMarket.ES else"b")*64,as_of=at)

def test_append_read_idempotence_and_market_isolation(tmp_path):
    es=report(tmp_path/"es");nq=report(tmp_path/"nq",FuturesCanonicalMarket.NQ)
    first=append_ninjatrader_canonical_smoke(tmp_path/"history",report=es)
    assert append_ninjatrader_canonical_smoke(tmp_path/"history",report=es)==first
    append_ninjatrader_canonical_smoke(tmp_path/"history",report=nq)
    assert len(read_ninjatrader_canonical_smoke_history(tmp_path/"history",market=FuturesCanonicalMarket.ES))==1
    assert len(read_ninjatrader_canonical_smoke_history(tmp_path/"history",market=FuturesCanonicalMarket.NQ))==1
    assert first.report["trading_authority"] is False

def test_tamper_and_authority_forgery_fail_closed(tmp_path):
    current=report(tmp_path/"source");root=tmp_path/"history"
    append_ninjatrader_canonical_smoke(root,report=current)
    path=root/"ES"/"events"/"00000000000000000000.json"
    value=json.loads(path.read_text());value["latest_outcome"]="CANDIDATE";path.write_text(json.dumps(value))
    with pytest.raises(NinjaTraderCanonicalSmokeHistoryError,match="binding"):
        read_ninjatrader_canonical_smoke_history(root,market=FuturesCanonicalMarket.ES)
    with pytest.raises(NinjaTraderCanonicalSmokeHistoryError,match="authoritative"):
        append_ninjatrader_canonical_smoke(tmp_path/"other",report=replace(current,trading_authority=True))

def test_sequence_chain_and_chronology(tmp_path):
    root=tmp_path/"history";first=report(tmp_path/"one")
    second=replace(first,evaluated_at=first.evaluated_at+timedelta(minutes=1),
        report_id="c"*64,dataset_fingerprint="d"*64,source_chain_head_sha256="e"*64)
    a=append_ninjatrader_canonical_smoke(root,report=first)
    b=append_ninjatrader_canonical_smoke(root,report=second)
    assert a.sequence==0 and a.previous_event_id is None
    assert b.sequence==1 and b.previous_event_id==a.event_id
    with pytest.raises(NinjaTraderCanonicalSmokeHistoryError,match="chronology"):
        append_ninjatrader_canonical_smoke(root,report=replace(first,report_id="f"*64,
            dataset_fingerprint="1"*64,source_chain_head_sha256="2"*64,
            evaluated_at=first.evaluated_at-timedelta(minutes=1)))

def test_unchanged_source_chain_does_not_grow_history(tmp_path):
    root=tmp_path/"history";first=report(tmp_path/"source")
    event=append_ninjatrader_canonical_smoke(root,report=first)
    repeated=replace(first,evaluated_at=first.evaluated_at+timedelta(minutes=5),report_id="e"*64)
    assert append_ninjatrader_canonical_smoke(root,report=repeated)==event
    assert len(read_ninjatrader_canonical_smoke_history(root,market=first.market))==1
