"""Typed, validated, hashed pilot configuration.

Every numeric default lives in ``config/mes_paper_pilot_v1.json`` with a
provenance label. Changing any value changes ``config_hash`` and therefore the
recorded strategy/config identity; results stay attached to the old hash.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from hashlib import sha256
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "mes_paper_pilot_v1.json"


class ConfigError(ValueError):
    pass


def _hhmm(text: str) -> time:
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def _positive(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"{name} must be a positive number, got {value!r}")
    return float(value)


def _non_negative(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or value < 0:
        raise ConfigError(f"{name} must be >= 0, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class Instrument:
    root: str
    tick_size: float
    tick_value: float
    point_value: float

    def ticks(self, price_distance: float) -> float:
        return price_distance / self.tick_size

    def round_down(self, price: float) -> float:
        return _floor_div(price, self.tick_size) * self.tick_size

    def round_up(self, price: float) -> float:
        return -_floor_div(-price, self.tick_size) * self.tick_size

    def on_grid(self, price: float) -> bool:
        return abs(price / self.tick_size - round(price / self.tick_size)) < 1e-9


def _floor_div(value: float, step: float) -> int:
    q = value / step
    r = round(q)
    return int(r) if abs(q - r) < 1e-9 else int(q // 1)


@dataclass(frozen=True)
class Costs:
    commission_per_side: float
    spread_ticks: int
    stop_slippage_ticks: int
    stressed_slippage_ticks: int
    margin_per_contract: float

    def round_trip_commission(self, contracts: int = 1) -> float:
        return round(2 * self.commission_per_side * contracts, 2)


@dataclass(frozen=True)
class RiskConfig:
    starting_equity: float
    static_floor: float
    execution_reserve: float
    max_trade_budget: float
    capacity_fraction: float
    daily_stop: float
    max_contracts: int
    max_entries_per_session: int
    consecutive_loss_pause: int
    max_open_positions: int
    user_trade_pct_max: float
    user_daily_pct: float
    user_daily_drawdown_share: float
    outer_daily_loss_pct: float
    outer_drawdown_pct: float


@dataclass(frozen=True)
class SessionConfig:
    timezone: str
    entry_start: time
    entry_end: time
    flat_by: time
    asia: tuple[time, time]
    london: tuple[time, time]
    day_rollover: time


@dataclass(frozen=True)
class EventConfig:
    required: bool
    currencies: tuple[str, ...]
    impacts: tuple[str, ...]
    before_min: int
    after_min: int
    flatten_before_min: int


@dataclass(frozen=True)
class StrategyConfig:
    swing_side_bars: int
    atr_period: int
    displacement_body_atr: float
    displacement_close_outer: float
    equal_tolerance_ticks: int
    sweep_min_ticks: int
    bos_min_ticks: int
    stop_buffer_ticks: int
    min_rr: float
    ote: tuple[float, float]
    ote_required: bool
    setup_expiry_min: int
    intent_lifetime_s: int
    intent_max_drift_ticks: int
    max_hold_min: int
    er_period: int
    continuation_min_er: float
    volatility_filter: bool
    volatility_sessions: int
    volatility_band: tuple[float, float]
    planning_p: float


@dataclass(frozen=True)
class AccumulationConfig:
    gate: bool
    lookback_closes: int
    max_range_atr: float
    max_er: float
    stale_after_bars: int


@dataclass(frozen=True)
class EvidenceConfig:
    min_positions: int
    min_sessions: int
    min_calendar_days: int
    promotion_win_rate: float
    higher_objective: float
    source_benchmark: float
    source_label: str


@dataclass(frozen=True)
class Splits:
    warmup_start: date
    development: tuple[date, date]
    validation: tuple[date, date]
    protected_oos: tuple[date, date]

    def label_for(self, day: date) -> str:
        if self.protected_oos[0] <= day <= self.protected_oos[1]:
            return "PROTECTED_OOS"
        if self.validation[0] <= day <= self.validation[1]:
            return "WALK_FORWARD"
        if self.development[0] <= day <= self.development[1]:
            return "HISTORICAL_DEVELOPMENT"
        if day > self.protected_oos[1]:
            return "POST_HOLDOUT_FORWARD_ARCHIVE"
        return "OUT_OF_RANGE"


@dataclass(frozen=True)
class PilotConfig:
    strategy_version: str
    config_hash: str
    mode: str
    live_auto_enabled: bool
    instrument: Instrument
    costs: Costs
    risk: RiskConfig
    session: SessionConfig
    events: EventConfig
    max_quote_age_s: float
    max_spread_ticks: int
    strategy: StrategyConfig
    accumulation: AccumulationConfig
    evidence: EvidenceConfig
    splits: Splits
    raw: dict


def load_config(path: Path | str = DEFAULT_CONFIG, overrides: dict | None = None) -> PilotConfig:
    raw_bytes = Path(path).read_bytes()
    raw = json.loads(raw_bytes)
    if overrides:
        raw = _deep_merge(raw, overrides)
    return parse_config(raw)


def _deep_merge(base: dict, extra: dict) -> dict:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def parse_config(raw: dict) -> PilotConfig:
    if raw.get("schema_version") != "mes-paper-pilot-config-v1":
        raise ConfigError("unsupported config schema_version")
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    config_hash = sha256(canonical).hexdigest()

    mode = raw["mode"]["value"]
    if mode not in raw["mode"]["allowed"]:
        raise ConfigError(f"unknown mode {mode}")

    i = raw["instrument"]
    instrument = Instrument(
        root=i["root"],
        tick_size=_positive("tick_size", i["tick_size"]),
        tick_value=_positive("tick_value_usd", i["tick_value_usd"]),
        point_value=_positive("point_value_usd", i["point_value_usd"]),
    )
    if abs(instrument.tick_value - instrument.tick_size * instrument.point_value) > 1e-9:
        raise ConfigError("tick_value must equal tick_size * point_value")

    c = raw["costs"]
    costs = Costs(
        commission_per_side=_non_negative("commission", c["commission_per_side_usd"]),
        spread_ticks=int(c["modeled_spread_ticks"]),
        stop_slippage_ticks=int(c["stop_exit_slippage_ticks"]),
        stressed_slippage_ticks=int(c["stressed_slippage_ticks_for_sizing"]),
        margin_per_contract=_positive("margin_per_contract_usd", c["margin_per_contract_usd"]),
    )

    r = raw["risk"]
    u = r["user_ceilings"]
    o = r["outer_caps"]
    risk = RiskConfig(
        starting_equity=_positive("starting_equity", r["synthetic_starting_equity_usd"]),
        static_floor=_positive("static_floor", r["static_synthetic_floor_usd"]),
        execution_reserve=_non_negative("reserve", r["execution_reserve_usd"]),
        max_trade_budget=_positive("max_trade_budget", r["max_new_trade_budget_usd"]),
        capacity_fraction=_positive("capacity_fraction", r["capacity_fraction"]),
        daily_stop=_positive("daily_stop", r["net_daily_stop_usd"]),
        max_contracts=int(r["max_contracts"]),
        max_entries_per_session=int(r["max_entries_per_session"]),
        consecutive_loss_pause=int(r["consecutive_loss_pause"]),
        max_open_positions=int(r["max_open_positions"]),
        user_trade_pct_max=_positive("per_trade_nominal_pct_max", u["per_trade_nominal_pct_max"]),
        user_daily_pct=_positive("daily_loss_nominal_pct", u["daily_loss_nominal_pct"]),
        user_daily_drawdown_share=_positive("daily_share", u["daily_share_of_drawdown_allowance"]),
        outer_daily_loss_pct=_positive("outer_daily", o["max_daily_loss_pct"]),
        outer_drawdown_pct=_positive("outer_dd", o["max_drawdown_pct"]),
    )
    if risk.static_floor >= risk.starting_equity:
        raise ConfigError("floor must be below starting equity")
    if risk.max_contracts < 1 or risk.max_contracts > u["max_micro_contracts_future_profile"]:
        raise ConfigError("max_contracts outside Frank's 1-3 micro range")
    if risk.capacity_fraction > 1:
        raise ConfigError("capacity_fraction must be <= 1")

    s = raw["session"]
    session = SessionConfig(
        timezone=s["timezone"],
        entry_start=_hhmm(s["entry_window_start"]),
        entry_end=_hhmm(s["entry_window_end"]),
        flat_by=_hhmm(s["flat_by"]),
        asia=(_hhmm(s["asia_window"][0]), _hhmm(s["asia_window"][1])),
        london=(_hhmm(s["london_window"][0]), _hhmm(s["london_window"][1])),
        day_rollover=_hhmm(s["trading_day_rollover"]),
    )
    if session.entry_start < time(9, 30):
        raise ConfigError("premarket entries are forbidden (entry start before 09:30 ET)")

    e = raw["events"]
    events = EventConfig(
        required=bool(e["required"]),
        currencies=tuple(e["currencies"]),
        impacts=tuple(e["impacts"]),
        before_min=int(e["blackout_before_minutes"]),
        after_min=int(e["blackout_after_minutes"]),
        flatten_before_min=int(e["flatten_before_minutes"]),
    )

    st = raw["strategy"]
    strategy = StrategyConfig(
        swing_side_bars=int(st["swing_side_bars"]),
        atr_period=int(st["atr_period"]),
        displacement_body_atr=_positive("displacement_body_atr_mult", st["displacement_body_atr_mult"]),
        displacement_close_outer=_positive("outer", st["displacement_close_outer_fraction"]),
        equal_tolerance_ticks=int(st["equal_level_tolerance_ticks"]),
        sweep_min_ticks=int(st["sweep_min_ticks"]),
        bos_min_ticks=int(st["bos_min_ticks"]),
        stop_buffer_ticks=int(st["stop_buffer_ticks"]),
        min_rr=_positive("min_reward_risk_gross", st["min_reward_risk_gross"]),
        ote=(float(st["ote_retracement"][0]), float(st["ote_retracement"][1])),
        ote_required=bool(st["ote_required"]),
        setup_expiry_min=int(st["setup_expiry_minutes"]),
        intent_lifetime_s=int(st["intent_lifetime_seconds"]),
        intent_max_drift_ticks=int(st["intent_max_drift_ticks"]),
        max_hold_min=int(st["max_hold_minutes"]),
        er_period=int(st["efficiency_ratio_period"]),
        continuation_min_er=float(st["continuation_min_efficiency_ratio"]),
        volatility_filter=bool(st["volatility_filter_enabled"]),
        volatility_sessions=int(st["volatility_lookback_sessions"]),
        volatility_band=(float(st["volatility_band_percentiles"][0]), float(st["volatility_band_percentiles"][1])),
        planning_p=float(st["planning_win_probability"]),
    )
    if strategy.min_rr < 1.0:
        raise ConfigError("pilot minimum gross reward/risk is 1.0")

    a = raw["accumulation"]
    accumulation = AccumulationConfig(
        gate=bool(a["enabled_as_gate"]),
        lookback_closes=int(a["lookback_closes"]),
        max_range_atr=float(a["max_range_atr_mult"]),
        max_er=float(a["max_efficiency_ratio"]),
        stale_after_bars=int(a["stale_after_bars"]),
    )

    ev = raw["evidence"]
    evidence = EvidenceConfig(
        min_positions=int(ev["initial_review_min_positions"]),
        min_sessions=int(ev["initial_review_min_sessions"]),
        min_calendar_days=int(ev["initial_review_min_calendar_days"]),
        promotion_win_rate=float(ev["promotion_min_observed_win_rate"]),
        higher_objective=float(ev["higher_objective_win_rate"]),
        source_benchmark=float(ev["source_engine_benchmark_win_rate"]),
        source_label=str(ev["source_engine_benchmark_label"]),
    )

    sp = raw["data_splits"]
    d = date.fromisoformat
    splits = Splits(
        warmup_start=d(sp["warmup_start"]),
        development=(d(sp["development"][0]), d(sp["development"][1])),
        validation=(d(sp["walk_forward_validation"][0]), d(sp["walk_forward_validation"][1])),
        protected_oos=(d(sp["protected_oos"][0]), d(sp["protected_oos"][1])),
    )

    return PilotConfig(
        strategy_version=raw["strategy_version"],
        config_hash=config_hash,
        mode=mode,
        live_auto_enabled=bool(raw["mode"]["live_auto_enabled"]),
        instrument=instrument,
        costs=costs,
        risk=risk,
        session=session,
        events=events,
        max_quote_age_s=float(raw["data"]["max_quote_age_seconds_live"]),
        max_spread_ticks=int(raw["data"]["max_spread_ticks"]),
        strategy=strategy,
        accumulation=accumulation,
        evidence=evidence,
        splits=splits,
        raw=raw,
    )
