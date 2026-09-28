# Quantitative Backtesting Architecture

Status: Phase 3 deterministic read-only Trading Brain evaluation boundary. It
evaluates setup facts but has no orders, fills, positions, or performance engine.

## Boundary and dependency direction

`historical source -> normalization -> validation -> immutable dataset/manifest
-> point-in-time view -> one-way adapter -> frozen Trading Brain public inputs`

The `backtesting` package is a top-level peer of `strategy`. It may depend on
the frozen `strategy.trading_brain` contract version and public-entry-point
manifest. The Trading Brain must never import `backtesting`, and the adapter
does not invoke, reproduce, or modify Trading Brain strategy, execution,
accounting, or analytics behavior.

`market_data.py` owns exact historical candle records, dataset validation,
content fingerprints, gaps, and multi-timeframe visibility. `manifests.py` owns
dataset provenance and deterministic run intent. `adapter.py` owns the sole
translation into approved candle inputs. No module imports exchange clients,
WebSockets, wallets, signing, order submission, risk/account mutation, or the
legacy paper engine.

`replay.py` owns only the deterministic historical clock, immutable candle-close
events, atomic timestamp batches, published availability snapshots, read-only
visibility queries, and resumable cursor checkpoints. It imports the frozen
Trading Brain contract version for compatibility validation but never calls a
Trading Brain entry point.

`orchestrator.py` owns the post-publication Phase 3 evaluation context, approved
primitive invocation order, immutable traces/setup facts, minimal historical
strategy state, and its checkpoint relationship. It never imports or invokes
#29.1 or any later execution, risk, lifecycle, accounting, or analytics owner.

## Historical data and determinism

- Each dataset is one source/exchange identity and uses immutable, UTC-aware,
  closed candles with exact `Decimal` OHLCV. Binary floats are rejected rather
  than converted.
- Supported Phase 1 timeframes are the repository's established `1m`, `5m`,
  `15m`, `1h`, and `4h`. Their opens align to UTC epoch boundaries and close is
  exactly one interval later.
- Canonical dataset order is `(open_time, symbol, timeframe, candle_id)`.
  Duplicate coordinates and identities, overlaps, incomplete/future candles,
  invalid geometry, and non-finite numbers fail closed.
- Gaps are either rejected or retained explicitly under `RECORD`; no candle is
  forward-filled. Fingerprints cover ordered identities, timestamps, exact
  economic values, and closed status.
- Dataset and replay intervals are explicitly half-open `[start, end)`. Dataset
  creation time is provenance and is not part of the content fingerprint.
- A run manifest records immutable data/configuration/version inputs, starting
  equity, execution-cost configuration identity, an explicit seed, practical
  runtime facts, `PAPER_SIMULATION`, and disabled exchange submission. It is a
  declaration only and cannot execute a run.

## Multi-timeframe visibility and adapter choice

A candle becomes visible at `close_time`, including a higher-timeframe candle.
At a lower-timeframe event time, only records satisfying
`higher.close_time <= event_time` are accessible. Forming and future candles
are never exposed; missing candles remain missing.

The frozen Trading Brain currently has two market representations. #19 accepts
a pandas frame; #20/#25 accept mappings. The canonical adapter starts from the
same validated record sequence, emits a pandas frame with object-backed
`Decimal` columns for #19, and immutable mapping proxies for #20/#25. Both use
the same candle IDs, exact values, ordering, closed flag, and Hyperliquid-style
integer epoch milliseconds. This narrow representational split follows the
frozen interface and does not create a second strategy model.

Phase 3 extends that same adapter—not a second conversion path—with immutable
`DeliveryCandle` records for canonical #11. IDs, Decimal OHLC, 1M ownership, and
close timestamps are preserved from the same validated published history.

## Phase 2 event clock and atomic publication

Only candles whose `close_time` is in the run manifest's half-open
`[replay_start_inclusive, replay_end_exclusive)` interval become events.
`close_time` is both the event timestamp and visibility boundary. The clock is
driven solely by the precomputed validated event sequence; it never reads wall
time, sleeps, uses randomness, performs I/O, or depends on scheduler timing.

