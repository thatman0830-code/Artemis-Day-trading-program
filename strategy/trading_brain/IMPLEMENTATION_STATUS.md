# Canonical Trading Brain Port Status

Authoritative source: attached Obsidian `Trading Brain Engine` vault.

Regression status: 712 Trading Brain tests passing; 784 full-repository tests passing.

## Implemented and tested

- #19 Mechanical Swing Selection
- #20 Phase A: dominant-extreme structural promotion and exact same-type classification
- #20 Phase B: frozen-state body-close/displacement BOS and MSS candidate qualification
- #16 conflict arbitration and immutable accepted/suppressed event decisions
- #20 Phase C: accepted-event commit, protected-swing lifecycle, persisted regime snapshots
- Structural pipeline integration: #20 qualify -> #16 resolve -> #20 commit -> #16 record
- #21 Active Dealing Range construction, replacement, termination, and invalid geometry
- Structural pipeline integration extended through #21 range creation
- #22 directional OTE geometry and immutable lifecycle
- Structural pipeline integration extended through #22 OTE generation
- #23 liquidity reference/pool construction, positional classification, and sweep/break lifecycle
- #24 deterministic LRL selection, persistence, termination, and #27 target handoff
- #25 exact FVG geometry, mitigation lifecycle, and one-time IFVG inversion
- #26 facts-only confluence relationships, active/historical persistence, and termination
- #11 deterministic 1M CISD reference selection, confirmation, and termination state machine
- #27 Phase A continuation and Reversal #1 pre-zone qualification only
- #28 frozen FVG/IFVG candidate selection, fallback lifecycle, and tick-normalized EQ
- #13 immutable continuation and Reversal #1 stop selection
- #27 Phase B frozen Entry/Stop/Target geometry and authoritative >=2R gate
- #29.1 deterministic paper/testnet entry-order lifecycle and exact frozen-EQ fills
- #29.2 exact Decimal position-sizing proposals with downward quantity normalization
- #29.3 isolated protective stop/target intents and unresolved OCO relationship
- #29.4 deterministic OHLC/finer-chronology exit resolution and terminal OCO facts
- #29.5 exact economic-price friction and explicit cash execution-cost records
- #29.6 global position availability and immutable OPEN/CLOSED lifecycle snapshots
- #29.7.1 finalized per-trade PnL, risk-normalized R, classification, and equity facts
- #29.7.2.1 read-only authoritative TradeResult classification counts
- #29.7.2.2 finalized-trade Return Statistics with canonical NULL empty-sample behavior
- #29.7.2.3 exact finalized-trade net-PnL and net-R Expectancy with canonical NULL empty-sample behavior
- #29.7.2.4 exact finalized-trade Profit Factor with finite, infinity, and NULL boundary behavior
- #29.7.2.5 canonical chronological cumulative NetPnL and NetR series
- #29.7.2.6 exact equity curve from explicit starting equity and immutable #29.7.2.5 points
- #29.7.2.7 canonical running-peak absolute/percentage drawdown and maximum extrema
- #29.7.2.8 authoritative-result maximum WIN/LOSS streaks with BREAKEVEN interruption
- #29.7.2.9 AccountTimezone daily/ISO-weekly/monthly/full-history period statistics
- #29.7.2.10 immutable NetPnL/NetR and authoritative-result distribution facts
- #29.7.2.11 canonical finalized-daily-equity Sharpe, Sortino, and Calmar statistics
- #29.7.2.12 canonical peak-to-recovery episodes, recovery durations, states, and aggregates
- #29.7.2.13 canonical point-in-time underwater states and completed-duration statistics
- #29.7.2.14 canonical finalized-trade path, transitions, result runs, and snapshots
- #29.7.2.15 canonical strategy conservation, explicit equity, and period-return observations
- #29.7.2.16 canonical portfolio membership, conservation, aligned periods, and merged equity/drawdown
- #29.7.2.17 exact signed strategy attribution, conservation, and immutable portfolio-period lineage
- #29.7.2.18 canonical half-open temporal overlap, unioned strategy-pair durations, and simultaneous strategy/risk observations
- #29.7.2.19 exact period-intersection NetR Pearson correlation with canonical NULL and constant-series states
- #29.7.2.20 exact pairwise sample covariance and complete symmetric covariance matrices

## #29.7.2 dependency map

- `.1 Classification/Count`, `.2 Return Statistics`, `.3 Expectancy`, `.4 Profit
  Factor`, `.5 Cumulative`, `.8 Streaks`, `.9 Period Statistics`, `.10
  Distribution`, and `.18 Overlap` consume finalized `#29.7.1` facts directly.
- `.6 Equity Curve` depends on `.5`; `.7 Drawdown` depends on `.6`.
- `.11 Risk-Adjusted` depends on finalized `#29.7.1` lineage and `.9` DAILY
  period facts, plus the canonical explicit daily-equity observations and the
  `.7` maximum-drawdown fact required by its detailed formula. The current
  `.9` model has no equity field, so `.11` uses the documented immutable
  daily-equity adapter rather than reconstructing or forward-filling equity.
- `.12 Recovery` depends on `.7` plus the explicit initial-equity observation
  required to timestamp the starting baseline; `.13 Underwater` depends on `.7`,
  `.12`, and that same immutable baseline observation for its initial state.
