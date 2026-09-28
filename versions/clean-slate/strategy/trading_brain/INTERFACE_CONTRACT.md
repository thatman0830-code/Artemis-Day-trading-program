# Trading Brain Interface Contract

Contract version: `trading-brain-interface-v1`  
Canonical authority: attached Obsidian Trading Brain Engine  
Audit scope: market-data boundary, #19–#28, #11, #13, #29.1–#29.7.1, and #29.7.2.1–.20.

## Contract status

The numbered Trading Brain is ready to be consumed by a **separate historical
replay/backtesting subsystem through the interfaces below**. This freezes the
current module/class/method names and frozen record handoffs. It does not freeze
private helpers, authorize live trading, or declare the bot production-ready.
The backtester must orchestrate these facts; it may not duplicate strategy
rules or acquire risk/execution authority.

## Public entry points

`strategy.trading_brain.PUBLIC_ENGINE_ENTRY_POINTS` is the machine-readable
manifest. The public module groups and their input/output families are:

| Owner | Module(s) and callable entry points | Input → output records |
|---|---|---|
| Market data / #19 | `p19_mechanical_swings.MechanicalSwingEngine.detect` | closed chronological candle frame → `MechanicalSwingResult` |
| #20/#16 | `StructuralStateProducer.ingest`; `DisplacementQualificationProducer.context/evaluate/invalidate`; `StructuralSwingSelector.select`; `StructuralBreakQualifier.qualify`; `ConflictResolver.resolve/finalize`; `StructuralStateCommitter.commit` | versioned replay-safe #19 availability + `MechanicalSwingResult` / 20 closed reference candles + evaluation candle + frozen structural context / candidates → append-only structural ledger, owner-policy displacement result, classification-ready state, structural facts, arbitration, next snapshot |
| #21–#26 | `ActiveDealingRangeEngine.update`; `OTEEngine.create/update`; structural and `OWNER_PRIOR_PERIOD_V1` liquidity-reference producers; liquidity pool/interaction engines; `LRLSelectionEngine.select`; `FVGEngine.detect/interact`; `ConfluenceEngine.evaluate_*/reconcile` | accepted structural/range/validated 1M facts → immutable ranges, OTE, structural/prior-period reference histories, pools/interactions, LRL, FVG/IFVG, facts-only confluence |
| #11/#27/#28/#13 | `ReversalDeliveryLegProducer.form/invalidate`; `CISDEngine.*`; `SetupQualificationEngine.qualify_*/finalize`; `EntryZoneSelectionEngine.select/invalidate_and_fallback`; `StopLossSelectionEngine.select` | genuine LRL/sweep/MSS/displacement plus published 1M candles → immutable reversal sequence/delivery history → confirmation; frozen structural/liquidity/zone facts → Phase A/final qualification, one frozen entry zone/EQ, immutable stop |
| #29.1–#29.6 | entry, sizing, protective-order, exit-resolution, cost, and lifecycle engine methods in the manifest | armed setup + explicit execution/risk/account/market boundaries → paper/testnet order/fill, proposed size, protective facts, exit fact, costs, availability/position snapshots |
| #29.7.1 | `TradeAccountingEngine.calculate` | compatible closed position/fill/size/exit/cost facts → final `TradeAccounting` |
| #29.7.2.1–.20 | each numbered analytics engine `calculate` method | immutable final accounting or declared upstream analytics → read-only snapshots/records |
| Owner policies | `owner_policies.MinimumRiskRewardPolicyRegistry.resolve`; `p29_7_2_owner_performance_readiness.PerformanceReadinessEngine.evaluate` | explicit versioned minimum-R selection → #27 threshold; finalized canonical count/expectancy → advisory readiness snapshot |

All public input/output/history/error/scope records are the `@dataclass(frozen=True)`
types declared in the owning module. Result wrappers return either an immutable
record/snapshot or an immutable error; callers must not infer success from a
partially populated object.

## Owner minimum-R and research-readiness extensions

Omitting a policy at `SetupQualificationEngine.finalize` preserves original
`CANONICAL_MIN_RR_V1`: exact `R >= 2.0` for both current models and the legacy
identity. Explicit `OWNER_MIN_RR_V1` requires exact `R >= 1.0`; every future
model requires an explicit value and no value may be below `1.0`. Policy/model
identity, required and actual R components, frozen #28/#13/#24 identities,
reason, and source/calculation versions are immutable lineage.