All candles with one close timestamp form one immutable `ReplayBatch`. Events
inside it use the canonical key `(symbol ASC, timeframe duration ASC,
timeframe value ASC, candle_id ASC)`. Batches use `(close_time ASC)` and
zero-based sequence numbers. Event, batch, availability, and complete sequence
identities hash immutable dataset/run/version coordinates and these canonical
positions.

Publication is atomic: before `advance`, none of the next batch's candles are
queryable. `advance` installs every stream addition for that timestamp before
returning its `ReplayPublication`; afterward, all are visible. There is no
callback or partial-batch observation point. This is especially important when
lower- and higher-timeframe candles close together.

Each symbol/timeframe history remains separate. Queries return immutable tuples
from already-published history and require UTC timestamps within run scope and
not beyond current simulated time. `history`, `latest`, and bounded `lookback`
are idempotent reads. Unknown streams, negative/bool lookbacks, naive times,
future times, and out-of-scope times fail closed. Missing candles remain gaps;
Phase 2 neither fills them nor constructs higher-timeframe candles.

The clock transitions `READY -> ACTIVE -> COMPLETED`. `start` is allowed once.
An event-free interval transitions directly from `READY` to `COMPLETED`. The
final publication transitions to `COMPLETED`; explicit advance after completion
or before start fails. Python iteration starts a ready clock and ends normally
at completion. Simulated time is monotonic and cannot be caller-directed, which
prevents skipped or conflicting advancement.

An immutable `ReplayCheckpoint` stores its schema version, dataset identity and
fingerprint, run and Trading Brain contract identities, complete event-sequence
identity, state, current time, next batch cursor, and last published batch ID.
Its dictionary representation uses enum strings and an ISO-8601 UTC timestamp.
Resume rebuilds published visibility deterministically and rejects any identity,
version, cursor, clock, last-batch, or sequence mismatch. The cursor is the next
unpublished batch, so resume neither duplicates nor skips publication. Strategy
state is deliberately absent.

Phase 1 permits one symbol per validated dataset. Phase 2 preserves that scope;
multi-symbol replay would require a later versioned Phase 1 dataset contract and
is not inferred here.

Failures at this boundary are exceptions before publication. A rejected start,
advance, query, or checkpoint does not alter published history or clock cursor.

## Phase 3 strategy-orchestration boundary

Evaluation occurs only after Phase 2 has returned a complete atomic
`ReplayPublication`. The context freezes dataset/fingerprint, run, replay batch,
symbol, timeframe set, strategy/model configurations, Trading Brain contract,
calculation version, and UTC evaluation timestamp. Every adapter read is capped
at that timestamp. The orchestrator has no callback during batch publication,
so same-timestamp event order cannot leak into strategy results.

The dependency-ready invocation order is:

1. #19 mechanical swings and #20 structural promotion from each published
   timeframe history; #25 FVG detection from the same adapter history.
2. An explicit immutable prior structural state is preserved through #21. #22
   creates/preserves OTE from its active range.
3. Explicit upstream liquidity references are consumed by #23; #24 freezes the
   nearest canonical target from those pools and the published current price.
4. #26 evaluates OTE/imbalance relationships using detected #25 facts.
5. Continuation calls #27 Phase A directly. Reversal #1 runs the #11 start,
   reference, wait, and body-close state machine from adapter-provided 1M
   candles, then calls #27 Phase A from the confirmed process.
6. Eligible Phase A facts flow through #28 frozen zone/EQ selection, #13 frozen
   stop selection, and #27 final geometry/R validation.
7. Evaluation stops. #29.1 and every later primitive are inaccessible.

Candles cannot canonically manufacture displacement qualification, accepted MSS,
protected structure, delivery legs, sweep facts, or higher-order liquidity
references because those have separate owners. A setup request may therefore
carry those immutable prior canonical facts. It may not carry a final setup,
entry, stop, or final qualification. Missing facts produce immutable
`MissingPrerequisite` records and canonical candidate/waiting/fail-closed states;
the orchestrator never substitutes an easier fact or converts absence into
eligibility.

