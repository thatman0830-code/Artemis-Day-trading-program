"""Fail-closed tests for Phase 5C-Z external authorization contracts."""
from __future__ import annotations

import copy
import json

import pytest

from bot2.phase5c_v3.authorization import (
    AUTHORIZATION_SCHEMA,
    AuthorizationDenied,
    authorization_contract_sha256,
    is_verified_authorization,
    load_authorization_document,
    validate_authorization_contract,
)


def _digest(letter: str) -> str:
    return letter * 64


REAL_CONTEXT = {
    "source_kind": "PASS_B_PROTECTED_ARCHIVE",
    "implementation_commit": "a" * 40,
    "manifest_sha256": _digest("b"),
    "dataset_manifest_sha256": _digest("c"),
    "raw_archive_tree_sha256": _digest("d"),
    "protocol_version": "bot2-phase5c-experiment-manifest-v3",
    "experiment_id": "phase5c-frozen-real-experiment",
    "execution_mode": "PROTECTED_OOS",
}

SYNTHETIC_CONTEXT = {
    "source_kind": "SYNTHETIC_TEST_DATASET_V1",
    "implementation_commit": "a" * 40,
    "manifest_sha256": _digest("b"),
    "dataset_manifest_sha256": _digest("c"),
    "raw_archive_tree_sha256": _digest("d"),
    "protocol_version": "bot2-phase5c-experiment-manifest-v3",
    "experiment_id": "phase5c-frozen-synthetic-test",
    "execution_mode": "SYNTHETIC_AUTHORIZED_CONTINUATION",
}


def _scope(context: dict) -> dict:
    return {
        "experiment_id": context["experiment_id"],
        "execution_mode": context["execution_mode"],
        "cell_sha256s": [_digest("e"), _digest("f")],
    }


def _document(context: dict, *, kind: str = "EXTERNAL", scope: dict | None = None) -> dict:
    result = {
        "schema_version": AUTHORIZATION_SCHEMA,
        "authorization_id": "external-approval-ticket-2026-09-23",
        "authorization_kind": kind,
        "binding": copy.deepcopy(context),
        "scope": copy.deepcopy(scope if scope is not None else _scope(context)),
        "authorization_sha256": "",
    }
    result["authorization_sha256"] = authorization_contract_sha256(result)
    return result


def _verify(document: dict, context: dict, *, scope: dict | None = None,
            trusted_digest: str | None = None, allow_test_only: bool = False):
    return validate_authorization_contract(
        document,
        expected_context=context,
        expected_scope=scope if scope is not None else _scope(context),
        trusted_authorization_sha256=(trusted_digest if trusted_digest is not None
                                      else document["authorization_sha256"]),
        allow_test_only=allow_test_only,
    )


def _assert_denied(reason: str, function, *args, **kwargs) -> None:
    with pytest.raises(AuthorizationDenied) as error:
        function(*args, **kwargs)
    assert error.value.reason_code == reason


def test_valid_external_contract_requires_an_independent_digest_and_exact_binding():
    document = _document(REAL_CONTEXT)
    verified = _verify(document, REAL_CONTEXT)
    assert verified.authorization_sha256 == document["authorization_sha256"]
    assert verified.binding == REAL_CONTEXT
    assert verified.scope == _scope(REAL_CONTEXT)
    assert is_verified_authorization(verified, expected_context=REAL_CONTEXT,
                                     expected_scope=_scope(REAL_CONTEXT))
    assert not is_verified_authorization(verified, expected_context=SYNTHETIC_CONTEXT,
                                         expected_scope=_scope(SYNTHETIC_CONTEXT))


