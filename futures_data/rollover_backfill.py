from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, time as day_time, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Callable

from .aggregate_probe import ALLOWED_HOST, BASE_URL, CHICAGO, VENUE
from .backfill_preflight import _classify_contract_rows
from .contracts import identity

SCHEMA_VERSION = "es-nq-rollover-backfill-v1"
POLICY_VERSION = "OWNER_TWO_SESSION_VOLUME_CROSSOVER_V1"
ROOTS = ("ES", "NQ")
OVERLAP_SESSIONS = 5
SESSIONS_PER_REQUEST = 5
MINUTES_PER_SESSION = 1380
MAX_CALLS_PER_MINUTE = 4
MIN_CALL_INTERVAL_SECONDS = 15.0
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
SESSION_CALENDAR_VERSION = "OWNER_CME_ROLLOVER_CALENDAR_V1"
NON_ORDINARY_SESSIONS = frozenset({date(2025, 6, 19)})
PLAN_NAME = "es_nq_rollover_discovery_plan_3"
STAGING_NAME = "es_nq_rollover_discovery_staging_1"
RESULT_NAME = "es_nq_rollover_discovery_1"


class RolloverBackfillError(RuntimeError):
    pass


def _json_bytes(value: object) -> bytes:
    def convert(item: object):
        if hasattr(item, "__dataclass_fields__"):
            return asdict(item)
        if isinstance(item, (datetime, date)):
            return item.isoformat().replace("+00:00", "Z")
        if isinstance(item, Decimal):
            return format(item, "f")
        raise TypeError(type(item).__name__)
    return (json.dumps(value, sort_keys=True, indent=2, default=convert) + "\n").encode("utf-8")


def _atomic_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    if path.exists() or temporary.exists():
        raise RolloverBackfillError("pre-existing unverified file")
    with temporary.open("xb") as handle:
        handle.write(payload); handle.flush(); os.fsync(handle.fileno())
    os.rename(temporary, path)


@dataclass(frozen=True)
class ContractFact:
    id: str
    root: str
    ticker: str
    contract_month: int
    contract_year: int
    first_trade_date: date
    last_trade_date: date
    settlement_date: date
    venue: str
    provenance_sha256: tuple[str, ...]


@dataclass(frozen=True)
class PairPlan:
    id: str
    root: str
    outgoing_id: str
    outgoing_ticker: str
    incoming_id: str
    incoming_ticker: str
    sessions: tuple[date, ...]
    start_utc: datetime
    end_utc: datetime
    request_ids: tuple[str, str]


@dataclass(frozen=True)
class DailyVolumeFact:
    id: str
    pair_id: str
    contract_id: str
    ticker: str
    session: date
    volume: Decimal
    finalized_at: datetime
    source_request_id: str


@dataclass(frozen=True)
class FrozenRollDecision:
    id: str
    pair_id: str
    root: str
    outgoing_id: str
    incoming_id: str
    decision_session: date
    decision_time: datetime
    effective_session: date
    reason: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ActiveWindow:
    contract_id: str
    ticker: str
    start: date
    end_exclusive: date
    roll_decision_id: str | None


def _weekdays_before(last_trade: date, count: int) -> tuple[date, ...]:
    result = []
    cursor = last_trade - timedelta(days=1)
    while len(result) < count:
        if cursor.weekday() < 5 and cursor not in NON_ORDINARY_SESSIONS:
            result.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(sorted(result))


