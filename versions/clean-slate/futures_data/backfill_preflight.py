from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from .aggregate_probe import (ALLOWED_HOST, BASE_URL, CHICAGO, MIN_CALL_INTERVAL_SECONDS,
                              SelectedContract, normalize_bars, session_bounds)
from .massive import parse_outright_ticker

SCHEMA_VERSION = "massive-es-nq-backfill-preflight-v1"
ROOTS = ("ES", "NQ")
VENUE = "XCME"
MAX_HISTORY_DAYS = 366 * 2
SESSIONS_PER_REQUEST = 5
MINUTES_PER_ORDINARY_SESSION = 23 * 60
MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_METADATA_PAGES_PER_ROOT = 4
PREFLIGHT_NAMES = {"ES": "es_backfill_preflight_1", "NQ": "nq_backfill_preflight_1"}
PROBE_NAMES = {"ES": "es_probe_staging_2", "NQ": "nq_probe_staging_2"}
SECRET_PATTERN = re.compile(r"(?i)(authorization\s*:|bearer\s+|api[_-]?key|massive_api_key)")


class PreflightError(RuntimeError):
    def __init__(self, message: str, *, category: str = "VALIDATION", root: str | None = None,
                 status: int | None = None, request_id: str | None = None,
                 content_type: str | None = None, response_bytes: int | None = None,
                 provider_code: str | None = None, provider_type: str | None = None,
                 provider_parameter: str | None = None, safe_message: str | None = None,
                 page_number: int | None = None, timeout_category: str | None = None,
                 exception_class: str | None = None, phase: str = "VALIDATION") -> None:
        super().__init__(message)
        self.safe = {"utc_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                     "lifecycle_stage": "BACKFILL_PREFLIGHT", "failure_phase": phase,
                     "rejection_category": category, "root": root,
                     "endpoint_class": "futures_contract_metadata", "http_status": status,
                     "provider_request_id": request_id, "response_content_type": content_type,
                     "response_byte_count": response_bytes, "provider_error_code": provider_code,
                     "provider_error_type": provider_type, "provider_error_parameter": provider_parameter,
                     "sanitized_error_message": safe_message, "pagination_page_number": page_number,
                     "timeout_category": timeout_category, "exception_class": exception_class,
                     "aggregate_requests": 0, "automatic_retry": False}


@dataclass(frozen=True)
class TransportResponse:
    status: int
    raw: bytes
    content_type: str | None = None
    request_id: str | None = None


def _bounded_text(value: object, limit: int = 200) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if re.search(r"(?i)authorization|bearer|api[_-]?key|token|secret", value):
        return "[REDACTED]"
    clean = re.sub(r"(?i)bearer\s+\S+", "[REDACTED]", value)
    clean = re.sub(r"https?://\S+", "[URL]", clean)
    if SECRET_PATTERN.search(clean):
        return "[REDACTED]"
    clean = re.sub(r"[A-Za-z0-9_-]{20,}", "[REDACTED]", clean)
    clean = " ".join(clean.split())
    return clean[:limit]


def _bounded_request_id(value: object) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
        return None
    return value


def _provider_error(raw: bytes) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return None, None, None, None, None
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        error = payload if isinstance(payload, dict) else {}
    return (_bounded_text(error.get("code"), 80), _bounded_text(error.get("type"), 80),
            _bounded_text(error.get("param") or error.get("parameter"), 80),
            _bounded_text(error.get("message")),
            _bounded_request_id(payload.get("request_id")) if isinstance(payload, dict) else None)


def _transport(value: object) -> TransportResponse:
    if isinstance(value, TransportResponse):
        return value
    if isinstance(value, tuple) and len(value) in (2, 3):
        status, raw = value[0], value[1]
        headers = value[2] if len(value) == 3 and isinstance(value[2], dict) else {}
        return TransportResponse(int(status), bytes(raw), _bounded_text(headers.get("Content-Type"), 128),
                                 _bounded_request_id(headers.get("X-Request-Id") or headers.get("Request-Id")))
    raise TypeError("transport returned an unsupported result")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, default=str) + "\n").encode("utf-8")


def _atomic_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    if path.exists() or temporary.exists():
        raise PreflightError("destination already exists", category="OUTPUT_EXISTS")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(temporary, path)