@pytest.mark.parametrize(("field", "reason"), [
    ("implementation_commit", "AUTHORIZATION_COMMIT_MISMATCH"),
    ("manifest_sha256", "AUTHORIZATION_MANIFEST_MISMATCH"),
    ("dataset_manifest_sha256", "AUTHORIZATION_DATASET_MISMATCH"),
    ("raw_archive_tree_sha256", "AUTHORIZATION_ARCHIVE_IDENTITY_MISMATCH"),
    ("protocol_version", "AUTHORIZATION_PROTOCOL_MISMATCH"),
    ("experiment_id", "AUTHORIZATION_EXPERIMENT_MISMATCH"),
    ("execution_mode", "AUTHORIZATION_EXECUTION_MODE_MISMATCH"),
    ("source_kind", "AUTHORIZATION_SOURCE_KIND_MISMATCH"),
])
def test_every_provenance_binding_mismatch_denies(field: str, reason: str):
    document = _document(REAL_CONTEXT)
    changed_context = dict(REAL_CONTEXT)
    if field == "implementation_commit":
        changed_context[field] = "9" * 40
    elif field in {"manifest_sha256", "dataset_manifest_sha256", "raw_archive_tree_sha256"}:
        changed_context[field] = _digest("0")
    else:
        changed_context[field] = changed_context[field] + "-wrong"
    _assert_denied(reason, _verify, document, changed_context)


def test_missing_untrusted_or_modified_contract_denies():
    document = _document(REAL_CONTEXT)
    _assert_denied("AUTHORIZATION_TRUST_ANCHOR_REQUIRED",
        validate_authorization_contract, document, expected_context=REAL_CONTEXT,
        expected_scope=_scope(REAL_CONTEXT), trusted_authorization_sha256=None)
    _assert_denied("AUTHORIZATION_DOCUMENT_MODIFIED_OR_UNTRUSTED",
        _verify, document, REAL_CONTEXT, trusted_digest=_digest("0"))

    approved_digest = document["authorization_sha256"]
    changed = copy.deepcopy(document)
    changed["authorization_id"] = "silently-edited-ticket"
    # Recomputing the document's own self-hash cannot replace the separately
    # held approval digest.
    changed["authorization_sha256"] = authorization_contract_sha256(changed)
    _assert_denied("AUTHORIZATION_DOCUMENT_MODIFIED_OR_UNTRUSTED",
        _verify, changed, REAL_CONTEXT, trusted_digest=approved_digest)


def test_wrong_schema_and_unknown_contract_fields_fail_closed():
    document = _document(REAL_CONTEXT)
    wrong_schema = copy.deepcopy(document)
    wrong_schema["schema_version"] = "future-schema"
    wrong_schema["authorization_sha256"] = authorization_contract_sha256(wrong_schema)
    _assert_denied("AUTHORIZATION_SCHEMA_MISMATCH", _verify, wrong_schema, REAL_CONTEXT)

    extra_field = copy.deepcopy(document)
    extra_field["allow_any"] = True
    extra_field["authorization_sha256"] = authorization_contract_sha256(extra_field)
    _assert_denied("AUTHORIZATION_DOCUMENT_MALFORMED", _verify, extra_field, REAL_CONTEXT)


def test_exact_scope_mismatch_unknown_id_or_wildcard_denies():
    document = _document(REAL_CONTEXT)
    wrong_scope = _scope(REAL_CONTEXT)
    wrong_scope["cell_sha256s"] = [_digest("0")]
    _assert_denied("AUTHORIZATION_SCOPE_MISMATCH", _verify, document, REAL_CONTEXT,
                   scope=wrong_scope)

    for cell_ids, reason in (([], "AUTHORIZATION_SCOPE_INVALID"),
                             (["*"], "AUTHORIZATION_SCOPE_INVALID"),
                             ([_digest("e"), _digest("e")],
                              "AUTHORIZATION_SCOPE_CELL_IDS_NOT_CANONICAL"),
                             ([_digest("f"), _digest("e")],
                              "AUTHORIZATION_SCOPE_CELL_IDS_NOT_CANONICAL")):
        changed = _scope(REAL_CONTEXT)
        changed["cell_sha256s"] = cell_ids
        malformed = _document(REAL_CONTEXT, scope=changed)
        _assert_denied(reason, _verify, malformed, REAL_CONTEXT)


