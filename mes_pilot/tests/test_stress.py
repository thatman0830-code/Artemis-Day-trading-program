"""Stress simulator: hand-computed deterministic paths, determinism, labelling.

With a 20-tick stop a -1R net outcome costs 20*1.25 = $25.00 per contract and
the sizing unit_loss is $30.45; a trade needs 0.05*C >= 30.45, i.e. C >= 609.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pytest

from mes_pilot.config import load_config
from mes_pilot.stress import (TOLERANCE_LABEL, _SessionBlockSampler, quantile_with_ci, run_iid_baseline, run_stress,
                              wilson_interval, worst_loss_block)


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def one(res, key="1"):
    return res["results_by_block_length"][key]


def test_all_losses_halt_on_capacity_not_floor(cfg):
    # C = 1400 - 25k; trades allowed while 0.05*C >= 30.45 -> k <= 31 -> 32 trades, cash 49,200.
    res = run_stress([-1.0] * 30, cfg, n_paths=200, block_lengths=(1, 3), seed=1, evidence_label="SYNTHETIC_UNIT")
    for key in ("1", "3"):
        m = one(res, key)
        assert m["positions_taken_mean"] == 32
        assert m["final_equity_usd"]["p50"] == pytest.approx(49200.0)
        assert m["max_drawdown_usd"]["p95"]["value"] == pytest.approx(800.0)
        assert m["p_breach"] == 0 and m["p_pass_before_breach"] == 0
        assert m["p_unresolved"] == 1 and m["p_capacity_exhausted"] == 1
        assert m["loss_pauses_per_path_mean"] == 10      # 10 full sessions of 3 losses
        assert m["sessions_used_mean"] == 11


def test_adverse_costs_hand_computed(cfg):
    # extra = doubled modeled cost (1.70 + 2 ticks*1.25 = 4.20) + 2 adverse ticks (2.50) = 6.70 -> loss 31.70
    # 1400 - 31.70k >= 609 -> k <= 24 -> 25 trades -> cash 50,000 - 792.50
    res = run_stress([-1.0] * 30, cfg, n_paths=100, block_lengths=(1,), scenario="adverse", seed=1,
                     evidence_label="SYNTHETIC_UNIT")
    assert res["extra_cost_per_contract_usd"] == pytest.approx(6.70)
    m = one(res)
    assert m["positions_taken_mean"] == 25
    assert m["final_equity_usd"]["p50"] == pytest.approx(49207.50)


def test_daily_stop_applied_on_every_path(cfg):
    # -2R = -$50: trades at day_net 0, -50, -100 (headroom 50 >= 30.45) -> -150 hits the stop each session.
    res = run_stress([-2.0] * 9, cfg, n_paths=50, block_lengths=(1,), seed=3, evidence_label="SYNTHETIC_UNIT")
    m = one(res)
    assert m["daily_stops_per_path_mean"] == 5          # 1400 - 50k >= 609 -> 16 trades: 5 full sessions + 1
    assert m["positions_taken_mean"] == 16


@pytest.mark.parametrize("r, breach", [(-60.0, 1.0), (-59.99, 0.0)])
def test_floor_breach_equality_counts(cfg, r, breach):
    # -60R = -$1,500 -> cash 48,500 == floor -> breach; -59.99R = -$1,499.75 -> 48,500.25, then capacity < 0.
    res = run_stress([r], cfg, n_paths=50, block_lengths=(1,), seed=4, evidence_label="SYNTHETIC_UNIT")
    m = one(res)
    assert m["p_breach"] == breach
    # Either way the path fails acceptance: a $1,499.75 drawdown exceeds the $1,400 usable capacity,
    # and 0 breaches in 50 paths still has a Wilson upper bound (~7%) above the 1% tolerance.
    assert m["max_drawdown_usd"]["p95"]["value"] == pytest.approx(-r * 25.0)
    assert m["acceptance"]["drawdown_p95_within_usable_capacity"] is False
    assert m["acceptance"]["breach_within_tolerance"] is False and m["acceptance"]["passed"] is False
    if not breach:
        assert m["p_capacity_exhausted"] == 1


def test_profit_target_pass_before_breach(cfg):
    res = run_stress([1.0] * 6, cfg, n_paths=50, block_lengths=(1,), seed=5, profit_target_usd=100.0,
                     evidence_label="SYNTHETIC_UNIT")
    m = one(res)
    assert m["p_pass_before_breach"] == 1 and m["positions_taken_mean"] == 4     # 4 x $25


def test_fixed_seed_is_deterministic_and_seed_matters(cfg):
    rng = np.random.default_rng(11)
    sessions = [list(np.where(rng.random(rng.integers(0, 4)) < 0.6, 1.3, -1.1)) for _ in range(40)]
    kw = dict(n_paths=1500, block_lengths=(1, 3, 5), scenario="adverse", evidence_label="SYNTHETIC_UNIT")
    a = run_stress(sessions, cfg, seed=123, **kw)
    b = run_stress(sessions, cfg, seed=123, **kw)
    c = run_stress(sessions, cfg, seed=124, **kw)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert json.dumps(a["results_by_block_length"], sort_keys=True) != json.dumps(c["results_by_block_length"], sort_keys=True)
    assert a["seed"] == 123 and set(a["results_by_block_length"]) == {"1", "3", "5"}


def test_tolerance_labelling_and_evidence_refusal(cfg):
    res = run_stress([1.0, -1.0, 1.0], cfg, n_paths=50, seed=1, evidence_label="WALK_FORWARD_LEDGER",
                     input_is_synthetic=True)
    assert res["label"] == TOLERANCE_LABEL and res["acceptance"]["label"] == TOLERANCE_LABEL
    assert one(res)["acceptance"]["label"] == TOLERANCE_LABEL
    assert res["evidence_label"] == "WALK_FORWARD_LEDGER"
    assert res["counts_as_evidence"] is False and res["evidence_refusal_reason"] == "SYNTHETIC_INPUT_OUTCOMES"

    marked = run_stress([1.0, -1.0], cfg, n_paths=20, seed=1, evidence_label="synthetic_replay")
    assert marked["counts_as_evidence"] is False

    real = run_stress([1.0, -1.0], cfg, n_paths=20, seed=1, evidence_label="WALK_FORWARD_LEDGER")
    assert real["counts_as_evidence"] is True and "sample_warning" in real

    iid = run_iid_baseline(0.65, 1.0, cfg, n_paths=50, seed=1, evidence_label="WALK_FORWARD_LEDGER")
    assert iid["counts_as_evidence"] is False and iid["evidence_refusal_reason"] == "IID_BASELINE_FROM_ASSUMED_PARAMETERS"


def test_iid_baseline_extremes(cfg):
    # Gross R basis: base cost 4.20 per trade. Always win 1R -> +20.80 per trade, 100 trades -> +2,080.
    res = run_iid_baseline(1.0, 1.0, cfg, n_paths=20, seed=2)
    m = res["results_by_block_length"]["iid"]
    assert m["positions_taken_mean"] == 100 and m["final_equity_usd"]["p50"] == pytest.approx(52080.0)
    assert m["p_pass_before_breach"] == 1
    adverse = run_iid_baseline(1.0, 1.0, cfg, n_paths=20000, seed=2, scenario="adverse")
    assert adverse["simulated_win_rate"] == pytest.approx(0.95)


def test_block_sampler_keeps_consecutive_sessions_within_a_block():
    sessions = [[float(i)] for i in range(10)]
    s = _SessionBlockSampler(sessions, block_len=4, n_paths=500)
    rng = np.random.default_rng(0)
    draws = np.stack([s.next(rng)[0][:, 0] for _ in range(8)], axis=1)
    for k in (1, 2, 3, 5, 6, 7):                    # positions inside a block of 4
        assert np.all(draws[:, k] == (draws[:, k - 1] + 1) % 10)


def test_statistics_helpers():
    lo, hi = wilson_interval(0, 10_000)
    assert lo == 0 and hi == pytest.approx(3.8415 / (10_000 + 3.8415), rel=1e-3)
    assert worst_loss_block([1.0, -1.0, -2.0, 0.5, -3.0, 2.0, -1.0]) == [-1.0, -2.0, 0.5, -3.0]
    assert worst_loss_block([1.0, 2.0]) == []
    q = quantile_with_ci(np.arange(1, 1001, dtype=float), 0.95)
    assert q["value"] == 951.0 and q["ci95"][0] < 951.0 < q["ci95"][1]


def test_input_validation(cfg):
    with pytest.raises(ValueError):
        run_stress([], cfg, evidence_label="x")
    with pytest.raises(ValueError):
        run_stress([1.0, float("nan")], cfg, evidence_label="x")
    with pytest.raises(ValueError):
        run_stress([1.0], cfg, scenario="optimistic", evidence_label="x")
    with pytest.raises(TypeError):
        run_stress([1.0], cfg)                       # evidence_label is mandatory


def test_full_size_run_is_fast(cfg):
    rng = np.random.default_rng(5)
    sessions = [list(np.where(rng.random(rng.integers(0, 4)) < 0.65, 1.2, -1.05)) for _ in range(80)]
    t = time.perf_counter()
    res = run_stress(sessions, cfg, n_paths=10_000, horizon_positions=100, block_lengths=(1, 3, 5),
                     scenario="adverse", seed=99, evidence_label="SYNTHETIC_UNIT", input_is_synthetic=True)
    assert time.perf_counter() - t < 15.0
    assert all(v["n_paths"] == 10_000 for v in res["results_by_block_length"].values())
