"""Future-looking labels kept separate from causal feature generation."""
from __future__ import annotations

from datetime import datetime
import math
from typing import Mapping, Sequence
from bot2.data_foundation.contracts import MarketEvent
from ._common import EPOCH, commit_id, log_return, ordered, session
from .contracts import (AMBIGUOUS_OUTCOME, INSUFFICIENT_FUTURE_DATA, SESSION_BOUNDARY, LabelConfig,
                        LabelRow, config_hash)


def generate_labels(events_by_instrument: Mapping[str, Sequence[MarketEvent]], *,
                    source_dataset_id: str, source_dataset_sha256: str,
                    config: LabelConfig | None = None, generated_at: datetime = EPOCH,
                    code_commit: str | None = None) -> tuple[LabelRow, ...]:
    cfg = config or LabelConfig()
    commit = code_commit or commit_id()
    cfg_hash = config_hash(cfg.to_dict())
    rows: list[LabelRow] = []
    for instrument in sorted(events_by_instrument):
        events = ordered(events_by_instrument[instrument])
        for i, event in enumerate(events):
            for horizon in cfg.horizons:
                future = events[i + 1:i + horizon + 1]
                reasons: list[str] = []
                fwd = direction = mfe = mae = vol = outcome = None
                if len(future) < horizon:
                    reasons.append(INSUFFICIENT_FUTURE_DATA)
                elif any(session(x) != session(event) for x in future):
                    reasons.append(SESSION_BOUNDARY)
                else:
                    returns = [log_return(x.price, event.price) for x in future]
                    fwd = future[-1].price / event.price - 1
                    direction = "UP" if fwd > cfg.direction_threshold else "DOWN" if fwd < -cfg.direction_threshold else "FLAT"
                    mfe = max(x.price / event.price - 1 for x in future)
                    mae = min(x.price / event.price - 1 for x in future)
                    vol = math.sqrt(sum(r * r for r in returns) / len(returns))
                    hits = []
                    for x in future:
                        favorable = x.price >= event.price * (1 + cfg.favorable_barrier)
                        adverse = x.price <= event.price * (1 - cfg.adverse_barrier)
                        if favorable and adverse:
                            hits.append(AMBIGUOUS_OUTCOME); break
                        if favorable:
                            hits.append("FAVORABLE"); break
                        if adverse:
                            hits.append("ADVERSE"); break
                    outcome = hits[0] if hits else "NEITHER"
                    if outcome == AMBIGUOUS_OUTCOME:
                        reasons.append(AMBIGUOUS_OUTCOME)
                        fwd = direction = mfe = mae = vol = None
                validity = "VALID" if not reasons else reasons[0]
                rows.append(LabelRow(instrument, event.exchange_time.isoformat().replace("+00:00", "Z"),
                    event.exchange_time.isoformat().replace("+00:00", "Z"), cfg.version, source_dataset_id,
                    source_dataset_sha256, session(event), horizon, validity, tuple(sorted(set(reasons))), fwd,
                    direction, mfe, mae, vol, outcome, cfg_hash, commit,
                    generated_at.isoformat().replace("+00:00", "Z")))
    return tuple(rows)
