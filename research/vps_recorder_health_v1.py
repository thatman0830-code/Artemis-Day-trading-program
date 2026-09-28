"""Container health probe for the read-only Hyperliquid recorder."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys


def healthy(path: Path, *, now: datetime | None = None) -> bool:
    try:
        doc = json.loads(path.read_text("utf-8")); current = now or datetime.now(timezone.utc)
        updated = datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00"))
        if (doc.get("state") != "RECORDING" or doc.get("source") != "hyperliquid-public-mainnet"
                or current - updated > __import__("datetime").timedelta(minutes=5)):
            return False
        for name, digest in doc.get("checksums", {}).items():
            target = path.parent / name
            if not target.is_file() or sha256(target.read_bytes()).hexdigest() != digest:
                return False
        return bool(doc.get("checksums"))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


if __name__ == "__main__":
    raise SystemExit(0 if len(sys.argv) == 2 and healthy(Path(sys.argv[1])) else 1)
