---
title: Identity — Versioning Policy
governing_amendments: ["002-R2"]
---

# Identity / Versioning Policy (Amendment 002 R2)

- IDs are **opaque and immutable**.
- Finalized records are **append-only**.
- Distinct version fields (do not conflate):
  - `source_version` — version of the upstream source data set.
  - `calculation_version` — version of the analytical calculation logic.
  - `historical_version` — version in the correction/append lineage of a record.
- **Correction lineage is authoritative.** A superseded prior record version is **not** a duplicate when version semantics make only one version authoritative. Analytics may **not** choose authoritative versions themselves.
- `portfolio_id + portfolio_version` identifies the exact portfolio definition. v1 statistics never silently become v2.

See [[Amendment 002]], [[#29.7.2.16 Portfolio-Level Aggregation]].
