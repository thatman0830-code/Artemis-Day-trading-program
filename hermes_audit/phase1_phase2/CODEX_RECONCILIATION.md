# Codex Reconciliation — Hermes V2 Phase 1/2 Audit

Hermes commit reviewed: `5c8f65e76b25126bcbb62033077dc86727457a1e`.

The commit was inspected read-only and was not merged or cherry-picked. It contained exactly one
adversarial test file and seven `hermes_audit/phase1_phase2/` artifacts; no production file changed.
The external Hermes skill modification reported after the audit was not opened, copied, relied on,
or modified.

## Test-group disposition

| Group | Disposition | Reconciliation |
|---|---|---|
| Phase 1 contract immutability | Accepted unchanged | Public frozen/slotted records. |
| Decimal-only enforcement | Accepted after correction | Removed private validator import; expanded non-finite checks through public constructors. |
| Timezone rejection | Accepted unchanged | Claims narrowed to representative tests plus shared-validator inspection. |
| Schema versions | Accepted unchanged | Public constructors. |
| Specification intervals | Accepted unchanged | Public validator, boundary-focused. |
| Evidence checksums | Accepted unchanged | Temporary local files only. |
| Mixed schema/ledger versions | Accepted unchanged | Public eligibility APIs. |
| Synthetic-fixture leakage | Accepted unchanged | Public eligibility APIs. |
| Eligibility blocker coverage | Accepted unchanged | BTC spot audit count corrected from four to five. |
| Deterministic serialization | Accepted unchanged | Public serialization/fingerprint APIs. |
| SHA-256 identity | Accepted unchanged | Public constructors. |
| Order type/TIF validation | Accepted unchanged | Public constructors. |
| Grid validation | Accepted unchanged | Public validators. |
| Repository provenance | Accepted unchanged | Public repository/validator APIs and temporary files. |
| State graph versus matrix | Accepted unchanged | `ALLOWED_TRANSITIONS` is an exported public Phase 2 contract. |
| Terminal immutability | Accepted after correction | Removed unused duplicate parametrization; requires exact terminal reason. |
| Quantity conservation | Accepted unchanged | Public ledger behavior. |
| Cancellation/fill ordering | Accepted unchanged | Public ledger behavior. |
| Replacement lineage | Accepted unchanged | Public ledger behavior. |
| Duplicate/conflicting events | Accepted unchanged | Public ledger behavior. |
| Stale versions/identity | Accepted unchanged | Public ledger behavior. |
| Equal-timestamp ordering | Accepted after correction | Requires `EVENT_SEQUENCE_REGRESSION`, not any ledger error. |
| DAY/GTC/IOC constraints | Accepted unchanged | Phase 2 lifecycle scope; Phase 3 independently gates executable bars. |
| Stop trigger/fill separation | Accepted unchanged | Public ledger behavior and compatible with Phase 3. |
| Checkpoint/replay | Accepted unchanged | Public checkpoint and replay APIs. |
| Mixed v1/v2 ledger rejection | Accepted unchanged | Public API. |
| Forced-close intent | Accepted unchanged | Public lifecycle fact only. |
| End-of-data validation | Accepted unchanged | Public API. |
| Negative transition coverage | Rejected as redundant/misleading | Three tests duplicated baseline cases while the unused table claimed exhaustive coverage. |
| Repeated deterministic output | Accepted unchanged | Repeated public lifecycle replay provides useful adversarial stability coverage. |

No group was retained solely through a private helper import. No production change was made to make
an audit assertion pass.

Integrated adversarial test SHA-256:
`f95d288cf9746dafb8605264fbc2b3ae9ffd381ff409531403bbcb1f877919d7`.

The original audit source checksums were independently recomputed against the audited Windows
worktree and all seven matched. They cover CRLF working-tree bytes rather than normalized Git blob
bytes; `FILE_CHECKSUMS.json` now states that scope explicitly. The original committed adversarial
test checksum also recomputed successfully.

## Security and isolation

The integrated tests use no network, credentials, archives, collectors, schedulers, exchange
clients, OOS data, or provider access. They use deterministic in-memory records and pytest temporary
directories only.

## Phase 3 boundary

The audit authenticates Phase 1 contracts/validation and Phase 2 ledger behavior at checkpoint
`76fdc05`. It does not independently audit Phase 3 OHLC touch logic, price rules, collision handling,
volume allocation, or fill lineage. That remains the next Hermes audit boundary.

## Integrated verification

- Corrected Hermes adversarial file: `158 passed in 1.30s`.
- Complete `execution_accounting_v2` suite including Phase 3: `219 passed in 1.43s`.
- Full offline repository suite: `1349 passed in 45.15s`.
- `git diff --check`: passed.
