"""Frozen Phase 5C v3 manifest integrity and version compatibility gates."""
from __future__ import annotations

import hashlib
import json
import copy
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

V2_CANONICAL_SHA256 = "e805a78d552bc6c04d5665c818a9022dec7eb0a4da5e4db1432f28246e1973bb"
V2_COMMIT = "ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94"
V3_SCHEMA = "bot2-phase5c-experiment-manifest-v3"
V3_MANIFEST_CANONICAL_SHA256 = "c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19"
V3_PROTOCOL_ANCHOR_COMMIT = "9a1ecfaf08077252049dd187d44f8641da1186aa"
V3_PROTOCOL_PARENT_COMMIT = "ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94"
V3_EXTERNAL_ANCHOR_TYPE = "bot2-phase5c-v3-user-preserved-anchor-v1"
_VERIFIED_TOKEN = object()


class VerifiedManifest:
    """Manifest object constructible only through the pinned loader."""

    __slots__ = ("_data", "_pin", "sha256", "pin_sha256", "anchor_path",
                 "external_anchor_content_verified", "anchor_signature_status",
                 "independent_custody_proven", "_token", "_sealed")

    def __init__(self, data: dict, pin: dict, sha256: str, pin_sha256: str,
                 anchor_path: str, *, _token: object):
        if _token is not _VERIFIED_TOKEN:
            raise ValueError("MANIFEST_NOT_VERIFIED")
        object.__setattr__(self, "_data", copy.deepcopy(data))
        object.__setattr__(self, "_pin", copy.deepcopy(pin))
        object.__setattr__(self, "sha256", sha256)
        object.__setattr__(self, "pin_sha256", pin_sha256)
        object.__setattr__(self, "anchor_path", anchor_path)
        object.__setattr__(self, "external_anchor_content_verified", True)
        object.__setattr__(self, "anchor_signature_status", str(pin.get("signature_status", "UNSIGNED")).upper())
        object.__setattr__(self, "independent_custody_proven", False)
        object.__setattr__(self, "_token", _token)
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("VERIFIED_MANIFEST_IS_IMMUTABLE")
        object.__setattr__(self, name, value)

    @property
    def data(self) -> dict:
        # A defensive copy prevents callers mutating the verified source of truth.
        return copy.deepcopy(self._data)

    @property
    def pin(self) -> dict:
        return copy.deepcopy(self._pin)


def _repository_root(path: Path) -> Path:
    resolved = path.resolve()
    for parent in (resolved.parent, *resolved.parents):
        if (parent / ".git").exists():
            return parent
    return resolved.parent.parent


