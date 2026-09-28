# V2 Phase 1 Stable Reason Codes

| Code | Meaning |
|---|---|
| `MISSING_INSTRUMENT_SPEC` | No authoritative instrument record covers the interval. |
| `MISSING_BROKER_COMMISSION_SPEC` | Owner broker commission is absent. |
| `MISSING_EXECUTION_COST_SPEC` | Required exchange fee or slippage specification is absent. |
| `MISSING_PARTICIPATION_SPEC` | Owner participation policy is absent. |
| `MISSING_RISK_LIMIT_SPEC` | Required owner risk inputs are absent. |
| `MISSING_SESSION_SPEC` | Verified session facts do not cover the interval. |
| `MISSING_MARGIN_SPEC` | Required clearing/perpetual margin specification is absent. |
| `MISSING_SETTLEMENT_SPEC` | Futures settlement specification is absent. |
| `MISSING_FUNDING_SPEC` | Perpetual funding history/specification is absent. |
| `MISSING_MARK_PRICE_EVIDENCE` | Synchronized historical mark evidence is absent. |
| `SPEC_EFFECTIVE_DATE_GAP` | Required interval is not continuously covered. |
| `SPEC_EFFECTIVE_DATE_OVERLAP` | More than one specification governs a time slice. |
| `SPEC_PROVENANCE_INVALID` | Source identity/path/applicability lineage is invalid. |
| `SPEC_CHECKSUM_MISMATCH` | Retained source bytes do not match their SHA-256. |
| `INSTRUMENT_IDENTITY_MISMATCH` | Market, instrument, contract, order, or fill identities disagree. |
| `OFF_TICK_ECONOMICS` | Price or quantity is not on its exact configured grid. |
| `MIXED_LEDGER_VERSION` | A non-v2 or mixed ledger was supplied. |
| `UNSUPPORTED_INSTRUMENT_PROFILE` | Requested profile is unknown or unproven. |
| `OWNER_APPROVAL_REQUIRED` | Record is synthetic or lacks production owner approval. |
| `AMBIGUOUS_INTRABAR_REJECTED` | No declared adverse ownership resolves OHLC ambiguity. |
| `END_OF_DATA_RESIDUAL` | End-of-data order/position remains unresolved. |

Codes are additive. Existing meanings must never be reassigned.

## Phase 2 order-ledger additions

| Code | Meaning |
|---|---|
| `INVALID_ORDER_TRANSITION` | Event is not declared for the current state. |
| `TERMINAL_ORDER_MUTATION` | A terminal order received another transition. |
| `ORDER_NOT_ACTIVE` | Fill-like event occurred before activation. |
| `STOP_NOT_TRIGGERED` | Stop order received a fill before a trigger fact. |
| `ZERO_FILL_QUANTITY` | Candidate fill quantity is zero or negative. |
| `ORDER_OVERFILL` | Candidate fill exceeds remaining quantity. |
| `QUANTITY_CONSERVATION_FAILURE` | Accepted quantity does not equal filled plus remaining. |
| `EVENT_SEQUENCE_REGRESSION` | Global sequence or equal-time canonical order regressed. |
| `EVENT_TIME_REGRESSION` | Logical UTC event time regressed. |
| `DUPLICATE_EVENT_CONFLICT` | Event identity was reused with different bytes or ledger was tampered. |
| `STALE_ORDER_VERSION` | Event expected a different immutable order version. |
| `ORDER_IDENTITY_MISMATCH` | Event market/instrument/contract differs from the order. |
| `CONTRACT_ELIGIBILITY_UNPROVEN` | Required exact-contract policy evidence is absent. |
| `SESSION_BOUNDARY_UNPROVEN` | DAY expiry lacks verified session-boundary evidence. |

Phase 5 adds the stable `RiskReason` catalog documented in
`PHASE5_REASON_CODE_CATALOG.md`; these reasons describe advisory risk/session rejection and
unresolved forced-action facts only.

