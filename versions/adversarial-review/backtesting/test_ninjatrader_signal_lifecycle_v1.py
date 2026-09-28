from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket as M
from backtesting.ninjatrader_canonical_smoke_v1 import evaluate_ninjatrader_canonical_smoke
from backtesting.ninjatrader_closed_bar_dataset_v1 import read_closed_bar_dataset
from backtesting.ninjatrader_signal_lifecycle_v1 import *
from backtesting.test_ninjatrader_closed_bar_dataset_v1 import NOW,build
def base(tmp_path):
 build(tmp_path,M.ES);e=read_closed_bar_dataset(tmp_path,market=M.ES,day="2026-09-08",as_of=NOW+timedelta(minutes=4));return evaluate_ninjatrader_canonical_smoke(evidence=e,minimum_tick=Decimal(".25"),instrument_specification_id="a"*64,as_of=NOW+timedelta(minutes=4)),e.dataset.candles
def armed(report,**changes):
 values=dict(qualified_signal_id="f"*64,signal_side="LONG",signal_time=NOW,entry_price=Decimal("101"),stop_price=Decimal("99"),target_price=Decimal("102"));values.update(changes);return replace(report,**values)
def test_no_signal_and_waiting_entry_are_nontrades(tmp_path):
 report,bars=base(tmp_path);assert resolve_signal_lifecycle(report=report,bars=bars).outcome is LifecycleOutcome.NO_SIGNAL
 waiting=resolve_signal_lifecycle(report=armed(report,entry_price=Decimal("200")),bars=bars);assert waiting.outcome is LifecycleOutcome.WAITING_ENTRY and waiting.completed_trade is None
def test_target_completion_emits_one_exact_shadow_trade(tmp_path):
 report,bars=base(tmp_path);result=resolve_signal_lifecycle(report=armed(report),bars=bars);assert result.outcome is LifecycleOutcome.TARGET and result.completed_trade.exit_price==Decimal("102");assert result.paper_execution_permitted is result.trading_authority is False
def test_same_bar_stop_and_target_resolves_stop_first(tmp_path):
 report,bars=base(tmp_path);result=resolve_signal_lifecycle(report=armed(report,stop_price=Decimal("100")),bars=bars);assert result.outcome is LifecycleOutcome.STOP and result.ambiguous_bar_resolved_stop_first and result.completed_trade.exit_price==Decimal("100")
def test_incomplete_signal_fails_closed(tmp_path):
 report,bars=base(tmp_path)
 import pytest
 with pytest.raises(ValueError,match="complete"):resolve_signal_lifecycle(report=replace(report,qualified_signal_id="f"*64),bars=bars)
def test_no_execution_surface():
 source=__import__('pathlib').Path(__file__).with_name('ninjatrader_signal_lifecycle_v1.py').read_text();assert'from execution'not in source
 for text in('SubmitOrder','CreateOrder','trading_authority:bool=True'):assert text not in source
