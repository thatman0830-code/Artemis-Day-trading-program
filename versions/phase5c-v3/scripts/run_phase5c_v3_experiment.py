"""Explicit-mode CLI for the Phase 5C-v3 experiment runner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bot2.phase5c_v3.experiment_runner import (
    ExecutionMode, Phase5CExecutionError, run_phase5c_experiment,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=[mode.value for mode in ExecutionMode])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--external-anchor", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    try:
        result = run_phase5c_experiment(args.mode, manifest_path=args.manifest,
            external_anchor_path=args.external_anchor, repo_root=args.repo_root,
            dataset_root=args.dataset_root, output_directory=args.output_directory)
    except Phase5CExecutionError as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": exc.reason_code}, sort_keys=True))
        return 2
    print(json.dumps({"status": result.get("status", "PREFLIGHT_COMPLETE"),
        "execution_mode": args.mode, "result_artifact_sha256": result.get("result_artifact_sha256"),
        "manifest_sha256": result.get("manifest_sha256"),
        "protected_oos_execution": result.get("protected_oos_execution", "NOT EXECUTED"),
        "trading_authority": result.get("trading_authority", "NONE")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
