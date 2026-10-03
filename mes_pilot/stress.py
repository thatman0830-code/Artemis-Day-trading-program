"""Seeded path stress test for the pilot's dollar sizing (master spec page 15).

Every simulated path applies the exact pilot rules from ``mes_pilot.risk``:
capacity C = cash - floor - reserve, budget = min(trade cap, fraction*C, daily
headroom, C, per-trade ceiling, firm limit), integer quantity capped at the
internal/margin/firm caps (qty 0 => skip), the net daily stop, the session
entry cap and the consecutive-loss pause. Cash is realized only.

Resampling:
* ``outcomes_r`` as per-session lists (chronological): fixed-length block
  bootstrap of whole sessions, blocks of L consecutive sessions (circular) so
  serial dependence inside a block is retained; sweep L via ``block_lengths``.
* ``outcomes_r`` as a flat chronological list: grouped into pseudo-sessions
  of ``max_entries_per_session`` positions, then block-bootstrapped the same way.
* ``run_iid_baseline``: IID Bernoulli outcomes from an assumed win rate and
  payoff. Baseline only; never evidence.

Adverse scenario: costs doubled, +1 adverse tick per side, win probability
-5 percentage points (wins converted to resampled observed losses), and the
worst observed contiguous loss block replayed once in every path at a seeded
random position.

Outcomes are R multiples of the stop distance (ledger ``net_r`` by default,
i.e. net of modeled costs). Acceptance thresholds are DESIGN TOLERANCES, not
guarantees, and are judged on the upper 95% confidence bound.
"""
from __future__ import annotations

from collections.abc import Sequence
import math

import numpy as np

from mes_pilot.config import PilotConfig
from mes_pilot.risk import daily_loss_limit, effective_floor, per_trade_ceiling, unit_loss_for

TOLERANCE_LABEL = "DESIGN_TOLERANCE_NOT_GUARANTEE"
BREACH_TOLERANCE = {"base": 0.01, "adverse": 0.05}
ADVERSE_WIN_PROB_SHIFT = 0.05
ADVERSE_TICKS_PER_SIDE = 1
_NON_EVIDENCE_MARKERS = ("SYNTHETIC", "ASSUMED", "IID", "FIXTURE", "PLACEHOLDER")
_Z95 = 1.959963984540054
_EPS = 1e-9
_SCENARIO_CODE = {"base": 1, "adverse": 2}


# ---------------------------------------------------------------------- statistics
def wilson_interval(successes: int, n: int, z: float = _Z95) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def quantile_with_ci(values: np.ndarray, q: float, z: float = _Z95) -> dict:
    """Empirical quantile with a distribution-free order-statistic 95% CI."""
    v = np.sort(np.asarray(values, dtype=float))
    n = len(v)
    half = z * math.sqrt(n * q * (1 - q))
    lo = int(min(n - 1, max(0, math.floor(n * q - half) - 1)))
    hi = int(min(n - 1, max(0, math.ceil(n * q + half) - 1)))
    return {"q": q, "value": round(float(np.quantile(v, q, method="higher")), 2),
            "ci95": [round(float(v[lo]), 2), round(float(v[hi]), 2)]}


def worst_loss_block(outcomes: Sequence[float]) -> list[float]:
    """Contiguous run with the most negative cumulative R (Kadane on the minimum)."""
    best_sum, best = 0.0, (0, 0)
    cur_sum, cur_start = 0.0, 0
    for i, x in enumerate(outcomes):
        if cur_sum > 0:
            cur_sum, cur_start = 0.0, i
        cur_sum += x
        if cur_sum < best_sum - _EPS:
            best_sum, best = cur_sum, (cur_start, i + 1)
    return list(outcomes[best[0]:best[1]])