def _session_bounds(sessions: tuple[date, ...]) -> tuple[datetime, datetime]:
    start = datetime.combine(sessions[0] - timedelta(days=1), day_time(17), CHICAGO)
    end = datetime.combine(sessions[-1], day_time(16), CHICAGO)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _retained_rows(repository: Path, root: str) -> tuple[list[dict], dict[str, set[str]], datetime, date]:
    base = repository / "data/backtests" / f"{root.lower()}_backfill_preflight_1"
    rows: list[dict] = []
    provenance: dict[str, set[str]] = {}
    retrieved = set()
    first_nonempty = None
    for manifest_path in sorted((base / "manifests").glob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_path = base / manifest["raw_relative_path"]
        raw = raw_path.read_bytes()
        digest = sha256(raw).hexdigest()
        if digest != manifest["raw_response_sha256"]:
            raise RolloverBackfillError("metadata checksum conflict")
        payload = json.loads(raw.decode("utf-8"), parse_float=Decimal)
        if payload.get("status") != "OK" or not isinstance(payload.get("results"), list):
            raise RolloverBackfillError("retained metadata schema conflict")
        retrieved.add(datetime.fromisoformat(manifest["retrieved_at"].replace("Z", "+00:00")))
        if payload["results"] and first_nonempty is None:
            first_nonempty = date.fromisoformat(manifest["discovery_point_date"])
        for row in payload["results"]:
            rows.append(row)
            provenance.setdefault(str(row.get("ticker")), set()).add(digest)
    if len(retrieved) != 1 or first_nonempty is None:
        raise RolloverBackfillError("metadata as-of or availability boundary is ambiguous")
    return rows, provenance, next(iter(retrieved)), first_nonempty


def build_fixed_inventory(repository: Path, root: str) -> dict:
    rows, provenance, as_of, evidence_start = _retained_rows(repository, root)
    nominal_start = as_of - timedelta(days=366 * 2)
    history_end = as_of.date()  # current CME session is not presumed finalized
    accepted, exclusions = _classify_contract_rows(root, rows, start=nominal_start.date(), end=history_end)
    by_ticker = {item["ticker"]: item for item in accepted}
    ordered = sorted(by_ticker.values(), key=lambda x: (x["settlement_date"], x["ticker"]))
    useful = [x for x in ordered if date.fromisoformat(x["last_trade_date"]) >= evidence_start]
    chain = []
    for item in useful:
        chain.append(item)
        if date.fromisoformat(item["last_trade_date"]) >= history_end:
            break
    if not chain or date.fromisoformat(chain[-1]["last_trade_date"]) < history_end:
        raise RolloverBackfillError("front-contract coverage is incomplete")
    expected = []
    month, year = chain[0]["contract_month"], chain[0]["contract_year"]
    for _ in chain:
        expected.append((month, year))
        month += 3
        if month > 12:
            month -= 12; year += 1
    if [(x["contract_month"], x["contract_year"]) for x in chain] != expected:
        raise RolloverBackfillError("quarterly chain is non-contiguous")
    facts = []
    for item in chain:
        ticker = item["ticker"]
        contract_id = identity(SCHEMA_VERSION, root, ticker, item["first_trade_date"],
                               item["last_trade_date"], item["settlement_date"], VENUE)
        facts.append(ContractFact(contract_id, root, ticker, item["contract_month"], item["contract_year"],
            date.fromisoformat(item["first_trade_date"]), date.fromisoformat(item["last_trade_date"]),
            date.fromisoformat(item["settlement_date"]), VENUE, tuple(sorted(provenance[ticker]))))
    selected = {x.ticker for x in facts}
    far_future = sorted(x["ticker"] for x in useful if x["ticker"] not in selected)
    return {"schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION, "root": root,
        "as_of": as_of, "nominal_entitlement_start": nominal_start, "history_end_exclusive": history_end,
        "evidence_supported_start": evidence_start, "contracts": tuple(facts),
        "excluded": {"SPREAD_OR_COMBO_OBSERVATIONS": sum(1 for x in exclusions if x["category"] == "SPREAD_OR_COMBO"),
                     "FAR_FUTURE_CONTRACTS": far_future,
                     "PRE_EVIDENCE_HISTORY": [nominal_start.date().isoformat(), evidence_start.isoformat()]}}


def build_pass_a_plan(repository: Path) -> dict:
    inventories = {root: build_fixed_inventory(repository, root) for root in ROOTS}
    as_of = {x["as_of"] for x in inventories.values()}
    if len(as_of) != 1:
        raise RolloverBackfillError("ES/NQ as-of mismatch")
    markets = {}
    total_requests = total_rows = total_raw = total_normalized = 0
    for root, inventory in inventories.items():
        pairs = []
        contracts = inventory["contracts"]
        for outgoing, incoming in zip(contracts, contracts[1:]):
            sessions = _weekdays_before(outgoing.last_trade_date, OVERLAP_SESSIONS)
            start, end = _session_bounds(sessions)
            pair_id = identity(SCHEMA_VERSION, POLICY_VERSION, outgoing.id, incoming.id,
                               *(x.isoformat() for x in sessions))
            request_ids = (identity(pair_id, outgoing.id, start.isoformat(), end.isoformat()),
                           identity(pair_id, incoming.id, start.isoformat(), end.isoformat()))
            pairs.append(PairPlan(pair_id, root, outgoing.id, outgoing.ticker, incoming.id,
                                  incoming.ticker, sessions, start, end, request_ids))
        requests = len(pairs) * 2
        rows = len(pairs) * OVERLAP_SESSIONS * MINUTES_PER_SESSION * 2
        raw = rows * (203 if root == "ES" else 207)
        normalized = rows * 225
        provisional_sessions = sum(1 for offset in range((inventory["history_end_exclusive"] - inventory["evidence_supported_start"]).days)
                                   if (inventory["evidence_supported_start"] + timedelta(days=offset)).weekday() < 5)
        provisional_rows = provisional_sessions * MINUTES_PER_SESSION
        provisional_requests = (provisional_sessions + SESSIONS_PER_REQUEST - 1) // SESSIONS_PER_REQUEST
        markets[root] = {**inventory, "pairs": tuple(pairs), "pass_a_estimate": {
            "requests": requests, "rows": rows, "raw_bytes": raw, "normalized_bytes": normalized,
            "minimum_duration_minutes": (requests + 3) // 4}, "provisional_pass_b_estimate": {
            "sessions": provisional_sessions, "requests": provisional_requests, "rows": provisional_rows,
            "raw_bytes_range": [provisional_rows * 180, provisional_rows * 260],
            "normalized_bytes": provisional_rows * 225,
            "minimum_duration_minutes": (provisional_requests + 3) // 4,
            "final_plan_requires_validated_roll_decisions": True}}
        total_requests += requests; total_rows += rows; total_raw += raw; total_normalized += normalized
    plan_id = identity(SCHEMA_VERSION, POLICY_VERSION, SESSION_CALENDAR_VERSION, next(iter(as_of)).isoformat(),
                       *(x.id for root in ROOTS for x in markets[root]["contracts"]))
    return {"id": plan_id, "schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION,
            "session_calendar_version": SESSION_CALENDAR_VERSION,
            "as_of": next(iter(as_of)), "phase": "PASS_A_ROLLOVER_DISCOVERY_NOT_STARTED",
            "aggregate_requests_made": 0, "automatic_retry": False, "calls_per_minute": 4,
            "markets": markets, "combined_pass_a": {"requests": total_requests, "rows": total_rows,
                "raw_bytes": total_raw, "normalized_bytes": total_normalized,
                "minimum_duration_minutes": (total_requests + 3) // 4}}


def write_plan(repository: Path) -> Path:
    plan = build_pass_a_plan(repository)
    target = repository / "data/backtests" / PLAN_NAME
    if target.exists():
        existing = (target / "plan.json").read_bytes()
        if existing != _json_bytes(plan):
            raise RolloverBackfillError("conflicting frozen plan exists")
        return target / "plan.json"
    temporary = target.with_name("." + target.name + ".partial")
    if temporary.exists():
        raise RolloverBackfillError("partial plan exists")
    temporary.mkdir(parents=True)
    _atomic_new(temporary / "plan.json", _json_bytes(plan))
    _atomic_new(temporary / "status.json", _json_bytes({"plan_id": plan["id"], "state": "NOT_STARTED",
                "completed_requests": 0, "total_requests": plan["combined_pass_a"]["requests"]}))
    os.rename(temporary, target)
    return target / "plan.json"


def decide_roll(pair: PairPlan, facts: tuple[DailyVolumeFact, ...], *, evaluated_at: datetime) -> FrozenRollDecision:
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() != timedelta(0):
        raise RolloverBackfillError("evaluation timestamp must be UTC")
    by_session: dict[date, dict[str, DailyVolumeFact]] = {}
    for fact in facts:
        if fact.pair_id != pair.id or fact.contract_id not in (pair.outgoing_id, pair.incoming_id):
            raise RolloverBackfillError("volume fact identity mismatch")
        if fact.session not in pair.sessions or fact.finalized_at > evaluated_at:
            raise RolloverBackfillError("future or out-of-window volume fact")
        if not fact.volume.is_finite() or fact.volume < 0:
            raise RolloverBackfillError("invalid volume")
        bucket = by_session.setdefault(fact.session, {})
        if fact.contract_id in bucket:
            raise RolloverBackfillError("duplicate daily volume fact")
        bucket[fact.contract_id] = fact
    consecutive = 0
    evidence = []
    for index, session in enumerate(pair.sessions):
        bucket = by_session.get(session, {})
        old = bucket.get(pair.outgoing_id); new = bucket.get(pair.incoming_id)
        if old is not None and new is not None and new.volume > old.volume:
            consecutive += 1; evidence.extend((old.id, new.id))
        else:
            consecutive = 0; evidence = []
        if consecutive == 2:
            if index + 1 >= len(pair.sessions):
                break
            decision_time = max(old.finalized_at, new.finalized_at)
            effective = pair.sessions[index + 1]
            ident = identity(SCHEMA_VERSION, POLICY_VERSION, pair.id, session, effective, "VOLUME_CROSSOVER", *evidence)
            return FrozenRollDecision(ident, pair.id, pair.root, pair.outgoing_id, pair.incoming_id,
                session, decision_time, effective, "TWO_CONSECUTIVE_FINALIZED_DAILY_VOLUME_CROSSOVER", tuple(evidence))
    fallback_index = len(pair.sessions) - 2
    fallback_session = pair.sessions[fallback_index]
    complete = by_session.get(fallback_session, {})
    if set(complete) != {pair.outgoing_id, pair.incoming_id}:
        raise RolloverBackfillError("fallback evidence is incomplete")
    decision_time = max(x.finalized_at for x in complete.values())
    effective = pair.sessions[-1]
    evidence = tuple(x.id for x in sorted(complete.values(), key=lambda x: x.contract_id))
    ident = identity(SCHEMA_VERSION, POLICY_VERSION, pair.id, fallback_session, effective, "CALENDAR_FALLBACK", *evidence)
    return FrozenRollDecision(ident, pair.id, pair.root, pair.outgoing_id, pair.incoming_id,
        fallback_session, decision_time, effective, "CALENDAR_FALLBACK_BEFORE_LAST_TRADABLE_SESSION", evidence)


def build_active_windows(contracts: tuple[ContractFact, ...], decisions: tuple[FrozenRollDecision, ...],
                         *, start: date, end: date) -> tuple[ActiveWindow, ...]:
    if not contracts or start >= end or len(decisions) != len(contracts) - 1:
        raise RolloverBackfillError("active-window inputs incomplete")
    decision_by_old = {x.outgoing_id: x for x in decisions}
    result = []
    cursor = start
    for contract in contracts[:-1]:
        decision = decision_by_old.get(contract.id)
        if decision is None or decision.effective_session <= cursor or decision.incoming_id != contracts[len(result)+1].id:
            raise RolloverBackfillError("roll decision chain conflict")
        result.append(ActiveWindow(contract.id, contract.ticker, cursor, decision.effective_session, decision.id))
        cursor = decision.effective_session
    result.append(ActiveWindow(contracts[-1].id, contracts[-1].ticker, cursor, end, None))
    if any(left.end_exclusive != right.start for left, right in zip(result, result[1:])):
        raise RolloverBackfillError("active windows overlap or gap")
    return tuple(result)


class RequestStore:
    def __init__(self, repository: Path, plan_id: str):
        self.repository = repository
        self.plan_id = plan_id
        self.stage = repository / "data/backtests" / STAGING_NAME
        self.stop_file = repository / "data/backtests/es_nq_rollover_discovery.stop"

    def is_complete(self, root: str, request_id: str) -> bool:
        manifest_path = self.stage / root / "manifests" / f"{request_id}.json"
        if not manifest_path.exists():
            return False
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_path = self.stage / root / manifest["raw_relative_path"]
        normalized_path = self.stage / root / manifest["normalized_relative_path"]
        if not raw_path.exists() or not normalized_path.exists():
            raise RolloverBackfillError("checkpoint references missing files")
        if sha256(raw_path.read_bytes()).hexdigest() != manifest["raw_sha256"] or sha256(normalized_path.read_bytes()).hexdigest() != manifest["normalized_sha256"]:
            raise RolloverBackfillError("checksum conflict")
        return True

    def retained_raw(self, root: str, request_id: str) -> tuple[bytes, dict] | None:
        """Return a checksum-verified raw-first transaction for crash-safe resume."""
        raw_path = self.stage / root / "raw" / f"{request_id}.json"
        pending_path = self.stage / root / "pending" / f"{request_id}.json"
        if not raw_path.exists() and not pending_path.exists():
            return None
        if not raw_path.exists() or not pending_path.exists():
            raise RolloverBackfillError("incomplete raw-first transaction")
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        if (pending.get("schema_version") != SCHEMA_VERSION
                or pending.get("plan_id") != self.plan_id
                or pending.get("request_id") != request_id
                or pending.get("root") != root
                or pending.get("state") != "RAW_RETAINED"):
            raise RolloverBackfillError("raw-first transaction identity conflict")
        raw = raw_path.read_bytes()
        if len(raw) != pending.get("raw_bytes") or sha256(raw).hexdigest() != pending.get("raw_sha256"):
            raise RolloverBackfillError("checksum conflict")
        return raw, pending

    def commit(self, root: str, request_id: str, *, raw: bytes, normalized: bytes,
               request_facts: dict) -> None:
        if self.is_complete(root, request_id):
            return
        self.retain_raw(root, request_id, raw=raw, request_facts=request_facts)
        self.complete(root, request_id, normalized=normalized, request_facts=request_facts)

    def retain_raw(self, root: str, request_id: str, *, raw: bytes, request_facts: dict) -> None:
        if self.stop_file.exists():
            raise RolloverBackfillError("owner stop requested")
        if self.is_complete(root, request_id):
            return
        serialized_facts = json.dumps(request_facts, sort_keys=True, default=str).lower()
        if any(word in serialized_facts for word in ("authorization", "bearer ", "api_key", "api-key", "credential")):
            raise RolloverBackfillError("credential-bearing request facts are forbidden")
        raw_path = self.stage / root / "raw" / f"{request_id}.json"
        pending_path = self.stage / root / "pending" / f"{request_id}.json"
        for path in (raw_path, pending_path):
            if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
                raise RolloverBackfillError("pre-existing unverified file")
        _atomic_new(raw_path, raw)
        _atomic_new(pending_path, _json_bytes({"schema_version": SCHEMA_VERSION, "plan_id": self.plan_id,
            "request_id": request_id, "root": root, "raw_relative_path": f"raw/{raw_path.name}",
            "raw_sha256": sha256(raw).hexdigest(), "raw_bytes": len(raw), "state": "RAW_RETAINED",
            "automatic_retry": False, **request_facts}))

    def complete(self, root: str, request_id: str, *, normalized: bytes, request_facts: dict) -> None:
        raw_path = self.stage / root / "raw" / f"{request_id}.json"
        pending_path = self.stage / root / "pending" / f"{request_id}.json"
        normalized_path = self.stage / root / "normalized" / f"{request_id}.json"
        manifest_path = self.stage / root / "manifests" / f"{request_id}.json"
        checkpoint_path = self.stage / root / "checkpoints" / f"{request_id}.json"
        if not raw_path.exists() or not pending_path.exists():
            raise RolloverBackfillError("raw-first transaction is missing")
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        raw = raw_path.read_bytes()
        if sha256(raw).hexdigest() != pending["raw_sha256"]:
            raise RolloverBackfillError("checksum conflict")
        for path in (normalized_path, manifest_path, checkpoint_path):
            if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
                raise RolloverBackfillError("pre-existing unverified file")
        _atomic_new(normalized_path, normalized)
        manifest = {"schema_version": SCHEMA_VERSION, "plan_id": self.plan_id, "request_id": request_id,
            "root": root, "raw_relative_path": f"raw/{raw_path.name}", "normalized_relative_path": f"normalized/{normalized_path.name}",
            "raw_sha256": sha256(raw).hexdigest(), "normalized_sha256": sha256(normalized).hexdigest(),
            "raw_bytes": len(raw), "automatic_retry": False, **request_facts}
        _atomic_new(manifest_path, _json_bytes(manifest))
        _atomic_new(checkpoint_path, _json_bytes({"plan_id": self.plan_id, "request_id": request_id,
            "manifest_sha256": sha256(_json_bytes(manifest)).hexdigest(), "state": "VERIFIED"}))

    def promote(self) -> Path:
        destination = self.repository / "data/backtests" / RESULT_NAME
        if destination.exists() or not self.stage.exists():
            raise RolloverBackfillError("promotion destination or staging state invalid")
        os.rename(self.stage, destination)
        return destination


def _default_fetch(ticker: str, start: datetime, end: datetime, key: str) -> tuple[int, bytes, dict]:
    query = {"resolution": "1min", "window_start.gte": str(int(start.timestamp() * 1_000_000_000)),
             "window_start.lt": str(int(end.timestamp() * 1_000_000_000)), "limit": "10000",
             "sort": "window_start.asc"}
    url = BASE_URL + "/futures/v1/aggs/" + urllib.parse.quote(ticker, safe="") + "?" + urllib.parse.urlencode(query)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or "key" in parsed.query.lower():
        raise RolloverBackfillError("request boundary invalid")
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key,
                                                   "Accept": "application/json"}, method="GET")
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=20.0, context=context) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1), {
                "content_type": response.headers.get("Content-Type"),
                "request_id": response.headers.get("X-Request-Id") or response.headers.get("Request-Id")}
    except urllib.error.HTTPError as error:
        return error.code, error.read(65536), {"content_type": error.headers.get("Content-Type"),
            "request_id": error.headers.get("X-Request-Id") or error.headers.get("Request-Id")}


