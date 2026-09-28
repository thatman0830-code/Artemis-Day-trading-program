from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_4_profit_factor import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope(**changes):
    return replace(TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def trade(suffix, closed, net_pnl, result=TradeResult.WIN):
    return replace(accounting(result, suffix, closed), net_pnl=Decimal(net_pnl))


def test_finite_profit_factor_and_intermediate_components():
    items = (trade("w1", 26, "1000"), trade("l", 27, "-1000", TradeResult.LOSS), trade("w2", 28, "500"), trade("be", 29, "0", TradeResult.BREAKEVEN))
    snapshot = ProfitFactorEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.trade_count == 4
    assert (snapshot.total_winning_net_pnl, snapshot.summed_negative_net_pnl, snapshot.gross_loss) == (Decimal("1500"), Decimal("-1000"), Decimal("1000"))
    assert snapshot.profit_factor == Decimal("1.5")


def test_no_losses_with_profit_is_positive_infinity():
    snapshot = ProfitFactorEngine().calculate(scope=scope(), trades=(trade("w", 26, "5"), trade("be", 27, "0", TradeResult.BREAKEVEN)), as_of_time=30).snapshot
    assert snapshot.gross_loss == 0 and snapshot.profit_factor == Decimal("Infinity")


@pytest.mark.parametrize("items", [(), (trade("be", 26, "0", TradeResult.BREAKEVEN),)])
def test_no_profit_and_no_loss_is_null(items):
    snapshot = ProfitFactorEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.total_winning_net_pnl == snapshot.gross_loss == 0
    assert snapshot.profit_factor is None


def test_losses_without_profit_produce_exact_zero():
    snapshot = ProfitFactorEngine().calculate(scope=scope(), trades=(trade("loss", 26, "-4", TradeResult.LOSS),), as_of_time=30).snapshot
    assert snapshot.gross_loss == 4 and snapshot.profit_factor == 0


def test_exact_decimal_ratio_uses_canonical_precision():
    snapshot = ProfitFactorEngine().calculate(scope=scope(), trades=(trade("w", 26, "1"), trade("l", 27, "-3", TradeResult.LOSS)), as_of_time=30).snapshot
    assert snapshot.profit_factor == Decimal("0.3333333333333333333333333333")


def test_point_in_time_exclusion_and_ordering():
    items = (trade("b", 27, "2"), trade("future", 31, "100"), trade("a", 27, "1"), trade("z", 26, "-1", TradeResult.LOSS))
    snapshot = ProfitFactorEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.source_trade_ids == ("trade-z", "trade-a", "trade-b")
    assert snapshot.future_excluded_trade_ids == ("trade-future",)
    assert snapshot.profit_factor == 3


def test_formula_uses_net_pnl_sign_without_reclassifying_result():
    positive_labeled_loss = trade("odd", 26, "6", TradeResult.LOSS)
    snapshot = ProfitFactorEngine().calculate(scope=scope(), trades=(positive_labeled_loss,), as_of_time=30).snapshot
    assert snapshot.total_winning_net_pnl == 6 and snapshot.profit_factor == Decimal("Infinity")
    assert positive_labeled_loss.trade_result == TradeResult.LOSS


@pytest.mark.parametrize("field", ["scope", "trades"])
def test_missing_inputs_fail_closed(field):
    values = {"scope": scope(), "trades": ()}; values[field] = None
    assert ProfitFactorEngine().calculate(**values, as_of_time=30).error.reason == "REQUIRED_PROFIT_FACTOR_INPUT_MISSING"


@pytest.mark.parametrize("change,reason", [
    ({"strategy_id": "other"}, "PROFIT_FACTOR_SCOPE_IDENTITY_MISMATCH"),
    ({"symbol": "ETH"}, "PROFIT_FACTOR_SCOPE_IDENTITY_MISMATCH"),
    ({"timeframe": "5m"}, "PROFIT_FACTOR_TIMEFRAME_MISMATCH"),
    ({"model": SetupModel.REVERSAL_1}, "PROFIT_FACTOR_MODEL_OR_DIRECTION_MISMATCH"),
    ({"direction": StructuralRegime.BEARISH}, "PROFIT_FACTOR_MODEL_OR_DIRECTION_MISMATCH"),
    ({"input_version": "v2"}, "PROFIT_FACTOR_INPUT_VERSION_MISMATCH"),
])
def test_scope_and_version_separation(change, reason):
    item = replace(trade("one", 26, "1"), **change)
    assert ProfitFactorEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).error.reason == reason


def test_duplicate_keys_have_absolute_data_integrity_precedence():
    item = trade("same", 26, "1")
    result = ProfitFactorEngine().calculate(scope=scope(), trades=(item, replace(item, id="other", immutable=False)), as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_nonfinal_nonfinite_and_invalid_chronology_fail_closed():
    engine = ProfitFactorEngine(); item = trade("one", 26, "1")
    assert engine.calculate(scope=scope(), trades=(replace(item, immutable=False),), as_of_time=30).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(), trades=(replace(item, net_pnl=Decimal("NaN")),), as_of_time=30).error.reason == "NON_FINITE_PROFIT_FACTOR_INPUT"
    assert engine.calculate(scope=scope(), trades=(replace(item, opened_time=27),), as_of_time=30).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"


def test_idempotent_replay_and_conflicting_snapshot_prevention():
    engine = ProfitFactorEngine(); item = trade("one", 26, "1")
    first = engine.calculate(scope=scope(), trades=(item,), as_of_time=30)
    replay = engine.calculate(scope=scope(), trades=(item,), as_of_time=30, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = engine.calculate(scope=scope(), trades=(item, trade("two", 27, "2")), as_of_time=30, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_snapshot_is_immutable_and_source_unchanged():
    item = trade("one", 26, "1"); original = item
    snapshot = ProfitFactorEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert item == original
    with pytest.raises(FrozenInstanceError):
        snapshot.profit_factor = Decimal("9")
