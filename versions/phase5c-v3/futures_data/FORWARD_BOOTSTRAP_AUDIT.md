# ES/NQ Forward Bootstrap Audit

The earlier completion report covered the delayed collector, wrappers, DPAPI boundary, and tests, but left generation of `config/es_nq_forward_sessions.json` as an unmet prose prerequisite. The installer therefore existed without its required immutable input.

The correction derives the bootstrap from `data/backtests/es_nq_pass_b_plan_3/{calendar,rollovers,plan}.json`, their artifact manifest, and `outputs/archive_audits/es_nq_pass_b_final_audit.json`. Every listed source and all archive audit artifact links are rehashed before generation. The generated configuration records 313 archived sessions for ES and 313 for NQ, links the verified archive tree, freezes coverage as `[2025-06-02, 2026-08-27)`, and has zero pending downloads. No date after the retained 2026-08-26 session is present.

Artifacts:

- `config/es_nq_forward_sessions.json`
- `config/es_nq_forward_sessions.manifest.json`
- `outputs/futures_forward/bootstrap_audit.json`

Reference advancement is implemented as a separate raw-first, capped, non-retrying producer. It accepts only authoritative schedule and exact XCME outright contract evidence and creates a new content-addressed configuration version. Rollover overlap may be prepared, but no rollover is finalized without the existing completed-volume evidence rule.

This work authorizes neither Task Scheduler installation nor provider access, collection, trading, or BTC-recorder control.