#28 still owns entry/EQ, #13 stop, and #24 target/LRL. Neither policy may move
or reselect them. Geometry and positive risk remain mandatory.

`OWNER_WIN_RATE_OBJECTIVE_V1` consumes finalized #29.7.2.1 counts and #29.7.2.3
net expectancy only. BTC, ES, and NQ are separate; it requires 200 finalized
out-of-sample trades, win rate `>= 0.60`, and positive net expectancy after
#29.5 costs. Combined evaluation requires an explicit compatible universe.
`OBJECTIVE_MET` permits owner review only; `live_trading_authorized` is always
false and no objective output can feed back into trading decisions.

## Market-data contract

- Canonical timestamps are integer Unix epoch values. Candle sequences are
  unique, strictly increasing, closed-only, and use `t/h/l/c` plus `is_closed`;
  #19 currently accepts a pandas `DataFrame`, while #20/#25 accept mapping
  records. This representation adapter is outside strategy ownership.
- Price inputs become finite `Decimal` values at the first economic/geometry
  boundary. OHLC geometry and chronology fail closed.
- #19 needs two closed bars to the left and right; its confirmed swing is not
  available before the second right bar closes. A replay caller must release
  results only at their canonical confirmation time.
- `StructuralStateProducer.ingest` is the approved #19 → #20 replay handoff.
  `MechanicalSwing.pivot_time` remains occurrence time. The caller supplies the
  UTC-aware publication boundary as `available_at`; the producer records it in
  an immutable `StructuralSwingAvailability` carrying symbol, timeframe,
  source version, calculation version, and the unchanged #19 swing identity.
  Multiple newly observed pivot times at one boundary fail closed because their
  individual availability cannot be proven by this interface.
- Account periods use a valid IANA `AccountTimezone`, integer epoch boundaries,
  and half-open `[start, end)` intervals. Timezone belongs to period identity;
  sessions are not accounting boundaries.

## Identity and version contract

- Opaque `id` plus the owner-specific source identities are immutable.
- Handoffs preserve applicable `setup_id`, `setup_candidate_id`, symbol,
  timeframe, model/setup type, direction, order/fill/position IDs, and source
  record IDs. Mismatch fails closed; no downstream owner replaces a source.
- Analytics scopes isolate `strategy_id` or portfolio/universe membership plus
  symbol, timeframe, model, direction, period type, AccountTimezone, and the
  applicable `input_version`, `source_version`, `calculation_version`,
  `historical_version`, and portfolio/universe version.
- Same canonical key in one authoritative version is `DATA_INTEGRITY_ERROR`.
  A formally corrected authoritative version is a new version, not a duplicate.

### #20 structural ingestion contract

`StructuralStateProducer.ingest` consumes one canonical
`MechanicalSwingResult`, explicit `symbol`, UTC-aware `available_at`,
`source_version`, `calculation_version`, and an optional prior immutable
`StructuralIngestionLedger`/contiguous #20 state. It returns a new immutable
append-only ledger containing availability facts, finalized structural swings,
pending source IDs, superseded source IDs, historical structural IDs, and every
initialization/advancement snapshot.

- One accepted side is retained as pending history; no
  `StructuralStateSnapshot` is emitted and `classification_ready` is false.
- The first opposite high/low pair emits the unclassified INITIALIZING
  baseline. No directional regime is inferred.
- Structural legs alternate. Until closed by an opposite swing, the most
  extreme same-type fact remains pending; an exact-price tie retains the first
  chronological identity. Superseded facts remain in availability history.
- After baseline formation, the newest leg remains pending until the next
  opposite leg closes it. Governing references therefore contain finalized
  structural swings only.
- In a BULLISH prior state a finalized HL may become candidate protected low;
  in a BEARISH prior state a finalized LH may become candidate protected high.
  The producer never promotes protection or changes regime: accepted #16
  decisions and `StructuralStateCommitter.commit` retain that ownership.
- Duplicate identical replay is idempotent. Conflicting identity reuse,
  missing/mismatched lineage, stale chronology, non-Decimal/non-finite prices,
  or unproven availability fails closed with `ValueError`/`TypeError` before a
  new ledger is emitted.

