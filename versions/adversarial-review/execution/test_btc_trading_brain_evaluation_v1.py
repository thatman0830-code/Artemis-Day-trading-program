from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import json

import pytest
from backtesting.execution_accounting_v2.specifications import InstrumentProfile

from execution.btc_archive_dataset_source_v1 import read_btc_archive_dataset
from execution.btc_trading_brain_evaluation_v1 import (
    BTCTradingBrainEvaluationError, evaluate_btc_trading_brain,
    persist_btc_trading_brain_evaluation,
)
from execution.test_btc_archive_dataset_source_v1 import T, archive


SPEC = "a" * 64


def evaluate(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    archive(tmp_path)
    source = read_btc_archive_dataset(tmp_path, as_of=T)
    return evaluate_btc_trading_brain(source=source, minimum_tick=Decimal("0.1"),
                                      instrument_specification_id=SPEC)


def test_canonical_evaluation_is_deterministic_immutable_and_advisory(tmp_path):
    first = evaluate(tmp_path); second = evaluate(tmp_path)
    assert first == second and first.evaluated_batch_count > 0
    assert sum(dict(first.outcome_counts).values()) == first.evaluated_batch_count
    assert first.advisory_only is True
    assert first.live_trading_permitted is first.trading_authority is False
    assert first.instrument_profile is InstrumentProfile.BTC_LINEAR_PERPETUAL
    assert len(first.report_id) == len(first.run_id) == 64
    with pytest.raises(FrozenInstanceError): first.report_id = "x"
    with pytest.raises(BTCTradingBrainEvaluationError, match="identity"):
        replace(first, report_id="b" * 64)


def test_exact_instrument_inputs_are_mandatory(tmp_path):
    archive(tmp_path); source = read_btc_archive_dataset(tmp_path, as_of=T)
    for tick, specification in ((Decimal("0"), SPEC), (Decimal("NaN"), SPEC),
                                (Decimal("0.1"), "candidate")):
        with pytest.raises(BTCTradingBrainEvaluationError):
            evaluate_btc_trading_brain(source=source, minimum_tick=tick,
                                       instrument_specification_id=specification)


def test_persistence_is_atomic_idempotent_and_conflict_rejecting(tmp_path):
    report = evaluate(tmp_path / "archive")
    target = tmp_path / "evidence" / "evaluation.json"
    assert persist_btc_trading_brain_evaluation(report, target) == target.absolute()
    assert json.loads(target.read_text())["report_id"] == report.report_id
    assert persist_btc_trading_brain_evaluation(report, target) == target.absolute()
    target.write_text("{}")
    with pytest.raises(BTCTradingBrainEvaluationError, match="conflicting"):
        persist_btc_trading_brain_evaluation(report, target)
