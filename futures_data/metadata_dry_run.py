from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .massive import parse_outright_ticker
from .planning import create_backfill_plan

BASE_URL = "https://api.massive.com"
ALLOWED_HOST = "api.massive.com"
ROOTS = ("ES", "NQ")
MAX_CALLS = 4
MIN_CALL_INTERVAL_SECONDS = 15.0


class MetadataDryRunError(RuntimeError):
    def __init__(self, message: str, *, category: str = "VALIDATION",
                 endpoint: str | None = None, http_status: int | None = None,
                 request_id: str | None = None, record_count: int | None = None,
                 offending_root: str | None = None, offending_type: str | None = None,
                 instrument_class: str | None = None):
        super().__init__(message)
        self.safe = {"lifecycle_stage":"METADATA_VALIDATION","http_status":http_status,
            "endpoint":endpoint,"provider_request_id":request_id,"returned_record_count":record_count,
            "rejection_category":category,"offending_root":offending_root,
            "offending_type":offending_type,"offending_instrument_class":instrument_class}


def _request(*, path: str, query: dict[str, str], key: str,
             opener: Callable[[urllib.request.Request, float], tuple[int, bytes]],
             timeout: float = 20.0) -> dict:
    if not path.startswith("/futures/v1/") or "aggs" in path or "trades" in path or "quotes" in path:
        raise MetadataDryRunError("only futures reference metadata endpoints are permitted")
    url = BASE_URL + path + "?" + urllib.parse.urlencode(query)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or "apikey" in parsed.query.lower():
        raise MetadataDryRunError("request destination or authentication boundary is invalid")
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key,
                                                   "Accept": "application/json"}, method="GET")
    status, raw = opener(request, timeout)
    endpoint = path.rsplit("/", 1)[-1]
    if status in (401, 403): raise MetadataDryRunError("Massive authentication or Futures entitlement rejected",category="AUTH_OR_ENTITLEMENT",endpoint=endpoint,http_status=status)
    if status == 429: raise MetadataDryRunError("Massive metadata rate limit reached; no automatic retry",category="RATE_LIMIT",endpoint=endpoint,http_status=status)
    if status != 200: raise MetadataDryRunError(f"Massive metadata request failed with HTTP {status}",category="HTTP_ERROR",endpoint=endpoint,http_status=status)
    try: payload = json.loads(raw.decode("utf-8"))
    except Exception as error: raise MetadataDryRunError("Massive returned malformed metadata JSON") from error
    request_id = payload.get("request_id") if isinstance(payload.get("request_id"), str) else None
    results = payload.get("results")
    if payload.get("status") != "OK" or not isinstance(results, list):
        raise MetadataDryRunError("Massive metadata response shape/status is invalid",category="MALFORMED_RESPONSE",endpoint=endpoint,http_status=status,request_id=request_id)
    if payload.get("next_url"):
        raise MetadataDryRunError("metadata result exceeded the bounded first page; pagination is not authorized",category="PAGINATION_REQUIRED",endpoint=endpoint,http_status=status,request_id=request_id,record_count=len(results))
    return payload