This entry point is approved for historical replay. It does not accept candles,
qualify displacement/BOS/MSS, build liquidity, create CISD/delivery facts,
qualify setups, or invoke execution.

### #23 structural liquidity-reference contract

`StructuralLiquidityReferenceProducer.derive` is the approved replay-safe
#19/#20/#21 → #23 handoff. It consumes the immutable #20 ingestion ledger, a
directional accepted state that directly descends from that ledger's current
snapshot, the accepted event identity, and the exact compatible active #21
range. It emits at most one reference for each active governing/protected
boundary: high → BSL and low → LSL. The original #19 mechanical swing identity
is preserved as lineage; the accepted #20 state/event and #21 range provide
eligibility. A source is visible only after both its #19 availability and range
confirmation, never at pivot occurrence alone.

Every emitted reference is `major_reference=True` because identity and price
must exactly equal the corresponding active range boundary; otherwise derivation
fails closed. Pending, candidate, one-sided, superseded, historical, rejected,
future, or lineage-incompatible facts cannot produce references. Equal prices
from different source swings retain distinct identities, while the same source
is never duplicated as separate mechanical and structural references.

`StructuralLiquidityReferenceLedger` is immutable and append-only. Replacement
historicizes prior active references prospectively. `consume` accepts only an
existing #23 confirmed consuming interaction; a touch/unconfirmed interaction
does nothing. Historical or consumed identities never reactivate, and stale
context replay fails closed without affecting newer facts. Identical active
replay is idempotent. External/session/manual/prior-period registration is not
part of this producer and remains unavailable pending a separate contract.

Both methods are approved for historical replay. They create no pools by
themselves and own no sweep detection, LRL selection, delivery legs, CISD,
setup qualification, risk, or execution behavior.

### Owner-authored prior-period reference contract

`PriorPeriodLiquidityReferenceProducer.evaluate/consume/invalidate` is the replay-safe
registration boundary for owner-authored `OWNER_PRIOR_PERIOD_V1`; it is not
represented as an originally completed canonical rule. Its only source families
are PDH, PDL, PWH, and PWL.

It consumes validated published closed 1M candles with exact lineage. Daily
boundaries are local calendar `[midnight, midnight)` periods and weekly
boundaries are ISO Monday periods in the declared IANA `AccountTimezone`, then
converted to UTC. Every one-minute interval must exist exactly once, including
DST-variable 23/24/25-hour days. Missing, duplicate, overlapping, forming,
future, malformed, or incompatible inputs produce immutable insufficient or
invalid statuses; no substitution, interpolation, synthesis, or forward fill
is permitted.

Highs use exact maximum Decimal high/BSL and lows exact minimum Decimal low/LSL;
all tied candle IDs are retained. Day/week and later-period identities remain
distinct even at the same price. Availability equals completed period end.
Every fact is active, major, versioned, and explicitly owner-authored.

History is immutable and append-only. Identical replay is idempotent and
conflicts fail closed. Only an existing #23 confirmed consuming interaction can
append a terminal consumed/historical transition; touches do nothing. An
explicit timestamped upstream invalidation can retire a reference but cannot
precede its availability. This producer never creates pools, LRLs, sweeps,
setups, or trades.

### Reversal #1 delivery-formation contract

`ReversalDeliveryLegProducer.form` is the approved replay-safe input producer
for #11. It requires a genuine frozen Reversal #1 LRL, confirmed consuming #23
sweep, accepted #16 MSS evaluated against the supplied prior #20 state, active
qualified MSS displacement, and validated published 1M candles with exact
symbol/dataset/run/source/calculation/configuration lineage. The MSS and sweep
event candles must be present as canonical 1M facts; higher-timeframe context
cannot replace them.

The accepted owner policy derives direction from Amendment 005A and the
accepted MSS. It selects the unique maximal, gap-free run of strict opposing
body-direction candles immediately adjacent to the intended-direction MSS
candle. A strict doji or direction change terminates a run. A preceding
contiguous boundary must prove where the run began; dataset truncation, a gap,
forming/future data, incompatible lineage, or a non-opposing adjacent candle
emits immutable `INSUFFICIENT_HISTORY`, `NOT_CONFIRMABLE`, `INVALID_INPUT`, or
`UPSTREAM_INVALID`, never an older fallback. These labels describe producer
availability/integrity and do not add trading states.