# ---------------------------------------------------------------------- samplers
class _SessionBlockSampler:
    """Draws whole sessions in blocks of ``block_len`` consecutive sessions (circular)."""

    def __init__(self, sessions: list[list[float]], block_len: int, n_paths: int):
        self.n_sessions = len(sessions)
        self.slots = max(1, max(len(s) for s in sessions))
        self.matrix = np.zeros((self.n_sessions, self.slots))
        self.lengths = np.zeros(self.n_sessions, dtype=np.int64)
        for i, s in enumerate(sessions):
            self.matrix[i, :len(s)] = s
            self.lengths[i] = len(s)
        self.block_len = int(block_len)
        self.cur = np.zeros(n_paths, dtype=np.int64)
        self.remaining = np.zeros(n_paths, dtype=np.int64)

    def next(self, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        new = self.remaining <= 0
        starts = rng.integers(0, self.n_sessions, size=len(self.cur))
        self.cur = np.where(new, starts, (self.cur + 1) % self.n_sessions)
        self.remaining = np.where(new, self.block_len, self.remaining) - 1
        return self.matrix[self.cur], self.lengths[self.cur]


class _IIDSampler:
    def __init__(self, win_rate: float, payoff_r: float, loss_r: float, slots: int, n_paths: int):
        self.p, self.win, self.loss, self.slots, self.n = win_rate, payoff_r, loss_r, slots, n_paths

    def next(self, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        wins = rng.random((self.n, self.slots)) < self.p
        return np.where(wins, self.win, self.loss), np.full(self.n, self.slots, dtype=np.int64)


# ---------------------------------------------------------------------- core path simulation
def _simulate(cfg: PilotConfig, sampler, rng: np.random.Generator, *, n_paths: int, horizon: int, stop_ticks: int,
              extra_cost: float, win_haircut: float, loss_pool: np.ndarray, forced_block: np.ndarray | None,
              profit_target: float | None, firm_contract_cap: int | None, firm_trade_limit: float | None,
              max_sessions: int) -> dict:
    r, inst = cfg.risk, cfg.instrument
    start, floor, reserve = r.starting_equity, effective_floor(cfg), r.execution_reserve
    unit = unit_loss_for(cfg, stop_ticks)
    risk_per_contract = stop_ticks * inst.tick_value
    day_limit = daily_loss_limit(cfg)
    static_caps = [r.max_trade_budget, per_trade_ceiling(cfg)] + ([firm_trade_limit] if firm_trade_limit is not None else [])
    static_cap = min(static_caps)
    qty_cap = min([r.max_contracts] + ([firm_contract_cap] if firm_contract_cap is not None else []))

    cash = np.full(n_paths, start)
    peak = cash.copy()
    max_dd = np.zeros(n_paths)
    taken = np.zeros(n_paths, dtype=np.int64)
    consec = np.zeros(n_paths, dtype=np.int64)
    breached = np.zeros(n_paths, dtype=bool)
    target_hit = np.zeros(n_paths, dtype=bool)
    halted = np.zeros(n_paths, dtype=bool)
    sessions_used = np.zeros(n_paths, dtype=np.int64)
    daily_stops = np.zeros(n_paths, dtype=np.int64)
    pauses = np.zeros(n_paths, dtype=np.int64)
    if forced_block is not None and len(forced_block):
        blen = len(forced_block)
        inj = rng.integers(0, max(1, horizon - blen + 1), size=n_paths)
    else:
        blen, inj = 0, None

    for _ in range(max_sessions):
        active = ~breached & ~target_hit & ~halted & (taken < horizon)
        if not active.any():
            break
        sessions_used += active
        # Pause lasts until the next session AND a logged review; the stress assumes the review is logged.
        consec[consec >= r.consecutive_loss_pause] = 0
        R, lengths = sampler.next(rng)
        if win_haircut > 0:
            convert = (R > 0) & (rng.random(R.shape) < win_haircut)
            R = np.where(convert, loss_pool[rng.integers(0, len(loss_pool), size=R.shape)], R)
        day_net = np.zeros(n_paths)
        entries = np.zeros(n_paths, dtype=np.int64)
        stop_hit = np.zeros(n_paths, dtype=bool)
        for j in range(R.shape[1]):
            cand = active & (j < lengths) & (taken < horizon)
            if not cand.any():
                continue
            out = R[:, j]
            if inj is not None:
                idx = taken - inj
                use = (idx >= 0) & (idx < blen)
                out = np.where(use, forced_block[np.clip(idx, 0, blen - 1)], out)
            C = cash - floor - reserve
            perm_budget = np.minimum(np.minimum(static_cap, r.capacity_fraction * C), C)
            budget = np.maximum(0.0, np.minimum(perm_budget, day_limit + day_net))
            qty = np.floor(budget / unit + _EPS)
            qty = np.minimum(np.minimum(qty, qty_cap), np.floor(np.maximum(cash, 0.0) / cfg.costs.margin_per_contract))
            # Without trades cash never changes, so a capacity-driven zero quantity is permanent.
            halted |= cand & (np.floor(np.maximum(perm_budget, 0.0) / unit + _EPS) < 1)
            ok = (cand & (entries < r.max_entries_per_session) & (day_net > -r.daily_stop + _EPS)
                  & (consec < r.consecutive_loss_pause) & (qty >= 1) & ~halted)
            pnl = np.where(ok, qty * (out * risk_per_contract - extra_cost), 0.0)
            cash = cash + pnl
            day_net = day_net + pnl
            entries += ok
            taken += ok
            consec = np.where(ok & (pnl < 0), consec + 1, np.where(ok & (pnl > 0), 0, consec))
            pauses += ok & (pnl < 0) & (consec == r.consecutive_loss_pause)
            newly_stopped = ok & (day_net <= -r.daily_stop + _EPS) & ~stop_hit
            daily_stops += newly_stopped
            stop_hit |= newly_stopped
            peak = np.maximum(peak, cash)
            max_dd = np.maximum(max_dd, peak - cash)
            breached |= ok & (cash <= floor + _EPS)          # equality counts as breach
            if profit_target is not None:
                target_hit |= ok & ~breached & (cash >= start + profit_target - _EPS)
            active = active & ~breached & ~target_hit
    completed = taken >= horizon
    return {"cash": cash, "max_dd": max_dd, "taken": taken, "breached": breached, "target_hit": target_hit,
            "completed": completed, "halted": halted, "sessions": sessions_used,
            "daily_stops": daily_stops, "pauses": pauses, "unit_loss": unit}


def _summarize(sim: dict, cfg: PilotConfig, scenario: str, profit_target: float | None) -> dict:
    r = cfg.risk
    n = len(sim["cash"])
    breach = sim["breached"]
    passed = (sim["target_hit"] if profit_target is not None else sim["completed"]) & ~breach
    unresolved = ~breach & ~passed
    usable = r.starting_equity - effective_floor(cfg) - r.execution_reserve
    tol = BREACH_TOLERANCE[scenario]
    nb, npass, nun = int(breach.sum()), int(passed.sum()), int(unresolved.sum())
    breach_ci = wilson_interval(nb, n)
    dd95 = quantile_with_ci(sim["max_dd"], 0.95)
    loss_from_start = np.maximum(0.0, r.starting_equity - np.minimum(sim["cash"], r.starting_equity))
    breach_ok = breach_ci[1] <= tol
    dd_ok = dd95["ci95"][1] <= usable
    return {
        "n_paths": n,
        "p_pass_before_breach": round(npass / n, 6), "p_pass_ci95": [round(x, 6) for x in wilson_interval(npass, n)],
        "p_breach": round(nb / n, 6), "p_breach_ci95": [round(x, 6) for x in breach_ci],
        "p_unresolved": round(nun / n, 6), "p_unresolved_ci95": [round(x, 6) for x in wilson_interval(nun, n)],
        "p_capacity_exhausted": round(float(sim["halted"].mean()), 6),
        "max_drawdown_usd": {"p50": quantile_with_ci(sim["max_dd"], 0.50), "p95": dd95,
                             "p99": quantile_with_ci(sim["max_dd"], 0.99), "max": round(float(sim["max_dd"].max()), 2)},
        "final_loss_from_start_p95_usd": quantile_with_ci(loss_from_start, 0.95),
        "final_equity_usd": {"p05": round(float(np.quantile(sim["cash"], 0.05)), 2),
                             "p50": round(float(np.quantile(sim["cash"], 0.50)), 2),
                             "p95": round(float(np.quantile(sim["cash"], 0.95)), 2)},
        "positions_taken_mean": round(float(sim["taken"].mean()), 2),
        "sessions_used_mean": round(float(sim["sessions"].mean()), 2),
        "daily_stops_per_path_mean": round(float(sim["daily_stops"].mean()), 4),
        "loss_pauses_per_path_mean": round(float(sim["pauses"].mean()), 4),
        "acceptance": {
            "label": TOLERANCE_LABEL,
            "breach_tolerance": tol, "breach_upper_ci95": round(breach_ci[1], 6), "breach_within_tolerance": breach_ok,
            "usable_capacity_after_reserve_usd": usable, "drawdown_p95_upper_ci95": dd95["ci95"][1],
            "drawdown_p95_within_usable_capacity": dd_ok,
            "passed": bool(breach_ok and dd_ok),
        },
    }


def _evidence(evidence_label: str, input_is_synthetic: bool, iid: bool, n_obs: int, cfg: PilotConfig) -> dict:
    marked = any(m in evidence_label.upper() for m in _NON_EVIDENCE_MARKERS)
    refusal = None
    if iid:
        refusal = "IID_BASELINE_FROM_ASSUMED_PARAMETERS"
    elif input_is_synthetic:
        refusal = "SYNTHETIC_INPUT_OUTCOMES"
    elif marked:
        refusal = "EVIDENCE_LABEL_MARKS_NON_EVIDENCE_INPUT"
    out = {"evidence_label": evidence_label, "counts_as_evidence": refusal is None,
           "evidence_refusal_reason": refusal}
    if refusal is None and n_obs < cfg.evidence.min_positions:
        out["sample_warning"] = f"only {n_obs} observed positions (< {cfg.evidence.min_positions}); resampling cannot add information"
    return out


def _cost_terms(cfg: PilotConfig, scenario: str, outcomes_are_net: bool) -> tuple[float, float]:
    c, tv = cfg.costs, cfg.instrument.tick_value
    base_cost = c.round_trip_commission(1) + (c.spread_ticks + c.stop_slippage_ticks) * tv
    if scenario == "base":
        return (0.0 if outcomes_are_net else base_cost), base_cost
    doubled = base_cost if outcomes_are_net else 2 * base_cost
    return doubled + 2 * ADVERSE_TICKS_PER_SIDE * tv, base_cost


def _normalize_sessions(outcomes_r, group: int) -> tuple[list[list[float]], str]:
    if not outcomes_r:
        raise ValueError("outcomes_r is empty")
    if all(isinstance(x, (list, tuple, np.ndarray)) for x in outcomes_r):
        sessions = [[float(v) for v in s] for s in outcomes_r]
        mode = "SESSION_BLOCK_BOOTSTRAP"
    elif all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in outcomes_r):
        flat = [float(v) for v in outcomes_r]
        sessions = [flat[i:i + group] for i in range(0, len(flat), group)]
        mode = f"FLAT_SEQUENCE_GROUPED_INTO_PSEUDO_SESSIONS_OF_{group}"
    else:
        raise ValueError("outcomes_r must be a flat list of floats or a list of per-session lists")
    values = [v for s in sessions for v in s]
    if not values:
        raise ValueError("no observed positions in outcomes_r")
    if not all(math.isfinite(v) for v in values):
        raise ValueError("outcomes_r contains non-finite values")
    return sessions, mode


def _validate(scenario: str, n_paths: int, horizon: int, stop_ticks: int):
    if scenario not in BREACH_TOLERANCE:
        raise ValueError("scenario must be 'base' or 'adverse'")
    if n_paths < 1 or horizon < 1 or stop_ticks < 1:
        raise ValueError("n_paths, horizon_positions and stop_ticks must be >= 1")


def _header(cfg: PilotConfig, scenario: str, seed: int, n_paths: int, horizon: int, stop_ticks: int,
            outcomes_are_net: bool, profit_target: float | None, extra_cost: float, base_cost: float) -> dict:
    return {
        "label": TOLERANCE_LABEL, "scenario": scenario, "seed": seed, "n_paths": n_paths,
        "horizon_positions": horizon, "stop_ticks_assumed": stop_ticks,
        "unit_loss_usd": unit_loss_for(cfg, stop_ticks), "outcome_basis": "NET_R" if outcomes_are_net else "GROSS_R",
        "modeled_round_trip_cost_usd": round(base_cost, 2), "extra_cost_per_contract_usd": round(extra_cost, 2),
        "pass_definition": (f"equity reaches start + {profit_target} before breach" if profit_target is not None
                            else f"{horizon} positions completed without breach"),
        "breach_definition": f"realized equity <= floor {effective_floor(cfg)} (equality counts)",
        "config_hash": cfg.config_hash,
        "assumptions": [
            "review is logged before the next session after a loss-streak pause",
            "one position at a time; positions resolve within their session",
            "a fixed stop distance (stop_ticks_assumed) converts R to dollars",
            "a capacity-driven zero quantity is permanent (cash only changes through trades)",
            "acceptance judged on the upper 95% confidence bound",
        ],
    }


# ---------------------------------------------------------------------- public API
def run_stress(outcomes_r, cfg: PilotConfig, n_paths: int = 10_000, horizon_positions: int = 100,
               block_lengths: Sequence[int] = (1, 3, 5), scenario: str = "base", seed: int = 20260930, *,
               evidence_label: str, input_is_synthetic: bool = False, stop_ticks: int = 20,
               outcomes_are_net: bool = True, profit_target_usd: float | None = None,
               firm_contract_cap: int | None = None, firm_trade_limit: float | None = None,
               max_sessions: int | None = None) -> dict:
    """Block-bootstrap stress of observed outcomes (R) under the exact pilot sizing rules."""
    _validate(scenario, n_paths, horizon_positions, stop_ticks)
    sessions, mode = _normalize_sessions(outcomes_r, cfg.risk.max_entries_per_session)
    flat = [v for s in sessions for v in s]
    wins = sum(1 for v in flat if v > 0)
    losses = np.array([v for v in flat if v < 0] or [-1.0])
    p_obs = wins / len(flat)
    extra_cost, base_cost = _cost_terms(cfg, scenario, outcomes_are_net)
    adverse = scenario == "adverse"
    haircut = min(1.0, ADVERSE_WIN_PROB_SHIFT / p_obs) if (adverse and p_obs > 0) else 0.0
    block = np.array(worst_loss_block(flat)) if adverse else None
    max_sessions = max_sessions or horizon_positions * 50

    result = _header(cfg, scenario, seed, n_paths, horizon_positions, stop_ticks, outcomes_are_net,
                     profit_target_usd, extra_cost, base_cost)
    result.update(_evidence(evidence_label, input_is_synthetic, False, len(flat), cfg))
    result.update({"resampling": mode, "observed_positions": len(flat), "observed_sessions": len(sessions),
                   "observed_win_rate": round(p_obs, 4),
                   "adverse_adjustments": ({"win_prob_shift_pp": -100 * ADVERSE_WIN_PROB_SHIFT,
                                            "win_to_loss_conversion_prob": round(haircut, 4),
                                            "costs": "doubled", "adverse_ticks_per_side": ADVERSE_TICKS_PER_SIDE,
                                            "worst_loss_block_r": [round(x, 4) for x in block.tolist()],
                                            "worst_loss_block_sum_r": round(float(block.sum()), 4) if len(block) else 0.0}
                                           if adverse else None)})
    by_len = {}
    for L in block_lengths:
        if int(L) < 1:
            raise ValueError("block lengths must be >= 1")
        rng = np.random.default_rng([int(seed), int(L), _SCENARIO_CODE[scenario]])
        sampler = _SessionBlockSampler(sessions, int(L), n_paths)
        sim = _simulate(cfg, sampler, rng, n_paths=n_paths, horizon=horizon_positions, stop_ticks=stop_ticks,
                        extra_cost=extra_cost, win_haircut=haircut, loss_pool=losses, forced_block=block,
                        profit_target=profit_target_usd, firm_contract_cap=firm_contract_cap,
                        firm_trade_limit=firm_trade_limit, max_sessions=max_sessions)
        by_len[str(int(L))] = _summarize(sim, cfg, scenario, profit_target_usd)
    result["results_by_block_length"] = by_len
    result["acceptance"] = _overall(by_len)
    return result


def run_iid_baseline(win_rate: float, payoff_r: float, cfg: PilotConfig, n_paths: int = 10_000,
                     horizon_positions: int = 100, scenario: str = "base", seed: int = 20260930, *,
                     loss_r: float = -1.0, trades_per_session: int | None = None, stop_ticks: int = 20,
                     outcomes_are_net: bool = False, profit_target_usd: float | None = None,
                     evidence_label: str = "IID_BASELINE_ASSUMED_PARAMETERS", max_sessions: int | None = None) -> dict:
    """IID Bernoulli baseline from an ASSUMED win rate/payoff (gross R by default). Never evidence."""
    _validate(scenario, n_paths, horizon_positions, stop_ticks)
    if not 0 <= win_rate <= 1 or payoff_r <= 0 or loss_r >= 0:
        raise ValueError("need 0 <= win_rate <= 1, payoff_r > 0, loss_r < 0")
    slots = trades_per_session or cfg.risk.max_entries_per_session
    adverse = scenario == "adverse"
    p = max(0.0, win_rate - ADVERSE_WIN_PROB_SHIFT) if adverse else win_rate
    extra_cost, base_cost = _cost_terms(cfg, scenario, outcomes_are_net)
    result = _header(cfg, scenario, seed, n_paths, horizon_positions, stop_ticks, outcomes_are_net,
                     profit_target_usd, extra_cost, base_cost)
    result.update(_evidence(evidence_label, True, True, 0, cfg))
    result.update({"resampling": "IID_BERNOULLI_BASELINE", "assumed_win_rate": win_rate, "simulated_win_rate": p,
                   "payoff_r": payoff_r, "loss_r": loss_r, "trades_offered_per_session": slots,
                   "adverse_adjustments": ({"win_prob_shift_pp": -100 * ADVERSE_WIN_PROB_SHIFT, "costs": "doubled",
                                            "adverse_ticks_per_side": ADVERSE_TICKS_PER_SIDE,
                                            "worst_loss_block": "NOT_APPLICABLE_NO_OBSERVED_SEQUENCE"}
                                           if adverse else None)})
    rng = np.random.default_rng([int(seed), 0, _SCENARIO_CODE[scenario]])
    sim = _simulate(cfg, _IIDSampler(p, payoff_r, loss_r, slots, n_paths), rng, n_paths=n_paths,
                    horizon=horizon_positions, stop_ticks=stop_ticks, extra_cost=extra_cost, win_haircut=0.0,
                    loss_pool=np.array([loss_r]), forced_block=None, profit_target=profit_target_usd,
                    firm_contract_cap=None, firm_trade_limit=None, max_sessions=max_sessions or horizon_positions * 50)
    by_len = {"iid": _summarize(sim, cfg, scenario, profit_target_usd)}
    result["results_by_block_length"] = by_len
    result["acceptance"] = _overall(by_len)
    return result


def _overall(by_len: dict) -> dict:
    worst_breach = max(v["acceptance"]["breach_upper_ci95"] for v in by_len.values())
    worst_dd = max(v["acceptance"]["drawdown_p95_upper_ci95"] for v in by_len.values())
    return {"label": TOLERANCE_LABEL, "passed_all_block_lengths": all(v["acceptance"]["passed"] for v in by_len.values()),
            "worst_breach_upper_ci95": worst_breach, "worst_drawdown_p95_upper_ci95": worst_dd,
            "note": "Design tolerances for a paper pilot; not a guarantee of future results."}
