from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtesting.ninjatrader_canonical_boundary_v1 import (
    CanonicalBoundaryV1, QuarantinedArchiveV1, evaluate_canonical_paper_readiness,
)


def clean(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, tuple): return [clean(item) for item in value]
    if isinstance(value, dict): return {key: clean(item) for key, item in value.items()}
    return value


def main() -> int:
    source = ROOT / "outputs/operational_health/ninjatrader-canonical-boundary-2026-09-14.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    boundary = CanonicalBoundaryV1(
        target_day_utc=raw["target_day_utc"],
        established_at=datetime.fromisoformat(raw["established_at"]),
        prior_archives=tuple(QuarantinedArchiveV1(**row) for row in raw["prior_archives"]),
        state=raw["state"], paper_execution_permitted=raw["paper_execution_permitted"],
        trading_authority=raw["trading_authority"], schema_version=raw["schema_version"])
    result = evaluate_canonical_paper_readiness(
        boundary=boundary, archive_root=ROOT / "data/ninjatrader_closed_bars",
        as_of=datetime.now(timezone.utc))
    target = ROOT / "outputs/operational_health/ninjatrader-monday-readiness.json"
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(clean(asdict(result)), sort_keys=True,
                                    separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, target)
    print(json.dumps(clean(asdict(result)), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__": raise SystemExit(main())