The shared sweep/MSS candle is permitted only with a delivery reference formed
entirely before it. It cannot join, create, or retrospectively change that
reference. Formation availability is the latest boundary among every source
candle and upstream fact. Output preserves the exact ordered source candles and
IDs plus the existing immutable `DeliveryLeg` and
`ReversalConfirmationSequence` consumed unchanged by `CISDEngine`.

`ReversalDeliveryLedger` is append-only. Identical replay is idempotent;
conflicting identity reuse fails closed. `invalidate` prospectively appends a
historical terminal record, and the same upstream identity never reactivates.
The producer does not evaluate CISD, create FVG/IFVG, qualify/arm setups, select
zones/stops/targets, or invoke risk/execution.

### Owner-authored displacement policy contract

`DisplacementQualificationProducer.evaluate` is the approved replay interface
for policy `OWNER_MECHANICAL_V1`. This is an owner-authored extension filling a
source rule explicitly marked pending validation; it is not represented as
original canonical language and remains subject to quantitative sensitivity and
out-of-sample validation.

The immutable `MechanicalDisplacementPolicy` fixes: 20 immediately preceding
contiguous closed reference candles; median prior body; body expansion `>= 1.5`;
body/range `>= 0.60`; and a same-direction close at least one configured tick
beyond the frozen governing reference. Body is `abs(close-open)` and range is
`high-low`, using exact Decimal arithmetic. The evaluation candle is excluded
from the reference window, occurs and becomes available at its UTC close, and
no later candle participates.

Inputs preserve evaluation/reference candle identities, frozen structural
snapshot/context/governing identities, symbol, timeframe, direction/event,
dataset, run, source version, calculation version, tick, and policy identity.
Outputs are immutable `DisplacementQualification` records with exact components
and one closed outcome: `QUALIFIED`, `NOT_QUALIFIED`,
`INSUFFICIENT_REFERENCE`, `INVALID_INPUT`, or `UPSTREAM_INVALID`. Missing or
gapped references are insufficient, never false; forming/future/incompatible
facts are invalid. Identical evaluation is idempotent and conflicting reuse of
the evaluation key fails closed. Upstream invalidation appends a historical
inactive record without rewriting the original.

`StructuralBreakQualifier.qualify` retains Boolean compatibility for existing
callers and additionally accepts a compatible active qualified record. It
validates snapshot, timeframe, candle, direction, governing reference, and the
deterministic candidate identity. This policy does not construct discretionary
multi-candle legs, use ATR/volume/volatility/FVG, resolve #16 conflicts, or
create liquidity, CISD, setup, risk, or execution facts.

## Numeric and time conventions

- Economic prices, quantity, risk, PnL, R, rates, costs, equity, statistics,
  tick sizes, and quantity steps are finite `Decimal`; binary `float` is not a
  public economic boundary.
- Decimal computation uses at least 28 significant digits. EQ uses
  `ROUND_HALF_UP` to `minimum_tick`; sizing normalizes quantity downward to the
  legal step and never increases allowed risk. Other statistics retain exact
  computation precision unless their owner states a rounding rule.
- Prices must be on the configured tick grid and quantities on the configured
  step where the owning primitive requires them.
- Event/candle/period/accounting timestamps are integer epochs. Chronology is
  owner-validated; point-in-time analytics use `closed_time <= as_of_time` or
  `period_end <= as_of_time` and finalized facts only.
- Missing period ≠ zero period; `NULL` ≠ zero; future records never repair or
  alter an earlier decision.

## Ownership, state, and dependency direction

Canonical forward direction:

`market data → #19 → #20 ingestion → OWNER_MECHANICAL_V1 displacement → #20 structural-break qualification → #16 → #20 commit → #21 → #22 → #23 structural-reference derivation → #23 pools/interactions → #24 → Reversal #1 delivery formation → #11 → #25 → #26 → #27 Phase A → #28 → #13 → #27 final → #29.1 → #29.2 → #29.3 → #29.4 → #29.5/#29.6 → #29.7.1 → analytics`.

#11 is the Reversal #1 confirmation dependency consumed by #27/#28. #29.6 owns
position availability and lifecycle; #29.4 owns exit winner/price; #29.5 owns
cost facts; #29.7.1 owns accounting; analytics are terminal read-only consumers.

