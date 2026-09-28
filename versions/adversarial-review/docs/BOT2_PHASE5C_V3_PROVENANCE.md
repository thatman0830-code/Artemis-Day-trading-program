# BOT 2.0 Phase 5C-S — Manifest and Artifact Provenance

## Frozen source identities

- Manifest: `config/bot2_phase5c_experiment_manifest_v3.json`
- Canonical v3 manifest SHA-256: `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`
- External lock: `config/bot2_phase5c_v3_manifest.lock.json`
- Lock file SHA-256: `7cb99e0862aad63d28896ab888f9422e99737f923a0f8ded8b3dc3238dbc4a32`
- Raw archive-tree SHA-256 pinned in lock: `405ff5602600fbe361c7136b85be0b26d46567c1c080dfefab2e506e109a775b`
- Protocol parent: `ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94`
- Protocol anchor: `9a1ecfaf08077252049dd187d44f8641da1186aa`

The prior Phase 5C v2 and v3 manifest files remain unchanged. The lock is canonical JSON and is pinned by a constant in the verifier. Verification checks the lock digest, schema/name/version, canonical manifest digest, raw archive-tree digest, and protocol ancestry. A `VerifiedManifest` cannot be freely constructed and its public accessors return deep copies.

## Artifact lineage

Artifacts use schema `bot2-phase5c-a2-artifact-v4`. Their expected identity is derived from the verified manifest and binds:

`experiment/protocol → manifest → source dataset manifest → feature registry → target specification → architecture/seed/market/horizon → sequence and partition windows → raw archive tree → TRAIN-only preprocessing → model weights → optional calibration/result artifacts`.

Digests are format-checked and compared to the corresponding artifact and manifest fields. Artifact loading revalidates identity, hash, provenance links, and authority fields. Calibration/result outputs remain null before any authorized scoring; there is no result artifact in this Phase 5C-S work. The code commit is required as a full Git SHA in artifact lineage. The runner additionally checks that the frozen protocol anchor is in HEAD ancestry and refuses to run on a dirty tree.

## Atomic persistence

Artifact bytes are written to a unique temporary file in the destination directory, flushed and fsynced, then published with a hard-link operation that fails if the final path already exists. The digest is checked after publication, and the temporary file is cleaned up. Tests cover existing-target no-overwrite and concurrent competing writes. This prevents replacement/race corruption on the supported local filesystem; cross-filesystem/network-share semantics are not claimed.

## Dataset and preprocessing identity

The standardizer accepts only TRAIN rows with canonical identities `(exact_contract, session_id, exchange_timestamp_utc)`, and validates uniqueness, market, manifest contract/date eligibility, row width, and finite numeric values. The persisted scaler state includes its version, training-only partition, feature width, mean/scale, manifest and dataset digests, market, identity-key schema, and unique training-row count. Its canonical SHA-256 is attached to every partition and artifact. Fit rejects duplicated identities, even when duplicate rows have equal values; differing values for the same identity use a distinct reason code.

Each sequence carries its exact contract/session/UTC exchange timestamps and data schema versions, market, horizon, source-dataset digest, and preprocessing digest. Validation enforces manifest time windows, cadence, sequence length, allowed instrument inventory, and partition-disjoint observation identities. Train/evaluation windows are chronological and separated by the frozen purge/embargo rules. Validation/calibration is the only evaluation partition available to checkpoint selection; OOS is not consumed by the model fit/preflight.

## Reproducibility / authority state

Fixed seeds are drawn from the frozen manifest. Data order is deterministic and chronological; training avoids batch shuffling. Tests verify fixed-seed repeatability, causal outputs, future-mutation invariance, and numerical gradients. This establishes software determinism tests, not predictive validity or trading edge.

Current gates remain: `evaluation_permitted=false`, `oos_model_scoring_performed=false`, and `trading_authority=false`. No protected OOS samples, metrics, predictions, or outcomes were opened or calculated. The preflight harness does not score models or affect production/paper execution.
