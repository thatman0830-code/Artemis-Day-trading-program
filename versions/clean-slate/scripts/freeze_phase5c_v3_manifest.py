"""Create the one-time, immutable v3 manifest by preserving v2 settings."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from bot2.phase5c_v3.manifest import V2_CANONICAL_SHA256, V2_COMMIT, canonical_hash

ROOT = Path(__file__).resolve().parents[1]
V2_PATH = ROOT / "config" / "bot2_phase5c_experiment_manifest_v2.json"
V3_PATH = ROOT / "config" / "bot2_phase5c_experiment_manifest_v3.json"


def main() -> None:
    if V3_PATH.exists():
        raise SystemExit("REFUSE_OVERWRITE_FROZEN_V3_MANIFEST")
    v2 = json.loads(V2_PATH.read_text(encoding="utf-8"))
    if canonical_hash(v2) != V2_CANONICAL_SHA256 or v2.get("manifest_sha256") != V2_CANONICAL_SHA256:
        raise SystemExit("V2_CANONICAL_HASH_MISMATCH_STOP")
    v3 = copy.deepcopy(v2)
    v3.update({
        "schema_version": "bot2-phase5c-experiment-manifest-v3",
        "experiment_id": "bot2-phase5c-future-state-esnq-v3",
        "protocol_status": "FROZEN_NOT_APPROVED_PENDING_INDEPENDENT_REVIEW",
        "evaluation_permitted": False,
        "oos_model_scoring_performed": False,
        "protocol_parent_commit": V2_COMMIT,
        "supersedes_manifest_sha256": V2_CANONICAL_SHA256,
        "supersession_reason": "Phase 5C v2 was superseded before OOS scoring because its frozen A2 summary transform conflicted with the intended learned temporal-convolution architecture.",
        "protocol_frozen_date": "2026-09-22",
    })
    v3.pop("implementation_commit", None)
    v3["implementation_commit_policy"] = "Every dry-run or future scoring artifact must record the exact full Git commit; scoring additionally requires a clean working tree and independent approval."
    v3["architectures"]["A2_LEARNED_CAUSAL_TCN"] = {
        "implementation": "bot2.phase5c_v3.model.CausalTemporalConv",
        "architecture_version": "bot2-phase5c-a2-causal-tcn-v3",
        "input": "[batch, sequence_length=8, features=24]; temporal order preserved",
        "blocks": [
            {"type": "causal_conv1d", "in_channels": 24, "out_channels": 32, "kernel_width": 3, "stride": 1, "dilation": 1, "padding": "left-only-zero", "activation": "ReLU"},
            {"type": "causal_conv1d", "in_channels": 32, "out_channels": 32, "kernel_width": 3, "stride": 1, "dilation": 2, "padding": "left-only-zero", "activation": "ReLU"},
            {"type": "causal_conv1d", "in_channels": 32, "out_channels": 16, "kernel_width": 3, "stride": 1, "dilation": 4, "padding": "left-only-zero", "activation": "ReLU"},
        ],
        "receptive_field_timesteps": 15,
        "temporal_readout": "final valid timestamp T only; no pooling over padded or future positions",
        "shared_representation": {"dense": "16->16", "activation": "ReLU"},
        "heads": {"direction": "16->3 logits", "volatility": "16->3 logits", "structure": "16->3 logits"},
        "probability_conversion": "stable softmax; preserve logits and probabilities separately",
        "dropout": False,
        "batch_normalization": False,
        "future_looking_or_bidirectional_operations": False,
    }
    v3["a2_training"] = {
        "optimizer": "Adam",
        "learning_rate": 0.001,
        "adam_beta1": 0.9,
        "adam_beta2": 0.999,
        "adam_epsilon": 1e-8,
        "batch_size": 256,
        "batch_order": "chronological contiguous batches; no minibatch shuffle",
        "max_epochs": 50,
        "early_stopping": {"enabled": True, "partition": "VALIDATION_AND_CALIBRATION", "patience": 5, "checkpoint": "lowest authorized validation multi-head categorical cross-entropy"},
        "gradient_clipping": {"method": "global L2 norm", "maximum_norm": 1.0},
        "loss": {"type": "sum of categorical cross-entropies", "head_weights": {"direction": 1.0, "volatility": 1.0, "structure": 1.0}},
        "class_imbalance": "No class weights, resampling, or synthetic examples; equal per-head categorical loss, consistent with frozen v2 policy.",
        "initialization": {"rng": "numpy.random.default_rng(seed)", "convolution_and_shared_dense": "He normal, std=sqrt(2/fan_in), fan_in includes kernel width for convolutions", "head_weights": "Glorot/Xavier uniform, limit=sqrt(6/(fan_in+fan_out))", "all_biases": "zero", "dtype": "float32"},
        "determinism": "Fixed seed, deterministic NumPy CPU operations, sequential fixed-order batching; no stochastic layers.",
    }
    v3["a1_training"] = {
        "inherited_from_v2": True,
        "optimizer": "full-batch simultaneous gradient descent",
        "learning_rate": 0.01,
        "epochs": 50,
        "early_stopping": False,
        "regularization": "none",
        "minibatch_shuffle": False,
    }
    v3["independent_review_required_before_scoring"] = True
    v3["trading_authority"] = False
    v3["manifest_hashing"] = "SHA-256 canonical sorted compact UTF-8 JSON excluding manifest_sha256"
    v3.pop("manifest_sha256", None)
    v3["manifest_sha256"] = canonical_hash(v3)
    V3_PATH.write_text(json.dumps(v3, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(V3_PATH), "manifest_sha256": v3["manifest_sha256"], "v2_sha256": V2_CANONICAL_SHA256}, indent=2))


if __name__ == "__main__":
    main()
