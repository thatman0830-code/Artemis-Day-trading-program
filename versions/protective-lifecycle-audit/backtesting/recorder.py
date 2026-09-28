from __future__ import annotations

import csv
import io
import json
import os
import random
import shutil
import ssl
import time
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path

from backtesting.downloader import (
    CANDLE_SCHEMA, CSV_FIELDS, PUBLIC_URLS, PublicCandleTransport, _ms, _stamp,
)
from backtesting.file_runner import DATA_MANIFEST_SCHEMA, _json_bytes
from backtesting.market_data import (
    CanonicalTimeframe, GapPolicy, HistoricalCandle, normalize_hyperliquid_candle,
    validate_dataset,
)


ARCHIVE_SCHEMA = "backtesting-forward-archive-v1"
TRANSACTION_SCHEMA = "backtesting-recorder-transaction-v1"


class ArchiveState(str, Enum):
    RECORDING = "RECORDING"
    STOPPED = "STOPPED"
    STALE = "STALE"
    GAPPED = "GAPPED"
    VALIDATED_SNAPSHOT = "VALIDATED_SNAPSHOT"


@dataclass(frozen=True)
class RecorderConfiguration:
    symbol: str
    timeframes: tuple[CanonicalTimeframe, ...]
    data_network: str
    output: Path
    poll_seconds: float = 15.0
    timeout_seconds: float = 15.0
    retry_limit: int = 3
    bootstrap_candles: int = 5000
    retry_base_seconds: float = 1.0
    retry_max_seconds: float = 30.0
    retry_jitter_fraction: float = 0.20
    cycle_failure_limit: int = 3
    gap_backfill_limit: int = 8


@dataclass(frozen=True)
class RecorderEvent:
    timestamp: datetime
    level: str
    event: str
    state: str | None
    symbol: str
    timeframe: str | None = None
    details: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict:
        return {
            "timestamp": _stamp(self.timestamp), "level": self.level,
            "event": self.event, "state": self.state, "symbol": self.symbol,
            "timeframe": self.timeframe, "details": dict(self.details),
        }


class JsonLineEventSink:
    """Append-only structured recorder log containing approved fields only."""

    def __init__(self, path: Path):
        self.path = path

    def __call__(self, event: RecorderEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(event.as_dict(), sort_keys=True,
                             separators=(",", ":"), ensure_ascii=True) + "\n"
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())


def _decode(raw: bytes) -> list[dict]:
    value = json.loads(raw.decode("utf-8"), parse_float=str, parse_int=int)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("malformed public candle response")
    return value


def _canonical(row: dict, *, timeframe: CanonicalTimeframe, dataset_id: str,
               source: str) -> HistoricalCandle:
    required = {"t", "T", "s", "i", "o", "h", "l", "c"}
    if not required <= set(row):
        raise ValueError("malformed public candle fields")
    duration = int(timeframe.duration.total_seconds() * 1000)
    normalized = dict(row)
    if normalized["T"] == normalized["t"] + duration - 1:
        normalized["T"] += 1
    return normalize_hyperliquid_candle(
        {**normalized, "is_closed": True}, dataset_id=dataset_id,
        schema_version=CANDLE_SCHEMA, source=source, exchange="hyperliquid",
    )


