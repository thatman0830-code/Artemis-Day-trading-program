from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backtesting.futures_canonical_evaluation_v1 import (
    FuturesCanonicalEvaluationError,
    assert_distinct_futures_evaluations,
    evaluate_futures_canonical_lane,
)
from backtesting.futures_canonical_lane_v1 import (
    FuturesCanonicalMarket,
    admit_futures_canonical_lane,
)
from backtesting.test_futures_canonical_lane_v1 import split
from backtesting.test_core_v1_production_adapters import pass_b_fixture


NOW = datetime(2026, 1, 6, tzinfo=timezone.utc)
SPEC = "a" * 64


def prepared(tmp_path, market):
    adapter, _ = pass_b_fixture(tmp_path / market.value.lower(), market.value)
    lane = admit_futures_canonical_lane(market=market, adapter=adapter,
        split_plan=split(market.value),
        strategy_configuration_version="canonical-strategy-v1",
        model_configuration_version="canonical-model-v1")
    return lane, adapter


@pytest.mark.parametrize("market", list(FuturesCanonicalMarket))
def test_verified_lane_replays_through_canonical_brain_without_authority(tmp_path, market):
    lane, adapter = prepared(tmp_path, market)
    result = evaluate_futures_canonical_lane(lane=lane, adapter=adapter,
        minimum_tick=Decimal("0.25"), instrument_specification_id=SPEC, as_of=NOW)
    assert result.market is market
    assert result.source_bar_count == result.evaluated_batch_count == 1
    assert result.source_contract_ids == (f"c-{market.value}",)
    assert result.latest_outcome == "NO_SETUP"
    assert result.advisory_only is True
    assert result.paper_execution_permitted is False
    assert result.live_trading_permitted is False
    assert result.trading_authority is False


def test_evaluation_is_byte_identity_deterministic(tmp_path):
    lane, adapter = prepared(tmp_path, FuturesCanonicalMarket.ES)
    kwargs = dict(lane=lane, adapter=adapter, minimum_tick=Decimal("0.25"),
                  instrument_specification_id=SPEC, as_of=NOW)
    assert evaluate_futures_canonical_lane(**kwargs) == evaluate_futures_canonical_lane(**kwargs)


def test_es_nq_evaluations_remain_distinct(tmp_path):
    es_lane, es_adapter = prepared(tmp_path, FuturesCanonicalMarket.ES)
    nq_lane, nq_adapter = prepared(tmp_path, FuturesCanonicalMarket.NQ)
    es = evaluate_futures_canonical_lane(lane=es_lane, adapter=es_adapter,
        minimum_tick=Decimal("0.25"), instrument_specification_id="a"*64, as_of=NOW)
    nq = evaluate_futures_canonical_lane(lane=nq_lane, adapter=nq_adapter,
        minimum_tick=Decimal("0.25"), instrument_specification_id="b"*64, as_of=NOW)
    assert_distinct_futures_evaluations(es, nq)


def test_cross_market_adapter_stale_time_and_invalid_spec_reject(tmp_path):
    es_lane, _ = prepared(tmp_path, FuturesCanonicalMarket.ES)
    _, nq_adapter = prepared(tmp_path, FuturesCanonicalMarket.NQ)
    with pytest.raises(FuturesCanonicalEvaluationError, match="differs"):
        evaluate_futures_canonical_lane(lane=es_lane, adapter=nq_adapter,
            minimum_tick=Decimal("0.25"), instrument_specification_id=SPEC, as_of=NOW)
    es_lane, es_adapter = prepared(tmp_path / "second", FuturesCanonicalMarket.ES)
    with pytest.raises(FuturesCanonicalEvaluationError, match="precede"):
        evaluate_futures_canonical_lane(lane=es_lane, adapter=es_adapter,
            minimum_tick=Decimal("0.25"), instrument_specification_id=SPEC,
            as_of=datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc))
    with pytest.raises(FuturesCanonicalEvaluationError, match="SHA-256"):
        evaluate_futures_canonical_lane(lane=es_lane, adapter=es_adapter,
            minimum_tick=Decimal("0.25"), instrument_specification_id="not-evidence", as_of=NOW)


def test_float_or_nonpositive_tick_rejects(tmp_path):
    lane, adapter = prepared(tmp_path, FuturesCanonicalMarket.ES)
    for tick in (0.25, Decimal("0")):
        with pytest.raises(FuturesCanonicalEvaluationError, match="positive exact Decimal"):
            evaluate_futures_canonical_lane(lane=lane, adapter=adapter,
                minimum_tick=tick, instrument_specification_id=SPEC, as_of=NOW)

