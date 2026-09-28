# Owner-Authorized Implementation Decisions

## #22 OTE directional arithmetic

The persisted #22 note locks directional 0.50–0.79 OTE orientation but does not
state the arithmetic formula for the 0.79 price. On owner authorization to select
the best interpretation, the port uses conventional deep-retracement geometry:

- bullish: discount-side zone, `OTE79 = High - 0.79 * (High - Low)`;
- bearish: premium-side zone, `OTE79 = Low + 0.79 * (High - Low)`;
- both: `EQ50 = Low + 0.50 * (High - Low)`.

This decision does not alter #21 boundaries. It should be synchronized into the
Obsidian canonical source as a formal owner amendment before production release.

## #28 directional meaning of "deepest"

The persisted #28 note locks the ordering `IFVG > FVG > newest > deepest > ID`
but does not provide arithmetic for the `deepest` tie-break. The port compares
the immutable raw zone midpoint for candidates tied on type and confirmation
time: lower midpoint first for bullish setups and higher midpoint first for
bearish setups. This implements directional retracement depth without using
future price or mutable mitigation depth. It should be synchronized into the
canonical source before production release.

## #29.1 OHLC touch chronology and #29.6 boundary

The persisted #29.1 note specifies OHLC touch fills, exact frozen-EQ pricing,
same-candle ambiguity prevention, and the one-live-position invariant, but does
not define an intrabar path or assign #29.1 ownership of position state. The
port treats touch as inclusive containment `Low <= frozen EQ <= High` and only
evaluates candles whose interval begins at or after activation. An in-progress
candle cannot retroactively fill. The one-position invariant is consumed as an
immutable availability fact owned by the later #29.6 boundary; missing, stale,
mismatched, or non-zero facts fail closed. #29.1 never creates a Position.

## #29.2 tick-value arithmetic and optional maximum quantity

The locked #29.2 note requires tick, tick-value, and contract-multiplier-aware
sizing but does not state whether configured `tick_value` already embeds the
multiplier. The port keeps all three canonical inputs explicit and uses
`risk_per_unit = (abs(Entry-Stop)/minimum_tick) * tick_value * contract_multiplier`.
`RiskPercent` is interpreted as percentage points, so maximum risk is
`pre_fill_equity * RiskPercent / 100`. The runtime registry specifies minimum
quantity and increment but no maximum quantity; therefore maximum quantity is
an optional exchange constraint. When supplied it caps quantity before the same
downward increment normalization. No unconfigured maximum is invented.

## #29.3 protective lifecycle and unresolved exchange OrderType

The locked #29.3 source owns construction of the OCO stop/target relationship
but assigns exit selection and chronology to #29.4. The enum registry names a
closed `OrderType` family without supplying its members. The port therefore
records the canonical #29.3-owned `STOP` versus `TARGET` intent kind and does
not falsely label the protective stop as the entry module's `LIMIT` type.
Protective intents may transition together from PENDING to ACTIVE, but #29.3
cannot mark either filled or cancel its sibling until a later #29.4 resolution
fact exists. All records remain non-submittable and explicitly unauthorized;
the existing authorization layers retain final veto authority.

## #29.5 configured cost bases and exact monetary precision

The locked #29.5 record and anti-double-counting boundary are explicit, while
the runtime cost models name their bases without giving formulas or a monetary
rounding increment. The port interprets percentage values as percentage points
and notional as `price * quantity * contract_multiplier`; `PER_UNIT` uses
quantity, `PER_CONTRACT` uses quantity times contract multiplier,
`FIXED_ORDER` applies once to entry and once to exit, and `FIXED_TRADE` applies
once overall. Fixed-tick friction is ticks times minimum tick, fixed-price is a
per-side price delta, and percentage friction is a percentage of that side's
mechanical price. All price friction is adverse by direction and is excluded
from explicit cash costs. Because no monetary increment or rounding mode is
registered, calculations remain exact Decimal values with no monetary rounding.
Dynamic `INSTRUMENT_SPECIFIC` and `VOLATILITY_DEPENDENT` models fail closed
until their formulas are configured canonically. Funding is not a canonical
#29.5 category and is not implemented.

## #29.6 / #29.1 availability bootstrap

The canonical lifecycle explicitly says that no Position object exists before a
confirmed fill, while #29.1 must enforce the one-live-position rule before it
can create that fill. The port resolves this interface boundary by having #29.6
derive an immutable availability fact from its append-only lifecycle history.
An empty history yields a confirmed global open count of zero; #29.1 consumes
that fact, and the confirmed fill can then create the OPEN Position. Availability
is global rather than per-symbol: the fact retains the requested symbol for
#29.1 identity validation, but its count includes every currently OPEN Position.
A query earlier than the newest lifecycle snapshot is marked unconfirmed and
therefore retains #29.1's fail-closed behavior.

## #29.7.2.3 ExpectancyStatus registry gap

The locked #29.7.2.3 specification and Amendment 003 name a closed
`ExpectancyStatus` enum family, but neither the canonical enum registry nor the
primitive, examples, amendments, golden scenarios, or recovered archive define
any of its members. The port does not invent status values. It records the
explicit canonical result directly: both expectancy values are `NULL` when the
finalized trade count is zero and are exact Decimal values otherwise. A status
field can be added only after canonical enum members are supplied.

## #29.7.2.4 ProfitFactorStatus registry gap

