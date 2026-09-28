from __future__ import annotations

import csv
import json
import os
import shutil
import ssl
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from backtesting.file_runner import DATA_MANIFEST_SCHEMA, _json_bytes
from backtesting.market_data import (
    CanonicalTimeframe, GapPolicy, dataset_fingerprint,
    normalize_hyperliquid_candle, validate_dataset,
)


PUBLIC_URLS = {
    "testnet": "https://api.hyperliquid-testnet.xyz/info",
    "main" + "net": "https://api.hyperliquid.xyz/info",
}
DOWNLOAD_SCHEMA = "backtesting-public-download-v1"
CANDLE_SCHEMA = "historical-candle-v1"
CSV_FIELDS = ("symbol","timeframe","open_time","close_time","open","high","low","close","volume","is_closed")


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _ms(value: datetime) -> int:
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _last_closed_boundary(value: datetime,
                          timeframe: CanonicalTimeframe) -> datetime:
    duration_ms = int(timeframe.duration.total_seconds() * 1000)
    boundary_ms = (_ms(value) // duration_ms) * duration_ms
    return datetime.fromtimestamp(boundary_ms / 1000, tz=timezone.utc)


class PublicCandleTransport:
    """HTTPS-only public information transport; no authentication surface."""

    def post(self, *, url: str, payload: bytes, timeout: float) -> bytes:
        request = urllib.request.Request(url, data=payload, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "canonical-backtesting-data/1"})
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.read()


@dataclass(frozen=True)
class DownloadRequest:
    symbol: str
    timeframes: tuple[CanonicalTimeframe, ...]
    start: datetime
    end: datetime
    data_network: str
    output: Path
    gap_policy: GapPolicy = GapPolicy.REJECT
    overwrite: bool = False
    resume: bool = False
    timeout_seconds: float = 15.0
    retry_limit: int = 3
    window_candles: int = 1000