def validate_raw_probe(repository: Path) -> dict:
    """Recompute the immutable corrected-probe evidence without changing it."""
    summaries: dict[str, dict] = {}
    paths: set[Path] = set()
    for root in ROOTS:
        market = repository / "data" / "backtests" / PROBE_NAMES[root]
        if not market.is_dir() or market.resolve() in paths:
            raise PreflightError("probe market path missing or colliding", category="PROBE_PATH", root=root)
        paths.add(market.resolve())
        report = json.loads((market / "reports" / "validation.json").read_text(encoding="utf-8"))
        contract = json.loads((market / "normalized" / "contract.json").read_text(encoding="utf-8"))
        if report.get("status") != "VALIDATED_STAGING" or report.get("root") != root:
            raise PreflightError("probe report identity invalid", category="PROBE_IDENTITY", root=root)
        ticker = report.get("ticker")
        if contract.get("root") != root or contract.get("ticker") != ticker:
            raise PreflightError("probe contract lineage invalid", category="PROBE_IDENTITY", root=root)
        sessions = tuple(date.fromisoformat(x) for x in report.get("sessions", ()))
        if len(sessions) != 5 or len(set(sessions)) != 5 or tuple(sorted(sessions)) != sessions:
            raise PreflightError("probe session set invalid", category="PROBE_SESSIONS", root=root)
        manifests = sorted((market / "manifests").glob("*_request.json"))
        if len(manifests) != 3:
            raise PreflightError("probe request manifest set incomplete", category="PROBE_MANIFEST", root=root)
        aggregate_manifest = None
        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("raw_retained") is not True or manifest.get("ticker") != ticker:
                raise PreflightError("raw retention or identity assertion missing", category="PROBE_MANIFEST", root=root)
            raw_path = market / str(manifest.get("raw_relative_path", ""))
            if not raw_path.is_file():
                raise PreflightError("retained raw response missing", category="PROBE_RAW_MISSING", root=root)
            raw = raw_path.read_bytes()
            if len(raw) != manifest.get("response_byte_count") or sha256(raw).hexdigest() != manifest.get("raw_response_sha256"):
                raise PreflightError("retained raw checksum conflict", category="PROBE_RAW_CHECKSUM", root=root)
            if manifest.get("endpoint") == "aggregates":
                aggregate_manifest = manifest
        if aggregate_manifest is None:
            raise PreflightError("aggregate manifest missing", category="PROBE_MANIFEST", root=root)
        normalized_path = market / "normalized" / "bars.jsonl"
        normalized = normalized_path.read_bytes()
        if sha256(normalized).hexdigest() != aggregate_manifest.get("normalized_output_sha256"):
            raise PreflightError("normalized checksum conflict", category="PROBE_NORMALIZED_CHECKSUM", root=root)
        rows = [json.loads(line, parse_float=Decimal) for line in normalized.decode("utf-8").splitlines()]
        if len(rows) != aggregate_manifest.get("normalized_row_count") or len(rows) != report.get("row_count"):
            raise PreflightError("normalized row count conflict", category="PROBE_ROW_COUNT", root=root)
        identities = set()
        previous = None
        observed_sessions = set()
        for row in rows:
            if row.get("ticker") != ticker or row.get("root") != root:
                raise PreflightError("cross-contract normalized row", category="PROBE_CONTAMINATION", root=root)
            identity = (ticker, row.get("window_start_ns"))
            if identity in identities or not isinstance(identity[1], int) or (previous is not None and identity[1] <= previous):
                raise PreflightError("duplicate or unordered normalized row", category="PROBE_ORDERING", root=root)
            identities.add(identity)
            previous = identity[1]
            observed_sessions.add(date.fromisoformat(row["session_end_date"]))
        if observed_sessions != set(sessions) or report.get("gap_count") != 0:
            raise PreflightError("session coverage or gap classification invalid", category="PROBE_GAPS", root=root)
        raw_aggregate = json.loads((market / aggregate_manifest["raw_relative_path"]).read_text(encoding="utf-8"),
                                   parse_float=Decimal)
        selected = SelectedContract(root, ticker, date.fromisoformat(contract["first_trade_date"]),
                                    date.fromisoformat(contract["last_trade_date"]),
                                    date.fromisoformat(contract["settlement_date"]),
                                    Decimal(str(contract["tick_size"])), contract["venue"],
                                    str(aggregate_manifest.get("provider_request_id") or ""))
        regenerated, gaps = normalize_bars(selected, (raw_aggregate,), sessions)
        regenerated_bytes = ("\n".join(json.dumps(x, sort_keys=True, separators=(",", ":"))
                                        for x in regenerated) + "\n").encode("utf-8")
        if regenerated_bytes != normalized or gaps:
            raise PreflightError("raw-to-normalized reproduction conflict", category="PROBE_REPRODUCTION", root=root)
        earliest = datetime.fromisoformat(report["earliest"].replace("Z", "+00:00"))
        latest = datetime.fromisoformat(report["latest"].replace("Z", "+00:00"))
        expected_start, expected_end = session_bounds(sessions)
        if earliest != expected_start or latest + timedelta(minutes=1) != expected_end:
            raise PreflightError("probe session boundary conflict", category="PROBE_SESSIONS", root=root)
        summaries[root] = {"ticker": ticker, "sessions": [x.isoformat() for x in sessions],
                           "row_count": len(rows), "gap_count": 0,
                           "earliest_utc": earliest.isoformat().replace("+00:00", "Z"),
                           "latest_utc": latest.isoformat().replace("+00:00", "Z"),
                           "earliest_chicago": earliest.astimezone(CHICAGO).isoformat(),
                           "latest_chicago": latest.astimezone(CHICAGO).isoformat(),
                           "raw_manifest_count": len(manifests), "raw_retained": True}
    return {"status": "ES_NQ_RAW_PROBE_VALIDATED", "markets": summaries}