The locked #29.7.2.4 specification and Amendment 003 name a closed
`ProfitFactorStatus` enum family, but no member values are defined in the
primitive, canonical enum registry, amendments, tests, golden scenarios, or
recovered archive. The port does not invent enum values. It preserves the three
explicitly locked numeric states directly: a finite Decimal when gross loss is
positive, positive Decimal infinity when gross loss is zero and gross profit is
positive, and `NULL` when both are zero. A status field remains unavailable
until the canonical enum members are supplied.

## #29.7.2.6 EquityPoint drawdown ownership boundary

The locked #29.7.2.6 note names an `EquityPoint` shape containing
`drawdown_abs` and `drawdown_pct`, while the immediately downstream locked
#29.7.2.7 primitive explicitly owns peak equity, absolute/percentage drawdown,
and maximum drawdown. Recovery and underwater transitions are separately owned
by #29.7.2.12 and #29.7.2.13. The #29.7.2.6 port therefore emits only the
canonical equity observation and its immutable #29.7.2.5 source identity; it
does not populate, default, or precompute downstream drawdown/recovery fields.
This is the narrowest boundary that avoids inventing values and preserves the
declared dependency chain.

## #29.7.2.7 non-positive peak percentages and extrema ties

The canonical percentage formula divides absolute drawdown by applicable peak
equity and the global analytics rules require zero denominators to produce
`NULL`, but the source does not define percentage semantics for a negative peak.
A negative percentage would conflict with drawdown magnitude semantics. The port
therefore emits `NULL` percentage drawdown whenever peak equity is non-positive,
while retaining the fully defined absolute drawdown. It does not reject or alter
the upstream equity curve.

The source defines maximum drawdown as the maximum observed magnitude but gives
no identity tie-break when multiple chronological points have the same maximum.
The port preserves every tied maximum equity-point identity in canonical order
instead of selecting an arbitrary winner. Recovery-point and episode ownership
remain deferred to #29.7.2.12; equality with the peak mechanically produces zero
drawdown in #29.7.2.7 but is not labeled as a recovery here.

## #29.7.2.8 streak enum and maximum-tie registry gaps

The locked #29.7.2.8 note and Amendment 003 name closed `StreakDirection` and
`StreakStatus` enum families, but no members are defined in the primitive,
canonical enum registry, amendments, examples, tests, golden scenarios, or
recovered archive. The port does not invent enum values; authoritative
`TradeResult` values remain the only classifications consumed.

The source defines maximum consecutive WIN/LOSS counts but no identity
tie-break when multiple streaks share a maximum. The port retains every tied
maximum source-trade group in canonical chronological order rather than
selecting an arbitrary streak. It does not emit the broader run/transition
model owned by #29.7.2.14.

## #29.7.2.9 opaque period identity

Amendment 002 R1 freezes period types, timezone assignment, and half-open
boundaries but does not define a human-readable `period_id` format. Amendment
002 R2 separately requires IDs to be opaque and immutable. The port therefore
derives the period record ID deterministically from the exact scope, period
type, AccountTimezone, start/end instants, source/historical versions, and
calculation version. It does not invent a semantic date-string identifier.
Periods are explicitly requested: an empty requested period creates the locked
zero/`NULL` record, while an unrequested period remains missing (no record).

## #29.7.2.10 undefined general percentile contract

The locked #29.7.2.10 note says downstream layers must reuse a locked percentile
convention, but the primitive, amendments, registries, tests, golden scenarios,
and recovered distribution section define neither percentile levels nor a
general rank/interpolation formula. The archive only explicitly defines median
for a later underwater-duration use case (odd middle; even arithmetic mean).
The port therefore implements the explicitly owned raw NetPnL/NetR and
authoritative WIN/LOSS/BREAKEVEN distributions, with both canonical
chronological observations and exact sorted values. It emits no percentile,
quartile, variance, skew, kurtosis, or other statistic whose contract is absent.
Those fields must remain unavailable until the owner supplies the missing
general percentile contract.

## #29.7.2.11 finalized daily-equity integration boundary

The locked #29.7.2.11 definition requires finalized daily account-equity
observations and says that the daily series is established by #29.7.2.9. The
implemented #29.7.2.9 `PeriodStatisticsSnapshot`, however, intentionally owns
period trade statistics and contains no ending-equity field. Reconstructing
daily equity from trade PnL, carrying an earlier balance through a zero-trade
day, or adding an equity field retroactively to #29.7.2.9 would cross ownership
boundaries and weaken audit lineage.

The #29.7.2.11 port therefore requires an explicit immutable
`DailyEquityObservation` linked one-to-one to its finalized DAILY #29.7.2.9
snapshot and to its upstream equity snapshot/point identity. A zero-trade day
participates only when that explicit observation is supplied. Missing days are
recorded and never forward-filled; a return is not computed across a period
gap. This is the narrowest fail-closed adapter until the canonical owner adds a
daily-equity field to an upstream record.

The existing #29.7.2.7 implementation stores percentage drawdown in percent
points (`absolute / peak * 100`), while #29.7.2.11 Calmar divides a decimal
annualized return by a decimal drawdown fraction. The port preserves the exact
upstream percent-points value and records the explicit `/ 100` conversion as
`maximum_drawdown_fraction` before calculating Calmar; it does not recalculate
drawdown from equity.

