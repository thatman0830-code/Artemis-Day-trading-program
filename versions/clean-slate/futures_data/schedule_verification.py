from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable

SCHEMA_VERSION = "massive-es-nq-schedule-verification-v1"
BASE_URL = "https://api.massive.com"
ALLOWED_HOST = "api.massive.com"
ROOTS = ("ES", "NQ")
START = date(2025, 6, 1)
END = date(2026, 8, 26)
MAX_PAGES_PER_ROOT = 8
MAX_REQUESTS = 16
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MIN_CALL_INTERVAL_SECONDS = 15.0
STAGING_NAME = "es_nq_schedule_verification_staging_2"
RESULT_NAME = "es_nq_schedule_verification_2"
EXPECTED_PRODUCT_NAMES = {"ES": "E-mini S&P 500 Futures", "NQ": "E-mini Nasdaq-100 Futures"}
SECRET = re.compile(r"(?i)(authorization|bearer\s+|api[_-]?key|credential|secret)")


class ScheduleVerificationError(RuntimeError):
    pass


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _atomic_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    if path.exists() or temporary.exists():
        raise ScheduleVerificationError("existing destination rejected")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(temporary, path)


def _safe_request_id(value: object) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) else None


def _default_fetch(url: str, key: str) -> tuple[int, bytes, dict]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or SECRET.search(parsed.query):
        raise ScheduleVerificationError("request boundary rejected")
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key,
                                                   "Accept": "application/json"}, method="GET")
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return response.status, response.read(MAX_RESPONSE_BYTES + 1), {
            "content_type": response.headers.get("Content-Type"),
            "request_id": response.headers.get("X-Request-Id") or response.headers.get("Request-Id")}


def _first_url(root: str) -> str:
    query = {"product_code": root, "session_end_date.gte": START.isoformat(),
             "session_end_date.lte": END.isoformat(), "limit": "1000",
             "sort": "session_end_date.asc"}
    return BASE_URL + "/futures/v1/schedules?" + urllib.parse.urlencode(query)


