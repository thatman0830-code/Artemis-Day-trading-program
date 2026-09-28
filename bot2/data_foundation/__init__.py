"""Versioned, deterministic BOT 2.0 market-data foundation."""

from .contracts import (
    DATASET_MANIFEST_SCHEMA,
    DATA_QUALITY_SCHEMA,
    RAW_EVENT_SCHEMA,
    DataQualityReport,
    DatasetManifest,
    MarketEvent,
    QualityReason,
)
from .manifest import build_manifest
from .replay import deterministic_replay
from .sync import synchronize_es_nq
from .instruments import InstrumentIdentity, normalize_contract
from .sync import RootSynchronizationReport, synchronize_contract_roots
from .validation import validate_events, validate_synchronized_events

__all__ = [
    "DATASET_MANIFEST_SCHEMA", "DATA_QUALITY_SCHEMA", "RAW_EVENT_SCHEMA",
    "DataQualityReport", "DatasetManifest", "MarketEvent", "QualityReason",
    "InstrumentIdentity", "normalize_contract", "RootSynchronizationReport", "synchronize_contract_roots",
    "build_manifest", "deterministic_replay", "synchronize_es_nq",
    "validate_events", "validate_synchronized_events",
]