Every approved call emits a `PrimitiveResultReference` containing its exact
canonical result and state/reason. A trace and batch setup fact append to the
immutable `OrchestrationState`; prior results and terminated range/OTE/LRL/CISD
facts are retained rather than deleted. The aggregate outcome distinguishes no
setup, waiting, candidate, MSS/CISD-confirmed reversal, armed continuation,
entry-zone-armed reversal, canonical rejection, and invalid/fail-closed. Exact
canonical entry, stop, selected target, risk, reward, and R records are held by
reference without recalculation.

The same batch plus identical state/request returns the prior immutable result.
A changed request for an already committed batch is a conflict. Batches must be
consumed consecutively from sequence zero; skipped batches, older timestamps,
or mismatched dataset/run/configuration/contract/calculation versions fail
before state changes.

`OrchestrationCheckpoint` binds the complete immutable orchestration state ID to
the compatible Phase 2 checkpoint and its next-batch cursor. Resume validation
recomputes this identity and rejects any state, dataset, fingerprint, run,
contract, calculation-version, or cursor mismatch. Persistence is not owned yet.

## Planned phases

1. **Complete:** immutable data contracts, validation, manifests,
   multi-timeframe visibility, and compatibility adaptation.
2. **Complete:** deterministic closed-candle event clock, atomic timestamp
   publication, read-only point-in-time histories, and replay checkpoints.
3. **Complete:** read-only setup evaluation through canonical final #27, using
   only approved interfaces and explicit immutable upstream prerequisites.
4. **Complete:** deterministic canonical #29.1-#29.6 paper lifecycle simulation.
5. Planned canonical accounting and performance-result handoffs.
6. Separately authorized research workflows such as walk-forward evaluation;
   optimization is not implied by this architecture.

Historical simulation remains separate from the future 24/7 paper/testnet
runner. It does not share a live WebSocket loop, account mutation, exchange
client, private key, signing path, or order-submission capability. Nothing in
No backtesting phase authorizes live/mainnet or production trading.

## Phase 4 canonical trade simulation

`simulation.py` consumes an exact Phase 2 publication and its matching Phase 3
evaluation. It delegates the full flow without reimplementing calculations:
`#29.6 availability -> #29.1 order/fill -> #29.2 proposed size -> #29.3
protective facts -> #29.6 OPEN -> #29.4 exit/OCO -> #29.5 costs -> #29.6
CLOSED`.

Availability is #29.6's bootstrap boundary before a persisted position exists.
This is execution modelling, not authorization: the #29.2 proposal remains
`authorized=False`, and no market-health, portfolio, master-risk, exchange, or
account authority is emulated. Starting equity is copied unchanged from the run
manifest. Phase 4 never compounds or mutates it. Tick value, multiplier,
price/quantity grids, size bounds, risk percentage, and costs are explicit
immutable versioned inputs.

Orders activate after the armed setup's atomic batch, so that batch cannot fill
them. A later fill can create sizing, protection, and OPEN facts, but the fill
candle is never reused for exit resolution. Exit evaluation begins in a later
batch. Optional chronological `PriceObservation` facts may prove intrabar order;
otherwise canonical gap and adverse OHLC collision rules apply. No missing bar
is forward-filled and unrelated simultaneous timeframes cannot affect an order.

Only one unfinished lifecycle is admitted; canonical #29.6 independently
enforces the global one-OPEN-position rule. Consumed setup IDs, all canonical
histories, lifecycle references, and fail-closed prerequisites are immutable.
Checkpoints bind the full state to exact Phase 2/3 cursors and record active
order, protective-set, and open-position identities.

The planned Phase 5 may consume completed lifecycle and cost records for
#29.7.1 accounting and later performance reporting. Phase 4 does not calculate
PnL, realized R, equity changes, or analytics.

## Phase 5A trade accounting and simulated equity

