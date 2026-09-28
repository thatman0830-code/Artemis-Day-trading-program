# Supervised Paper-Trading Launch Gate — Independent Audit Report

**Audit assignment:** AUDIT-SUPERVISED-PAPER-LAUNCH-GATE
**Checkpoint:** `dcb37600fa98a59db0cb8ea686eaa0e3ee2761e2`
**Date:** 2026-09-01

## 1. Workspace verification

| Check | Value |
|---|---|
| Branch | `hermes/audit-lane` |
| Parent SHA | `95695dedcc455b6f4efa5661899808715efc4948` |
| Status | clean (only adversarial test untracked) |
| Remotes | none |

## 2. Uncommitted files audited

| File | Type | Filesystem SHA-256 |
|---|---|---|
| `execution/supervised_paper_launch_gate_v1.py` | new (untracked) | `16970977…` |
| `execution/test_supervised_paper_launch_gate_v1.py` | new (untracked) | `7338e562…` |

## 3. Baseline (primary repository)

| Suite | Result |
|---|---|
| Focused (launch gate) | 25 passed |
| Full repo | 3,921 passed, 5 skipped |

## 4. Adversarial tests (74 tests, all PASS)

- Advisory only (5): advisory_only, live_trading_permitted, trading_authority, policy TA rejects, facts TA rejects
- Eligibility gates (6): dirty repo, checkpoint mismatch, stale evidence, future evidence, future heartbeat, watchdog
- BTC health (5): not running, not healthy, stale 91s, 90s boundary, gaps
- ES/NQ health (3): not ready, result nonzero, missed runs
- Drill results (4): recovery unverified, stale alert unverified, unhealthy not delivered, healthy not delivered
- Clock skew (4): +3, -3, +2 boundary, -2 boundary
- Supervision (2): no supervision, no stop control
- Ineligible (2): no expiry, no markets
- Reasons (2): unique sorted, deterministic
- Permit expiry (1): 5 minutes
- Hard ceilings (14): session 30m, commands 10, notional 500, gross 800, over each rejects, permit 5m, evidence 5m, BTC-only, non-BTC rejects, zero commands, bool commands, zero notional
- Immutable (5): decision, policy, facts, launch_id SHA-256, schema version
- No prohibited (5): no network, no credentials, no live, no task mutation, no paper submission
- No false claims (5): no profitability, no OOS, no deployment, advisory in docstring, no unattended
- Facts validation (6): naive observed_at, naive heartbeat, invalid checkpoint, negative gap, bool gap, bool skew
- Eligible decision (1): all fields correct
- Classification (3)

## 5. Post-adversarial results

| Suite | Result |
|---|---|
| Adversarial only | 74 passed in 0.07s |
| Focused (6 test files) | 83 passed in 1.47s |
| Execution | 701 passed, 4 skipped in 6.55s |
| git diff --check | clean |

## 6. Findings

**No production defects found.** All 74 adversarial tests pass.

## 7. Test disposition

- **Accepted unchanged:** 6 existing tests (25 focused total)
- **Accepted after correction:** 0
- **Redundant:** some overlap on eligibility gates, hard ceilings, future evidence, no network
- **Implementation-coupled:** 0
- **Incorrect or misleading:** 0

## 8. Security-boundary confirmation

- ✅ No provider, credential, network, process, scheduled-task, recorder-control, exchange, wallet, broker, signing, paper-submission, or live-submission surface
- ✅ Advisory-only — cannot submit an order
- ✅ `live_trading_permitted=False`, `trading_authority=False` always
- ✅ No profitability, OOS success, deployment approval, or unattended-operation claim
- ✅ No production files modified
- ✅ No external Hermes skills or memory accessed
- ✅ No merge, cherry-pick, rebase, amend, reset, push, stash, or history rewrite
- ✅ Filesystem SHA-256 computed without placeholders or self-reference
- ✅ Final `git status` clean

HERMES_SUPERVISED_PAPER_LAUNCH_GATE_AUDIT_COMPLETE
