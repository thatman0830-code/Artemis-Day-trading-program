"""Append verified NinjaTrader MES/MNQ observations to restart-safe hash chains."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import argparse, hashlib, json, os, time

from execution.ninjatrader_quote_bridge_v1 import NinjaTraderQuoteBridgeError, read_quote_snapshot

VERSION = "ninjatrader-observation-recorder-v1"

def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def _atomic(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_canonical(value) + b"\n")
    os.replace(temporary, path)

def _load_chain(path: Path):
    previous = "0" * 64
    last_sequence = 0
    count = 0
    if not path.exists(): return previous, last_sequence, count
    for raw in path.read_bytes().splitlines():
        doc = json.loads(raw)
        digest = doc.pop("record_sha256")
        if doc.get("schema_version") != VERSION or doc.get("previous_record_sha256") != previous:
            raise ValueError("observation chain continuity failed")
        if hashlib.sha256(_canonical(doc)).hexdigest() != digest:
            raise ValueError("observation chain hash failed")
        if type(doc.get("source_sequence")) is not int or doc["source_sequence"] <= last_sequence:
            raise ValueError("source sequence regressed")
        previous, last_sequence, count = digest, doc["source_sequence"], count + 1
    return previous, last_sequence, count

def record_one(*, quote_path: Path, archive_root: Path, as_of: datetime):
    snapshot = read_quote_snapshot(path=quote_path, as_of=as_of)
    lane = snapshot.market.value
    day = snapshot.captured_at.date().isoformat()
    chain = archive_root / lane / (day + ".jsonl")
    chain.parent.mkdir(parents=True, exist_ok=True)
    previous, last_sequence, count = _load_chain(chain)
    if snapshot.sequence == last_sequence: return False
    if snapshot.sequence < last_sequence: raise ValueError("source sequence regressed")
    body = {
        "ask": str(snapshot.ask), "bid": str(snapshot.bid),
        "captured_at_utc": snapshot.captured_at.isoformat(), "instrument": snapshot.instrument,
        "last": str(snapshot.last), "last_volume": snapshot.last_volume,
        "market": lane, "paper_only": True, "previous_record_sha256": previous,
        "recorded_at_utc": as_of.isoformat(), "schema_version": VERSION,
        "source": snapshot.source, "source_sequence": snapshot.sequence,
        "source_sequence_delta": snapshot.sequence - last_sequence if last_sequence else None,
        "trading_authority": False,
    }
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    with chain.open("ab") as stream:
        stream.write(_canonical({**body, "record_sha256": digest}) + b"\n")
        stream.flush(); os.fsync(stream.fileno())
    _atomic(archive_root / lane / "manifest.json", {
        "archive_file": chain.name, "head_record_sha256": digest, "instrument": snapshot.instrument,
        "last_captured_at_utc": snapshot.captured_at.isoformat(), "last_source_sequence": snapshot.sequence,
        "market": lane, "record_count": count + 1, "schema_version": VERSION,
        "state": "RECORDING", "trading_authority": False,
    })
    return True

def record_cycle(*, quote_root: Path, archive_root: Path, as_of: datetime):
    result = {}
    for root in ("MES", "MNQ"):
        try:
            result[root] = record_one(quote_path=quote_root/(root+".quote.json"),
                                      archive_root=archive_root, as_of=as_of)
        except (NinjaTraderQuoteBridgeError, FileNotFoundError):
            # Provider disconnection is an expected fail-closed state. Keep the
            # supervisor alive, write nothing, and resume only on fresh evidence.
            result[root] = None
    return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--quote-root",type=Path,required=True)
    parser.add_argument("--archive-root",type=Path,required=True); parser.add_argument("--interval",type=float,default=1.0)
    args=parser.parse_args()
    while True:
        record_cycle(quote_root=args.quote_root,archive_root=args.archive_root,as_of=datetime.now(timezone.utc))
        time.sleep(args.interval)

if __name__ == "__main__": main()
