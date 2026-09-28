# Audit Report — AUDIT-V2-PHASE1-PHASE2

## Summary

**Assignment:** Independent audit of V2 Phase 1 contracts/validation and Phase 2 order ledger.
**Auditor:** Hermes Agent (independent; Codex remains primary implementer).
**Date:** 2026-08-27 (US Mountain Standard Time, UTC-07:00)
**Workspace:** `C:\Users\fjone\hyperliquid-trading-bot-hermes` (Hermes worktree)
**Branch:** `hermes/audit-lane`
**HEAD:** `76fdc05cf0b587e874bcb24bf2f0788e82de7a55`

## Workspace verification

- Current working directory: `C:/Users/fjone/hyperliquid-trading-bot-hermes` ✓
- Branch: `hermes/audit-lane` ✓
- HEAD: `76fdc05cf0b587e874bcb24bf2f0788e82de7a55` ✓
- Git status: clean (no untracked or modified files before audit work) ✓
- No Git remote configured ✓
- No `.env`, `.env.txt`, `.envt`, `data/`, `outputs/`, `logs/`, `*.db`, `*.lock` present ✓

## Scope

### Production inputs inspected (read-only)

| File | SHA-256 |
|---|---|
| `contracts.py` | `f4a9811a…` |
| `specifications.py` | `8f17e909…` |
| `validation.py` | `d06455d5…` |
| `eligibility.py` | `506be2ad…` |
| `order_ledger.py` | `1a973da6…` |
| `REASON_CODES.json` | `7183c1cb…` |
| `__init__.py` | `995943d7…` |
| Existing test files (3) | inspected |
| Design docs (2) | inspected |

### Permitted writes

- `hermes_audit/phase1_phase2/**` (7 artifacts)
- `backtesting/execution_accounting_v2/test_hermes_phase1_phase2_adversarial.py` (1 new test file)

No production source, existing tests, design documents, evidence, manifests, or Git configuration were modified.

## Phase 1 audit results

### Contract inventory and immutability

Every Phase 1 contract is a `@dataclass(frozen=True, slots=True)`:

- `InstrumentSpecificationV2` (contracts.py:94-131)
- `OwnerAssumptionV2` (contracts.py:133-165)
- `CapabilityDeclarationV2` (contracts.py:168-197)
- `OrderIntentV2` (contracts.py:200-258)
- `OrderTransitionV2` (contracts.py:261-284)
- `FillV2` (contracts.py:287-322)
- `AccountingSnapshotV2` (contracts.py:325-359)
- `RiskEventV2` (contracts.py:362-389)
- `BacktestResultIdentityV2` (contracts.py:392-425)
- `EvidenceRecord` (specifications.py:94-127)
- `SpecificationRecord` (specifications.py:129-161)
- `SpecificationRepository` (specifications.py:197-220)

**Mutation resistance:** VERIFIED. All 12 dataclass types raise `FrozenInstanceError` on attribute assignment.

### Decimal-only economic fields

Every economic field uses `Decimal` and rejects `float`, `int`, and non-finite values via `_finite_decimal`, `_positive`, and `_nonnegative` validators. The `canonical_fingerprint` function explicitly raises `ValueError` on float inputs (specifications.py:182-183).

**Float/integer leakage:** VERIFIED by validator inspection and representative public-contract
coverage. The original adversarial file also called one private validator directly; reconciliation
replaced that coupling with public constructor checks.

### Timezone-naive timestamp rejection

All datetime fields validate timezone-aware UTC via `_utc` (specifications.py:79-81), which checks `tzinfo`, `utcoffset()`, and verifies offset equals zero.

**Timezone-naive rejection:** VERIFIED by shared validator inspection and representative contract
coverage. The tests do not independently instantiate every possible datetime field with every bad
timezone variant.

### Specification interval gaps and overlaps

`validate_specification_intervals` (validation.py:128-160) correctly detects:
- Gaps: required interval with no covering specification
- Overlaps: two specifications covering the same sub-interval
- Half-open semantics: `[effective_from, effective_to)` — adjacent intervals do not gap or overlap

**Interval validation:** VERIFIED. Gap, overlap, adjacency, open-ended, and triple-contiguous cases all tested.

### Stale, conflicting, and checksum-invalid evidence

`validate_evidence_checksum` (validation.py:106-125) validates:
- File existence and path containment (no path escape)
- SHA-256 checksum match (stale file detection)
- Missing file detection

**Evidence integrity:** VERIFIED. Valid, stale, missing, and path-escape cases all tested.

