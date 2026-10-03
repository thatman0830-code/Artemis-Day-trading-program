"""Append-only, hash-chained evidence ledger, one file per evidence label.

Evidence labels are never pooled: SYNTHETIC_TEST, HISTORICAL_DEVELOPMENT,
WALK_FORWARD, PROTECTED_OOS, AUTONOMOUS_PAPER, MANUAL_PROP, PERSONAL_LIVE
(plus replay diagnostics). Records carrying a ``dedupe_key`` are written at
most once, so retries and replays cannot duplicate intents, orders or fills.
Corrections are appended as CORRECTION records; nothing is rewritten.

Completed positions can also be mirrored into the pre-existing SQLite
``database.trade_ledger.TradeLedger`` (its UNIQUE(position_id) is a second
duplicate guard). The mirror's opened_at/closed_at are write times.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import threading

EVIDENCE_LABELS = {
    "SYNTHETIC_TEST", "HISTORICAL_DEVELOPMENT", "WALK_FORWARD", "PROTECTED_OOS",
    "POST_HOLDOUT_FORWARD_ARCHIVE", "AUTONOMOUS_PAPER", "MANUAL_PROP", "DELAYED_MANUAL_SIMULATION",
    "PERSONAL_LIVE", "REPLAY_DIAGNOSTIC_NON_DEPLOYABLE",
}


RESERVED_FIELDS = {"seq", "type", "evidence_label", "written_at_utc", "dedupe_key", "prev_hash", "hash"}


def _default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "value"):
        return o.value
    raise TypeError(f"not serializable: {type(o)}")


class EvidenceLedger:
    def __init__(self, directory: Path, evidence_label: str, run_id: str, *, sqlite_mirror=None):
        if evidence_label not in EVIDENCE_LABELS:
            raise ValueError(f"unknown evidence label {evidence_label}")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.label = evidence_label
        self.run_id = run_id
        self.path = self.directory / f"{evidence_label.lower()}-ledger.jsonl"
        self._lock = threading.Lock()
        self._keys: set[str] = set()
        self._prev = "0" * 64
        self._seq = 0
        self.sqlite_mirror = sqlite_mirror
        self._mirror_ids: dict[str, int] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                self._prev = rec["hash"]
                self._seq = max(self._seq, rec["seq"])
                if rec.get("dedupe_key"):
                    self._keys.add(rec["dedupe_key"])
                if rec["type"] == "POSITION_OPENED" and "mirror_id" in rec:
                    self._mirror_ids[rec["position_id"]] = rec["mirror_id"]

    def has(self, dedupe_key: str) -> bool:
        return dedupe_key in self._keys

    def append(self, rec_type: str, *, dedupe_key: str | None = None, **fields) -> dict | None:
        clash = RESERVED_FIELDS & fields.keys()
        if clash:
            raise ValueError(f"ledger fields may not override chain metadata: {sorted(clash)}")
        if "run_id" in fields and fields["run_id"] != self.run_id:
            raise ValueError("run_id field differs from the ledger run_id")
        with self._lock:
            if dedupe_key and dedupe_key in self._keys:
                return None
            body = {**fields, "seq": self._seq + 1, "type": rec_type, "evidence_label": self.label,
                    "run_id": self.run_id, "written_at_utc": datetime.now(timezone.utc).isoformat(),
                    "dedupe_key": dedupe_key, "prev_hash": self._prev}
            # Normalize to plain JSON first so the hash is computed over exactly what
            # verify_chain() will read back (non-string dict keys, tuples, datetimes).
            body = json.loads(json.dumps(body, default=_default))
            text = json.dumps(body, sort_keys=True, separators=(",", ":"))
            body["hash"] = sha256(text.encode()).hexdigest()
            line = json.dumps(body, sort_keys=True, separators=(",", ":"))
            with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._seq += 1
            self._prev = body["hash"]
            if dedupe_key:
                self._keys.add(dedupe_key)
            return body

    # ------------------------------------------------------------------ mirror
    def mirror_open(self, position_id: str, **kw) -> int | None:
        if self.sqlite_mirror is None:
            return None
        mirror_id = max(self._mirror_ids.values(), default=0) + 1
        self.sqlite_mirror.record_entry(position_id=mirror_id, **kw)
        self._mirror_ids[position_id] = mirror_id
        return mirror_id

    def mirror_close(self, position_id: str, **kw):
        if self.sqlite_mirror is None or position_id not in self._mirror_ids:
            return
        self.sqlite_mirror.record_exit(position_id=self._mirror_ids[position_id], **kw)

    # ------------------------------------------------------------------ reading
    def records(self, rec_type: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec_type is None or rec["type"] == rec_type:
                    out.append(rec)
        return out

    def verify_chain(self) -> bool:
        prev = "0" * 64
        for rec in self.records():
            body = dict(rec)
            digest = body.pop("hash")
            if body["prev_hash"] != prev:
                return False
            text = json.dumps(body, sort_keys=True, separators=(",", ":"))
            if sha256(text.encode()).hexdigest() != digest:
                return False
            prev = digest
        return True
