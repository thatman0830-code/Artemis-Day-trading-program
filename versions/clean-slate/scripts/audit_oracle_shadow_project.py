"""Static, fail-closed preflight for a third-party Oracle shadow project."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path


SCHEMA = "oracle-shadow-project-audit-v1"
TEXT_SUFFIXES = {".py", ".js", ".ts", ".json", ".toml", ".yaml", ".yml", ".txt", ".md"}
FORBIDDEN = {
    "private_key": "PRIVATE_KEY_REFERENCE",
    "seed phrase": "SEED_PHRASE_REFERENCE",
    "mnemonic": "MNEMONIC_REFERENCE",
    "place_order": "ORDER_SUBMISSION_SURFACE",
    "market_open": "ORDER_SUBMISSION_SURFACE",
    "/exchange": "HYPERLIQUID_EXCHANGE_ENDPOINT",
}


def audit(root: Path) -> dict:
    base = root.resolve()
    if not base.is_dir():
        raise ValueError("Oracle project directory is required")
    files = []; findings = []
    for path in sorted(x for x in base.rglob("*") if x.is_file() and x.suffix.lower() in TEXT_SUFFIXES):
        raw = path.read_bytes()
        if len(raw) > 2_000_000:
            findings.append({"code":"OVERSIZED_TEXT_FILE", "path":path.relative_to(base).as_posix()})
            continue
        text = raw.decode("utf-8", errors="replace").lower()
        relative = path.relative_to(base).as_posix()
        files.append({"path":relative, "sha256":sha256(raw).hexdigest(), "size":len(raw)})
        for needle, code in FORBIDDEN.items():
            if needle in text:
                findings.append({"code":code, "path":relative})
    state = "REVIEW_REQUIRED" if findings else "STATIC_PREFLIGHT_CLEAR"
    return {"schema_version":SCHEMA, "state":state, "root_name":base.name,
            "files":files, "findings":findings, "execution_permitted":False,
            "deployment_permitted":False, "trading_authority":False,
            "limitations":["Static scanning cannot prove runtime behavior.",
                           "Manual dependency, network, license, and telemetry review is required."]}


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path, required=True);args=parser.parse_args()
    result=audit(args.project);args.output.parent.mkdir(parents=True, exist_ok=True)
    payload=json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    temporary=args.output.with_suffix(args.output.suffix+".tmp")
    temporary.write_text(payload, encoding="utf-8");temporary.replace(args.output)
    print(payload, end="");return 0 if result["state"]=="STATIC_PREFLIGHT_CLEAR" else 2


if __name__ == "__main__":
    raise SystemExit(main())
