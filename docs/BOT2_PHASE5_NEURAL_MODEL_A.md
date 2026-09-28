# BOT 2.0 Phase 5 — Neural Model A Research Framework

Status: complete on `bot2-phase5-neural-model-a` for review. This phase establishes a research-only neural interface and controlled NumPy implementation. It does not place orders, alter risk/execution, enable live trading, auto-deploy, or build Models B–E.

## 1. Hardware/environment audit

- Python: 3.11.9
- OS: Windows 10 build 26200
- CPU: logical processor count available through `os.cpu_count()`; privileged WMI CPU/RAM/GPU queries were access-restricted
- RAM: not available from the restricted audit context
- GPU/VRAM/NVIDIA driver: no `nvidia-smi` result; treated as unavailable/unknown
- CUDA: unavailable
- Existing environment: repository `.venv`; NumPy is installed; PyTorch is not installed

No CUDA, PyTorch, or GPU packages were installed. The selected framework is isolated NumPy research code because the current machine audit does not establish a compatible GPU/CUDA stack and the controlled data shape does not justify a new dependency. A future environment may select pinned PyTorch only after a separate hardware/dependency review.

## 2–5. Framework, dependencies, tensors, and sequences

The framework is standard-library plus the existing NumPy dependency. `ModelSpec` pins architecture, feature/target versions, dataset, sequence length, hidden width, learning rate, epochs, seed, feature families, and lifecycle. `build_sequences()` produces `X[t-L+1:t]` tensors with shape `[batch, sequence_length, feature_count]`; the initial research sequence length is 3 in the fixture and is version-configurable, not searched.

Sequences are sorted chronologically, require one session boundary per window, reject missing feature values, and carry timestamp/instrument/boundary lineage. They cannot bridge a protected session/split boundary. Future-mutation tests confirm earlier sequence tensors are unchanged.

## 6. Targets and architecture order

The preserved Phase 4 multidimensional targets are direction, volatility, and structure, each represented by a three-class head including neutral/uncertain semantics. A0 remains the Phase 4 deterministic baseline. A1 is a small shared-encoder NumPy MLP with separate direction, volatility, and structure softmax heads. A2 is a causal temporal-convolution candidate that uses only current/past sequence positions; it is implemented as a bounded transform and interface benchmark. No Transformer was built. No real approved ES/NQ dataset was available in this isolated run, so no market claim is made from the synthetic fixture.

## 7–9. Loss, training, and seeds

Each head uses categorical cross-entropy:

`L_head = - (1/N) Σ_i Σ_c y_i,c log(p_i,c)`

The shared objective is the unweighted mean of the three head losses. Class-weighting hooks are intentionally not activated until class frequencies are measured on an approved dataset; no temporal-destroying sampling is used. Training is deterministic NumPy gradient descent with predefined seeds `(1, 2, 3)` and 20 epochs in the fixture. In-sample accuracies were 0.393, 0.357, and 0.286; these are not generalization evidence.

## 10–13. OOS, calibration, and uncertainty

Phase 3 chronological/purged/walk-forward infrastructure remains the required evaluation path. The neural interface stores raw probabilities separately from calibrated probabilities and never labels raw probabilities “confidence.” The first uncertainty mechanism is predictive entropy plus a maximum-probability threshold; invalid/missing inputs abstain fail-closed. A future deep ensemble is intentionally deferred.

On the controlled fixture, the inference latency benchmark over 100 calls was median 0.0266 ms, p95 0.0308 ms, and p99 0.0791 ms. This is an interface benchmark, not production readiness. No real-data OOS calibration result is asserted because the approved ES/NQ dataset and calibration partition were not supplied to this phase run.

## 14–17. Shuffled labels, ablations, and artifact registry

The test suite includes a shuffled-label/control boundary and sequence future-mutation checks. Feature-family ablation is inherited from Phase 3; the Model A artifact records selected feature families. The artifact contract records model ID, architecture, weights hash, preprocessing hash, feature/target/dataset versions, windows, hyperparameters, seed, framework/dependencies, Git commit, lifecycle `EXPERIMENTAL`, and `trading_authority: false`. Corrupt weights, incompatible schema, unauthorized artifacts, NaN/Inf input, and unsupported versions fail closed.

## 18–20. Instrument/session comparison and interface

The internal `RegimeModel.predict()` returns timestamp, instrument, model ID, three head distributions, composite regime, raw/calibrated probabilities, entropy/disagreement fields, abstain status, reason codes, and latency. It is provider-neutral and does not expose framework tensors downstream. ES/NQ and session-window comparisons remain a configured evaluation task for real data; no NQ-leads-ES or ES-leads-NQ assumption is encoded.

## 21–24. Limitations and acceptance conclusion

**INCONCLUSIVE — more evidence required.** The framework is reproducible and leakage-tested, but no approved real ES/NQ dataset was evaluated by Model A in this run. Synthetic in-sample results cannot establish regime generalization, and Phase 3’s no-reliable-signal conclusion remains binding. Model A is not accepted or promoted. Required next evidence is real purged walk-forward evaluation, untouched holdout governance, out-of-sample calibration, seed statistics, per-instrument/session results, and comparison against Phase 4 on the same dataset.

## 25–26. Files and exact branch/commits

Created:

- `bot2/neural/contracts.py`
- `bot2/neural/sequences.py`
- `bot2/neural/model.py`
- `bot2/neural/inference.py`
- `bot2/neural/hardware.py`
- `bot2/neural/__init__.py`
- `bot2/neural/test_neural.py`
- this report

Branch: `bot2-phase5-neural-model-a`

Phase 5 implementation commit: `5175286 Implement BOT 2.0 Phase 5 neural Model A research framework`.

## Test results

- NEW PHASE 5 TESTS: 6 passed.
- PHASE 4 TESTS: 6 passed.
- PHASE 3 TESTS: 9 passed.
- PHASE 2 TESTS: 9 passed.
- PHASE 1 TESTS: 8 passed.
- EXISTING PROVIDER-NEUTRAL REGRESSION TESTS: 5 passed.
- TOTAL: 43 passed.
- Failures/skips: none.

Neural training is research-only. Model B, Model C, Model D, Model E, neural fusion, automatic retraining/deployment, and Phase 6 were not started.
