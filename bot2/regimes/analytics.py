from __future__ import annotations
from collections import Counter, defaultdict
from statistics import median
from typing import Sequence, Mapping, Any


def duration_statistics(assignments: Sequence[Any]) -> dict:
    durations = defaultdict(list); current = None; length = 0
    for row in assignments:
        state = row.primary_state
        if state != current:
            if current is not None: durations[current].append(length)
            current, length = state, 1
        else: length += 1
    if current is not None: durations[current].append(length)
    return {state: {"count": len(values), "average_duration": sum(values) / len(values), "median_duration": median(values),
                    "max_duration": max(values)} for state, values in sorted(durations.items())}


def transition_matrix(assignments: Sequence[Any]) -> dict:
    counts = Counter((a.primary_state, b.primary_state) for a, b in zip(assignments, assignments[1:]))
    states = sorted({x for pair in counts for x in pair} | {a.primary_state for a in assignments})
    return {source: {target: counts[(source, target)] for target in states} for source in states}


def conditional_outcomes(assignments: Sequence[Any], labels: Sequence[Any]) -> dict:
    groups = defaultdict(list)
    for regime, label in zip(assignments, labels):
        if regime.primary_state == "UNCERTAIN" or getattr(label, "validity", None) != "VALID": continue
        groups[regime.primary_state].append(label)
    output = {}
    for state, rows in sorted(groups.items()):
        returns = [r.forward_return for r in rows if r.forward_return is not None]
        ups = [r for r in rows if r.direction == "UP"]
        vols = [r.future_realized_volatility for r in rows if r.future_realized_volatility is not None]
        output[state] = {"count": len(rows), "mean_forward_return": sum(returns) / len(returns) if returns else None,
                         "p_up": len(ups) / len(rows) if rows else None, "mean_future_volatility": sum(vols) / len(vols) if vols else None,
                         "mfe_values": [r.mfe for r in rows], "mae_values": [r.mae for r in rows],
                         "barrier_outcomes": dict(Counter(r.barrier_outcome for r in rows))}
    return output


def cross_market_relationship(assignments_by_instrument: Mapping[str, Sequence[Any]]) -> dict:
    es = list(assignments_by_instrument.get("ES", ())); nq = list(assignments_by_instrument.get("NQ", ()))
    pairs = []
    for left in es:
        eligible = [right for right in nq if right.cutoff_time <= left.cutoff_time]
        if eligible: pairs.append((left, eligible[-1]))
    same = sum(a.primary_state == b.primary_state for a, b in pairs); divergent = len(pairs) - same
    return {"paired_count": len(pairs), "simultaneous_same_state_rate": same / len(pairs) if pairs else None,
            "divergent_state_rate": divergent / len(pairs) if pairs else None,
            "lag_direction_claim": "NOT_ESTABLISHED", "method": "ES cutoff paired with latest NQ observation at-or-before cutoff"}