After #29.6 produces an immutable CLOSED snapshot and #29.5 costs exist, the
simulator calls frozen `TradeAccountingEngine.calculate` exactly once. The
backtesting package does not calculate or reclassify PnL, R, costs, outcomes,
or economic prices. The resulting #29.7.1 record is linked to the exact fill,
size, exit, cost, and closed-position facts.

`accounting.py` owns only an immutable equity-event chain. Sequence zero is a
deterministic initial snapshot sourced solely from the run manifest. Each later
snapshot identifies its predecessor and canonical TradeAccounting record and
enforces `new equity = prior equity + account_equity_change`. Duplicate replay
is idempotent; run/version mismatches, forks, retroactive records, inconsistent
pre/post equity, and noncanonical same-time order are rejected.

The canonical source fixes #29.7.1 pre-trade equity to #29.2 pre-fill equity and
post-trade equity to that value plus net PnL, but defines no separate fixed-base
ledger. The explicit Phase 5A policy is therefore `COMPOUNDED`: only a committed
preceding snapshot can supply a future fill's sizing equity. Existing sizing is
never changed, and a trade cannot see its own or future accounting. Zero or
negative terminal equity remains an exact ledger fact; canonical #29.2 then
fails closed for any subsequent size instead of the ledger inventing capital.

Phase 5A checkpoints extend the Phase 2/3/4 binding with the latest accounting
record and equity-snapshot identities. Planned Phase 5B may orchestrate frozen
#29.7.2 analytics downstream of finalized TradeResults. Phase 5A invokes none of
those analytics and provides no reports, persistence, or performance claims.

## Phase 5B canonical analytics and BacktestResult

`analytics.py` is a terminal, read-only orchestrator. It invokes frozen
#29.7.2 owners in dependency order and retains their records by identity; it
contains no analytics formulas. For a compatible single-strategy run it calls
.1–.10, .12–.15, and .18. `.11` remains explicitly `NOT_APPLICABLE` without a
finalized canonical DAILY period/equity-observation series. `.16`, `.17`, `.19`,
and `.20` remain explicitly `NOT_APPLICABLE` without immutable portfolio or
universe definitions. No strategy or membership is invented.

The immutable `BacktestResult` binds run/dataset/contract/configuration
identities, half-open replay interval, UTC `as_of`, starting/ending equity,
canonical counts, every analytics reference/status, and a complete lineage
fingerprint. Canonical NULL, infinity, insufficient-sample, empty-distribution,
constant-series, and status values stay inside their owning records; the result
does not coerce them to zero or copy/recompute metrics.

Final results require a completed interval, no unfinished lifecycle, finalized
accounting no later than `as_of`, an unbroken equity ledger, unique trade keys,
and one compatible scope/version. Full-history periods use the run's explicit
UTC AccountTimezone and exact `[start, end)` horizon. Missing periods are never
forward-filled. Identical orchestration is deterministic; analytics checkpoints
bind simulation state, accounting cursor, equity snapshot, result, and `as_of`.
Analytics cannot feed strategy, sizing, execution, or equity.

Planned Phase 6 may provide a reproducible export/report layer over this frozen
in-memory result. Phase 5B adds no JSON/CSV/SQLite output, charts, optimization,
walk-forward/Monte Carlo work, network/exchange access, or live execution.

## Phase 6 reproducible local command and exports

Phase 6 adds an offline file boundary around the unchanged Phase 1–5B pipeline.
The canonical command is:

`python -m backtesting run --data <dataset_manifest.json> --config
<backtest_config.json> --output <directory>`

`validate` checks both inputs without replay, and `inspect` prints stable
dataset/run facts. `run --overwrite` is the only way to replace an existing
output. Exit codes are 0 success, 2 input/config validation, 3 replay, and 4
output-policy failure. The PowerShell wrapper is `scripts/run_backtest.ps1`.

