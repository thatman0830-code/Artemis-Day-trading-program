from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_v1 import (
    NinjaTraderCanonicalSmokeError, assert_distinct_ninjatrader_smokes,
    evaluate_ninjatrader_canonical_smoke,
)
from backtesting.ninjatrader_closed_bar_dataset_v1 import read_closed_bar_dataset
from backtesting.test_ninjatrader_closed_bar_dataset_v1 import NOW, build


def prepared(tmp_path, market):
    build(tmp_path, market)
    evidence = read_closed_bar_dataset(tmp_path, market=market,
        day="2026-09-08", as_of=NOW + timedelta(minutes=4))
    return evidence


@pytest.mark.parametrize("market", list(FuturesCanonicalMarket))
def test_genuine_shape_replays_twice_without_authority(tmp_path, market):
    evidence = prepared(tmp_path, market)
    result = evaluate_ninjatrader_canonical_smoke(evidence=evidence,
        minimum_tick=Decimal("0.25"), instrument_specification_id="a" * 64,
        as_of=NOW + timedelta(minutes=4))
    assert result.source_bar_count == result.evaluated_batch_count == 3
    assert result.deterministic_repeat_verified is True
    assert result.advisory_only is True
    assert result.paper_execution_permitted is False
    assert result.live_trading_permitted is False
    assert result.trading_authority is False


def test_same_evidence_produces_identical_report(tmp_path):
    evidence = prepared(tmp_path, FuturesCanonicalMarket.ES)
    kwargs = dict(evidence=evidence, minimum_tick=Decimal("0.25"),
        instrument_specification_id="a" * 64,
        as_of=NOW + timedelta(minutes=4))
    assert evaluate_ninjatrader_canonical_smoke(**kwargs) == evaluate_ninjatrader_canonical_smoke(**kwargs)


def test_es_nq_reports_are_isolated(tmp_path):
    es = evaluate_ninjatrader_canonical_smoke(
        evidence=prepared(tmp_path / "es", FuturesCanonicalMarket.ES),
        minimum_tick=Decimal("0.25"), instrument_specification_id="a" * 64,
        as_of=NOW + timedelta(minutes=4))
    nq = evaluate_ninjatrader_canonical_smoke(
        evidence=prepared(tmp_path / "nq", FuturesCanonicalMarket.NQ),
        minimum_tick=Decimal("0.25"), instrument_specification_id="b" * 64,
        as_of=NOW + timedelta(minutes=4))
    assert_distinct_ninjatrader_smokes(es, nq)


def test_authority_forgery_and_invalid_inputs_fail_closed(tmp_path):
    evidence = prepared(tmp_path, FuturesCanonicalMarket.ES)
    with pytest.raises(NinjaTraderCanonicalSmokeError, match="prohibited authority"):
        evaluate_ninjatrader_canonical_smoke(evidence=replace(evidence, trading_authority=True),
            minimum_tick=Decimal("0.25"), instrument_specification_id="a" * 64,
            as_of=NOW + timedelta(minutes=4))
    with pytest.raises(NinjaTraderCanonicalSmokeError, match="positive exact Decimal"):
        evaluate_ninjatrader_canonical_smoke(evidence=evidence, minimum_tick=0.25,
            instrument_specification_id="a" * 64, as_of=NOW + timedelta(minutes=4))


def test_module_has_no_execution_dependency_or_order_surface():
    source = __import__("pathlib").Path(__file__).with_name(
        "ninjatrader_canonical_smoke_v1.py").read_text()
    assert "from execution" not in source
    for text in ("SubmitOrder", "CreateOrder", "paper_execution_permitted: bool = True",
                 "trading_authority: bool = True"):
        assert text not in source
