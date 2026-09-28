# V2 Phase 1 Public API and Schema Reference

Import from `backtesting.execution_accounting_v2`.

## Records

- `EvidenceRecord` (`evidence-record-v2-1`)
- `SpecificationRecord` (`economic-specification-v2-1`)
- `InstrumentSpecificationV2` (`instrument-spec-v2-1`)
- `OwnerAssumptionV2` (`owner-assumption-v2-1`)
- `CapabilityDeclarationV2` (`capability-declaration-v2-1`)
- `OrderIntentV2` (`order-intent-v2-1`)
- `OrderTransitionV2` (`order-transition-v2-1`)
- `FillV2` (`fill-v2-1`)
- `AccountingSnapshotV2` (`accounting-snapshot-v2-1`)
- `RiskEventV2` (`risk-event-v2-1`)
- `BacktestResultIdentityV2` (`backtest-result-v2-1`)
- `ProductionEligibilityReportV2` (`production-eligibility-v2-1`)

All records are frozen, slotted dataclasses. Economic numbers are finite `Decimal`; serialized
economic decimals are strings. Times are UTC-aware and effective ranges are `[from, to)`. IDs and
fingerprints requiring content identity are lowercase SHA-256.

## Validation entry points

- `canonical_fingerprint(*records)` — deterministic canonical SHA-256; floats reject.
- `SpecificationRepository.resolve(...)` — point-in-time exact lookup; ambiguity rejects.
- `validate_specification_intervals(...)` — collecting gap/overlap validation.
- `validate_evidence_checksum(...)` and `validate_repository_provenance(...)`.
- `validate_order_against_instrument(...)` — identity, effective date, price and quantity grids.
- `validate_fill_against_order(...)` — record compatibility only; never creates a fill.
- `evaluate_production_interval(...)` — deterministic complete blocking report with market,
  instrument, field, interval, and evidence class.

Machine schemas are in `schemas/`; `phase1-records-v2.schema.json` is the record union. Stable codes
are in `REASON_CODES.json`. Core v1 readers and results are outside this namespace and never converted.

## Phase 2 order ledger

- `OrderLedgerEventV2` (`order-ledger-event-v2-1`)
- `OrderLedgerTransitionV2` (`order-ledger-transition-v2-1`)
- `OrderLedgerSnapshotV2` (`order-ledger-snapshot-v2-1`)
- `OrderLedgerV2` (`order-ledger-v2-1`)
- `LedgerCheckpointV2` (`order-ledger-checkpoint-v2-1`)
- `OrderLedgerV2.create`, `.apply`, `.replay`, `.checkpoint`, `.resume`, `.verify_integrity`,
  `.validate_end_of_data`

`order-ledger-v2.schema.json` is the machine contract. These APIs record lifecycle facts only; no
method decides an OHLC fill, price, fee, margin event, or external order action.

## Phase 3 conservative OHLC execution

- `OHLCBarV2` (`ohlc-bar-v2-1`)
- `ExecutionPolicyV2` (`ohlc-execution-policy-v2-1`)
- `ExecutionInstructionV2` (`execution-instruction-v2-1`)
- `ExecutionSourceLineageV2` (`execution-source-lineage-v2-1`)
- `CollisionGroupV2` (`collision-group-v2-1`)
- `ExecutionFillV2` (`execution-fill-v2-1`)
- `ExecutionEvaluationV2` (`ohlc-execution-evaluation-v2-1`)
- `evaluate_bar(...)`

`evaluate_bar` accepts one finalized, aligned one-minute bar, an immutable Phase 2 ledger, the exact
Phase 1 instrument specification, and explicit owner-assumption lineage. It returns immutable
trigger/fill/evaluation facts plus a new ledger; the input ledger is never mutated. It implements
only `CONSERVATIVE_OHLC_1M_V1` and `BAR_VOLUME_PARTICIPATION_V1`.

Every instruction must contain `ExecutionSourceLineageV2`, whose canonical fingerprint binds the
finalized source bar, strategy action, order, and exact ledger activation event. The source bar must
be distinct from the evaluated bar and available no later than the evaluated bar open. An equal
`activation_at`/bar-open timestamp is eligible only when that prior-source identity and availability
are proven. Missing, conflicting, same-source, or late source lineage fails closed.

