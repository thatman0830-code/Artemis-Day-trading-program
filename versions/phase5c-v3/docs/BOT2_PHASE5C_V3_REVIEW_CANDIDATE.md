# BOT 2.0 Phase 5C v3 — Review Candidate Record

Date: 2026-09-22
Branch: `bot2-phase5c-v-executable-controls`
Review candidate identity: the exact full Git SHA in the post-commit external anchor field `review_candidate_commit` (the repository cannot contain its own final commit SHA without changing that SHA). The anchor export is `C:\Users\fjone\Downloads\phase5c_v3_external_anchor_final.txt`.

## Frozen scientific identity

- Protocol version: `bot2-phase5c-experiment-manifest-v3`
- Canonical manifest SHA-256: `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`
- Dataset identity: `bot2-real-research-dataset-manifest-v2`
- Dataset manifest SHA-256: `e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67`
- Dataset date range: 2025-06-02 through 2026-08-26 inclusive
- Feature version: `bot2-feature-row-v3`
- Target version: `bot2-future-market-state-v3`
- Frozen protocol anchor commit: `9a1ecfaf08077252049dd187d44f8641da1186aa`
- Manifest changed: **No**

## Implementation identity and trust semantics

The preflight requires the running full `HEAD` to equal the anchor's full `review_candidate_commit`, verifies protocol-anchor ancestry, and requires a clean worktree. Ancestry alone is not accepted. The external export carries `signature_status: UNSIGNED` and `independent_custody_status: NOT_CRYPTOGRAPHICALLY_PROVEN`; it records a separate reference but does not claim authorship, signature, or proven custody. The external anchor is written only after commit so it can contain the exact commit without recursive self-reference.

## Gate state

- Exact-pin enforcement: exercised by positive/mismatch tests; clean commit preflight is run after anchor export.
- Dirty worktree: negative test rejects a modified tracked file; a restored clean tree is accepted.
- Full suite: 5,560 passed, 36 known common failures, 10 skipped; no candidate-only failures.
- Focused suite: 14 passed.
- A2 non-ALL ablation: intentionally fails closed because the frozen 24-channel architecture and feature-removal manifest lack a compatible mapping.
- Protected models scored: 0.
- Protected OOS execution: NOT AUTHORIZED.
- Trading authority: NONE.
- Production risk, broker, paper-order, and live execution behavior: unchanged.

## Review instruction

This record is a candidate handoff, not an approval. A separate independent reviewer must inspect this exact commit and its external anchor. The current implementation conclusion is **BLOCKERS REMAIN**. No Phase 5C v3 OOS or walk-forward scoring is authorized.