Phase 6 adds the stable `Phase6Reason` catalog documented in
`PHASE6_REASON_CODE_CATALOG.md`. These reasons describe rollover/funding coordination failures and
never authorize submission or fabricate economic facts.

Phase 7 adds the stable `Phase7Reason` catalog documented in
`PHASE7_REASON_CODE_CATALOG.md`. These reasons describe reporting, reconciliation,
evidence-separation, economic-hurdle, and advisory-promotion failures only.
| `IOC_ALREADY_EVALUATED` | IOC received a second execution evaluation. |
| `CANCELLED_ORDER_FILL` | A cancelled order received a fill candidate. |
| `REPLACED_ORDER_FILL` | A replaced order received a fill candidate. |
| `INVALID_REPLACEMENT` | Replacement child identity, lineage, or quantity is invalid. |

## Phase 3 execution additions

| Code | Meaning |
|---|---|
| `INVALID_POLICY` | Execution or participation policy is unsupported or internally inconsistent. |
| `INVALID_BAR` | OHLC geometry, interval alignment, or tick grid is invalid. |
| `BAR_NOT_FINAL` | A forming candle was offered to execution. |
| `BAR_NOT_AVAILABLE` | Evaluation precedes the immutable bar availability timestamp. |
| `BAR_INELIGIBLE` | Session, data-quality, or exact-contract eligibility failed closed. |
| `IDENTITY_MISMATCH` | Bar, order, instrument, or contract identities disagree. |
| `VERSION_MISMATCH` | Frozen policy or assumption lineage differs across inputs. |
| `ORDER_NOT_EXECUTABLE` | An instruction references a non-executable order state/type. |
| `SAME_SOURCE_BAR_INELIGIBLE` | The evaluated bar is the immutable source bar for the order. |
| `SOURCE_LINEAGE_UNPROVEN` | Source bar, action, order, and ledger activation lineage is absent or incompatible. |
| `MISSING_VOLUME` | Required exact volume is unavailable for participation allocation. |
| `INVALID_COLLISION_GROUP` | Protective collision ownership/identity is malformed or conflicting. |
| `DUPLICATE_IDENTITY_CONFLICT` | Instruction, trigger, or collision identity conflicts with history. |

## Phase 4 accounting additions

| Code | Meaning |
|---|---|
| `MIXED_LEDGER_VERSION` | A v1 or non-v2 fill/accounting fact was supplied. |
| `IDENTITY_MISMATCH` | Market, instrument, contract, currency, or source lineage differs. |
| `VERSION_MISMATCH` | Accounting or immutable cost version differs. |
| `EVENT_TIME_REGRESSION` | Availability-time canonical event order regressed. |
| `DUPLICATE_EVENT_CONFLICT` | An event ID was reused with different bytes. |
| `DUPLICATE_ECONOMIC_EVENT` | A cost, mark, settlement, or funding fact was already applied. |
| `INVALID_ECONOMIC_FACT` | Exact economic attribution or capability evidence is inconsistent. |
| `OFF_GRID_ECONOMICS` | Fill, mark, or settlement price/quantity is off its verified grid. |
| `MISSING_FILL_COST` | An accepted fill lacks compatible immutable cost lineage. |
| `MISSING_MARK_EVIDENCE` | The profile-authoritative price type is absent or incompatible. |
| `MISSING_SETTLEMENT_FACT` | Futures settlement evidence/specification is absent. |
| `SETTLEMENT_NOT_SUPPORTED` | Settlement was supplied to a profile without variation settlement. |
| `FUNDING_NOT_SUPPORTED` | Funding was supplied to spot or futures. |
| `MISSING_PERPETUAL_CAPABILITY` | BTC perpetual accounting capability was not explicitly enabled. |
| `STALE_SPECIFICATION` | Effective-dated margin facts do not cover the event. |
| `CHECKPOINT_TAMPERED` | Ledger/checkpoint bytes do not reproduce their fingerprint. |
| `END_OF_DATA_RESIDUAL` | A position remains open at the completed-run boundary. |
