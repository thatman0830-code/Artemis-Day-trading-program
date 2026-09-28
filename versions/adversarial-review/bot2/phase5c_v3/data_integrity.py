"""Data-derived Phase 5C partition identities and fit-time boundary enforcement."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

import numpy as np

from .manifest import VerifiedManifest, canonical_bytes, canonical_hash, is_verified_manifest

_SPLIT_TOKEN = object()
_HEADS = ("direction", "volatility", "structure")


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_OBSERVATION_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("OBSERVATION_TIMESTAMP_MUST_BE_UTC")
    return parsed.astimezone(timezone.utc)


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class MarketObservation:
    """One actual feature/target row. row_id is deliberately advisory and ignored."""
    market: str
    contract: str
    session_id: str
    exchange_timestamp_utc: str
    session_open_utc: str
    feature_names: tuple[str, ...]
    features: tuple[float, ...]
    targets: Mapping[str, int]
    label_end_utc: str
    dataset_manifest_sha256: str
    feature_version: str
    target_version: str
    row_id: str | None = None

    @property
    def observation_id(self) -> str:
        """Canonical key derived from observation fields, never from row_id."""
        return _sha({"market": self.market, "contract": self.contract,
                     "session_id": self.session_id,
                     "exchange_timestamp_utc": _utc(self.exchange_timestamp_utc).isoformat()})

    @property
    def content_digest(self) -> str:
        return _sha({"observation_id": self.observation_id,
                     "session_open_utc": _utc(self.session_open_utc).isoformat(),
                     "feature_names": list(self.feature_names), "features": list(self.features),
                     "targets": dict(sorted(self.targets.items())),
                     "label_end_utc": _utc(self.label_end_utc).isoformat(),
                     "dataset_manifest_sha256": self.dataset_manifest_sha256,
                     "feature_version": self.feature_version, "target_version": self.target_version})


@dataclass(frozen=True, slots=True)
class AuthorizedSplit:
    """Factory-created split; model.fit accepts this, not caller-built arrays."""
    market: str
    horizon_minutes: int
    dataset_manifest_sha256: str
    partition_fingerprints: Mapping[str, str]
    canonical_rows: Mapping[str, tuple[MarketObservation, ...]]
    prepared_fingerprints: Mapping[str, str]
    preprocessing_sha256: str
    preprocessing_state: Mapping[str, object]
    train: object
    validation: object
    ablation_contract: Mapping[str, object]
    walk_forward_window_id: str | None
    _token: object = field(repr=False, compare=False)

    def valid(self) -> bool:
        return self._token is _SPLIT_TOKEN


def partition_fingerprint(rows: Sequence[MarketObservation], *, partition: str,
                          horizon_minutes: int) -> str:
    return _sha({"procedure": "bot2-canonical-observation-and-target-fingerprint-v1",
                 "partition": partition, "horizon_minutes": horizon_minutes,
                 "rows_in_semantic_order": [
                     {"observation_id": row.observation_id,
                      "content_digest": row.content_digest,
                      "target_identity": _sha({"horizon_minutes": horizon_minutes,
                                                "targets": dict(sorted(row.targets.items())),
                                                "label_end_utc": _utc(row.label_end_utc).isoformat()})}
                     for row in rows]})


def feature_partition_fingerprint(rows: Sequence[MarketObservation], *, partition: str) -> str:
    """Preprocessor identity over the ordered observed feature rows (targets excluded)."""
    return _sha({"procedure": "bot2-training-feature-observation-fingerprint-v1",
                 "partition": partition,
                 "rows_in_semantic_order": [
                     {"observation_id": row.observation_id,
                      "feature_names": list(row.feature_names),
                      "features": list(row.features),
                      "dataset_manifest_sha256": row.dataset_manifest_sha256,
                      "feature_version": row.feature_version}
                     for row in rows]})


def _prepared_fingerprint(data: object) -> str:
    return _sha({"x": np.asarray(data.x).tolist(),
                 "targets": {name: np.asarray(values).tolist()
                             for name, values in sorted(data.targets.items())},
                 "sequence_keys": data.sequence_keys,
                 "sequence_label_intervals": data.sequence_label_intervals,
                 "partition": data.partition, "market": data.market,
                 "horizon_minutes": data.horizon_minutes,
                 "dataset_manifest_sha256": data.dataset_manifest_sha256,
                 "feature_version": data.feature_version,
                 "target_version": data.target_version,
                 "preprocessing_sha256": data.preprocessing_sha256,
                 "ablation_id": data.ablation_id,
                 "ablation_sha256": data.ablation_sha256,
                 "feature_mask": list(data.feature_mask)})


def build_authorized_split(verified_manifest: VerifiedManifest, *, market: str,
                           horizon_minutes: int,
                           partition_rows: Mapping[str, Sequence[MarketObservation]],
                           preprocessor: object,
                           ablation_id: str = "ALL",
                           walk_forward_window_id: str | None = None) -> AuthorizedSplit:
    """Derive all row identities and enforce frozen splits, purge, embargo and cadence."""
    if not is_verified_manifest(verified_manifest) or not verified_manifest.external_anchor_content_verified:
        raise ValueError("EXTERNALLY_ANCHORED_MANIFEST_REQUIRED")
    if market not in {"ES", "NQ"}:
        raise ValueError("MARKET_NOT_IN_MANIFEST")
    manifest = verified_manifest.data
    if horizon_minutes not in manifest["target_specification"]["horizons_minutes"]:
        raise ValueError("TARGET_WINDOW_NOT_IN_MANIFEST")
    from .model import TrainingOnlyStandardizer
    from .experiment_controls import create_ablation_contract, apply_ablation_mask
    if not isinstance(preprocessor, TrainingOnlyStandardizer):
        raise ValueError("PREPROCESSING_ARTIFACT_MISSING")
    try:
        preprocessing_sha256 = preprocessor.sha256
        preprocessing_state = preprocessor.state()
    except (AttributeError, ValueError) as exc:
        raise ValueError("PREPROCESSING_ARTIFACT_MISSING") from exc
    if (preprocessor.manifest_sha256_ != verified_manifest.sha256
            or preprocessor.dataset_sha256_ != manifest["source_dataset_manifest_sha256"]
            or preprocessor.feature_version_ != manifest["feature_specification"]["schema_version"]
            or preprocessor.market_ != market
            or preprocessor._feature_order_ != tuple(manifest["feature_specification"]["features"])):
        raise ValueError("PREPROCESSING_PROVENANCE_MISMATCH")
    ordered_names = [name for name in ("TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST")
                     if name in partition_rows]
    if "TRAIN" not in partition_rows or "VALIDATION_AND_CALIBRATION" not in partition_rows:
        raise ValueError("AUTHORIZED_TRAIN_VALIDATION_SPLIT_REQUIRED")
    if set(partition_rows) - set(("TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST")):
        raise ValueError("PARTITION_TAG_NOT_IN_MANIFEST")
    features = tuple(manifest["feature_specification"]["features"])
    dataset_hash = manifest["source_dataset_manifest_sha256"]
    feature_version = manifest["feature_specification"]["schema_version"]
    ablation_contract = create_ablation_contract(verified_manifest, ablation_id)
    if (ablation_contract["preprocessing_version"] != preprocessing_state.get("version")
            or ablation_contract["canonical_feature_order"] != list(features)):
        raise ValueError("ABLATION_PREPROCESSING_CONTRACT_MISMATCH")
    target_version = manifest["target_specification"]["version"]
    contracts = set(manifest["source_dataset"]["contracts"][market])
    windows = _authorized_partition_windows(manifest, walk_forward_window_id)
    cadence = int(manifest["feature_specification"]["sequence_cadence_seconds"])
    sequence_length = int(manifest["feature_specification"]["sequence_length"])
    purge = timedelta(minutes=int(manifest["purge_embargo"]["purge_minutes"]))
    embargo = timedelta(minutes=int(manifest["purge_embargo"]["embargo_minutes"]))
    all_ids: dict[str, str] = {}
    canonical_rows: dict[str, list[MarketObservation]] = {}
    fingerprints: dict[str, str] = {}
    for partition in ordered_names:
        rows = list(partition_rows[partition])
        if not rows:
            raise ValueError("EMPTY_AUTHORIZED_PARTITION")
        if rows != sorted(rows, key=lambda row: (_utc(row.exchange_timestamp_utc), row.contract)):
            raise ValueError("OBSERVATIONS_NOT_IN_CANONICAL_ORDER")
        start, end = windows[partition]
        for row in rows:
            ts, session_open, label_end = (_utc(row.exchange_timestamp_utc),
                                           _utc(row.session_open_utc), _utc(row.label_end_utc))
            identity = row.observation_id
            if identity in all_ids:
                raise ValueError("DUPLICATE_OBSERVATION_CROSSES_PARTITION")
            all_ids[identity] = partition
            if row.market != market or row.contract not in contracts:
                raise ValueError("INSTRUMENT_OR_CONTRACT_NOT_IN_MANIFEST")
            if row.dataset_manifest_sha256 != dataset_hash:
                raise ValueError("DATASET_MANIFEST_BINDING_MISMATCH")
            if row.feature_version != feature_version or row.target_version != target_version:
                raise ValueError("FEATURE_OR_TARGET_VERSION_MISMATCH")
            if row.feature_names != features or len(row.features) != len(features):
                raise ValueError("FEATURE_ORDER_OR_WIDTH_MISMATCH")
            values = np.asarray(row.features, dtype=np.float64)
            if not np.isfinite(values).all():
                raise ValueError("NONFINITE_FEATURE_VALUE")
            if set(row.targets) != set(_HEADS) or any(int(row.targets[h]) not in (0, 1, 2) for h in _HEADS):
                raise ValueError("INVALID_TARGET_OR_TARGET_VERSION_MISMATCH")
            if label_end != ts + timedelta(minutes=horizon_minutes):
                raise ValueError("LABEL_INFORMATION_INTERVAL_MISMATCH")
            if session_open > ts:
                raise ValueError("SESSION_OPEN_AFTER_OBSERVATION")
            if not start <= ts.date().isoformat() <= end:
                raise ValueError("PARTITION_TIMESTAMP_OUTSIDE_MANIFEST_WINDOW")
        canonical_rows[partition] = rows
        fingerprints[partition] = partition_fingerprint(rows, partition=partition,
                                                        horizon_minutes=horizon_minutes)
    # Derive eligible terminal observations ourselves. Purged/embargoed rows may
    # remain as historical context but cannot become training or validation examples.
    terminal_allowed: dict[str, set[str]] = {name: {row.observation_id for row in rows}
                                             for name, rows in canonical_rows.items()}
    for previous, following in zip(ordered_names, ordered_names[1:]):
        boundary = _utc(canonical_rows[following][0].exchange_timestamp_utc)
        cutoff = boundary - purge
        terminal_allowed[previous] = {row.observation_id for row in canonical_rows[previous]
                                       if _utc(row.label_end_utc) < cutoff}
    if preprocessing_state.get("training_feature_fingerprint") != feature_partition_fingerprint(
            canonical_rows["TRAIN"], partition="TRAIN"):
        raise ValueError("PREPROCESSING_TRAINING_PARTITION_MISMATCH")
    # Build contiguous examples from the actual rows. The metadata keys and
    # fingerprints are always computed here; advisory caller IDs are never used.
    from .model import PartitionData
    prepared: dict[str, object] = {}
    prepared_fingerprints: dict[str, str] = {}
    for partition in ("TRAIN", "VALIDATION_AND_CALIBRATION"):
        rows = canonical_rows[partition]
        examples: list[list[MarketObservation]] = []
        embargo_start_by_session = {}
        if partition == "VALIDATION_AND_CALIBRATION":
            for row in rows:
                embargo_start_by_session[(row.contract, row.session_id)] = _utc(row.session_open_utc) + embargo
        for index in range(sequence_length - 1, len(rows)):
            sample = rows[index - sequence_length + 1:index + 1]
            if any(left.contract != right.contract or left.session_id != right.session_id
                   or _utc(right.exchange_timestamp_utc) - _utc(left.exchange_timestamp_utc) != timedelta(seconds=cadence)
                   for left, right in zip(sample, sample[1:])):
                continue
            terminal = sample[-1]
            if terminal.observation_id not in terminal_allowed[partition]:
                continue
            if (partition == "VALIDATION_AND_CALIBRATION"
                    and _utc(terminal.exchange_timestamp_utc)
                    < embargo_start_by_session[(terminal.contract, terminal.session_id)]):
                continue
            examples.append(sample)
        if not examples:
            raise ValueError("NO_VALID_CONTIGUOUS_SEQUENCES")
        raw_x = np.asarray([[row.features for row in sample] for sample in examples], dtype=np.float64)
        standardized_x = preprocessor.transform(raw_x)
        x = apply_ablation_mask(standardized_x, contract=ablation_contract,
            verified_manifest=verified_manifest, feature_order=features)
        y = {head: np.asarray([sample[-1].targets[head] for sample in examples], dtype=np.int64)
             for head in _HEADS}
        keys = tuple(tuple((row.contract, row.session_id, _utc(row.exchange_timestamp_utc).isoformat())
                           for row in sample) for sample in examples)
        intervals = tuple((_utc(sample[-1].exchange_timestamp_utc).isoformat(),
                           _utc(sample[-1].label_end_utc).isoformat()) for sample in examples)
        x.setflags(write=False)
        for values in y.values():
            values.setflags(write=False)
        prepared[partition] = PartitionData(x, y, partition, keys, feature_version, target_version,
            market, horizon_minutes, dataset_hash, preprocessing_sha256,
            fingerprints[partition], intervals, True, ablation_id,
            ablation_contract["ablation_sha256"], tuple(ablation_contract["feature_mask"]))
        prepared_fingerprints[partition] = _prepared_fingerprint(prepared[partition])
    return AuthorizedSplit(market, horizon_minutes, dataset_hash, fingerprints,
        {name: tuple(rows) for name, rows in canonical_rows.items()}, prepared_fingerprints,
        preprocessing_sha256, preprocessing_state,
        prepared["TRAIN"], prepared["VALIDATION_AND_CALIBRATION"],
        ablation_contract, walk_forward_window_id, _SPLIT_TOKEN)


def _authorized_partition_windows(manifest: Mapping, window_id: str | None) -> Mapping:
    """Return only a globally frozen split or an exact manifest WF window."""
    if window_id is None:
        return manifest["chronological_partitions_inclusive"]
    matches = [window for window in manifest.get("walk_forward_windows_inclusive", [])
               if window.get("id") == window_id]
    if len(matches) != 1:
        raise ValueError("WALK_FORWARD_WINDOW_NOT_IN_MANIFEST")
    selected = matches[0]
    return {"TRAIN": selected["train"],
        "VALIDATION_AND_CALIBRATION": selected["validation"],
        "OOS_TEST": selected["test"]}


def validate_authorized_split(split: AuthorizedSplit, verified_manifest: VerifiedManifest) -> None:
    """Recompute identities/content and boundary policy at the model fit boundary."""
    if not isinstance(split, AuthorizedSplit) or not split.valid():
        raise ValueError("UNAUTHORIZED_SPLIT_OBJECT")
    if not is_verified_manifest(verified_manifest) or not verified_manifest.external_anchor_content_verified:
        raise ValueError("EXTERNALLY_ANCHORED_MANIFEST_REQUIRED")
    manifest = verified_manifest.data
    from .experiment_controls import create_ablation_contract, apply_ablation_mask, verify_ablation_contract
    verify_ablation_contract(split.ablation_contract, verified_manifest)
    expected_contract = create_ablation_contract(verified_manifest,
        str(split.ablation_contract.get("ablation_id", "")))
    if dict(split.ablation_contract) != expected_contract:
        raise ValueError("AUTHORIZED_SPLIT_ABLATION_CONTRACT_MISMATCH")
    if split.dataset_manifest_sha256 != manifest["source_dataset_manifest_sha256"]:
        raise ValueError("DATASET_MANIFEST_BINDING_MISMATCH")
    preprocessing = dict(split.preprocessing_state)
    if (canonical_hash(preprocessing) != split.preprocessing_sha256
            or preprocessing.get("manifest_sha256") != verified_manifest.sha256
            or preprocessing.get("dataset_manifest_sha256") != split.dataset_manifest_sha256
            or preprocessing.get("feature_version") != manifest["feature_specification"]["schema_version"]
            or preprocessing.get("market") != split.market
            or preprocessing.get("feature_order") != manifest["feature_specification"]["features"]
            or preprocessing.get("fit_partition") != "TRAIN"):
        raise ValueError("PREPROCESSING_ARTIFACT_MISMATCH")
    windows = _authorized_partition_windows(manifest, split.walk_forward_window_id)
    for partition, rows in split.canonical_rows.items():
        observed = partition_fingerprint(rows, partition=partition,
                                         horizon_minutes=split.horizon_minutes)
        if observed != split.partition_fingerprints.get(partition):
            raise ValueError("PARTITION_FINGERPRINT_MISMATCH")
    for partition, rows in split.canonical_rows.items():
        if partition not in windows:
            raise ValueError("PARTITION_TAG_NOT_IN_MANIFEST")
        start, end = windows[partition]
        if any(not start <= _utc(row.exchange_timestamp_utc).date().isoformat() <= end
               for row in rows):
            raise ValueError("PARTITION_TIMESTAMP_OUTSIDE_MANIFEST_WINDOW")
    ordered = [name for name in ("TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST")
               if name in split.canonical_rows]
    purge = timedelta(minutes=int(manifest["purge_embargo"]["purge_minutes"]))
    prepared_data = {"TRAIN": split.train,
                     "VALIDATION_AND_CALIBRATION": split.validation}
    for previous, following in zip(ordered, ordered[1:]):
        boundary = _utc(split.canonical_rows[following][0].exchange_timestamp_utc)
        data = prepared_data.get(previous)
        if data is not None and any(_utc(end) >= boundary - purge
                                    for _, end in data.sequence_label_intervals):
            raise ValueError("LABEL_INTERVAL_VIOLATES_PURGE")
    embargo = timedelta(minutes=int(manifest["purge_embargo"]["embargo_minutes"]))
    for partition in ("VALIDATION_AND_CALIBRATION", "OOS_TEST"):
        data = prepared_data.get(partition)
        if data is None:
            continue
        raw_by_key = {(row.contract, row.session_id,
                       _utc(row.exchange_timestamp_utc).isoformat()): row
                      for row in split.canonical_rows[partition]}
        for sequence, (start, _) in zip(data.sequence_keys, data.sequence_label_intervals):
            terminal = sequence[-1]
            row = raw_by_key.get(terminal)
            if row is None or _utc(start) < _utc(row.session_open_utc) + embargo:
                raise ValueError("OBSERVATION_INSIDE_EMBARGO")
    for partition, data in (("TRAIN", split.train),
                            ("VALIDATION_AND_CALIBRATION", split.validation)):
        if not data.derived_from_observations:
            raise ValueError("PARTITION_NOT_DATA_DERIVED")
        if (data.partition != partition or data.market != split.market
                or data.horizon_minutes != split.horizon_minutes
                or data.dataset_manifest_sha256 != split.dataset_manifest_sha256
                or data.preprocessing_sha256 != split.preprocessing_sha256):
            raise ValueError("PREPARED_PARTITION_METADATA_MISMATCH")
        if (data.ablation_id != split.ablation_contract["ablation_id"]
                or data.ablation_sha256 != split.ablation_contract["ablation_sha256"]
                or data.feature_mask != tuple(split.ablation_contract["feature_mask"])):
            raise ValueError("PREPARED_PARTITION_ABLATION_MISMATCH")
        actual = _prepared_fingerprint(data)
        if actual != split.prepared_fingerprints.get(partition):
            raise ValueError("PREPARED_PARTITION_CONTENT_MISMATCH")
        canonical_ids = {row.observation_id for row in split.canonical_rows[partition]}
        for sequence in data.sequence_keys:
            for contract, session, timestamp in sequence:
                row = next((item for item in split.canonical_rows[partition]
                            if item.contract == contract and item.session_id == session
                            and _utc(item.exchange_timestamp_utc).isoformat() == timestamp), None)
                if row is None or row.observation_id not in canonical_ids:
                    raise ValueError("SEQUENCE_NOT_BOUND_TO_CANONICAL_OBSERVATIONS")
        from .model import validate_sequence_identities
        validate_sequence_identities(data, sequence_length=int(
            manifest["feature_specification"]["sequence_length"]), cadence_seconds=int(
            manifest["feature_specification"]["sequence_cadence_seconds"]))
        rows = split.canonical_rows[partition]
        cadence = timedelta(seconds=int(manifest["feature_specification"]["sequence_cadence_seconds"]))
        length = int(manifest["feature_specification"]["sequence_length"])
        allowed = {row.observation_id for row in rows}
        following = ("VALIDATION_AND_CALIBRATION" if partition == "TRAIN" else "OOS_TEST")
        if following in split.canonical_rows:
            boundary = _utc(split.canonical_rows[following][0].exchange_timestamp_utc)
            allowed = {row.observation_id for row in rows
                       if _utc(row.label_end_utc) < boundary - purge}
        raw_sequences, raw_targets, raw_intervals = [], {head: [] for head in _HEADS}, []
        embargo_by_session = {}
        if partition == "VALIDATION_AND_CALIBRATION":
            for row in rows:
                embargo_by_session[(row.contract, row.session_id)] = _utc(row.session_open_utc) + embargo
        for end_index in range(length - 1, len(rows)):
            sample = rows[end_index - length + 1:end_index + 1]
            if any(left.contract != right.contract or left.session_id != right.session_id
                   or _utc(right.exchange_timestamp_utc) - _utc(left.exchange_timestamp_utc) != cadence
                   for left, right in zip(sample, sample[1:])):
                continue
            terminal = sample[-1]
            if terminal.observation_id not in allowed:
                continue
            ts = _utc(terminal.exchange_timestamp_utc)
            if (partition == "VALIDATION_AND_CALIBRATION"
                    and ts < embargo_by_session[(terminal.contract, terminal.session_id)]):
                continue
            raw_sequences.append(sample)
            for head in _HEADS:
                raw_targets[head].append(terminal.targets[head])
            raw_intervals.append((ts.isoformat(), _utc(terminal.label_end_utc).isoformat()))
        if not raw_sequences:
            raise ValueError("NO_VALID_CONTIGUOUS_SEQUENCES")
        expected_keys = tuple(tuple((row.contract, row.session_id,
                                     _utc(row.exchange_timestamp_utc).isoformat())
                                    for row in sample) for sample in raw_sequences)
        if data.sequence_keys != expected_keys or data.sequence_label_intervals != tuple(raw_intervals):
            raise ValueError("SEQUENCE_NOT_BOUND_TO_CANONICAL_OBSERVATIONS")
        means = np.asarray(preprocessing.get("mean"), dtype=np.float64)
        scales = np.asarray(preprocessing.get("scale"), dtype=np.float64)
        feature_count = len(manifest["feature_specification"]["features"])
        if (means.shape != (feature_count,) or scales.shape != (feature_count,)
                or not np.isfinite(means).all() or not np.isfinite(scales).all()
                or np.any(scales <= 0)):
            raise ValueError("PREPROCESSING_PARAMETER_DIMENSION_OR_VALUE_INVALID")
        expected_x = ((np.asarray([[row.features for row in sample]
                                  for sample in raw_sequences], dtype=np.float64) - means)
                      / scales).astype(np.float32)
        expected_x = apply_ablation_mask(expected_x,
            contract=split.ablation_contract, verified_manifest=verified_manifest,
            feature_order=manifest["feature_specification"]["features"])
        if not np.array_equal(np.asarray(data.x), expected_x):
            raise ValueError("PREPARED_FEATURES_NOT_BOUND_TO_CANONICAL_ROWS")
        for head in _HEADS:
            if not np.array_equal(np.asarray(data.targets[head]), np.asarray(raw_targets[head], dtype=np.int64)):
                raise ValueError("PREPARED_TARGETS_NOT_BOUND_TO_CANONICAL_ROWS")
