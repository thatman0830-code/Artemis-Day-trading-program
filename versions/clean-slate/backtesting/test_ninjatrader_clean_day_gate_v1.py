from datetime import timedelta

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_clean_day_gate_v1 import evaluate_ninjatrader_clean_day_gate
from backtesting.test_ninjatrader_closed_bar_dataset_v1 import NOW, build


def test_clean_gate_collects_then_becomes_ready(tmp_path):
    for market in FuturesCanonicalMarket: build(tmp_path, market)
    collecting = evaluate_ninjatrader_clean_day_gate(
        archive_root=tmp_path, as_of=NOW + timedelta(minutes=4), minimum_bars_per_market=4
    )
    assert collecting.state == "COLLECTING" and collecting.canonical_evaluation_permitted is False
    ready = evaluate_ninjatrader_clean_day_gate(
        archive_root=tmp_path, as_of=NOW + timedelta(minutes=4), minimum_bars_per_market=3
    )
    assert ready.state == "READY" and ready.canonical_evaluation_permitted is True
    assert ready.paper_execution_permitted is ready.trading_authority is False


def test_clean_gate_rejects_gap_or_missing_market(tmp_path):
    build(tmp_path, FuturesCanonicalMarket.ES, gap=True)
    rejected = evaluate_ninjatrader_clean_day_gate(
        archive_root=tmp_path, as_of=NOW + timedelta(minutes=5), minimum_bars_per_market=3
    )
    assert rejected.state == "REJECTED" and rejected.canonical_evaluation_permitted is False


def test_clean_gate_has_no_execution_authority():
    source = __import__("pathlib").Path(__file__).with_name("ninjatrader_clean_day_gate_v1.py").read_text()
    for prohibited in ("SubmitOrder", "CreateOrder", "paper_execution_permitted: bool = True", "trading_authority: bool = True"):
        assert prohibited not in source
