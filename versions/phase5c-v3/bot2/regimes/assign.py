"""Causal deterministic regime assignment. Only the current feature row is read."""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Mapping, Sequence, Any
from .contracts import RegimeAssignment, RegimeConfig, RegimeSequence, REGIME_SCHEMA


def _cfg_hash(config): return sha256(json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _value(row: Any, name: str):
    values = row.values if hasattr(row, "values") else row.get("values", {})
    aliases = {"log_return_3": "log_return_3m", "log_return_5": "log_return_5m",
               "realized_volatility_3": "realized_volatility_3m",
               "realized_volatility_5": "realized_volatility_5m",
               "rolling_price_range_3": "rolling_price_range_3m"}
    return values.get(aliases.get(name, name), values.get(name))


def _meta(row, name): return getattr(row, name, None) if hasattr(row, name) else row.get(name)


def assign_regime(row: Any, *, source_dataset_id: str, source_dataset_sha256: str,
                  config: RegimeConfig | None = None, code_commit: str = "UNKNOWN") -> RegimeAssignment:
    cfg = config or RegimeConfig(); reasons = []
    r3, r5 = _value(row, "log_return_3"), _value(row, "log_return_5")
    v3, v5 = _value(row, "realized_volatility_3"), _value(row, "realized_volatility_5")
    price = _value(row, "price"); rng = _value(row, "rolling_price_range_3")
    direction = "UNKNOWN"; volatility = "UNKNOWN"; structure = "UNKNOWN"
    if r3 is None or price is None: reasons.append("INSUFFICIENT_HISTORY")
    else: direction = "UP" if r3 >= cfg.return_threshold else "DOWN" if r3 <= -cfg.return_threshold else "NEUTRAL"
    if v3 is None or v5 is None or v5 == 0: reasons.append("INSUFFICIENT_HISTORY")
    else:
        ratio = v3 / v5; volatility = "EXPANDING" if ratio >= cfg.volatility_expansion_ratio else "CONTRACTING" if ratio <= cfg.volatility_contraction_ratio else "STABLE"
    if r3 is None or rng is None: reasons.append("INSUFFICIENT_HISTORY")
    else: structure = "TRENDING" if abs(r3) >= cfg.structure_return_threshold else "RANGING"
    probabilities = {state: 0.0 for state in ("TREND_UP", "TREND_DOWN", "RANGE", "VOLATILITY_EXPANSION", "VOLATILITY_CONTRACTION", "TRANSITION", "UNCERTAIN")}
    if direction == "UP" and structure == "TRENDING": primary = "TREND_UP"
    elif direction == "DOWN" and structure == "TRENDING": primary = "TREND_DOWN"
    elif volatility == "EXPANDING": primary = "VOLATILITY_EXPANSION"
    elif volatility == "CONTRACTING": primary = "VOLATILITY_CONTRACTION"
    elif direction == "NEUTRAL" and structure == "RANGING": primary = "RANGE"
    elif direction != "UNKNOWN" and volatility != "UNKNOWN": primary = "TRANSITION"
    else: primary = "UNCERTAIN"
    if reasons: primary = "UNCERTAIN"
    probabilities[primary] = 1.0 if primary != "UNCERTAIN" else 0.5
    confidence = probabilities[primary]
    if confidence < cfg.minimum_confidence: primary = "UNCERTAIN"; probabilities["UNCERTAIN"] = max(probabilities["UNCERTAIN"], confidence)
    validity = "VALID" if not reasons and primary != "UNCERTAIN" else "UNCERTAIN"
    return RegimeAssignment(_meta(row, "instrument") or "UNKNOWN", _meta(row, "observation_time"), _meta(row, "cutoff_time") or _meta(row, "observation_time"),
        _meta(row, "session_id") or "UNKNOWN", direction, volatility, structure, primary, probabilities, confidence, validity,
        tuple(sorted(set(reasons))), cfg.version, source_dataset_id, source_dataset_sha256, _cfg_hash(cfg), code_commit, False)


def assign_sequence(rows: Sequence[Any], **kwargs) -> RegimeSequence:
    assignments = tuple(assign_regime(row, **kwargs) for row in rows)
    transitions = sum(a.primary_state != b.primary_state for a, b in zip(assignments, assignments[1:]))
    churn = transitions / (len(assignments) - 1) if len(assignments) > 1 else 0.0
    return RegimeSequence(assignments, assignments[0].instrument if assignments else "UNKNOWN", transitions, churn,
                          kwargs["source_dataset_id"], (kwargs.get("config") or RegimeConfig()).version, False)
