"""Future-only targets normalized by a strictly causal trailing-volatility reference."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from statistics import mean
from typing import Mapping, Sequence

from bot2.data_foundation.contracts import MarketEvent
from bot2.data_foundation.instruments import normalize_contract
from ._common import log_return, ordered, session

TARGET_VERSION = "bot2-future-market-state-v3"
TARGET_SCHEMA = "bot2-future-target-row-v3"
HORIZONS_MINUTES = (5, 15, 30)
REFERENCE_MINUTES = 30
TARGET_SPEC = {
    "version": TARGET_VERSION,
    "horizons_minutes": list(HORIZONS_MINUTES),
    "direction": "sign(close[T+H]-close[T]); FLAT iff absolute displacement is less than one instrument tick",
    "volatility": "future RV=sqrt(mean(square(log returns))) for exactly H future 1m returns; causal reference RV is the prior 30 consecutive 1m returns ending at T; ratio <0.8 LOW, 0.8<=ratio<=1.2 NORMAL, >1.2 HIGH",
    "structure": "efficiency=abs(log(close[T+H]/close[T]))/sum(abs(future 1m log returns)); TREND if efficiency>=0.60 and displacement>=4 ticks; RANGE if efficiency<=0.25; otherwise TRANSITION",
    "future_window": "strictly future closes T+1 through T+H, exactly one minute apart, within the same session and listed contract; no fill",
    "volatility_reference_window": "30 consecutive one-minute returns ending at T; same session and exact listed contract; no future observations",
    "label_information_interval": "[first close used by trailing reference, final future bar close]; future subinterval starts at T+1",
    "tick_size_points": {"ES": 0.25, "NQ": 0.25},
}


@dataclass(frozen=True, slots=True)
class FutureTargetRow:
    schema_version: str
    target_version: str
    instrument: str
    root_symbol: str
    contract_id: str
    session_id: str
    observation_time: str
    horizon_minutes: int
    label_information_start: str | None
    future_window_start: str | None
    label_end_time: str | None
    validity: str
    reason_codes: tuple[str, ...]
    future_return: float | None
    future_direction: str | None
    reference_realized_volatility: float | None
    future_realized_volatility: float | None
    future_volatility_ratio: float | None
    future_volatility_state: str | None
    path_efficiency: float | None
    future_structure: str | None

    def to_dict(self):
        return asdict(self) | {"reason_codes": list(self.reason_codes)}


def generate_future_targets(events_by_contract: Mapping[str, Sequence[MarketEvent]], *,
                            horizons: Sequence[int] = HORIZONS_MINUTES,
                            tick_sizes: Mapping[str, float] | None = None) -> tuple[FutureTargetRow, ...]:
    ticks = dict(tick_sizes or TARGET_SPEC["tick_size_points"])
    rows: list[FutureTargetRow] = []
    for contract in sorted(events_by_contract):
        events = ordered(events_by_contract[contract])
        if any(event.instrument != contract for event in events):
            raise ValueError("future target input must preserve exact contract symbol")
        for index, event in enumerate(events):
            identity = normalize_contract(contract, event.contract_id or contract,
                                          reference_date=event.exchange_time.date())
            tick = ticks[identity.root_symbol]
            prior = events[max(0, index - REFERENCE_MINUTES):index + 1]
            prior_reason = None
            if len(prior) != REFERENCE_MINUTES + 1 or any(session(candidate) != session(event) for candidate in prior):
                prior_reason = "INSUFFICIENT_VOLATILITY_REFERENCE"
            elif any(candidate.contract_id != event.contract_id for candidate in prior):
                prior_reason = "CONTRACT_BOUNDARY"
            elif any((right.exchange_time - left.exchange_time).total_seconds() != 60
                     for left, right in zip(prior, prior[1:])):
                prior_reason = "VOLATILITY_REFERENCE_GAP"
            reference_vol = None
            if prior_reason is None:
                reference_returns = [log_return(right.price, left.price) for left, right in zip(prior, prior[1:])]
                reference_vol = math.sqrt(mean(value * value for value in reference_returns))
                if reference_vol <= 0:
                    prior_reason = "ZERO_VOLATILITY_REFERENCE"
            for horizon in horizons:
                if horizon <= 0:
                    raise ValueError("future horizon must be positive")
                future = events[index + 1:index + horizon + 1]
                reasons = []
                if len(future) != horizon:
                    reasons.append("INSUFFICIENT_FUTURE_DATA")
                elif any(session(candidate) != session(event) for candidate in future):
                    reasons.append("SESSION_BOUNDARY")
                elif any(candidate.instrument != event.instrument for candidate in future):
                    reasons.append("CONTRACT_BOUNDARY")
                elif any(candidate.contract_id != event.contract_id for candidate in future):
                    reasons.append("CONTRACT_BOUNDARY")
                elif any((right.exchange_time - left.exchange_time).total_seconds() != 60
                         for left, right in zip((event, *future[:-1]), future)):
                    reasons.append("FUTURE_WINDOW_GAP")
                if prior_reason:
                    reasons.append(prior_reason)
                if reasons:
                    rows.append(FutureTargetRow(TARGET_SCHEMA, TARGET_VERSION, contract,
                        identity.root_symbol, event.contract_id or contract, session(event),
                        event.exchange_time.isoformat().replace("+00:00", "Z"), horizon,
                        prior[0].exchange_time.isoformat().replace("+00:00", "Z") if prior else None,
                        None, None, reasons[0], tuple(sorted(set(reasons))), None, None,
                        reference_vol, None, None, None, None, None))
                    continue
                prices = [event.price, *(candidate.price for candidate in future)]
                changes = [log_return(right, left) for left, right in zip(prices, prices[1:])]
                displacement = prices[-1] - prices[0]
                direction = "UP" if displacement >= tick else "DOWN" if displacement <= -tick else "FLAT"
                future_vol = math.sqrt(mean(change * change for change in changes))
                vol_ratio = future_vol / reference_vol
                volatility = "LOW" if vol_ratio < 0.8 else "HIGH" if vol_ratio > 1.2 else "NORMAL"
                path = sum(abs(change) for change in changes)
                efficiency = abs(math.log(prices[-1] / prices[0])) / path if path else 0.0
                if efficiency >= 0.60 and abs(displacement) >= 4 * tick:
                    structure = "TREND"
                elif efficiency <= 0.25:
                    structure = "RANGE"
                else:
                    structure = "TRANSITION"
                rows.append(FutureTargetRow(TARGET_SCHEMA, TARGET_VERSION, contract,
                    identity.root_symbol, event.contract_id or contract, session(event),
                    event.exchange_time.isoformat().replace("+00:00", "Z"), horizon,
                    prior[0].exchange_time.isoformat().replace("+00:00", "Z"),
                    future[0].exchange_time.isoformat().replace("+00:00", "Z"),
                    future[-1].exchange_time.isoformat().replace("+00:00", "Z"), "VALID", (),
                    prices[-1] / prices[0] - 1, direction, reference_vol, future_vol,
                    vol_ratio, volatility, efficiency, structure))
    return tuple(rows)