## #29.7.2.12 initial peak timestamp boundary

The locked recovery object requires `peak_time`, and the initial-equity rule
allows the explicit starting equity to serve as the first peak. The existing
#29.7.2.7 `DrawdownSnapshot` preserves `starting_equity` but not the timestamp
or identity of that baseline observation. Assigning the first trade time or an
arbitrary zero timestamp would invent chronology and could change the first
episode's recovery duration.

The #29.7.2.12 port therefore requires an immutable
`StartingEquityObservation` whose equity and equity-curve identity must match
the #29.7.2.7 snapshot. Its timestamp must precede or equal the first drawdown
point. Later peak timestamps come directly from authoritative drawdown points.
This explicit boundary supplies only the missing baseline identity/time; the
engine never reconstructs equity, peaks, drawdown depth, percentage, or maximum
drawdown facts.

The source explicitly defines episode states as `RECOVERED` and `UNRECOVERED`
and gives the precise active-state vocabulary `NO_ACTIVE_DRAWDOWN`,
`UNDERWATER`, and `RECOVERED`; those closed values are used directly. For tied
maximum recovered durations, where no single-winner rule is supplied, every
tied immutable episode identity is retained in chronological order rather than
selecting an arbitrary winner.

## #29.7.2.13 completed versus active underwater duration

The locked #29.7.2.13 definition explicitly separates completed historical
underwater durations from the currently active duration. The port therefore
uses only recovered #29.7.2.12 episodes for the duration distribution, total,
average, median, and maximum. An unresolved episode has `duration = NULL` and a
separate `current_duration` ending at the latest finalized observation carried
by the recovery snapshot—not wall-clock time and not a later `as_of_time` with
no new observation. It is never represented as infinity or mixed into a
completed denominator.

Although #29.7.2.10 does not define a general percentile contract, #29.7.2.13
itself explicitly locks median duration: chronological episode durations are
sorted numerically, an odd population selects the middle value, and an even
population uses the exact arithmetic mean of the two middle values. The port
implements only this locally explicit median rule and does not introduce a
general percentile API. The immutable starting-equity observation documented
for #29.7.2.12 is reused solely to emit the required initial non-underwater
state and its timestamp; no equity or peak is reconstructed.

## #29.7.2.14 grouping and threshold boundaries

The locked #29.7.2.14 definition says setup, instrument, timeframe, direction,
day, week, and month may be used for grouping, but supplies no period-timezone
input, boundary constructor, grouped-snapshot object, or cross-group formula.
It also defines no numeric path threshold. The port therefore emits the one
canonical chronological sequence for the explicitly isolated strategy/symbol/
timeframe/model/direction scope. It does not invent period groups, thresholds,
or a second time-boundary policy; downstream callers may request separate
scopes using already-canonical period facts when those owners are implemented.

Transition probability uses the explicitly locked source-state denominator:
only occurrences of the source result with a following finalized trade count.
The final trade never enters an outgoing denominator. Consequently every one
of the nine transition cells is `NULL` when its source has no outgoing
transition; no infinity is produced. Ordinary WIN/LOSS/BREAKEVEN runs are
#29.7.2.14 path facts, while maximum WIN/LOSS lengths and tied source groups are
copied from and compatibility-checked against immutable #29.7.2.8 facts rather
than replaced by locally selected maxima.

## #29.7.2.15 downstream-statistic references and strategy comparisons

The locked #29.7.2.15 ownership summary says a broad `StrategyPerformance`
object may reference cumulative/equity/drawdown/recovery/streak/distribution
facts, while its canonical dependency declaration and recorded dependency map
require only finalized #29.7.1 accounting and #29.7.2.9 period facts. The port
does not manufacture references to snapshots that were not supplied and does
not silently add dependencies beyond the owner-declared boundary. It emits the
strategy conservation, expectancy/profit-factor boundaries, explicit-starting-
equity path, and canonical period-return observations that are deterministically
defined from those declared inputs. Later aggregation may carry separately
supplied downstream references without changing these facts.

The source permits strategy comparison facts but explicitly forbids declaring
one strategy superior and supplies no comparison formula, ranking direction,
minimum history, or tie-break. No comparison/ranking record is therefore
invented. Each invocation remains isolated to one exact strategy, symbol,
timeframe, model, direction, period type, AccountTimezone, and version scope.
Missing period records remain absent; discontinuities between supplied periods
are preserved as gap identities and are never forward-filled. A supplied
zero-trade period remains a real zero-valued period-return observation.

## #29.7.2.16 period alignment, weighting, and merged-path boundary

The locked portfolio definition explicitly defers capital allocation and says
combined Gross/Net PnL and Gross/Net R are sums over included strategy
populations. It supplies no capital weights, equity weights, normalization
base, or rebalancing schedule. The port therefore applies no implicit weights:
each qualifying trade contributes exactly once through its immutable strategy
population, and all portfolio totals and strategy contributions conserve those
exact additive facts.

For portfolio period observations, the source locks missing ≠ zero, genuine
zero as a real observation, and identical AccountTimezone/half-open boundaries,
but does not authorize partial-population imputation. The port uses the
narrowest deterministic alignment: a portfolio-period observation exists only
at a `period_end` present for every effective included strategy and only when
all boundary/type/timezone facts agree exactly. Ends missing from any included
strategy are retained as `missing_period_ends`; they are not forward-filled or
converted to zero. Real aligned zero-return observations remain in the series.