class ForwardCandleRecorder:
    """Public REST polling archive. It owns no strategy or trading behavior."""

    def __init__(self, *, configuration: RecorderConfiguration,
                 transport=None, now=None, sleeper=time.sleep, jitter=None,
                 event_sink=None, alert_hook=None):
        self.configuration = configuration
        self.transport = transport or PublicCandleTransport()
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.sleeper = sleeper
        self.jitter = jitter or random.random
        self.event_sink = event_sink
        self.alert_hook = alert_hook
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        c = self.configuration
        if not c.symbol.strip() or c.symbol != c.symbol.upper():
            raise ValueError("symbol must be explicit uppercase text")
        if c.data_network not in PUBLIC_URLS:
            raise ValueError("unsupported public data network")
        if not c.timeframes or len(set(c.timeframes)) != len(c.timeframes):
            raise ValueError("timeframes must be unique and nonempty")
        if (c.poll_seconds < 0 or c.timeout_seconds <= 0 or c.retry_limit < 0
                or c.retry_base_seconds < 0 or c.retry_max_seconds <= 0
                or c.retry_base_seconds > c.retry_max_seconds
                or not 0 <= c.retry_jitter_fraction <= 1
                or c.cycle_failure_limit < 1 or c.gap_backfill_limit < 0):
            raise ValueError("recorder timing/retry configuration is invalid")

    @property
    def manifest_path(self) -> Path:
        return self.configuration.output / "archive_manifest.json"

    @property
    def transaction_path(self) -> Path:
        return self.configuration.output / "recorder_transaction.json"

    @property
    def transaction_directory(self) -> Path:
        return self.configuration.output / ".recorder_transaction"

    def _emit(self, event: str, *, level: str = "INFO",
              state: ArchiveState | None = None,
              timeframe: CanonicalTimeframe | None = None,
              alert: bool = False, **details) -> None:
        record = RecorderEvent(
            self.now().astimezone(timezone.utc), level, event,
            state.value if state else None, self.configuration.symbol,
            timeframe.value if timeframe else None,
            tuple(sorted((str(key), str(value)) for key, value in details.items())),
        )
        if self.event_sink is not None:
            self.event_sink(record)
        if alert and self.alert_hook is not None:
            self.alert_hook(record)

    def _delay(self, attempt: int) -> float:
        base = min(self.configuration.retry_base_seconds * (2 ** attempt),
                   self.configuration.retry_max_seconds)
        spread = base * self.configuration.retry_jitter_fraction
        return max(0.0, base + spread * (2 * float(self.jitter()) - 1))

    @staticmethod
    def _is_transient(error: BaseException) -> bool:
        if isinstance(error, urllib.error.HTTPError):
            return error.code in (408, 425, 429, 500, 502, 503, 504)
        return isinstance(error, (TimeoutError, ConnectionError,
                                  urllib.error.URLError, ssl.SSLError, OSError))

    def _request(self, timeframe: CanonicalTimeframe, start: datetime,
                 end: datetime) -> list[dict]:
        body = json.dumps({"type": "candleSnapshot", "req": {
            "coin": self.configuration.symbol, "interval": timeframe.value,
            "startTime": _ms(start), "endTime": _ms(end),
        }}, separators=(",", ":"), sort_keys=True).encode()
        for attempt in range(self.configuration.retry_limit + 1):
            try:
                return _decode(self.transport.post(
                    url=PUBLIC_URLS[self.configuration.data_network], payload=body,
                    timeout=self.configuration.timeout_seconds,
                ))
            except Exception as error:
                if not self._is_transient(error) or attempt >= self.configuration.retry_limit:
                    raise
                delay = self._delay(attempt)
                self._emit("request_retry", level="WARNING", timeframe=timeframe,
                           attempt=attempt + 1, delay_seconds=format(delay, ".6f"),
                           error_type=type(error).__name__)
                self.sleeper(delay)
        raise RuntimeError("bounded recorder retry exhausted")

    @staticmethod
    def _read(path: Path, *, timeframe: CanonicalTimeframe,
              dataset_id: str, source: str) -> tuple[HistoricalCandle, ...]:
        if not path.exists():
            return ()
        rows = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != CSV_FIELDS:
                raise ValueError("archive CSV schema is corrupt")
            for item in reader:
                opened = datetime.fromisoformat(item["open_time"].replace("Z", "+00:00"))
                closed = datetime.fromisoformat(item["close_time"].replace("Z", "+00:00"))
                rows.append(_canonical({
                    "s": item["symbol"], "i": item["timeframe"],
                    "t": _ms(opened), "T": _ms(closed), "o": item["open"],
                    "h": item["high"], "l": item["low"], "c": item["close"],
                    "v": item["volume"] or None,
                }, timeframe=timeframe, dataset_id=dataset_id, source=source))
        return tuple(rows)

    @staticmethod
    def _csv_bytes(candles: tuple[HistoricalCandle, ...]) -> bytes:
        handle = io.StringIO(newline="")
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_FIELDS)
        for c in candles:
            writer.writerow((c.symbol, c.timeframe.value, _stamp(c.open_time),
                _stamp(c.close_time), format(c.open, "f"), format(c.high, "f"),
                format(c.low, "f"), format(c.close, "f"),
                "" if c.volume is None else format(c.volume, "f"), "true"))
        return handle.getvalue().encode("utf-8")

    @staticmethod
    def _atomic_bytes(path: Path, payload: bytes) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)

    @classmethod
    def _write(cls, path: Path, candles: tuple[HistoricalCandle, ...]) -> None:
        cls._atomic_bytes(path, cls._csv_bytes(candles))

    def _clear_transaction(self) -> None:
        if self.transaction_path.exists(): self.transaction_path.unlink()
        if self.transaction_directory.exists():
            shutil.rmtree(self.transaction_directory)

    def _recover_transaction(self) -> None:
        staging = self.transaction_directory
        if not self.transaction_path.exists():
            if staging.exists():
                shutil.rmtree(staging)
                self._emit("orphan_staging_removed", level="WARNING")
            return
        value = json.loads(self.transaction_path.read_text(encoding="utf-8"))
        if (value.get("schema_version") != TRANSACTION_SCHEMA
                or value.get("symbol") != self.configuration.symbol
                or value.get("archive_schema") != ARCHIVE_SCHEMA):
            raise ValueError("recorder transaction identity/version is incompatible")
        manifest_payload = (staging / "archive_manifest.json").read_bytes()
        if sha256(manifest_payload).hexdigest() != value.get("manifest_sha256"):
            raise ValueError("recorder transaction manifest checksum mismatch")
        for name, expected in value.get("new_checksums", {}).items():
            staged = staging / name
            if not staged.is_file() or sha256(staged.read_bytes()).hexdigest() != expected:
                raise ValueError("recorder transaction staged checksum mismatch")
            target = self.configuration.output / name
            current = sha256(target.read_bytes()).hexdigest() if target.is_file() else None
            old = value.get("old_checksums", {}).get(name)
            if current not in (old, expected):
                raise ValueError("recorder transaction target conflicts with recovery")
            if current != expected:
                self._atomic_bytes(target, staged.read_bytes())
        self._atomic_bytes(self.manifest_path, manifest_payload)
        self._clear_transaction()
        self._emit("transaction_recovered", level="WARNING")

    def _load_manifest(self) -> dict:
        self._recover_transaction()
        if not self.manifest_path.exists():
            if self.configuration.output.exists() and any(
                self.configuration.output.glob("*.csv")
            ):
                raise ValueError("archive manifest missing for existing candle files")
            return {"schema_version": ARCHIVE_SCHEMA,
                "archive_id": sha256((ARCHIVE_SCHEMA + self.configuration.symbol
                    + self.configuration.data_network).encode()).hexdigest(),
                "symbol": self.configuration.symbol,
                "timeframes": [item.value for item in self.configuration.timeframes],
                "data_network": self.configuration.data_network,
                "source": f"hyperliquid-public-{self.configuration.data_network}",
                "candle_schema_version": CANDLE_SCHEMA,
                "state": ArchiveState.STOPPED.value, "checksums": {}, "streams": {}}
        value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        expected = (ARCHIVE_SCHEMA, self.configuration.symbol,
                    [item.value for item in self.configuration.timeframes],
                    self.configuration.data_network, CANDLE_SCHEMA)
        actual = (value.get("schema_version"), value.get("symbol"),
                  value.get("timeframes"), value.get("data_network"),
                  value.get("candle_schema_version"))
        if actual != expected:
            raise ValueError("archive identity/version is incompatible")
        for name, digest in value.get("checksums", {}).items():
            path = self.configuration.output / name
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("archive checksum verification failed")
        return value

    def _commit(self, manifest: dict, *, state: ArchiveState,
                streams: dict, files: dict[str, bytes] | None = None) -> dict:
        files = files or {}; checksums = {}
        for timeframe in self.configuration.timeframes:
            path = self.configuration.output / f"{self.configuration.symbol}_{timeframe.value}.csv"
            if path.name in files: checksums[path.name] = sha256(files[path.name]).hexdigest()
            elif path.exists(): checksums[path.name] = sha256(path.read_bytes()).hexdigest()
        result = {**manifest, "state": state.value, "updated_at": _stamp(self.now()),
                  "streams": streams, "checksums": checksums}
        previous_state = manifest.get("state")
        if files:
            if self.transaction_path.exists() or self.transaction_directory.exists():
                raise ValueError("unrecovered recorder transaction exists")
            self.transaction_directory.mkdir()
            for name, payload in files.items():
                self._atomic_bytes(self.transaction_directory / name, payload)
            manifest_payload = _json_bytes(result)
            self._atomic_bytes(self.transaction_directory / "archive_manifest.json",
                               manifest_payload)
            transaction = {"schema_version": TRANSACTION_SCHEMA,
                "archive_schema": ARCHIVE_SCHEMA, "symbol": self.configuration.symbol,
                "old_checksums": manifest.get("checksums", {}),
                "new_checksums": {name: sha256(payload).hexdigest()
                                  for name, payload in files.items()},
                "manifest_sha256": sha256(manifest_payload).hexdigest()}
            self._atomic_bytes(self.transaction_path, _json_bytes(transaction))
            for name, payload in files.items():
                self._atomic_bytes(self.configuration.output / name, payload)
            self._atomic_bytes(self.manifest_path, manifest_payload)
            self._clear_transaction()
        else:
            self._atomic_bytes(self.manifest_path, _json_bytes(result))
        if previous_state != state.value:
            alert = state in (ArchiveState.STALE, ArchiveState.GAPPED)
            self._emit("archive_state_changed", level="WARNING" if alert else "INFO",
                       state=state, alert=alert, previous_state=previous_state or "NONE")
        return result

    def _merge_rows(self, existing: tuple[HistoricalCandle, ...], rows: list[dict],
                    *, timeframe: CanonicalTimeframe, dataset_id: str,
                    source: str, start: datetime, end: datetime,
                    now: datetime) -> tuple[HistoricalCandle, ...]:
        by_open = {item.open_time: item for item in existing}
        for row in rows:
            candle = _canonical(row, timeframe=timeframe,
                                dataset_id=dataset_id, source=source)
            if candle.symbol != self.configuration.symbol or candle.timeframe != timeframe:
                raise ValueError("response identity mismatch")
            # Hyperliquid's endTime is inclusive. A polling request whose end
            # falls inside the active interval therefore returns that forming
            # candle (or, when aligned, the candle opening exactly at end).
            # Validate the complete record and identity first, then exclude
            # only those two precisely-owned boundary cases. Every other
            # out-of-window/future record remains an error.
            if candle.open_time == end:
                self._emit("inclusive_end_candle_excluded", timeframe=timeframe,
                           open_time=_stamp(candle.open_time),
                           close_time=_stamp(candle.close_time))
                continue
            if (end == now and start <= candle.open_time < end
                    and end < candle.close_time and candle.close_time > now):
                self._emit("forming_candle_excluded", timeframe=timeframe,
                           open_time=_stamp(candle.open_time),
                           close_time=_stamp(candle.close_time),
                           requested_end=_stamp(end))
                continue
            if not (start <= candle.open_time and candle.close_time <= end):
                self._emit("response_boundary_rejected", level="ERROR",
                    timeframe=timeframe, requested_start=_stamp(start),
                    requested_end=_stamp(end), open_time=_stamp(candle.open_time),
                    close_time=_stamp(candle.close_time))
                raise ValueError("response outside requested recorder window")
            if candle.close_time > now:
                self._emit("future_candle_rejected", level="ERROR",
                    timeframe=timeframe, visibility_time=_stamp(now),
                    open_time=_stamp(candle.open_time),
                    close_time=_stamp(candle.close_time))
                raise ValueError("future candle outside recorder visibility")
            prior = by_open.get(candle.open_time)
            if prior is not None and prior != candle:
                raise ValueError("conflicting/forked archive candle")
            by_open[candle.open_time] = candle
        return tuple(by_open[key] for key in sorted(by_open))

    def poll_once(self) -> dict:
        output = self.configuration.output
        output.mkdir(parents=True, exist_ok=True)
        manifest = self._load_manifest(); dataset_id = manifest["archive_id"]
        source = manifest["source"]; now = self.now().astimezone(timezone.utc)
        all_streams = {}; any_gap = False; any_stale = False; pending_files = {}
        for timeframe in self.configuration.timeframes:
            path = output / f"{self.configuration.symbol}_{timeframe.value}.csv"
            existing = self._read(path, timeframe=timeframe,
                                  dataset_id=dataset_id, source=source)
            start = (existing[-1].close_time if existing else
                     now - timeframe.duration * self.configuration.bootstrap_candles)
            rows = self._request(timeframe, start, now)
            merged = self._merge_rows(existing, rows, timeframe=timeframe,
                dataset_id=dataset_id, source=source, start=start, end=now, now=now)
            if merged:
                validated = validate_dataset(
                    merged, dataset_id=dataset_id, schema_version=CANDLE_SCHEMA,
                    source=source, exchange="hyperliquid", gap_policy=GapPolicy.RECORD,
                    validation_time=now,
                )
                attempts = 0
                for gap in validated.gaps:
                    if attempts >= self.configuration.gap_backfill_limit: break
                    attempts += 1
                    gap_rows = self._request(timeframe, gap.expected_open_time,
                                             gap.actual_open_time)
                    merged = self._merge_rows(merged, gap_rows, timeframe=timeframe,
                        dataset_id=dataset_id, source=source,
                        start=gap.expected_open_time, end=gap.actual_open_time, now=now)
                    self._emit("gap_backfill_attempt", level="WARNING",
                        timeframe=timeframe, gap_start=_stamp(gap.expected_open_time),
                        gap_end=_stamp(gap.actual_open_time))
                validated = validate_dataset(merged, dataset_id=dataset_id,
                    schema_version=CANDLE_SCHEMA, source=source,
                    exchange="hyperliquid", gap_policy=GapPolicy.RECORD,
                    validation_time=now)
                any_gap = any_gap or bool(validated.gaps)
                latest = merged[-1].close_time
                any_stale = any_stale or now - latest > timeframe.duration * 2
                pending_files[path.name] = self._csv_bytes(merged)
                all_streams[timeframe.value] = {
                    "count": len(merged), "earliest": _stamp(merged[0].open_time),
                    "latest_close": _stamp(latest), "gap_count": len(validated.gaps),
                    "stale": now - latest > timeframe.duration * 2,
                    "backfill_attempts": attempts,
                }
            else:
                any_stale = True
                all_streams[timeframe.value] = {"count": 0, "earliest": None,
                                                "latest_close": None, "gap_count": 0}
        state = ArchiveState.GAPPED if any_gap else (
            ArchiveState.STALE if any_stale else ArchiveState.RECORDING)
        return self._commit(manifest, state=state, streams=all_streams,
                            files=pending_files)

    def run(self, *, max_cycles: int | None = None) -> dict:
        cycles = 0; failures = 0; result = None
        try:
            while max_cycles is None or cycles < max_cycles:
                cycles += 1
                try:
                    result = self.poll_once(); failures = 0
                    self._emit("poll_complete", state=ArchiveState(result["state"]),
                               cycle=cycles)
                except Exception as error:
                    if not self._is_transient(error): raise
                    failures += 1
                    self._emit("poll_reconnect", level="WARNING", failures=failures,
                               error_type=type(error).__name__)
                    if failures >= self.configuration.cycle_failure_limit:
                        manifest = self._load_manifest()
                        result = self._commit(manifest, state=ArchiveState.STALE,
                            streams=manifest.get("streams", {}))
                    if max_cycles is not None and cycles >= max_cycles: break
                if max_cycles is None or cycles < max_cycles:
                    self.sleeper(self.configuration.poll_seconds)
            if result is None:
                raise RuntimeError("recorder ended without a health result")
            return result
        except KeyboardInterrupt:
            manifest = self._load_manifest()
            return self._commit(manifest, state=ArchiveState.STOPPED,
                                streams=manifest.get("streams", {}))
        except Exception as error:
            manifest = self._load_manifest()
            stopped = self._commit(manifest, state=ArchiveState.STOPPED,
                                   streams=manifest.get("streams", {}))
            self._emit("recorder_stopped_unexpectedly", level="ERROR",
                       state=ArchiveState.STOPPED, alert=True,
                       error_type=type(error).__name__)
            raise

    def stop(self) -> dict:
        manifest = self._load_manifest()
        return self._commit(manifest, state=ArchiveState.STOPPED,
                            streams=manifest.get("streams", {}))


