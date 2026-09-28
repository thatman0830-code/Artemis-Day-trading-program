"""Fail-closed entry point for the isolated Hermes engineering worker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse


SOURCE_COMMIT = "fcbd1076a93841fa88855acce810e342a5b78101"
ALLOWED_BRANCH_PREFIX = "hermes/"
ALLOWED_TOOLSETS = "terminal,file"
FORBIDDEN_ENV_FRAGMENTS = (
    "PRIVATE_KEY",
    "SEED_PHRASE",
    "MNEMONIC",
    "WALLET",
    "EXCHANGE_API",
    "BROKER",
    "HYPERLIQUID",
    "AWS_",
    "AZURE_",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "SSH_",
)


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"HERMES WORKER SECURITY ERROR: {message}")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd="/workspace",
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def audit() -> dict[str, object]:
    workspace = Path("/workspace").resolve()
    if workspace != Path.cwd().resolve():
        fail("working directory is not /workspace")
    branch = git("branch", "--show-current")
    if not branch.startswith(ALLOWED_BRANCH_PREFIX):
        fail(f"branch {branch!r} is outside hermes/*")
    origin = git("remote", "get-url", "origin") if git("remote") else ""
    if origin and not origin.startswith("file://"):
        fail("workspace origin is not a local file URL")
    forbidden = sorted(
        key for key in os.environ
        if any(fragment in key.upper() for fragment in FORBIDDEN_ENV_FRAGMENTS)
    )
    if forbidden:
        fail("forbidden secret-like environment names are present: " + ", ".join(forbidden))
    return {
        "status": "PASS",
        "source_commit": SOURCE_COMMIT,
        "workspace": str(workspace),
        "branch": branch,
        "origin": origin,
        "uid": os.getuid(),
        "gid": os.getgid(),
        "host_time_utc": os.environ.get("HERMES_HOST_TIME_UTC", ""),
    }


def run_task(prompt_path: str) -> None:
    facts = audit()
    prompt = Path(prompt_path).resolve()
    workspace = Path("/workspace").resolve()
    if workspace not in prompt.parents or not prompt.is_file():
        fail("prompt must be a regular file beneath /workspace")
    base_url = os.environ.get("HERMES_INFERENCE_BASE_URL", "").strip()
    model = os.environ.get("HERMES_INFERENCE_MODEL", "").strip()
    if not base_url or not model:
        fail("dedicated inference base URL and model are required")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        fail("inference base URL must be HTTPS")
    allowed_host = os.environ.get("HERMES_INFERENCE_HOST", "").strip().lower()
    if parsed.hostname.lower() != allowed_host:
        fail("inference host does not match the audited allowlist identity")
    max_turns = int(os.environ.get("HERMES_MAX_TURNS", "10"))
    if not 1 <= max_turns <= 80:
        fail("turn budget must be between 1 and 80")
    query = prompt.read_text(encoding="utf-8")
    if not query.strip():
        fail("task prompt is empty")
    if os.environ.get("HERMES_CREDENTIAL_STDIN") != "1":
        fail("credential must be supplied through the audited stdin boundary")
    api_key = sys.stdin.readline().rstrip("\r\n")
    if not api_key:
        fail("dedicated inference credential was not provided")
    print(json.dumps({**facts, "mode": "task", "prompt": str(prompt)}, sort_keys=True))
    from run_agent import main

    main(
        query=query,
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_turns=max_turns,
        enabled_toolsets=ALLOWED_TOOLSETS,
        disabled_toolsets=None,
        save_trajectories=True,
        save_sample=False,
        verbose=False,
        log_prefix_chars=0,
    )


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if command == "audit" and len(sys.argv) == 2:
        print(json.dumps(audit(), sort_keys=True))
        return
    if command == "task" and len(sys.argv) == 3:
        run_task(sys.argv[2])
        return
    fail("only 'audit' and 'task <workspace-prompt>' are permitted")


if __name__ == "__main__":
    main()
