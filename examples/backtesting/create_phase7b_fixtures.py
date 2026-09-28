"""Generate deterministic local Phase 7B CLI fixtures; never contacts a network."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


UTC = timezone.utc
ROOT = Path(__file__).parent
FIELDS = (
    "symbol", "timeframe", "open_time", "close_time", "open", "high",
    "low", "close", "volume", "is_closed",
)


def stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def candle(start: datetime, minutes: int, timeframe: str,
           o: str, h: str, l: str, c: str) -> dict[str, str]:
    opened = start + timedelta(minutes=minutes)
    duration = 1 if timeframe == "1m" else 5
    return {
        "symbol": "BTC", "timeframe": timeframe,
        "open_time": stamp(opened),
        "close_time": stamp(opened + timedelta(minutes=duration)),
        "open": o, "high": h, "low": l, "close": c,
        "volume": "1", "is_closed": "true",
    }


def rows_1m(start: datetime, scored_minutes: int) -> list[dict[str, str]]:
    rows = [candle(start, i, "1m", "100", "101", "99", "100") for i in range(1440)]
    overrides = {
        101: ("105", "110", "104", "106"),
        102: ("110", "120", "109", "110"),
        103: ("106", "110", "104", "105"),
        198: ("100", "101", "98", "99"),
        199: ("98", "99", "95", "97"),
        200: ("92", "94", "90", "92"),
        201: ("97", "99", "95", "98"),
        202: ("100", "101", "98", "100"),
    }
    for index, values in overrides.items():
        rows[index] = candle(start, index, "1m", *values)
    day2 = start + timedelta(days=1)
    for index in range(scored_minutes):
        rows.append(candle(day2, index, "1m", "105", "106", "103", "104"))
    rows[1440 + 20] = candle(day2, 20, "1m", "104", "105", "88", "89")
    return rows


def rows_5m(start: datetime, scored_bars: int) -> list[dict[str, str]]:
    rows = [candle(start, i * 5, "5m", "100", "102", "99", "101") for i in range(288)]
    overrides = {
        269: ("104", "105", "99", "103"),
        270: ("105", "110", "100", "106"),
        271: ("104", "105", "99", "103"),
        275: ("97", "101", "95", "98"),
        276: ("92", "99", "90", "93"),
        277: ("97", "101", "95", "98"),
    }
    for index, values in overrides.items():
        rows[index] = candle(start, index * 5, "5m", *values)
    day2 = start + timedelta(days=1)
    for index in range(scored_bars):
        rows.append(candle(day2, index * 5, "5m", "100", "102", "99", "101"))
    if scored_bars > 25:
        rows[288 + 23] = candle(day2, 23 * 5, "5m", "95", "96", "94", "96")
        rows[288 + 24] = candle(day2, 24 * 5, "5m", "96", "98", "95", "97")
        rows[288 + 25] = candle(day2, 25 * 5, "5m", "98", "113", "98", "112")
    if scored_bars > 26:
        rows[288 + 26] = candle(day2, 26 * 5, "5m", "108", "113", "97", "108")
    if scored_bars > 27:
        rows[288 + 27] = candle(day2, 27 * 5, "5m", "120", "121", "100", "120")
    return rows


def write_fixture(name: str, *, trade: bool) -> None:
    directory = ROOT / name
    directory.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 1, 5, tzinfo=UTC)
    scored_bars = 29 if trade else 6
    scored_minutes = scored_bars * 5
    files = []
    for timeframe, rows in (
        ("1m", rows_1m(start, scored_minutes)),
        ("5m", rows_5m(start, scored_bars)),
    ):
        path = directory / f"candles_{timeframe}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader(); writer.writerows(rows)
        files.append({"timeframe": timeframe, "path": path.name})
    day2 = start + timedelta(days=1)
    end = day2 + timedelta(minutes=scored_minutes, microseconds=1)
    manifest = {
        "schema_version": "backtesting-data-manifest-v1",
        "dataset_id": f"phase7b-{name}-v1",
        "candle_schema_version": "historical-candle-v1",
        "source": "synthetic-local-fixture", "exchange": "none",
        "gap_policy": "REJECT", "validation_time": stamp(end + timedelta(days=1)),
        "files": files,
    }
    config = {
        "schema_version": "backtesting-config-v1",
        "strategy_configuration_version": "phase7b-continuation-v1",
        "model_configuration_version": "phase7b-model-v1",
        "setup_request_mode": "CANONICAL_TRADING_BRAIN",
        "canonical_timeframe_roles": {"execution": "1m", "structure": "5m"},
        "warmup_start_inclusive": stamp(start),
        "mechanical_swing": {"left_bars": 2, "right_bars": 2},
        "displacement_policy_id": "OWNER_MECHANICAL_V1",
        "prior_period_policy_id": "OWNER_PRIOR_PERIOD_V1",
        "risk_reward_policy_id": "OWNER_MIN_RR_V1",
        "performance_objective_id": "OWNER_WIN_RATE_OBJECTIVE_V1",
        "enabled_prior_period_reference_types": ["PDH", "PDL"],
        "simulation_only": True,
        "replay_start_inclusive": stamp(day2),
        "replay_end_exclusive": stamp(end),
        "starting_equity": "10000", "risk_percent": "1",
        "minimum_tick": "0.25", "tick_value": "1",
        "contract_multiplier": "1", "minimum_quantity": "0.01",
        "quantity_increment": "0.01", "maximum_quantity": "1000",
        "input_version": "phase7b-input-v1",
        "calculation_version": "phase7b-calculation-v1",
        "historical_version": "phase7b-history-v1",
        "account_timezone": "UTC", "random_seed": 0,
        "costs": {
            "id": "phase7b-zero-cost-v1", "commission_model": "ZERO",
            "commission_rate": "0", "transaction_fee_model": "ZERO",
            "transaction_fee_rate": "0", "spread_model": "NONE",
            "spread_value": "0", "slippage_model": "NONE",
            "slippage_value": "0",
        },
    }
    for filename, value in (("dataset_manifest.json", manifest),
                            ("backtest_config.json", config)):
        (directory / filename).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )


if __name__ == "__main__":
    write_fixture("canonical_zero", trade=False)
    write_fixture("canonical_trade", trade=True)
