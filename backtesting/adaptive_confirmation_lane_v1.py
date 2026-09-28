"""Deterministic partial-confirmation research lane.

The baseline strategy is never modified.  This lane only admits a candidate
when a fair-value-gap is present plus at least one independent confirmation
(liquidity sweep or displacement/acceptance).  It emits comparison evidence,
never orders or trading authority.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime, timezone
from hashlib import sha256
import json

VERSION = "adaptive-confirmation-lane-v1"
RISK_FRACTION = Decimal("0.25")

@dataclass(frozen=True, slots=True)
class AdaptiveCandidate:
    candidate_id: str
    symbol: str
    timestamp: str
    direction: str
    fvg: bool
    liquidity_sweep: bool
    displacement: bool
    acceptance: bool
    missing_confirmations: tuple[str, ...]
    risk_fraction: str = "0.25R"
    comparison_only: bool = True
    paper_execution_permitted: bool = False
    trading_authority: bool = False

def _d(v) -> Decimal:
    return Decimal(str(v))

def detect_candidate(symbol: str, bars: list[dict]) -> AdaptiveCandidate | None:
    if len(bars) < 3:
        return None
    a, b, c = bars[-3:]
    try:
        ah, al, ac = _d(a["high"]), _d(a["low"]), _d(a["close"])
        bh, bl, bo, bc = _d(b["high"]), _d(b["low"]), _d(b["open"]), _d(b["close"])
        ch, cl, cc = _d(c["high"]), _d(c["low"]), _d(c["close"])
    except (KeyError, ValueError, TypeError):
        return None
    bullish_fvg = cl > ah
    bearish_fvg = ch < al
    if not (bullish_fvg or bearish_fvg):
        return None
    direction = "LONG" if bullish_fvg else "SHORT"
    sweep = (cl < al and cc > al) if bullish_fvg else (ch > ah and cc < ah)
    displacement = abs(bc - bo) >= (ah - al if ah > al else ch - cl) * Decimal("0.60")
    acceptance = (cc > ah if bullish_fvg else cc < al)
    present = {"fvg": True, "liquidity_sweep": sweep, "displacement": displacement, "acceptance": acceptance}
    # FVG is mandatory; one of sweep/displacement/acceptance is sufficient.
    if not (sweep or displacement or acceptance):
        return None
    missing = tuple(k for k, v in present.items() if not v)
    stamp = str(c.get("close_time") or c.get("open_time") or "")
    identity = sha256(json.dumps([VERSION, symbol, stamp, direction, present], sort_keys=True).encode()).hexdigest()
    return AdaptiveCandidate(identity, symbol, stamp, direction, True, sweep, displacement, acceptance, missing)

def evaluate(symbol: str, bars: list[dict], evaluated_at: datetime | None = None) -> dict:
    now = evaluated_at or datetime.now(timezone.utc)
    candidate = detect_candidate(symbol, bars)
    # Never admit a bar whose close is in the future relative to the
    # evaluation clock; the live capture can publish a forming minute before
    # its close timestamp is finalized.
    if candidate is not None:
        try:
            candidate_time = datetime.fromisoformat(candidate.timestamp.replace("Z", "+00:00"))
            if candidate_time.tzinfo is not None and candidate_time > now:
                candidate = None
        except ValueError:
            candidate = None
    return {
        "schema_version": VERSION,
        "evaluated_at": now.isoformat(),
        "symbol": symbol,
        "bars_examined": len(bars),
        "candidate": None if candidate is None else asdict(candidate),
        "baseline_unchanged": True,
        "comparison_only": True,
        "paper_execution_permitted": False,
        "trading_authority": False,
    }