def _normalize_volume(raw: bytes, pair: dict, contract_id: str, ticker: str,
                      request_id: str, as_of: datetime) -> bytes:
    try:
        payload = json.loads(raw.decode("utf-8"), parse_float=Decimal)
    except Exception as error:
        raise RolloverBackfillError("aggregate schema drift") from error
    if payload.get("status") != "OK" or not isinstance(payload.get("results"), list) or payload.get("next_url"):
        raise RolloverBackfillError("partial response or pagination anomaly")
    sessions = {date.fromisoformat(x) for x in pair["sessions"]}
    totals = {session: Decimal(0) for session in sessions}
    observed = set()
    start = datetime.fromisoformat(pair["start_utc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(pair["end_utc"].replace("Z", "+00:00"))
    for row in payload["results"]:
        if row.get("ticker") != ticker:
            raise RolloverBackfillError("contract identity contamination")
        ns = row.get("window_start")
        if isinstance(ns, bool) or not isinstance(ns, int) or ns in observed:
            raise RolloverBackfillError("duplicate or malformed bar timestamp")
        observed.add(ns)
        stamp = datetime.fromtimestamp(ns / 1_000_000_000, timezone.utc)
        if not start <= stamp < end or stamp >= as_of:
            raise RolloverBackfillError("future or out-of-window bar")
        session = date.fromisoformat(str(row.get("session_end_date")))
        if session not in sessions:
            raise RolloverBackfillError("session contamination")
        volume = Decimal(str(row.get("volume")))
        values = {name: Decimal(str(row.get(name))) for name in ("open", "high", "low", "close")}
        if (not volume.is_finite() or volume < 0 or any(not x.is_finite() or x <= 0 for x in values.values())
                or values["high"] < max(values["open"], values["close"])
                or values["low"] > min(values["open"], values["close"])):
            raise RolloverBackfillError("invalid volume")
        totals[session] += volume
    facts = []
    for session in sorted(sessions):
        if not any(date.fromisoformat(str(row.get("session_end_date"))) == session for row in payload["results"]):
            continue
        finalized = datetime.combine(session, day_time(16), CHICAGO).astimezone(timezone.utc)
        fact_id = identity(SCHEMA_VERSION, pair["id"], contract_id, session, totals[session], request_id)
        facts.append({"id": fact_id, "pair_id": pair["id"], "contract_id": contract_id,
            "ticker": ticker, "session": session.isoformat(), "volume": format(totals[session], "f"),
            "finalized_at": finalized.isoformat().replace("+00:00", "Z"), "source_request_id": request_id})
    return _json_bytes(facts)


def _pair_from_dict(value: dict) -> PairPlan:
    return PairPlan(value["id"], value["root"], value["outgoing_id"], value["outgoing_ticker"],
        value["incoming_id"], value["incoming_ticker"], tuple(date.fromisoformat(x) for x in value["sessions"]),
        datetime.fromisoformat(value["start_utc"].replace("Z", "+00:00")),
        datetime.fromisoformat(value["end_utc"].replace("Z", "+00:00")), tuple(value["request_ids"]))


def _contract_from_dict(value: dict) -> ContractFact:
    return ContractFact(value["id"], value["root"], value["ticker"], value["contract_month"],
        value["contract_year"], date.fromisoformat(value["first_trade_date"]),
        date.fromisoformat(value["last_trade_date"]), date.fromisoformat(value["settlement_date"]),
        value["venue"], tuple(value["provenance_sha256"]))


def _volume_facts(path: Path) -> tuple[DailyVolumeFact, ...]:
    values = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return tuple(DailyVolumeFact(x["id"], x["pair_id"], x["contract_id"], x["ticker"],
        date.fromisoformat(x["session"]), Decimal(x["volume"]),
        datetime.fromisoformat(x["finalized_at"].replace("Z", "+00:00")), x["source_request_id"])
        for x in values)


def _sessions_between(start: date, end: date) -> tuple[date, ...]:
    return tuple(start + timedelta(days=offset) for offset in range((end - start).days)
                 if (start + timedelta(days=offset)).weekday() < 5
                 and (start + timedelta(days=offset)) not in NON_ORDINARY_SESSIONS)


def finalize_pass_a(repository: Path, plan: dict, store: RequestStore) -> dict:
    markets = {}
    for root in ROOTS:
        market = plan["markets"][root]
        contracts = tuple(_contract_from_dict(x) for x in market["contracts"])
        decisions = []
        for pair_value in market["pairs"]:
            pair = _pair_from_dict(pair_value)
            facts = []
            for request_id in pair.request_ids:
                if not store.is_complete(root, request_id):
                    raise RolloverBackfillError("Pass A request set incomplete")
                facts.extend(_volume_facts(store.stage / root / "normalized" / f"{request_id}.json"))
            decisions.append(decide_roll(pair, tuple(facts), evaluated_at=datetime.fromisoformat(plan["as_of"].replace("Z", "+00:00"))))
        windows = build_active_windows(contracts, tuple(decisions),
            start=date.fromisoformat(market["evidence_supported_start"]),
            end=date.fromisoformat(market["history_end_exclusive"]))
        requests = []
        for window in windows:
            sessions = _sessions_between(window.start, window.end_exclusive)
            for offset in range(0, len(sessions), SESSIONS_PER_REQUEST):
                chunk = sessions[offset:offset + SESSIONS_PER_REQUEST]
                start_utc, end_utc = _session_bounds(chunk)
                request_id = identity(SCHEMA_VERSION, plan["id"], "PASS_B", window.contract_id,
                                      *(x.isoformat() for x in chunk))
                requests.append({"id": request_id, "root": root, "contract_id": window.contract_id,
                    "ticker": window.ticker, "sessions": [x.isoformat() for x in chunk],
                    "start_utc": start_utc, "end_utc": end_utc})
        markets[root] = {"decisions": decisions, "active_windows": windows, "requests": requests,
                         "request_count": len(requests),
                         "finalized_only_after_pass_a": True}
        _atomic_new(store.stage / root / "rollover_decisions.json", _json_bytes(decisions))
        _atomic_new(store.stage / root / "pass_b_plan.json", _json_bytes(markets[root]))
    result = {"schema_version": SCHEMA_VERSION, "plan_id": plan["id"], "policy_version": POLICY_VERSION,
              "state": "PASS_A_VALIDATED_PASS_B_FROZEN", "markets": markets,
              "aggregate_requests_made": plan["combined_pass_a"]["requests"]}
    _atomic_new(store.stage / "validation_report.json", _json_bytes(result))
    destination = store.promote()
    return {"state": result["state"], "destination": str(destination), "plan_id": plan["id"]}


def execute_pass_a(repository: Path, key: str, *, fetch: Callable = _default_fetch,
                   sleep: Callable[[float], None] = time.sleep) -> dict:
    plan_path = repository / "data/backtests" / PLAN_NAME / "plan.json"
    if not plan_path.exists():
        raise RolloverBackfillError("frozen Pass A plan is missing")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    store = RequestStore(repository, plan["id"])
    as_of = datetime.fromisoformat(plan["as_of"].replace("Z", "+00:00"))
    calls = 0
    for root in ROOTS:
        contracts = {x["id"]: x for x in plan["markets"][root]["contracts"]}
        for pair in plan["markets"][root]["pairs"]:
            for contract_id, ticker, request_id in ((pair["outgoing_id"], pair["outgoing_ticker"], pair["request_ids"][0]),
                                                     (pair["incoming_id"], pair["incoming_ticker"], pair["request_ids"][1])):
                if store.is_complete(root, request_id):
                    continue
                if store.stop_file.exists():
                    raise RolloverBackfillError("owner stop requested")
                start = datetime.fromisoformat(pair["start_utc"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(pair["end_utc"].replace("Z", "+00:00"))
                retained = store.retained_raw(root, request_id)
                if retained is None:
                    if calls:
                        sleep(MIN_CALL_INTERVAL_SECONDS)
                    status, raw, headers = fetch(ticker, start, end, key); calls += 1
                    safe = {"endpoint_class": "futures_minute_aggregates", "ticker": ticker,
                        "start_utc": pair["start_utc"], "end_utc": pair["end_utc"], "http_status": status,
                        "response_content_type": headers.get("content_type"), "provider_request_id": headers.get("request_id")}
                    store.retain_raw(root, request_id, raw=raw, request_facts=safe)
                else:
                    raw, pending = retained
                    status = pending["http_status"]
                    safe = {name: pending.get(name) for name in ("endpoint_class", "ticker", "start_utc",
                        "end_utc", "http_status", "response_content_type", "provider_request_id")}
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RolloverBackfillError("unsafe response-size condition")
                if status in (401, 403):
                    raise RolloverBackfillError("authorization or entitlement rejected")
                if status == 429:
                    raise RolloverBackfillError("rate-limit anomaly")
                if status != 200:
                    raise RolloverBackfillError("provider response failed")
                normalized = _normalize_volume(raw, pair, contract_id, ticker, request_id, as_of)
                store.complete(root, request_id, normalized=normalized, request_facts=safe)
    finalized = finalize_pass_a(repository, plan, store)
    return {**finalized, "network_calls": calls, "automatic_retry": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded Pass A ES/NQ rollover discovery")
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--prepare-plan", action="store_true")
    parser.add_argument("--execute-pass-a", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare_plan:
        print(write_plan(args.repository.resolve()))
        return 0
    if args.execute_pass_a:
        key = sys.stdin.readline().rstrip("\r\n")
        try:
            print(json.dumps(execute_pass_a(args.repository.resolve(), key), sort_keys=True))
            return 0
        finally:
            key = ""
    raise SystemExit("execution requires a separately reviewed owner helper")


if __name__ == "__main__":
    raise SystemExit(main())
