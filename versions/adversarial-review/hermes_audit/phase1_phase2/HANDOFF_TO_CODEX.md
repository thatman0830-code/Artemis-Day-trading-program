# Handoff to Codex — AUDIT-V2-PHASE1-PHASE2

## Status

Hermes independently audited V2 Phase 1 (contracts/validation) and Phase 2 (order ledger).

**Verdict: HERMES_ACCEPTED_V2_PHASE1_PHASE2**

No production code defects were found. All 209 tests pass (49 existing + 160 new adversarial).

## What was done

1. Verified workspace: branch `hermes/audit-lane`, HEAD `76fdc05`, clean, no remote, no runtime state.
2. Read all production inputs: contracts.py, specifications.py, validation.py, eligibility.py, order_ledger.py, REASON_CODES.json, __init__.py, existing tests, design docs, transition matrix, reports.
3. Ran baseline V2 suite: 49 passed.
4. Derived the complete state-transition graph from `ALLOWED_TRANSITIONS` in order_ledger.py:228-245 and compared with the frozen matrix in ORDER_LEDGER_TRANSITION_MATRIX.md — exact match.
5. Wrote 160 adversarial tests addressing the Phase 1 and Phase 2 audit requirements. Some groups
   intentionally overlap baseline invariants; the original file did not provide exhaustive runtime
   coverage of every disallowed transition edge.
6. Ran adversarial tests: 160 passed.
7. Ran complete focused V2 suite: 209 passed.
8. Committed audit artifacts and adversarial test file to `hermes/audit-lane`.

## Files committed

- `hermes_audit/phase1_phase2/AUDIT_REPORT.md`
- `hermes_audit/phase1_phase2/FINDINGS.json`
- `hermes_audit/phase1_phase2/CONTRACT_INVARIANT_MATRIX.json`
- `hermes_audit/phase1_phase2/ORDER_TRANSITION_COVERAGE.json`
- `hermes_audit/phase1_phase2/TEST_RESULTS.md`
- `hermes_audit/phase1_phase2/FILE_CHECKSUMS.json`
- `hermes_audit/phase1_phase2/HANDOFF_TO_CODEX.md`
- `backtesting/execution_accounting_v2/test_hermes_phase1_phase2_adversarial.py`

## No production code changes

No production source, existing tests, design documents, evidence, manifests, or Git configuration were modified.

## Original integration readiness

The `hermes/audit-lane` branch is NOT integration-ready. It contains audit artifacts and adversarial tests only. Codex should review the findings (none) and decide whether to promote the adversarial test file into the primary branch.

Codex subsequently performed that review without merging or cherry-picking the commit. The accepted
tests and artifacts were copied selectively and corrected as recorded in
`CODEX_RECONCILIATION.md`.

## Key observations for Codex

1. The implementation matches the frozen transition matrix exactly.
2. All contracts are frozen+slots, Decimal-only, UTC-only.
3. The `_precise_reason` function in eligibility.py:79-88 remaps some reason codes (e.g., SLIPPAGE → MISSING_EXECUTION_COST_SPEC, CLEARING_MARGIN → MISSING_MARGIN_SPEC). This is a design choice, not a defect.
4. IOC full fill sets `ioc_evaluated=True` even though no residual cancellation occurs (order_ledger.py:485-488). This is correct — the evaluation happened.
5. `FILL` and `EXECUTION_EVALUATED` share priority 60 in `EVENT_PRIORITY`. Equal-timestamp ordering between them falls to lexical `event_id`. This is consistent with the frozen matrix.
6. `stop_limit` fill must be strictly after trigger event time (`event.event_time > snapshot.last_event_time`), not equal-or-after (order_ledger.py:473-476).

## Commit

See the exact commit SHA in the audit report or `git log` on `hermes/audit-lane`.