### Mixed schema/ledger versions

Both `evaluate_production_eligibility` and `evaluate_production_interval` accept a `ledger_schema_version` parameter and reject non-v2 values with `MIXED_LEDGER_VERSION`.

**Mixed version rejection:** VERIFIED.

### Synthetic-fixture leakage

Synthetic specifications (`synthetic_test_only=True`) cannot pass production eligibility:
- `SpecificationRecord.__post_init__` rejects `synthetic_test_only and owner_approved`
- `evaluate_production_eligibility` checks `synthetic_test_only or not item.owner_approved`
- `evaluate_production_interval` checks the same for each covering specification

**Synthetic isolation:** VERIFIED. Synthetic fixtures cannot leak to production eligibility.

### Eligibility reports return all applicable blockers

- ES_FUTURE with empty repo: 9 issues (9 required spec types)
- NQ_FUTURE with empty repo: 9 issues
- BTC_SPOT with empty repo: 5 issues (INSTRUMENT, FEE_TIER, SLIPPAGE, PARTICIPATION, RISK_LIMITS — `_precise_reason` remaps some)
- BTC_LINEAR_PERPETUAL with empty repo: 9 issues (INSTRUMENT + 7 historical + SLIPPAGE/PARTICIPATION/RISK_LIMITS)
- BTC_UNKNOWN_UNSUPPORTED: 1 issue (INSTRUMENT_PROFILE_UNPROVEN)

**Blocker coverage:** VERIFIED. All applicable blockers are returned for every profile.

### Deterministic serialization and fingerprints

`canonical_fingerprint` (specifications.py:187-194) uses:
- `json.dumps(..., sort_keys=True, separators=(",",":"), ensure_ascii=True)`
- Decimal normalization: `value.normalize()` with `"0"` for zero
- Enum `.value` extraction
- datetime ISO format with `+00:00` → `Z` replacement

**Determinism:** VERIFIED. Equal records produce equal fingerprints; repeated construction produces identical serialization.

## Phase 2 audit results

### State-transition graph: implementation vs. frozen matrix

The `ALLOWED_TRANSITIONS` dict (order_ledger.py:228-245) defines the complete state-transition graph. I derived the full graph from the implementation and compared it with the frozen matrix in `ORDER_LEDGER_TRANSITION_MATRIX.md`.

**Match:** VERIFIED. The implementation's `ALLOWED_TRANSITIONS` exactly matches the frozen matrix:
- 7 nonterminal states with outgoing edges
- 5 terminal states with no outgoing edges
- Every (state, event) combination has a deterministic boolean answer

### Terminal-state immutability

Terminal states (`FILLED`, `REJECTED`, `CANCELLED`, `EXPIRED`, `REPLACED`) reject all events:
- `FILLED`: `TERMINAL_ORDER_MUTATION`
- `REJECTED`: `TERMINAL_ORDER_MUTATION`
- `CANCELLED`: `CANCELLED_ORDER_FILL` for fill, `TERMINAL_ORDER_MUTATION` for others
- `EXPIRED`: `TERMINAL_ORDER_MUTATION`
- `REPLACED`: `REPLACED_ORDER_FILL` for fill, `TERMINAL_ORDER_MUTATION` for others

**Terminal immutability:** VERIFIED.

### Zero fills, overfills, and quantity conservation

- Zero and negative fill quantities: `ZERO_FILL_QUANTITY` (order_ledger.py:478-479)
- Overfill (quantity > remaining): `ORDER_OVERFILL` (order_ledger.py:480-481)
- Quantity conservation: `accepted == filled + remaining` checked in every transition (order_ledger.py:530) and every snapshot (order_ledger.py:203-204)
- `verify_integrity` re-checks all conservation invariants (order_ledger.py:313-315)

**Quantity conservation:** VERIFIED. Zero fill, overfill, partial fill, exact completion, and multiple partial fills all tested.

### Cancellation / fill ordering

- Fill then cancel: preserves filled quantity
- Cancel then fill: rejected with `CANCELLED_ORDER_FILL`
- Fill in `CANCEL_REQUESTED` state: allowed (results in `PARTIALLY_FILLED`)

**Cancellation ordering:** VERIFIED.

### Replacement lineage after partial fill

- `REPLACE` creates a child `OrderLedgerSnapshotV2` in `CREATED` state
- Parent transitions to `REPLACED` with `replacement_child_order_id` set
- Parent transition history is preserved (not truncated)
- Child must have `parent_order_id` and `replaces_order_id` linking to parent
- Replacement quantity must not exceed parent's remaining quantity
- Replaced parent rejects future fills with `REPLACED_ORDER_FILL`

