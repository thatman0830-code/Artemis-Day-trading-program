"""Bounded offline OCO replay journal; evidence remains caller-owned.

Not a runtime launcher, gateway transaction, or automatic recovery mechanism.
"""
import json
import os
from pathlib import Path
from uuid import uuid4

from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from execution.paper_oco_execution_v1 import PaperOCOCoordinatorV1, PaperOCOError


MAX_BYTES = 1_000_000
MAX_ACTIONS = 1000


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PaperOCOError("duplicate journal key")
        result[key] = value
    return result


class PaperOCOCheckpointV1:
    """Exclusive writer + CAS + deterministic replay, never implicit initialization.

    Evidence mapping keys are canonical_fingerprint(payload). EVALUATE payloads
    contain bar, evaluated_at, accounting; ACK payloads contain accounting only.
    Reload requires every referenced payload. Hashes detect corruption, not a
    malicious writer or rollback of the entire directory.
    """

    def __init__(self, root, *, initial):
        self.root = Path(root).absolute()
        self.path = self.root / "oco-checkpoint.json"
        self.lock = self.root / "oco-checkpoint.lock"
        self.initial = dict(initial)
        self.initial["instructions"] = tuple(initial["instructions"])
        PaperOCOCoordinatorV1(**self.initial)
        self.initial_id = canonical_fingerprint(self.initial)

    def _safe(self):
        for path in (self.root, *self.root.parents, self.path, self.lock):
            if path.is_symlink():
                raise PaperOCOError("linked journal path")
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if getattr(info, "st_file_attributes", 0) & 0x400:
                raise PaperOCOError("reparse journal path")
        if not self.root.is_dir():
            raise PaperOCOError("existing journal directory required")

    def _acquire(self):
        self._safe()
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise PaperOCOError("journal writer lock conflict") from exc
        os.close(fd)

    def _write(self, body):
        self._safe()
        document = {"checkpoint_id": canonical_fingerprint(body), "body": body}
        raw = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > MAX_BYTES:
            raise PaperOCOError("journal size limit")
        temporary = self.root / (".oco-" + uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return document

    def initialize(self):
        self._acquire()
        try:
            return self._initialize_locked()
        finally:
            self.lock.unlink()

    def _initialize_locked(self):
        if self.path.exists():
            raise PaperOCOError("journal already exists")
        return self._write(dict(version="paper-oco-checkpoint-v1", initial_id=self.initial_id,
            actions=[], status="COMMITTED", state="ARMED", trading_authority=False))

    def _read(self):
        self._safe()
        if canonical_fingerprint(self.initial) != self.initial_id:
            raise PaperOCOError("initial evidence changed")
        with self.path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise PaperOCOError("journal size limit")
        try:
            doc = json.loads(raw, object_pairs_hook=_unique,
                parse_constant=lambda _: (_ for _ in ()).throw(PaperOCOError("invalid number")))
            if not isinstance(doc, dict) or set(doc) != {"checkpoint_id", "body"}:
                raise PaperOCOError("invalid journal envelope")
            body = doc["body"]
            if (not isinstance(body, dict) or set(body) !=
                    {"version", "initial_id", "actions", "status", "state", "trading_authority"}
                    or body["version"] != "paper-oco-checkpoint-v1"
                    or body["initial_id"] != self.initial_id or body["trading_authority"] is not False
                    or type(body["actions"]) is not list or len(body["actions"]) > MAX_ACTIONS
                    or doc["checkpoint_id"] != canonical_fingerprint(body)):
                raise PaperOCOError("invalid journal identity or checksum")
            return doc
        except (ValueError, TypeError, KeyError) as exc:
            raise PaperOCOError("invalid journal") from exc

    @staticmethod
    def _apply(coordinator, kind, payload):
        keys = ({"bar", "evaluated_at", "accounting"} if kind == "EVALUATE" else
                {"accounting", "cancellations"} if kind == "CANCEL_ACK" else {"accounting"})
        if type(payload) is not dict or set(payload) != keys:
            raise PaperOCOError("invalid operation evidence")
        if kind == "EVALUATE":
            return coordinator.evaluate(**payload).result_id
        if kind == "ACK":
            return coordinator.acknowledge_accounting(**payload)
        if kind == "CANCEL_ACK":
            return coordinator.acknowledge_cancellation(**payload)
        raise PaperOCOError("unknown journal operation")

    def load(self, *, evidence):
        doc = self._read()
        body = doc["body"]
        if body["status"] != "COMMITTED":
            raise PaperOCOError("journal blocked: interrupted or failed operation")
        coordinator = PaperOCOCoordinatorV1(**self.initial)
        for action in body["actions"]:
            if type(action) is not dict or set(action) != {"kind", "evidence_id", "result", "state"}:
                raise PaperOCOError("invalid journal action")
            payload = evidence.get(action["evidence_id"])
            if payload is None or canonical_fingerprint(payload) != action["evidence_id"]:
                raise PaperOCOError("missing or mismatched replay evidence")
            result = self._apply(coordinator, action["kind"], payload)
            if result != action["result"] or coordinator.state != action["state"]:
                raise PaperOCOError("journal replay mismatch")
        if coordinator.state != body["state"]:
            raise PaperOCOError("journal state mismatch")
        return doc, coordinator

    def advance(self, *, kind, payload, evidence, expected_checkpoint_id):
        self._acquire()
        try:
            doc, coordinator = self.load(evidence=evidence)
            if doc["checkpoint_id"] != expected_checkpoint_id:
                raise PaperOCOError("stale journal checkpoint")
            body = doc["body"]
            if len(body["actions"]) >= MAX_ACTIONS:
                raise PaperOCOError("journal action limit")
            # Durable intent precedes evaluation. Any uncertain failure blocks
            # reload, even if the in-memory operation never ran.
            self._write({**body, "status": "IN_FLIGHT"})
            result = self._apply(coordinator, kind, payload)
            action = dict(kind=kind, evidence_id=canonical_fingerprint(payload),
                result=result, state=coordinator.state)
            return self._write({**body, "actions": [*body["actions"], action],
                "status": "COMMITTED", "state": coordinator.state})
        finally:
            self.lock.unlink()