def _validate_next_url(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ScheduleVerificationError("pagination schema invalid")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or SECRET.search(parsed.query):
        raise ScheduleVerificationError("pagination boundary rejected")
    return value


def _validate_page(raw: bytes, root: str, source_request_id: str) -> tuple[list[dict], str | None]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ScheduleVerificationError("schedule response is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ScheduleVerificationError("schedule schema invalid")
    records = []
    for item in payload["results"]:
        if not isinstance(item, dict) or item.get("product_code") != root:
            raise ScheduleVerificationError("wrong-product schedule record")
        if not all(isinstance(item.get(name), str) for name in
                   ("product_name", "trading_venue", "session_end_date", "event", "timestamp")):
            raise ScheduleVerificationError("schedule event fields invalid")
        try:
            session = date.fromisoformat(item["session_end_date"])
            stamp = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ScheduleVerificationError("schedule date or timestamp invalid") from exc
        if not START <= session <= END or stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ScheduleVerificationError("schedule chronology invalid")
        if item["trading_venue"] != "XCME":
            raise ScheduleVerificationError("wrong-venue schedule record")
        records.append({"product_code": root, "product_name": item["product_name"],
                        "trading_venue": item["trading_venue"], "session_end_date": session.isoformat(),
                        "event": item["event"], "timestamp": stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "source_request_id": source_request_id})
    return records, _validate_next_url(payload.get("next_url"))


def verify_schedules(repository: Path, key: str, *, fetch: Callable = _default_fetch,
                     sleep: Callable[[float], None] = time.sleep) -> dict:
    stage = repository / "data" / "backtests" / STAGING_NAME
    result = repository / "data" / "backtests" / RESULT_NAME
    if stage.exists() or result.exists():
        raise ScheduleVerificationError("existing schedule-verification path rejected")
    calls = 0
    total_bytes = 0
    summaries = {}
    for root in ROOTS:
        url = _first_url(root)
        seen_urls = set()
        records = []
        for page in range(1, MAX_PAGES_PER_ROOT + 1):
            if url in seen_urls:
                raise ScheduleVerificationError("pagination cycle rejected")
            seen_urls.add(url)
            if calls:
                sleep(MIN_CALL_INTERVAL_SECONDS)
            status, raw, headers = fetch(url, key)
            calls += 1
            total_bytes += len(raw)
            if calls > MAX_REQUESTS or len(raw) > MAX_RESPONSE_BYTES or total_bytes > MAX_TOTAL_BYTES:
                raise ScheduleVerificationError("schedule verification cap exceeded")
            request_id = sha256(f"{SCHEMA_VERSION}|{root}|{page}|{url}".encode()).hexdigest()
            raw_path = stage / root / "raw" / f"{request_id}.json"
            _atomic_new(raw_path, raw)
            manifest = {"schema_version": SCHEMA_VERSION, "root": root, "page": page,
                        "endpoint_class": "futures_schedules", "http_status": status,
                        "provider_request_id": _safe_request_id(headers.get("request_id")),
                        "response_content_type": str(headers.get("content_type") or "")[:128],
                        "response_bytes": len(raw), "raw_sha256": sha256(raw).hexdigest(),
                        "raw_relative_path": f"raw/{raw_path.name}", "automatic_retry": False,
                        "aggregate_requests": 0}
            _atomic_new(stage / root / "manifests" / f"{request_id}.json", _json_bytes(manifest))
            if status != 200:
                raise ScheduleVerificationError("schedule provider response rejected")
            page_records, next_url = _validate_page(raw, root, request_id)
            records.extend(page_records)
            if next_url is None:
                break
            url = next_url
        else:
            raise ScheduleVerificationError("schedule pagination cap exhausted")
        if not records:
            raise ScheduleVerificationError("schedule range empty without adjacent non-session evidence")
        identities = [(x["product_code"], x["product_name"], x["trading_venue"], x["session_end_date"],
                       x["event"], x["timestamp"], x["source_request_id"]) for x in records]
        if len(identities) != len(set(identities)):
            raise ScheduleVerificationError("byte-equivalent schedule record duplicated within one source response")
        outright = [x for x in records if x["product_name"] == EXPECTED_PRODUCT_NAMES[root]]
        if not outright:
            raise ScheduleVerificationError("expected outright schedule product absent")
        semantic = [(x["product_code"], x["product_name"], x["trading_venue"], x["session_end_date"],
                     x["event"], x["timestamp"]) for x in outright]
        if len(semantic) != len(set(semantic)):
            raise ScheduleVerificationError("conflicting or overlapping outright schedule observations")
        normalized = _json_bytes(sorted(outright, key=lambda x: (x["session_end_date"], x["timestamp"], x["event"])))
        _atomic_new(stage / root / "normalized" / "schedule_events.json", normalized)
        summaries[root] = {"returned_records": len(records), "outright_records": len(outright),
                           "excluded_other_product_records": len(records) - len(outright), "pages": len(seen_urls),
                           "normalized_sha256": sha256(normalized).hexdigest()}
    report = {"schema_version": SCHEMA_VERSION, "state": "SCHEDULES_RETAINED_FOR_OFFLINE_CALENDAR_REVIEW",
              "start": START.isoformat(), "end_inclusive": END.isoformat(), "network_calls": calls,
              "aggregate_requests": 0, "automatic_retry": False, "total_raw_bytes": total_bytes,
              "markets": summaries}
    _atomic_new(stage / "validation_report.json", _json_bytes(report))
    os.rename(stage, result)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded schedules-only ES/NQ verification")
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    key = sys.stdin.readline().rstrip("\r\n")
    try:
        try:
            print(json.dumps(verify_schedules(args.repository.resolve(), key), sort_keys=True))
            return 0
        except ScheduleVerificationError as exc:
            diagnostic = {"schema_version": SCHEMA_VERSION, "utc_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                          "failure_phase": "SCHEDULES_VERIFICATION", "exception_class": type(exc).__name__,
                          "sanitized_message": str(exc)[:200], "aggregate_requests": 0, "automatic_retry": False}
            directory = args.repository.resolve() / "data/backtests/schedule_verification_diagnostics"
            name = "diagnostic-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json"
            _atomic_new(directory / name, _json_bytes(diagnostic))
            print("BLOCKED: schedules verification failed closed; see local sanitized diagnostic", file=sys.stderr)
            return 2
    finally:
        key = ""


if __name__ == "__main__":
    raise SystemExit(main())