The current #29.7.2.15 object exposes chronological per-trade NetPnL equity
points and aggregate result/PnL/R facts, but not per-trade result, NetR, or
GrossPnL observations. #29.7.2.16 can therefore build the canonically required
merged equity/drawdown path and additive portfolio statistics without summing
strategy drawdowns, but it cannot invent merged trade-result streak/recovery/
underwater records or per-trade R contribution rows from absent inputs. It
preserves strategy-level source trade/accounting identities and dimensional
facts in each contribution. Those additional merged path objects remain
unavailable until their exact per-trade facts are carried by the declared
#29.7.2.15 population boundary.

## #29.7.2.17 attribution weighting, ranking, and period boundary

The locked attribution owner defines exact strategy contribution conservation:
the signed strategy PnL contributions sum to portfolio NetPnL and the signed
strategy R contributions sum to portfolio NetR. It defines no percentage-share
formula, capital or equity weighting rule, denominator for zero or non-positive
portfolio results, ranking direction, or tie-break. The port therefore records
the exact immutable signed #29.7.2.16 contribution rows in effective-membership
order and proves zero conservation deltas; it does not invent shares, weights,
ranks, or a zero-denominator convention.

#29.7.2.16 exposes aggregate aligned portfolio-period observations and their
strategy-period source identities, but not a per-strategy contribution value
inside each portfolio-period fact. #29.7.2.17 consequently preserves those
period observations as immutable finalized lineage, including gaps and genuine
zero-return periods, without reconstructing period attribution from trades or
upstream strategy records. A future owner may consume richer period
contributions only when they are explicitly present at the declared boundary.

## #29.7.2.18 undefined aggregate denominators and exposure boundary

The locked overlap owner defines exact `[opened_time, closed_time)` trade-pair
intersections, unioned strategy-pair durations, point-in-time active-strategy
sets, maximum simultaneous strategy count, and simultaneous ActualRisk as the
sum of immutable upstream risk facts. It names average simultaneous strategy
count, total simultaneous risk, and non-overlapping periods but supplies no
observation horizon, time weighting, integration formula, denominator, or unit
for those aggregates. The port therefore emits exact event-segment observations
and their canonically defined maxima, but does not invent averages, risk-time
integrals, or non-overlap durations.

The #29.7.1 boundary contains quantity and economic prices but no canonical
instrument-specific notional formula or contract specification sufficient to
normalize exposure across instruments. In accordance with the explicit source
rule, simultaneous notional exposure is `NULL`, not estimated. Strategy,
symbol, timeframe, model, setup direction, position, trade, and accounting
identities remain descriptive immutable lineage; they do not partition or
prevent temporal overlap because the owner explicitly allows different symbols
and opposite directions to overlap. Source/input versions remain isolated.

## #29.7.2.19 covariance intermediate versus #29.7.2.20 ownership

The recovered correlation definition includes sample covariance, variances,
and standard deviations inside the locked `StrategyCorrelation` object because
they are the explicit intermediate components of Pearson correlation. The
frozen Amendment 001 numbering and current canonical notes assign standalone
strategy covariance records and matrices to #29.7.2.20. The #29.7.2.19 port
therefore preserves covariance and `(N-1)` variance components for auditability
inside each correlation record, but does not emit a `StrategyCovariance`, a
covariance matrix, or any #29.7.2.20 snapshot.

Pair records use the one deterministic lexical identity `strategy_a_id <
strategy_b_id`; symmetry is represented by that single canonical record rather
than duplicated `(A,B)` and `(B,A)` records. Symbol, timeframe, setup model,
direction, and upstream calculation identity are validated independently for
each strategy series. Only exact matching period boundaries, period type,
AccountTimezone, source version, calculation version, and historical version
are aligned. No numeric display rounding is applied: calculations use Decimal
precision above the canonical 28-significant-digit minimum.

## #29.7.2.20 pairwise-complete matrix population

The locked covariance algorithm says to repeat the pair calculation for every
strategy pair, aligns each pair on timestamps available to both strategies,
and permits each matrix cell to be `NULL` for insufficient paired history. It
does not impose a single listwise/common period intersection across the whole
universe. The port therefore uses pairwise-complete samples: each off-diagonal
cell uses that pair's exact period intersection, while each diagonal aligns the
strategy with itself and is its sample variance over its own eligible series.
This preserves missing ≠ zero and allows different cells to carry different
observation counts without making the matrix structurally incomplete.

Matrix completeness is structural, not numeric: an `N`-member immutable,
lexically ordered universe has `N(N+1)/2` canonical covariance records and
`N²` row-major cells. Both symmetric cells reference the same lexical pair
record; every diagonal is present; an insufficient cell is present with
`covariance = NULL`. Empty and single-member universes follow the same formula.
`FULL_HISTORY` and `EXPANDING` consume all point-in-time eligible observations;
`ROLLING` requires an explicit window of at least two and selects the most
recent aligned observations independently for each pair. No mode or window is
selected implicitly.

## Interface audit: #29.4 open-position boundary dependency

