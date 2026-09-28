from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path

from futures_data.validate_forward_configuration import validate_configuration

SCHEMA = "es-nq-verified-forward-sessions-v1"
BOOTSTRAP_POLICY = "RETAINED_PASS_B_ARCHIVE_BOOTSTRAP_V1"


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists() or partial.exists():
        raise ValueError("bootstrap destination already exists")
    with partial.open("xb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.rename(partial, path)


def build_bootstrap(repository: Path) -> tuple[dict, dict, dict]:
    repository = repository.resolve()
    plan_dir = repository / "data/backtests/es_nq_pass_b_plan_3"
    evidence_manifest_path = plan_dir / "artifact_manifest.json"
    evidence_manifest = json.loads(evidence_manifest_path.read_text(encoding="utf-8"))
    evidence = []
    for name, expected in sorted(evidence_manifest["sha256"].items()):
        path = plan_dir / name
        actual = _hash(path)
        if actual != expected:
            raise ValueError("Pass B plan evidence checksum conflict")
        evidence.append({"path": path.relative_to(repository).as_posix(), "sha256": actual})
    evidence.append({"path": evidence_manifest_path.relative_to(repository).as_posix(), "sha256": _hash(evidence_manifest_path)})

    audit_path = repository / "outputs/archive_audits/es_nq_pass_b_final_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    archive = Path(audit["archive_path"]).resolve()
    for item in audit["artifact_hashes"]:
        path = repository / item["path"]
        if _hash(path) != item["sha256"]:
            raise ValueError("historical archive checksum conflict")
    evidence.append({"path": audit_path.relative_to(repository).as_posix(), "sha256": _hash(audit_path)})

    calendar = json.loads((plan_dir / "calendar.json").read_text(encoding="utf-8"))
    rollovers = json.loads((plan_dir / "rollovers.json").read_text(encoding="utf-8"))
    history = []
    for root in ("ES", "NQ"):
        windows = rollovers["markets"][root]["active_windows"]
        for session in calendar["sessions"]:
            day = session["session_date"]
            window = next((x for x in windows if x["start"] <= day < x["end_exclusive"]), None)
            if window is None:
                raise ValueError("verified calendar session has no active contract")
            history.append({
                "root": root, "session_date": day, "ticker": window["ticker"],
                "contract_id": window["contract_id"], "state": "ARCHIVED_IMMUTABLE",
                "archive_tree_sha256": audit["archive_tree_sha256"],
            })
    material = {
        "schema_version": SCHEMA, "configuration_policy": BOOTSTRAP_POLICY,
        "finalized": True, "source_id": evidence_manifest["plan_id"],
        "schedule_version": calendar["calendar_version"],
        "verified_coverage": {"start_inclusive": calendar["sessions"][0]["session_date"],
                              "end_exclusive": "2026-08-27", "last_session": calendar["sessions"][-1]["session_date"]},
        "evidence": evidence, "history": history, "sessions": [],
        "pending_session_count": 0, "refresh_required": True,
        "refresh_reason": "NO_RETAINED_VERIFIED_SESSION_AFTER_COVERAGE_BOUNDARY",
        "trading": False, "recorder_control": False,
    }
    config_id = sha256(_bytes(material)).hexdigest()
    configuration = {**material, "configuration_id": config_id}
    config_bytes = _bytes(configuration)
    manifest = {"schema_version": "es-nq-forward-configuration-manifest-v1", "configuration_id": config_id,
                "configuration_path": "config/es_nq_forward_sessions.json", "configuration_sha256": sha256(config_bytes).hexdigest(),
                "source_evidence": evidence}
    audit_report = {"schema_version": "es-nq-forward-bootstrap-audit-v1", "configuration_id": config_id,
                    "result": "VALID_ZERO_PENDING_BOOTSTRAP", "history_sessions_per_market": len(calendar["sessions"]),
                    "pending_sessions": 0, "verified_coverage": material["verified_coverage"],
                    "archive_tree_sha256": audit["archive_tree_sha256"], "source_evidence": evidence,
                    "reason": "Retained verified schedules end at 2026-08-26; no later session was inferred."}
    return configuration, manifest, audit_report


def publish_bootstrap(repository: Path) -> tuple[Path, Path, Path]:
    configuration, manifest, audit = build_bootstrap(repository)
    paths = (repository / "config/es_nq_forward_sessions.json",
             repository / "config/es_nq_forward_sessions.manifest.json",
             repository / "outputs/futures_forward/bootstrap_audit.json")
    _atomic(paths[0], _bytes(configuration)); _atomic(paths[1], _bytes(manifest)); _atomic(paths[2], _bytes(audit))
    validate_configuration(paths[0], repository=repository)
    return paths
