# Phase 7 Invariant Matrix

| Invariant | Enforcement |
|---|---|
| Decimal-only economics | Every economic input passes finite `Decimal` validation |
| Exact cost reconciliation | Gross minus costs plus signed funding equals net |
| Final chronology | UTC close strictly follows open; snapshot excludes future closes |
| Scope isolation | Run, market, instrument and evidence partition must match |
| No blended headline | Promotion accepts `UNTOUCHED_OOS` metrics only |
| Partition registry | Reject source relabeling and cross-partition interval overlap |
| Point-in-time regime | `known_at <= effective_from`; exactly one label per trade |
| Cross-ledger lineage | Eight distinct immutable component fingerprints |
| Upstream finality | Any unresolved identity makes reconciliation incomplete |
| Promotion evidence | >=200 untouched-OOS finalized trades per market |
| Required stress evidence | Explicit required stress/ruin inputs fail closed when absent |
| Economic quality | Positive expectancy, all R:R >=1, every hurdle passes |
| Advisory boundary | Promotion record has `advisory_only=True`; no execution API |
| Determinism | Canonical ordering and content-addressed records |
| Tamper detection | Result identity recomputes from all result lineage |
| Stress reproducibility | Explicit versioned inputs; empirical ruin uses explicit paths |
