"""Small, explicit feature-family ablation selector; no search is performed."""
from __future__ import annotations

FAMILY_PREFIXES = {
    "PRICE": ("price", "log_return", "session_open_distance", "session_high_distance", "session_low_distance"),
    "VOLATILITY": ("rolling_price_range", "realized_volatility"),
    "VOLUME": ("volume", "relative_volume", "cumulative_volume"),
    "VWAP": ("session_vwap", "price_to_session_vwap"),
    "SESSION_TIME": ("seconds_since_session_open", "session_phase", "time_sin", "time_cos"),
    "CROSS_MARKET": ("cross_market",),
}


def select_feature_names(names: tuple[str, ...], families: tuple[str, ...]) -> tuple[str, ...]:
    if "ALL" in families:
        return names
    prefixes = tuple(prefix for family in families for prefix in FAMILY_PREFIXES.get(family, ()))
    return tuple(name for name in names if name.startswith(prefixes))
