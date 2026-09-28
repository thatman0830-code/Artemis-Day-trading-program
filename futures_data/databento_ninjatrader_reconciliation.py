"""Offline, non-mutating Databento/NinjaTrader minute reconciliation."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path


VERSION = "databento-ninjatrader-reconciliation-v1"
NINJA_VERSION = "ninjatrader-closed-bar-recorder-v1"
ZERO_HASH = "0" * 64
FIELDS = ("open", "high", "low", "close", "volume")
MAX_DETAIL_MINUTES = 200


class ReconciliationError(ValueError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _stamp(value: object) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise ReconciliationError("timestamp invalid") from None
    if stamp.second or stamp.microsecond:
        raise ReconciliationError("timestamp not minute aligned")
    return stamp


def _number(value: object, field: str) -> Decimal:
    if isinstance(value, float):
        raise ReconciliationError(f"binary float forbidden for {field}")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ReconciliationError(f"invalid {field}") from None
    if not number.is_finite() or number < 0 or (field != "volume" and number == 0):
        raise ReconciliationError(f"invalid {field}")
    return number


def read_ninja(path: Path, *, lane: str) -> dict[datetime, tuple[Decimal, ...]]:
    previous = ZERO_HASH
    result = {}
    for raw in path.read_bytes().splitlines():
        row = json.loads(raw)
        digest = row.pop("record_sha256", None)
        if (row.get("schema_version") != NINJA_VERSION
                or row.get("market") != lane
                or row.get("paper_only") is not True
                or row.get("trading_authority") is not False
                or row.get("previous_record_sha256") != previous
                or digest != sha256(_canonical(row)).hexdigest()):
            raise ReconciliationError("NinjaTrader chain invalid")
        stamp = _stamp(row.get("open_time_utc"))
        if stamp in result:
            raise ReconciliationError("duplicate NinjaTrader minute")
        result[stamp] = tuple(_number(row[field], field) for field in FIELDS)
        previous = digest
    return result


def read_databento(path: Path) -> dict[datetime, tuple[Decimal, ...]]:
    result = {}
    for raw in path.read_bytes().splitlines():
        row = json.loads(raw)
        header = row.get("hd") if isinstance(row, dict) else None
        if not isinstance(header, dict) or not all(field in row for field in FIELDS):
            continue
        stamp = _stamp(header.get("ts_event"))
        values = tuple(_number(row[field], field) for field in FIELDS)
        if stamp in result and result[stamp] != values:
            raise ReconciliationError("conflicting Databento minute")
        result[stamp] = values
    if not result:
        raise ReconciliationError("Databento input contains no OHLCV minutes")
    return result


def reconcile(*, lane: str, session_date: str, ninja_path: Path,
              databento_path: Path) -> dict:
    if lane not in {"ES", "NQ"}:
        raise ReconciliationError("lane invalid")
    ninja = read_ninja(ninja_path, lane=lane)
    databento = read_databento(databento_path)
    try:
        declared_date = datetime.fromisoformat(session_date).date()
    except ValueError:
        raise ReconciliationError("session date invalid") from None
    outside_ninja = sorted(stamp for stamp in ninja if stamp.date() != declared_date)
    allowed_boundary = datetime.combine(declared_date, datetime.min.time(), timezone.utc) - timedelta(minutes=1)
    if outside_ninja not in ([], [allowed_boundary]) or any(stamp.date() != declared_date for stamp in databento):
        raise ReconciliationError("record outside declared UTC archive day")
    ninja = {stamp: values for stamp, values in ninja.items() if stamp.date() == declared_date}
    ninja_times, databento_times = set(ninja), set(databento)
    conflicts = sorted(stamp for stamp in ninja_times & databento_times
                       if ninja[stamp] != databento[stamp])
    price_conflicts = sorted(stamp for stamp in ninja_times & databento_times
                             if ninja[stamp][:4] != databento[stamp][:4])
    volume_only_conflicts = sorted(stamp for stamp in ninja_times & databento_times
                                   if ninja[stamp][:4] == databento[stamp][:4]
                                   and ninja[stamp][4] != databento[stamp][4])
    missing_ninja = sorted(databento_times - ninja_times)
    missing_databento = sorted(ninja_times - databento_times)
    state = "MATCHED" if not (conflicts or missing_ninja or missing_databento) else "REVIEW_REQUIRED"
    report = {
        "cross_source_merge_performed": False,
        "databento_input_sha256": sha256(databento_path.read_bytes()).hexdigest(),
        "databento_minute_count": len(databento),
        "lane": lane, "matched_minute_count": len(ninja_times & databento_times) - len(conflicts),
        "missing_databento_count": len(missing_databento),
        "missing_databento_detail_truncated": len(missing_databento) > MAX_DETAIL_MINUTES,
        "missing_databento_minutes_utc": [x.isoformat().replace("+00:00", "Z") for x in missing_databento[:MAX_DETAIL_MINUTES]],
        "missing_ninjatrader_count": len(missing_ninja),
        "missing_ninjatrader_detail_truncated": len(missing_ninja) > MAX_DETAIL_MINUTES,
        "missing_ninjatrader_minutes_utc": [x.isoformat().replace("+00:00", "Z") for x in missing_ninja[:MAX_DETAIL_MINUTES]],
        "ninjatrader_input_sha256": sha256(ninja_path.read_bytes()).hexdigest(),
        "ninjatrader_boundary_minute_excluded_count": len(outside_ninja),
        "ninjatrader_minute_count": len(ninja), "paper_only": True,
        "price_or_volume_conflict_count": len(conflicts),
        "price_or_volume_conflict_detail_truncated": len(conflicts) > MAX_DETAIL_MINUTES,
        "price_or_volume_conflict_minutes_utc": [x.isoformat().replace("+00:00", "Z") for x in conflicts[:MAX_DETAIL_MINUTES]],
        "price_conflict_count": len(price_conflicts),
        "price_conflict_minutes_utc": [x.isoformat().replace("+00:00", "Z") for x in price_conflicts[:MAX_DETAIL_MINUTES]],
        "volume_only_conflict_count": len(volume_only_conflicts),
        "volume_only_conflict_detail_truncated": len(volume_only_conflicts) > MAX_DETAIL_MINUTES,
        "recovery_candidates_are_noncanonical": True, "schema_version": VERSION,
        "session_date": session_date, "state": state, "trading_authority": False,
    }
    report["report_sha256"] = sha256(_canonical(report)).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=("ES", "NQ"), required=True)
    parser.add_argument("--session-date", required=True)
    parser.add_argument("--ninjatrader", type=Path, required=True)
    parser.add_argument("--databento", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = reconcile(lane=args.lane, session_date=args.session_date,
                       ninja_path=args.ninjatrader.resolve(),
                       databento_path=args.databento.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_bytes(_canonical(report) + b"\n")
    temporary.replace(args.output)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
