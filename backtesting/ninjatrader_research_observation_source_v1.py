"""Verify hash-chained NinjaTrader observations for isolated ES/NQ research."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import hashlib, json

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
VERSION = "ninjatrader-research-observation-source-v1"
RECORD_VERSION = "ninjatrader-observation-recorder-v1"
_INSTRUMENT = {FuturesCanonicalMarket.ES: "MES SEP26", FuturesCanonicalMarket.NQ: "MNQ SEP26"}

def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()

@dataclass(frozen=True)
class FuturesResearchObservationV1:
    captured_at: datetime
    bid: Decimal
    ask: Decimal
    last: Decimal
    last_volume: int
    source_sequence: int
    record_sha256: str

@dataclass(frozen=True)
class FuturesResearchObservationBatchV1:
    market: FuturesCanonicalMarket
    instrument: str
    observations: tuple[FuturesResearchObservationV1, ...]
    chain_head_sha256: str
    maximum_observation_gap_seconds: Decimal
    complete_market_bars: bool = False
    backtest_eligible: bool = False
    signal_eligible: bool = False
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION

def _utc(value):
    result=datetime.fromisoformat(value.replace("Z","+00:00"))
    if result.tzinfo is None or result.utcoffset()!=timedelta(0): raise ValueError("UTC timestamp required")
    return result

def read_futures_research_observations(archive_root, *, market, day, as_of):
    if not isinstance(market,FuturesCanonicalMarket): raise TypeError("explicit ES or NQ market required")
    if not isinstance(day,str) or len(day)!=10: raise ValueError("ISO day required")
    if not isinstance(as_of,datetime) or as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0): raise ValueError("UTC as_of required")
    root=Path(archive_root)/market.value; chain=root/(day+".jsonl"); manifest=root/"manifest.json"
    if not chain.is_file() or chain.is_symlink() or not manifest.is_file() or manifest.is_symlink(): raise ValueError("plain archive evidence required")
    metadata=json.loads(manifest.read_bytes()); expected_instrument=_INSTRUMENT[market]
    required={"archive_file","head_record_sha256","instrument","last_captured_at_utc","last_source_sequence","market","record_count","schema_version","state","trading_authority"}
    if (set(metadata)!=required or metadata["archive_file"]!=chain.name or metadata["instrument"]!=expected_instrument
        or metadata["market"]!=market.value or metadata["schema_version"]!=RECORD_VERSION or metadata["state"]!="RECORDING"
        or metadata["trading_authority"] is not False): raise ValueError("manifest identity or authority invalid")
    previous="0"*64; observations=[]; prior_time=None; maximum=Decimal("0")
    for raw in chain.read_bytes().splitlines():
        doc=json.loads(raw); digest=doc.pop("record_sha256")
        if (doc.get("schema_version")!=RECORD_VERSION or doc.get("previous_record_sha256")!=previous
            or hashlib.sha256(_canonical(doc)).hexdigest()!=digest or doc.get("market")!=market.value
            or doc.get("instrument")!=expected_instrument or doc.get("paper_only") is not True
            or doc.get("trading_authority") is not False): raise ValueError("observation chain invalid")
        captured=_utc(doc["captured_at_utc"])
        if captured>as_of or (prior_time is not None and captured<=prior_time): raise ValueError("observation chronology invalid")
        if prior_time is not None: maximum=max(maximum,Decimal(str((captured-prior_time).total_seconds())))
        values=tuple(Decimal(doc[key]) for key in ("bid","ask","last"))
        if any(not x.is_finite() or x<=0 for x in values) or values[1]<values[0]: raise ValueError("observation prices invalid")
        if type(doc.get("last_volume")) is not int or doc["last_volume"]<0 or type(doc.get("source_sequence")) is not int: raise ValueError("observation quantities invalid")
        observations.append(FuturesResearchObservationV1(captured,*values,doc["last_volume"],doc["source_sequence"],digest))
        previous=digest;prior_time=captured
    if not observations or metadata["record_count"]!=len(observations) or metadata["head_record_sha256"]!=previous or metadata["last_source_sequence"]!=observations[-1].source_sequence: raise ValueError("manifest and chain differ")
    return FuturesResearchObservationBatchV1(market,expected_instrument,tuple(observations),previous,maximum)