The data manifest explicitly maps each timeframe to a CSV file; filenames are
never guessed. CSV decimal text goes directly to Decimal and timestamps require
UTC `Z`. JSON configuration is schema-versioned, strictly field-checked, rejects
binary JSON floats and secret-like keys, and explicitly supplies run interval,
capital/risk/instrument/cost/version/timezone/seed facts. Phase 6 currently
requires `setup_request_mode: NONE`: it performs a complete zero-setup pipeline
without fabricating Phase 3 structural prerequisites.

Exports are UTF-8 with LF newlines and stable JSON keys/CSV columns and row
ordering. Decimal values are strings; NULL and canonical status values remain
distinct, and infinity is a tagged status rather than invalid JSON. The atomic
run directory contains manifests, result, trades, equity, summary, and SHA-256
checksums. A temporary sibling directory is renamed only after every artifact
succeeds, so failure cannot resemble a complete run.

Phase 6 is historical simulation only. It downloads nothing, reads no secret
environment, contacts no exchange, and adds no optimization, walk-forward,
Monte Carlo, dashboard, wallet/signing/mainnet, or 24/7 runner capability.

## Phase 7A public historical-data acquisition

`downloader.py` is a terminal producer for the Phase 1 boundary. It sends only
unauthenticated HTTPS `candleSnapshot` requests to the repository-approved
Hyperliquid public `/info` endpoint. Testnet is the default. Public mainnet data
requires explicit `--data-network mainnet`; that selects market data only and
does not authorize or initialize trading.

The command is:

`python -m backtesting download --symbol BTC --timeframes 1m 5m --start
2026-08-01T00:00:00Z --end 2026-08-01T01:00:00Z --data-network mainnet
--output .\data\btc-short`

Requests use bounded candle windows, HTTPS certificate verification, timeouts,
finite exponential-backoff retries, and retry only transient transport/429/5xx
failures. Responses are parsed without binary floats, normalized immediately to
Phase 1 records, and checked for identity, interval, closure, ordering,
duplicates, overlaps, and gaps. Forming candles are excluded and recorded; no
bar is synthesized or forward-filled.

Each symbol/timeframe has one stable canonical CSV. The versioned manifest
records network, requested interval, validation cutoff, explicit gaps and
exclusions, file checksums, and the Phase 1 dataset fingerprint. Window progress
is committed to a checksum-protected `.partial` sibling. `--resume` verifies its
request identity and files before continuing; `--overwrite` is explicit and
mutually exclusive. Only an atomically renamed complete directory is accepted
by Phase 6 validate/inspect/run.

The PowerShell helper is `scripts/download_backtest_data.ps1`. Phase 7A never
starts a backtest, imports an order client, authenticates, reads secrets, or
supports wallet/signing/private-key behavior.

## Phase 7B prerequisite 5: prior-period liquidity references

The owner-authored, versioned `OWNER_PRIOR_PERIOD_V1` policy is an additive
producer at the Trading Brain #23 boundary. From already-published validated
1M candles it registers only complete prior-day PDH/PDL and prior-ISO-week
PWH/PWL facts. Local calendar boundaries use the configured IANA
`AccountTimezone`; conversion to UTC therefore preserves DST-variable period
lengths. A reference becomes visible only at its completed period end.

Phase 3 passes immutable published 1M history to this producer and supplies its
active references to the existing #23 inventory engine alongside structural
references. It does not synthesize missing bars, pool references, infer sweeps,
or advance #24 and later owners. The append-only ledger retains registrations,
consumption, and explicit upstream invalidation. The policy remains historical
simulation infrastructure and supplies no order, risk, credential, exchange,
or live-trading authority. Full canonical CLI mode remains disabled pending the
remaining explicitly owned orchestration work.
## Phase 7B canonical CLI mode

`setup_request_mode: CANONICAL_TRADING_BRAIN` is the full historical strategy
path; `NONE` remains the zero-authority smoke path. Canonical mode requires
explicit 1M execution and 5M structure roles, scored and warm-up boundaries,
strict #19 2-left/2-right configuration, `OWNER_MECHANICAL_V1`,
`OWNER_PRIOR_PERIOD_V1`, enabled prior-period families, IANA AccountTimezone,
instrument/risk/cost/version identities, a deterministic seed, and explicit
simulation-only status. Unknown modes, policies, streams, secret-like fields,
and prebuilt intermediate facts fail validation.