The implemented #29.4 `OpenPositionBoundary` is the explicit fail-closed
position-availability adapter required before #29.6 creates the canonical
position lifecycle. It previously imported #29.6's `PositionState` solely to
compare against `OPEN`, which reversed the canonical dependency direction
(`#29.4 -> #29.6`) and made the adapter depend on its later consumer. The
single `PositionState` definition now lives in the neutral serialized boundary
module and is re-exported by both #29.4 and owner #29.6. #29.4 therefore no
longer imports the later lifecycle module, while existing callers importing
`PositionState.OPEN` from either numbered module retain object identity and
compatibility. #29.6 remains the sole transition owner; the neutral enum has no
engine or transition behavior.

## Phase 7B prerequisite 1 — accepted #20 ingestion boundary

Owner authorization accepted the four narrow fail-closed decisions on
2026-08-22. Implemented decision identities:

- `P7B-P1-D1-INCOMPLETE-BASELINE-PENDING`: retain a one-sided swing only in
  immutable pending history and emit no classification-ready snapshot.
- `P7B-P1-D2-EXPLICIT-AVAILABILITY`: preserve pivot occurrence separately from
  an explicit UTC-aware availability boundary; unproven replay availability
  fails closed.
- `P7B-P1-D3-LINEAGE-ENVELOPE`: carry symbol, timeframe, source version, and
  calculation version in the immutable #19 → #20 availability fact while
  preserving the source swing identity.
- `P7B-P1-D4-APPEND-ONLY-LEDGER`: retain availability, pending, superseded,
  finalized, historical, and snapshot lineage in an immutable #20-owned ledger.

| Missing rule | Canonical passages inspected | Available interpretations | Consequences | Narrowest fail-closed recommendation |
|---|---|---|---|---|
| Observable state before the first opposite swing completes the initial baseline | `#20 Structural Classification` Initialization; Amendment 006 Parts III, VII, VIII–X; recovered transcript steps 1–9 and alternating-leg definition | (A) publish a snapshot with the first swing installed as one governing side; (B) publish no snapshot and retain the swing in separate pending history; (C) discard until both sides exist | A exposes an unfinalized leg candidate as governing structure; B adds an infrastructure-only immutable ledger without trading eligibility; C loses accepted source history | **Accepted B (`P7B-P1-D1`)**. |
| Canonical event chronology for a confirmed #19 swing | `#19 Mechanical Swing Selection` Inputs/Outputs and two-right-bar invariant; Amendment 006 Part II; Interface Contract market-data chronology | (A) order ingestion by `pivot_time`; (B) add caller-supplied observation/confirmation time; (C) change #19 to emit confirmation time | A can expose a pivot before its two right bars close and cannot distinguish late/replayed observation; B preserves existing #19 records through an additive handoff fact; C changes the frozen #19 constructor | **Accepted B (`P7B-P1-D2`)**. |
| Symbol and version compatibility for #19 → #20 ingestion | Canonical Object Registry (`MechanicalSwing`, `StructuralSwing`); Identity/Versioning Policy; current #19/#20 schemas; Interface Contract identity rules | (A) add symbol/source/calculation versions to existing records; (B) introduce a versioned ingestion envelope; (C) trust caller context without preserving it in output | A changes frozen record constructors; B is additive and preserves source identity; C cannot prove lineage or reject mismatches | **Accepted B (`P7B-P1-D3`)**. |
| Historical preservation for superseded same-leg candidates and demoted governing/protected swings | `#20 Structural Classification` survival rule; Amendment 006 Parts IV, VII, VIII–X; recovered transcript alternating-leg and demotion rules | (A) store complete immutable structural/pending history in a new aggregate; (B) retain only lineage IDs in snapshots; (C) rely on an external event store | A provides deterministic replay/audit lineage without adding a trading status; B cannot preserve all requested identities; C leaves the public boundary incomplete | **Accepted A (`P7B-P1-D4`)**. |

Rules that *are* explicit and therefore need no decision are: first opposite
high/low pair forms an unclassified INITIALIZING baseline; external structural
swings alternate; the most extreme same-type candidate survives an incomplete
leg with chronological-first identity on an exact tie; classification compares
against the prior finalized same-type swing; bullish HL and bearish LH are only
candidate protection; and only accepted #16 BOS/MSS decisions may transfer or
terminate protection/regime. These rules are insufficient to define the new
public operation's complete input/output and lineage contract without the four
accepted owner decisions above. Those decisions are now implemented by
`StructuralStateProducer.ingest` and `StructuralIngestionLedger`.

## Phase 7B prerequisite 2 — accepted OWNER_MECHANICAL_V1 displacement

Owner authorization on 2026-08-22 approved the explicit extension policy
`OWNER_MECHANICAL_V1`. These numerical choices are owner-authored because the
canonical source leaves displacement pending validation; they are not quoted or
represented as original canonical rules. Implemented decision identities:

- `P7B-P2-D1-OWNER-MECHANICAL-V1`: fixed 20-candle, median-body expansion and
  body/range policy with exact thresholds and one-tick structural clearance.
- `P7B-P2-D2-SINGLE-EVALUATION-CANDLE`: the structural-break candle is the
  complete displacement evaluation; no discretionary multi-candle leg.
- `P7B-P2-D3-CLOSED-OUTCOMES`: immutable qualified/not-qualified/insufficient/
  invalid/upstream-invalid results preserve unavailable separately from false.
- `P7B-P2-D4-CLOSE-AVAILABILITY`: occurrence and availability are the closed
  evaluation candle's UTC close; later candles never revise the result.