def _ticker_exclusion(ticker: object) -> dict:
    text = str(ticker or "")
    if text.startswith(("MES", "MNQ")):
        category = "MICRO"
    elif "-" in text:
        category = "SPREAD_OR_COMBO"
    elif any(mark in text for mark in ("!", "/", ":")):
        category = "CONTINUOUS_OR_SYNTHETIC"
    else:
        category = "OPTION_OR_NON_OUTRIGHT_OR_MALFORMED"
    pattern = re.sub(r"[A-Z]", "A", re.sub(r"\d", "9", text))
    return {"category": category, "sanitized_ticker_pattern": pattern, "ticker_length": len(text)}


def _classify_contract_rows(root: str, rows: list[dict], *, start: date,
                            end: date) -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    contracts = []
    exclusions = []
    seen: dict[str, tuple[object, ...]] = {}
    for row in rows:
        ticker = row.get("ticker")
        if row.get("product_code") != root or row.get("type") != "single" or row.get("trading_venue") != VENUE:
            raise PreflightError("provider returned a prohibited contract", category="CONTRACT_SCOPE", root=root)
        try:
            first = date.fromisoformat(row["first_trade_date"])
            last = date.fromisoformat(row["last_trade_date"])
            settlement = date.fromisoformat(row["settlement_date"])
        except Exception as error:
            raise PreflightError("contract lifecycle schema invalid", category="CONTRACT_SCHEMA", root=root) from error
        try:
            parsed_root, month, year = parse_outright_ticker(str(ticker), contract_year_hint=settlement.year)
        except ValueError:
            exclusions.append(_ticker_exclusion(ticker))
            continue
        lineage = (row.get("product_code"), row.get("type"), row.get("trading_venue"),
                   first, last, settlement, month, year)
        if ticker in seen:
            if seen[ticker] != lineage:
                raise PreflightError("duplicate ticker has conflicting metadata", category="CONTRACT_AMBIGUITY", root=root)
            continue
        if parsed_root.value != root or month not in (3, 6, 9, 12) or not first <= last <= settlement:
            raise PreflightError("contract is ambiguous or not an ordinary quarterly outright", category="CONTRACT_SCOPE", root=root)
        seen[str(ticker)] = lineage
        eligible_start = max(first, start)
        eligible_end = min(last + timedelta(days=1), end)
        if eligible_start < eligible_end:
            contracts.append({"ticker": ticker, "root": root, "type": "single", "venue": VENUE,
                              "first_trade_date": first.isoformat(), "last_trade_date": last.isoformat(),
                              "settlement_date": settlement.isoformat(), "contract_month": month,
                              "contract_year": year, "eligible_start": eligible_start.isoformat(),
                              "eligible_end_exclusive": eligible_end.isoformat()})
    if not contracts:
        raise PreflightError("no eligible contracts returned", category="NO_ELIGIBLE_CONTRACTS", root=root)
    contracts.sort(key=lambda x: (x["eligible_start"], x["ticker"]))
    exclusions.sort(key=lambda x: (x["category"], x["sanitized_ticker_pattern"], x["ticker_length"]))
    return tuple(contracts), tuple(exclusions)