At each atomic timestamp, Phase 4 first advances existing orders and positions.
Phase 3 then advances #19 swing availability, #20 initialization and accepted
#16/#20 commits, ranges, OTE, structural and prior-period references, unchanged
#23 pool/interaction rules, LRL, FVG, confluence, qualification, entry zone,
stop, and final qualification. Only a newly armed immutable fact reaches Phase
4, so its creation candle cannot fill it retroactively. Finalized #29.7.1
accounting updates compounded equity once; only finalized accounting facts
enter the final analytics pass.

The synthetic `canonical_zero` and `canonical_trade` fixtures invoke actual
public producers. The trade path forms a 1M structural-plus-PDH pool through
#23, arms a 5M continuation, fills and exits on later 5M candles, and reaches
accounting and analytics. Pending orders and open positions are never
force-resolved at end-of-data and are reported separately.

This mode is deterministic historical simulation only. It has no network,
exchange submission, wallet, signing, private-key, mainnet execution, or
analytics-to-strategy feedback path. Results neither demonstrate future
profitability nor authorize live trading.
## Recent coverage probing and forward archives

The public `candleSnapshot` endpoint is a recent-history interface, not a
long-range archive. The 2026-08-23 BTC probe returned approximately 5,000
candles per timeframe: 1M began at `2026-08-19T17:38:00Z`, while progressively
higher timeframes reached farther back. The five-stream overlap could not
provide twenty prior 4H bars plus a six-hour scored interval, so no diagnostic
strategy run was authorized. Longer tests require accumulated forward archives
or a separately approved historical data source.

`python -m backtesting record` is a public unauthenticated REST-polling terminal
producer. Testnet is the safe default and public mainnet requires an explicit
flag. It bootstraps the newest available candles, commits closed Phase 1 records
only, deduplicates exact replay, rejects conflicts, records gaps, detects stale
streams, and uses bounded exponential retry with deterministic injectable
jitter. DNS, TLS, timeout, HTTP 408/425/429, and transient 5xx failures reconnect
without converting malformed or permanent errors into retry loops. Per-request
retry and consecutive-poll budgets are distinct; budget exhaustion transitions
health to `STALE` while later polls remain eligible to recover.

Hyperliquid documents `startTime` and `endTime` as inclusive and reports candle
`T` as the inclusive final millisecond. The canonical adapter first validates
and normalizes every returned record to an exclusive close. A candle opening
exactly at `endTime` belongs to the next interval; when a wall-clock polling end
falls inside the current interval, that one validated forming candle is also
excluded. Any other record outside the requested window or visibility boundary
is rejected and logged with its exact request/open/close timestamps. Historical
downloads whose validation cutoff falls inside an interval require coverage
only through the last canonical closed boundary for each timeframe.

Each poll stages every changed stream plus the next checksum manifest in a
durable transaction. The transaction record is persisted before any archive
file is replaced. On restart, each target must match either its recorded old or
new checksum; compatible partial commits are completed, while forks or corrupt
staging fail closed. Orphan pre-transaction staging is discarded only after the
previous manifest remains authoritative. Stream and manifest writes use flushed
temporary files and atomic replacement.

Detected internal gaps are requested directly using their exact canonical
boundaries, up to the configured backfill budget. Returned public candles pass
the same identity, closure, interval, Decimal, conflict, and Phase 1 validation
as normal polling. Missing candles remain explicit gaps; the recorder never
forward-fills or synthesizes data. Each stream records gap count, staleness, and
backfill attempts. Archive states are `RECORDING`, `STOPPED`, `STALE`, and
`GAPPED`. Ctrl+C writes an expected `STOPPED`; unexpected termination records
`STOPPED` and emits an alert before propagating the error.