- `P7B-P2-D5-APPEND-ONLY-INVALIDATION`: upstream invalidation appends an inactive
  historical record and preserves the original qualification.

| Exact missing rule | Canonical passages inspected | Available interpretations | Consequences | Narrowest fail-closed recommendation |
|---|---|---|---|---|
| Displacement method and numerical threshold | Runtime Configuration Registry (`DISPLACEMENT_THRESHOLD`, `DISPLACEMENT_METHOD`: configurable / pending validation); Implementation Readiness; recovered readiness table | Multiple previously possible methods | Owner selected a new explicit extension rather than attributing a rule to canonical source | **Accepted `OWNER_MECHANICAL_V1` (`P7B-P2-D1`)**: 20 references, expansion `>=1.5`, body/range `>=0.60`, one tick. |
| Displacement leg construction and initiating/reference/comparison candle selection | #16 §11; §39; Amendment 006 Part V; recovered “current move”/“leg” references | Several possible leg definitions | Multi-candle choices would remain discretionary | **Accepted single structural-break evaluation candle (`P7B-P2-D2`)**, compared with exactly 20 prior contiguous candles. |
| Direction, candle geometry, wick/body/open/close basis, and equality | #16 §§9–12; #11 §§13–14; recovered #25 references; tests/invariants | Several possible geometries | Each produces different events | **Accepted (`P7B-P2-D1`)**: `abs(close-open)`, `high-low`, close direction, inclusive numeric thresholds, and inclusive one-tick clearance. |
| Confirmation/availability, multi-candle chronology, gaps, and invalidation lifecycle | #16 chronology; Amendment 006 Part II; global integrity/no-look-ahead | Several completion/invalidation models | Provisional models permit retroactive change | **Accepted (`P7B-P2-D4/D5`)**: available at evaluation close, 20 contiguous references required, no future invalidation rule, upstream invalidation only and append-only. |
| Canonical outcome/error model and uniqueness key | Object/enum/error registries and fail-closed policy | Boolean or closed result | Boolean collapses unavailable into false | **Accepted (`P7B-P2-D3`)**: five closed outcomes and deterministic dataset/run/context/candle/policy/version evaluation key; conflicting reuse fails closed. |

Rules that are explicit but insufficient are: displacement is independent from
sweep, FVG, CISD, BOS, and MSS; a structural break requires both its own strict
body close and qualifying displacement; the associated displacement leg must
contain the structural confirmation candle; independent events may share one
closed candle; and no intrabar order may be invented. These constraints do not
define displacement qualification itself.

## Phase 7B prerequisite 3 — accepted #23 structural-reference derivation

Owner authorization on 2026-08-22 accepted the five narrow fail-closed
recommendations. Implemented decision identities:

- `P7B-P3-D1-SINGLE-STRUCTURAL-PROVENANCE`: one reference per eligible source
  swing and compatible scope; preserve #19 identity but derive eligibility only
  from the accepted #20 state/event.
- `P7B-P3-D2-ACTIVE-BOUNDARIES-ONLY`: only active confirmed governing/protected
  boundaries qualify; every other structural lifecycle position is excluded.
- `P7B-P3-D3-EXACT-RANGE-MAJOR`: create a reference only when identity and price
  exactly form the corresponding active #21 boundary, then mark it major.
- `P7B-P3-D4-APPEND-ONLY-TERMINALITY`: replacement historicizes, confirmed #23
  sweep consumption consumes, and historical/consumed identities never revive.
- `P7B-P3-D5-VERSIONED-REFERENCE-LEDGER`: deterministic identity includes source
  swing, state/event, range, symbol, timeframe, side, and versions; history is
  immutable and external/session registration remains unavailable.

| Exact missing rule | Canonical passages inspected | Available interpretations | Consequences | Narrowest fail-closed recommendation |
|---|---|---|---|---|
| Mechanical-versus-structural source identity when one #20 structural swing preserves the same #19 swing | #19 final definition; #20 source identity/survival; #23 §4 and Final Locked Definition; existing `LiquidityReference.source_type` | Separate duplicates, mutable upgrade, structural-only, or one identity with provenance | Duplicate/upgrade alternatives corrupt pool identity or immutable history | **Accepted one structural reference preserving #19 source lineage (`P7B-P3-D1`)**. |
| Exact structural eligibility | #20 Amendment 006 Parts IV/VII/VIII–X; #23 §§20–24; #24 §6 | All confirmed, finalized, governing/protected, or status-as-priority | Each changes active liquidity population | **Accepted active confirmed governing/protected only (`P7B-P3-D2`)**. |
| “Major structural extreme” designation and range-boundary equality | #23 Internal/External §§22–25; #24 §§7–8 | Governing, protected, exact range boundary, or registered-only | Major changes external priority | **Accepted exact active #21 identity-and-price boundary (`P7B-P3-D3`)**. |
| Reference lifecycle and supersession | #23 State/Lifecycle §§29–32; #21 range transitions; #24 filters | Permanently active, pool-consumed, supersession-historical, or independent lifecycle | Permanent components can recreate consumed pools | **Accepted replacement historicization plus confirmed #23 consumption (`P7B-P3-D4`)**. |
| Producer uniqueness and external/session boundary | #23 object/registries; identity policy; #19/#20 availability | Source ID, price key, registration ID, or separate schemas | Price collapses genuine equal-price sources; external availability is undefined | **Accepted full versioned identity and append-only ledger; external/session unavailable (`P7B-P3-D5`)**. |