def _validate_contract_rows(root: str, rows: list[dict], *, start: date, end: date) -> tuple[dict, ...]:
    return _classify_contract_rows(root, rows, start=start, end=end)[0]


def _ordinary_sessions(start: date, end: date) -> int:
    return sum(1 for offset in range((end - start).days)
               if (start + timedelta(days=offset)).weekday() < 5)


def build_inventory(root: str, contracts: tuple[dict, ...], *, raw_bytes_per_row: Decimal) -> dict:
    planned = []
    sessions = requests = rows = 0
    for contract in contracts:
        count = _ordinary_sessions(date.fromisoformat(contract["eligible_start"]),
                                   date.fromisoformat(contract["eligible_end_exclusive"]))
        contract_requests = (count + SESSIONS_PER_REQUEST - 1) // SESSIONS_PER_REQUEST
        contract_rows = count * MINUTES_PER_ORDINARY_SESSION
        sessions += count
        requests += contract_requests
        rows += contract_rows
        planned.append({**contract, "estimated_ordinary_sessions": count,
                        "estimated_aggregate_requests": contract_requests,
                        "estimated_rows": contract_rows})
    raw_bytes = int(Decimal(rows) * raw_bytes_per_row)
    normalized_bytes = rows * 225
    return {"root": root, "contracts": planned, "contract_count": len(planned),
            "estimated_sessions": sessions, "estimated_aggregate_requests": requests,
            "estimated_rows": rows, "estimated_raw_bytes": raw_bytes,
            "estimated_normalized_bytes": normalized_bytes,
            "estimated_duration_minutes_at_4_requests_per_minute": (requests + 3) // 4,
            "checkpoint_after_every_successful_request": True,
            "overwrite_verified_raw_files": False}


def default_opener(request: urllib.request.Request, timeout: float) -> TransportResponse:
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return TransportResponse(response.status, response.read(MAX_METADATA_BYTES + 1),
                                     response.headers.get("Content-Type"),
                                     response.headers.get("X-Request-Id") or response.headers.get("Request-Id"))
    except urllib.error.HTTPError as error:
        return TransportResponse(error.code, error.read(65536), error.headers.get("Content-Type"),
                                 error.headers.get("X-Request-Id") or error.headers.get("Request-Id"))


