from __future__ import annotations

from pathlib import Path
import json
from .contracts import ExperimentResult


class ExperimentRegistry:
    """Append-only registry: finalized experiment IDs cannot be overwritten."""
    def __init__(self, path: str | Path): self.path = Path(path)

    def finalize(self, result: ExperimentResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if self.path.exists():
            existing = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        ids = {entry["experiment"]["experiment_id"] for entry in existing}
        if result.spec.experiment_id in ids: raise ValueError("experiment ID is immutable and already finalized")
        with self.path.open("a", encoding="utf-8") as handle: handle.write(result.canonical_json() + "\n")
