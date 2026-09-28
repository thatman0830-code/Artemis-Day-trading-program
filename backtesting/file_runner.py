from __future__ import annotations

import csv
import json
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import asdict, fields, is_dataclass, replace
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backtesting.analytics import AnalyticsConfiguration, CanonicalAnalyticsOrchestrator
from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.market_data import GapPolicy, normalize_historical_candle, validate_dataset
from backtesting.orchestrator import TradingBrainEvaluationOrchestrator
from backtesting.replay import DeterministicReplay
from backtesting.simulation import (
    HistoricalTradeSimulator, SimulationAccountInput, SimulationInstrumentInput,
    TradeSimulationConfiguration,
)
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_1_entry_execution import ExecutionMode
from strategy.trading_brain.p29_5_execution_costs import (
    CommissionModel, ExecutionCostSpecification, SlippageModel,
)
from strategy.trading_brain.p23_prior_period_references import POLICY_ID as PRIOR_PERIOD_POLICY_ID
from strategy.trading_brain.owner_policies import (
    LEGACY_MIN_RR_POLICY_ID, OWNER_MIN_RR_POLICY_ID,
    OWNER_WIN_RATE_OBJECTIVE_ID, minimum_rr_policy,
)


DATA_MANIFEST_SCHEMA = "backtesting-data-manifest-v1"
CONFIG_SCHEMA = "backtesting-config-v1"
EXPORT_SCHEMA = "backtesting-result-export-v1"
SETUP_REQUEST_MODES = {"NONE", "CANONICAL_TRADING_BRAIN"}
SECRET_FRAGMENTS = ("private" + "_key", "private" + "key", "seed_phrase", "mnemonic", "wallet",
                    "api_secret", "secret_key", "sign" + "ing", "credential")


def _strict(value: dict, expected: set[str], label: str) -> None:
    unknown, missing = set(value) - expected, expected - set(value)
    if unknown or missing:
        raise ValueError(f"{label} fields invalid; missing={sorted(missing)}, unknown={sorted(unknown)}")


def _utc(text: object, field: str) -> datetime:
    if not isinstance(text, str) or not text.endswith("Z"):
        raise ValueError(f"{field} must be ISO 8601 UTC with Z")
    try:
        value = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field} is malformed") from error
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{field} must be UTC")
    return value


def _decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an exact decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field} is malformed") from error
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def _require_prior_period_warmup(dataset, *, replay_start: datetime,
                                 account_timezone: str,
                                 enabled: set[str]) -> None:
    zone = ZoneInfo(account_timezone)
    local_day = replay_start.astimezone(zone).date()
    periods = []
    if enabled & {"PDH", "PDL"}:
        end = datetime.combine(local_day, time.min, tzinfo=zone)
        periods.append(("prior day", end - timedelta(days=1), end))
    if enabled & {"PWH", "PWL"}:
        current_week = local_day - timedelta(days=local_day.weekday())
        end = datetime.combine(current_week, time.min, tzinfo=zone)
        periods.append(("prior week", end - timedelta(days=7), end))
    minute_candles = tuple(
        item for item in dataset.candles if item.timeframe.value == "1m"
    )
    for label, local_start, local_end in periods:
        start, end = local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)
        selected = tuple(item for item in minute_candles
                         if start <= item.open_time and item.close_time <= end)
        expected = int((end - start).total_seconds() // 60)
        complete = bool(
            len(selected) == expected and selected
            and selected[0].open_time == start and selected[-1].close_time == end
            and all(selected[index].close_time == selected[index + 1].open_time
                    for index in range(len(selected) - 1))
        )
        if not complete:
            raise ValueError(f"canonical {label} warm-up is incomplete")


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_float=lambda _: (_ for _ in ()).throw(ValueError("JSON floats are forbidden; use decimal strings")))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain one object")
    def scan(item, trail=""):
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = str(key).lower().replace("-", "_")
                if any(fragment in normalized for fragment in SECRET_FRAGMENTS):
                    raise ValueError(f"secret-like configuration field is forbidden: {trail}{key}")
                scan(child, trail + str(key) + ".")
        elif isinstance(item, list):
            for child in item: scan(child, trail)
    scan(value)
    return value


