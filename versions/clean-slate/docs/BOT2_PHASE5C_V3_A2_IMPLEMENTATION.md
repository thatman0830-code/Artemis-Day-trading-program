# BOT 2.0 Phase 5C v3 A2 Implementation

## Implemented architecture

`bot2/phase5c_v3/model.py` contains the deterministic NumPy implementation `CausalTemporalConv`:

1. Input `[batch, 8, 24]`.
2. Causal Conv1D blocks: 24→32, kernel 3, dilation 1; 32→32, kernel 3, dilation 2; 32→16, kernel 3, dilation 4. Each uses stride 1, left-only zero padding, and ReLU.
3. Read only the final valid timestep; shared dense 16→16/ReLU; independent 16→3 direction, volatility, and structure logits; stable softmax conversion kept separate from logits.
4. No dropout or batch normalization. Parameter count: **7,417**. The receptive field is `1 + (3−1)×(1+2+4) = 15` input positions. With sequence length 8, only eight observed historical rows are available.

Initialization is frozen in the manifest: `numpy.random.default_rng(seed)`, He normal for convolution/shared dense weights, Glorot/Xavier uniform for head weights, zero biases, float32 parameters. Adam uses the frozen beta/epsilon values and learning rate; batches are chronological, no minibatch shuffle; validation-only checkpoint selection and clipping follow the manifest. No torch/CUDA dependency was added. The environment used for checks is Windows 10 build 26200, AMD64, Python 3.11.9, NumPy 2.4.6. CPU implementation is sufficient for the architecture's small input/batch dimensions; no GPU requirement was demonstrated.

## Leakage barriers

`PartitionData` tags training and validation partitions. Fitting rejects anything except `TRAIN`; checkpoint selection rejects anything except `VALIDATION_AND_CALIBRATION`. `TrainingOnlyStandardizer` fits only unique 2-D TRAIN rows, then applies the frozen transform to later partitions. The forward convolution shifts inputs only from current/past indices; tests mutate future positions and prove earlier logits remain unchanged. No test or implementation invokes evaluation/performance scoring.

## Artifact integrity

`artifacts.py` creates research-only model artifacts with dataset/feature/target/sequence/seed/window/preprocessing/code/dependency lineage, hashes weights and preprocessing, checks a canonical content hash on read, rejects incompatible feature/target/architecture versions, and hard-codes `trading_authority: false` and `oos_scoring_performed: false`. Writes refuse overwrite.

## Dependencies and limitations

NumPy only; no neural framework was installed. The hand-written NumPy backprop/Adam path has deterministic small-fixture update and repeatability tests but still requires independent code review and an end-to-end small synthetic parity/gradient review before any scoring. It is not connected to paper/live execution and is not a trading model.
