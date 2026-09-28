# Supervised Paper Launch-Decision Contract — Independent Audit Report

**Audit assignment:** AUDIT-SUPERVISED-PAPER-LAUNCH-DECISION
**Checkpoint:** `da0d484efb015ffb63818962d0571e94b7f36c5f`
**Date:** 2026-09-01

## 1. Workspace verification

| Check | Value |
|---|---|
| Branch | `hermes/audit-lane` |
| Parent SHA | `ddf2b016afb2f3927aaebdf0e6d6751a443c2ffe` |
| Status | clean (only adversarial test untracked) |
| Remotes | none |

## 2. Uncommitted files audited

| File | Type | Filesystem SHA-256 |
|---|---|---|
| `execution/supervised_paper_launch_decision_v1.py` | new (untracked) | `ee962d2d…` |
| `execution/test_supervised_paper_launch_decision_v1.py` | new (untracked) | `8928a19d…` |

## 3. Baseline (primary repository)

| Suite | Result |
|---|---|
| Focused (decision) | 7 passed |
| Full repo | 4,184 passed, 5 skipped |

## 4. Adversarial tests (67 tests, all PASS)

- Acknowledgements (5): false/true, true/false, false/false, None/true, int supervision, int stop
- Evidence parsing (3): eligible, evidence_id preserved, checkpoint preserved
- Confirmation (3): ID SHA-256, checkpoint-bound, expires ≤5 min
- Determinism (2): identical produces identical, different as_of different envelope
- Envelope identity (2): SHA-256, tamper-evident
- Atomic output (2): no temp, valid JSON
- Ineligible evidence (8): stale, unhealthy watchdog, dirty repo, BTC not running, gaps, recovery drill unverified, stale alert unverified, authority true, future
- Limits (8): session 900s, commands 5, notional "100", gross "200", constants verified
- Eligible decision (8): BTC-only, advisory, live_trading false, trading false, no reasons, has expires, no expires ineligible, no markets ineligible
- No prohibited (5): no network, no credentials, no live, no task mutation, no workflow acquisition
- No false claims (6): no owner approval, no profitability, no OOS, no deployment, no unattended, no live readiness, advisory in docstring
- Direct construction (4): naive as_of, non-UTC as_of, no supervision, malformed evidence
- Envelope schema (4): version, envelope ID SHA-256, launch ID, confirmation ID
- Classification (3)

## 5. Post-adversarial results

| Suite | Result |
|---|---|
| Adversarial only | 67 passed in 0.84s |
| Focused (3 test files) | 45 passed in 0.10s |
| Execution | 957 passed, 4 skipped in 6.23s |
| git diff --check | clean |

## 6. Findings

**No production defects found.** All 67 adversarial tests pass.

## 7. Test disposition

- **Accepted unchanged:** 5 existing test functions (7 focused total)
- **Accepted after correction:** 1 (TestIneligibleEvidence — `_decision` helper called `_evidence` in default args, overwriting modified evidence; fixed to only create evidence if `evidence_path` not provided)
- **Redundant:** some overlap on acknowledgements, stale evidence, atomic output, no submission surface
- **Implementation-coupled:** 0
- **Incorrect or misleading:** 0

## 8. Security-boundary confirmation

- ✅ No scheduler mutation, session start, workflow acquisition, gateway execution, provider, credential, network, broker, exchange, signing, wallet, paper-order, live-order, or submission surface
- ✅ No owner-approval, profitability, OOS-success, deployment, unattended-readiness, or live-readiness claim
- ✅ Direct function calls and direct construction fail closed
- ✅ `live_trading_permitted=false` and `trading_authority=false` throughout
- ✅ No production files modified
- ✅ No external Hermes skills or memory accessed
- ✅ No merge, cherry-pick, rebase, amend, reset, push, stash, or history rewrite
- ✅ Filesystem SHA-256 computed without placeholders or self-reference
- ✅ Final `git status` clean

HERMES_SUPERVISED_PAPER_LAUNCH_DECISION_AUDIT_COMPLETE
