from datetime import datetime, timezone
from pathlib import Path
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_historical_export_v1 import read_ninjatrader_historical_export
from backtesting.ninjatrader_export_canonical_replay_v1 import evaluate_ninjatrader_export


def test_export_replay_is_deterministic_advisory_and_not_equivalence_claim(tmp_path):
    path=tmp_path/"MES.txt"; path.write_text("20260908 140000;7700;7701;7699.75;7700.25;10\n20260908 140100;7700.25;7702;7700;7701;12\n20260908 140200;7701;7702;7700.5;7701.25;8\n",encoding="ascii")
    now=datetime(2026,9,8,15,tzinfo=timezone.utc); evidence=read_ninjatrader_historical_export(path,market=FuturesCanonicalMarket.ES,as_of=now)
    a=evaluate_ninjatrader_export(evidence=evidence,specification_id="a"*64,as_of=now);b=evaluate_ninjatrader_export(evidence=evidence,specification_id="a"*64,as_of=now)
    assert a==b and a.source_bar_count==a.evaluated_batch_count==3
    assert a.cross_source_equivalence_claimed is False and a.paper_execution_permitted is False and a.trading_authority is False
