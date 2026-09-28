"""Compare three advisory book-derived feature lanes on verified archives."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.day_of_week_feature_research_v1 import extract_day_of_week_features
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.gap_feature_research_v1 import extract_gap_session_features
from backtesting.moving_average_channel_research_v1 import extract_moving_average_channel_features
from backtesting.ninjatrader_closed_bar_dataset_v1 import read_closed_bar_dataset


def _verified_day(root: Path, market: FuturesCanonicalMarket, day: str):
    source = root / market.value / f"{day}.jsonl"
    lines = source.read_bytes().splitlines()
    last = json.loads(lines[-1])
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / market.value
        target.mkdir()
        shutil.copyfile(source, target / source.name)
        manifest = {
            "archive_file": source.name,
            "head_record_sha256": last["record_sha256"],
            "instrument": last["instrument"],
            "last_close_time_utc": last["close_time_utc"],
            "market": market.value,
            "record_count": len(lines),
            "schema_version": last["schema_version"],
            "state": "RECORDING",
            "trading_authority": False,
            "unresolved_gap_count": 0,
        }
        (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return read_closed_bar_dataset(
            temporary, market=market, day=day, as_of=datetime.now(timezone.utc)
        ).dataset.candles


def compare(root: Path, days: tuple[str, ...]) -> dict:
    markets = {}
    for market in FuturesCanonicalMarket:
        by_day = {}
        rejected = {}
        for day in days:
            try:
                by_day[day] = _verified_day(root, market, day)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                rejected[day] = type(error).__name__ + ": " + str(error)
        if rejected:
            markets[market.value] = {
                "state": "BLOCKED_SOURCE_INELIGIBLE",
                "rejected_days": rejected,
                "verified_source_bars": sum(len(items) for items in by_day.values()),
            }
            continue
        combined = tuple(item for day in days for item in by_day[day])
        gaps = extract_gap_session_features(combined, market=market)
        calendar = extract_day_of_week_features(combined, market=market)
        channels = tuple(item for day in days for item in
                         extract_moving_average_channel_features(by_day[day], market=market))
        markets[market.value] = {
            "state": "COMPLETE",
            "verified_source_bars": len(combined),
            "gap_sessions": len(gaps),
            "gap_triggered": sum(item.triggered is True for item in gaps),
            "channel_observations": len(channels),
            "channel_candidates": sum(item.candidate_setup for item in channels),
            "calendar_sessions": len(calendar),
            "calendar_observations": sum(item.calendar_setup.value.endswith("OBSERVATION") for item in calendar),
        }
    complete = all(item["state"] == "COMPLETE" for item in markets.values())
    return {
        "schema_version": "book-research-lane-comparison-v1",
        "state": "COMPLETE" if complete else "BLOCKED_SOURCE_INELIGIBLE",
        "days": list(days),
        "markets": markets,
        "advisory_only": True,
        "paper_execution_permitted": False,
        "live_trading_permitted": False,
        "trading_authority": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--days", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.archive_root, tuple(args.days))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