def freeze_snapshot(*, archive: Path, output: Path, start: datetime,
                    end: datetime, overwrite: bool = False) -> Path:
    manifest_path = archive / "archive_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("verified archive manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = RecorderConfiguration(manifest["symbol"],
        tuple(CanonicalTimeframe(item) for item in manifest["timeframes"]),
        manifest["data_network"], archive)
    recorder = ForwardCandleRecorder(configuration=config)
    verified = recorder._load_manifest()
    if output.exists() and not overwrite:
        raise FileExistsError("snapshot output exists; use --overwrite")
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        raise FileExistsError("snapshot temporary output already exists")
    temporary.mkdir(parents=True)
    try:
        mappings=[]; checks={}; all_candles=[]
        for timeframe in config.timeframes:
            candles = recorder._read(archive / f"{config.symbol}_{timeframe.value}.csv",
                                     timeframe=timeframe, dataset_id=verified["archive_id"],
                                     source=verified["source"])
            selected = tuple(item for item in candles
                             if start <= item.open_time and item.close_time <= end)
            if not selected or selected[0].open_time != start or selected[-1].close_time != end:
                raise ValueError(f"snapshot {timeframe.value} boundary coverage incomplete")
            validate_dataset(selected, dataset_id=verified["archive_id"],
                schema_version=CANDLE_SCHEMA, source=verified["source"],
                exchange="hyperliquid", gap_policy=GapPolicy.REJECT,
                validation_time=end)
            name=f"{config.symbol}_{timeframe.value}.csv"
            recorder._write(temporary/name, selected)
            checks[name]=sha256((temporary/name).read_bytes()).hexdigest()
            mappings.append({"timeframe":timeframe.value,"path":name})
            all_candles.extend(selected)
        dataset = validate_dataset(tuple(sorted(all_candles,
            key=lambda item:(item.open_time,item.timeframe.value,item.id))),
            dataset_id=verified["archive_id"],schema_version=CANDLE_SCHEMA,
            source=verified["source"],exchange="hyperliquid",
            gap_policy=GapPolicy.REJECT,validation_time=end)
        frozen={"schema_version":DATA_MANIFEST_SCHEMA,"dataset_id":verified["archive_id"],
            "candle_schema_version":CANDLE_SCHEMA,"source":verified["source"],
            "exchange":"hyperliquid","data_network":config.data_network,
            "gap_policy":"REJECT","validation_time":_stamp(end),
            "requested_start":_stamp(start),"requested_end":_stamp(end),
            "files":mappings,"gaps":[],"approved_exclusions":[],
            "checksums":checks,"dataset_fingerprint":dataset.fingerprint}
        (temporary/"dataset_manifest.json").write_bytes(_json_bytes(frozen))
        if output.exists():
            import shutil; shutil.rmtree(output)
        os.replace(temporary,output)
        return output/"dataset_manifest.json"
    except Exception:
        import shutil; shutil.rmtree(temporary,ignore_errors=True); raise