def _metadata_request(root: str, key: str, *, opener, page_number: int,
                      query: dict[str, str] | None = None, next_url: str | None = None) -> tuple[dict, bytes, dict]:
    if (query is None) == (next_url is None):
        raise PreflightError("metadata page request is ambiguous", category="LOCAL_IMPLEMENTATION", root=root,
                             page_number=page_number, phase="REQUEST_BUILD")
    url = BASE_URL + "/futures/v1/contracts?" + urllib.parse.urlencode(query) if query is not None else str(next_url)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.path != "/futures/v1/contracts" or "key" in parsed.query.lower():
        raise PreflightError("request boundary invalid", category="INVALID_ENDPOINT_OR_PARAMETERS", root=root,
                             page_number=page_number, phase="REQUEST_BUILD")
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key,
                                                   "Accept": "application/json"}, method="GET")
    try:
        response = _transport(opener(request, 20.0))
    except (TimeoutError, urllib.error.URLError, OSError) as error:
        timeout_category = "TIMEOUT" if isinstance(error, TimeoutError) or "timed out" in str(error).lower() else "CONNECTIVITY"
        raise PreflightError("metadata transport failed", category="TIMEOUT_OR_CONNECTIVITY", root=root,
                             page_number=page_number, timeout_category=timeout_category,
                             exception_class=type(error).__name__, phase="TRANSPORT") from error
    except Exception as error:
        raise PreflightError("metadata transport implementation failed", category="LOCAL_IMPLEMENTATION", root=root,
                             page_number=page_number, exception_class=type(error).__name__, phase="TRANSPORT") from error
    status, raw = response.status, response.raw
    code, error_type, parameter, safe_message, body_request_id = _provider_error(raw)
    request_id = _bounded_request_id(response.request_id) or body_request_id
    if len(raw) > MAX_METADATA_BYTES:
        raise PreflightError("metadata response exceeds cap", category="UNSAFE_RESPONSE_SIZE", root=root, status=status,
                             request_id=request_id, content_type=response.content_type, response_bytes=len(raw),
                             page_number=page_number, phase="RESPONSE_BOUNDARY")
    if status in (401, 403):
        raise PreflightError("authorization or entitlement rejected", category="AUTHENTICATION_OR_ENTITLEMENT", root=root,
                             status=status, request_id=request_id, content_type=response.content_type,
                             response_bytes=len(raw), provider_code=code, provider_type=error_type,
                             provider_parameter=parameter, safe_message=safe_message,
                             page_number=page_number, phase="HTTP_RESPONSE")
    if status == 429:
        raise PreflightError("rate limit anomaly", category="RATE_LIMITING", root=root, status=status,
                             request_id=request_id, content_type=response.content_type, response_bytes=len(raw),
                             provider_code=code, provider_type=error_type, provider_parameter=parameter,
                             safe_message=safe_message, page_number=page_number, phase="HTTP_RESPONSE")
    if status != 200:
        category = "INVALID_ENDPOINT_OR_PARAMETERS" if status in (400, 404, 405, 422) else "PROVIDER_SERVER_FAILURE"
        raise PreflightError("metadata request failed", category=category, root=root, status=status,
                             request_id=request_id, content_type=response.content_type, response_bytes=len(raw),
                             provider_code=code, provider_type=error_type, provider_parameter=parameter,
                             safe_message=safe_message, page_number=page_number, phase="HTTP_RESPONSE")
    try:
        payload = json.loads(raw.decode("utf-8"), parse_float=Decimal)
    except Exception as error:
        raise PreflightError("metadata schema invalid", category="SCHEMA_MISMATCH", root=root, status=status,
                             request_id=request_id, content_type=response.content_type, response_bytes=len(raw),
                             page_number=page_number, exception_class=type(error).__name__, phase="PARSE") from error
    request_id = request_id or (payload.get("request_id") if isinstance(payload.get("request_id"), str) else None)
    if payload.get("status") != "OK" or not isinstance(payload.get("results"), list):
        raise PreflightError("changed metadata response", category="SCHEMA_MISMATCH", root=root,
                             status=status, request_id=request_id, content_type=response.content_type,
                             response_bytes=len(raw), page_number=page_number, phase="PARSE")
    audit = {"provider": "massive-futures", "endpoint": "/futures/v1/contracts",
             "endpoint_class": "futures_contract_metadata", "root": root, "http_status": status,
             "provider_request_id": request_id, "response_byte_count": len(raw),
             "raw_response_sha256": sha256(raw).hexdigest(), "raw_retained": True,
             "response_content_type": response.content_type, "pagination_page_number": page_number,
             "server_filters": {"product_code": root, "type": "single", "active": "true",
                                "date": query.get("date") if query is not None else "cursor_page"},
             "aggregate_requests": 0, "automatic_retry": False}
    return payload, raw, audit


def _discovery_dates(start: date, end: date) -> tuple[date, ...]:
    points = {start, end - timedelta(days=1)}
    for year in range(start.year, end.year + 1):
        for month in (3, 6, 9, 12):
            point = date(year, month, 1)
            if start <= point < end:
                points.add(point)
    result = tuple(sorted(points))
    if not result or len(result) > 12:
        raise PreflightError("point-in-time discovery schedule is invalid", category="LOCAL_IMPLEMENTATION",
                             phase="REQUEST_BUILD")
    return result