class HistoricalCandleDownloader:
    def __init__(self, *, transport=None, sleeper=time.sleep, now=None):
        self.transport = transport or PublicCandleTransport()
        self.sleeper = sleeper
        self.now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _validate(request: DownloadRequest):
        if not request.symbol.strip() or request.symbol != request.symbol.upper():
            raise ValueError("symbol must be explicit uppercase text")
        if request.data_network not in PUBLIC_URLS: raise ValueError("unsupported data network")
        if request.start.tzinfo is None or request.start.utcoffset() != timedelta(0) or request.end.tzinfo is None or request.end.utcoffset() != timedelta(0):
            raise ValueError("download boundaries must be UTC timezone-aware")
        if request.start >= request.end: raise ValueError("download interval must be nonempty [start,end)")
        if not request.timeframes or len(set(request.timeframes)) != len(request.timeframes):
            raise ValueError("canonical timeframes must be unique and nonempty")
        if request.overwrite and request.resume: raise ValueError("overwrite and resume are mutually exclusive")
        if request.retry_limit < 0 or request.window_candles < 1 or request.timeout_seconds <= 0:
            raise ValueError("request bounds and retry policy are invalid")
        for tf in request.timeframes:
            seconds = int(tf.duration.total_seconds())
            if int(request.start.timestamp()) % seconds or int(request.end.timestamp()) % seconds:
                raise ValueError("requested boundaries must align to every timeframe")

    @staticmethod
    def _identity(request):
        return sha256("\x1f".join((DOWNLOAD_SCHEMA, request.symbol,
            ",".join(tf.value for tf in request.timeframes), _stamp(request.start),
            _stamp(request.end), request.data_network, request.gap_policy.value)).encode()).hexdigest()

    def _fetch(self, request, timeframe, start_ms, end_ms):
        body = json.dumps({"type":"candleSnapshot","req":{"coin":request.symbol,
            "interval":timeframe.value,"startTime":start_ms,"endTime":end_ms}},
            separators=(",", ":"), sort_keys=True).encode()
        for attempt in range(request.retry_limit + 1):
            try:
                raw = self.transport.post(url=PUBLIC_URLS[request.data_network], payload=body,
                                          timeout=request.timeout_seconds)
                value = json.loads(raw.decode("utf-8"), parse_float=str, parse_int=int)
                if not isinstance(value, list): raise ValueError("malformed candle response")
                return value
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt >= request.retry_limit: raise
            except (TimeoutError, urllib.error.URLError):
                if attempt >= request.retry_limit: raise
            if attempt < request.retry_limit: self.sleeper(min(2 ** attempt, 8))
        raise RuntimeError("bounded retry loop exhausted")

    @staticmethod
    def _write_csv(path, candles):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n"); writer.writerow(CSV_FIELDS)
            for c in candles:
                writer.writerow((c.symbol,c.timeframe.value,_stamp(c.open_time),_stamp(c.close_time),
                    format(c.open,"f"),format(c.high,"f"),format(c.low,"f"),format(c.close,"f"),
                    "" if c.volume is None else format(c.volume,"f"),"true"))

    def download(self, request: DownloadRequest, progress=print) -> Path:
        self._validate(request); target = request.output.resolve(); partial = target.with_name(target.name + ".partial")
        if target.exists() and not request.overwrite: raise FileExistsError("completed dataset exists; use --overwrite")
        if partial.exists() and not request.resume and not request.overwrite:
            raise FileExistsError("partial dataset exists; use --resume or --overwrite")
        identity = self._identity(request)
        if request.overwrite:
            if target.exists(): shutil.rmtree(target)
            if partial.exists(): shutil.rmtree(partial)
        partial.mkdir(parents=True, exist_ok=True)
        state_path = partial / "partial_manifest.json"
        state = {"schema_version": DOWNLOAD_SCHEMA,"request_id":identity,"completed":{}}
        if request.resume and state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("schema_version") != DOWNLOAD_SCHEMA or state.get("request_id") != identity:
                raise ValueError("partial download is incompatible with request")
        elif request.resume and any(partial.iterdir()): raise ValueError("partial manifest missing")
        dataset_id = "hyperliquid-public-" + identity[:24]
        all_candles = []
        cutoff = min(request.end, self.now())
        for tf in request.timeframes:
            chunk_path = partial / f"{request.symbol}_{tf.value}.csv"
            existing = []
            if tf.value in state["completed"]:
                if not chunk_path.is_file() or sha256(chunk_path.read_bytes()).hexdigest() != state["completed"][tf.value]["sha256"]:
                    raise ValueError("partial candle file checksum mismatch")
                existing = self._read_canonical(chunk_path, dataset_id, request, tf)
            cursor = existing[-1].close_time if existing else request.start
            candles = list(existing)
            window = tf.duration * request.window_candles
            while cursor < request.end:
                window_end = min(cursor + window, request.end)
                progress(f"{request.symbol} {tf.value} {_stamp(cursor)} -> {_stamp(window_end)}")
                rows = self._fetch(request, tf, _ms(cursor), _ms(window_end))
                normalized = []
                for row in rows:
                    if not isinstance(row, dict): raise ValueError("malformed candle record")
                    required = {"t","T","s","i","o","h","l","c"}
                    if not required.issubset(row): raise ValueError("malformed candle record fields")
                    # The public endpoint treats endTime as inclusive and may
                    # return the candle opening exactly at the requested
                    # exclusive boundary. It belongs to the next window.
                    if row["t"] == _ms(window_end):
                        continue
                    normalized_row = dict(row)
                    duration_ms = int(tf.duration.total_seconds() * 1000)
                    # Hyperliquid public candles use an inclusive final
                    # millisecond. Phase 1 owns exclusive close boundaries.
                    if normalized_row["T"] == normalized_row["t"] + duration_ms - 1:
                        normalized_row["T"] += 1
                    candle = normalize_hyperliquid_candle({**normalized_row,"is_closed":True}, dataset_id=dataset_id,
                        schema_version=CANDLE_SCHEMA, source=f"hyperliquid-public-{request.data_network}", exchange="hyperliquid")
                    if candle.symbol != request.symbol or candle.timeframe != tf: raise ValueError("response identity mismatch")
                    if not (cursor <= candle.open_time and candle.close_time <= window_end): raise ValueError("response outside requested window")
                    if candle.close_time > cutoff: continue
                    normalized.append(candle)
                normalized.sort(key=lambda c: (c.open_time,c.id))
                if len({c.id for c in normalized}) != len(normalized): raise ValueError("duplicate candle in response")
                if candles and normalized and normalized[0].open_time < candles[-1].close_time: raise ValueError("overlapping download windows")
                candles.extend(normalized); cursor = window_end
                self._write_csv(chunk_path, candles)
                state["completed"][tf.value] = {"through":_stamp(cursor),"sha256":sha256(chunk_path.read_bytes()).hexdigest()}
                state_path.write_bytes(_json_bytes(state))
            actual_start = candles[0].open_time if candles else None
            actual_end = candles[-1].close_time if candles else None
            required_end = (request.end if cutoff >= request.end
                            else _last_closed_boundary(cutoff, tf))
            if actual_start != request.start or actual_end != required_end:
                raise ValueError(
                    f"{request.symbol} {tf.value} requested boundary coverage incomplete: "
                    f"expected [{_stamp(request.start)}, {_stamp(required_end)}), "
                    f"actual [{_stamp(actual_start) if actual_start else 'NONE'}, "
                    f"{_stamp(actual_end) if actual_end else 'NONE'})"
                )
            all_candles.extend(candles)
        ordered = tuple(sorted(all_candles,key=lambda c:(c.open_time,c.symbol,c.timeframe.value,c.id)))
        dataset = validate_dataset(ordered,dataset_id=dataset_id,schema_version=CANDLE_SCHEMA,
            source=f"hyperliquid-public-{request.data_network}",exchange="hyperliquid",
            gap_policy=request.gap_policy,validation_time=cutoff)
        staging = Path(tempfile.mkdtemp(prefix=target.name+".complete-",dir=target.parent))
        try:
            mappings=[]; checks={}
            for tf in request.timeframes:
                name=f"{request.symbol}_{tf.value}.csv"; source_file=partial/name
                shutil.copyfile(source_file,staging/name); checks[name]=sha256((staging/name).read_bytes()).hexdigest()
                mappings.append({"timeframe":tf.value,"path":name})
            manifest={"schema_version":DATA_MANIFEST_SCHEMA,"dataset_id":dataset_id,
                "candle_schema_version":CANDLE_SCHEMA,"source":dataset.source,"exchange":"hyperliquid",
                "data_network":request.data_network,"gap_policy":request.gap_policy.value,
                "validation_time":_stamp(cutoff),"requested_start":_stamp(request.start),
                "requested_end":_stamp(request.end),"files":mappings,
                "gaps":[{"symbol":g.symbol,"timeframe":g.timeframe.value,"missing_intervals":g.missing_count,
                         "gap_start":_stamp(g.expected_open_time),"gap_end":_stamp(g.actual_open_time)} for g in dataset.gaps],
                "approved_exclusions":([f"forming interval excluded after {_stamp(cutoff)}"] if cutoff < request.end else []),
                "checksums":checks,"dataset_fingerprint":dataset.fingerprint}
            (staging/"dataset_manifest.json").write_bytes(_json_bytes(manifest))
            if target.exists(): shutil.rmtree(target)
            os.replace(staging,target); shutil.rmtree(partial)
        except Exception:
            shutil.rmtree(staging,ignore_errors=True); raise
        progress(f"COMPLETE fingerprint={dataset.fingerprint}")
        return target/"dataset_manifest.json"

    @staticmethod
    def _read_canonical(path,dataset_id,request,tf):
        result=[]
        with path.open("r",encoding="utf-8",newline="") as handle:
            reader=csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != CSV_FIELDS: raise ValueError("partial CSV schema mismatch")
            epoch=datetime(1970,1,1,tzinfo=timezone.utc)
            for row in reader:
                opened=datetime.fromisoformat(row["open_time"].replace("Z","+00:00")); closed=datetime.fromisoformat(row["close_time"].replace("Z","+00:00"))
                result.append(normalize_hyperliquid_candle({"s":row["symbol"],"i":row["timeframe"],
                    "t":_ms(opened),"T":_ms(closed),"o":row["open"],"h":row["high"],"l":row["low"],"c":row["close"],
                    "v":row["volume"] or None,"is_closed":True},dataset_id=dataset_id,schema_version=CANDLE_SCHEMA,
                    source=f"hyperliquid-public-{request.data_network}",exchange="hyperliquid"))
        if any(c.symbol!=request.symbol or c.timeframe!=tf for c in result): raise ValueError("partial identity mismatch")
        return result