The implementation retains the explicit canonical H→BSL/L→LSL, occurrence
versus availability, one-reference-versus-pool, component preservation, #23
sweep ownership, and #24 selection boundaries. The accepted decisions add no
external/session registration, delivery-leg, CISD, setup, or execution rule.

## Phase 7B prerequisite 4 — accepted Reversal #1 delivery formation

Owner authorization on 2026-08-22 accepted all six narrow fail-closed
recommendations as an additive mechanical formation boundary. Implemented
decision identities:

- `P7B-P4-D1-BODY-DIRECTION-CONTIGUOUS`: expected direction comes from the
  accepted reversal sequence; strict body direction segments a maximal,
  contiguous 1M run and a doji terminates it.
- `P7B-P4-D2-CAUSALLY-ADJACENT-RUN`: only the unique opposing run immediately
  adjacent to the intended-direction MSS candle qualifies; no older fallback.
- `P7B-P4-D3-FROZEN-SAME-CANDLE`: same-candle sweep/MSS/CISD may use only a
  complete reference frozen before the shared candle.
- `P7B-P4-D4-GAPS-NOT-CONFIRMABLE`: missing required 1M history or boundaries
  fail closed; no shortening, bridging, synthesis, or forward fill.
- `P7B-P4-D5-GENUINE-UPSTREAM-ENVELOPE`: require exact reversal LRL, consuming
  sweep, accepted 1M MSS, qualified displacement, state, and full lineage.
- `P7B-P4-D6-VERSIONED-APPEND-ONLY-LEDGER`: deterministic candle/upstream
  identity, latest-fact availability, terminal invalidation, and idempotency.

| Exact missing rule | Canonical passages inspected | Available interpretations | Consequences | Narrowest fail-closed recommendation |
|---|---|---|---|---|
| Mechanical delivery direction and contiguous-leg segmentation | #11 §§4–6, 37–42 and Final Locked Definition; Appendix A (`most recent contiguous delivery leg`, `first candle`, `doji terminates delivery`); Golden #11 scenarios | Body direction, close-to-close, displacement/structure, or registered leg | Alternatives select different starts | **Accepted strict body direction and maximal gap-free same-direction run (`P7B-P4-D1`)**; intended/opposing direction is fixed by the accepted reversal sequence. |
| Causal window and exact leg start/end relative to sweep and MSS | #11 §§5–6, 16–21, 41–45; Amendment 005A §1; #16 §§9–13; Golden #11 scenarios | Sweep-containing, adjacent-to-reversal, pre-MSS, or arbitrary-history run | Each changes causal association | **Accepted unique maximal opposing run directly adjacent to the accepted intended-direction MSS candle (`P7B-P4-D2`)**; otherwise unavailable, never older fallback. |
| Same-candle sweep/MSS/CISD and frozen reference sequencing | #11 §§18–21 and 41–45; #16 §§2, 7, 9–10, 17; Appendix A same-candle/no-intrabar-order passages | Pre-open frozen leg, close-created leg, or inferred intrabar transition | Later choices create retroactive reference | **Accepted pre-event frozen reference only (`P7B-P4-D3`)**. |
| Missing 1M intervals and dataset boundaries | #11 completed-candle/no-look-ahead rules; #16 data integrity; Hard Invariants I22/I24 | Restart, fail closed, bridge, or forward-fill | Restart may falsely claim adjacency; bridge/fill fabricates | **Accepted insufficient/not-confirmable with no shortening or bridge (`P7B-P4-D4`)**. |
| Genuine sweep/LRL/MSS identity handoff and timeframe compatibility | #11 §§16–25/40–45; Amendment 005A §1; #16/#23/#24 objects | Caller IDs, direct facts, or association envelope | Caller IDs cannot prove canonical acceptance/lineage | **Accepted immutable genuine-fact envelope and 1M formation/MSS boundary (`P7B-P4-D5`)**; higher-timeframe context cannot replace missing 1M facts. |
| Producer identity, availability, invalidation, and append-only history | #11 §§23, 33–39; Identity/Versioning Policy; registries; current schemas | Mutable rebuild, freeze only, append ledger, or external state | Mutation/reselection violates replay history | **Accepted versioned immutable ledger and terminal invalidation (`P7B-P4-D6`)**. |

Rules that are explicit and require no decision remain enforced by existing
`CISDEngine`: Amendment 005A sweep-side mapping; `SweepTime <= MSSTime`;
strict bullish `close > bearish-open` / bearish `close < bullish-open`; equality
and wick-only rejection; no older fallback after an invalid selected reference;
pre-sweep/pre-MSS ineligibility; same-candle confirmation only from frozen
pre-state; immutable accepted confirmation; and no #25/#27/#28/#13/execution
ownership. The accepted additive producer supplies only the raw-candle leg and
sequence handoff; it does not change those canonical #11 rules.

## Phase 7B completion — unresolved liquidity-population boundary

The requested autonomous canonical file runner cannot currently reach #24.
This is a contract-level blocker, not a missing orchestration convenience:

- canonical #23 requires **two or more same-side references** for a pool and
  explicitly keeps a single reference outside `LiquidityPool`;
