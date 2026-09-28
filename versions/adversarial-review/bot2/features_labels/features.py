"""Causal, cadence-aware Phase 2 features. No row-count window is called minutes."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import math
from statistics import mean
from typing import Mapping, Sequence

from bot2.data_foundation.contracts import MarketEvent
from bot2.data_foundation.instruments import normalize_contract
from bot2.data_foundation.cadence import EXPECTED_BAR_INTERVAL
from ._common import EPOCH, commit_id, log_return, ordered, session
from .contracts import (FEATURE_SCHEMA, FEATURE_REGISTRY_VERSION, FeatureConfig, FeatureRow,
                        INSUFFICIENT_HISTORY, INVALID_SOURCE_DATA, SYNCHRONIZATION_UNAVAILABLE,
                        UNAVAILABLE, VALID, config_hash)

FEATURE_NAMES_V3 = (
    "price", "log_return_1m", "log_return_3m", "log_return_5m",
    "rolling_price_range_3m", "rolling_price_range_5m", "realized_volatility_3m", "realized_volatility_5m",
    "session_open_distance", "session_high_distance", "session_low_distance", "cumulative_volume_session",
    "relative_volume_3m", "volume_acceleration_1m", "session_vwap", "price_to_session_vwap",
    "seconds_since_session_open", "session_phase", "time_sin", "time_cos",
    "cross_market_log_return_1m", "cross_market_relative_return_1m", "cross_market_rolling_correlation_5m",
    "cross_market_divergence_1m",
)


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = mean(xs), mean(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    return sum(x * y for x, y in zip(dx, dy)) / den if den else None


def _exact_window(by_time: Mapping[datetime, MarketEvent], end: datetime, minutes: int,
                  cadence: timedelta = EXPECTED_BAR_INTERVAL) -> tuple[MarketEvent, ...] | None:
    result = tuple(by_time.get(end - cadence * offset) for offset in range(minutes, -1, -1))
    return result if all(row is not None for row in result) else None


def generate_features(events_by_instrument: Mapping[str, Sequence[MarketEvent]], *,
                      source_dataset_id: str, source_dataset_sha256: str,
                      config: FeatureConfig | None = None,
                      generated_at: datetime = EPOCH,
                      code_commit: str | None = None,
                      root_groups: Mapping[str, str] | None = None) -> tuple[FeatureRow, ...]:
    cfg = config or FeatureConfig()
    if cfg.version != FEATURE_REGISTRY_VERSION:
        raise ValueError("only cadence-aware bot2-feature-registry-v3 is executable; legacy row-count semantics are historical")
    cadence = timedelta(seconds=cfg.expected_cadence_seconds)
    if cadence != EXPECTED_BAR_INTERVAL:
        raise ValueError("Phase 5C v2 freezes one-minute cadence")
    series = {instrument: ordered(events) for instrument, events in events_by_instrument.items()}
    roots = dict(root_groups or {name: name for name in series if name in ("ES", "NQ")})
    if any(root not in ("ES", "NQ") for root in roots.values()):
        raise ValueError("canonical root group must be ES or NQ")
    for instrument, root in roots.items():
        if instrument not in series:
            raise ValueError("root group references an unknown exact instrument")
        if instrument not in ("ES", "NQ"):
            for event in series[instrument]:
                if normalize_contract(instrument, event.contract_id or instrument,
                                      reference_date=event.exchange_time.date()).root_symbol != root:
                    raise ValueError("root group conflicts with canonical contract identity")

    root_index: dict[str, dict[tuple[str, datetime], MarketEvent]] = {}
    root_series: dict[str, list[MarketEvent]] = defaultdict(list)
    for instrument, events in series.items():
        if instrument in roots:
            root_series[roots[instrument]].extend(events)
    for root, rows in root_series.items():
        index = {}
        for event in rows:
            key = (session(event), event.exchange_time)
            if key in index:
                raise ValueError(f"duplicate active {root} observation at {key}")
            index[key] = event
        root_index[root] = index

    commit = code_commit or commit_id()
    cfg_hash = config_hash(cfg.to_dict())
    outputs: list[FeatureRow] = []
    for instrument in sorted(series):
        events = series[instrument]
        sessions: dict[str, list[MarketEvent]] = defaultdict(list)
        for event in events:
            sessions[session(event)].append(event)
        for sid, rows in sorted(sessions.items()):
            rows.sort(key=lambda event: event.exchange_time)
            by_time = {event.exchange_time: event for event in rows}
            session_open = rows[0].exchange_time
            cumulative_volume = 0.0
            cumulative_pv = 0.0
            session_high = -math.inf
            session_low = math.inf
            own_root = roots.get(instrument)
            counterpart = "NQ" if own_root == "ES" else "ES" if own_root == "NQ" else None
            cp_index = root_index.get(counterpart, {}) if counterpart else {}
            for event in rows:
                ts = event.exchange_time
                cumulative_volume += event.volume
                cumulative_pv += event.price * event.volume
                session_high = max(session_high, event.price)
                session_low = min(session_low, event.price)
                values: dict[str, float | str | None] = {name: None for name in FEATURE_NAMES_V3}
                reasons: set[str] = set()
                values["price"] = event.price
                for horizon in cfg.return_horizons:
                    window = _exact_window(by_time, ts, horizon, cadence)
                    key = f"log_return_{horizon}m"
                    if window is None:
                        reasons.add(INSUFFICIENT_HISTORY if ts - session_open < cadence * horizon else "FEATURE_WINDOW_GAP")
                    else:
                        values[key] = log_return(window[-1].price, window[0].price)
                for window_minutes in cfg.rolling_windows:
                    window = _exact_window(by_time, ts, window_minutes, cadence)
                    range_key = f"rolling_price_range_{window_minutes}m"
                    vol_key = f"realized_volatility_{window_minutes}m"
                    if window is None:
                        reasons.add(INSUFFICIENT_HISTORY if ts - session_open < cadence * window_minutes else "FEATURE_WINDOW_GAP")
                    else:
                        prices = [row.price for row in window]
                        returns = [log_return(right.price, left.price) for left, right in zip(window, window[1:])]
                        values[range_key] = max(prices) - min(prices)
                        values[vol_key] = math.sqrt(sum(value * value for value in returns) / window_minutes)
                prior_volume_window = _exact_window(by_time, ts - cadence, cfg.relative_volume_window - 1, cadence)
                if prior_volume_window is None:
                    reasons.add(INSUFFICIENT_HISTORY if ts - session_open < cadence * cfg.relative_volume_window else "FEATURE_WINDOW_GAP")
                else:
                    baseline_volume = mean(row.volume for row in prior_volume_window)
                    if baseline_volume > 0:
                        values["relative_volume_3m"] = event.volume / baseline_volume
                previous = by_time.get(ts - cadence)
                if previous is None:
                    reasons.add(INSUFFICIENT_HISTORY if ts - session_open < cadence else "FEATURE_WINDOW_GAP")
                else:
                    values["volume_acceleration_1m"] = event.volume / previous.volume - 1 if previous.volume > 0 else None
                values["session_open_distance"] = event.price - rows[0].price
                values["session_high_distance"] = event.price - session_high
                values["session_low_distance"] = event.price - session_low
                values["cumulative_volume_session"] = cumulative_volume
                values["session_vwap"] = cumulative_pv / cumulative_volume if cumulative_volume else None
                values["price_to_session_vwap"] = event.price - values["session_vwap"] if values["session_vwap"] is not None else None
                elapsed = (ts - session_open).total_seconds()
                values["seconds_since_session_open"] = elapsed
                values["session_phase"] = ("OPENING" if elapsed < cfg.session_phase_minutes[0] * 60
                    else "EARLY" if elapsed < cfg.session_phase_minutes[1] * 60 else "LATE")
                values["time_sin"] = math.sin(2 * math.pi * elapsed / 86400)
                values["time_cos"] = math.cos(2 * math.pi * elapsed / 86400)
                if counterpart:
                    cp_now = cp_index.get((sid, ts))
                    cp_prev = cp_index.get((sid, ts - cadence))
                    own_prev = previous
                    if cp_now is None or cp_prev is None or own_prev is None:
                        reasons.add(SYNCHRONIZATION_UNAVAILABLE)
                    else:
                        cross_return = log_return(cp_now.price, cp_prev.price)
                        own_return = log_return(event.price, own_prev.price)
                        values["cross_market_log_return_1m"] = cross_return
                        values["cross_market_relative_return_1m"] = own_return - cross_return
                        values["cross_market_divergence_1m"] = own_return - cross_return
                        pair_own: list[float] = []
                        pair_cross: list[float] = []
                        first_time = ts - cadence * 5
                        exact = [by_time.get(first_time + cadence * offset) for offset in range(6)]
                        cp_exact = [cp_index.get((sid, first_time + cadence * offset)) for offset in range(6)]
                        if all(exact) and all(cp_exact):
                            pair_own = [log_return(exact[i + 1].price, exact[i].price) for i in range(5)]
                            pair_cross = [log_return(cp_exact[i + 1].price, cp_exact[i].price) for i in range(5)]
                            values["cross_market_rolling_correlation_5m"] = _corr(pair_own, pair_cross)
                        else:
                            reasons.add("FEATURE_WINDOW_GAP")
                elif any(name.startswith("cross_market_") for name in FEATURE_NAMES_V3):
                    reasons.add(SYNCHRONIZATION_UNAVAILABLE)
                # Read-only compatibility aliases for existing Phase 4 callers.
                # They are not members of the v3 registry and must not be model inputs.
                for old, new in (("log_return_1", "log_return_1m"), ("log_return_3", "log_return_3m"),
                    ("log_return_5", "log_return_5m"), ("rolling_price_range_3", "rolling_price_range_3m"),
                    ("rolling_price_range_5", "rolling_price_range_5m"),
                    ("realized_volatility_3", "realized_volatility_3m"),
                    ("realized_volatility_5", "realized_volatility_5m"),
                    ("relative_volume", "relative_volume_3m"), ("volume_acceleration", "volume_acceleration_1m"),
                    ("cross_market_log_return_1", "cross_market_log_return_1m"),
                    ("cross_market_relative_return_1", "cross_market_relative_return_1m"),
                    ("cross_market_rolling_correlation_5", "cross_market_rolling_correlation_5m"),
                    ("cross_market_divergence_1", "cross_market_divergence_1m")):
                    values[old] = values[new]
                validity = VALID if not reasons else (INVALID_SOURCE_DATA if INVALID_SOURCE_DATA in reasons else UNAVAILABLE)
                outputs.append(FeatureRow(instrument, ts.isoformat().replace("+00:00", "Z"),
                    ts.isoformat().replace("+00:00", "Z"), cfg.version, source_dataset_id,
                    source_dataset_sha256, sid, validity, tuple(sorted(reasons)), values,
                    cfg_hash, commit, generated_at.isoformat().replace("+00:00", "Z"),
                    schema_version=FEATURE_SCHEMA, contract_id=event.contract_id or instrument))
    return tuple(outputs)
