"""Real-archive Phase 5C structural preflight. This module has no inference path."""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

import numpy as np

from backtesting.core_v1.production_adapters import PassBV3ArchiveAdapter
from bot2.data_foundation.contracts import MarketEvent
from bot2.data_foundation.instruments import normalize_contract
from bot2.data_foundation.sync import synchronize_contract_roots
from bot2.features_labels.features import FEATURE_NAMES_V3, generate_features
from bot2.features_labels.targets_v3 import TARGET_SPEC, generate_future_targets
from bot2.features_labels.contracts import config_hash
from bot2.neural.sequences import DEFAULT_CATEGORICAL_ENCODINGS
from .data_integrity import MarketObservation, build_authorized_split, validate_authorized_split
from .experiment_controls import (apply_ablation_mask, create_ablation_contract,
    create_model_input_contract, validate_model_input_contract, verify_ablation_contract)
from .experiment_matrix import derive_walk_forward_windows, expected_cell_ledger, validate_walk_forward_rows
from .manifest import load_verified_manifest
from .model import TrainingOnlyStandardizer, expected_parameter_count
from .no_score_boundary import protected_no_score_boundary

NO_SCORE_SCHEMA = "bot2-phase5c-v3-protected-preflight-no-score-v1"
TARGET_CLASS = {
    "direction": {"DOWN": 0, "FLAT": 1, "UP": 2},
    "volatility": {"LOW": 0, "NORMAL": 1, "HIGH": 2},
    "structure": {"RANGE": 0, "TRANSITION": 1, "TREND": 2},
}


@dataclass(frozen=True, slots=True)
class VerifiedCellInputs:
    """Ephemeral, verified arrays shared by preflight and any future authorized continuation."""
    cell: Mapping
    split: object
    input_contract: Mapping
    ablation_contract: Mapping | None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return _sha(raw)


