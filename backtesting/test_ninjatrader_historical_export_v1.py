from datetime import datetime, timezone
from pathlib import Path
import pytest

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_historical_export_v1 import read_ninjatrader_historical_export

NOW = datetime(2026, 9, 8, 15, tzinfo=timezone.utc)


def test_accepts_strict_continuous_utc_minute_export(tmp_path):
    path = tmp_path / "MES 09-26.Last.txt"
    path.write_text("20260908 140000;7700;7701;7699.75;7700.25;10\n20260908 140100;7700.25;7702;7700;7701;12\n", encoding="ascii")
    result = read_ninjatrader_historical_export(path, market=FuturesCanonicalMarket.ES, as_of=NOW)
    assert result.record_count == 2 and result.historical_replay_eligible is True
    assert result.immutable_archive_repair_eligible is False and result.trading_authority is False


@pytest.mark.parametrize("rows", [
    "20260908 140000;7700;7701;7699.75;7700.1;10\n",
    "20260908 140000;7700;7701;7699.75;7700.25;-1\n",
    "20260908 140000;7700;7701;7699.75;7700.25;10\n20260908 140200;7700;7701;7699.75;7700.25;10\n",
])
def test_rejects_off_tick_negative_volume_and_gaps(tmp_path, rows):
    path = tmp_path / "bad.txt"; path.write_text(rows, encoding="ascii")
    with pytest.raises(ValueError):
        read_ninjatrader_historical_export(path, market=FuturesCanonicalMarket.ES, as_of=NOW)
