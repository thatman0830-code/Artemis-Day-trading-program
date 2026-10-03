"""Append-only evidence-qualification corrections (repair 2026-10-02).

A correction reclassifies a recorded session for QUALIFICATION only; raw ledgers
are never rewritten. Each row is anchored to the immutable hash-chain value of
the original SESSION_SUMMARY record (``session_summary_record_hash``), so it
keeps applying after later sessions append to the same ledger, and stops
applying if the original record were ever altered (the record hash would
differ and the ledger chain would fail verification). The full-file SHA-256 at
correction time is kept as provenance only.

A later diagnostic replay of complete data is a separate run with its own
ledger and label; it can never be relabelled as the original live session.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "outputs" / "mes_pilot" / "evidence_qualification" / "corrections.jsonl"
SCHEMA = "mes-evidence-correction-v1"
REQUIRED = ("schema", "session_date", "ledger_relpath", "session_summary_record_hash", "run_id",
            "ledger_sha256_at_correction", "original_classification", "corrected_classification",
            "reason_code", "reason_detail", "evidence_ref", "recorded_at_utc", "author")
ALLOWED_CORRECTIONS = ("CONTEXT_INCOMPLETE", "OPERATIONAL_FAULT")


class CorrectionError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    h = sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def validate(row: dict) -> dict:
    missing = [k for k in REQUIRED if k not in row]
    if missing:
        raise CorrectionError(f"correction missing fields {missing}")
    if row["schema"] != SCHEMA:
        raise CorrectionError("unsupported correction schema")
    if row["corrected_classification"] not in ALLOWED_CORRECTIONS:
        raise CorrectionError("corrections may only DOWNGRADE evidence (CONTEXT_INCOMPLETE / OPERATIONAL_FAULT)")
    return row


def load_corrections(path: Path | None = None) -> list[dict]:
    path = Path(path or os.environ.get("MES_EVIDENCE_CORRECTIONS") or DEFAULT_REGISTRY)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(validate(json.loads(line)))
    return rows


def append_correction(row: dict, path: Path | None = None) -> bool:
    """Append one correction; returns False (no write) for an exact duplicate anchor."""
    row = validate(dict(row))
    path = Path(path or DEFAULT_REGISTRY)
    for old in load_corrections(path):
        if (old["session_summary_record_hash"], old["corrected_classification"]) == \
                (row["session_summary_record_hash"], row["corrected_classification"]):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return True


def correction_for_summary(ledger_path: Path, session_date: str, *, original_classification: str,
                           corrected_classification: str, reason_code: str, reason_detail: str,
                           evidence_ref: str, author: str, repo_root: Path = ROOT) -> dict:
    """Build a correction anchored to the SESSION_SUMMARY record(s) of ``session_date`` in ``ledger_path``."""
    recs = [json.loads(x) for x in Path(ledger_path).read_text(encoding="utf-8").splitlines() if x.strip()]
    summaries = [r for r in recs if r["type"] == "SESSION_SUMMARY" and r["session_date"] == session_date]
    if len(summaries) != 1:
        raise CorrectionError(f"expected exactly one SESSION_SUMMARY for {session_date}, found {len(summaries)}")
    s = summaries[0]
    if s["classification"] != original_classification:
        raise CorrectionError(f"recorded classification {s['classification']} != {original_classification}")
    try:
        rel = str(Path(ledger_path).resolve().relative_to(Path(repo_root).resolve())).replace("\\", "/")
    except ValueError:
        rel = str(ledger_path)
    return validate({"schema": SCHEMA, "session_date": session_date, "ledger_relpath": rel,
                     "session_summary_record_hash": s["hash"], "run_id": s["run_id"],
                     "ledger_sha256_at_correction": sha256_file(Path(ledger_path)),
                     "original_classification": original_classification,
                     "corrected_classification": corrected_classification, "reason_code": reason_code,
                     "reason_detail": reason_detail, "evidence_ref": evidence_ref,
                     "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "author": author})


def apply_corrections(sessions: list[dict], corrections: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (sessions with corrected classifications, list of applied corrections). Pure; no I/O."""
    by_hash = {c["session_summary_record_hash"]: c for c in corrections}
    out, applied = [], []
    for s in sessions:
        c = by_hash.get(s.get("hash"))
        if c is not None and c["session_date"] == s.get("session_date"):
            out.append({**s, "classification": c["corrected_classification"], "corrected_by": c["reason_code"]})
            applied.append({k: c[k] for k in ("session_date", "original_classification", "corrected_classification",
                                              "reason_code", "reason_detail", "evidence_ref",
                                              "session_summary_record_hash")})
        else:
            out.append(s)
    return out, applied