def default_opener(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.status, response.read(2_000_000)
    except urllib.error.HTTPError as error:
        return error.code, error.read(65536)


def credential_free_mock_opener(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    """Strict offline transport used only by the installed helper rehearsal."""
    parsed = urllib.parse.urlparse(request.full_url)
    query = urllib.parse.parse_qs(parsed.query)
    root = query.get("product_code", [""])[0]
    if root not in ROOTS or request.get_header("Authorization") != "Bearer synthetic-offline-only":
        return 403, b'{"status":"ERROR"}'
    if parsed.path == "/futures/v1/contracts":
        result = {"product_code":root,"ticker":root+"U2026","type":"single",
                  "first_trade_date":"2025-01-01","last_trade_date":"2026-09-18",
                  "settlement_date":"2026-09-18","trade_tick_size":"0.25","trading_venue":"XCME"}
    elif parsed.path == "/futures/v1/products":
        result = {"product_code":root,"name":root+" E-mini","type":"single","trading_venue":"XCME",
                  "unit_of_measure":"index points","unit_of_measure_qty":50 if root=="ES" else 20,
                  "settlement_currency_code":"USD"}
    else:
        return 404, b'{"status":"ERROR"}'
    return 200, json.dumps({"status":"OK","results":[result]}, separators=(",", ":")).encode()


def _validate_contracts(root: str, rows: list[dict]) -> tuple[dict, ...]:
    if not rows or len(rows) > 64: raise MetadataDryRunError(f"{root} contract count outside bounded expectation")
    clean = []
    for row in rows:
        returned_root, returned_type, venue = row.get("product_code"), row.get("type"), row.get("trading_venue")
        if returned_root != root or returned_type != "single" or venue != "XCME":
            category = "WRONG_ROOT" if returned_root != root else "WRONG_TYPE" if returned_type != "single" else "WRONG_VENUE"
            raise MetadataDryRunError(f"{root} response violates exact contract filters",category=category,
                endpoint="contracts",record_count=len(rows),offending_root=str(returned_root),
                offending_type=str(returned_type),instrument_class="CONTRACT")
        ticker = str(row.get("ticker", ""))
        required = ("first_trade_date", "last_trade_date", "settlement_date", "trade_tick_size", "trading_venue")
        if any(row.get(name) in (None, "") for name in required):
            raise MetadataDryRunError(f"{root} contract metadata is incomplete",category="MISSING_FIELD",endpoint="contracts",record_count=len(rows),offending_root=root,offending_type="single",instrument_class="CONTRACT")
        try:
            settlement = row.get("settlement_date")
            if not isinstance(settlement, str): raise ValueError("missing settlement date")
            year_hint = datetime.strptime(settlement, "%Y-%m-%d").year
            parsed_root, month, year = parse_outright_ticker(ticker, contract_year_hint=year_hint)
        except (TypeError, ValueError) as error:
            instrument = "MICRO" if ticker.startswith(("MES","MNQ")) else "OPTION_OR_SPREAD_OR_CONTINUOUS_OR_MALFORMED"
            raise MetadataDryRunError(f"{root} response contains a prohibited instrument",category="PROHIBITED_INSTRUMENT",
                endpoint="contracts",record_count=len(rows),offending_root=ticker[:3],
                offending_type=str(returned_type),instrument_class=instrument) from error
        if parsed_root.value != root: raise MetadataDryRunError("wrong-root instrument contamination")
        clean.append({"ticker":ticker,"root":root,"contract_month":month,"contract_year":year,
                      **{name:row[name] for name in required}})
    return tuple(sorted(clean, key=lambda x:(x["contract_year"],x["contract_month"],x["ticker"])))


def _validate_product(root: str, rows: list[dict]) -> dict:
    matches = [x for x in rows if x.get("product_code") == root and x.get("type") == "single"]
    if len(matches) != 1: raise MetadataDryRunError(f"{root} product metadata is missing or ambiguous",category="PRODUCT_AMBIGUOUS",endpoint="products",record_count=len(rows),offending_root=root,instrument_class="PRODUCT")
    item = matches[0]
    if item.get("trading_venue") not in {"XCME", "CME", "XCBT"}:
        raise MetadataDryRunError(f"{root} product has an unexpected trading venue",category="WRONG_VENUE",endpoint="products",record_count=len(rows),offending_root=root,offending_type="single",instrument_class="PRODUCT")
    return {k:item.get(k) for k in ("product_code","name","trading_venue","type","unit_of_measure","unit_of_measure_qty","settlement_currency_code")}


def run_metadata_dry_run(*, key: str, as_of: datetime, repository: Path,
                         opener=default_opener, sleep=time.sleep) -> dict:
    if not isinstance(key, str) or not key.strip(): raise MetadataDryRunError("credential was not supplied")
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0): raise MetadataDryRunError("as_of must be UTC")
    responses = {}; calls = 0
    for root in ROOTS:
        if calls: sleep(MIN_CALL_INTERVAL_SECONDS)
        responses[(root,"contracts")] = _request(path="/futures/v1/contracts",
            query={"product_code":root,"date":as_of.date().isoformat(),"active":"true","type":"single","limit":"1000","sort":"ticker.asc"},
            key=key, opener=opener); calls += 1
        sleep(MIN_CALL_INTERVAL_SECONDS)
        responses[(root,"product")] = _request(path="/futures/v1/products",
            query={"product_code":root,"date":as_of.date().isoformat(),"trading_venue":"XCME","type":"single","limit":"10"},
            key=key, opener=opener); calls += 1
    if calls != MAX_CALLS: raise AssertionError("metadata call budget mismatch")
    contracts={root:_validate_contracts(root,responses[(root,"contracts")]["results"]) for root in ROOTS}
    products={root:_validate_product(root,responses[(root,"product")]["results"]) for root in ROOTS}
    return {"status":"DRY_RUN_VALIDATED","provider":"massive-futures","as_of_utc":as_of.isoformat().replace("+00:00","Z"),
            "authentication":"Authorization Bearer header","aggregate_requests":0,"collector_started":False,
            "request_count":calls,"maximum_calls_per_minute":4,
            "contracts":contracts,"products":products,
            "archive_paths":{"ES":str(repository/"data/backtests/es_forward_archive_1"),
                             "NQ":str(repository/"data/backtests/nq_forward_archive_1")}}


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Bounded Massive ES/NQ metadata-only dry run")
    parser.add_argument("--repository",type=Path,required=True); parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--credential-free-mock", action="store_true", help=argparse.SUPPRESS)
    args=parser.parse_args(argv); key=sys.stdin.readline().rstrip("\r\n")
    try:
        opener = credential_free_mock_opener if args.credential_free_mock else default_opener
        sleeper = (lambda _seconds: None) if args.credential_free_mock else time.sleep
        report=run_metadata_dry_run(key=key,as_of=datetime.now(timezone.utc),repository=args.repository.resolve(),
                                    opener=opener, sleep=sleeper)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        temporary=args.output.with_suffix(args.output.suffix+".tmp")
        temporary.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        temporary.replace(args.output); args.output.with_suffix(".diagnostic.json").unlink(missing_ok=True)
        print("DRY_RUN_VALIDATED")
        return 0
    except Exception as error:
        diagnostic = getattr(error, "safe", {"lifecycle_stage":"METADATA_VALIDATION","http_status":None,
            "endpoint":None,"provider_request_id":None,"returned_record_count":None,
            "rejection_category":"UNCLASSIFIED","offending_root":None,"offending_type":None,
            "offending_instrument_class":None})
        diagnostic_path = args.output.with_suffix(".diagnostic.json")
        diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostic_path.write_text(json.dumps(diagnostic,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        print("BLOCKED: "+str(error),file=sys.stderr); return 1
    finally:
        key=""


if __name__ == "__main__": raise SystemExit(main())