- `.14 Trade Sequence/Path` depends on `#29.7.1`, `.5`, and `.8`.
- `.15 Strategy Aggregation` depends on `#29.7.1` and `.9`.
- `.16 Portfolio Aggregation` depends on `.15`; `.17 Attribution` depends on `.16`.
- `.19 Correlation` and `.20 Covariance` depend on `.15` period-return observations.

Current analytics status: `.1` through `.20` implemented and regression-tested.
This analytics completion does not make the bot production-ready or authorize
live trading.

## Not yet implemented

- Quantitative backtesting Trading Brain orchestration, simulated strategy/fill
  processing, parameter optimization, and walk-forward testing
- Exchange submission, signing/private-key handling, mainnet support, and the
  24/7 production runner

## Trading Brain interface audit and contract freeze

Audit result: **PASS** for consumption by a separate quantitative backtesting
subsystem under contract version `trading-brain-interface-v1`.

- The public replay surface is frozen in `INTERFACE_CONTRACT.md` and the
  machine-readable `PUBLIC_ENGINE_ENTRY_POINTS` manifest.
- Public inputs and immutable outputs, identity/version lineage, integer epoch
  chronology, AccountTimezone period semantics, Decimal/grid conventions,
  fail-closed behavior, state ownership, dependency direction, and idempotency
  expectations are documented and covered by deterministic contract tests.
- One genuine ownership defect was found and corrected compatibly: #29.4 no
  longer imports the later #29.6 lifecycle implementation. Both modules retain
  their stable `PositionState` export by re-exporting the identical enum from
  the neutral `position_state_contract` module; #29.6 remains the lifecycle
  transition owner.
- No circular production-module imports, duplicate canonical state enum at that
  boundary, binary-float economic fields, mutable owned records, or exchange,
  signing, private-key, mainnet, risk-authorization, legacy execution, database,
  or analytics-to-trading imports were found in the canonical package.
- The Phase 1 backtesting package now supplies the market-data compatibility
  adapter anticipated by the audit while preserving the canonical pandas and
  mapping forms without duplicating strategy logic.
- No interface blocker remains for beginning a separate quantitative
  backtesting subsystem. Passing this audit does **not** make the bot
  production-ready and does not authorize live trading.

The earlier `strategy` scaffold is not the canonical Trading Brain implementation.
The canonical #29.1 module is an isolated paper/testnet fact engine and is not
connected to the repository's legacy paper engine or any exchange interface.
Live brokerage deployment is not authorized.

## Quantitative backtesting subsystem — Phase 1

Status: **COMPLETE (data boundary only)**.

- Added the separate top-level `backtesting` package. Dependency direction is
  historical data -> validation/manifests -> point-in-time view -> one-way
  adapter -> frozen Trading Brain public inputs. Trading Brain does not depend
  on the backtesting package.
- Added frozen exact historical candles for the repository-established `1m`,
  `5m`, `15m`, `1h`, and `4h` timeframes with UTC-aware interval boundaries,
  deterministic identities, finite Decimal OHLCV, explicit finality, canonical
  alignment, and strict geometry.
- Added deterministic dataset validation/fingerprinting with source, exchange,
  schema/dataset versions, single-symbol isolation, strict ordering, duplicate,
  overlap, current/future-candle, and gap handling. Gaps are either rejected or
  explicitly recorded; they are never forward-filled.
- Added immutable dataset and run manifests with half-open intervals, counts,
  gaps, provenance, configuration identities, Trading Brain contract version,
  starting equity, cost configuration, seed, runtime facts, explicit
  `PAPER_SIMULATION`, and exchange submission fixed to disabled.
- Added deterministic multi-timeframe visibility: every candle, including a
  higher-timeframe candle, becomes visible only at its close timestamp.
- Added a one-way compatibility adapter outside Trading Brain. It emits the
  object-backed Decimal pandas frame required by #19 or immutable mappings for
  #20/#25 from the same validated records, preserving IDs, exact values,
  ordering, close status, and integer epoch milliseconds.
- Phase 1 focused tests: 24 passing. Frozen Trading Brain interface-contract
  tests: 11 passing. Complete Trading Brain suite: 712 passing. Full repository
  suite: 747 passing.

The subsystem cannot execute or replay a strategy yet. Phase 1 adds no replay
loop, simulated fills, optimization, walk-forward testing, live WebSocket,
account mutation, exchange submission, wallet/private-key/signing support,
mainnet support, or performance claims.

## Quantitative backtesting subsystem — Phase 2

Status: **COMPLETE (market-data event replay only)**.

- Added a deterministic simulation clock with immutable `READY`, `ACTIVE`, and
  `COMPLETED` snapshots. It is driven exclusively by validated historical close
  timestamps and never reads wall time, sleeps, performs I/O, or uses randomness.
- Added immutable replay events, atomic close-timestamp batches, availability
  snapshots, publications, and checkpoints with deterministic identities and
  full candle/dataset/run/schema/contract/source/symbol/timeframe lineage.
- Replay eligibility follows the run manifest's exact half-open interval using
  `replay_start_inclusive <= candle.close_time < replay_end_exclusive`.
- Same-timestamp candles publish atomically. Inside each batch the canonical key
  is symbol, timeframe duration, timeframe value, then candle identity. Before
  publication none of that timestamp's candles are visible; afterward all are.
