# BOT 2.0 Phase 5C Technical Inventory (Factual Only)

**Status:** inventory snapshot; not a scientific protocol, not adopted, non-executable.  
**Branch:** `bot2-phase5c-clean-slate-protocol`  
**Inventory HEAD:** `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`  
**Parent:** `f867bf4ee42a852b9a8cbea3901171811cd85cdc`  
**Worktree:** clean at inventory time.

This document records technical identities needed to describe a future evaluation object. It deliberately does not specify evaluation populations, splits, metrics, purges, embargoes, thresholds, scoring, or scientific authority. No protected outcomes or protected result artifacts were opened for this inventory. This file does not authorize model evaluation, inference, trading, or implementation.

## Declared experiment object

- Manifest: `config/bot2_phase5c_experiment_manifest_v3.json`; SHA-256 `FB12989A0E4062EA63B0A335D62B718BA02AD3082C42E63372CABC2F035A1FA5`.
- Lock: `config/bot2_phase5c_v3_manifest.lock.json`; SHA-256 `2D20F38EE53E810E921313E572C1AECC915D0C4C1601E333905A5C58B17714A7`.
- Declared experiment ID: `bot2-phase5c-future-state-esnq-v3`.
- Declared manifest schema: `bot2-phase5c-experiment-manifest-v3`.
- Declared canonical manifest hash: `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
- Source dataset-manifest SHA-256: `e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67`.
- `source_dataset.dataset_id` is null in the declared object; no dataset ID is inferred here.
- Instruments: ES and NQ.
- Contract symbols listed: ES — ESM5, ESU5, ESZ5, ESH6, ESM6, ESU6; NQ — NQM5, NQU5, NQZ5, NQH6, NQM6, NQU6.
- Declared walk-forward identifiers: WF1–WF4. The inventory records the identifiers only; it does not infer or authorize dates, split semantics, or eligibility.
- Target horizons: 5, 15, and 30 minutes.
- Feature identity: `bot2-feature-row-v3`, registry/schema version 3, 24 declared features, sequence length 8.
- Target identity: `bot2-future-market-state-v3`; direction classes DOWN/FLAT/UP; volatility classes LOW/NORMAL/HIGH; structure classes RANGE/TRANSITION/TREND.
- Declared ablation families: ALL, MINUS_CROSS_MARKET, MINUS_VWAP, MINUS_VOLUME, MINUS_VOLATILITY, MINUS_SESSION_TIME.

## Model implementation identities

These are code-level descriptions only, not claims about model quality or valid evaluation methodology.

- A0 implementations enumerated by the runner: `A0_PREVIOUS_LABEL_PERSISTENCE`, `A0_TRAIN_MAJORITY`, `A0_TRAIN_TRANSITION_MATRIX`.
- A1: `A1_NUMPY_MULTIHEAD_MLP`, implemented in `bot2/neural/model.py`; declared flattened input width 192 (= 8 × 24), hidden width 8, shared tanh representation, and three 3-class heads.
- A2: `A2_LEARNED_CAUSAL_TCN`, implemented in `bot2/phase5c_v3/model.py`; architecture identifier `bot2-phase5c-a2-causal-tcn-v3`; declared input shape `[8,24]`; channels 24→32→32→16; kernel size 3; dilations 1/2/4; shared dense width 16; three heads 16→3.
- The implementation contains static shape/parameter-count assertions for `[8,24]` and 7,417 parameters. No model was instantiated or executed as part of this inventory; the recorded parameter identity is code-declared, not independently recomputed by an execution.
- No architecture, target, hyperparameter, or training changes were made.

## Relevant schema surfaces

- Raw-event schema: `bot2/data_foundation/schemas/raw-market-event-v2.json`, `$id` `bot2-raw-market-event-v2`. Required fields include `schema_version`, `instrument`, `venue`, `event_type`, `event_timestamp`, `receive_timestamp`, `receive_timestamp_available`, `timestamp_source`, `price`, and `volume`. Other declared fields include `exchange_time`, `receipt_time`, `sequence`, `event_id`, `session_id`, and `contract_id`.
- Dataset-manifest schema: `bot2/data_foundation/schemas/dataset-manifest-v2.json`, `$id` `bot2-dataset-manifest-v2`. Required fields include `manifest_schema_version`, `dataset_id`, `source`, `instruments`, `start_exchange_time`, `end_exchange_time`, `schema_version`, `validation_status`, `source_sha256`, `normalized_sha256`, `code_commit`, `configuration_sha256`, `event_count`, `quality_report`, `timestamp_provenance`, and `trading_authority`.
- Feature schema: `bot2/features_labels/schemas/feature-row-v3.json`; target schema: `bot2/features_labels/schemas/future-target-row-v3.json`.

## Source-file identity hashes

SHA-256 values below identify the files as present at this snapshot; they do not establish scientific authority.

| File | SHA-256 |
|---|---|
| `bot2/features_labels/features.py` | `5BB93CDC5D611FA9C65C24FEB56ED08F4AC6B29E15FFCD8969DEC0B7803A5790` |
| `bot2/features_labels/contracts.py` | `48F47A754C8F9D83AE6E42A287384B41E181644C32D5262407F4B1FBCC269711` |
| `bot2/features_labels/targets_v3.py` | `19ED3A1E48B8D7D9A1F2B561F3D334804684EA5D7336D80C0AF88A195E6BFDB8` |
| `bot2/features_labels/schemas/feature-row-v3.json` | `549D600B9332CEE303D3DD59DF127A930DED62BF123D9B77F782D6CB28D60E0B` |
| `bot2/features_labels/schemas/future-target-row-v3.json` | `2C6479FA9E7A59D067FEB336931CED69B29D36DA839EC71E25BF81A2ED0F9AEC` |
| `bot2/data_foundation/schemas/raw-market-event-v2.json` | `9FEA6747C5B26E412F98E101331AE5A42C707993ACB0E146189F95DE342CDD6C` |
| `bot2/data_foundation/schemas/dataset-manifest-v2.json` | `5267F0680D793256B951F0CAAB02224ECBB520C8132C527B8BD5FFBF5099E0FD` |
| `bot2/phase5c_v3/model.py` | `669213ABD48E37DF0B9F1592AD3DED405736667F95CF9DD05527BACA41E39F2C` |
| `bot2/phase5c_v3/experiment_runner.py` | `13DF4E89993AB795A45C46950C1BA14BB1564852661032CC378EF8E1631F374F` |
| `bot2/phase5c_v3/experiment_matrix.py` | `41CE5177DD82C19AA5113513092E6FA48F1D85BD7346015AF505D8F0B888E516` |
| `bot2/neural/model.py` | `D3849997001AC0008BB8F9153D773A18635EBF6E8D889609913DE9D4A0AEEF` |

## Technical-definition addendum (read-only source inspection)

This addendum records the current v3 feature/target code and registry as technical identity, not as a recommendation about whether the definitions are scientifically ideal. It was added after the P1–P5 initial drafts and is not retroactively attributed to them.

- Feature registry: `config/bot2_feature_registry_v3.json`; cadence is exactly 60 seconds, temporal semantics are `ELAPSED_TIME_STRICT_CADENCE`, and sequence length is 8.
- The 24 feature names are: `price`; `log_return_1m`, `log_return_3m`, `log_return_5m`; `rolling_price_range_3m`, `rolling_price_range_5m`; `realized_volatility_3m`, `realized_volatility_5m`; `session_open_distance`, `session_high_distance`, `session_low_distance`, `cumulative_volume_session`; `relative_volume_3m`, `volume_acceleration_1m`; `session_vwap`, `price_to_session_vwap`; `seconds_since_session_open`, `session_phase`, `time_sin`, `time_cos`; `cross_market_log_return_1m`, `cross_market_relative_return_1m`, `cross_market_rolling_correlation_5m`, `cross_market_divergence_1m`.
- Registry semantics: returns use exact T−N through T one-minute observations; price range uses N+1 consecutive closes; realized volatility uses exactly N one-minute returns; relative volume compares current volume against exact T−3 through T−1; cross-market features use same-session exact timestamps; five-minute rolling correlation needs five complete synchronized return pairs. Missing required windows remain null with reason codes; no fill/interpolation is specified. `session_phase` is encoded OPENING=0, EARLY=1, LATE=2.
- Session aggregates (open/high/low distances, cumulative observed volume, and session VWAP) use all observed source bars from the explicit session open through the current anchor. Therefore their raw support reaches back to the session open, rather than only the five-minute rolling window. No synthetic zero-volume bars are inserted.
- The current registry declares per-feature mean and population-standard-deviation normalization fitted on TRAIN eligible rows, then frozen for validation/calibration/WF test/OOS. This inventory does not review the provenance or adequacy of any historical experiment applying that declaration.
- Target identity: `bot2-future-market-state-v3`, schema `bot2-future-target-row-v3`, horizons 5/15/30 minutes. Direction uses displacement from close T to close T+H, with FLAT when absolute displacement is less than one root tick; current tick sizes are ES=0.25 and NQ=0.25 points.
- Volatility target is RMS of exactly H future one-minute log returns divided by RMS of the prior 30 consecutive one-minute returns ending at T; LOW below 0.8, NORMAL from 0.8 through 1.2 inclusive, HIGH above 1.2.
- Structure target uses `abs(log(close[T+H]/close[T])) / sum(abs(future one-minute log returns))`; TREND requires efficiency ≥0.60 and displacement ≥4 ticks; RANGE requires efficiency ≤0.25; otherwise TRANSITION.
- Future target window uses closes T+1 through T+H, exactly one minute apart, same session and exact listed contract, with no fill. It also needs a trailing 30-return volatility reference ending at T; the target code records label-information start and label-end time. Thus target-information support differs by head and cannot be represented by horizon alone.
- Current feature code's cross-market join is a same-session exact exchange-time match, not a general nearest/as-of join; the inspected feature computation does not establish when a counterpart event was actually received. Exchange-time exactness is a code fact, not proof of point-in-time receipt availability. Receipt-time provenance/latency remains an evaluation prerequisite.
- The target code expresses label endpoints in exchange time and uses exactly 60-second event-time spacing; it does not itself prove when the final event/label was received or that later source corrections were finalized. Actual label maturity for a real-time information set remains an evaluation prerequisite.
- Source dataset identity remains incomplete: the experiment manifest's source dataset ID is null, and this inspection did not locate or access protected data to repair that missing identifier. No split dates or scientific evaluation semantics are inferred from code in this addendum.

### Addendum source hashes

| File | SHA-256 |
|---|---|
| `config/bot2_feature_registry_v3.json` | `60631310AED0F558DC99CA8C920A4832975EFE55786784B731403ABBB73B86A2` |
| `bot2/features_labels/features.py` | `5BB93CDC5D611FA9C65C24FEB56ED08F4AC6B29E15FFCD8969DEC0B7803A5790` |
| `bot2/features_labels/contracts.py` | `48F47A754C8F9D83AE6E42A287384B41E181644C32D5262407F4B1FBCC269711` |
| `bot2/features_labels/targets_v3.py` | `19ED3A1E48B8D7D9A1F2B561F3D334804684EA5D7336D80C0AF88A195E6BFDB8` |

## Scope boundary

No historical protocol lineage was consulted as scientific authority. Historical materials remain preserved and nonauthoritative. No protected archive run, inference, prediction, probability, metric, P&L, or score was accessed or generated. No tests, training, model execution, data scoring, or order simulation was performed. The next clean-slate work is independent methodology drafting and public-methodology sourcing only.
