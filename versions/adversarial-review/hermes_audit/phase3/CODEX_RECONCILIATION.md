# Codex Reconciliation — Hermes Phase 3 Audit

Hermes commit reviewed: `5f1c8843cae626b43a15f1cde37a19748d7be883`.
Starting checkpoint: `b2711098c0f9777e52af63e7d41b313f64cc9dc1`.

The commit contained exactly one adversarial test file and seven `hermes_audit/phase3/` artifacts.
It modified no production source. No Hermes skill, memory, or external file was inspected, relied on,
or modified.

## Signal-bar conclusion

Hermes OBS-001 was incorrect. Frozen decision D01 says a decision using finalized bar `t` cannot
fill on `t`; the truth table explicitly makes a signal/threshold on the same source bar ineligible.
The old comparison `activation_at > bar.open_time` could not prove this ownership boundary because
equal timestamps did not identify the source market event.

The smallest compatible correction is additive `ExecutionSourceLineageV2`. Its canonical SHA-256
binds the complete finalized source bar, strategy `action_id`, `order_id`, exact Phase 2 activation
event ID, and activation time. Evaluation independently verifies:

- source and evaluated market/instrument/contract/dataset identities;
- exactly one matching ledger activation event;
- activation not before the immutable order activation time;
- order submission not before source availability;
- source bar identity differs from evaluated bar identity; and
- source close/availability is no later than the evaluated bar open.

Missing or conflicting lineage fails with `SOURCE_LINEAGE_UNPROVEN`; identical source/evaluated bar
identity fails with `SAME_SOURCE_BAR_INELIGIBLE`. Therefore equal activation/open timestamps remain
eligible only for a proven distinct prior finalized bar.

## Test-group disposition

| Hermes group | Count | Disposition | Rationale |
|---|---:|---|---|
| Market orders | 17 | Accepted after correction | Replaced two timestamp-only claims and added prior-bar, same-source, identity, missing-lineage, late-availability, and first-later-bar cases. |
| Limit orders | 11 | Accepted unchanged semantically | Independent touch/gap/no-improvement and symmetry coverage; shared fixture gained required lineage. |
| Stop-market orders | 8 | Accepted unchanged semantically | Independent gap/threshold/no-trigger and symmetry coverage; shared fixture gained required lineage. |
| Stop-limit orders | 8 | Accepted unchanged semantically | Direct trigger/fill separation and persistence coverage; shared fixture gained required lineage. |
| Intrabar collisions | 5 | Accepted unchanged semantically | Public collision API and fail-closed ownership coverage. |
| Tick rounding and costs | 9 | Accepted unchanged semantically | Exact Decimal adverse rounding and friction facts; no Phase 4 behavior assumed. |
| Participation | 12 | Accepted unchanged semantically | Shared-budget conservation, priority, tie-break, and missing/zero-volume boundaries. |
| IOC and lifecycle | 10 | Accepted unchanged semantically | Public ledger transitions, cancellation finality, and immutable lineage. |
| Determinism and replay | 47 | Accepted unchanged semantically | Public constructors/ledger APIs, schema rejection, replay, fingerprint, tamper, and immutability contracts. |

Rejected as redundant: none. Rejected as implementation-coupled: none. Rejected as incorrect: the
two original timestamp-only market assertions were not retained; their corrected replacements are
counted above. The test module imports no private helper and has no network, credential, archive,
collector, scheduler, exchange, or out-of-sample access.

## Artifact corrections

`FINDINGS.json`, `AUDIT_REPORT.md`, `HANDOFF_TO_CODEX.md`, and `TEST_RESULTS.md` were corrected so
they no longer claim zero defects or timestamp-only eligibility. `FILE_CHECKSUMS.json` contains
actual SHA-256 values for every listed production/test/audit artifact. The checksum inventory itself
is explicitly excluded from self-hashing because embedding its own digest has no stable fixed point.