Optional JSON Lines event and alert sinks contain a fixed, secret-free schema:
timestamp, level, event, state, symbol, timeframe, and approved scalar details.
Alerts fire on transitions to `STALE` or `GAPPED` and on unexpected `STOPPED`.
`scripts/supervise_backtest_recorder.ps1` is a foreground Windows supervisor
with bounded process restarts and exponential restart delay. It installs no
service, scheduled task, or startup entry and exits after a clean Ctrl+C stop.
It invokes only `python -m backtesting record`; it owns no trading behavior.
Relative archive and log paths are normalized against the repository containing
the supervisor script before any child process starts, so launch working
directory cannot redirect writes into `C:\Windows\System32` or another caller
directory. `-ResolvePathsOnly` reports those resolved paths and exits without
creating logs or launching Python.

The growing archive is never a backtest input. `python -m backtesting snapshot`
verifies checksums and exact `[start, end)` coverage, rejects every gap, and
atomically freezes a Phase 6/7-compatible immutable dataset. This recorder has
no strategy evaluation, account API, exchange client, order submission,
wallet, signing, private-key, credential, or automatic-backtest dependency.

Owner-reviewed public BTC startup example (run from the repository root only
after tests and archive verification pass):

```powershell
& .\scripts\supervise_backtest_recorder.ps1 -Symbol BTC -Timeframes @('1m','5m','15m','1h','4h') -DataNetwork mainnet -Archive .\data\backtests\btc_forward_archive_2 -LogDirectory .\outputs\recorder_health\btc_forward_archive_2 -PollSeconds 15 -MaximumRestarts 5
```

For owner-scoped restart recovery on Windows, install the disabled logon task with
`scripts/install_btc_forward_recorder_task.ps1`, validate and enable it with
`scripts/enable_btc_forward_recorder_task.ps1`, and use
`scripts/start_and_verify_btc_forward_recorder_task.ps1` for the initial controlled
handoff. The task uses `IgnoreNew` plus a named mutex, runs at limited privilege with
the interactive owner token, and is restricted to the public BTC research archive.
`scripts/get_btc_forward_recorder_status.ps1` reports health only when a recent
completed `RECORDING` poll exists. Close any legacy foreground supervisor before the
initial task start because processes launched before singleton support do not own the
new mutex.

This is public mainnet market-data recording only. It does not authorize or
submit trades, and it must not be configured as automatic startup without a
separate owner decision.

## Versioned minimum-R and performance-readiness policies

Canonical-mode configuration may explicitly select `risk_reward_policy_id`.
Legacy omission retains `CANONICAL_MIN_RR_V1` and historical exact 2R behavior.
New research configurations use `OWNER_MIN_RR_V1` (exact 1R for Continuation
and Reversal #1). The selected ID is bound into run/result lineage and summaries
without changing frozen entry, stop, target, execution, or risk ownership.

`performance_objective_id: OWNER_WIN_RATE_OBJECTIVE_V1` requests an advisory
post-analytics snapshot. Below 200 out-of-sample trades it is
`INSUFFICIENT_SAMPLE`; otherwise canonical win rate must be at least 0.60 and
net expectancy after configured costs must be positive. BTC, ES, and NQ remain
isolated. No ES/NQ or combined result is fabricated without data and an explicit
universe. This output never enters replay inputs and never authorizes trading.

## Scientific validation framework

`scientific_validation.py` is a separate downstream research boundary. It
freezes configuration/dataset identities before evaluation, owns chronological
TRAIN/VALIDATION/final-TEST partitions and walk-forward folds, records
descriptive regimes, owner-authored sensitivity observations, multiple-testing
families, anti-overfitting assessments, and deterministic Decimal-based 95%
bootstrap intervals. It consumes immutable finalized accounting projections
and never calls replay, qualification, risk, sizing, execution, or exchange
interfaces.

The BTC-only owner gate returns `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE` for
the locked untouched test. All outputs are advisory and structurally incapable
of authorizing or modifying a trade. See `SCIENTIFIC_VALIDATION.md` for the
public research contract and explicit statistical limitations.
