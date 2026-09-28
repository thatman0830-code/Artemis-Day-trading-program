"""Immutable ES/NQ canonical research-lane admission.

This module binds one verified futures archive to one market-isolated strategy
and split plan.  It is offline/advisory infrastructure only and deliberately
has no dependency on BTC paper execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backtesting.core_v1.models import fingerprint
from backtesting.core_v1.production_adapters import (
    AdapterMetadata,
    ArchiveEligibility,
    PassBV3ArchiveAdapter,
)
from backtesting.core_v1.splits import PartitionRole, SplitPlan


LANE_VERSION = "futures-canonical-research-lane-v1"


class FuturesCanonicalMarket(str, Enum):
    ES = "ES"
    NQ = "NQ"


@dataclass(frozen=True)
class FuturesCanonicalLaneV1:
    lane_id: str
    market: FuturesCanonicalMarket
    dataset_id: str
    dataset_fingerprint: str
    split_plan_id: str
    strategy_configuration_version: str
    model_configuration_version: str
    archive_adapter_version: str
    purpose: ArchiveEligibility
    advisory_only: bool = True
    trading_authority: bool = False
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    schema_version: str = LANE_VERSION


def admit_futures_canonical_lane(
    *,
    market: FuturesCanonicalMarket,
    adapter: PassBV3ArchiveAdapter,
    split_plan: SplitPlan,
    strategy_configuration_version: str,
    model_configuration_version: str,
    purpose: ArchiveEligibility = ArchiveEligibility.TRAINING_VALIDATION,
) -> FuturesCanonicalLaneV1:
    """Validate and bind one ES or NQ research lane, failing closed."""
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("an explicit ES or NQ canonical market is required")
    if not isinstance(adapter, PassBV3ArchiveAdapter):
        raise TypeError("a verified Pass B v3 archive adapter is required")
    if purpose not in (ArchiveEligibility.SMOKE_REPLAY,
                       ArchiveEligibility.TRAINING_VALIDATION,
                       ArchiveEligibility.UNTOUCHED_OOS):
        raise ValueError("canonical futures lane supports research purposes only")
    if not strategy_configuration_version or not model_configuration_version:
        raise ValueError("strategy and model configuration versions are required")

    metadata: AdapterMetadata = adapter.validate()
    if adapter.market != market.value or metadata.markets != (market.value,):
        raise ValueError("archive and canonical lane market identities differ")
    if not metadata.instruments or any(not value.startswith(market.value) for value in metadata.instruments):
        raise ValueError("archive instrument inventory escapes the canonical market")
    if not metadata.eligibility.permits(purpose):
        raise ValueError("archive evidence is ineligible for the requested research purpose")

    partitions = split_plan.partitions
    if len(partitions) != 3 or {row.market for row in partitions} != {market.value}:
        raise ValueError("lane requires exactly one market-isolated split plan")
    if tuple(row.role for row in sorted(partitions, key=lambda row: row.start_inclusive)) != (
        PartitionRole.TRAIN, PartitionRole.VALIDATION, PartitionRole.TEST
    ):
        raise ValueError("lane split roles must be chronological TRAIN/VALIDATION/TEST")

    identity = fingerprint((
        LANE_VERSION, market.value, metadata.dataset_id,
        metadata.dataset_fingerprint, split_plan.id,
        strategy_configuration_version, model_configuration_version,
        adapter.adapter_version, purpose.value,
    ))
    return FuturesCanonicalLaneV1(
        identity, market, metadata.dataset_id, metadata.dataset_fingerprint,
        split_plan.id, strategy_configuration_version,
        model_configuration_version, adapter.adapter_version, purpose,
    )


def assert_distinct_futures_lanes(
    es: FuturesCanonicalLaneV1, nq: FuturesCanonicalLaneV1
) -> None:
    """Reject cross-market identity, dataset, or split-plan contamination."""
    if (es.market, nq.market) != (FuturesCanonicalMarket.ES, FuturesCanonicalMarket.NQ):
        raise ValueError("expected ordered ES and NQ canonical lanes")
    if es.lane_id == nq.lane_id or es.dataset_id == nq.dataset_id:
        raise ValueError("ES and NQ lane identities must be distinct")
    if es.dataset_fingerprint == nq.dataset_fingerprint:
        raise ValueError("ES and NQ datasets must be independently fingerprinted")
    if es.split_plan_id == nq.split_plan_id:
        raise ValueError("ES and NQ split plans must be independently owned")

