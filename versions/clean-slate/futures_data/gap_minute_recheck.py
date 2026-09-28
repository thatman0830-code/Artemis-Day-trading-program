"""Capped read-only recheck of one ES/NQ aggregate minute."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from futures_data.pass_b_backfill import MAX_RESPONSE_BYTES, PassBError, _fetch

VERSION = "ES_NQ_GAP_MINUTE_RECHECK_V1"


class GapMinuteRecheckError(RuntimeError): pass


def recheck(ticker: str, minute: datetime, key: str, fetch=_fetch) -> tuple[dict, bytes]:
    if ticker not in ("ESU6", "NQU6") or not key:
        raise GapMinuteRecheckError("approved ticker or credential missing")
    if minute.tzinfo is None or minute.astimezone(timezone.utc).second or minute.microsecond:
        raise GapMinuteRecheckError("minute must be aligned UTC")
    start = minute.astimezone(timezone.utc)
    request = {"ticker": ticker, "start_utc": start.isoformat().replace("+00:00", "Z"),
               "end_utc": (start + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")}
    status, raw, request_id = fetch(request, key)
    if status != 200 or len(raw) > MAX_RESPONSE_BYTES:
        raise GapMinuteRecheckError("provider response rejected")
    try: payload = json.loads(raw)
    except json.JSONDecodeError as exc: raise GapMinuteRecheckError("provider JSON malformed") from exc
    results = payload.get("results")
    target = int(start.timestamp() * 1_000_000_000)
    if payload.get("status") != "OK" or not isinstance(results, list) or payload.get("next_url"):
        raise GapMinuteRecheckError("provider response incomplete")
    if len(results) > 1 or any(row.get("window_start") != target for row in results):
        raise GapMinuteRecheckError("provider minute boundary violated")
    evidence = {"schema_version": VERSION, "ticker": ticker, "minute_utc": request["start_utc"],
                "http_status": status, "provider_request_id": request_id,
                "result_count": len(results), "raw_sha256": sha256(raw).hexdigest(),
                "classification": "AGGREGATE_PRESENT" if results else "PROVIDER_CONFIRMED_NO_AGGREGATE_ON_RECHECK",
                "archive_modified": False, "request_count": 1, "automatic_retry": False,
                "trading_authority": False}
    return evidence, raw


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".partial")
    if path.exists() or temporary.exists(): raise GapMinuteRecheckError("evidence collision")
    with temporary.open("xb") as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--repository",type=Path,required=True)
    parser.add_argument("--ticker",required=True); parser.add_argument("--minute",required=True)
    args=parser.parse_args(argv); key=sys.stdin.readline().rstrip("\r\n")
    try:
        minute=datetime.fromisoformat(args.minute.replace("Z","+00:00")); evidence,raw=recheck(args.ticker,minute,key)
        root=args.repository.resolve()/"outputs/es_nq_gap_rechecks"
        stem=minute.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+args.ticker+"-"+evidence["raw_sha256"][:12]
        _write_new(root/(stem+".raw.json"),raw)
        _write_new(root/(stem+".evidence.json"),(json.dumps(evidence,sort_keys=True,separators=(",",":"))+"\n").encode())
        print(json.dumps(evidence,sort_keys=True,separators=(",",":"))); return 0
    except (GapMinuteRecheckError,PassBError,ValueError) as exc:
        print(f"BLOCKED: ES/NQ minute recheck failed closed ({type(exc).__name__})",file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