**Replacement lineage:** VERIFIED.

### Duplicate and conflicting event identities

- Exact duplicate event (same `event_id`, same content): idempotent — returns same ledger
- Conflicting (same `event_id`, different content): `DUPLICATE_EVENT_CONFLICT`
- Duplicate event at incompatible state: `INVALID_ORDER_TRANSITION`

**Duplicate handling:** VERIFIED.

### Stale expected versions

- `expected_order_version` must match `snapshot.order_version`
- Stale version: `STALE_ORDER_VERSION`
- Wrong identity: `ORDER_IDENTITY_MISMATCH`

**Stale version detection:** VERIFIED.

### Equal-timestamp deterministic ordering

Events at the same timestamp are ordered by:
1. `EVENT_PRIORITY[kind]` (order_ledger.py:33-46)
2. `event_id` (lexical SHA-256)

If `(priority, event_id)` of the current event ≤ that of the previous event, `EVENT_SEQUENCE_REGRESSION` is raised.

**Equal-timestamp ordering:** VERIFIED. Priority then identity; time regression and sequence regression both rejected.

### DAY, GTC, and IOC constraints

- **DAY**: `EXPIRE` requires `session_boundary_verified=True` or raises `SESSION_BOUNDARY_UNPROVEN`; DAY fills do NOT require `contract_eligibility_verified`
- **GTC**: `FILL`, `TRIGGER`, `EXECUTION_EVALUATED`, and `EXPIRE` all require `contract_eligibility_verified=True` or raise `CONTRACT_ELIGIBILITY_UNPROVEN`
- **IOC**: First fill evaluates and cancels residual; `EXECUTION_EVALUATED` cancels if no fill; double evaluation raises `IOC_ALREADY_EVALUATED`; full fill sets `ioc_evaluated=True` without cancelling

**TIF constraints:** VERIFIED.

### Stop-limit trigger/fill separation

- `STOP_MARKET` and `STOP_LIMIT` require `TRIGGER` before `FILL` (or `STOP_NOT_TRIGGERED`)
- `STOP_LIMIT` fill time must be strictly after trigger event time (order_ledger.py:473-476)
- Non-stop orders reject `TRIGGER` with `INVALID_ORDER_TRANSITION`

**Stop-limit separation:** VERIFIED.

### Checkpoint / replay equivalence and tamper detection

- `checkpoint()` returns `LedgerCheckpointV2` with fingerprint
- `resume()` verifies checkpoint then replays new events
- `replay()` from root intents produces byte-identical serialization
- Tampered `ledger_fingerprint` detected by `verify_integrity()`
- Reordered events rejected by sequence/time regression
- Repeated replay (5×) produces identical serialization

**Checkpoint/replay:** VERIFIED. Equivalence, tamper detection, and repeated determinism all confirmed.

### Mixed v1/v2 rejection

- `OrderLedgerV2.create()` with `ledger_version="order-ledger-v1"`: `MIXED_LEDGER_VERSION`
- `OrderLedgerEventV2` with wrong `schema_version`: rejected at construction

**Mixed version rejection:** VERIFIED.

### Deterministic output comparison

- 10× full lifecycle: identical serialization
- 10× IOC lifecycle: identical serialization
- Repeated fingerprint construction: stable

**Deterministic output:** VERIFIED.

## Phase 2 economic boundary

At the audited checkpoint, Phase 2 did not economically match OHLC bars. The ledger validates fill quantities and lifecycle eligibility but does not:
- Inspect OHLC data
- Decide whether a touch occurred
- Choose a fill price
- Generate fills from market data
- Calculate costs, PnL, margin, or funding
- Liquidate positions

`intrabar_owner` is metadata only. The conservative OHLC collision policy belongs to Phase 3. Phase
3 was implemented later on `main` and was not part of this independent audit.

## Codex reconciliation note

The original 160-test audit result is preserved as historical evidence. Codex integrated 158 tests:
three targeted negative-transition tests were rejected as redundant and misleadingly labeled
exhaustive; an unused two-case terminal parametrization was collapsed; public non-finite coverage
was expanded; and equal-time rejection now asserts the exact frozen reason. No production defect or
production behavior change resulted from reconciliation.

## Findings

No production code defects were found. All 209 tests pass (49 existing + 160 adversarial).

## Verdict

HERMES_ACCEPTED_V2_PHASE1_PHASE2