def _discover_metadata(root: str, key: str, *, start: date, end: date, opener, sleep,
                       market: Path, prior_calls: int, retrieved_at: datetime) -> tuple[list[dict], int]:
    rows: list[dict] = []
    calls = prior_calls
    request_number = 0
    for point in _discovery_dates(start, end):
        query = {"product_code": root, "date": point.isoformat(), "active": "true",
                 "type": "single", "limit": "1000", "sort": "ticker.asc"}
        next_url = None
        for page_number in range(1, MAX_METADATA_PAGES_PER_ROOT + 1):
            if calls:
                sleep(MIN_CALL_INTERVAL_SECONDS)
            payload, raw, audit = _metadata_request(root, key, opener=opener, page_number=page_number,
                                                    query=query if page_number == 1 else None,
                                                    next_url=next_url if page_number > 1 else None)
            calls += 1
            request_number += 1
            raw_path = market / "raw" / f"{request_number:03d}_contract_discovery.json"
            manifest_path = market / "manifests" / f"{request_number:03d}_metadata_request.json"
            checkpoint_path = market / "checkpoints" / f"{request_number:03d}_metadata_page.json"
            _atomic_new(raw_path, raw)
            audit["retrieved_at"] = retrieved_at.isoformat().replace("+00:00", "Z")
            audit["schema_version"] = SCHEMA_VERSION
            audit["raw_relative_path"] = f"raw/{raw_path.name}"
            audit["discovery_point_date"] = point.isoformat()
            _atomic_new(manifest_path, _json_bytes(audit))
            _atomic_new(checkpoint_path, _json_bytes({"root": root, "discovery_point_date": point.isoformat(),
                        "page_number": page_number, "raw_sha256": audit["raw_response_sha256"],
                        "request_manifest_sha256": sha256(_json_bytes(audit)).hexdigest(),
                        "aggregate_requests": 0}))
            rows.extend(payload["results"])
            next_url = payload.get("next_url")
            if not next_url:
                break
            if page_number == MAX_METADATA_PAGES_PER_ROOT:
                raise PreflightError("metadata pagination exceeds bounded page budget", category="PAGINATION_DEFECT",
                                     root=root, request_id=audit.get("provider_request_id"),
                                     page_number=page_number, phase="PAGINATION")
    return rows, calls


