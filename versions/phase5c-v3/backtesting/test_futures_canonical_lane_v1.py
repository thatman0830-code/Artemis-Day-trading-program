from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backtesting.core_v1.production_adapters import ArchiveEligibility
from backtesting.core_v1.splits import PartitionRole, TimePartition, build_split_plan
from backtesting.futures_canonical_lane_v1 import (
    FuturesCanonicalMarket,
    admit_futures_canonical_lane,
    assert_distinct_futures_lanes,
)
from backtesting.test_core_v1_production_adapters import pass_b_fixture


UTC = timezone.utc
T0 = datetime(2025, 1, 1, tzinfo=UTC)


def split(market: str, suffix: str = ""):
    rows = tuple(
        TimePartition(f"{market}-{role.value}{suffix}", market, role,
                      T0 + timedelta(days=index * 10),
                      T0 + timedelta(days=(index + 1) * 10))
        for index, role in enumerate((PartitionRole.TRAIN,
                                      PartitionRole.VALIDATION,
                                      PartitionRole.TEST))
    )
    return build_split_plan(version=f"split-{market}{suffix}", partitions=rows)


def lane(tmp_path, market: FuturesCanonicalMarket):
    adapter, _ = pass_b_fixture(tmp_path / market.value.lower(), market.value)
    return admit_futures_canonical_lane(
        market=market, adapter=adapter, split_plan=split(market.value),
        strategy_configuration_version="canonical-strategy-v1",
        model_configuration_version="canonical-model-v1",
    )


@pytest.mark.parametrize("market", list(FuturesCanonicalMarket))
def test_es_and_nq_admit_as_advisory_isolated_research_lanes(tmp_path, market):
    result = lane(tmp_path, market)
    assert result.market is market
    assert result.purpose is ArchiveEligibility.TRAINING_VALIDATION
    assert result.advisory_only is True
    assert result.trading_authority is False
    assert result.paper_execution_permitted is False
    assert result.live_trading_permitted is False


def test_es_and_nq_have_distinct_dataset_split_and_lane_identities(tmp_path):
    es = lane(tmp_path, FuturesCanonicalMarket.ES)
    nq_adapter, _ = pass_b_fixture(tmp_path / "nq", "NQ")
    nq = admit_futures_canonical_lane(
        market=FuturesCanonicalMarket.NQ, adapter=nq_adapter,
        split_plan=split("NQ", "-independent"),
        strategy_configuration_version="canonical-strategy-v1",
        model_configuration_version="canonical-model-v1",
    )
    assert_distinct_futures_lanes(es, nq)


def test_cross_market_archive_or_split_rejects(tmp_path):
    es_adapter, _ = pass_b_fixture(tmp_path / "es", "ES")
    with pytest.raises(ValueError, match="market identities differ"):
        admit_futures_canonical_lane(
            market=FuturesCanonicalMarket.NQ, adapter=es_adapter,
            split_plan=split("NQ"), strategy_configuration_version="s1",
            model_configuration_version="m1")
    with pytest.raises(ValueError, match="market-isolated split"):
        admit_futures_canonical_lane(
            market=FuturesCanonicalMarket.ES, adapter=es_adapter,
            split_plan=split("NQ"), strategy_configuration_version="s1",
            model_configuration_version="m1")


def test_final_acceptance_and_unverified_configuration_reject(tmp_path):
    adapter, _ = pass_b_fixture(tmp_path / "es", "ES")
    with pytest.raises(ValueError, match="research purposes only"):
        admit_futures_canonical_lane(
            market=FuturesCanonicalMarket.ES, adapter=adapter,
            split_plan=split("ES"), strategy_configuration_version="s1",
            model_configuration_version="m1",
            purpose=ArchiveEligibility.FINAL_ACCEPTANCE)
    with pytest.raises(ValueError, match="configuration versions"):
        admit_futures_canonical_lane(
            market=FuturesCanonicalMarket.ES, adapter=adapter,
            split_plan=split("ES"), strategy_configuration_version="",
            model_configuration_version="m1")


def test_distinct_lane_guard_rejects_shared_evidence(tmp_path):
    es = lane(tmp_path, FuturesCanonicalMarket.ES)
    forged_nq = replace(es, market=FuturesCanonicalMarket.NQ)
    with pytest.raises(ValueError, match="identities must be distinct"):
        assert_distinct_futures_lanes(es, forged_nq)

