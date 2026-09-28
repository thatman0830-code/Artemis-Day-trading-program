"""Reproducible dataset provenance manifests."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib, json, subprocess
from collections import Counter
from pathlib import Path
from typing import Iterable
from .contracts import DatasetManifest, DataQualityReport, MarketEvent


def _sha(value: bytes) -> str: return hashlib.sha256(value).hexdigest()


def build_manifest(*, dataset_id: str, source: str, events: Iterable[MarketEvent],
                   quality_report: DataQualityReport, schema_version: str,
                   configuration: object = None, source_bytes: bytes | None = None,
                   code_commit: str | None = None, created_at: datetime | None = None) -> DatasetManifest:
    rows = tuple(events)
    if not rows or quality_report.state != "HEALTHY":
        raise ValueError("only non-empty healthy data can receive a manifest")
    canonical = "\n".join(json.dumps(e.to_dict(), sort_keys=True, separators=(",", ":")) for e in rows).encode()
    config_bytes = json.dumps(configuration or {}, sort_keys=True, separators=(",", ":")).encode()
    if code_commit is None:
        try: code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        except Exception: code_commit = "UNKNOWN"
    # A default derived from source data keeps manifests reproducible. Callers
    # may provide an operational wall-clock timestamp explicitly for audit UI.
    created_at = created_at or rows[-1].exchange_time
    provenance = Counter(f"{e.timestamp_source}:receive={str(e.receive_timestamp_available).lower()}" for e in rows)
    return DatasetManifest(dataset_id=dataset_id, source=source,
        instruments=tuple(sorted({e.instrument for e in rows})),
        start_exchange_time=rows[0].exchange_time.isoformat(), end_exchange_time=rows[-1].exchange_time.isoformat(),
        schema_version=schema_version, validation_status=quality_report.state,
        source_sha256=_sha(source_bytes if source_bytes is not None else canonical), normalized_sha256=_sha(canonical),
        code_commit=code_commit, configuration_sha256=_sha(config_bytes), event_count=len(rows),
        quality_report=quality_report, created_at=created_at.isoformat(),
        timestamp_provenance=dict(sorted(provenance.items())), trading_authority=False)
