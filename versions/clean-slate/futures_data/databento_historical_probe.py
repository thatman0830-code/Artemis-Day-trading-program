"""Bounded, sanitized Databento historical connectivity probe."""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable


ENDPOINT = "https://hist.databento.com/v0/timeseries.get_range"
DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1m"
SYMBOLS = ("MES.v.0", "MNQ.v.0")
MAX_RESPONSE_BYTES = 256_000
TIMEOUT_SECONDS = 20


class ProbeError(RuntimeError):
    pass


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _default_open(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        return response.status, payload


def run_probe(*, key: str, start: datetime, output: Path,
              opener: Callable = _default_open) -> dict:
    if not isinstance(key, str) or len(key.strip()) != 32 or not key.startswith("db-"):
        raise ProbeError("credential format rejected")
    if start.tzinfo is None or start.second or start.microsecond:
        raise ProbeError("start must be an aligned timezone-aware minute")
    start = start.astimezone(timezone.utc)
    end = start + timedelta(minutes=5)
    query = urllib.parse.urlencode({
        "dataset": DATASET, "schema": SCHEMA, "symbols": ",".join(SYMBOLS),
        "stype_in": "continuous", "stype_out": "instrument_id",
        "start": _iso(start), "end": _iso(end), "encoding": "json", "limit": "20",
    })
    request = urllib.request.Request(f"{ENDPOINT}?{query}")
    token = base64.b64encode(f"{key}:".encode("ascii")).decode("ascii")
    request.add_header("Authorization", f"Basic {token}")
    try:
        status, payload = opener(request, TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        category = "AUTH_OR_ENTITLEMENT" if exc.code in {401, 402, 403} else "PROVIDER_HTTP"
        raise ProbeError(f"{category}: HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProbeError("NETWORK_OR_TIMEOUT") from None
    finally:
        request.headers.pop("Authorization", None)
        token = ""
    if status != 200:
        raise ProbeError(f"PROVIDER_HTTP: HTTP {status}")
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ProbeError("response cap exceeded")
    lines = [line for line in payload.splitlines() if line.strip()]
    if not lines:
        raise ProbeError("NO_DATA")
    try:
        records = [json.loads(line) for line in lines]
    except json.JSONDecodeError:
        raise ProbeError("provider schema rejected") from None
    bars = [row for row in records if isinstance(row, dict)
            and isinstance(row.get("hd"), dict)
            and "instrument_id" in row["hd"] and "ts_event" in row["hd"]]
    try:
        instruments = sorted({int(row["hd"]["instrument_id"]) for row in bars})
        timestamps = sorted({str(row["hd"]["ts_event"]) for row in bars})
    except (TypeError, ValueError):
        raise ProbeError("provider schema rejected") from None
    if not instruments or not timestamps or len(bars) > 20:
        raise ProbeError("provider schema rejected")
    report = {
        "dataset": DATASET, "end_utc": _iso(end), "http_status": status,
        "instrument_count": len(instruments), "maximum_records": 20,
        "order_endpoints_present": False, "paper_only": True,
        "record_count": len(bars), "request_count": 1, "schema": SCHEMA,
        "source": "databento-historical", "start_utc": _iso(start),
        "state": "HISTORICAL_CONNECTIVITY_PROBE_PASSED", "symbols": list(SYMBOLS),
        "trading_authority": False,
    }
    report["report_sha256"] = sha256(_canonical(report)).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(_canonical(report) + b"\n")
    temporary.replace(output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        key = sys.stdin.readline().strip()
        start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
        report = run_probe(key=key, start=start, output=args.output.resolve())
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0
    except ProbeError as exc:
        print(f"DATABENTO_HISTORICAL_PROBE_FAILED_SANITIZED:{exc}", file=sys.stderr)
        return 1
    except ValueError:
        print("DATABENTO_HISTORICAL_PROBE_FAILED_SANITIZED:INPUT", file=sys.stderr)
        return 1
    finally:
        key = ""


if __name__ == "__main__":
    raise SystemExit(main())
