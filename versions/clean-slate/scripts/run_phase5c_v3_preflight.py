"""Run the frozen Phase 5C v3 preflight only; no model scoring code exists here."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from bot2.phase5c_v3.runner import run_preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True,
                        help="Required. The only supported mode; final scoring is not implemented.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dataset-root", type=Path, required=True,
                        help="Root containing ES/normalized and NQ/normalized Pass B JSONL payloads.")
    parser.add_argument("--output-directory", type=Path, default=None)
    parser.add_argument("--external-anchor", type=Path, required=True,
                        help="User-preserved anchor file outside the repository/worktree.")
    args = parser.parse_args()
    control_command = [sys.executable, "-m", "pytest", "-q",
                       str(args.repo_root / "bot2" / "phase5c_v3" / "test_phase5c_v3.py")]
    controls = subprocess.run(control_command, cwd=args.repo_root,
                              capture_output=True, text=True, timeout=180)
    control_result = {
        "status": "PASS" if controls.returncode == 0 else "FAIL",
        "command": ["python", "-m", "pytest", "-q",
                    "bot2/phase5c_v3/test_phase5c_v3.py"],
        "returncode": controls.returncode,
        "stdout": controls.stdout,
        "stderr": controls.stderr,
        "scope": "synthetic/non-protected executable controls only",
    }
    if controls.returncode != 0:
        print(json.dumps({"executable_controls": control_result,
                          "status": "PREFLIGHT_BLOCKED",
                          "reason_code": "EXECUTABLE_CONTROLS_TESTS_FAILED"},
                         sort_keys=True, indent=2))
        return 3
    result = run_preflight(args.repo_root, args.dataset_root, output_directory=args.output_directory,
                           external_anchor_path=args.external_anchor)
    print(json.dumps({"executable_controls": control_result,
                      "preflight": result,
                      "status": result["status"]}, sort_keys=True, indent=2))
    return 0 if result["status"] == "PREFLIGHT_READY_NO_SCORING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
