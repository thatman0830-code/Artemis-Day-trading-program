# BOT 2.0 Phase 3 — Baseline Modeling and Evaluation

Status: complete on `bot2-phase3-baseline-modeling` for review. This is research-plane infrastructure only. No production strategy, risk limit, broker behavior, paper execution authority, or live trading path was changed.

## Objective and protocol

Phase 3 answers whether the versioned Phase 2 representation can demonstrate reproducible out-of-sample information without neural networks. The predefined matrix is recorded in `config/bot2_phase3_experiment_matrix_v1.json` before evaluation: forward-return zero reference, directional majority class, directional logistic regression, future-volatility prior mean, and a small explicit feature-family ablation set. There is no parameter sweep and no test-set feedback loop.

Every finalized record contains experiment ID, dataset ID/hash, feature and label versions, instruments, train/validation/test periods, feature list/families, target, model, hyperparameters, seed, configurable cost assumptions, Git commit, environment, split counts, metrics, calibration bins, and `trading_authority: false`. `bot2/modeling/registry.py` is append-only and rejects duplicate finalized IDs.

## Temporal isolation, purging, and holdout

`chronological_split()` sorts by observation time and creates TRAIN → VALIDATION → OUT-OF-SAMPLE TEST partitions. It never shuffles observations. Rows whose `label_end_time + purge` crosses the validation boundary are removed from training. An optional embargo removes the configured leading interval of the validation partition. `walk_forward_splits()` provides deterministic expanding/rolling windows with configuration-driven sizes. The fixture test produced two walk-forward windows.

Final holdout policy is represented by `UNTOUCHED_FINAL_HOLDOUT_NOT_USED`; `assert_holdout_not_for_tuning()` fails if a feedback loop is declared. This phase does not designate or inspect a production final holdout.

## Preprocessing and leakage controls

`TrainOnlyStandardizer` fits means/scales only on `X_train`; validation and test are transformed using those frozen parameters. The feature cutoff guard rejects a feature whose source maximum time exceeds its observation cutoff. Phase 2’s causal feature tests remain in the suite, including future ES/NQ mutation and past-only VWAP checks.

Feature-family ablation is explicit and bounded through `feature_families.py` for PRICE, VOLATILITY, VOLUME, VWAP, SESSION_TIME, and CROSS_MARKET. The framework does not search families automatically.

## Baselines, metrics, and friction

Implemented baselines are majority class, prior probability/mean, zero-return reference, deterministic logistic regression, and ridge-style regression. A conservative tree ensemble was not added because the environment did not justify another dependency. No neural models were installed or trained.

Classification reports log loss, Brier score, ROC-AUC where defined, precision, recall, confusion matrix, accuracy, and reliability bins. Regression reports MAE, RMSE, correlation, and directional relationship. Probability outputs are called probabilities, never “confidence.”

`CostModel` represents commissions, exchange/clearing fees, spread, and slippage. Unknown broker-specific values remain `null` and are never invented; the runner records configured cost per unit but does not optimize P&L.

## Baseline results

The focused deterministic fixture executed all four initial baselines. These numbers demonstrate the framework, not predictive evidence about live ES/NQ because no claim is made from a synthetic fixture:

| Target/model | OOS result | Interpretation |
|---|---:|---|
| Direction / majority | log loss 0.69315, Brier 0.25, AUC 0.50 | no-skill reference |
| Direction / logistic | log loss 0.69327, Brier 0.25006, AUC 0.556 | indistinguishable from no-skill at this fixture size; not evidence of signal |
| Forward return / zero | MAE 0.50, RMSE 0.7071 | reference only |
| Future volatility / prior mean | MAE 0.50, RMSE 0.50 | reference only |

Calibration bins are emitted for probabilistic models. Logistic OOS bins were approximately mean predicted 0.4974 versus observed frequency 0.50. This is a calibration demonstration, not a claim of model quality.

The shuffled-label sanity test produced logistic OOS log loss 0.69327 and AUC 0.556 on the same controlled fixture—near the 0.69315/0.50 no-skill reference. No positive predictive claim is made; a larger real-data sanity run is required before interpreting small-sample AUC differences.

## Walk-forward results

The deterministic fixture produced 2 configured windows with train/validation/test sizes 12/6/6 and a one-minute purge. Window boundaries remained chronological and no label end time was permitted to bridge the protected boundary.

## Feature families evaluated

The ablation mechanism and predefined matrix cover PRICE, VOLATILITY, VOLUME, VWAP, SESSION_TIME, and CROSS_MARKET. No broad search was run. Order-book/microstructure features remain unavailable under the Phase 1 data contract.

## Test results

- NEW PHASE 3 TESTS PASSED: 9.
- PHASE 2 TESTS PASSED: 9.
- PHASE 1 TESTS PASSED: 8.
- EXISTING PROVIDER-NEUTRAL REGRESSION TESTS PASSED: 5.
- TOTAL TESTS PASSED: 31.
- Failures/skips: none in the relevant suite.

Command:

```text
.venv\\Scripts\\python.exe -m pytest -q bot2/modeling/test_modeling.py bot2/features_labels/test_feature_label_engine.py bot2/data_foundation/test_data_foundation.py backtesting/test_provider_neutral_market_feed_v1.py backtesting/test_provider_neutral_latency_contract_v1.py backtesting/test_provider_neutral_paper_authority_v1.py backtesting/test_provider_neutral_replay_validation_v1.py backtesting/test_provider_neutral_cockpit_v1.py
```

## Limitations and Phase 4 prerequisites

The runner currently accepts generic row dictionaries; an approved production adapter from Phase 2 `FeatureRow`/`LabelRow` datasets, real dataset manifests, and a designated untouched holdout must be wired before interpreting ES/NQ results. The logistic and ridge implementations are deliberately small and should be cross-checked against an independently reviewed implementation. Real exchange calendars, multi-session label boundaries, richer OHLC/order-book contracts, model artifact hashing, and statistical confidence intervals remain open work. Phase 4 prerequisites are a reviewed real-data experiment, completed purged walk-forward coverage, finalized cost assumptions, independent leakage audit, and explicit model acceptance criteria.

Phase 4 was not started.
