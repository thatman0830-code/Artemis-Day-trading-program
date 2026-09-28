"""Crash-safe, market-isolated history for NinjaTrader canonical smoke reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import os
from pathlib import Path

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_v1 import NinjaTraderCanonicalSmokeV1

VERSION = "ninjatrader-canonical-smoke-history-v1"


class NinjaTraderCanonicalSmokeHistoryError(RuntimeError):
    pass


def _value(value):
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise NinjaTraderCanonicalSmokeHistoryError("history timestamp must be UTC")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Decimal): return format(value, "f")
    if isinstance(value, Enum): return value.value
    if isinstance(value, tuple): return [_value(item) for item in value]
    if isinstance(value, dict): return {key: _value(item) for key, item in sorted(value.items())}
    return value


def _bytes(value):
    return json.dumps(_value(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _payload(report):
    return {name: _value(getattr(report, name)) for name in report.__dataclass_fields__}


@dataclass(frozen=True)
class NinjaTraderCanonicalSmokeHistoryEventV1:
    event_id: str
    sequence: int
    previous_event_id: str | None
    market: FuturesCanonicalMarket
    evaluated_at: datetime
    report_id: str
    dataset_fingerprint: str
    source_chain_head_sha256: str
    latest_outcome: str
    report: dict
    schema_version: str = VERSION


def read_ninjatrader_canonical_smoke_history(root, *, market):
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("explicit ES or NQ history market required")
    directory = Path(root).absolute() / market.value / "events"
    if not directory.exists(): return ()
    if not directory.is_dir() or directory.is_symlink():
        raise NinjaTraderCanonicalSmokeHistoryError("history event path is unsafe")
    paths = sorted(directory.iterdir(), key=lambda item: item.name)
    if ([path.name for path in paths] != [f"{i:020d}.json" for i in range(len(paths))]
            or any(not path.is_file() or path.is_symlink() for path in paths)):
        raise NinjaTraderCanonicalSmokeHistoryError("history event inventory is invalid")
    events=[]; previous=None; last_time=None
    for sequence,path in enumerate(paths):
        try: document=json.loads(path.read_bytes())
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:
            raise NinjaTraderCanonicalSmokeHistoryError("history event is unreadable") from exc
        required={"schema_version","event_id","sequence","previous_event_id","market",
            "evaluated_at","report_id","dataset_fingerprint","source_chain_head_sha256",
            "latest_outcome","report"}
        if not isinstance(document,dict) or set(document)!=required:
            raise NinjaTraderCanonicalSmokeHistoryError("history event schema is invalid")
        identity=dict(document);claimed=identity.pop("event_id")
        try:
            at=datetime.fromisoformat(document["evaluated_at"].replace("Z","+00:00"))
            parsed_market=FuturesCanonicalMarket(document["market"])
        except (TypeError,ValueError) as exc:
            raise NinjaTraderCanonicalSmokeHistoryError("history event identity is invalid") from exc
        report=document["report"]
        if (document["schema_version"]!=VERSION or document["sequence"]!=sequence
                or document["previous_event_id"]!=previous or parsed_market is not market
                or claimed!=hashlib.sha256(_bytes(identity)).hexdigest()
                or not isinstance(report,dict) or report.get("report_id")!=document["report_id"]
                or report.get("market")!=market.value
                or report.get("evaluated_at")!=document["evaluated_at"]
                or report.get("dataset_fingerprint")!=document["dataset_fingerprint"]
                or report.get("source_chain_head_sha256")!=document["source_chain_head_sha256"]
                or report.get("latest_outcome")!=document["latest_outcome"]
                or report.get("trading_authority") is not False):
            raise NinjaTraderCanonicalSmokeHistoryError("history chain or report binding is invalid")
        if last_time is not None and at<last_time:
            raise NinjaTraderCanonicalSmokeHistoryError("history chronology regressed")
        event=NinjaTraderCanonicalSmokeHistoryEventV1(claimed,sequence,previous,
            parsed_market,at,document["report_id"],document["dataset_fingerprint"],
            document["source_chain_head_sha256"],document["latest_outcome"],report)
        events.append(event);previous=claimed;last_time=at
    return tuple(events)


def append_ninjatrader_canonical_smoke(root, *, report):
    if not isinstance(report,NinjaTraderCanonicalSmokeV1):
        raise TypeError("NinjaTrader canonical smoke report required")
    if (report.deterministic_repeat_verified is not True or report.advisory_only is not True
            or report.paper_execution_permitted is not False
            or report.live_trading_permitted is not False or report.trading_authority is not False):
        raise NinjaTraderCanonicalSmokeHistoryError("unverified or authoritative report rejected")
    base=Path(root).absolute()
    if base.exists() and (not base.is_dir() or base.is_symlink()):
        raise NinjaTraderCanonicalSmokeHistoryError("history root is unsafe")
    events=read_ninjatrader_canonical_smoke_history(base,market=report.market)
    exact=tuple(event for event in events if event.report_id==report.report_id)
    if exact:
        if len(exact)!=1 or exact[0].report!=_payload(report):
            raise NinjaTraderCanonicalSmokeHistoryError("report identity conflicts with history")
        return exact[0]
    same_source=tuple(event for event in events
        if event.source_chain_head_sha256==report.source_chain_head_sha256)
    if same_source:
        if (len(same_source)!=1 or same_source[0].dataset_fingerprint!=report.dataset_fingerprint
                or same_source[0].market is not report.market):
            raise NinjaTraderCanonicalSmokeHistoryError("source identity conflicts with history")
        return same_source[0]
    if events and report.evaluated_at<events[-1].evaluated_at:
        raise NinjaTraderCanonicalSmokeHistoryError("history chronology regressed")
    directory=base/report.market.value/"events";directory.mkdir(parents=True,exist_ok=True)
    if directory.is_symlink() or directory.parent.is_symlink():
        raise NinjaTraderCanonicalSmokeHistoryError("history directory is unsafe")
    body={"schema_version":VERSION,"sequence":len(events),
        "previous_event_id":events[-1].event_id if events else None,
        "market":report.market.value,"evaluated_at":_value(report.evaluated_at),
        "report_id":report.report_id,"dataset_fingerprint":report.dataset_fingerprint,
        "source_chain_head_sha256":report.source_chain_head_sha256,
        "latest_outcome":report.latest_outcome,"report":_payload(report)}
    document={**body,"event_id":hashlib.sha256(_bytes(body)).hexdigest()}
    target=directory/f"{len(events):020d}.json";temporary=target.with_suffix(".json.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(_bytes(document));stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    finally:
        if temporary.exists(): temporary.unlink()
    return read_ninjatrader_canonical_smoke_history(base,market=report.market)[-1]