def _assert_score_free_payload(value: object) -> None:
    """Reject non-count prediction/scoring artifacts before publication."""
    forbidden = {"predictions", "probabilities", "metrics", "pnl", "trades",
        "signals", "model_outputs", "logits", "performance", "confusion_matrix"}
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in forbidden:
                raise ValueError("PROTECTED_SCORE_ARTIFACT_KEY_FORBIDDEN")
            _assert_score_free_payload(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_score_free_payload(child)


def _validate_frozen_feature_registry(verified, repository_root: Path) -> tuple[dict, str]:
    spec = verified.data["feature_specification"]
    registry_path = (repository_root / spec["registry_path"]).resolve(strict=True)
    payload = registry_path.read_bytes().replace(b"\r\n", b"\n")
    digest = _sha(payload)
    if digest != spec["registry_sha256"]:
        raise ValueError("FEATURE_REGISTRY_HASH_MISMATCH")
    registry = json.loads(payload.decode("utf-8"))
    if (registry.get("schema_version") != spec["registry_version"]
            or registry.get("feature_schema") != spec["schema_version"]
            or tuple(registry.get("features", ())) != tuple(spec["features"])
            or registry.get("categorical_encoding") != DEFAULT_CATEGORICAL_ENCODINGS
            or registry.get("future_information_in_features") is not False):
        raise ValueError("FEATURE_SCHEMA_MISMATCH:REGISTRY_CONTRACT")
    return registry, digest


def _validate_frozen_target_specification(verified) -> str:
    spec = verified.data["target_specification"]
    digest = config_hash(TARGET_SPEC)
    if (digest != spec["spec_sha256"] or TARGET_SPEC.get("version") != spec["version"]
            or tuple(TARGET_SPEC.get("horizons_minutes", ()))
               != tuple(spec["horizons_minutes"])):
        raise ValueError("TARGET_SCHEMA_MISMATCH:FROZEN_TARGET_SPECIFICATION")
    return digest


def _bar_event(item) -> MarketEvent:
    bar = item.bar
    return MarketEvent(bar.instrument_id, "CME", "OHLCV_1M_BAR_CLOSE",
        bar.close_time, None, float(bar.close), float(bar.volume), sequence=bar.sequence,
        # The archive adapter's contract_id is a content identity hash.  The
        # Phase 5C experiment identity is the exact listed contract symbol,
        # which the same archive preserves as instrument_id (e.g. ESM5).
        event_id=bar.id, session_id=bar.session_id, contract_id=bar.instrument_id,
        timestamp_source="HISTORICAL_EXCHANGE_EVENT")


def _load_market_events(*, repository_root: Path, archive_root: Path, root: str):
    adapter = PassBV3ArchiveAdapter(market=root, repository_root=repository_root,
        archive_root=archive_root, plan_root=repository_root / "data/backtests/es_nq_pass_b_plan_3",
        continuation_root=repository_root / "data/backtests/es_nq_pass_b_continuation_plan_1",
        final_audit_path=repository_root / "outputs/archive_audits/es_nq_pass_b_final_audit.json")
    metadata = adapter.validate()
    events = tuple(_bar_event(item) for item in adapter.iter_events())
    if not events:
        raise ValueError("MISSING_INPUT:EMPTY_ARCHIVE_MARKET")
    return metadata, events


def _observations_by_root_horizon(verified, events_by_root):
    manifest = verified.data
    feature_names = tuple(manifest["feature_specification"]["features"])
    if feature_names != tuple(FEATURE_NAMES_V3):
        raise ValueError("FEATURE_SCHEMA_MISMATCH:FEATURE_ORDER_OR_VERSION")
    if (manifest["feature_specification"].get("sequence_length") != 8
            or manifest["feature_specification"].get("sequence_cadence_seconds") != 60):
        raise ValueError("FEATURE_SCHEMA_MISMATCH:SEQUENCE_CADENCE_OR_LENGTH")
    target_version = manifest["target_specification"]["version"]
    horizons = tuple(manifest["target_specification"]["horizons_minutes"])
    dataset_sha = manifest["source_dataset_manifest_sha256"]
    feature_schema_version = manifest["feature_specification"]["schema_version"]
    feature_registry_version = manifest["feature_specification"]["registry_version"]
    by_session: dict[str, dict[str, list[MarketEvent]]] = defaultdict(lambda: {"ES": [], "NQ": []})
    for root, events in events_by_root.items():
        for event in events:
            by_session[event.session_id or ""][root].append(event)

    observations = {(root, horizon): [] for root in ("ES", "NQ") for horizon in horizons}
    feature_invalid = Counter()
    target_invalid = Counter()
    structural_target_hash_inputs = []
    session_alignment = Counter()
    for session_id, market_events in sorted(by_session.items()):
        instruments = {}
        root_groups = {}
        for root, rows in market_events.items():
            for event in rows:
                instruments.setdefault(event.instrument, []).append(event)
                root_groups[event.instrument] = root
        if not instruments:
            continue
        result = synchronize_contract_roots(market_events["ES"], market_events["NQ"])
        session_alignment["exact_matches"] += result[1].exact_matches
        session_alignment["unmatched_es"] += result[1].es_unmatched
        session_alignment["unmatched_nq"] += result[1].nq_unmatched
        features = generate_features(instruments, source_dataset_id="phase5b-esnq-passb-v3",
            source_dataset_sha256=dataset_sha, root_groups=root_groups)
        features_by_instrument_time = {(row.instrument, row.observation_time): row for row in features}
        for instrument, rows in sorted(instruments.items()):
            rows.sort(key=lambda event: event.exchange_time)
            targets = generate_future_targets({instrument: rows}, horizons=horizons)
            target_by_key = {(row.instrument, row.observation_time, row.horizon_minutes): row
                             for row in targets}
            root = root_groups[instrument]
            session_open = rows[0].exchange_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            for event in rows:
                stamp = event.exchange_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                feature = features_by_instrument_time.get((instrument, stamp))
                if feature is None:
                    feature_invalid["FEATURE_ROW_MISSING"] += 1
                    continue
                if feature.schema_version != feature_schema_version:
                    feature_invalid["FEATURE_SCHEMA_VERSION_MISMATCH"] += 1
                    continue
                if feature.feature_version != feature_registry_version:
                    feature_invalid["FEATURE_REGISTRY_VERSION_MISMATCH"] += 1
                    continue
                if feature.validity != "VALID":
                    reasons = feature.reason_codes or ("FEATURE_NOT_VALID",)
                    for reason in reasons:
                        feature_invalid[f"FEATURE_INVALID:{reason}"] += 1
                    continue
                values = []
                for name in feature_names:
                    value = feature.values.get(name)
                    if value is not None and name in DEFAULT_CATEGORICAL_ENCODINGS:
                        value = DEFAULT_CATEGORICAL_ENCODINGS[name].get(value)
                    values.append(value)
                if any(value is None for value in values):
                    feature_invalid["FEATURE_VALID_ROW_HAS_MISSING_VALUE"] += 1
                    continue
                try:
                    feature_values = tuple(float(value) for value in values)
                except (TypeError, ValueError):
                    feature_invalid["FEATURE_VALUE_NOT_NUMERIC"] += 1
                    continue
                if not np.isfinite(np.asarray(feature_values, dtype=np.float64)).all():
                    feature_invalid["FEATURE_VALUE_NONFINITE"] += 1
                    continue
                for horizon in horizons:
                    target = target_by_key.get((instrument, stamp, horizon))
                    if target is None:
                        target_invalid[f"{horizon}:TARGET_ROW_MISSING"] += 1
                        continue
                    # Fingerprint only structural target facts, never class/outcome values.
                    structural_target_hash_inputs.append((target.instrument, target.session_id,
                        target.observation_time, target.horizon_minutes, target.validity,
                        tuple(sorted(target.reason_codes)), target.label_end_time))
                    if target.target_version != target_version or target.validity != "VALID":
                        reason = (target.reason_codes[0] if target.reason_codes else "TARGET_INVALID")
                        target_invalid[f"{horizon}:{reason}"] += 1
                        continue
                    labels = {"direction": target.future_direction,
                        "volatility": target.future_volatility_state,
                        "structure": target.future_structure}
                    try:
                        encoded = {head: TARGET_CLASS[head][labels[head]] for head in TARGET_CLASS}
                    except (KeyError, TypeError):
                        target_invalid[f"{horizon}:TARGET_CLASS_SCHEMA_MISMATCH"] += 1
                        continue
                    observations[(root, horizon)].append(MarketObservation(root,
                        target.contract_id, target.session_id, stamp, session_open,
                        feature_names, feature_values, encoded, target.label_end_time,
                        dataset_sha, feature_schema_version, target_version))
    for rows in observations.values():
        rows.sort(key=lambda row: (row.exchange_timestamp_utc, row.contract))
    target_structural_fingerprint = _canonical_sha(structural_target_hash_inputs)
    return observations, feature_invalid, target_invalid, session_alignment, target_structural_fingerprint


def _partition_rows(rows, window):
    spans = {"TRAIN": window.train,
        "VALIDATION_AND_CALIBRATION": window.validation, "OOS_TEST": window.test}
    output, boundary_exclusions = {}, {}
    for name, (start, end) in spans.items():
        eligible, excluded = [], 0
        for row in rows:
            observation_day = row.exchange_timestamp_utc[:10]
            if not start <= observation_day <= end:
                continue
            if row.label_end_utc[:10] > end:
                excluded += 1
                continue
            eligible.append(row)
        output[name] = tuple(eligible)
        boundary_exclusions[name] = excluded

    purge_exclusions = _apply_walk_forward_purge(output,
        purge_minutes=int(window.purge_minutes))
    return spans, output, boundary_exclusions, purge_exclusions


def _apply_walk_forward_purge(output, *, purge_minutes: int) -> dict[str, int]:
    """Drop prior-partition labels that reach the next partition's purge zone."""
    # The manifest defines purge in elapsed time relative to the first actual
    # observation in the following partition, not relative to midnight on its
    # first calendar day. The strict validators independently repeat this check.
    purge = timedelta(minutes=int(purge_minutes))
    purge_exclusions = {}
    for previous, following in zip(
            ("TRAIN", "VALIDATION_AND_CALIBRATION"),
            ("VALIDATION_AND_CALIBRATION", "OOS_TEST")):
        following_rows = output[following]
        if not following_rows:
            purge_exclusions[previous] = 0
            continue
        first_next = min(datetime.fromisoformat(
            row.exchange_timestamp_utc.replace("Z", "+00:00"))
            for row in following_rows)
        cutoff = first_next - purge
        retained, excluded = [], 0
        for row in output[previous]:
            label_end = datetime.fromisoformat(row.label_end_utc.replace("Z", "+00:00"))
            if label_end >= cutoff:
                excluded += 1
            else:
                retained.append(row)
        output[previous] = tuple(retained)
        purge_exclusions[previous] = excluded
    purge_exclusions["OOS_TEST"] = 0
    return purge_exclusions


def _cell_readiness(verified, cell, split, sample_x, oos_structure,
        boundary_exclusions):
    identity = cell["identity"]
    if int(oos_structure["count"]) <= 0:
        raise ValueError("SEQUENCE_INVALID:NO_OOS_SEQUENCE")
    model_id = identity["model_id"]
    neural = model_id in {"A1_NUMPY_MULTIHEAD_MLP", "A2_LEARNED_CAUSAL_TCN"}
    ablation = create_ablation_contract(verified, identity["ablation_id"]) if neural else None
    if ablation is not None:
        verify_ablation_contract(ablation, verified)
        masked = apply_ablation_mask(sample_x, contract=ablation, verified_manifest=verified,
            feature_order=tuple(verified.data["feature_specification"]["features"]))
        if masked.shape != sample_x.shape or masked.shape[-1] != 24:
            raise ValueError("ABLATION_MISMATCH:INPUT_WIDTH_CHANGED")
        if oos_structure["sample_x"] is None:
            raise ValueError("SEQUENCE_INVALID:NO_OOS_SEQUENCE")
        oos_masked = apply_ablation_mask(oos_structure["sample_x"], contract=ablation,
            verified_manifest=verified,
            feature_order=tuple(verified.data["feature_specification"]["features"]))
        if oos_masked.shape != (1, 8, 24) or not np.isfinite(oos_masked).all():
            raise ValueError("ABLATION_MISMATCH:OOS_INPUT_SHAPE_OR_VALUE")
        if model_id == "A2_LEARNED_CAUSAL_TCN" and expected_parameter_count(24) != 7417:
            raise ValueError("ABLATION_MISMATCH:A2_PARAMETER_COUNT_CHANGED")
    seed = (identity["seed"] if isinstance(identity["seed"], int)
            else int(verified.data["random_seeds"][0]))
    contract = create_model_input_contract(verified, model_id=model_id,
        seed=seed, ablation_id=(identity["ablation_id"] if neural else "ALL"))
    actual_features = tuple(contract["features"])
    actual_shape = list(sample_x.shape[1:]) if neural else []
    mask = ablation["feature_mask"] if ablation is not None else None
    latest = split.validation.sequence_keys[-1][-1][2] if len(split.validation.sequence_keys) else ""
    contains_target_labels = model_id in {
        "A0_PREVIOUS_LABEL_PERSISTENCE", "A0_TRAIN_TRANSITION_MATRIX"}
    label_information_end = None
    if contains_target_labels:
        terminal = split.validation.sequence_keys[-1][-1]
        decision = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        prior = [row for row in split.canonical_rows["VALIDATION_AND_CALIBRATION"]
            if row.contract == terminal[0] and row.session_id == terminal[1]
            and datetime.fromisoformat(row.exchange_timestamp_utc.replace("Z", "+00:00")) < decision
            and datetime.fromisoformat(row.label_end_utc.replace("Z", "+00:00")) <= decision]
        if not prior:
            raise ValueError("A0_PRIOR_LABEL_INELIGIBLE")
        eligible_prior = max(prior, key=lambda row: row.exchange_timestamp_utc)
        label_information_end = eligible_prior.label_end_utc
    validate_model_input_contract(contract, verified, actual_features=actual_features,
        actual_sequence_shape=actual_shape, actual_feature_mask=mask,
        latest_input_timestamp_utc=latest, decision_timestamp_utc=latest,
        contains_target_labels=contains_target_labels,
        label_information_end_utc=label_information_end)
    control = identity["control_condition"]
    if control != "NONE":
        prefix = "SHUFFLED_TRAIN_LABELS:"
        if (not neural or not control.startswith(prefix)
                or int(control[len(prefix):]) not in verified.data["shuffled_label_control"]["seeds"]):
            raise ValueError("CONTROL_CONFIGURATION_INVALID")
    return {"cell_sha256": cell["cell_sha256"], "manifest_sha256": verified.sha256,
        "dataset_sha256": identity["dataset_identity"], **identity,
        "partition_fingerprints": dict(split.partition_fingerprints),
        "target_boundary_exclusions": dict(boundary_exclusions),
        "feature_schema": verified.data["feature_specification"]["schema_version"],
        "feature_order_sha256": _canonical_sha(list(actual_features)),
        "feature_width": 24, "input_schema": contract["architecture_version"],
        "input_shape": actual_shape, "eligible_rows": {
            "TRAIN": int(len(split.train.x)),
            "VALIDATION_AND_CALIBRATION": int(len(split.validation.x)),
            "OOS_TEST": int(oos_structure["count"])},
        "oos_sequence_fingerprint": oos_structure["fingerprint"],
        "ablation_sha256": ablation["ablation_sha256"] if ablation else None,
        "control_plan": control, "status": "READY", "reason_code": None}


def _validate_oos_sequence_structure(split, scaler, verified) -> dict:
    """Validate all OOS sequence/input windows without retaining labels or scores."""
    manifest = verified.data
    rows = split.canonical_rows["OOS_TEST"]
    length = int(manifest["feature_specification"]["sequence_length"])
    cadence = int(manifest["feature_specification"]["sequence_cadence_seconds"])
    horizon = int(split.horizon_minutes)
    digest = hashlib.sha256(b"[")
    count = 0
    sample_x = None
    for end in range(length - 1, len(rows)):
        window = rows[end - length + 1:end + 1]
        times = [datetime.fromisoformat(row.exchange_timestamp_utc.replace("Z", "+00:00"))
            for row in window]
        if any(left.contract != right.contract or left.session_id != right.session_id
                or right_time - left_time != timedelta(seconds=cadence)
                for left, right, left_time, right_time in zip(
                    window, window[1:], times, times[1:])):
            continue
        terminal = window[-1]
        label_end = datetime.fromisoformat(terminal.label_end_utc.replace("Z", "+00:00"))
        if label_end != times[-1] + timedelta(minutes=horizon):
            raise ValueError("TARGET_SCHEMA_MISMATCH:OOS_HORIZON_BOUNDARY")
        raw = np.asarray([[row.features for row in window]], dtype=np.float64)
        transformed = scaler.transform(raw)
        expected_shape = (1, length, len(manifest["feature_specification"]["features"]))
        if transformed.shape != expected_shape or not np.isfinite(transformed).all():
            raise ValueError("SEQUENCE_INVALID:OOS_INPUT_SHAPE_OR_VALUE")
        identity = [(row.contract, row.session_id, row.exchange_timestamp_utc)
            for row in window]
        if count:
            digest.update(b",")
        digest.update(json.dumps(identity, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False).encode("utf-8"))
        count += 1
        if sample_x is None:
            sample_x = transformed
    digest.update(b"]")
    return {"count": count, "fingerprint": digest.hexdigest(), "sample_x": sample_x}


def run_protected_preflight_no_score(*, manifest_path: str | Path,
        external_anchor_path: str | Path, archive_root: str | Path,
        output_path: str | Path, repository_root: str | Path | None = None) -> dict:
    """Validate real protected inputs, and stop before any model operation.

    Only aggregate structural counts, opaque fingerprints, and per-cell input
    receipts are written. Target class values are never included in output.
    """
    destination = Path(output_path)
    if os.path.lexists(destination):
        raise ValueError("PREFLIGHT_OUTPUT_ALREADY_EXISTS")
    archive = Path(archive_root).resolve()
    repo = (Path(repository_root).resolve() if repository_root else archive.parents[2])
    verified = load_verified_manifest(manifest_path, external_anchor_path=external_anchor_path)
    manifest = verified.data
    _, feature_registry_sha = _validate_frozen_feature_registry(verified, repo)
    target_spec_sha = _validate_frozen_target_specification(verified)
    with protected_no_score_boundary() as blocked_operations:
        data = {}
        for root in ("ES", "NQ"):
            metadata, events = _load_market_events(repository_root=repo,
                archive_root=archive, root=root)
            data[root] = {"metadata": metadata, "events": events,
                "event_count": len(events)}
            if metadata.lineage.archive_sha256 != verified.pin["raw_archive_tree_sha256"]:
                raise ValueError("DATASET_IDENTITY_MISMATCH")
        observations, feature_invalid, target_invalid, alignment, target_fp = \
            _observations_by_root_horizon(verified,
                {root: data[root]["events"] for root in data})
        # Keep only adapter lineage after normalization; the canonical
        # MarketObservation set is the reusable input source for every WF.
        for root in data:
            del data[root]["events"]
        del events
        ledger = expected_cell_ledger(verified)
        cells = ledger["cells"]
        if len({cell["cell_sha256"] for cell in cells}) != len(cells):
            raise ValueError("MATRIX_DUPLICATE_CELL_IDENTITY")
        windows = {window.window_id: window for window in derive_walk_forward_windows(verified)}
        cells_by_group: dict[tuple[str, int, str], list[Mapping]] = defaultdict(list)
        for cell in cells:
            identity = cell["identity"]
            cells_by_group[(identity["root"], int(identity["horizon_minutes"]),
                identity["walk_forward_window"])].append(cell)
        receipt_by_id = {}
        group_failure_count = 0
        boundary_exclusion_totals = {}
        purge_exclusion_totals = {}
        for root in ("ES", "NQ"):
            for horizon in manifest["target_specification"]["horizons_minutes"]:
                for window_id, window in windows.items():
                    key = (root, int(horizon), window_id)
                    group_cells = cells_by_group.get(key, ())
                    try:
                        spans, parts, boundary_exclusions, purge_exclusions = _partition_rows(
                            observations[key[:2]], window)
                        for partition, excluded in boundary_exclusions.items():
                            boundary_exclusion_totals[
                                f"{root}:{horizon}:{window_id}:{partition}"] = excluded
                        for partition, excluded in purge_exclusions.items():
                            purge_exclusion_totals[
                                f"{root}:{horizon}:{window_id}:{partition}"] = excluded
                        validate_walk_forward_rows(verified, root=root,
                            horizon_minutes=int(horizon), window_id=window_id,
                            rows_by_partition=parts)
                        scaler = TrainingOnlyStandardizer().fit_observations(parts["TRAIN"],
                            market=root, verified_manifest=verified,
                            code_commit=verified.pin["review_candidate_commit"])
                        split = build_authorized_split(verified, market=root,
                            horizon_minutes=int(horizon), partition_rows=parts,
                            preprocessor=scaler, walk_forward_window_id=window_id)
                        validate_authorized_split(split, verified)
                        oos_structure = _validate_oos_sequence_structure(split,
                            scaler, verified)
                        if (split.train.x.ndim != 3 or split.train.x.shape[1:] != (8,24)
                                or split.validation.x.ndim != 3 or split.validation.x.shape[1:] != (8,24)
                                or oos_structure["sample_x"] is None
                                or oos_structure["sample_x"].shape != (1,8,24)):
                            raise ValueError("SEQUENCE_INVALID:INPUT_SHAPE_MISMATCH")
                    except Exception as exc:
                        group_failure_count += 1
                        reason = getattr(exc, "reason_code", None) or str(exc)
                        for cell in group_cells:
                            ident = cell["identity"]
                            receipt_by_id[cell["cell_sha256"]] = {
                                "cell_sha256": cell["cell_sha256"],
                                "manifest_sha256": verified.sha256,
                                "dataset_sha256": manifest["source_dataset_manifest_sha256"],
                                **ident, "status": "NOT_READY", "reason_code": reason}
                        continue
                    for cell in group_cells:
                        ident = cell["identity"]
                        try:
                            sample = split.validation.x[:1]
                            if not len(sample):
                                raise ValueError("SEQUENCE_INVALID:NO_VALIDATION_SEQUENCE")
                            receipt_by_id[cell["cell_sha256"]] = _cell_readiness(
                                verified, cell, split, sample, oos_structure,
                                {"label_end_after_partition": boundary_exclusions,
                                 "walk_forward_purge": purge_exclusions})
                        except Exception as exc:
                            receipt_by_id[cell["cell_sha256"]] = {
                                "cell_sha256": cell["cell_sha256"],
                                "manifest_sha256": verified.sha256,
                                "dataset_sha256": manifest["source_dataset_manifest_sha256"],
                                **ident, "status": "NOT_READY",
                                "reason_code": getattr(exc, "reason_code", None) or str(exc)}
                    del split, scaler, parts, oos_structure

        receipts = [receipt_by_id[cell["cell_sha256"]] for cell in cells]

    ready = sum(item["status"] == "READY" for item in receipts)
    reasons = Counter(item.get("reason_code") for item in receipts if item["status"] != "READY")
    status = "READY_NO_SCORE" if ready == len(cells) and not group_failure_count else "BLOCKED_NO_SCORE"
    archive_identity = {root: {"adapter_dataset_fingerprint": data[root]["metadata"].dataset_fingerprint,
        "archive_tree_sha256": data[root]["metadata"].lineage.archive_sha256,
        "event_count": data[root]["event_count"]} for root in data}
    result = {"schema_version": NO_SCORE_SCHEMA, "mode": "PROTECTED_PREFLIGHT_NO_SCORE",
        "status": status, "manifest_sha256": verified.sha256,
        "dataset_manifest_sha256": manifest["source_dataset_manifest_sha256"],
        "archive_identity": archive_identity,
        "feature_version": manifest["feature_specification"]["schema_version"],
        "feature_registry_sha256": feature_registry_sha,
        "feature_order_sha256": _canonical_sha(manifest["feature_specification"]["features"]),
        "feature_width": 24, "target_version": manifest["target_specification"]["version"],
        "target_spec_sha256": target_spec_sha,
        "target_structural_fingerprint": target_fp,
        "feature_invalid_reason_counts": dict(sorted(feature_invalid.items())),
        "target_invalid_structural_reason_counts": dict(sorted(target_invalid.items())),
        "es_nq_synchronization": dict(alignment),
        "walk_forward_windows": sorted(windows),
        "walk_forward_target_boundary_exclusions": boundary_exclusion_totals,
        "walk_forward_purge_exclusions": purge_exclusion_totals,
        "matrix": {"derived_cell_count": len(cells),
            "unique_cell_count": len({cell["cell_sha256"] for cell in cells}),
            "duplicate_cell_count": len(cells) - len({cell["cell_sha256"] for cell in cells}),
            "ready_cell_count": ready, "not_ready_cell_count": len(cells) - ready,
            "reason_counts": dict(sorted(reasons.items(), key=lambda item: str(item[0]))),
            "per_cell_receipt_count": len(receipts)},
        "a2_structural_contract": {"input_shape": [8,24],
            "parameter_count": expected_parameter_count(24), "inference_performed": False},
        "protected_inference_count": 0, "protected_prediction_count": 0,
        "protected_probability_count": 0, "protected_metric_count": 0,
        "protected_pnl_count": 0, "protected_trade_or_signal_count": 0,
        "protected_model_scores": 0, "protected_result_score_artifacts": 0,
        "no_score_boundary": {"active_during_preflight": True,
            "blocked_scoring_operations": len(blocked_operations)},
        "trading_authority": "NONE", "cell_readiness_receipts": receipts}
    _assert_score_free_payload(result)
    if blocked_operations:
        raise ValueError("PROTECTED_PREFLIGHT_SCORING_OPERATION_BLOCKED")
    zero_fields = ("protected_inference_count", "protected_prediction_count",
        "protected_probability_count", "protected_metric_count", "protected_pnl_count",
        "protected_trade_or_signal_count", "protected_model_scores",
        "protected_result_score_artifacts")
    if any(result[field] != 0 for field in zero_fields):
        raise ValueError("PROTECTED_PREFLIGHT_NONZERO_SCORE_COUNTER")
    raw = json.dumps(result, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    result["result_sha256"] = _sha(raw)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + ".tmp")
    if os.path.lexists(temp):
        raise ValueError("PREFLIGHT_TEMP_OUTPUT_ALREADY_EXISTS")
    try:
        with temp.open("xb") as handle:
            handle.write(json.dumps(result, sort_keys=True, indent=2,
                ensure_ascii=False, allow_nan=False).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(temp, destination)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return result