def test_test_only_contract_cannot_authorize_real_archive_or_protected_mode():
    document = _document(REAL_CONTEXT, kind="TEST_ONLY")
    _assert_denied("TEST_ONLY_AUTHORIZATION_NOT_ENABLED", _verify, document, REAL_CONTEXT)
    _assert_denied("TEST_ONLY_AUTHORIZATION_FORBIDDEN_FOR_REAL_DATA", _verify,
                   document, REAL_CONTEXT, allow_test_only=True)

    synthetic_but_protected_mode = dict(SYNTHETIC_CONTEXT, execution_mode="PROTECTED_OOS")
    mismatched = _document(synthetic_but_protected_mode, kind="TEST_ONLY")
    _assert_denied("TEST_ONLY_AUTHORIZATION_FORBIDDEN_FOR_REAL_DATA", _verify,
                   mismatched, synthetic_but_protected_mode, allow_test_only=True)


def test_test_only_contract_is_scoped_to_synthetic_context_only():
    document = _document(SYNTHETIC_CONTEXT, kind="TEST_ONLY")
    verified = _verify(document, SYNTHETIC_CONTEXT, allow_test_only=True)
    assert verified.binding["source_kind"].startswith("SYNTHETIC")
    assert verified.binding["execution_mode"].startswith("SYNTHETIC")
    assert is_verified_authorization(verified, expected_context=SYNTHETIC_CONTEXT,
                                     expected_scope=_scope(SYNTHETIC_CONTEXT))


def test_invalid_authorization_denies_before_any_future_effects():
    """The intended gate order is explicit: validate first, effects second."""
    document = _document(REAL_CONTEXT)
    approved_digest = document["authorization_sha256"]
    # Test the authorization boundary with sentinels representing each forbidden
    # downstream effect. This module itself has no inference/scoring/publishing
    # callbacks and cannot produce any of them.
    effects = {"inference": 0, "scoring": 0, "artifact": 0}

    def future_gated_path(candidate, digest):
        authorization = validate_authorization_contract(
            candidate, expected_context=REAL_CONTEXT, expected_scope=_scope(REAL_CONTEXT),
            trusted_authorization_sha256=digest,
        )
        # Future integration must remain below successful validation.
        effects["inference"] += 1
        effects["scoring"] += 1
        effects["artifact"] += 1
        return authorization

    changed = copy.deepcopy(document)
    changed["binding"]["implementation_commit"] = "9" * 40
    changed["authorization_sha256"] = authorization_contract_sha256(changed)
    _assert_denied("AUTHORIZATION_DOCUMENT_MODIFIED_OR_UNTRUSTED",
                   future_gated_path, changed, approved_digest)
    assert effects == {"inference": 0, "scoring": 0, "artifact": 0}


def test_duplicate_json_keys_are_rejected_before_mapping_construction(tmp_path):
    path = tmp_path / "duplicate-authorization.json"
    path.write_text('{"schema_version":"first","schema_version":"second"}',
                    encoding="utf-8")
    _assert_denied("AUTHORIZATION_DOCUMENT_DUPLICATE_KEY", load_authorization_document,
                   path)


def test_verified_wrapper_returns_defensive_copies_and_revalidation_detects_mutation():
    document = _document(REAL_CONTEXT)
    verified = _verify(document, REAL_CONTEXT)
    returned = verified.contract
    returned["binding"]["experiment_id"] = "attacker-edited"
    assert is_verified_authorization(verified, expected_context=REAL_CONTEXT,
                                     expected_scope=_scope(REAL_CONTEXT))

    # Bypass attempts through ordinary attribute assignment are refused.
    with pytest.raises(AttributeError, match="VERIFIED_AUTHORIZATION_IS_IMMUTABLE"):
        verified._contract = {}

    # Even low-level object mutation invalidates the verified capability.
    object.__setattr__(verified, "_contract", {})
    assert not is_verified_authorization(verified, expected_context=REAL_CONTEXT,
                                         expected_scope=_scope(REAL_CONTEXT))