Permitted transitions are only those exposed by the owning engine. In
particular: #26 never qualifies/arms; #27 owns qualification/arming; #28 owns
one frozen zone/EQ; #13 owns StopPrice, not ExitPrice; #29.1 owns paper/testnet
entry facts, not authorization; #29.2 proposes size, not approval; #29.3 owns
protective intents, not exit resolution; #29.4 owns one exit/OCO outcome; #29.6
opens/closes once; analytics cannot feed upstream.

Production-module imports must form an acyclic graph and may reference only
canonical upstream owners or explicit compatibility boundaries. The audit fixed
one reverse dependency: #29.4 no longer imports the later #29.6 module. Both
numbered modules re-export the one neutral serialized `PositionState` enum;
#29.6 remains the sole lifecycle transition owner.

## Failure, immutability, and replay

- Missing, non-final, stale, future-ineligible, mismatched, non-finite,
  off-grid, invalid-geometry, invalid-state, or duplicate inputs fail closed by
  immutable error/result records or documented `ValueError` at early market
  geometry contracts.
- Every domain/history/error/result dataclass is frozen. Histories are tuples;
  new facts append rather than mutate prior records.
- Repeating identical inputs/history returns the identical canonical record and
  unchanged history. A different result for the same owner identity/as-of key
  is a conflict/data-integrity error.
- Approved replay interfaces are exactly `PUBLIC_ENGINE_ENTRY_POINTS`, with
  deterministic caller-supplied data, clocks/as-of timestamps, configuration,
  account facts, risk-authorization facts, and position-availability facts.
  Engines never read wall-clock time.

## Separation and backtester access

The Trading Brain package contains no imports of repository `exchange`, legacy
`execution.paper_engine`, `risk`, `database`, runner, private-key, signing, or
mainnet modules. The future backtester may call strategy facts, explicit
paper/testnet execution fact engines, accounting, and analytics. It must not:

- submit, sign, route, amend, or cancel an exchange order;
- access private keys, wallets, mainnet clients, or live account mutation;
- bypass market-health, portfolio-risk, master authorization, or availability
  boundaries by fabricating approval facts;
- feed analytics into setup qualification, arming, sizing authority, execution,
  or lifecycle decisions;
- reconstruct canonical strategy logic from analytics or duplicate it in the
  replay loop.

`FORBIDDEN_BACKTESTER_DEPENDENCIES` records the inaccessible dependency classes.

## Audit result

### Confirmed stable interfaces

- All manifest entry points and their owning frozen records.
- The structural candidate → arbitration → commit pipeline.
- Phase A → frozen zone/EQ → stop → final qualification handoff.
- Paper/testnet entry → sizing proposal → protective facts → exit → costs →
  lifecycle → accounting identities.
- Final accounting → atomic/path/strategy/portfolio/attribution/overlap/
  correlation/covariance analytics.

### Compatibility adapters needed later

- A read-only candle adapter from historical storage into #19 pandas frames and
  #20/#25 candle mappings; it must preserve IDs, closure, epoch time, and exact
  decimal strings.
- An orchestration adapter that supplies explicit clocks/as-of values and keeps
  per-owner immutable histories. This is not the replay loop itself.
- Optional serialization adapters for enums/Decimals/frozen records; adapters
  must not create alternative domain models.

### Unresolved canonical ambiguities

Owner decisions already recorded in `OWNER_IMPLEMENTATION_DECISIONS.md` remain:
undefined downstream allocation/ranking formulas, selected analytics boundary
details, and explicit fail-closed interpretations. None requires redesign of
the frozen callable contracts before deterministic historical replay.

### Non-blocking technical debt

- Market candle representations differ between #19 and #20/#25.
- Early market primitives use documented `ValueError`; later primitives use
  result/error records. A wrapper may normalize transport errors without
  changing owner behavior.
- Several state fields intentionally use `object` to accept canonical boundary
  enums without reverse imports; serialized enum values remain validated.
- The package manifest freezes import paths but does not eagerly re-export every
  record type from package root.

### Backtesting blockers

No Trading Brain interface blocker remains after removing the #29.4 → #29.6
reverse import. Historical ingestion, replay scheduling, authorization-fixture
policy, and output persistence are separate future subsystem work and were not
implemented by this audit.

Passing this audit **does not authorize production deployment, live/mainnet
trading, exchange submission, signing, private-key use, or a 24/7 runner**.