def _verify_external_anchor(manifest_path: Path, anchor_path: str | Path | None) -> tuple[dict, str]:
    if anchor_path is None:
        raise ValueError("EXTERNAL_TRUST_ANCHOR_REQUIRED")
    path = Path(anchor_path).resolve(strict=True)
    repository = _repository_root(manifest_path)
    if path == repository or repository in path.parents:
        raise ValueError("TRUST_ANCHOR_MUST_BE_OUTSIDE_REPOSITORY")
    try:
        anchor = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("EXTERNAL_TRUST_ANCHOR_INVALID") from exc
    required = {
        "anchor_type": V3_EXTERNAL_ANCHOR_TYPE,
        "protocol_version": V3_SCHEMA,
        "manifest_filename": manifest_path.name,
        "canonical_manifest_sha256": V3_MANIFEST_CANONICAL_SHA256,
        "dataset_manifest_sha256": "e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67",
        "raw_archive_tree_sha256": "405ff5602600fbe361c7136b85be0b26d46567c1c080dfefab2e506e109a775b",
        "feature_version": "bot2-feature-row-v3",
        "target_version": "bot2-future-market-state-v3",
    }
    if any(anchor.get(key) != value for key, value in required.items()):
        raise ValueError("EXTERNAL_TRUST_ANCHOR_MISMATCH")
    for key in ("frozen_protocol_anchor_commit", "reviewed_implementation_commit",
                "review_candidate_commit", "phase5c_u_remediation_base_commit"):
        value = anchor.get(key)
        if not isinstance(value, str) or len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("EXTERNAL_TRUST_ANCHOR_COMMIT_INVALID")
    if anchor["reviewed_implementation_commit"] != anchor["review_candidate_commit"]:
        raise ValueError("EXTERNAL_TRUST_ANCHOR_CANDIDATE_PIN_MISMATCH")
    if anchor.get("signature_status") != "UNSIGNED":
        raise ValueError("EXTERNAL_TRUST_ANCHOR_SIGNATURE_STATUS_INVALID")
    if anchor.get("independent_custody_status") != "NOT_CRYPTOGRAPHICALLY_PROVEN":
        raise ValueError("EXTERNAL_TRUST_ANCHOR_CUSTODY_STATUS_INVALID")
    try:
        created = datetime.fromisoformat(str(anchor.get("anchor_created_utc", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("EXTERNAL_TRUST_ANCHOR_TIMESTAMP_INVALID") from exc
    if created.tzinfo is None or created.utcoffset().total_seconds() != 0:
        raise ValueError("EXTERNAL_TRUST_ANCHOR_TIMESTAMP_INVALID")
    return anchor, sha256_file(path)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_hash(value: Any, *, excluded_key: str = "manifest_sha256") -> str:
    payload = dict(value)
    payload.pop(excluded_key, None)
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_and_verify_manifest(path: str | Path, *, expected_schema: str = V3_SCHEMA,
                             external_anchor_path: str | Path | None = None) -> tuple[dict, str]:
    manifest_path = Path(path)
    anchor, _ = _verify_external_anchor(manifest_path, external_anchor_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != expected_schema:
        raise ValueError("MANIFEST_SCHEMA_MISMATCH")
    actual = canonical_hash(manifest)
    if actual != manifest.get("manifest_sha256") or actual != anchor["canonical_manifest_sha256"]:
        raise ValueError("MANIFEST_HASH_MISMATCH")
    if manifest.get("evaluation_permitted") is not False or manifest.get("oos_model_scoring_performed") is not False:
        raise ValueError("PROTECTED_SCORING_GATE_OPEN_OR_INCONSISTENT")
    if manifest.get("trading_authority") is not False:
        raise ValueError("TRADING_AUTHORITY_MUST_REMAIN_FALSE")
    return manifest, actual


def load_verified_manifest(path: str | Path, *, external_anchor_path: str | Path | None = None) -> VerifiedManifest:
    manifest, digest = load_and_verify_manifest(path, external_anchor_path=external_anchor_path)
    anchor, anchor_digest = _verify_external_anchor(Path(path), external_anchor_path)
    return VerifiedManifest(manifest, anchor, digest, anchor_digest, str(Path(external_anchor_path).resolve()),
                            _token=_VERIFIED_TOKEN)


def is_verified_manifest(value: object) -> bool:
    if not isinstance(value, VerifiedManifest) or value._token is not _VERIFIED_TOKEN:
        return False
    # The verified wrapper is immutable through its public API, but Python callers
    # can still bypass that API (for example with object.__setattr__). Recheck the
    # frozen payload digest at every trust boundary so a forged/tampered wrapper
    # cannot retain verified status merely by carrying the private issuance token.
    try:
        return canonical_hash(value._data) == value.sha256
    except (TypeError, ValueError):
        return False


def verify_git_binding(repo_root: str | Path, *, expected_commit: str) -> dict[str, str | bool]:
    """Require the pinned implementation candidate, protocol ancestry, and a clean tree."""
    root = Path(repo_root).resolve()
    if (not isinstance(expected_commit, str) or len(expected_commit) != 40
            or any(ch not in "0123456789abcdef" for ch in expected_commit)):
        raise ValueError("REVIEW_CANDIDATE_COMMIT_INVALID")
    common = ["git", "-c", f"safe.directory={root}", "-C", str(root)]
    head = subprocess.run(common + ["rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True, timeout=15).stdout.strip()
    if head != expected_commit:
        raise ValueError("REVIEWED_COMMIT_MISMATCH")
    ancestor = subprocess.run(common + ["merge-base", "--is-ancestor", V3_PROTOCOL_ANCHOR_COMMIT, "HEAD"],
                              capture_output=True, text=True, timeout=15)
    if ancestor.returncode != 0:
        raise ValueError("PROTOCOL_ANCHOR_NOT_IN_COMMIT_ANCESTRY")
    status = subprocess.run(common + ["status", "--porcelain", "--untracked-files=all"],
                            check=True, capture_output=True, text=True, timeout=15).stdout
    if status.strip():
        raise ValueError("IMPLEMENTATION_WORKTREE_NOT_CLEAN")
    return {"commit": head, "review_candidate_commit": expected_commit,
            "protocol_anchor_commit": V3_PROTOCOL_ANCHOR_COMMIT,
            "exact_commit_match": True, "clean_worktree": True}


def require_manifest_overrides_match(verified: VerifiedManifest, overrides: dict[str, Any]) -> None:
    """Fail closed if callers try to introduce a second source of truth."""
    if not is_verified_manifest(verified):
        raise ValueError("MANIFEST_NOT_VERIFIED")
    manifest = verified.data
    allowed = {
        "experiment_id": manifest["experiment_id"],
        "feature_version": manifest["feature_specification"]["schema_version"],
        "target_version": manifest["target_specification"]["version"],
        "sequence_length": manifest["feature_specification"]["sequence_length"],
        "horizons_minutes": manifest["target_specification"]["horizons_minutes"],
        "architecture": manifest["architectures"]["A2_LEARNED_CAUSAL_TCN"],
        "training": manifest["a2_training"],
        "random_seeds": manifest["random_seeds"],
        "partitions": manifest["chronological_partitions_inclusive"],
        "walk_forward_windows": manifest["walk_forward_windows_inclusive"],
        "purge_embargo": manifest["purge_embargo"],
        "calibration": manifest["calibration"],
        "abstention": manifest["uncertainty_abstention"],
        "ablations": manifest["feature_ablations"],
        "metrics": manifest["metrics"],
    }
    if set(overrides) - set(allowed):
        raise ValueError("UNRECOGNIZED_PROTECTED_OVERRIDE")
    if any(overrides[key] != allowed[key] for key in overrides):
        raise ValueError("PROTECTED_OVERRIDE_MISMATCH")


def verify_model_compatibility(artifact: dict, manifest: dict) -> None:
    if artifact.get("architecture_version") != manifest["architectures"]["A2_LEARNED_CAUSAL_TCN"]["architecture_version"]:
        raise ValueError("MODEL_ARCHITECTURE_VERSION_MISMATCH")
    if artifact.get("feature_version") != manifest["feature_specification"]["schema_version"]:
        raise ValueError("MODEL_FEATURE_VERSION_MISMATCH")
    if artifact.get("target_version") != manifest["target_specification"]["version"]:
        raise ValueError("MODEL_TARGET_VERSION_MISMATCH")
    if artifact.get("trading_authority") is not False:
        raise ValueError("MODEL_TRADING_AUTHORITY_MUST_REMAIN_FALSE")