- canonical #24 selects an LRL from `LiquidityPool` records only;
- accepted decision `P7B-P3-D2` permits only the current governing/protected
  boundaries, yielding exactly one active BSL and one active LSL;
- accepted decision `P7B-P3-D4` historicizes replaced structural references,
  so prior same-side facts cannot accumulate into a new active pool;
- `P7B-P3-D5` explicitly deferred external/session/prior-period registration;
- canonical-mode configuration now explicitly forbids injected references,
  pools, LRLs, sweeps, and other prebuilt strategy facts.

Consequently, genuine file data passed through the frozen public producers can
produce only `LiquidityInventory.single_references`, never a pool. #24 returns
no LRL, #23 can confirm no pool sweep, and neither continuation nor Reversal #1
can reach #27. A claimed meaningful trade example would require fabricating an
intermediate or changing a previously frozen owner rule.

| Missing authority | Canonical/current passages | Available interpretations | Consequences | Narrowest compatible recommendation |
|---|---|---|---|---|
| Source of the second same-side active reference needed by #23/#24 | #23 Canonical Definition/Hard Invariants; #24 Canonical Definition; `P7B-P3-D1`–`D5`; `LiquidityPoolEngine.build_inventory`; `LRLSelectionEngine.select` | (A) implement the separately deferred explicit external/session/prior-period registration contract; (B) keep superseded structural references active; (C) allow #24 to select single references; (D) inject prebuilt references in configuration | A preserves #23 pool cardinality and #24 input ownership; B contradicts terminal replacement/history decisions; C contradicts #24's pool-only locked definition and changes LRL population; D violates the Phase 7B request and replay provenance | **Recommend A:** authorize a new additive, replay-safe external/session/prior-period reference producer with exact source families, calendar/session boundaries, availability, identity/version lineage, lifecycle, and gap rules. Until then `CANONICAL_TRADING_BRAIN` must fail validation as dependency-incomplete rather than pretend to be meaningful. |

No choice was inferred. In particular, the implementation must not duplicate
one structural swing, combine opposite sides, reactivate historical references,
promote a singleton to a pool, or hide a prebuilt liquidity fact in the CLI.

### Accepted resolution: `OWNER_PRIOR_PERIOD_V1`

Owner authorization on 2026-08-22 selected interpretation A as decision
`P7B-P5-D1-OWNER-PRIOR-PERIOD-V1`. The additive policy registers only PDH/PDL
and ISO-week PWH/PWL from complete contiguous published 1M periods in the run's
IANA `AccountTimezone`. It preserves calendar/DST boundaries, exact Decimal
extrema, every tied candle identity, completed-period availability, full
lineage, and explicit owner-authored provenance.

Decision `P7B-P5-D2-APPEND-ONLY-PRIOR-PERIOD-LIFECYCLE` fixes immutable
registration/evaluation/transition history. Confirmed #23 consumption is
terminal; touches do nothing; an explicit chronological upstream invalidation
may retire a reference without deleting it; later periods always receive new
identities.

This resolves the missing second-reference source without weakening #23's 2+
same-side pool rule or #24's pool-only contract. It does not authorize manual,
session, opening-range, prior-month, order-book, or user-entered references.
The policy remains subject to later sensitivity and out-of-sample validation.

# Backtesting Phase 5A equity policy

Canonical #29.7.1 fixes `pre_trade_equity` to the immutable #29.2
`pre_fill_equity` and fixes `post_trade_equity = pre_trade_equity + net_pnl`.
It does not define a separate fixed-initial-equity portfolio ledger or a mode
that breaks the predecessor relationship between finalized trades. Phase 5A
therefore exposes only the narrow deterministic `COMPOUNDED` policy: after a
TradeResult is committed, its post-trade equity becomes the next eligible
trade's sizing equity. The initial run-manifest equity remains the source for
the first trade and for a zero-trade run. No fixed-equity mode is invented.
# Phase 7B canonical CLI completion

With `P7B-P5-D1` and `P7B-P5-D2` implemented, no further owner interpretation
was required. The canonical runner advances 1M structural ownership so the
owner-authored 1M prior-period facts can be handed unchanged to existing #23;
the engine itself decides pool formation. Accepted 5M BOS facts alone create
continuation requests. No prebuilt intermediate fact, forced pool, synthetic
setup state, or analytics feedback was authorized.

# Owner minimum-R and performance-readiness policies

Decision `OWNER-RR-D1-OWNER-MIN-RR-V1` adds immutable `OWNER_MIN_RR_V1`.
Its global floor and both current model values are exact Decimal `1.0`; future
models fail closed without an explicit value. Original `CANONICAL_MIN_RR_V1`
exact 2R values and legacy identity remain the default when policy is omitted.
Explicit owner-policy identities enter qualifications and backtest manifests.
#28 entry, #13 stop, and #24 target ownership is unchanged.

Decision `OWNER-PERF-D1-WIN-RATE-OBJECTIVE-V1` adds advisory
`OWNER_WIN_RATE_OBJECTIVE_V1`. It consumes finalized count and net-expectancy
analytics; requires 200 out-of-sample trades, win rate at least 0.60, and
positive net expectancy; and isolates BTC, ES, and NQ. Combined evaluation is
unavailable until a compatible explicit universe exists. `OBJECTIVE_MET` means
eligible for owner review, never live authorization. No profitability claim is
made.
