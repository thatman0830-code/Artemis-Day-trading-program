from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterator

from .models import CORE_V1_VERSION, CoreBar, CoreEvent, EventType, fingerprint, require_utc


PASS_B_SCHEMA = "es-nq-pass-b-backfill-v3"
BTC_SCHEMA = "backtesting-public-download-v1"


class ArchiveEligibility(str, Enum):
    SMOKE_REPLAY = "SMOKE_REPLAY"
    TRAINING_VALIDATION = "TRAINING_VALIDATION"
    UNTOUCHED_OOS = "UNTOUCHED_OOS"
    FINAL_ACCEPTANCE = "FINAL_ACCEPTANCE"


@dataclass(frozen=True)
class EligibilityFlags:
    smoke_replay: bool
    training_validation: bool
    untouched_oos: bool
    final_acceptance: bool
    classification: str

    def permits(self, purpose: ArchiveEligibility) -> bool:
        return {
            ArchiveEligibility.SMOKE_REPLAY: self.smoke_replay,
            ArchiveEligibility.TRAINING_VALIDATION: self.training_validation,
            ArchiveEligibility.UNTOUCHED_OOS: self.untouched_oos,
            ArchiveEligibility.FINAL_ACCEPTANCE: self.final_acceptance,
        }[purpose]


@dataclass(frozen=True)
class DataQualityEvent:
    id: str
    market: str
    instrument_id: str
    contract_id: str | None
    session_id: str
    start_inclusive: datetime
    end_exclusive: datetime
    missing_intervals: int
    reason: str
    source_request_id: str
    dataset_fingerprint: str


@dataclass(frozen=True)
class SourceLineage:
    schema_version: str
    plan_id: str | None
    continuation_plan_id: str | None
    calendar_sha256: str | None
    rollover_sha256: str | None
    archive_sha256: str
    manifest_sha256: str


@dataclass(frozen=True)
class AdapterMetadata:
    adapter_version: str
    dataset_id: str
    dataset_fingerprint: str
    markets: tuple[str, ...]
    instruments: tuple[str, ...]
    coverage_start: datetime
    coverage_end_exclusive: datetime
    lineage: SourceLineage
    eligibility: EligibilityFlags


@dataclass(frozen=True)
class CoreMarketDataEvent:
    event: CoreEvent
    bar: CoreBar


