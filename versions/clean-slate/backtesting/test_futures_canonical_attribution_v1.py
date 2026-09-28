from datetime import timedelta
from decimal import Decimal
import json

import pytest

from backtesting.futures_canonical_attribution_v1 import (
    FuturesCanonicalAttributionError,
    assert_distinct_futures_attributions,
    evaluate_futures_canonical_attribution,
    write_futures_canonical_attribution,
)
from backtesting.futures_canonical_evaluation_v1 import evaluate_futures_canonical_lane
from backtesting.futures_canonical_history_v1 import append_futures_canonical_evaluation
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.test_futures_canonical_evaluation_v1 import NOW, SPEC, prepared


def append(root, source, market, as_of):
    lane, adapter = prepared(source, market)
    report = evaluate_futures_canonical_lane(lane=lane, adapter=adapter,
        minimum_tick=Decimal("0.25"), instrument_specification_id=SPEC, as_of=as_of)
    return append_futures_canonical_evaluation(root, report=report)


def test_empty_market_is_explicitly_insufficient(tmp_path):
    summary = evaluate_futures_canonical_attribution(tmp_path, market=FuturesCanonicalMarket.ES)
    assert summary.history_event_count == summary.finalized_trade_count == 0
    assert summary.minimum_finalized_trades_required == 200
    assert summary.minimum_sample_met is False
    assert summary.finalized_accounting_available is False
    assert summary.untouched_oos_eligible is False


def test_evaluations_are_counted_but_never_fabricated_as_trades(tmp_path):
    root = tmp_path / "history"
    append(root, tmp_path / "a", FuturesCanonicalMarket.ES, NOW)
    append(root, tmp_path / "b", FuturesCanonicalMarket.ES, NOW + timedelta(minutes=1))
    summary = evaluate_futures_canonical_attribution(root, market=FuturesCanonicalMarket.ES)
    assert summary.history_event_count == 2
    assert dict(summary.evaluation_outcome_counts) == {"NO_SETUP": 2}
    assert summary.finalized_trade_count == 0
    assert summary.untouched_oos_eligible is False
    assert summary.history_head_event_id is not None


def test_es_nq_summaries_and_artifacts_are_isolated(tmp_path):
    history = tmp_path / "history"
    append(history, tmp_path / "es", FuturesCanonicalMarket.ES, NOW)
    append(history, tmp_path / "nq", FuturesCanonicalMarket.NQ, NOW)
    es = evaluate_futures_canonical_attribution(history, market=FuturesCanonicalMarket.ES)
    nq = evaluate_futures_canonical_attribution(history, market=FuturesCanonicalMarket.NQ)
    assert_distinct_futures_attributions(es, nq)
    es_path = write_futures_canonical_attribution(history, tmp_path / "output",
        market=FuturesCanonicalMarket.ES)
    nq_path = write_futures_canonical_attribution(history, tmp_path / "output",
        market=FuturesCanonicalMarket.NQ)
    assert es_path.parent.name == "ES" and nq_path.parent.name == "NQ"
    assert json.loads(es_path.read_text())["trading_authority"] is False
    assert write_futures_canonical_attribution(history, tmp_path / "output",
        market=FuturesCanonicalMarket.ES) == es_path


def test_gate_cannot_be_lowered_to_zero_or_bool(tmp_path):
    for bad in (0, True):
        with pytest.raises(FuturesCanonicalAttributionError, match="must be positive"):
            evaluate_futures_canonical_attribution(tmp_path,
                market=FuturesCanonicalMarket.ES, minimum_finalized_trades=bad)