- Added isolated, ordered symbol/timeframe histories with published-only
  `history`, `latest`, and bounded `lookback` queries. Queries reject unknown
  streams, naive/out-of-scope/future timestamps, and invalid lookbacks. Higher
  timeframes are neither formed nor exposed early, and gaps are not filled.
- Added immutable serializable replay checkpoints. Resume verifies checkpoint,
  dataset, fingerprint, run, Trading Brain contract, complete event-sequence,
  cursor, clock, and last-batch identities before rebuilding published history;
  it cannot duplicate or skip a batch.
- Corrected a Phase 1 half-open boundary defect discovered by Phase 2 testing:
  the dataset manifest's exclusive event horizon is now one canonical datetime
  quantum beyond the final included close, so the final candle can be replayed
  without weakening strict half-open event semantics.
- Phase 2 focused tests: 23 passing. All backtesting tests: 47 passing. Frozen
  Trading Brain interface-contract tests: 11 passing. Complete Trading Brain
  suite: 712 passing. Full repository suite: 770 passing.

Phase 2 can replay deterministic market-data events and answer point-in-time
availability queries. It still cannot evaluate the Trading Brain, generate a
setup, simulate an order/fill/position, calculate costs/PnL/accounting/analytics,
optimize parameters, run walk-forward tests, connect to an exchange, or operate
as a live/24/7 runner.

## Quantitative backtesting subsystem — Phase 3

Status: **COMPLETE (read-only historical setup evaluation only)**.

- Added an immutable post-publication evaluation context, primitive result
  references, missing-prerequisite facts, evaluation traces, setup-state facts,
  per-request historical state, batch results, and orchestration checkpoints.
- Phase 3 accepts only an exact canonical Phase 2 publication at the expected
  cursor. Evaluation occurs after atomic batch publication and every adapter
  read is capped at that batch's UTC close timestamp.
- The orchestrator uses the Phase 1 adapter exclusively. Its smallest extension
  emits exact immutable #11 `DeliveryCandle` records from the same validated,
  published 1M history; no alternative market-data conversion path was added.
- The dependency-ready chain invokes actual frozen public owners: candle-driven
  #19/#20 and #25; prior immutable structural facts through #21/#22; explicit
  upstream liquidity references through #23/#24; #26 confluence; the complete
  #11 CISD state machine for Reversal #1; and #27 Phase A -> #28 -> #13 -> final
  #27 qualification. It stops before #29.1.
- Displacement, accepted MSS, protected structure, delivery-leg, sweep, and
  higher-order liquidity facts are never inferred from candle titles or prices.
  They must exist as immutable canonical prior facts. Future-dated facts are
  excluded, and unavailable facts produce deterministic candidate, waiting,
  MSS/CISD-confirmed, or fail-closed results with explicit missing lineage.
- Exact canonical EntryZoneSelection/EQ, StopSelection, frozen LRL target,
  risk, reward, R, and final continuation/reversal state are preserved without
  recomputation. A farther target is never substituted after #24 selection.
- Duplicate identical evaluation is idempotent; changed same-batch requests,
  skipped/older batches, forged publications, or identity/version conflicts
  fail before state mutation. Terminated range/OTE/LRL/CISD facts and all prior
  batch results remain in immutable history.
- Orchestration checkpoints bind the full state identity to a compatible Phase
  2 replay checkpoint/cursor. No disk persistence or mutable strategy-state
  serialization was added.
- Phase 3 focused tests: 14 passing. All backtesting tests: 61 passing. Frozen
  Trading Brain interface-contract tests: 11 passing. Complete Trading Brain
  suite: 712 passing. Full repository suite: 784 passing.

Phase 3 can evaluate historical continuation and Reversal #1 setup states
through canonical final #27. It cannot call #29.1 or later, simulate orders,
fills or positions, authorize risk, size positions, calculate costs/PnL/
accounting/analytics, optimize parameters, run walk-forward tests, connect to
an exchange, or operate as a live/24/7 runner.

## Quantitative backtesting subsystem — Phase 4