def load_inputs(data_path: str | Path, config_path: str | Path):
    manifest_path, configuration_path = Path(data_path).resolve(), Path(config_path).resolve()
    raw_manifest, config = _load_json(manifest_path), _load_json(configuration_path)
    required_manifest = {"schema_version", "dataset_id", "candle_schema_version", "source",
        "exchange", "gap_policy", "validation_time", "files"}
    optional_manifest = {"data_network", "requested_start", "requested_end", "gaps",
                         "approved_exclusions", "checksums", "dataset_fingerprint"}
    unknown, missing = set(raw_manifest) - required_manifest - optional_manifest, required_manifest - set(raw_manifest)
    if unknown or missing:
        raise ValueError(f"data manifest fields invalid; missing={sorted(missing)}, unknown={sorted(unknown)}")
    if raw_manifest["schema_version"] != DATA_MANIFEST_SCHEMA:
        raise ValueError("unsupported data manifest schema version")
    if not isinstance(raw_manifest["files"], list) or not raw_manifest["files"]:
        raise ValueError("data manifest files must be a nonempty list")
    candles = []
    seen_files = set()
    expected_csv = {"symbol", "timeframe", "open_time", "close_time", "open", "high", "low", "close", "volume", "is_closed"}
    for entry in raw_manifest["files"]:
        if not isinstance(entry, dict): raise ValueError("file mapping must be an object")
        _strict(entry, {"timeframe", "path"}, "file mapping")
        if entry["timeframe"] in seen_files: raise ValueError("duplicate timeframe file mapping")
        seen_files.add(entry["timeframe"])
        csv_path = (manifest_path.parent / str(entry["path"])).resolve()
        if not csv_path.is_file(): raise ValueError(f"missing timeframe file: {entry['path']}")
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if set(reader.fieldnames or ()) != expected_csv:
                raise ValueError("CSV fields are incomplete or unknown")
            for row in reader:
                if row["timeframe"] != entry["timeframe"]:
                    raise ValueError("CSV timeframe does not match manifest mapping")
                if row["is_closed"] not in ("true", "false"):
                    raise ValueError("is_closed must be lowercase true or false")
                candles.append(normalize_historical_candle({
                    "symbol": row["symbol"], "timeframe": row["timeframe"],
                    "open_time": _utc(row["open_time"], "open_time"),
                    "close_time": _utc(row["close_time"], "close_time"),
                    "open": _decimal(row["open"], "open"), "high": _decimal(row["high"], "high"),
                    "low": _decimal(row["low"], "low"), "close": _decimal(row["close"], "close"),
                    "volume": _decimal(row["volume"], "volume") if row["volume"] else None,
                    "is_closed": row["is_closed"] == "true",
                }, dataset_id=raw_manifest["dataset_id"], schema_version=raw_manifest["candle_schema_version"],
                   source=raw_manifest["source"], exchange=raw_manifest["exchange"]))
    ordered = tuple(sorted(candles, key=lambda c: (c.open_time, c.symbol, c.timeframe.value, c.id)))
    dataset = validate_dataset(ordered, dataset_id=raw_manifest["dataset_id"],
        schema_version=raw_manifest["candle_schema_version"], source=raw_manifest["source"],
        exchange=raw_manifest["exchange"], gap_policy=GapPolicy(raw_manifest["gap_policy"]),
        validation_time=_utc(raw_manifest["validation_time"], "validation_time"))
    expected_config = {"schema_version", "strategy_configuration_version", "model_configuration_version",
        "setup_request_mode", "replay_start_inclusive", "replay_end_exclusive", "starting_equity",
        "risk_percent", "minimum_tick", "tick_value", "contract_multiplier", "minimum_quantity",
        "quantity_increment", "maximum_quantity", "input_version", "calculation_version",
        "historical_version", "account_timezone", "random_seed", "costs"}
    optional_config = {
        "prior_period_policy_id", "canonical_timeframe_roles",
        "warmup_start_inclusive", "mechanical_swing",
        "displacement_policy_id", "enabled_prior_period_reference_types",
        "simulation_only",
        "risk_reward_policy_id", "performance_objective_id",
    }
    unknown, missing = set(config) - expected_config - optional_config, expected_config - set(config)
    if unknown or missing:
        raise ValueError(f"configuration fields invalid; missing={sorted(missing)}, unknown={sorted(unknown)}")
    if config["schema_version"] != CONFIG_SCHEMA: raise ValueError("unsupported configuration schema version")
    mode = config["setup_request_mode"]
    if mode not in SETUP_REQUEST_MODES:
        raise ValueError("unknown setup_request_mode")
    try:
        ZoneInfo(config["account_timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise ValueError("AccountTimezone must be a valid IANA timezone") from error
    if config.get("prior_period_policy_id", PRIOR_PERIOD_POLICY_ID) != PRIOR_PERIOD_POLICY_ID:
        raise ValueError("unknown prior-period policy identity")
    minimum_rr_policy(config.get("risk_reward_policy_id", LEGACY_MIN_RR_POLICY_ID))
    if config.get("performance_objective_id", "NONE") not in {"NONE", OWNER_WIN_RATE_OBJECTIVE_ID}:
        raise ValueError("unknown performance objective identity")
    if mode == "CANONICAL_TRADING_BRAIN":
        canonical_fields = {
            "canonical_timeframe_roles", "warmup_start_inclusive",
            "mechanical_swing", "displacement_policy_id",
            "prior_period_policy_id", "enabled_prior_period_reference_types",
            "simulation_only",
        }
        missing_canonical = canonical_fields - set(config)
        if missing_canonical:
            raise ValueError(
                f"canonical mode fields missing: {sorted(missing_canonical)}"
            )
        if config["simulation_only"] is not True:
            raise ValueError("canonical mode is simulation-only")
        roles = config["canonical_timeframe_roles"]
        _strict(roles, {"execution", "structure"}, "canonical timeframe roles")
        if roles != {"execution": "1m", "structure": "5m"}:
            raise ValueError("canonical mode requires execution=1m and structure=5m")
        streams = {item.timeframe.value for item in dataset.candles}
        if not set(roles.values()) <= streams:
            raise ValueError("canonical mode required timeframe stream is missing")
        swing = config["mechanical_swing"]
        _strict(swing, {"left_bars", "right_bars"}, "mechanical swing")
        if swing != {"left_bars": 2, "right_bars": 2}:
            raise ValueError("canonical #19 requires strict 2-left/2-right swings")
        if config["displacement_policy_id"] != "OWNER_MECHANICAL_V1":
            raise ValueError("unknown displacement policy identity")
        enabled = config["enabled_prior_period_reference_types"]
        if (not isinstance(enabled, list) or not enabled
                or len(enabled) != len(set(enabled))
                or not set(enabled) <= {"PDH", "PDL", "PWH", "PWL"}):
            raise ValueError("enabled prior-period reference types are invalid")
        warmup = _utc(config["warmup_start_inclusive"], "warmup_start_inclusive")
        replay_start = _utc(config["replay_start_inclusive"], "replay_start_inclusive")
        if warmup >= replay_start:
            raise ValueError("canonical warm-up must begin before scored replay")
        available_starts = {
            timeframe: min(c.open_time for c in dataset.candles if c.timeframe.value == timeframe)
            for timeframe in set(roles.values())
        }
        if any(available_starts[timeframe] > warmup for timeframe in available_starts):
            raise ValueError("canonical warm-up does not cover every required stream")
        _require_prior_period_warmup(
            dataset, replay_start=replay_start,
            account_timezone=config["account_timezone"], enabled=set(enabled),
        )
    if isinstance(config["random_seed"], bool) or not isinstance(config["random_seed"], int):
        raise ValueError("random_seed must be an integer")
    costs = config["costs"]
    _strict(costs, {"id", "commission_model", "commission_rate", "transaction_fee_model",
        "transaction_fee_rate", "spread_model", "spread_value", "slippage_model", "slippage_value"}, "costs")
    return dataset, raw_manifest, config


def build_pipeline(dataset, raw_manifest, config):
    dataset_manifest = DatasetManifest.from_dataset(dataset, symbol=dataset.symbol,
        created_at=_utc(raw_manifest["validation_time"], "validation_time"), configuration_id=config["input_version"])
    run = BacktestRunManifest.create(dataset=dataset_manifest,
        trading_brain_contract_version=INTERFACE_CONTRACT_VERSION,
        strategy_configuration_version=config["strategy_configuration_version"],
        model_configuration_version=config["model_configuration_version"],
        replay_start_inclusive=_utc(config["replay_start_inclusive"], "replay_start_inclusive"),
        replay_end_exclusive=_utc(config["replay_end_exclusive"], "replay_end_exclusive"),
        starting_equity=_decimal(config["starting_equity"], "starting_equity"),
        execution_cost_configuration_id=config["costs"]["id"], random_seed=config["random_seed"],
        runtime=RuntimeFacts(f"{sys.version_info.major}.{sys.version_info.minor}", platform.python_implementation(),
                             platform.system(), "backtesting-phase6-v1"),
        risk_reward_policy_id=config.get("risk_reward_policy_id", LEGACY_MIN_RR_POLICY_ID),
        performance_objective_id=config.get("performance_objective_id", "NONE"))
    tick = _decimal(config["minimum_tick"], "minimum_tick"); version = config["input_version"]
    account = SimulationAccountInput("file-account", "simulated-account", run.starting_equity,
                                     _decimal(config["risk_percent"], "risk_percent"), version)
    instrument = SimulationInstrumentInput("file-instrument", run.symbol, tick,
        _decimal(config["tick_value"], "tick_value"), _decimal(config["contract_multiplier"], "contract_multiplier"),
        _decimal(config["minimum_quantity"], "minimum_quantity"), _decimal(config["quantity_increment"], "quantity_increment"),
        _decimal(config["maximum_quantity"], "maximum_quantity") if config["maximum_quantity"] is not None else None, version)
    raw_cost = config["costs"]
    cost = ExecutionCostSpecification(raw_cost["id"], run.symbol, version,
        int(run.replay_start_inclusive.timestamp() * 1000), tick, instrument.contract_multiplier,
        CommissionModel(raw_cost["commission_model"]), _decimal(raw_cost["commission_rate"], "commission_rate"),
        CommissionModel(raw_cost["transaction_fee_model"]), _decimal(raw_cost["transaction_fee_rate"], "transaction_fee_rate"),
        SlippageModel(raw_cost["spread_model"]), _decimal(raw_cost["spread_value"], "spread_value"),
        SlippageModel(raw_cost["slippage_model"]), _decimal(raw_cost["slippage_value"], "slippage_value"))
    sim_config = TradeSimulationConfiguration("file-simulation", account, instrument, cost,
                                               config["calculation_version"], ExecutionMode.PAPER)
    return dataset_manifest, run, sim_config


def execute(dataset, raw_manifest, config):
    dataset_manifest, run, sim_config = build_pipeline(dataset, raw_manifest, config)
    replay = DeterministicReplay(dataset=dataset, run=run)
    strategy = TradingBrainEvaluationOrchestrator(dataset=dataset, run=run,
        minimum_tick=sim_config.instrument.minimum_tick, calculation_version=config["calculation_version"],
        account_timezone=config["account_timezone"],
        prior_period_policy_id=config.get("prior_period_policy_id", PRIOR_PERIOD_POLICY_ID),
        risk_reward_policy=minimum_rr_policy(config.get("risk_reward_policy_id", LEGACY_MIN_RR_POLICY_ID)),
        canonical_mode=config["setup_request_mode"] == "CANONICAL_TRADING_BRAIN",
        enabled_prior_period_reference_types=tuple(
            config.get("enabled_prior_period_reference_types", ("PDH", "PDL", "PWH", "PWL"))
        ))
    simulator = HistoricalTradeSimulator(run=run, configuration=sim_config)
    strategy_state, simulation_state = strategy.initial_state(), simulator.initial_state()
    for publication in replay:
        evaluated = strategy.evaluate(publication=publication, state=strategy_state, request=None)
        strategy_state = evaluated.state
        simulation_state = simulator.evaluate(publication=publication, evaluation=evaluated.result,
                                               state=simulation_state).state
    analytics = CanonicalAnalyticsOrchestrator(run=run, configuration=AnalyticsConfiguration(
        "file-analytics", run.strategy_configuration_version,
        (config.get("canonical_timeframe_roles", {}).get("structure")
         or run.timeframes[0].value),
        SetupModel.CONTINUATION, StructuralRegime.BULLISH, config["input_version"],
        config["input_version"], config["calculation_version"], config["historical_version"],
        config["account_timezone"], True,
        config.get("performance_objective_id", "NONE")))
    # Analytics receives only finalized lifecycle projections; unresolved
    # orders/positions remain in the returned simulation state and export.
    analytics_state = replace(
        simulation_state,
        trades=tuple(item for item in simulation_state.trades
                     if item.accounting is not None),
    )
    result = analytics.calculate(state=analytics_state, as_of=run.replay_end_exclusive)
    return dataset_manifest, run, simulation_state, result


def _value(value):
    if isinstance(value, Decimal):
        if value.is_infinite(): return {"status": "POSITIVE_INFINITY" if value > 0 else "NEGATIVE_INFINITY"}
        if value.is_nan(): return {"status": "UNDEFINED"}
        return format(value, "f")
    if isinstance(value, datetime): return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum): return value.value
    if is_dataclass(value): return {field.name: _value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple): return [_value(item) for item in value]
    if isinstance(value, dict): return {str(key): _value(value[key]) for key in sorted(value)}
    return value


def _json_bytes(value) -> bytes:
    return (json.dumps(_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def export(output: str | Path, *, dataset_manifest, run, state, result, overwrite=False):
    target = Path(output).resolve()
    if target.exists() and not overwrite: raise FileExistsError("output directory already exists; use --overwrite")
    parent = target.parent; parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=target.name + ".tmp-", dir=parent))
    try:
        artifacts = {
            "dataset_manifest.json": _json_bytes({"export_schema": EXPORT_SCHEMA, "manifest": dataset_manifest}),
            "run_manifest.json": _json_bytes({"export_schema": EXPORT_SCHEMA, "manifest": run}),
            "result.json": _json_bytes({"export_schema": EXPORT_SCHEMA, "result": result}),
        }
        trade_header = ("trade_id","accounting_id","closed_time","result","gross_pnl","net_pnl","gross_r","net_r","pre_trade_equity","post_trade_equity")
        trade_lines = [",".join(trade_header)]
        for row in sorted(state.accounting_history.records, key=lambda x: (x.closed_time, x.trade_id)):
            trade_lines.append(",".join((row.trade_id,row.id,str(row.closed_time),row.trade_result.value,
                format(row.gross_pnl,"f"),format(row.net_pnl,"f"),format(row.gross_r,"f"),format(row.net_r,"f"),
                format(row.pre_trade_equity,"f"),format(row.post_trade_equity,"f"))))
        artifacts["trades.csv"] = ("\n".join(trade_lines) + "\n").encode()
        equity_lines = ["sequence,snapshot_id,previous_snapshot_id,trade_accounting_id,effective_time,equity_change,equity"]
        for row in state.equity_ledger.snapshots:
            equity_lines.append(",".join((str(row.sequence),row.id,row.previous_snapshot_id or "",row.trade_accounting_id or "",
                str(row.effective_time),format(row.equity_change,"f"),format(row.equity,"f"))))
        artifacts["equity.csv"] = ("\n".join(equity_lines) + "\n").encode()
        outcome_counts = {
            value: state.setup_outcomes.count(value)
            for value in sorted(set(state.setup_outcomes))
        }
        orders = len(state.trades)
        fills = sum(item.fill is not None for item in state.trades)
        closures = sum(item.exit is not None for item in state.trades)
        pending = sum(item.fill is None and item.exit is None for item in state.trades)
        open_positions = sum(
            item.position is not None and item.exit is None for item in state.trades
        )
        objective_reference = next((item for item in result.analytics
            if item.owner == run.performance_objective_id), None)
        objective_outcome = (getattr(objective_reference.record, "outcome", "NOT_REQUESTED")
                             if objective_reference is not None else "NOT_REQUESTED")
        objective_outcome = getattr(objective_outcome, "value", objective_outcome)
        artifacts["summary.txt"] = (
            f"HISTORICAL SIMULATION ONLY\nRun: {run.id}\n"
            f"Risk/reward policy: {run.risk_reward_policy_id}\n"
            f"Performance objective: {run.performance_objective_id}\n"
            f"Performance objective outcome: {objective_outcome}\n"
            f"Setup outcomes: {json.dumps(outcome_counts, sort_keys=True, separators=(',', ':'))}\n"
            f"Orders: {orders}\nFills: {fills}\nClosures: {closures}\n"
            f"Finalized trades: {result.finalized_trade_count}\n"
            f"Unresolved pending orders: {pending}\nUnresolved open positions: {open_positions}\n"
            f"Starting equity: {result.starting_equity}\nEnding equity: {result.ending_equity}\n"
            f"Result: {result.id}\nNo profitability or live-trading claim.\n"
        ).encode()
        checksums = {name: sha256(data).hexdigest() for name, data in sorted(artifacts.items())}
        artifacts["checksums.json"] = _json_bytes({"schema_version": "backtesting-checksums-v1", "sha256": checksums})
        for name, data in artifacts.items(): (temp / name).write_bytes(data)
        if target.exists(): shutil.rmtree(target)
        os.replace(temp, target)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return target
