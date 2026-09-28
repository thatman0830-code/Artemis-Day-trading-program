"""Independent future-window labels; inputs remain causal at observation T."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
from statistics import mean
from typing import Mapping, Sequence

from bot2.data_foundation.contracts import MarketEvent
from bot2.data_foundation.instruments import normalize_contract
from ._common import log_return, ordered, session

TARGET_VERSION = "bot2-future-market-state-v2"
TARGET_SCHEMA = "bot2-future-target-row-v2"
HORIZONS_MINUTES = (5, 15, 30)
TARGET_SPEC = {
    "version": TARGET_VERSION,
    "horizons_minutes": list(HORIZONS_MINUTES),
    "direction": "sign(close[T+H]-close[T]); FLAT iff absolute displacement is less than one instrument tick",
    "volatility": "sqrt(mean(square(log-return))) across exactly H future 1-minute intervals; state cutpoints are train-only per root/horizon terciles",
    "structure": "efficiency=abs(log(close[T+H]/close[T]))/sum(abs(future 1-minute log returns)); TREND if efficiency>=0.60 and displacement>=4 ticks; RANGE if efficiency<=0.25; otherwise TRANSITION",
    "window": "strictly future closes T+1 through T+H, exactly one minute apart, within one session and one listed contract; no fill",
    "target_information_interval": "[first future bar close timestamp, final future bar close timestamp]",
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
    label_end_time: str | None
    validity: str
    reason_codes: tuple[str, ...]
    future_return: float | None
    future_direction: str | None
    future_realized_volatility: float | None
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
        if not events:
            continue
        for index, event in enumerate(events):
            identity = normalize_contract(contract, event.contract_id or contract,
                                          reference_date=event.exchange_time.date())
            tick = ticks[identity.root_symbol]
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
                elif any((right.exchange_time - left.exchange_time).total_seconds() != 60
                         for left, right in zip((event, *future[:-1]), future)):
                    reasons.append("FUTURE_WINDOW_GAP")
                if reasons:
                    rows.append(FutureTargetRow(TARGET_SCHEMA, TARGET_VERSION, contract,
                        identity.root_symbol, event.contract_id or contract, session(event),
                        event.exchange_time.isoformat().replace("+00:00", "Z"), horizon,
                        None, None, reasons[0], tuple(reasons), None, None, None, None, None, None))
                    continue
                prices = [event.price, *(candidate.price for candidate in future)]
                changes = [log_return(right, left) for left, right in zip(prices, prices[1:])]
                displacement = prices[-1] - prices[0]
                direction = "UP" if displacement >= tick else "DOWN" if displacement <= -tick else "FLAT"
                vol = math.sqrt(mean(change * change for change in changes))
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
                    future[0].exchange_time.isoformat().replace("+00:00", "Z"),
                    future[-1].exchange_time.isoformat().replace("+00:00", "Z"), "VALID", (),
                    prices[-1] / prices[0] - 1, direction, vol, None, efficiency, structure))
    return tuple(rows)


def training_volatility_cutpoints(rows: Sequence[FutureTargetRow]) -> dict[tuple[str, int], tuple[float, float]]:
    """Deterministic linear-interpolated terciles, grouped by root and horizon."""
    groups: dict[tuple[str, int], list[float]] = {}
    for row in rows:
        if row.validity == "VALID" and row.future_realized_volatility is not None:
            groups.setdefault((row.root_symbol, row.horizon_minutes), []).append(row.future_realized_volatility)

    def quantile(values: list[float], q: float) -> float:
        ordered_values = sorted(values)
        position = (len(ordered_values) - 1) * q
        low = int(position); high = min(low + 1, len(ordered_values) - 1)
        return ordered_values[low] + (ordered_values[high] - ordered_values[low]) * (position - low)

    return {key: (quantile(values, 1 / 3), quantile(values, 2 / 3))
            for key, values in groups.items() if values}


def apply_volatility_cutpoints(rows: Sequence[FutureTargetRow],
                               cutpoints: Mapping[tuple[str, int], tuple[float, float]]) -> tuple[FutureTargetRow, ...]:
    output = []
    for row in rows:
        if row.validity != "VALID" or row.future_realized_volatility is None:
            output.append(row); continue
        low, high = cutpoints[(row.root_symbol, row.horizon_minutes)]
        value = row.future_realized_volatility
        state = "LOW" if value <= low else "HIGH" if value > high else "MEDIUM"
        output.append(replace(row, future_volatility_state=state))
    return tuple(output)