`ExecutionFillV2` intentionally excludes fees and accounting. It records unrounded basis, adverse
tick-rounded price, friction, volume allocation, trigger/bar lineage, and policy identities. Phase 4
must consume it rather than reinterpret OHLC. No Phase 3 API accesses providers, archives, brokers,
wallets, recorders, or live/paper exchange execution.

## Phase 4 instrument accounting

- `FillEconomicsV2` (`fill-economics-v2-1`)
- `PriceEvidenceV2` (`price-evidence-v2-1`)
- `SettlementFactV2` (`settlement-fact-v2-1`)
- `FundingFactV2` (`funding-fact-v2-1`)
- `MarginSpecificationV2` (`margin-specification-v2-1`)
- `AccountingPolicyV2` (`accounting-policy-v2-1`)
- `AccountingEventV2` (`accounting-event-v2-1`)
- `PositionStateV2`
- `AccountingSnapshotPhase4V2` (`instrument-accounting-snapshot-v2-1`)
- `AccountingCheckpointV2` (`accounting-checkpoint-v2-1`)
- `InstrumentAccountingLedgerV2` (`instrument-accounting-ledger-v2-1`)

`InstrumentAccountingLedgerV2.create`, `.apply`, `.replay`, `.checkpoint`, `.resume`,
`.verify_integrity`, and `.validate_end_of_data` are the public Phase 4 entry points. The ledger is
single-run, single-market, single-instrument, single-contract, single-currency, and v2-only. It
consumes accepted Phase 3 fills without re-evaluating bars. Every fee, friction, funding, mark, and
settlement input is an immutable versioned fact and is applied once by economic identity.

Futures use the verified contract multiplier and explicit settlement facts. BTC spot uses base
quantity and quote cash, has no funding, and requires a zero-margin unlevered profile. BTC linear
perpetuals are disabled unless the policy capability is explicitly enabled and synchronized funding,
mark, oracle, margin, fee, and instrument lineage is supplied. Margin breaches are facts only; Phase
4 creates no liquidation or risk order. Open end-of-data positions return `END_OF_DATA_RESIDUAL`.

The machine contract is `schemas/instrument-accounting-v2.schema.json`. Phase 4 has no provider,
strategy, risk-authority, order-creation, execution, recorder, credential, or trading interface.

## Phase 5 risk and sessions

`risk_sessions.py` exports immutable `VerifiedSessionV2`, `RiskLimitsV2`,
`PortfolioRiskContextV2`, `PreTradeRiskRequestV2`, `RiskDecisionRecordV2`,
`SessionRiskStateV2`, `ForcedFlattenInstructionV2`, `MarginCallFactV2`,
`LiquidationRequiredFactV2`, `PostAccountingRiskEvaluationV2`, and the replay/checkpoint records.
Public operations are `resolve_session`, `evaluate_pre_trade`, `evaluate_post_accounting`,
`evaluate_session_flatten`, `validate_forced_flatten_bar`, and `completed_run_gate`. They are
advisory simulation interfaces and cannot create an order or fill.

## Phase 6 rollover and funding

`rollover_funding.py` exports immutable roll specifications, leg instructions/events/state,
funding requirements/applications, a deterministic Phase 6 event ledger/checkpoint, completed-run
gates, and cross-ledger reconciliation. Rollover legs remain separate and a missing incoming leg
preserves a flat incomplete state. Funding applications contain a verified Phase 4 accounting event;
they do not apply it or infer missing funding.

## Phase 7 reporting and validation

`reporting_validation.py` exports immutable finalized-trade, regime-label,
cross-ledger reconciliation, metric, stress, probability-of-ruin, economic-hurdle,
advisory promotion, and backtest-result records. Public calculations are
`reconcile`, `calculate_metrics`, `segment_trades_by_regime`, `run_stress`,
`probability_of_ruin`, `economic_hurdles`, and `evaluate_promotion`.
`validate_evidence_partitions` rejects cross-partition relabeling and overlap.

Evidence partitions remain isolated. Promotion evaluation accepts only untouched
OOS metrics, requires at least 200 finalized trades per market, and remains
advisory. No Phase 7 interface authorizes or submits a trade. The machine contract
is `schemas/reporting-validation-v2.schema.json`.