def _bytes(path: Path) -> bytes:
    # This is deliberately the only file access primitive: read-only binary.
    with path.open("rb") as handle:
        return handle.read()


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict:
    value = json.loads(_bytes(path).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object JSON required: {path.name}")
    return value


def _utc(text: str) -> datetime:
    if not isinstance(text, str) or not text.endswith("Z"):
        raise ValueError("canonical UTC Z timestamp required")
    value = datetime.fromisoformat(text[:-1] + "+00:00")
    require_utc(value)
    return value


def _ns_utc(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("integer nanosecond timestamp required")
    seconds, nanos = divmod(value, 1_000_000_000)
    if nanos % 1_000 != 0:
        raise ValueError("timestamp precision exceeds Core datetime contract")
    return datetime.fromtimestamp(seconds, timezone.utc).replace(microsecond=nanos // 1_000)


def _epoch_minute(value: datetime) -> int:
    require_utc(value)
    delta = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    seconds = delta.days * 86400 + delta.seconds
    if delta.microseconds or seconds % 60:
        raise ValueError("calendar interval must be minute-aligned")
    return seconds // 60


def _safe_child(base: Path, relative: str) -> Path:
    if not isinstance(relative, str): raise TypeError("relative path required")
    result = (base / relative).resolve()
    if base.resolve() not in result.parents:
        raise ValueError("manifest path escapes archive")
    return result


class PassBV3ArchiveAdapter:
    """Streaming read-only adapter over one promoted ES or NQ Pass B v3 market."""

    adapter_version = "core-v1-pass-b-v3-adapter-1"

    def __init__(self, *, repository_root: Path, market: str, archive_root: Path,
                 plan_root: Path, continuation_root: Path, final_audit_path: Path):
        if market not in ("ES", "NQ"): raise ValueError("Pass B supports exact ES or NQ only")
        self.repository_root = repository_root.resolve(); self.market = market
        self.archive_root = archive_root.resolve(); self.plan_root = plan_root.resolve()
        self.continuation_root = continuation_root.resolve(); self.final_audit_path = final_audit_path.resolve()
        self._metadata: AdapterMetadata | None = None
        self._quality: tuple[DataQualityEvent, ...] = ()

    def _audit_hash(self, audit: dict, path: Path) -> None:
        relative = path.resolve().relative_to(self.repository_root).as_posix()
        expected = {row["path"]: row["sha256"] for row in audit.get("artifact_hashes", [])}
        if expected.get(relative) != _sha(path):
            raise ValueError(f"final archive audit hash mismatch: {relative}")

    def validate(self) -> AdapterMetadata:
        audit = _json(self.final_audit_path)
        if audit.get("state") != "FINAL_ES_NQ_ARCHIVE_AUDIT_PASS" or audit.get("continuous_adjustment") is not False:
            raise ValueError("archive is not a promoted unadjusted Pass B result")
        if Path(audit.get("archive_path", "")).resolve() != self.archive_root:
            raise ValueError("promoted archive identity mismatch")
        if any(path.name.lower().startswith(("staging", "failed", "superseded"))
               for path in self.archive_root.iterdir()):
            raise ValueError("unpromoted archive artifact present")
        tree_payload = (json.dumps(sorted(audit.get("artifact_hashes", []), key=lambda x: x["path"]),
                                   sort_keys=True, separators=(",", ":")) + "\n").encode()
        if sha256(tree_payload).hexdigest() != audit.get("archive_tree_sha256"):
            raise ValueError("archive tree fingerprint mismatch")
        plan_manifest = _json(self.plan_root / "artifact_manifest.json")
        plan_path = self.plan_root / "plan.json"; calendar_path = self.plan_root / "calendar.json"
        rollover_path = self.plan_root / "rollovers.json"
        for name, path in (("plan.json", plan_path), ("calendar.json", calendar_path), ("rollovers.json", rollover_path)):
            if plan_manifest.get("sha256", {}).get(name) != _sha(path):
                raise ValueError(f"frozen plan artifact mismatch: {name}")
        plan = _json(plan_path); calendar = _json(calendar_path); rollovers = _json(rollover_path)
        plan_id = plan.get("id")
        if (plan.get("schema_version") != PASS_B_SCHEMA or plan_manifest.get("plan_id") != plan_id or
                audit.get("original_plan_id") != plan_id):
            raise ValueError("original plan identity/schema mismatch")
        continuation_manifest = _json(self.continuation_root / "artifact_manifest.json")
        continuation_path = self.continuation_root / "plan.json"
        if continuation_manifest.get("plan_sha256") != _sha(continuation_path):
            raise ValueError("continuation plan checksum mismatch")
        continuation = _json(continuation_path)
        if (continuation.get("id") != audit.get("continuation_plan_id") or
                continuation.get("original_plan_id") != plan_id):
            raise ValueError("continuation/original plan linkage mismatch")
        for path in (plan_path, self.plan_root / "artifact_manifest.json", continuation_path,
                     self.continuation_root / "artifact_manifest.json"):
            expected = audit.get("plan_hashes", {}).get(path.relative_to(self.repository_root).as_posix())
            if expected != _sha(path): raise ValueError("final audit plan hash mismatch")
        if calendar.get("schema_version") != PASS_B_SCHEMA or rollovers.get("schema_version") != PASS_B_SCHEMA:
            raise ValueError("calendar/rollover schema mismatch")
        requests = plan.get("markets", {}).get(self.market, {}).get("requests")
        windows = rollovers.get("markets", {}).get(self.market, {}).get("active_windows")
        if not isinstance(requests, list) or not requests or not isinstance(windows, list) or not windows:
            raise ValueError("market request inventory or active windows missing")
        expected_count = audit.get("markets", {}).get(self.market, {}).get("requests")
        if expected_count != len(requests): raise ValueError("request inventory count mismatch")
        session_map = {row["session_date"]: row for row in calendar.get("sessions", [])}
        if len(session_map) != len(calendar.get("sessions", [])): raise ValueError("duplicate calendar session")
        audit_artifacts = {row["path"]: row["sha256"] for row in audit.get("artifact_hashes", [])}
        quality: list[DataQualityEvent] = []; global_previous: datetime | None = None
        raw_bytes_total = normalized_bytes_total = 0
        sequence = 0; coverage_start = None; coverage_end = None
        for request in requests:
            rid = request.get("id")
            manifest_path = self.archive_root / self.market / "manifests" / f"{rid}.json"
            checkpoint_path = self.archive_root / self.market / "checkpoints" / f"{rid}.json"
            pending_path = self.archive_root / self.market / "pending" / f"{rid}.json"
            if not manifest_path.is_file() or not checkpoint_path.is_file() or not pending_path.is_file():
                raise ValueError("request manifest/checkpoint link missing")
            manifest = _json(manifest_path); checkpoint = _json(checkpoint_path); pending = _json(pending_path)
            if any(manifest.get(k) != request.get(k) for k in ("root", "ticker", "contract_id")):
                raise ValueError("request/manifest market identity mismatch")
            if (manifest.get("request_id") != rid or manifest.get("plan_id") != plan_id or
                    manifest.get("schema_version") != PASS_B_SCHEMA):
                raise ValueError("request manifest plan/schema mismatch")
            raw_path = _safe_child(self.archive_root / self.market, manifest.get("raw_relative_path"))
            normalized_path = _safe_child(self.archive_root / self.market, manifest.get("normalized_relative_path"))
            for path, hash_key, bytes_key in ((raw_path, "raw_sha256", "raw_bytes"),
                                               (normalized_path, "normalized_sha256", "normalized_bytes")):
                if not path.is_file() or path.stat().st_size != manifest.get(bytes_key) or _sha(path) != manifest.get(hash_key):
                    raise ValueError("request artifact checksum/byte mismatch")
                rel = path.relative_to(self.repository_root).as_posix()
                if audit_artifacts.get(rel) != manifest.get(hash_key):
                    raise ValueError("request artifact is not linked by final audit")
            raw_bytes_total += manifest["raw_bytes"]; normalized_bytes_total += manifest["normalized_bytes"]
            manifest_hash = _sha(manifest_path)
            if (checkpoint.get("request_id") != rid or checkpoint.get("plan_id") != plan_id or
                    checkpoint.get("manifest_sha256") != manifest_hash):
                raise ValueError("checkpoint chain mismatch")
            if pending.get("request_id") != rid or pending.get("raw_sha256") != manifest.get("raw_sha256"):
                raise ValueError("retained transaction descriptor conflict")
            self._audit_hash(audit, manifest_path); self._audit_hash(audit, checkpoint_path); self._audit_hash(audit, pending_path)
            raw = _json(raw_path); raw_by_key: dict[tuple, list[dict]] = {}
            for candidate in raw.get("results", []):
                key = (candidate.get("ticker"), candidate.get("session_end_date"), int(candidate["window_start"]))
                raw_by_key.setdefault(key, []).append(candidate)
            count = 0
            request_previous = None
            request_previous_session = None
            observed_minutes: dict[str, set[int]] = {s: set() for s in request.get("sessions", ())}
            with normalized_path.open("r", encoding="utf-8", newline="") as handle:
                for line in handle:
                    count += 1
                    row = json.loads(line)
                    if not isinstance(row, dict) or row.get("schema_version") != PASS_B_SCHEMA:
                        raise ValueError("normalized row schema mismatch")
                    expected = {"root": self.market, "ticker": request["ticker"],
                                "contract_id": request["contract_id"], "plan_id": plan_id}
                    if any(row.get(key) != value for key, value in expected.items()):
                        raise ValueError("normalized row market/contract/plan mismatch")
                    timestamp = _ns_utc(row.get("window_start_ns"))
                    if request_previous is not None and timestamp <= request_previous:
                        raise ValueError("duplicate or out-of-order normalized row")
                    if global_previous is not None and timestamp <= global_previous:
                        raise ValueError("cross-request duplicate or out-of-order row")
                    session_id = row.get("session_date")
                    if session_id not in request.get("sessions", ()) or session_id not in session_map:
                        raise ValueError("row session date conflicts with request/calendar")
                    intervals = session_map[session_id].get("active_intervals", [])
                    if sum(_utc(i["start_utc"]) <= timestamp < _utc(i["end_exclusive_utc"]) for i in intervals) != 1:
                        raise ValueError("row timestamp is outside its verified session")
                    matching = [w for w in windows if w.get("contract_id") == row["contract_id"] and
                                date.fromisoformat(w["start"]) <= date.fromisoformat(session_id) < date.fromisoformat(w["end_exclusive"])]
                    if len(matching) != 1 or matching[0].get("ticker") != row["ticker"]:
                        raise ValueError("row does not map to exactly one active-contract window")
                    for field in ("open", "high", "low", "close", "volume"):
                        value = Decimal(row[field])
                        if not value.is_finite(): raise ValueError("non-finite normalized economic value")
                    economic = {field: Decimal(row[field]) for field in ("open","high","low","close","volume")}
                    if (economic["volume"] < 0 or min(economic["open"], economic["close"]) < economic["low"] or
                            max(economic["open"], economic["close"]) > economic["high"] or economic["low"] > economic["high"]):
                        raise ValueError("normalized OHLCV geometry invalid")
                    candidates = raw_by_key.get((row["ticker"], session_id, row["window_start_ns"]), ())
                    if not any(all(Decimal(str(candidate[field])) == value for field, value in economic.items())
                               for candidate in candidates):
                        raise ValueError("normalized row lacks exact raw-response lineage")
                    observed_minutes[session_id].add(row["window_start_ns"] // 60_000_000_000)
                    request_previous = timestamp; request_previous_session = session_id
                    global_previous = timestamp; sequence += 1
                    coverage_start = timestamp if coverage_start is None else min(coverage_start, timestamp)
                    coverage_end = timestamp + timedelta(minutes=1)
            if count != manifest.get("normalized_rows"):
                raise ValueError("normalized row count mismatch")
            missing_total = 0
            for session_id, observed in observed_minutes.items():
                expected: list[int] = []
                for interval in session_map[session_id]["active_intervals"]:
                    cursor = _utc(interval["start_utc"])
                    end = _utc(interval["end_exclusive_utc"])
                    while cursor < end:
                        expected.append(_epoch_minute(cursor)); cursor += timedelta(minutes=1)
                missing_values = sorted(set(expected) - observed); missing_total += len(missing_values)
                start = previous = None
                for minute in missing_values + [None]:
                    if start is None and minute is not None: start = previous = minute; continue
                    if minute is not None and minute == previous + 1: previous = minute; continue
                    if start is not None:
                        begin = datetime.fromtimestamp(start*60, timezone.utc)
                        finish = datetime.fromtimestamp((previous+1)*60, timezone.utc)
                        quality.append(DataQualityEvent(fingerprint((rid, session_id, start, previous)), self.market,
                            request["ticker"], request["contract_id"], session_id, begin, finish,
                            previous-start+1, "SPARSE_NO_ELIGIBLE_TRADE_AGGREGATE", rid, "PENDING"))
                    start = previous = minute
            if missing_total != manifest.get("missing_aggregate_minutes"):
                raise ValueError("sparse missing-minute classification mismatch")
        market_audit = audit.get("markets", {}).get(self.market, {})
        if (sequence != market_audit.get("rows") or raw_bytes_total != market_audit.get("raw_bytes") or
                normalized_bytes_total != market_audit.get("normalized_bytes")):
            raise ValueError("market totals conflict with final archive audit")
        archive_fingerprint = audit.get("archive_tree_sha256")
        dataset_fingerprint = fingerprint((self.adapter_version, self.market, archive_fingerprint,
            plan_id, continuation.get("id"), _sha(calendar_path), _sha(rollover_path), sequence))
        self._quality = tuple(DataQualityEvent(q.id, q.market, q.instrument_id, q.contract_id, q.session_id,
            q.start_inclusive, q.end_exclusive, q.missing_intervals, q.reason, q.source_request_id,
            dataset_fingerprint) for q in quality)
        self._metadata = AdapterMetadata(self.adapter_version,
            fingerprint(("PASS_B_V3", self.market, plan_id)), dataset_fingerprint, (self.market,),
            tuple(sorted({r["ticker"] for r in requests})), coverage_start, coverage_end,
            SourceLineage(PASS_B_SCHEMA, plan_id, continuation.get("id"), _sha(calendar_path),
                _sha(rollover_path), archive_fingerprint, _sha(self.final_audit_path)),
            EligibilityFlags(True, True, True, False, "VERIFIED_RESEARCH_ARCHIVE"))
        return self._metadata

    @property
    def metadata(self) -> AdapterMetadata:
        return self._metadata or self.validate()

    @property
    def data_quality_events(self) -> tuple[DataQualityEvent, ...]:
        if self._metadata is None: self.validate()
        return self._quality

    def iter_events(self) -> Iterator[CoreMarketDataEvent]:
        metadata = self.metadata
        plan = _json(self.plan_root / "plan.json"); rollovers = _json(self.plan_root / "rollovers.json")
        windows = rollovers["markets"][self.market]["active_windows"]
        sequence = 0
        for request in plan["markets"][self.market]["requests"]:
            rid = request["id"]; manifest_path = self.archive_root / self.market / "manifests" / f"{rid}.json"
            manifest = _json(manifest_path)
            normalized_path = _safe_child(self.archive_root / self.market, manifest["normalized_relative_path"])
            previous = None; previous_session = None
            with normalized_path.open("r", encoding="utf-8", newline="") as handle:
                for line in handle:
                    row = json.loads(line); opened = _ns_utc(row["window_start_ns"])
                    missing = 0 if previous is None or previous_session != row["session_date"] else max(
                        0, int((opened-previous)/timedelta(minutes=1))-1)
                    window = next(w for w in windows if w["contract_id"] == row["contract_id"] and
                        date.fromisoformat(w["start"]) <= date.fromisoformat(row["session_date"]) < date.fromisoformat(w["end_exclusive"]))
                    bar_id = fingerprint((metadata.dataset_fingerprint, rid, row["contract_id"], row["window_start_ns"]))
                    bar = CoreBar(bar_id, self.market, row["ticker"], row["contract_id"], opened,
                        opened+timedelta(minutes=1), *(Decimal(row[k]) for k in ("open", "high", "low", "close", "volume")),
                        row["session_date"], rid, PASS_B_SCHEMA, manifest["normalized_sha256"], sequence,
                        True, missing, window.get("roll_decision_id"), metadata.dataset_fingerprint)
                    event = CoreEvent(fingerprint((bar.id, "finalized")), EventType.FINALIZED_MARKET_BAR,
                        bar.close_time, self.market, bar.instrument_id, bar.contract_id, bar.session_id,
                        rid, manifest["normalized_sha256"], sequence)
                    yield CoreMarketDataEvent(event, bar)
                    previous = opened; previous_session = row["session_date"]; sequence += 1

    def rollover_events(self) -> tuple[CoreEvent, ...]:
        metadata = self.metadata
        rollovers = _json(self.plan_root / "rollovers.json")["markets"][self.market]
        calendar = {row["session_date"]: row for row in _json(self.plan_root / "calendar.json")["sessions"]}
        windows = rollovers["active_windows"]
        ticker_by_contract = {row["contract_id"]: row["ticker"] for row in windows}
        events = []
        for sequence, decision in enumerate(rollovers.get("decisions", [])):
            effective = calendar[decision["effective_session"]]["active_intervals"][0]["start_utc"]
            common = (self.market, decision["id"], metadata.lineage.rollover_sha256)
            events.append(CoreEvent(fingerprint((decision["id"],"decision")), EventType.ROLLOVER_DECISION,
                _utc(decision["decision_time"]), self.market, ticker_by_contract[decision["outgoing_id"]],
                decision["outgoing_id"], decision["decision_session"], decision["id"],
                metadata.lineage.rollover_sha256 or "", sequence))
            events.append(CoreEvent(fingerprint((decision["id"],"effective")), EventType.ROLLOVER_EFFECTIVE,
                _utc(effective), self.market, ticker_by_contract[decision["incoming_id"]],
                decision["incoming_id"], decision["effective_session"], decision["id"],
                metadata.lineage.rollover_sha256 or "", sequence))
        return tuple(sorted(events,key=lambda event:event.ordering_key))


class BTCPhase7PartialAdapter:
    adapter_version = "core-v1-btc-phase7-partial-adapter-1"

    def __init__(self, archive_root: Path):
        self.archive_root = archive_root.resolve(); self._metadata = None; self._quality = ()

    def validate(self) -> AdapterMetadata:
        manifest_path = self.archive_root / "partial_manifest.json"; manifest = _json(manifest_path)
        if manifest.get("schema_version") != BTC_SCHEMA: raise ValueError("BTC partial schema mismatch")
        entry = manifest.get("completed", {}).get("1m")
        if not isinstance(entry, dict): raise ValueError("completed BTC 1m entry missing")
        path = self.archive_root / "BTC_1m.csv"; before = _sha(path)
        if before != entry.get("sha256"): raise ValueError("BTC completed file checksum mismatch")
        through = _utc(entry.get("through")); first = last = previous = None; count = 0; quality = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"symbol","timeframe","open_time","close_time","open","high","low","close","volume","is_closed"}
            if set(reader.fieldnames or ()) != required: raise ValueError("BTC CSV schema mismatch")
            for row in reader:
                count += 1
                if row["symbol"] != "BTC" or row["timeframe"] != "1m" or row["is_closed"].lower() != "true":
                    raise ValueError("BTC row scope/closed-state mismatch")
                opened, closed = _utc(row["open_time"]), _utc(row["close_time"])
                if closed-opened != timedelta(minutes=1) or closed > through:
                    raise ValueError("BTC row interval/completion boundary mismatch")
                if previous is not None and opened <= previous:
                    raise ValueError("BTC duplicate or out-of-order row")
                for field in ("open","high","low","close","volume"):
                    if not Decimal(row[field]).is_finite(): raise ValueError("BTC non-finite value")
                values = {field: Decimal(row[field]) for field in ("open","high","low","close","volume")}
                if (values["volume"] < 0 or min(values["open"],values["close"]) < values["low"] or
                        max(values["open"],values["close"]) > values["high"] or values["low"] > values["high"]):
                    raise ValueError("BTC OHLCV geometry invalid")
                if previous is not None and opened-previous > timedelta(minutes=1):
                    missing = int((opened-previous)/timedelta(minutes=1))-1
                    quality.append((previous+timedelta(minutes=1), opened, missing))
                first = opened if first is None else first; last = closed; previous = opened
        if not count or last != through or _sha(path) != before:
            raise ValueError("BTC file changed or does not reach completed boundary")
        dataset_fp = fingerprint((self.adapter_version, manifest.get("request_id"), before, through, count))
        self._quality = tuple(DataQualityEvent(fingerprint((dataset_fp, a, b)), "BTC", "BTC", None,
            a.date().isoformat(), a, b, n, "MISSING_COMPLETED_ONE_MINUTE_ROW", manifest["request_id"], dataset_fp)
            for a,b,n in quality)
        self._metadata = AdapterMetadata(self.adapter_version,
            fingerprint(("BTC_PARTIAL", manifest["request_id"])), dataset_fp, ("BTC",), ("BTC",), first,
            through, SourceLineage(BTC_SCHEMA, None, None, None, None, before, _sha(manifest_path)),
            EligibilityFlags(True, False, False, False, "PARTIAL_RESEARCH_ONLY"))
        return self._metadata

    @property
    def metadata(self): return self._metadata or self.validate()
    @property
    def data_quality_events(self):
        if self._metadata is None: self.validate()
        return self._quality

    def iter_events(self) -> Iterator[CoreMarketDataEvent]:
        metadata = self.metadata; path = self.archive_root / "BTC_1m.csv"; previous = None
        with path.open("r", encoding="utf-8", newline="") as handle:
            for sequence, row in enumerate(csv.DictReader(handle)):
                opened = _utc(row["open_time"]); closed = _utc(row["close_time"])
                missing = 0 if previous is None else max(0, int((opened-previous)/timedelta(minutes=1))-1)
                bar_id = fingerprint((metadata.dataset_fingerprint, row["open_time"], sequence))
                bar = CoreBar(bar_id, "BTC", "BTC", None, opened, closed,
                    *(Decimal(row[k]) for k in ("open","high","low","close","volume")),
                    opened.date().isoformat(), metadata.lineage.manifest_sha256, BTC_SCHEMA,
                    metadata.lineage.archive_sha256, sequence, True, missing, None, metadata.dataset_fingerprint)
                event = CoreEvent(fingerprint((bar.id,"finalized")), EventType.FINALIZED_MARKET_BAR,
                    closed,"BTC","BTC",None,bar.session_id,bar.source_id,bar.source_checksum,sequence)
                yield CoreMarketDataEvent(event,bar); previous=opened