def credential_free_mock_opener(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    parsed = urllib.parse.urlparse(request.full_url)
    query = urllib.parse.parse_qs(parsed.query)
    root = query.get("product_code", [""])[0]
    if parsed.path != "/futures/v1/contracts" or root not in ROOTS or request.get_header("Authorization") != "Bearer synthetic-offline-only":
        return 403, b'{"status":"ERROR"}'
    rows = []
    for ticker, first, last in ((root + "Z4", "2023-12-15", "2024-12-20"),
                                (root + "H5", "2024-03-15", "2025-03-21"),
                                (root + "M5", "2024-06-21", "2025-06-20"),
                                (root + "U5", "2024-09-20", "2025-09-19"),
                                (root + "Z5", "2024-12-20", "2025-12-19"),
                                (root + "H6", "2025-03-21", "2026-03-20"),
                                (root + "M6", "2025-06-20", "2026-06-18"),
                                (root + "U6", "2025-09-19", "2026-09-18")):
        rows.append({"ticker": ticker, "product_code": root, "type": "single", "trading_venue": VENUE,
                     "first_trade_date": first, "last_trade_date": last, "settlement_date": last})
    return 200, json.dumps({"status": "OK", "request_id": "mock-" + root, "results": rows},
                           separators=(",", ":")).encode("utf-8")


def run_preflight(*, key: str, repository: Path, as_of: datetime, opener=default_opener,
                  sleep=time.sleep) -> dict:
    validate_raw_probe(repository)
    if not isinstance(key, str) or not key.strip() or as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise PreflightError("credential or UTC evaluation time missing", category="INPUT")
    end = as_of.date() + timedelta(days=1)
    start = end - timedelta(days=MAX_HISTORY_DAYS)
    base = repository / "data" / "backtests"
    stop_path = base / "es_nq_backfill_preflight.stop"
    for name in PREFLIGHT_NAMES.values():
        if (base / name).exists():
            raise PreflightError("preflight destination exists", category="OUTPUT_EXISTS")
    transaction = base / ".es_nq_backfill_preflight_transaction"
    if transaction.exists():
        raise PreflightError("preflight transaction exists", category="OUTPUT_EXISTS")
    transaction.mkdir(parents=True)
    try:
        inventories = {}
        calls = 0
        for root in ROOTS:
            if stop_path.exists():
                raise PreflightError("owner stop requested", category="OWNER_STOP", root=root)
            market = transaction / root
            rows, calls = _discover_metadata(root, key, start=start, end=end, opener=opener, sleep=sleep,
                                             market=market, prior_calls=calls, retrieved_at=as_of)
            contracts, exclusions = _classify_contract_rows(root, rows, start=start, end=end)
            raw_per_row = Decimal("203") if root == "ES" else Decimal("207")
            inventory = build_inventory(root, contracts, raw_bytes_per_row=raw_per_row)
            inventory.update({"status": "PREFLIGHT_READY_NOT_STARTED", "schema_version": SCHEMA_VERSION,
                              "provider_entitlement_interval": {"start_inclusive": start.isoformat(),
                                                                "end_exclusive": end.isoformat()},
                              "aggregate_requests_made": 0, "backfill_started": False,
                              "continuous_recorder_started": False,
                              "staging_path": str(base / (root.lower() + "_backfill_staging_1")),
                              "checkpoint_path": str(base / (root.lower() + "_backfill_checkpoint_1.json")),
                              "archive_path": str(base / (root.lower() + "_historical_archive_1")),
                              "minimum_untouched_oos_trades_for_acceptance": 200,
                              "calendar_days_are_not_trade_sample_size": True,
                              "excluded_discovery_record_count": len(exclusions),
                              "excluded_discovery_records": list(exclusions)})
            _atomic_new(market / "plans" / "inventory.json", _json_bytes(inventory))
            _atomic_new(market / "checkpoints" / "metadata_complete.json",
                        _json_bytes({"root": root, "metadata_pages": len(list((market / "manifests").glob("*.json"))),
                                     "aggregate_requests": 0}))
            _atomic_new(market / "reports" / "preflight.json",
                        _json_bytes({"status": "PREFLIGHT_READY_NOT_STARTED", "root": root,
                                     "contract_count": inventory["contract_count"],
                                     "aggregate_requests_made": 0, "raw_metadata_retained": True}))
            inventories[root] = inventory
        for root in ROOTS:
            os.rename(transaction / root, base / PREFLIGHT_NAMES[root])
        transaction.rmdir()
        stop_path.unlink(missing_ok=True)
        return {"status": "READY_FOR_ES_NQ_BACKFILL_PREFLIGHT", "schema_version": SCHEMA_VERSION,
                "metadata_requests": calls, "aggregate_requests": 0, "markets": inventories}
    except Exception as error:
        failure = error
        raise
    finally:
        if transaction.exists():
            # Incomplete raw metadata remains rejected evidence instead of being promoted.
            rejected = base / "rejected_preflights" / ("preflight_" + as_of.strftime("%Y%m%dT%H%M%SZ"))
            if not rejected.exists():
                rejected.parent.mkdir(parents=True, exist_ok=True)
                os.rename(transaction, rejected)
                diagnostic = getattr(locals().get("failure"), "safe", {
                    "utc_timestamp": as_of.isoformat().replace("+00:00", "Z"),
                    "lifecycle_stage": "BACKFILL_PREFLIGHT", "failure_phase": "UNKNOWN",
                    "rejection_category": "LOCAL_IMPLEMENTATION", "endpoint_class": None,
                    "http_status": None, "provider_request_id": None, "response_content_type": None,
                    "response_byte_count": None, "provider_error_code": None,
                    "provider_error_type": None, "provider_error_parameter": None,
                    "sanitized_error_message": None, "pagination_page_number": None,
                    "timeout_category": None, "exception_class": type(locals().get("failure")).__name__,
                    "aggregate_requests": 0, "automatic_retry": False})
                _atomic_new(rejected / "sanitized_diagnostic.json", _json_bytes(diagnostic))
        key = ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Metadata-only ES/NQ historical-backfill preflight")
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--credential-free-mock", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    key = sys.stdin.readline().rstrip("\r\n")
    try:
        result = run_preflight(key=key, repository=args.repository.resolve(), as_of=datetime.now(timezone.utc),
                               opener=credential_free_mock_opener if args.credential_free_mock else default_opener,
                               sleep=(lambda _: None) if args.credential_free_mock else time.sleep)
        print(result["status"])
        return 0
    except Exception as error:
        print("BLOCKED: " + str(error), file=sys.stderr)
        return 1
    finally:
        key = ""


if __name__ == "__main__":
    raise SystemExit(main())