Status: **COMPLETE (canonical #29.1-#29.6 lifecycle simulation only)**.

- Added a deterministic paper-only simulator downstream of exact matching
  Phase 2 publications and Phase 3 setup facts. Frozen canonical owners retain
  every entry, sizing, protection, exit/OCO, cost, and lifecycle calculation.
- Starting equity is copied unchanged from the run manifest. Risk percentage,
  tick value, multiplier, grids, size bounds, and costs are immutable versioned
  inputs; #29.2 proposals remain explicitly unauthorized.
- Setup candles cannot fill newly activated orders, and fill candles cannot
  also produce OHLC-only exits. Later eligible bars, adverse gaps, collisions,
  and optional chronological observations are handled by #29.1/#29.4.
- Added immutable traces, fail-closed facts, histories, consumed-setup and
  single-lifecycle guards, and checkpoints bound to exact Phase 2/3 cursors and
  active order/protective-set/position identities.
- Extended the external adapter with exact one-candle #29.1/#29.4 records while
  preserving Decimal values, UTC timestamps, candle IDs, ordering, and version.
- Phase 4 focused tests: 12 passing. All backtesting tests: 73 passing. Frozen
  interface-contract tests: 11 passing. Complete Trading Brain suite: 712
  passing. Full repository suite: 796 passing.

Phase 4 simulates canonical trade lifecycles but does **not** calculate final
backtest PnL, realized R, equity changes, accounting, or performance analytics.
It adds no optimization, network, exchange, wallet, signing, private-key,
mainnet, or 24/7-runner capability and does not authorize production trading.

## Quantitative backtesting subsystem — Phase 5A

Status: **COMPLETE (individual accounting and immutable equity progression)**.

- Each compatible canonically CLOSED Phase 4 lifecycle now invokes frozen
  #29.7.1 exactly once. The linkage preserves its fill, size/risk, exit, costs,
  gross/net PnL, gross/net R, outcome, pre/post equity, and equity-change facts.
- Added a deterministic initial-equity snapshot sourced only from the run
  manifest and an immutable predecessor-linked ledger. Canonical TradeResults
  advance it in `closed_time ASC, trade_id ASC` order; duplicates are idempotent
  and forks, conflicts, version mismatches, retroactivity, and inconsistent
  equity equations fail closed.
- The explicit versioned policy is `COMPOUNDED`, because #29.7.1 binds
  pre-trade equity to #29.2 sizing equity and defines no separate fixed-base
  ledger mode. Only a finalized preceding snapshot can size a future fill;
  prior sizing records are never modified.
- Phase 4 checkpoints now also bind the latest accounting cursor and equity
  snapshot while retaining their Phase 2/3/4 cursor and active-lifecycle facts.
- Phase 5A focused tests: 11 passing. All backtesting tests: 84 passing. Frozen
  interface-contract tests: 11 passing. Complete Trading Brain suite: 712
  passing. Full repository suite: 807 passing.

Phase 5A calculates individual canonical trade results and equity progression.
It does **not** invoke #29.7.2 or produce aggregate backtest analytics, reports,
charts, persistence, optimization, walk-forward/Monte Carlo analysis, network
or exchange access, wallets, signing, private keys, mainnet, or a 24/7 runner.

## Quantitative backtesting subsystem — Phase 5B

Status: **COMPLETE (deterministic in-memory analytics result)**.

- Added terminal dependency-ordered orchestration over frozen canonical
  #29.7.2 records. Applicable single-strategy owners `.1–.10`, `.12–.15`, and
  `.18` are invoked directly from finalized Phase 5A facts.
- `.11` is preserved as `NOT_APPLICABLE` without the canonically required DAILY
  equity-observation series. `.16/.17/.19/.20` are `NOT_APPLICABLE` without an
  explicit immutable portfolio/universe definition; no membership or strategy
  is fabricated.
- Added an immutable deterministic BacktestResult containing run/dataset/
  contract/configuration identities, interval and UTC `as_of`, exact equity and
  canonical counts, analytics references/statuses, and a lineage fingerprint.
  Canonical NULL/infinity/insufficient/constant-series outcomes remain lossless.
- Added strict finality, no-look-ahead, lifecycle/accounting/ledger/scope/version
  validation and analytics checkpoints bound to simulation state, accounting
  cursor, equity snapshot, result identity, and `as_of`.
- Phase 5B focused tests: 7 passing. All backtesting tests: 91 passing. Frozen
  interface-contract tests: 11 passing. Complete Trading Brain suite: 712
  passing. Full repository suite: 814 passing.

Phase 5B produces complete deterministic in-memory backtest results for the
applicable declared scope. It does not provide exports, persistence, charts,
optimization, walk-forward validation, Monte Carlo analysis, production/live
execution, network/exchange access, wallets, signing, private keys, or mainnet.

## Quantitative backtesting subsystem — Phase 6

Status: **COMPLETE (reproducible offline files, CLI, and deterministic export)**.

- Added `python -m backtesting validate|inspect|run` with explicit local paths,
  overwrite policy, stable PowerShell-friendly messages, and categorized exit
  codes. `scripts/run_backtest.ps1` selects `.venv` Python 3.11 when available.
- Added a strict versioned data manifest with explicit timeframe-to-CSV mapping
  and a strict versioned JSON configuration. Decimal strings never pass through
  float; timestamps require UTC `Z`; unknown/secret-like fields, unsupported
  schemas, missing files, malformed facts, and incompatible runs fail closed.
- The command composes Phase 1–5B public interfaces. It explicitly supports
  `setup_request_mode: NONE` and never invents Phase 3 setup prerequisites.
- Added atomic deterministic exports for dataset/run manifests, BacktestResult,
  trades, equity, summary, and SHA-256 checksums with stable UTF-8/LF ordering,
  lossless Decimal/status/NULL/infinity handling, lineage, and simulation-only
  markings.
- Added non-secret synthetic CSV/JSON examples and a PowerShell usage guide.
- Phase 6 focused tests: 8 passing. Included synthetic example: validate,
  inspect, and complete export passing. All backtesting tests: 99 passing.
  Frozen interface-contract tests: 11 passing. Complete Trading Brain suite:
  712 passing. Full repository suite: 822 passing.

Run from PowerShell:
`.\scripts\run_backtest.ps1 -Data .\examples\backtesting\dataset_manifest.json
-Config .\examples\backtesting\backtest_config.json -Output
.\outputs\synthetic-example`

Phase 6 is historical simulation only. It neither demonstrates profitability
nor makes the strategy production-ready, and it adds no network/download,
exchange submission, wallet/signing/private-key/mainnet, optimization,
walk-forward/Monte Carlo, dashboard, or 24/7 runner capability.

## Quantitative backtesting subsystem — Phase 7A

Status: **COMPLETE (public historical market-data acquisition only)**.

- Added `python -m backtesting download` for unauthenticated, read-only public
  Hyperliquid candle snapshots. Testnet is the safest default; public mainnet
  data requires explicit `--data-network mainnet` and grants no trading power.
- Added bounded windows, HTTPS verification, timeout/retry limits, exponential
  backoff, transient rate-limit/server handling, strict malformed/permanent
  failure behavior, and concise per-window PowerShell output.
- Responses go directly through exact Phase 1 Decimal/UTC normalization and
  validation. Only closed `[start,end)` candles survive; forming bars,
  duplicates, gaps, overlaps, identity errors, and ordering defects are never
  hidden, forward-filled, or synthesized.
- Added stable per-timeframe CSV, versioned Phase 6-compatible manifest,
  checksums, gaps/exclusions, deterministic identities/fingerprint, atomic
  completion, overwrite protection, and verified `.partial` resume state.
- Added `scripts/download_backtest_data.ps1` and documented a short public-data
  example. Download never starts a backtest.
- Phase 7A focused mocked/local tests: 9 passing. All backtesting tests: 108
  passing. Frozen interface-contract tests: 11 passing. Complete Trading Brain
  suite: 712 passing. Full repository suite: 831 passing. No test used live
  internet access.

Phase 7A only acquires public historical data. It cannot place or authorize
trades and adds no authenticated endpoint, exchange order client, wallet,
signing credential, private key, secret loading, optimization, or live runner.

## Quantitative backtesting Phase 7B — prerequisite 1

Status: **COMPLETE — ADDITIVE #20 INGESTION PRODUCER**.

Implemented owner decisions `P7B-P1-D1` through `P7B-P1-D4` via the additive
public `StructuralStateProducer.ingest` operation and immutable
`StructuralIngestionLedger`/`StructuralSwingAvailability` facts. One-sided
initialization remains pending and cannot emit a trade-eligible snapshot.
Explicit UTC availability is distinct from pivot occurrence; symbol/timeframe/
source/calculation lineage is fail-closed; and all source, pending, superseded,
structural, historical, and snapshot facts remain append-only.

The producer follows canonical alternating-leg/extreme/tie/classification and
candidate-protection rules. It does not qualify displacement or BOS/MSS, commit
#16 decisions, or create liquidity, CISD, confluence, setup, risk, or execution
facts. Existing #19/#20 entry points and record constructors remain compatible.
The public manifest and interface contract now include the additive replay-safe
operation. Phase 3 incrementally consumes it at each published timestamp and
stores per-timeframe ledgers, but does not resume Phase 7B canonical mode or
invent the remaining missing producers.

Prerequisite 1 is complete. Phase 7B remains blocked on its separately owned
displacement, liquidity-reference, and reversal delivery-leg producers. No live
or production authority is implied.

Verification: 10 focused producer tests; 60 focused #19/#20/interface tests;
108 backtesting tests; 722 complete Trading Brain tests; 841 full repository
tests passing.

## Quantitative backtesting Phase 7B — prerequisite 2

Status: **COMPLETE — OWNER-AUTHORED `OWNER_MECHANICAL_V1`**.

Implemented immutable `MechanicalDisplacementPolicy`, `DisplacementCandle`,
`StructuralDisplacementContext`, `DisplacementQualification`, and append-only
`DisplacementLedger` records plus public context/evaluate/invalidate operations.
The policy uses exact Decimal median/body/range calculations, 20 contiguous
prior closed candles, inclusive `1.5`/`0.60` thresholds, and one-tick structural
clearance. It distinguishes all five owner-approved outcomes and preserves full
structural, candle, dataset/run, policy, and version lineage.

The existing #20 qualifier retains Boolean compatibility and now validates and
consumes a genuine active qualified record. Phase 3 evaluates this policy from
atomically published history and passes qualified records into #20 without
resolving/committing structure or creating later facts. The public manifest and
interface contract expose the additive operations.

Prerequisite 2 is complete. `OWNER_MECHANICAL_V1` is owner-authored, not original
canonical source, and remains subject to later quantitative sensitivity and
out-of-sample validation. Prerequisite 1 remains complete. Phase 7B remains
blocked on liquidity-reference and reversal delivery-leg producers. No setup,
execution, network, credential, or live-trading behavior was added.

Verification: 12 focused displacement tests; 72 focused displacement/#19/#20/
interface tests; 108 backtesting tests; 734 complete Trading Brain tests; 853
full repository tests passing.

## Quantitative backtesting Phase 7B — prerequisite 3

Status: **COMPLETE — ADDITIVE STRUCTURAL #23 REFERENCE PRODUCER**.

Implemented accepted decisions `P7B-P3-D1` through `P7B-P3-D5` through public
`StructuralLiquidityReferenceProducer.derive/consume` and immutable
`StructuralLiquidityReferenceLedger`. The producer preserves #19 source
identity and replay-safe availability, requires a directly compatible accepted
#20 directional state/event and exact active #21 boundary identity/price, and
emits only one major BSL/LSL reference per active governing/protected source.

Replacement and confirmed #23 consuming sweeps append historical terminal
facts; touches do not consume; stale contexts cannot reactivate or affect newer
references. Equal-price distinct swings retain distinct identities. The public
manifest and interface contract expose the handoff. Phase 3 stores the ledger
and passes derived references into the existing pool engine only when genuine
compatible #19/#20/#21 lineage is present; it does not fabricate missing facts.

Prerequisite 3 is complete. Phase 7B remains blocked on the separately owned
reversal delivery-leg producer and canonical-mode orchestration. No external or
session registration, CISD change, target/setup change, execution, network,
credential, or live-trading behavior was added.

Verification: 8 focused producer tests; 117 focused #19–#24/interface tests;
108 backtesting tests; 742 complete Trading Brain tests; 861 full repository
tests passing.

## Quantitative backtesting Phase 7B — prerequisite 4

Status: **COMPLETE — ADDITIVE REVERSAL #1 DELIVERY PRODUCER**.

Implemented accepted owner decisions `P7B-P4-D1` through `P7B-P4-D6` through
public `ReversalDeliveryLegProducer.form/invalidate`, immutable
`ReversalDeliveryFormation` facts, and `ReversalDeliveryLedger` history. The
producer requires the exact frozen reversal LRL, consuming sweep, accepted 1M
MSS, qualified displacement, prior state, and complete dataset/run/version
lineage. It forms only the unique maximal contiguous opposing 1M body-direction
run immediately adjacent to the intended-direction MSS candle, with a proven
start boundary and no older fallback.

Missing boundaries/gaps, future/forming candles, and incompatible upstream
facts produce closed unavailable/invalid outcomes. Same-candle sweep/MSS uses
only a reference completed before the shared candle. Availability is the latest
constituent/upstream boundary. Invalidation appends a terminal historical fact;
identical replay is idempotent and conflicting reuse fails closed.

The public manifest and interface contract expose the producer. Phase 3 accepts
an optional genuine `ReversalDeliverySource`, forms and stores its delivery
history from validated published 1M candles, and replaces manual sequence/leg
inputs only after a `READY` formation. A failed genuine source cannot fall back
to caller-constructed delivery facts. Existing callers without the additive
source retain compatibility.

Prerequisite 4 is complete. Full Phase 7B canonical CLI mode remains outside
this pass. No FVG, setup, zone, stop, target, risk, execution, network,
credential, or live-trading behavior was added.

Verification: 8 focused delivery-producer tests; 185 focused delivery/#11/
#19–#26/interface tests; 750 complete Trading Brain tests; 108 backtesting
tests; 869 full repository tests passing.

## Quantitative backtesting Phase 7B — canonical CLI completion audit

Status: **BLOCKED — NO CANONICAL SOURCE FOR A SECOND SAME-SIDE ACTIVE LIQUIDITY REFERENCE**.

The four named prerequisites are individually complete, but their frozen
contracts cannot yet form the first #23 pool required by #24. The structural
reference producer exposes one active BSL and one active LSL from the current
range. Replaced references are terminal historical facts. #23 requires at least
two same-side references, and #24 accepts pools—not singleton references.
External/session/prior-period registration remains explicitly unavailable.

Therefore a file-driven canonical run cannot produce an LRL or confirmed pool
sweep and cannot reach continuation/Reversal #1 qualification. Adding
`CANONICAL_TRADING_BRAIN` now would either be a zero-trade alias of `NONE` or
would require forbidden injected facts/canonical rule changes. Neither meets
the Phase 7B mode contract or meaningful synthetic-example requirement.

The exact alternatives and narrow recommendation are recorded in
`OWNER_IMPLEMENTATION_DECISIONS.md`. The recommended next prerequisite is an
additive, replay-safe external/session/prior-period liquidity-reference
registration producer, because that preserves #23's 2+ pool invariant and
#24's pool-only input. No canonical-mode CLI/configuration, autonomous setup
fabrication, synthetic trade fixture, or partial production behavior was added
during this audit. Existing `NONE` remains the explicit zero-trade smoke mode.

This blocker is unrelated to live trading: the subsystem remains historical
simulation only and provides no profitability, production-readiness, exchange,
wallet, signing, credential, or live execution authority.

## Quantitative backtesting Phase 7B — prerequisite 5

Status: **COMPLETE — OWNER-AUTHORED `OWNER_PRIOR_PERIOD_V1`**.

Implemented public `PriorPeriodLiquidityReferenceProducer.evaluate/consume/invalidate`
with immutable `PriorPeriodReferenceLedger` history. It registers only complete
prior-day PDH/PDL and prior-ISO-week PWH/PWL from exact contiguous published 1M
candles. Calendar periods use the configured IANA AccountTimezone and UTC
conversion, including DST-variable durations. Extrema use exact Decimal values
and retain every tied source candle identity.

References become available exactly at period end, remain distinct across
day/week and later periods, and carry full policy and data lineage. Missing,
partial, gapped, duplicate, forming, or future data fails closed. Existing #23
alone builds pools and confirms consumption; touches do nothing and consumed
references never reactivate. Explicit upstream invalidation is chronological,
terminal, and retained as immutable history.

The manifest and interface contract expose the policy. Phase 3 derives these
facts from published 1M history and combines active prior-period and structural
references only as inputs to the unchanged #23 inventory engine. Phase 6
configuration accepts only `OWNER_PRIOR_PERIOD_V1` and validates IANA
AccountTimezone; existing `NONE` smoke mode remains compatible.

Prerequisite 5 resolves the previously recorded liquidity-population authority.
Full canonical CLI mode is intentionally not resumed in this pass. The policy
is owner-authored and remains subject to later sensitivity and out-of-sample
validation. No pool, LRL, sweep, setup, trade, execution, network, credential,
or live behavior is fabricated.

Verification completed on 2026-08-22: 9 focused prerequisite tests passed;
137 focused #19–#24 plus interface-contract tests passed; all 759 Trading Brain
tests passed; all 108 backtesting tests passed; and the full repository suite
passed with 878 tests.
## Quantitative backtesting Phase 7B — canonical CLI mode

Status: **COMPLETE — HISTORICAL SIMULATION ONLY**.

The file runner accepts validated `CANONICAL_TRADING_BRAIN` and preserves
`NONE`. Canonical mode builds strategy facts exclusively from published
historical candles and immutable producer ledgers. It advances genuine 1M and
5M #19/#20 structure, owner-authored displacement and prior-period policies,
existing #23 pooling/interactions, and the unchanged #21–#28/#11/#13 chain.
Only genuinely armed facts reach the existing Phase 4 lifecycle; Phase 5A
accounts closed trades and advances equity, and Phase 5B consumes finalized
accounting only.

Checked-in deterministic `canonical_zero` and `canonical_trade` fixtures cover
the zero-setup path and one full continuation trade. The latter uses a genuine
structural-plus-PDH pool selected by #23, later-candle entry and exit, exact
accounting, and canonical analytics. End-of-data never forces lifecycle facts;
unresolved orders and positions are exported explicitly. Full security
separation remains intact.

Passing Phase 7B does not establish production readiness or future
profitability and does not authorize live trading, mainnet execution, exchange
submission, wallets, signing, private keys, or credentials.

Verification on 2026-08-22: 6 focused Phase 7B tests passed; the canonical
zero and trade fixtures passed through the Python CLI; the trade fixture passed
through the PowerShell launcher with the same deterministic result identity;
all 114 backtesting tests passed; all 759 Trading Brain tests passed; and the
full repository suite passed with 884 tests.
## Backtesting recent-data probe and forward archive recorder

Status: **RECORDER COMPLETE; REAL DIAGNOSTIC REFUSED FOR INSUFFICIENT COVERAGE**.

The public BTC mainnet probe found contiguous, duplicate-free recent responses
for 1M, 5M, 15M, 1H, and 4H, each constrained to roughly the newest 5,000
candles. The common history was too short to provide the declared twenty-bar
4H structural/displacement warm-up followed by six scored hours. The interval
gate failed before strategy execution; no dates, thresholds, or strategy facts
were changed and no real diagnostic result was produced.

Added the public REST-polling forward archive and immutable snapshot boundary,
the `record` and `snapshot` CLI commands, and
`scripts/record_backtest_data.ps1`. Archives preserve exact Decimal/UTC closed
candles, checksums, resume identity, gap/staleness state, bounded recovery, and
graceful interruption. Only verified immutable snapshots are compatible with
the backtest CLI. Longer historical testing now requires accumulated recordings
or a separately approved source.

This capability is public market-data recording only. It provides no exchange,
account, order, wallet, signing, private-key, mainnet-execution, or live-trading
authority.

Verification on 2026-08-23: 18 focused coverage/downloader/recorder tests
passed; all 123 backtesting tests passed; 11 interface-contract tests passed;
all 759 Trading Brain tests passed; and the full repository suite passed with
893 tests.

## Owner minimum-R and performance-readiness policies

Status: **IMPLEMENTED — VERSIONED, OPT-IN, SIMULATION/RESEARCH ONLY**.

Added `OWNER_MIN_RR_V1` with exact 1.0R model thresholds while preserving the
original default exact 2.0R behavior and legacy identity. Explicit policy runs
bind policy identity to #27 qualifications, run manifests, results, and
summaries. Frozen #28 entry, #13 stop, and #24 target facts are never moved or
reselected.

Added read-only `OWNER_WIN_RATE_OBJECTIVE_V1`, consuming finalized canonical
classification counts and net expectancy. It requires 200 out-of-sample trades,
win rate >= 0.60, and positive net expectancy; BTC/ES/NQ remain isolated and no
combined result exists without an explicit universe. It cannot feed back into
trading or authorize live execution. Neither policy guarantees profitability.

Verification on 2026-08-24: 36 focused policy/#27/interface tests passed; all
123 backtesting tests passed; all 766 Trading Brain tests passed; and the full
repository suite passed with 900 tests.

## BTC scientific validation framework

Status: **IMPLEMENTED — ADVISORY INFRASTRUCTURE ONLY; NO BTC CONCLUSION YET**.

Added a separate downstream `backtesting.scientific_validation` contract with
immutable locked configuration/dataset identities, contiguous chronological
TRAIN/VALIDATION/final untouched TEST partitions, immutable walk-forward folds
and fold results, descriptive-only regime facts, pre-test owner-authored
parameter-sensitivity records, explicit Bonferroni multiple-testing lineage,
anti-overfitting assessments, and deterministic trade-level 95% percentile
bootstrap intervals for win rate, net expectancy, and mean net R.

The BTC-only owner gate consumes finalized immutable accounting projections and
explicit frozen planned-R:R facts. It returns `INSUFFICIENT_EVIDENCE` below 200
out-of-sample trades, otherwise `FAIL` unless win rate is at least 0.60, net
expectancy after modeled costs is positive, and every accepted setup planned at
least 1.0R; only then can it return advisory `PASS`. Every snapshot explicitly
denies trading authority and strategy mutation. No ES/NQ result, optimization,
network access, archive mutation, account behavior, or execution capability was
added.

Verification on 2026-08-25: 8 focused scientific-validation tests passed; all
149 backtesting tests passed; all 766 Trading Brain tests passed; and the full
repository suite passed with 926 tests.
# ES/NQ Futures Market Data Phase 1 (2026-08-26)

- Added the isolated, provider-neutral `futures_data` package for ES and NQ
  individual outright futures only.
- Added an injected-transport Massive adapter tested exclusively with local
  mocks. No Massive account, credential, network request, subscription, or
  download was used.
- Added exact contract/bar records, point-in-time rollover facts, CME session
  classification, deterministic archives/checksums, single-writer protection,
  bounded rate/retry policy, dry-run planning, and delayed research-collector
  policy.
- Archive destinations are isolated as `data/backtests/es_forward_archive_1`
  and `data/backtests/nq_forward_archive_1`; no archive was created in Phase 1.
- Futures validation remains market-isolated from BTC and advisory-only. No
  execution, broker, account, wallet, signing, or order capability was added.
- This phase does not authorize live data acquisition, scheduling, backtesting,
  or trading. Licensing and entitlement details require owner confirmation
  before any credential workflow.

## ES/NQ corrected raw probe and backfill preflight tooling (2026-08-26)

- The corrected ESM6/NQM6 five-session probe is locally reproducible from six
  retained provider responses. Raw and normalized SHA-256 values, row counts,
  identities, UTC/Chicago boundaries, ordering, and zero-gap results validate.
- Added a metadata-only, no-retry historical-backfill preflight. A later
  owner-attended run retains contract metadata, rejects non-quarterly or
  non-outright instruments, caps history at two years, and produces isolated ES
  and NQ request/storage/time inventories without downloading aggregate bars.
- The preflight does not start a backfill or recorder. Future strategy
  acceptance still requires at least 200 finalized untouched out-of-sample
  trades per market; calendar history alone is not evidence of that sample.
## Backtesting Engine Core v1 (2026-08-27)

- Added the separate provider-neutral `backtesting.core_v1` boundary implementing
  `Trigger -> Action -> Strategy -> CalculationEngine -> BacktestResult`.
- Added immutable/versioned event, bar, action, order, fill, position, accounting, capability,
  archive-adapter, instrument, execution, risk, and chronological split contracts.
- Added deterministic fixture/no-op strategies, explicit stable event priority, point-in-time archive
  visibility, individual ES/NQ active-contract enforcement, next-valid-bar conservative execution,
  Decimal costs/accounting, and advisory-only evidence gating.
- Added JSON schemas, synthetic configuration, architecture/contract documentation, audit report,
  and focused offline tests.
- Core v1 is simulation-only and remains inaccessible to credentials, providers, recorders,
  exchange submission, wallets, brokerage accounts, and live trading.
## Core v1 production archive adapters (2026-08-27)

- Added a streaming, read-only Pass B v3 adapter for exact ES and NQ individual-contract archives.
- Added a strict BTC Phase 7 completed-slice adapter classified `PARTIAL_RESEARCH_ONLY`.
- Verified the complete promoted ES/NQ hash, plan, continuation, calendar, rollover, raw,
  normalized, manifest, transaction-descriptor, and checkpoint chain without running a strategy.
- ES fingerprint: `857fbdcfe324db45b88a364ac3923a5f23ae12017851d93140be3e23a6bd13d4`.
- NQ fingerprint: `8cc8cb7f803e2de7f7d63f3652feafe8162d16106fd05f11f60cba5dcf7fc323`.
- BTC partial fingerprint: `edb041de2e9495b28765c8db1ebe8e32585e732983a5fc1bfe76aafaace58996`.
- This enables read-only ES/NQ adapter smoke inspection only. It adds no execution capability and
  does not authorize strategy research, provider access, recorder/collector control, or trading.
## Core v1 bounded read-only archive smoke (2026-08-27)

- Completed deterministic read-only ES/NQ integration smoke over explicit contract/session slices.
- ES and NQ NoOp and non-predictive mechanical fixture runs replayed identically in fresh engines.
- Verified sparse data-quality facts, frozen rollover events, next-bar fills, adverse slippage, fees,
  flat position completion, accounting lineage, fail-closed adversarial cases, and market isolation.
- BTC completed-slice validation passed as `PARTIAL_RESEARCH_ONLY`; no BTC trade fixture ran.
- ES/NQ archive tree and BTC completed CSV hashes matched before and after; zero archive writes.
- Results are integration evidence only and contain no performance or predictive claim.
