"""Strict, externally pinned authorization contracts for Phase 5C-Z.

This module validates an authorization document; it does not create or grant
real protected-data authority.  A caller must obtain the expected document
digest through an independent trust channel and supply it as
``trusted_authorization_sha256``.  The document's self-hash alone is not a
trust anchor.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


AUTHORIZATION_SCHEMA = "bot2-phase5c-z-authorization-v1"
AUTHORIZATION_CONTEXT_FIELDS = (
    "source_kind",
    "implementation_commit",
    "manifest_sha256",
    "dataset_manifest_sha256",
    "raw_archive_tree_sha256",
    "protocol_version",
    "experiment_id",
    "execution_mode",
)
_CONTRACT_FIELDS = frozenset({
    "schema_version", "authorization_id", "authorization_kind", "binding",
    "scope", "authorization_sha256",
})
_BINDING_FIELDS = frozenset(AUTHORIZATION_CONTEXT_FIELDS)
_VERIFIED_TOKEN = object()
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class AuthorizationDenied(ValueError):
    """Authorization denial with a stable machine-readable reason code."""

    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


class VerifiedAuthorization:
    """Capability wrapper constructible only by successful verification."""

    __slots__ = ("_contract", "_contract_sha256", "_binding_sha256", "_scope_sha256",
                 "_token", "_sealed")

    def __init__(self, contract: Mapping[str, Any], *, _token: object):
        if _token is not _VERIFIED_TOKEN:
            raise AuthorizationDenied("AUTHORIZATION_NOT_VERIFIED")
        copied = json.loads(_canonical_json_bytes(dict(contract)).decode("utf-8"))
        object.__setattr__(self, "_contract", copied)
        object.__setattr__(self, "_contract_sha256", authorization_contract_sha256(copied))
        object.__setattr__(self, "_binding_sha256", _sha256(copied["binding"]))
        object.__setattr__(self, "_scope_sha256", _sha256(copied["scope"]))
        object.__setattr__(self, "_token", _token)
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("VERIFIED_AUTHORIZATION_IS_IMMUTABLE")
        object.__setattr__(self, name, value)

    @property
    def contract(self) -> dict[str, Any]:
        """Return a defensive copy of the verified authorization document."""
        return json.loads(_canonical_json_bytes(self._contract).decode("utf-8"))

    @property
    def authorization_sha256(self) -> str:
        return self._contract_sha256

    @property
    def binding(self) -> dict[str, Any]:
        return self.contract["binding"]

    @property
    def scope(self) -> dict[str, Any]:
        return self.contract["scope"]


def _deny(reason_code: str) -> None:
    raise AuthorizationDenied(reason_code)


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise AuthorizationDenied("AUTHORIZATION_DOCUMENT_NOT_CANONICALIZABLE") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def authorization_contract_sha256(document: Mapping[str, Any]) -> str:
    """Hash a complete contract excluding its ``authorization_sha256`` field.

    This is a content digest, not a signature.  Trust requires comparing it
    with a digest received and protected independently from the document.
    """
    if not isinstance(document, Mapping):
        _deny("AUTHORIZATION_DOCUMENT_MALFORMED")
    payload = dict(document)
    payload.pop("authorization_sha256", None)
    return _sha256(payload)


def _context_mapping(expected_context: object) -> dict[str, Any]:
    if isinstance(expected_context, Mapping):
        context = dict(expected_context)
    else:
        try:
            context = {name: getattr(expected_context, name)
                       for name in AUTHORIZATION_CONTEXT_FIELDS}
        except (AttributeError, TypeError) as exc:
            raise AuthorizationDenied("AUTHORIZATION_EXPECTED_CONTEXT_INVALID") from exc
    if set(context) != _BINDING_FIELDS:
        _deny("AUTHORIZATION_EXPECTED_CONTEXT_INVALID")
    for name, value in context.items():
        if not isinstance(value, str) or not value or value.strip() != value:
            _deny("AUTHORIZATION_EXPECTED_CONTEXT_INVALID")
    if not _COMMIT_RE.fullmatch(context["implementation_commit"]):
        _deny("AUTHORIZATION_EXPECTED_CONTEXT_INVALID")
    for name in ("manifest_sha256", "dataset_manifest_sha256", "raw_archive_tree_sha256"):
        if not _SHA256_RE.fullmatch(context[name]):
            _deny("AUTHORIZATION_EXPECTED_CONTEXT_INVALID")
    return context


def _scope_mapping(scope: object, reason: str) -> dict[str, Any]:
    if not isinstance(scope, Mapping) or not scope:
        _deny(reason)
    copied = dict(scope)
    if set(copied) != {"experiment_id", "execution_mode", "cell_sha256s"}:
        _deny(reason)
    if (not isinstance(copied["experiment_id"], str) or not copied["experiment_id"]
            or not isinstance(copied["execution_mode"], str) or not copied["execution_mode"]):
        _deny(reason)
    cell_ids = copied["cell_sha256s"]
    if not isinstance(cell_ids, list) or not cell_ids:
        _deny(reason)
    if any(not isinstance(cell_id, str) or not _SHA256_RE.fullmatch(cell_id)
           for cell_id in cell_ids):
        _deny(reason)
    if cell_ids != sorted(set(cell_ids)):
        _deny("AUTHORIZATION_SCOPE_CELL_IDS_NOT_CANONICAL")
    # Canonicalization rejects arbitrary Python objects and non-finite numbers.
    _canonical_json_bytes(copied)
    if _contains_wildcard(copied):
        _deny(reason)
    return copied


def _contains_wildcard(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"*", "all", "any", "allow_any"}
    if isinstance(value, Mapping):
        return any(_contains_wildcard(key) or _contains_wildcard(item)
                   for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_wildcard(item) for item in value)
    return False


def load_authorization_document(path: str | Path) -> dict[str, Any]:
    """Load strict JSON while rejecting duplicate keys and malformed input."""
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AuthorizationDenied("AUTHORIZATION_DOCUMENT_DUPLICATE_KEY")
            result[key] = value
        return result

    try:
        text = Path(path).read_text(encoding="utf-8")
        parsed = json.loads(text, object_pairs_hook=unique_object,
                            parse_constant=lambda _value: _deny("AUTHORIZATION_DOCUMENT_MALFORMED"))
    except AuthorizationDenied:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AuthorizationDenied("AUTHORIZATION_DOCUMENT_MALFORMED") from exc
    if not isinstance(parsed, dict):
        _deny("AUTHORIZATION_DOCUMENT_MALFORMED")
    return parsed


def validate_authorization_contract(
    document: Mapping[str, Any],
    *,
    expected_context: object,
    expected_scope: Mapping[str, Any],
    trusted_authorization_sha256: str | None,
    allow_test_only: bool = False,
) -> VerifiedAuthorization:
    """Validate every frozen binding against trusted execution context.

    Real protected authority is denied unless the complete document digest is
    supplied out-of-band.  Test-only documents can bind only to an explicitly
    synthetic source and synthetic mode, and still require exact digest,
    context, scope, and schema validation.
    """
    if not isinstance(document, Mapping):
        _deny("AUTHORIZATION_DOCUMENT_MALFORMED")
    contract = dict(document)
    if set(contract) != _CONTRACT_FIELDS:
        _deny("AUTHORIZATION_DOCUMENT_MALFORMED")
    try:
        _canonical_json_bytes(contract)
    except AuthorizationDenied:
        _deny("AUTHORIZATION_DOCUMENT_MALFORMED")
    if contract.get("schema_version") != AUTHORIZATION_SCHEMA:
        _deny("AUTHORIZATION_SCHEMA_MISMATCH")
    auth_id = contract.get("authorization_id")
    if not isinstance(auth_id, str) or not auth_id.strip() or auth_id.strip() != auth_id:
        _deny("AUTHORIZATION_DOCUMENT_MALFORMED")

    if not isinstance(trusted_authorization_sha256, str):
        _deny("AUTHORIZATION_TRUST_ANCHOR_REQUIRED")
    if not _SHA256_RE.fullmatch(trusted_authorization_sha256):
        _deny("AUTHORIZATION_TRUST_ANCHOR_INVALID")
    recorded_digest = contract.get("authorization_sha256")
    if not isinstance(recorded_digest, str) or not _SHA256_RE.fullmatch(recorded_digest):
        _deny("AUTHORIZATION_DOCUMENT_MALFORMED")
    actual_digest = authorization_contract_sha256(contract)
    if recorded_digest != actual_digest or trusted_authorization_sha256 != actual_digest:
        _deny("AUTHORIZATION_DOCUMENT_MODIFIED_OR_UNTRUSTED")

    binding = contract.get("binding")
    if not isinstance(binding, Mapping) or set(binding) != _BINDING_FIELDS:
        _deny("AUTHORIZATION_BINDING_MALFORMED")
    expected = _context_mapping(expected_context)
    actual_binding = dict(binding)
    if any(not isinstance(value, str) or not value or value.strip() != value
           for value in actual_binding.values()):
        _deny("AUTHORIZATION_BINDING_MALFORMED")
    if not _COMMIT_RE.fullmatch(actual_binding["implementation_commit"]):
        _deny("AUTHORIZATION_BINDING_MALFORMED")
    if any(not _SHA256_RE.fullmatch(actual_binding[name]) for name in
           ("manifest_sha256", "dataset_manifest_sha256", "raw_archive_tree_sha256")):
        _deny("AUTHORIZATION_BINDING_MALFORMED")
    if actual_binding != expected:
        # Stable, field-specific codes make remediation and audit receipts useful.
        code_by_field = {
            "implementation_commit": "AUTHORIZATION_COMMIT_MISMATCH",
            "manifest_sha256": "AUTHORIZATION_MANIFEST_MISMATCH",
            "dataset_manifest_sha256": "AUTHORIZATION_DATASET_MISMATCH",
            "raw_archive_tree_sha256": "AUTHORIZATION_ARCHIVE_IDENTITY_MISMATCH",
            "experiment_id": "AUTHORIZATION_EXPERIMENT_MISMATCH",
            "protocol_version": "AUTHORIZATION_PROTOCOL_MISMATCH",
            "execution_mode": "AUTHORIZATION_EXECUTION_MODE_MISMATCH",
            "source_kind": "AUTHORIZATION_SOURCE_KIND_MISMATCH",
        }
        for field in AUTHORIZATION_CONTEXT_FIELDS:
            if actual_binding.get(field) != expected[field]:
                _deny(code_by_field[field])

    scope = contract.get("scope")
    expected_scope_copy = _scope_mapping(expected_scope, "AUTHORIZATION_EXPECTED_SCOPE_INVALID")
    actual_scope = _scope_mapping(scope, "AUTHORIZATION_SCOPE_INVALID")
    if (actual_scope["experiment_id"] != actual_binding["experiment_id"]
            or actual_scope["execution_mode"] != actual_binding["execution_mode"]):
        _deny("AUTHORIZATION_SCOPE_BINDING_MISMATCH")
    if actual_scope != expected_scope_copy:
        _deny("AUTHORIZATION_SCOPE_MISMATCH")

    kind = contract.get("authorization_kind")
    if kind == "TEST_ONLY":
        if allow_test_only is not True:
            _deny("TEST_ONLY_AUTHORIZATION_NOT_ENABLED")
        source_kind = expected["source_kind"].upper()
        execution_mode = expected["execution_mode"].upper()
        if (not source_kind.startswith("SYNTHETIC")
                or any(token in source_kind for token in ("ARCHIVE", "PROTECTED", "REAL"))
                or not execution_mode.startswith("SYNTHETIC")):
            _deny("TEST_ONLY_AUTHORIZATION_FORBIDDEN_FOR_REAL_DATA")
    elif kind == "EXTERNAL":
        if expected["execution_mode"] != "PROTECTED_OOS":
            _deny("EXTERNAL_AUTHORIZATION_MODE_INVALID")
    else:
        _deny("AUTHORIZATION_KIND_INVALID")

    return VerifiedAuthorization(contract, _token=_VERIFIED_TOKEN)


def is_verified_authorization(
    value: object,
    *,
    expected_context: object,
    expected_scope: Mapping[str, Any],
) -> bool:
    """Revalidate a capability at a trust boundary; mutation invalidates it."""
    if not isinstance(value, VerifiedAuthorization) or value._token is not _VERIFIED_TOKEN:
        return False
    try:
        contract = value._contract
        if authorization_contract_sha256(contract) != value._contract_sha256:
            return False
        if _sha256(contract["binding"]) != value._binding_sha256:
            return False
        if _sha256(contract["scope"]) != value._scope_sha256:
            return False
        return (dict(contract["binding"]) == _context_mapping(expected_context)
                and dict(contract["scope"]) == _scope_mapping(
                    expected_scope, "AUTHORIZATION_EXPECTED_SCOPE_INVALID"))
    except (AuthorizationDenied, KeyError, TypeError, ValueError):
        return False
