# Appendix A — Recovered Historical Transcript

**STATUS: IMMUTABLE HISTORICAL SOURCE**

This document preserves the recovered historical wording verbatim. It does NOT automatically govern implementation. For canonical implementation precedence, see [[Trading Brain — Source Precedence]].

## Integrity Rules
- Historical source is immutable; not rewritten to match amendments.
- Contradictions are preserved, not deleted.
- Amendments 001-005A are NOT applied inside this transcript.
- Source artifact, not the canonical implementation layer.

## Provenance
Verbatim copy of the authoritative source file `Trading_Brain_Master_Implementation_Specification.md` (contains the §00-06 operating contract and the Appendix A recovered transcript). Companion source: `Trading_Brain_Master_Source_of_Truth.md` (recovered-core spec + declared GAP markers incl. `defif.docx`). The external originals remain unmodified.

## Known Superseded Historical Wording (preserved verbatim below, non-governing)
| Historical wording | Superseded by | Canonical behavior |
|---|---|---|
| #29.7.2.14 duplicate exclude-and-continue | Amendment 001 C2 | fail-closed DATA_INTEGRITY_ERROR |
| #29.7.2.17 duplicate retain-canonical-and-continue | Amendment 001 C2 | fail-closed DATA_INTEGRITY_ERROR |
| #29.7.2.15 internal numbering recap | Amendment 001 C1 | canonical .9-.20 registry |
| Reversal-LRL bearish->BSL / bullish->LSL | Amendment 005A | bearish->LSL / bullish->BSL |
| IF Setup.state != ARMED: #28 does nothing | Amendment 005A | #27 -> #28 -> #27 revalidation -> arm |

---

# ===== BEGIN VERBATIM RECOVERED SOURCE (IMMUTABLE) =====

# Trading Brain - Master Implementation Specification

**Source-complete normalization:** 2026-08-17  
**Canonical input:** `trading information script.docx` (4,309 source paragraphs and 4 source tables)  
**Implementation status:** Audit required before code; no trading-engine code is authorized by this document.

`START`

## 00 - Authority and implementation instructions

This is the single document Claude Code must ingest for the Trading Brain. It contains a canonical operating contract, an implementation-readiness audit, and the complete recovered source transcript. The transcript is included so no detail from the recovered Word file is silently lost during normalization.

Claude Code must:

1. Read this whole document from `START` to `END` before modifying code.
2. Treat text marked **LOCKED** or **Final Locked Definition** in the recovered transcript as source rules, subject to the conflict list below.
3. Treat planning language, alternatives, recommendations, questions, and superseded numbering in the transcript as non-authoritative unless a later final/locked definition explicitly resolves them.
4. Preserve the ownership boundaries: downstream analytics consume finalized upstream records and do not mutate, reinterpret, or rebuild them.
5. Stop for the project owner when a requirement is **UNRESOLVED**, **PENDING VALIDATION**, or internally contradictory. Do not invent a rule, threshold, schema, or default.
6. Build and test in dependency order only after the audit is accepted.

## 01 - Source completeness statement

The previous master was an incomplete recovery manifest. This edition embeds the full recovered Word-document text, including strategy rules, execution architecture, accounting, analytics, data-model discussion, enums, error-system discussion, invariants, tests, and #29.7.2.1-.20 material. No source paragraph or table is omitted from the transcript appendix.

The document is source-complete, but it is not automatically implementation-ready: the recovered source itself contains provisional language and conflicts that must remain explicit.

## 02 - Canonical architecture map - LOCKED

```text
Market data
  -> timeframe structure (primary hierarchy: 1H -> 15M -> 5M -> 1M)
  -> mechanical swing detection and structural classification
  -> HTF bias, order flow, protected swing, LRL identification/approach,
     liquidity sweep, delivery/CISD, displacement, MSS/BOS, FVG/IFVG, OTE
  -> setup qualification and entry-zone selection
  -> entry execution -> sizing -> protective orders -> exit resolution
  -> execution costs -> position lifecycle -> trade/account accounting
  -> performance primitives -> strategy aggregation -> portfolio aggregation
  -> attribution -> overlap -> correlation -> covariance
```

Primary intended markets are S&P 500 (ES/SPX) and Nasdaq (NQ/QQQ), while the engine architecture remains instrument-agnostic. Displacement is **CONFIGURABLE** and its numerical threshold/method is **PENDING VALIDATION**; the engine must never invent one.

## 03 - Locked cross-cutting rules

- Analytics are read-only and accept finalized upstream history only.
- No look-ahead: point-in-time calculations use only information finalized and eligible at that point.
- Historical observations/snapshots are immutable; later facts create later observations rather than rewriting history.
- `NULL` means unavailable, undefined, insufficient, or invalid; a mathematically valid `0` remains `0`.
- Missing does not mean zero unless an upstream finalized specification explicitly produces an actual zero observation.
- Cost anti-double-counting is mandatory: price-based friction already embedded in economic entry/exit prices cannot also be subtracted as explicit cash cost.
- Attribution is not optimization; temporal overlap is not return correlation; correlation/covariance are descriptive and not allocation/risk decisions.

## 04 - Canonical known formulas and boundaries

### 04.1 Trade accounting - #29.7.1 - LOCKED

```text
DirectionMultiplier: long = +1; short = -1
GrossPnL = (EconomicExitPrice - EconomicEntryPrice)
           * DirectionMultiplier * Quantity * ContractMultiplier
NetPnL = GrossPnL - ExplicitCashCosts
GrossR = GrossPnL / InitialRiskDollars
NetR = NetPnL / InitialRiskDollars
PostTradeEquity = PreTradeEquity + NetPnL
```

`InitialRiskDollars` comes from #29.2 and must be positive; non-positive risk is `ACCOUNTING_ERROR`, never infinity/NaN/zero R. Classification is based on `NetPnL`: positive WIN, negative LOSS, exact zero BREAKEVEN. Accounting never changes upstream entry, exit, quantity, stop, target, lifecycle, or costs.

### 04.2 Attribution - #29.7.2.17 - LOCKED

```text
sum StrategyNetPnL = PortfolioNetPnL
sum StrategyGrossPnL = PortfolioGrossPnL
sum StrategyNetR = PortfolioNetR
sum StrategyExplicitCashCosts = PortfolioExplicitCashCosts
StrategyNetPnL = StrategyGrossPnL - StrategyExplicitCashCosts
```

Each finalized portfolio trade maps to exactly one valid attribution strategy. A zero portfolio denominator produces `NULL` contribution percentage, not zero. A missing strategy identity is `ATTRIBUTION_INVALID`, never guessed.

### 04.3 Overlap - #29.7.2.18 - LOCKED

```text
position interval = [opened_time, closed_time)
overlap iff A.opened_time < B.closed_time and B.opened_time < A.closed_time
overlap_duration = min(A.closed_time, B.closed_time) - max(A.opened_time, B.opened_time)
```

A close/open timestamp touch is not overlap. Same-strategy positions are not inter-strategy overlap. Pair duration is the union of valid overlapping intervals, not a naÃ¯ve sum.

### 04.4 Correlation and covariance - #29.7.2.19-.20 - LOCKED SUBJECT TO INPUT-SCHEMA RESOLUTION

```text
Cov(A,B) = sum((RA,t - MeanA) * (RB,t - MeanB)) / (N - 1), N >= 2
rho(A,B) = Cov(A,B) / (StdA * StdB)
```

Paired observations only; pair-specific means; sample denominator `N-1`; covariance/correlation symmetry; covariance diagonal equals variance. Missing observations are excluded. Covariance of a constant series is valid zero; correlation of a constant series is `NULL` with `UNDEFINED_CONSTANT_SERIES`.

## 05 - Implementation-readiness audit

### LOCKED

- The detailed recovered source is preserved in Appendix A.
- The execution/accounting boundary and #29.7.1 P&L/R/equity formulas are present.
- The .17-.20 analytics contracts, including no-look-ahead and `NULL` versus zero principles, are present.
- Strategy terms, entry architecture, risk/execution boundaries, error ideas, data-model and test discussions are present in the transcript.

### CONFIGURABLE

- Displacement numerical threshold and method.
- Covariance mode: `FULL_HISTORY`, `EXPANDING`, or `ROLLING`; rolling requires an explicit size.
- Any parameter explicitly labelled configurable in Appendix A must remain configuration, not hard-coded logic.

### PENDING VALIDATION

- Displacement threshold/method.
- Any parameter the source labels `PENDING VALIDATION`; it cannot receive an assumed default merely to make a backtest run.

### UNRESOLVED - required owner decisions before implementation

1. **Numbering reconciliation.** The transcript contains inconsistent .1-.10 numbering descriptions. Freeze one identifier-to-primitive registry before interfaces/files are named.
2. **Duplicate-data policy.** .16/.17/.20 references are inconsistent. Define one global policy for duplicate `trade_id`, strategy-period, and strategy-timestamp records; canonical record selection; error status; exclusion; and snapshot effect.
3. **StrategyReturnObservation.** .19 uses periodic `{strategy_id, period_start, period_end, net_pnl, net_r, finalized}` while .20 uses `{strategy_id, timestamp, return_value}`. Decide whether these are distinct objects or define one canonical schema and define `return_value` relative to `net_r`.
4. **Period/time policy.** Define timezone, session calendar, daily/weekly/monthly boundary, period ID, week start, and no-trade-period representation.
5. **Global identity/versioning policy.** Define ID formats/uniqueness, correction lineage, `source_version`, `historical_version`, and immutable snapshot semantics.
6. **Precision/rounding policy.** Define stored precision, computation precision, equality tolerances, and display rounding. Never calculate from rounded display values.
7. **Source finality.** Where Appendix A presents an alternative or recommendation rather than an explicit final/locked definition, the owner must select or supply a final rule.

## 06 - Required implementation order

1. Resolve Section 05 and record each resolution as a versioned amendment.
2. Implement shared types: IDs, timestamps, statuses/errors, decimal precision, nullability, versions, and immutable snapshots.
3. Implement the market/strategy state machines only from final locked source rules.
4. Implement #29.1-.6 execution/lifecycle, then #29.7.1 accounting and its tests.
5. Implement performance primitives, strategy aggregation, portfolio aggregation, then .17-.20 read-only analytics.
6. Prove invariants with unit, golden, property, integrity, and no-look-ahead tests before any live integration.
7. Do not implement live order placement, optimization, allocation, or discretionary interpretation unless separately authorized.

## Appendix A - Complete recovered source transcript

**Preservation rule:** Every non-empty paragraph and all four tables from `trading information script.docx` follow. They are ordered exactly as recovered. This preserves the full source while the sections above identify the current authoritative operating contract and unresolved decisions.

are we done and ready to upload to claude code?

Not quite. We are very close, but I would not upload this to Claude Code as the final trading-engine specification yet.

The definitions we've locked are strong enough to form the core rulebook, but there are still a few mechanical dependencies that must be finalized before Claude Code can implement the system without making assumptions.

What is already locked

We have finalized:

#### MSS

#### BOS

#### FVG

#### IFVG

#### OTE

OTE swing selection

Universal Qualifying Displacement

HTF Bias

Order Flow Respect/Disrespect

Approaching LRL

LRL Target Selection

#### CISD

Relevant Delivery Candle

That is a substantial portion of the engine.

What is still NOT fully locked

These are the important remaining pieces:

The biggest one: displacement

We deliberately said:

Numerical threshold = UNDEFINED / PENDING VALIDATION

That's perfectly acceptable for the research/specification phase.

But Claude Code needs to know what to do when it encounters displacement.

So we have two choices:

A. Build the engine with displacement as a configurable parameter

This is what I recommend.

For example:

DISPLACEMENT_THRESHOLD = CONFIGURABLE

DISPLACEMENT_METHOD = PENDING_VALIDATION

Claude can then build the architecture without us pretending that we've already statistically validated the threshold.

B. Freeze a numerical threshold now

I do not recommend doing that yet.

More importantly: we need to finish the architecture

Right now we have been defining individual components.

The next step should be to turn them into a single deterministic specification:

#### MARKET DATA

â†“

#### TIMEFRAME STRUCTURE

â†“

#### SWING DETECTION

â†“

#### STRUCTURAL CLASSIFICATION

â†“

#### HTF BIAS

â†“

#### ORDER FLOW

â†“

#### PROTECTED SWING

â†“

#### LRL IDENTIFICATION

â†“

#### LRL APPROACH

â†“

#### LIQUIDITY SWEEP

â†“

#### DELIVERY / CISD

â†“

#### DISPLACEMENT

â†“

#### MSS / BOS

â†“

#### FVG / IFVG

â†“

#### OTE

â†“

#### SETUP QUALIFICATION

â†“

#### ENTRY TRIGGER

â†“

SL

â†“

#### LRL TP

â†“

R:R â‰¥ 2.0

â†“

#### TRADE

And then we need a priority/state system so Claude never has to guess what happens when two conditions conflict.

My recommendation

Don't upload to Claude Code yet.

We should finish the remaining definitions first, then I'll consolidate everything into a single Trading Brain Master Specification designed specifically for Claude Code.

That document should contain:

exact definitions

formulas

state machines

decision trees

required inputs

outputs

timeframe hierarchy

setup rules

entry rules

invalidation rules

no-trade rules

configurable parameters

pending-validation parameters

pseudocode

terminology dictionary

conflict-resolution hierarchy

Then we can tell Claude Code:

Implement exactly this specification. Do not infer, reinterpret, loosen, or add discretionary rules. Any undefined parameter must remain configurable or be flagged as UNDEFINED rather than assumed.

That is the point where I would say: yes, upload it to Claude Code.

And I think we're at the point where we should finish the remaining definitions systematically rather than jumping into coding prematurely.

lets continue then I also agree with you onÂ Â A. Build the engine with displacement as a configurable parameter. also this trade strategy we are using works best on the SNP 500 as well as the Nasdaq.

Yes. We should continue without coding yet.

And I agree with your decision on displacement:

Displacement will be a configurable engine parameter, not a permanently hard-coded numerical threshold.

We should also record S&P 500 and Nasdaq as the primary markets for which the strategy is optimized, while keeping the engine architecture instrument-agnostic so we can later test other markets without rewriting the logic.

Locked additions

Primary instruments

S&P 500 â€” preferably ES/SPX, depending on the data/execution layer

Nasdaq â€” preferably NQ/QQQ, depending on the data/execution layer

Primary timeframe hierarchy

1H â†’ 15M â†’ 5M â†’ 1M

Displacement architecture

Qualifying Displacement

â†“

Universal Rule

â†“

Direction

Body dominance

Relative expansion

Structural consequence

â†“

Numerical threshold

â†“

#### CONFIGURABLE PARAMETER

â†“

#### PENDING VALIDATION

The engine should never invent a displacement threshold.

What I suggest we define next

We should proceed in this order because each definition depends on the previous one:

#7 â€” Mechanical Swing Selection

This is the biggest remaining foundation.

We need to define exactly:

What constitutes a swing high?

What constitutes a swing low?

How many candles confirm it?

When does confirmation occur?

Can a confirmed swing be replaced?

What makes a swing structural?

How do we identify HH, HL, LH, LL?

Which swing becomes protected?

How do we handle equal highs/lows?

How do we handle nested swings?

How do we handle multiple valid swings?

What happens in real time before confirmation?

This is critical because HTF Bias, BOS, MSS, OTE, LRLs and protected order flow all depend on swing selection.

Then:

#8 â€” Exact Mechanical Equilibrium

We already have the OTE relationship:

50% = Equilibrium

But we should define exactly what equilibrium means operationally and when the engine is allowed to use it.

#9 â€” Exact Mechanical LRL Identification

We've defined how to approach an LRL and how to select an LRL target.

We still need to define exactly:

What makes a price level an LRL in the first place?

That needs to cover:

structural highs/lows

equal highs/lows

previous day high/low

session high/low

HTF highs/lows

internal vs external liquidity

clustering

already-swept levels

level creation timing

#10 â€” Exact Mechanical Liquidity Sweep

Then:

LRL â†’ Approach â†’ Reach â†’ Sweep

We need to distinguish mechanically between:

touch

sweep

breakout

rejection

acceptance

#11 â€” Exact Mechanical Rejection

Especially important for Reversal Entry #1.

#12 â€” Exact IFVG

We need to completely define:

FVG â†’ violation â†’ polarity inversion â†’ IFVG

#13 â€” Exact Stop-Loss Selection

This is essential before we can finalize the 2R system.

#14 â€” Exact Entry #1

#### LRL

â†“

Approach

â†“

Sweep

â†“

Rejection

â†“

#### CISD

â†“

#### MSS

â†“

1M confirmation

â†“

#### IFVG/BOS

â†“

Entry

We need to specify exactly which events are mandatory and which are optional.

#15 â€” Exact Entry #2

HTF Bias

â†“

15M structure

â†“

Displacement

â†“

5M BOS

â†“

5M FVG

â†“

#### OTE

â†“

â‰¥50% FVG/OTE overlap

â†“

1M execution

â†“

Entry

Then we'll define the exact trigger.

#16 â€” Conflict Resolution / State Priority

This is extremely important for automation.

For example:

1H bullish + 15M bearish MSS + 5M bullish BOS

The engine needs a deterministic answer.

No interpretation.

#17 â€” No-Trade Rules

We need an explicit list of situations where the engine says:

#### NO TRADE

rather than trying to force a setup.

One architectural decision I want to lock now

The engine should distinguish between:

#### CORE RULES

and

#### CONFIGURABLE PARAMETERS

For example:

#### CORE RULE

Bullish FVG:

C3 Low > C1 High

#### PARAMETER

Minimum displacement threshold:

#### CONFIGURABLE / PENDING VALIDATION

That way, when we backtest the S&P 500 and Nasdaq, we can optimize parameters without changing the underlying trading logic.

I think #7 â€” Mechanical Swing Selection should be our next definition. Once that is locked, a huge portion of the rest of the system becomes much easier to formalize.

Exact Mechanical Swing-Selection Rule
Master Definition
A mechanical swing is a confirmed local price extreme identified using a fixed left/right candle confirmation window. A Swing High is a candle whose high is strictly greater than the highs of the defined number of candles immediately preceding and following it. A Swing Low is a candle whose low is strictly lower than the lows of the defined number of candles immediately preceding and following it.

For the initial system:
Swing strength = 2 candles on each side.

Therefore, we use a 2-left / 2-right fractal.

Mechanical Swing High

A candle is a confirmed Swing High when:
Its High is greater than the High of the previous 2 candles

AND
Its High is greater than the High of the following 2 candles.

Formula
For candle i:
High[i] > High[i-1]

AND
High[i] > High[i-2]

AND
High[i] > High[i+1]

AND
High[i] > High[i+2]

Then:
Swing High = confirmed

Mechanical Swing Low

A candle is a confirmed Swing Low when:
Its Low is lower than the Low of the previous 2 candles

AND
Its Low is lower than the Low of the following 2 candles.

Formula
Low[i] < Low[i-1]

AND
Low[i] < Low[i-2]

AND
Low[i] < Low[i+1]

AND
Low[i] < Low[i+2]

Then:
Swing Low = confirmed

Confirmation delay

This is extremely important for automation.
A swing cannot be known immediately.
For example:
C1 C2 C3 C4 C5
â†‘
candidate
C3 cannot be confirmed until:
C4 and C5 have closed.

Therefore:
A swing becomes confirmed only after the required right-side candles have closed.

This prevents hindsight/repainting.
4. No intrabar confirmation

The engine must not confirm a swing using an unfinished candle.
All confirmation candles must be:
Closed candles.

Therefore:
Real-time price movement cannot prematurely create a confirmed swing.

Equal highs/lows

We need a strict rule here.
Because our definition uses:
strictly greater than

a candle tied with another candle's high is not automatically a Swing High.
Likewise:
equal lows do not automatically produce a Swing Low.

This is intentional because equal highs/lows are liquidity structures, not necessarily conventional swing points.
So:
Swing â‰  Equal High/Low

They should remain separate objects.
6. What happens with a plateau?

Example:
C1 High = 100
C2 High = 105
C3 High = 105
C4 High = 103
C5 High = 101
Neither C2 nor C3 satisfies:
strictly greater than the neighboring high.

Therefore:
No mechanical Swing High from this five-candle sequence.

The equal-high structure can separately be classified as:
Equal High Liquidity Pool

if it satisfies the equal-level rules.
7. Swing High and Swing Low can occur on the same candle

A candle can theoretically have:
a local high
and a local low
relative to the surrounding candles.
Under the pure mechanical definition, it could satisfy both conditions.
Therefore the engine should not automatically assume that every swing alternates High â†’ Low â†’ High â†’ Low.
Instead:
Each swing type is independently detected.

Structural sequencing is handled in the next layer.
8. Structural swing vs mechanical swing

This distinction is critical.
Mechanical swing
A local price extreme satisfying the 2-left / 2-right rule.

Structural swing
A confirmed mechanical swing that is selected as part of the currently relevant market structure.

Therefore:
Every structural swing is a mechanical swing.

But:
Not every mechanical swing is necessarily a structural swing.

This prevents every tiny intraday fluctuation from becoming meaningful structure.
9. How structural swings are selected

Once mechanical swings are identified, the engine evaluates them chronologically.
For a bullish structure:
Swing Low â†’ Swing High â†’ Higher Low â†’ Higher High

For bearish:
Swing High â†’ Swing Low â†’ Lower High â†’ Lower Low

The structural classification depends on comparison with the relevant prior structural swing.
Higher High
Current structural Swing High > previous structural Swing High

Lower High
Current structural Swing High < previous structural Swing High

Higher Low
Current structural Swing Low > previous structural Swing Low

Lower Low
Current structural Swing Low < previous structural Swing Low

Which swing becomes "protected"?

This connects directly to our Order Flow rule.
Bullish
The protected swing is:
The structural Higher Low that preceded and enabled the latest confirmed bullish continuation/BOS.

Bearish
The protected swing is:
The structural Lower High that preceded and enabled the latest confirmed bearish continuation/BOS.

This is the swing that must remain intact for order flow to remain respected.
11. Swing selection for OTE

This also connects directly to our previously locked OTE rule.
For OTE:
Bullish
Structural Swing Low initiating the relevant displacement â†’ Structural Swing High created by that displacement

Bearish
Structural Swing High initiating the relevant displacement â†’ Structural Swing Low created by that displacement

Therefore OTE does not independently select arbitrary Fibonacci swings.
It references the mechanical/structural swing engine.
12. Swing selection for BOS

A BOS must break a:
Confirmed structural swing

â€”not merely any mechanical swing.
Bullish BOS
Qualifying bullish displacement + body close above the relevant confirmed structural Swing High.

Bearish BOS
Qualifying bearish displacement + body close below the relevant confirmed structural Swing Low.

Swing selection for MSS

Likewise:
Bullish MSS
Qualifying bullish displacement + body close above the protected structural Lower High.

Bearish MSS
Qualifying bearish displacement + body close below the protected structural Higher Low.

Therefore the swing engine supplies the exact structural reference.
14. Timeframe independence

The algorithm itself is identical across timeframes.
The engine simply applies it independently to:
1H

15M

5M

1M

A 5M swing is a 5M swing.
It does not become an HTF swing because it happens to be large.
15. No discretionary swing selection

The engine must never select a swing because:
it looks important
it produced a nice FVG
it gives a favorable OTE
it creates a better R:R
it makes the chart look cleaner
it supports the desired bias
The sequence is:
Detect â†’ Confirm â†’ Classify â†’ Select

Never:
Choose â†’ Justify

Final mechanical algorithm

For every timeframe:
CLOSED CANDLES
â†“
Apply 2-left / 2-right test
â†“
Identify candidate Swing Highs/Lows
â†“
Wait for 2 right-side candles to CLOSE
â†“
Confirm swing
â†“
Store timestamp + price + type
â†“
Compare with prior confirmed structural swings
â†“
Classify:
HH / HL / LH / LL
â†“
Use structural swings for:
BOS
MSS
HTF Bias
Order Flow
OTE
LRL
17. Exact locked definition

I recommend we put this into the Trading Brain verbatim:
Mechanical Swing Selection: A mechanical Swing High is a closed candle whose high is strictly greater than the highs of the two immediately preceding closed candles and the two immediately following closed candles. A mechanical Swing Low is a closed candle whose low is strictly lower than the lows of the two immediately preceding and two immediately following closed candles. A swing is not confirmed until both required right-side candles have closed. Equal highs and equal lows do not qualify as mechanical swings under the strict inequality rule and are treated separately as potential liquidity pools. Mechanical swings are detected independently on each timeframe. Structural swings are selected from confirmed mechanical swings and are the only swings eligible for BOS, MSS, protected-order-flow, OTE-anchor, and structural-bias calculations.**

One parameter is now being locked
Swing strength:
2 candles left + 2 candles right

This gives us:
2L / 2R Mechanical Swing

and therefore a 2-candle confirmation delay.
The architecture now becomes:
Mechanical Swing
â†’ Structural Swing
â†’ Protected Swing
â†’ Order Flow
â†’ BOS / MSS
while:
Structural Swing
â†’ OTE
and:
Structural Swing / Liquidity Structure
â†’ LRL

Show more

Yes. #7 Mechanical Swing Selection is now sufficiently precise to lock.

This is an important milestone because it gives us the deterministic foundation for several downstream components.

#7 â€” LOCKED

Mechanical Swing

Swing High: High[i] > High[i-1], High[i-2], High[i+1], High[i+2]

Swing Low: Low[i] < Low[i-1], Low[i-2], Low[i+1], Low[i+2]

Confirmation requires 2 closed candles to the right

No intrabar confirmation

Equal highs/lows do not qualify as mechanical swings

Swing High and Swing Low detection are independent

Applied independently to 1H, 15M, 5M, and 1M

Swing strength = 2L / 2R

Critical distinction now locked

#### MECHANICAL SWING

â†“

Confirm

â†“

#### STRUCTURAL SWING

â†“

â”Œâ”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”

â†“    â†“             â†“

BOS  MSS       Protected Swing

â”‚    â”‚             â”‚

â””â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

â†“

HTF Bias

And separately:

#### STRUCTURAL SWING

â†“

OTE Anchors

and:

#### STRUCTURAL / LIQUIDITY STRUCTURE

â†“

#### LRL

One particularly important rule you've established is:

Detect â†’ Confirm â†’ Classify â†’ Select

rather than selecting a swing first and then rationalizing it.

That will be extremely important when we implement this in code.

One thing I would preserve exactly

We should not yet invent the algorithm for converting every confirmed mechanical swing into a structural swing beyond the rules you've already specified.

You've defined the distinction and the HH/HL/LH/LL classification, but the complete Structural Swing Selection Algorithm still deserves its own definition.

That should be #8, because it sits directly between mechanical swing detection and everything that consumes structural swings.

The next definition should therefore be:

#8 â€” Exact Mechanical Structural Swing Selection & HH/HL/LH/LL Classification

Specifically, we need to answer mechanically:

When does a confirmed mechanical swing become structural?

Which previous structural swing is it compared against?

What happens when several mechanical swings occur between two major structural points?

How are nested/internal swings handled?

Can a mechanical swing be skipped?

How are HH/HL/LH/LL sequences initialized?

What happens when structure becomes conflicting?

How is the structural swing associated with a BOS?

Exactly which HL/LH becomes protected?

What happens to the previous protected swing after a new BOS?

That is the next definition I would lock before moving to LRLs or liquidity sweeps.

Exact locked definition

I recommend we put this into the Trading Brain verbatim:
Mechanical Swing Selection: A mechanical Swing High is a closed candle whose high is strictly greater than the highs of the two immediately preceding closed candles and the two immediately following closed candles. A mechanical Swing Low is a closed candle whose low is strictly lower than the lows of the two immediately preceding and two immediately following closed candles. A swing is not confirmed until both required right-side candles have closed. Equal highs and equal lows do not qualify as mechanical swings under the strict inequality rule and are treated separately as potential liquidity pools. Mechanical swings are detected independently on each timeframe. Structural swings are selected from confirmed mechanical swings and are the only swings eligible for BOS, MSS, protected-order-flow, OTE-anchor, and structural-bias calculations.**

One parameter is now being locked
Swing strength:
2 candles left + 2 candles right

This gives us:
2L / 2R Mechanical Swing

and therefore a 2-candle confirmation delay.
The architecture now becomes:
Mechanical Swing
â†’ Structural Swing
â†’ Protected Swing
â†’ Order Flow
â†’ BOS / MSS
while:
Structural Swing
â†’ OTE
and:
Structural Swing / Liquidity Structure
â†’ LRL
This is an important foundation because we now have one authoritative swing-selection mechanism instead of allowing BOS, MSS, OTE, and LRL to each invent their own definition of a swing.

Exact Mechanical Structural Swing Selection & HH/HL/LH/LL Classification
Specifically, we need to answer mechanically:
When does a confirmed mechanical swing become structural?
Which previous structural swing is it compared against?
What happens when several mechanical swings occur between two major structural points?
How are nested/internal swings handled?
Can a mechanical swing be skipped?
How are HH/HL/LH/LL sequences initialized?
What happens when structure becomes conflicting?
How is the structural swing associated with a BOS?
Exactly which HL/LH becomes protected?
What happens to the previous protected swing after a new BOS?

Yes. This is the structural layer underneath BOS, MSS, HTF bias, order flow, and OTE, so I would make this considerably more precise than the basic 2L/2R swing detector.
The key distinction is:
Mechanical swing detection finds candidates. Structural swing selection decides which candidates actually belong to the market's external structure.

#8 â€” Exact Mechanical Structural Swing Selection & HH/HL/LH/LL Classification

When does a confirmed mechanical swing become structural?

A confirmed mechanical swing does not automatically become structural.
It becomes structural only when it is selected as the dominant extreme of the completed structural leg.
Structural High
A confirmed mechanical Swing High becomes a structural Swing High when:
It occurs after the most recent structural Swing Low, and
It is the highest confirmed mechanical Swing High produced during that upward structural leg, and
A subsequent confirmed mechanical Swing Low establishes that the upward leg has ended.
Structural Low
A confirmed mechanical Swing Low becomes a structural Swing Low when:
It occurs after the most recent structural Swing High, and
It is the lowest confirmed mechanical Swing Low produced during that downward structural leg, and
A subsequent confirmed mechanical Swing High establishes that the downward leg has ended.
So:
A structural swing is confirmed retrospectively at the completion of the leg, but its timestamp remains the timestamp of the actual mechanical swing that formed the extreme.

This allows the engine to skip internal/nested swings mechanically.
2. The structural-selection rule

The engine maintains two active candidates:
Active High Candidate

and
Active Low Candidate

While price is moving upward from a structural low:
Every confirmed mechanical Swing High becomes a candidate.

The engine retains only:
the highest candidate high.

While price is moving downward from a structural high:
Every confirmed mechanical Swing Low becomes a candidate.

The engine retains only:
the lowest candidate low.

Therefore:
Highest high wins.

Lowest low wins.

This is the primary rule for eliminating internal swings.
3. Example â€” several highs between structural lows

Suppose:
Structural Low
â†“
100
â”‚
â”œâ”€â”€ Mechanical High = 110
â”œâ”€â”€ Mechanical High = 114
â”œâ”€â”€ Mechanical High = 112
â”œâ”€â”€ Mechanical High = 118
â”‚
â†“
Mechanical Low = 115
The highs at:
110, 114, 112, 118

are all mechanical swings.
But only:
118

becomes the structural Swing High.
The others are:
internal/nested mechanical swings

and are skipped for external structure.
4. Several lows between structural highs

Exact inverse.
Structural High
â†“
120
â”‚
â”œâ”€â”€ Mechanical Low = 112
â”œâ”€â”€ Mechanical Low = 108
â”œâ”€â”€ Mechanical Low = 110
â”œâ”€â”€ Mechanical Low = 103
â”‚
â†“
Mechanical High = 107
The structural Swing Low is:
103

Not 112, 108, or 110.
Therefore:
Lowest low wins.

Can a mechanical swing be skipped?

Yes.
This is mandatory.
Mechanical swing â‰  structural swing.

A mechanical swing is skipped when another mechanical swing of the same type produces a more extreme price before the current structural leg terminates.
Example:
Mechanical High 110 â†’ 114 â†’ 112 â†’ 118

Only:
118

becomes structural.
This prevents every tiny fractal from becoming a structural BOS/MSS reference.
6. How nested/internal swings are handled

Nested swings remain recorded, but they are classified separately.
The engine should maintain:
Mechanical structure
All confirmed 2L/2R swings.
Structural structure
Only the selected dominant alternating swings.
Internal swings
Mechanical swings occurring inside the current structural leg that are not selected as its dominant extreme.
Therefore:
Internal swings may exist without changing external structure.

They may still be useful for lower-timeframe analysis, but they cannot replace the structural swing used by:
BOS
MSS
protected swing
HTF bias
OTE anchor
unless independently selected as structural on that timeframe.
7. Structural swings must alternate

The external structural sequence must alternate:
High â†’ Low â†’ High â†’ Low

or:
Low â†’ High â†’ Low â†’ High

The engine cannot produce:
High â†’ High â†’ High

as consecutive structural swings.
If multiple mechanical highs occur before a structural low is established:
Only the highest one survives as the structural high.

Likewise for lows.
8. How structure is initialized

This needs to be deterministic.
At the beginning of available historical data:
Step 1
Detect the first confirmed mechanical swing.
That becomes:
Initial structural anchor

but it is not yet classified HH/HL/LH/LL.
Step 2
Wait for the first confirmed mechanical swing of the opposite type.
Now we have:
High â†’ Low

or:
Low â†’ High

These establish the initial structural range.
Step 3
Wait for the next opposite-side structural candidate.
Now the engine can begin making comparisons.
For example:
Initial High = 100
Initial Low = 90
Next High = 110
The 110 high is:
Higher High (HH)

Then:
Next Low = 95
The 95 low is:
Higher Low (HL)

Now the bullish sequence is:
HH â†’ HL â†’ HH

and bullish structure is established.
9. Initial swings are not automatically HH/HL/LH/LL

This is important.
The first confirmed high is simply:
INITIAL_HIGH

The first confirmed low:
INITIAL_LOW

There is no legitimate basis for calling the first high a "Higher High" because there is no prior structural high.
Likewise:
The first low cannot be called a Higher Low or Lower Low.

The engine needs a prior structural swing of the same type for classification.
10. HH/HL/LH/LL classification

Classification is always against the previous structural swing of the same type.
Current High
Compare to:
Previous structural High

If:
Current High > Previous Structural High

then:
HH

If:
Current High < Previous Structural High

then:
LH

Current Low
Compare to:
Previous structural Low

If:
Current Low > Previous Structural Low

then:
HL

If:
Current Low < Previous Structural Low

then:
LL

Never compare a high to a low

This sounds obvious, but it should be explicit in the engine.
Wrong:
Current High vs previous Low.

Correct:
Current High vs previous structural High.

Likewise:
Current Low vs previous structural Low.

What happens when structure becomes conflicting?

A market can produce combinations such as:
HH + LL

or:
LH + HL

These do not automatically create a clean directional trend.
Therefore the engine should distinguish:
Bullish structural state
Requires:
HH + HL progression

Bearish structural state
Requires:
LL + LH progression

Conflicting structural state
Examples:
HH + LL

or
LH + HL

without a completed directional sequence.
Then:
Structural State = CONFLICTED / NEUTRAL

The engine must not force a bullish or bearish interpretation.
13. Important: conflicting structure does not erase the swings

If the sequence becomes:
HH â†’ LL

the HH and LL remain valid structural swings.
What changes is:
the directional interpretation.

Therefore:
Structural history remains intact.

Current directional state becomes neutral/conflicted.

Exact bullish sequence

The engine recognizes bullish structure when it establishes:
HH â†’ HL â†’ HH

The most recent sequence demonstrates:
higher high
higher low
higher high
The resulting state:
BULLISH STRUCTURE

The latest HL becomes the candidate protected low once the subsequent HH is confirmed by bullish continuation/BOS.
15. Exact bearish sequence

Bearish structure requires:
LL â†’ LH â†’ LL

The resulting state:
BEARISH STRUCTURE

The latest LH becomes the candidate protected high once the subsequent LL is confirmed by bearish continuation/BOS.
16. Which structural swing is associated with a BOS?

This needs to be exact.
Bullish BOS
A bullish BOS breaks:
the most recent confirmed structural Swing High that has not already been broken.

The candle must:
close above that structural high

AND
satisfy the qualifying bullish displacement rule.

That broken high becomes:
the structural high that was exceeded by the BOS.

Bearish BOS
A bearish BOS breaks:
the most recent confirmed structural Swing Low that has not already been broken.

The candle must:
close below that structural low

AND
satisfy qualifying bearish displacement.

What structural swing does the BOS create?

This distinction matters.
The swing that is broken is not the new swing.
Example:
HL
â”‚
â”‚
â””â”€â”€â”€â”€â”€â”€ HH = 120
â†‘
â”‚
Bullish BOS
â”‚
â†“
125
The BOS breaks:
120

But 125 is not automatically a confirmed structural Swing High.
It must first satisfy the mechanical swing-confirmation rule.
So:
BOS breaks an existing structural swing.

The resulting extreme becomes a new structural swing only after mechanical confirmation.

This prevents BOS from creating unconfirmed hindsight swings.
18. Exactly which HL becomes protected?

For a bullish BOS:
The protected HL is the most recent structural Higher Low that directly preceded the structural high broken by that BOS.

Example:
HL1 = 100
â†“
HH1 = 120
â†“
HL2 = 110
â†“
HH2 = 130
â†“
Bullish BOS of 130
The protected low is:
HL2 = 110

Not HL1.
Why?
Because HL2 is the structural low that produced the delivery into the broken HH2.
Therefore:
HL2 is protected.

Bearish protected swing

Exact inverse.
LH1 = 120
â†“
LL1 = 100
â†“
LH2 = 110
â†“
LL2 = 90
â†“
Bearish BOS of 90
The protected swing is:
LH2 = 110

because it directly preceded the structural low that was broken.
Therefore:
LH2 becomes the protected Lower High.

What happens to the previous protected swing after a new BOS?

This should be absolute:
The previous protected swing is demoted from protected status when a new BOS establishes a newer protected swing.

Example:
Before new BOS
Protected HL = 100

Price creates:
HL = 110 â†’ HH = 130

Bullish BOS occurs through 130.
Now:
110 becomes Protected HL.

The previous:
100 is no longer protected.

It remains a historical structural low, but it is no longer the active order-flow invalidation level.
21. Why this matters for MSS

This prevents the engine from using an old low as the MSS reference after the market has created newer structure.
Example:
Protected HL1 = 100
â†“
HH = 120
â†“
New HL = 110
â†“
HH = 130
â†“
BOS
After BOS:
Protected HL = 110

If price later closes below 110 with qualifying bearish displacement:
Bearish MSS

It does not need to break 100.
This makes the protected swing dynamic.
22. Structural state machine

The cleanest implementation is:
MECHANICAL SWINGS
â†“
CONFIRMED
â†“
STRUCTURAL CANDIDATE
â†“
SELECT DOMINANT EXTREME
â†“
STRUCTURAL SWING
â†“
CLASSIFY
HH / HL / LH / LL
â†“
ESTABLISH STRUCTURAL STATE
â†“
BOS / MSS
â†“
UPDATE PROTECTED SWING
23. Complete mechanical algorithm

Step 1 â€” Detect
Apply the previously locked:
2-left / 2-right mechanical swing rule.

Step 2 â€” Confirm
Wait for the two right-side candles to close.
Step 3 â€” Maintain candidates
During an upward leg:
retain the highest confirmed mechanical high.

During a downward leg:
retain the lowest confirmed mechanical low.

Step 4 â€” Structuralize
When the opposing leg is confirmed:
finalize the dominant extreme as the structural swing.

Step 5 â€” Classify
Compare current structural swing against the previous structural swing of the same type.
Step 6 â€” Determine state
HH + HL â†’ bullish

LL + LH â†’ bearish

conflicting â†’ neutral

Step 7 â€” BOS
A qualifying-displacement body close through the relevant structural swing creates BOS.
Step 8 â€” Protect
After bullish BOS:
most recent HL preceding the broken HH becomes Protected HL.

After bearish BOS:
most recent LH preceding the broken LL becomes Protected LH.

Step 9 â€” Demote
When a new BOS occurs:
previous protected swing â†’ historical/unprotected

newest qualifying HL/LH â†’ protected.

Final Locked Definition

I recommend this exact language for the system:
Mechanical Structural Swing Selection: Confirmed mechanical swings are structuralized through an alternating-leg selection process. During an upward structural leg, all confirmed mechanical Swing Highs are candidates and only the highest confirmed high becomes the structural Swing High once a subsequent structural Swing Low establishes completion of the leg. During a downward structural leg, all confirmed mechanical Swing Lows are candidates and only the lowest confirmed low becomes the structural Swing Low once a subsequent structural Swing High establishes completion of the leg. Mechanical swings that are superseded by a more extreme same-type swing within the same structural leg are classified as internal/nested swings and are skipped for external structural purposes. Structural swings alternate High/Low and are classified only against the previous structural swing of the same type: higher high = HH, lower high = LH, higher low = HL, lower low = LL. Initial swings are unclassified until a prior same-type structural swing exists. A valid bullish structural sequence requires HH/HL progression; a valid bearish sequence requires LL/LH progression; conflicting combinations produce a Neutral/Conflicted structural state rather than forcing directional bias.**

And:
BOS Association: A bullish BOS is a qualifying bullish displacement with a candle body close above the most recent unbroken confirmed structural Swing High. A bearish BOS is a qualifying bearish displacement with a candle body close below the most recent unbroken confirmed structural Swing Low. The extreme produced by the BOS is not considered a confirmed structural swing until it independently satisfies the mechanical swing-confirmation rule.**

And:
Protected Swing Rule: Following a bullish BOS, the protected swing is the most recent structural Higher Low that directly preceded the structural High broken by that BOS. Following a bearish BOS, the protected swing is the most recent structural Lower High that directly preceded the structural Low broken by that BOS. When a subsequent BOS establishes a newer protected swing, the previous protected swing is demoted to historical/unprotected status and the newer HL/LH becomes the sole active protected swing.**

The resulting architecture
This gives us a clean hierarchy:
2L/2R Mechanical Swing
â†’ Structural Swing Selection
â†’ HH / HL / LH / LL
â†’ Structural State
â†’ BOS / MSS
â†’ Protected Swing
â†’ Order Flow Respect/Disrespect
â†’ HTF Bias
And separately:
Structural Swings
â†’ OTE Anchors
and:
Structural/Liquidity Swings
â†’ LRL

Show more

Yes. We now have the Mechanical Swing Selection and the Structural Swing Selection / HH-HL-LH-LL Classification locked.

The next step should be to continue formalizing the remaining engine definitions before writing code. The architecture is now becoming sufficiently precise that we should avoid jumping into Claude Code prematurely.

I would proceed in this order:

Mechanical Swing Selection âœ…

2L / 2R

confirmed only after two right candles close

strict inequalities

equal highs/lows separate

Structural Swing Selection & Classification âœ…

dominant extreme wins

internal/nested swings skipped

alternating structural swings

#### HH / HL / LH / LL

conflicting structure â†’ Neutral/Conflicted

BOS association

dynamic protected swing

HTF Bias âœ…

1H

Bullish / Bearish / Neutral

MSS removes old bias

opposite BOS/structure required to establish new bias

Order Flow Respect / Disrespect âœ…

protected swing is authoritative

wick â‰  violation

close + qualifying displacement = disrespect

timeframe-specific

Approaching LRL âœ…

0.25 Ã— ATR(14) initial parameter

distance must decrease

pre-existing level

FAR â†’ APPROACHING â†’ REACHED â†’ VIOLATED

LRL Target Selection âœ…

nearest qualifying opposing LRL

already-swept liquidity excluded

no target shopping

minimum 2R

if nearest target <2R â†’ reject

Relevant Delivery Candle âœ…

most recent contiguous delivery leg

first candle of that leg

doji terminates delivery

initiation candle's open = CISD reference

CISD âœ…

bullish close above bearish delivery-open

bearish close below bullish delivery-open

body close required

no displacement requirement

CISD â‰  MSS

The important thing

I would not upload this to Claude Code yet.

We have the foundational definitions, but there are still several mechanical components that need to be locked before implementation. Otherwise Claude Code will inevitably make assumptions in the gaps, and those assumptions could become buried inside the implementation.

Next definitions I would lock

#9 â€” Exact Mechanical Displacement Definition

This should be next.

We already agreed on:

Displacement should be configurable rather than hard-coded as a universal market law.

Now we need to define exactly what qualifies as displacement.

For example, we need to mechanically settle:

What candle measurements are used?

Body size?

True range?

ATR?

Body-to-range ratio?

Close location?

Direction?

Minimum threshold?

Does displacement have to exceed X Ã— ATR(14)?

Is the ATR calculated on the same timeframe?

Does a displacement candle need to close near its extreme?

Can multiple candles collectively constitute displacement?

Can an FVG qualify as evidence of displacement?

Or are FVG and displacement completely independent?

Does displacement have to break a structural level?

What constitutes qualifying bullish displacement versus ordinary bullish expansion?

What constitutes qualifying bearish displacement?

How do we prevent one enormous news candle from automatically satisfying every displacement condition?

And most importantly:

We should separate the concepts

Candle Direction

â†“

Candle Expansion

â†“

Qualifying Displacement

â†“

#### BOS / MSS

rather than allowing:

Big candle = displacement

That distinction will matter enormously for automation.

Your market scope

Your clarification that the strategy is designed primarily for S&P 500 and Nasdaq is also useful for the eventual implementation.

I would encode the system architecture so that:

Instrument

â†“

#### ES / SPX

NQ / Nasdaq

â†“

Same structural engine

â†“

Instrument-specific parameters

rather than building two completely separate strategies.

That means things such as displacement thresholds, ATR behavior, session definitions, tick/price precision, and potentially liquidity tolerances can be configurable parameters, while the underlying structural logic remains identical.

So we should not optimize the definitions specifically to ES or NQ yet. First we make the mechanics universal; then the configuration can be tuned/backtested specifically for S&P 500 and Nasdaq.

so what do you need next?

Next, I need #23 â€” your exact mechanical Liquidity Pool & Liquidity Sweep definition.

Please give me the rules you want locked for:

Liquidity Pool

What exactly creates one?

Equal highs/lows?

Swing highs/lows?

Both?

Minimum number of touches?

How close must prices be to count as equal?

Liquidity Level

Exact price represented by the pool.

How multiple highs/lows are consolidated into one level.

Liquidity Sweep

What constitutes a sweep?

Wick through the liquidity level?

Body close through it?

Does the candle need to close back on the original side?

Is penetration required to be strictly greater than the level?

#### LRL / LSL

Exact definition of Low-Resistance Liquidity / Low-Side Liquidity if those are part of your system.

Exact relationship to liquidity pools.

Sweep vs structural break
We need to preserve the distinction between:

Liquidity Sweep

â‰ 

Structural Break

â‰ 

#### MSS

So define exactly where the boundaries are.

Protected swing liquidity

Is a protected high/low automatically a liquidity target?

Or does it only become liquidity when another qualifying condition exists?

Internal vs external liquidity

Whether you want this distinction now.

If yes, the exact mechanical criteria for each.

Timeframe behavior

Whether a 1M candle can sweep a 5M liquidity level.

Whether that counts as a 5M sweep or only a 1M interaction.

Persistence

When liquidity is considered consumed.

Whether a swept pool can be swept again.

Whether the original pool remains historically recorded.

One candle / multiple events

Whether one candle can simultaneously be:

Liquidity Sweep

+ Displacement

+ IFVG

+ MSS

which I expect should remain yes, consistent with your earlier architecture.

Most importantly

Don't worry about making it pretty. Give me #23 in the same detailed format you used for #17â€“#22.

I'll then do the same thing we've been doing:

your definition â†’ check for ambiguity/dependency conflicts â†’ mechanically formalize it â†’ identify anything that still needs to be parameterized â†’ lock #23.

After #23, we'll continue through the remaining primitives in dependency order rather than jumping prematurely into the actual trading/setup logic.

Yes. #23 should now lock the liquidity engine itself: how liquidity is created, consolidated, classified, swept, consumed, and exposed to lower-timeframe interaction.
I would make one terminology correction before locking it:
I recommend using LRL = Liquidity Reference Level rather than â€œLow-Resistance Liquidity.â€
An LRL is the specific liquidity price/level selected by the engine as the relevant target or sweep reference.

For downside liquidity, we can separately use LSL = Low-Side Liquidity.
For upside liquidity, BSL = Buy-Side Liquidity.
That gives us clean terminology:
BSL = Buy-Side Liquidity
LSL = Low-Side Liquidity
LRL = Liquidity Reference Level
#23 â€” Exact Mechanical Liquidity Pool & Liquidity Sweep Definition

What is liquidity?

For this engine:
Liquidity is a mechanically identifiable concentration of resting stop/trigger orders inferred from repeated or structurally significant price extremes.

The engine does not claim to see actual resting orders.
It infers liquidity from observable price structure.
The primary observable sources are:
equal highs
equal lows
confirmed structural highs
confirmed structural lows
significant session highs/lows
previous-day high/low
previous-week high/low
other explicitly defined external reference highs/lows
But not every one of these automatically becomes a liquidity pool.
2. Liquidity Pool

A Liquidity Pool is:
A collection of two or more qualifying same-side price extremes whose prices fall within the system's equality tolerance and therefore represent one consolidated liquidity level.

So:
High A
High B
High C
â†“
within tolerance
â†“
ONE Buy-Side Liquidity Pool
Likewise:
Low A
Low B
â†“
within tolerance
â†“
ONE Low-Side Liquidity Pool
3. Minimum number of touches

The minimum is:
2 qualifying touches.

Therefore:
H1 â‰ˆ H2
is sufficient to create a pool.
Three touches:
H1 â‰ˆ H2 â‰ˆ H3
strengthen the pool but are not required for creation.
This preserves the idea of equal highs/lows without requiring an arbitrary three-touch rule.
4. What counts as a qualifying touch?

A touch must be a qualifying price extreme, not simply any candle high/low.
For a buy-side pool:
Qualifying High =
confirmed mechanical swing high
OR
explicitly registered external/session reference high
For a low-side pool:
Qualifying Low =
confirmed mechanical swing low
OR
explicitly registered external/session reference low
Ordinary candle highs/lows that are not qualifying reference points do not independently create liquidity pools.
5. Exact equality tolerance

This must be objective.
I recommend:
Equality tolerance = 1 minimum price increment (1 tick).

Therefore two highs qualify as equal when:
abs(HighA - HighB) â‰¤ TickSize
and two lows qualify when:
abs(LowA - LowB) â‰¤ TickSize
Examples:
If tick size is 0.25:
5000.00
5000.25
qualify as equal.
But:
5000.00
5000.50
do not.
6. Why fixed tick tolerance?

We should not use ATR-normalized equality.
ATR changes with volatility.
That would mean the same two prices could be equal in one volatility regime and unequal in another.
Liquidity geometry should remain deterministic.
Therefore:
EqualityTolerance = 1 Ã— TickSize
is locked.
7. Liquidity Level

A liquidity pool needs one representative price.
For a pool containing:
5000.00
5000.25
5000.00
the engine consolidates the pool into one level.
I recommend the representative level be:
the arithmetic mean of the qualifying extreme prices contained in the pool.

So:
(5000.00 + 5000.25 + 5000.00) / 3
= 5000.0833...
However, because execution occurs on discrete ticks, the stored liquidity level should be rounded to the nearest valid tick.
This gives:
LiquidityLevel

RoundToTick(mean(component_prices))
8. Alternative simpler level

For actual sweep detection, however, I recommend something even more robust:
The liquidity pool retains both its component extremes and its consolidated level.

So the object contains:
component_prices[]
consolidated_level
This preserves the original information rather than destroying it.
9. Buy-side vs low-side liquidity

Buy-side liquidity
Generally resides above price.
Examples:
equal highs
swing highs
session high
previous-day high
previous-week high
These become:
BSL
Low-side liquidity
Generally resides below price.
Examples:
equal lows
swing lows
session low
previous-day low
previous-week low
These become:
LSL
10. LRL

I recommend defining:
LRL = Liquidity Reference Level.

An LRL is not a new kind of liquidity.
It is a selected liquidity level that the setup engine has determined is relevant to the current analysis.
For example:
BSL Pool A
BSL Pool B
LSL Pool C
LSL Pool D
The liquidity engine identifies all of them.
The target-selection engine may then designate:
LRL = Pool C
as the relevant liquidity reference.
Therefore:
Liquidity Pool
â†“
Liquidity Level
â†“
LRL selection
This keeps #23 separate from the earlier LRL Target Selection definition.
11. Liquidity Sweep

The exact sweep rule should be:
A liquidity sweep occurs when price trades beyond a qualified liquidity level and subsequently closes back on the original side of that level within the same candle.

For buy-side liquidity:
Price above level
â†“
trades above BSL
â†“
closes back BELOW BSL
â†“
BUY-SIDE SWEEP
For low-side liquidity:
Price below level
â†“
trades below LSL
â†“
closes back ABOVE LSL
â†“
LOW-SIDE SWEEP
12. Wick-through requirement

Yes.
A sweep requires actual penetration beyond the liquidity level.
Therefore:
High > BSL
is required for a buy-side sweep.
And:
Low < LSL
is required for a low-side sweep.
A candle that merely touches:
High = BSL
is not a sweep.
13. Strict inequality

This should be explicit.
Buy-side:
Candle.High > LiquidityLevel
Low-side:
Candle.Low < LiquidityLevel
Equality alone does not count.
14. Does the candle need to close back across the level?

Yes.
This is essential.
A buy-side sweep requires:
High > BSL
AND
Close < BSL
A low-side sweep requires:
Low < LSL
AND
Close > LSL
Therefore:
penetration + rejection
is required.
15. Body close through the level

A body close beyond the liquidity level without returning to the original side is not a sweep.
Example:
BSL = 5000

High = 5010
Close = 5005
This is:
Liquidity penetration
NOT sweep
It represents acceptance/continuation beyond the liquidity level.
If the level is also a structural reference, it may participate in BOS/MSS logic independently.
16. Sweep does not require displacement

This remains locked:
A liquidity sweep does not require qualifying displacement.

Therefore:
Sweep
â‰ 
Displacement
A tiny rejection candle can technically sweep liquidity.
Whether that sweep becomes part of a valid trading setup depends on subsequent requirements.
17. Sweep does not require BOS

Also:
Sweep
â‰ 
BOS
A liquidity sweep can occur without breaking structural structure.
18. Sweep does not require MSS

Likewise:
Sweep
â‰ 
MSS
For the reversal model:
LRL sweep
â†“
qualifying displacement
â†“
protected swing break
â†“
MSS
The sweep is the liquidity event.
MSS is the structural event.
19. Sweep vs structural break

This distinction should be permanently encoded.
Liquidity Sweep
Requires:
penetration beyond liquidity
+
close back across liquidity level
Structural Break
Requires:
structural swing violation
+
required body close
+
qualifying displacement
MSS
Requires:
opposing structural regime
+
protected swing break
+
body close through protection
+
qualifying displacement
And for the reversal setup:
LRL sweep must precede MSS
20. Protected swing liquidity

A protected swing is not automatically an LRL.
This is important.
A protected low can be:
Protected Low
without necessarily being a liquidity pool.
However, because it is a structural extreme, it can become a liquidity reference if it meets the relevant liquidity-selection criteria.
So:
Protected Swing
â†“
structural reference
â†“
potential liquidity
but not:
Protected Swing
â†“
automatically liquidity pool
21. Why?

Because otherwise every protected swing would automatically be a liquidity target.
That would collapse:
structure
and:
liquidity
into the same primitive.
We want them separate.
22. Can a single structural swing be liquidity?

Yes.
A confirmed structural high/low can itself represent a liquidity level when it is a qualifying external/reference liquidity point.
But a pool requires two or more qualifying components.
So:
One swing
â†’ liquidity level/reference
while:
Two+ equal qualifying swings
â†’ liquidity pool
23. Internal vs external liquidity

I recommend defining this now.
Internal Liquidity
Liquidity located inside the current active dealing range.
Examples:
internal swing high
internal equal highs
internal swing low
internal equal lows
External Liquidity
Liquidity located outside the current active dealing range, or represented by a major external reference such as:
previous-day high/low
previous-week high/low
session extreme
major structural extreme
The exact classification is therefore positional:
Current Dealing Range
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ INTERNAL LIQUIDITY â”‚
â”‚ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â†‘ â†‘
EXTERNAL EXTERNAL
LIQUIDITY LIQUIDITY
24. Internal liquidity cannot modify the range

An internal liquidity pool being swept does not automatically alter:
dealing range
protected swing
structural regime
bias
It is a liquidity event only.
25. External liquidity has higher target priority

For target selection, external liquidity should generally outrank internal liquidity.
Therefore, when the engine is searching for an LRL target:
External qualifying liquidity
is preferred over:
Internal qualifying liquidity
subject to the previously defined target-selection constraints.
This prevents the system from routinely targeting tiny internal pools when a meaningful external liquidity objective exists.
26. Timeframe behavior

This is critical.
Liquidity is timeframe-owned, but lower timeframes can interact with higher-timeframe liquidity.
Example:
5M liquidity level = 5000
A 1M candle can trade:
5000.25
and close:
4999.75
That is a 1M sweep of a 5M liquidity level.
But it does not automatically become a 5M sweep.
27. Exact timeframe rule

The timeframe of the sweep is the timeframe of the candle that performs the sweep. The timeframe of the liquidity is the timeframe on which the liquidity level was created.

So the event can be represented:
Liquidity:
5M

Sweep:
1M
as:
SweepEvent {
liquidity_timeframe = 5M
sweep_timeframe = 1M
}
This is extremely useful for your multi-timeframe model.
28. 1M sweep of 5M liquidity

A 1M candle can therefore trigger:
1M Sweep
of
5M LRL
But:
5M sweep = FALSE
until a 5M candle itself satisfies the sweep criteria.
29. Does a lower-timeframe sweep invalidate the higher-timeframe liquidity?

Yes, if it is a genuine sweep.
The liquidity pool becomes:
CONSUMED
from the perspective of that liquidity event.
But the higher-timeframe liquidity object remains historically recorded.
30. Persistence

Liquidity objects should be immutable historical records.
A pool can transition:
ACTIVE
â†“
SWEPT
â†“
CONSUMED
but the original object is never deleted.
31. Can swept liquidity be swept again?

The same liquidity pool should not generate another independent sweep event after it has been consumed.
This prevents:
same level
â†“
sweep
â†“
rejection
â†“
"sweep" again
â†“
"sweep" again
from generating unlimited signals.
So:
One liquidity pool = one consumable liquidity event.

What if new liquidity forms at the same price?

That is different.
Suppose:
Old pool = 5000
gets swept.
Later:
new equal highs form at 5000
Those can create a new liquidity pool object if the new qualifying references satisfy the pool rules.
Therefore:
Old Pool #17
â‰ 
New Pool #42
even if their representative prices are identical.
33. Sweep penetration distance

We should not impose a maximum penetration distance.
A sweep remains a sweep as long as:
price penetrates beyond level
+
same candle closes back across level
Therefore:
penetration = 1 tick
can qualify.
And:
penetration = 20 ticks
can also qualify.
There is no ATR-based penetration threshold.
34. But what if price travels enormously beyond the level?

Still a sweep if the same candle closes back across the level.
Example:
BSL = 5000

High = 5100
Close = 4990
Technically:
BSL Sweep = TRUE
Whether the candle also qualifies as displacement is a separate question.
This is important because liquidity and displacement remain independent.
35. One candle can perform multiple events

Yes.
A single candle can simultaneously be:
Liquidity Sweep
+
Qualifying Displacement
+
FVG Creation
+
IFVG conversion
+
MSS
provided every primitive's individual conditions are satisfied.
There is no rule requiring these events to occur on separate candles.
36. Example: complete reversal candle

Suppose:
Bearish structure
Protected High = 5000
LRL/BSL = 5005
A candle:
High = 5010
Low = 4970
Close = 4965
could potentially:

Sweep 5005

Generate qualifying bearish displacement

Close below protected high 5000

Confirm bearish/bullish MSS depending on existing regime

Create FVG

The engine evaluates each event independently.
37. Sweep and displacement causal order

Although one candle can perform both, the engine should still store event timestamps at candle granularity.
For a same-candle event:
Sweep.timestamp = CandleClose
Displacement.timestamp = CandleClose
MSS.timestamp = CandleClose
and:
same_candle = TRUE
This avoids inventing intrabar sequencing that the OHLC data cannot prove.
38. Important: do not infer intrabar order

If the candle contains:
High
Low
Close
we know the extremes occurred, but without lower-timeframe data we cannot know exactly whether:
sweep â†’ displacement
or:
displacement â†’ sweep
occurred intrabar.
Therefore the engine should never invent that sequence.
It records:
same candle
and relies on timeframe-specific confirmation rules.
39. Multiple liquidity pools swept by one candle

Yes.
A sufficiently large candle can sweep multiple liquidity levels.
Example:
BSL1 = 5000
BSL2 = 5005
BSL3 = 5010

Candle High = 5015
Close = 4995
The candle has penetrated all three.
Each qualifying pool can produce a sweep event.
However, the engine should consolidate overlapping/equivalent pools before event generation so that one physical pool does not produce duplicate events.
40. Sweep state machine

I recommend:
Liquidity Pool
â”‚
â–¼
ACTIVE
â”‚
â”‚ penetration
â–¼
VIOLATED
â”‚
â”‚ close returns across level
â–¼
SWEPT
â”‚
â–¼
CONSUMED
If price penetrates the level but doesn't close back across it:
ACTIVE
â†“
VIOLATED
â†“
NOT SWEPT
The pool is not considered swept merely because price traded through it.
41. What happens after failed penetration?

Example:
BSL = 5000
High = 5010
Close = 5005
Then:
penetrated = TRUE
sweep = FALSE
The liquidity has been traded through, so it should no longer be treated as untouched liquidity.
I recommend the state:
CONSUMED / BROKEN
rather than leaving it active.
Why?
Because stops that were sitting above 5000 have already been exposed/triggered.
It should not later be treated as untouched liquidity.
42. Therefore two different events exist

Sweep
penetration
+
close back across
Liquidity consumption without sweep
penetration
+
close remains beyond
This distinction is extremely useful.
43. Exact pool lifecycle

ACTIVE
â”‚
â”œâ”€â”€ no interaction â†’ ACTIVE
â”‚
â”œâ”€â”€ touch only â†’ ACTIVE
â”‚
â”œâ”€â”€ penetration + close back â†’ SWEPT â†’ CONSUMED
â”‚
â””â”€â”€ penetration + close beyond â†’ BROKEN â†’ CONSUMED
A mere touch does not consume liquidity.
44. Liquidity pool object

I recommend:
LiquidityPool {
id
timeframe

side

// BSL

// LSL

component_reference_ids[]

component_prices[]

consolidated_level

tolerance_ticks = 1

touch_count

created_time

confirmation_time

state

// ACTIVE

// SWEPT

// BROKEN

// CONSUMED

sweep_event_id

consumed_time

structural_context

// INTERNAL

// EXTERNAL

}
45. Sweep event object

LiquiditySweep {
id

liquidity_pool_id

liquidity_timeframe

sweep_timeframe

side

// BSL

// LSL

liquidity_level

penetration_price

penetration_ticks

candle_id

candle_time

close_price

displacement_present

bos_present

mss_present

same_candle_events[]

confirmed

}
This gives the engine enough information to reconstruct exactly what happened.
46. Exact bullish/low-side sweep algorithm

For an LSL:
Given liquidity level L:

IF Candle.Low < L
AND Candle.Close > L

#### THEN:

SweepConfirmed = TRUE
Otherwise:
SweepConfirmed = FALSE
Strictly:
Low < L
not:
Low <= L
47. Exact bearish/buy-side sweep algorithm

For BSL:
Given liquidity level H:

IF Candle.High > H
AND Candle.Close < H

#### THEN:

SweepConfirmed = TRUE
Otherwise:
SweepConfirmed = FALSE
48. What about a candle that sweeps and closes exactly on the level?

I recommend not counting it as a sweep.
For BSL:
High > BSL
AND
Close < BSL
For LSL:
Low < LSL
AND
Close > LSL
Equality is insufficient.
This maintains the strict rejection requirement.
49. Liquidity vs protected structure

We now have three independent concepts:
Liquidity
â†“
potential target / sweep location

Protected Structure
â†“
structural regime defense

MSS
â†“
confirmed structural reversal
A protected low may also be a liquidity reference.
But:
protected low â‰  automatically LSL pool
And:
LSL sweep â‰  MSS
Only when the protected structural requirements are also satisfied does MSS occur.
50. Final locked definition

Liquidity Pool: A pool consists of at least two qualifying same-side price extremes whose prices are within one minimum tick of one another. Qualifying extremes are confirmed mechanical/structural swing highs or lows and explicitly registered external/session reference highs/lows.

Liquidity Level: Each pool is represented by a consolidated tick-valid level derived from its component prices, while retaining the original component prices.

BSL: Buy-side liquidity located above the relevant current price context.

LSL: Low-side liquidity located below the relevant current price context.

LRL: Liquidity Reference Level; the specific liquidity level selected by the engine as the relevant liquidity objective/reference for the current setup. It is not a separate liquidity type.

Liquidity Sweep: A candle sweeps BSL when its high is strictly greater than the BSL level and its close is strictly below that level. A candle sweeps LSL when its low is strictly less than the LSL level and its close is strictly above that level.

Touch: A candle whose extreme equals or approaches the liquidity level without strict penetration is not a sweep.

Sweep displacement: Displacement is not required for a sweep.

Sweep vs structure: A liquidity sweep does not constitute BOS or MSS. BOS/MSS require their own structural-break and displacement conditions.

Protected swings: A protected high/low is not automatically a liquidity pool, although it may independently serve as a liquidity reference if it meets the relevant liquidity criteria.

Timeframes: Liquidity belongs to the timeframe on which its reference was established. A lower-timeframe candle may sweep a higher-timeframe liquidity level, but the event remains a lower-timeframe sweep of a higher-timeframe pool.

Consumption: Once liquidity has been penetrated, it is considered consumed. A sweep is the specific consumed state in which price subsequently closes back across the level. Penetration followed by a close beyond the level is consumption/breaking without a sweep.

Persistence: Historical liquidity pools are never deleted. A consumed pool cannot generate another sweep event. New qualifying liquidity formed afterward creates a new liquidity object.

Multiple events: One candle may simultaneously produce a liquidity sweep, qualifying displacement, FVG/IFVG event, BOS, and/or MSS, provided every individual primitive's conditions are satisfied. The engine must not infer an intrabar ordering that its timeframe data cannot establish.

The resulting architecture
We now have a clean separation:
LIQUIDITY
â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â–¼ â–¼
BSL LSL
â”‚ â”‚
â–¼ â–¼
Liquidity Pool Liquidity Pool
â”‚ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â–¼
LRL
â”‚
â–¼
SWEEP EVENT
â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”
â–¼ â–¼
No structure Structure
â”‚ â”‚
Sweep only BOS / MSS
And critically:
LIQUIDITY SWEEP
â‰ 
DISPLACEMENT
â‰ 
BOS
â‰ 
MSS
They can occur on the same candle, but they remain independent state variables.
That gives the engine the exact distinction your reversal model needs:
LRL/LSL identified
â†“
Liquidity Sweep
â†“
Qualifying Displacement
â†“
Protected Swing violation
â†“
MSS
â†“
1M confirmation / IFVG / FVG
This is the right foundation for the next primitive: #24 â€” exact mechanical LRL selection / target selection,

Show more

Yes. With #23 now locked, the next primitive is clearly:

#24 â€” Exact Mechanical LRL / Target Selection

This is the correct next step because #23 tells us what liquidity exists and when it is consumed, but it deliberately leaves open the question:

When multiple valid liquidity pools exist, which one becomes the relevant Liquidity Reference Level (LRL) for the current setup?

That selection cannot be discretionary.

The dependency chain is now:

#19 Mechanical Swings

â†“

#20 Structural Classification

â†“

#21 Structural / Dealing Range

â†“

#22 OTE

â†“

#23 Liquidity Pools / Sweeps

â†“

#24 LRL / Target Selection

â†“

#25 FVG / IFVG interaction

â†“

#26 Setup / Entry qualification

#24 needs to mechanically answer

Given:

Current Price

Active Dealing Range

Structural Regime

Protected Swing

BSL pools

LSL pools

Internal liquidity

External liquidity

Consumed liquidity

Historical liquidity

the engine must deterministically select:

LRL = exactly one relevant liquidity reference

â€”or explicitly return:

LRL = NONE

if no qualifying target exists.

The major definitions we need to lock

I would make #24 answer these in order:

Eligible liquidity

Which BSL/LSL pools are eligible?

Must they be unconsumed?

Can internal liquidity qualify?

Can external liquidity qualify?

Can the protected swing itself become the LRL?

Directional eligibility

In bullish structure, are we selecting BSL?

In bearish structure, LSL?

What happens during TRANSITION?

External vs internal priority
You already proposed:

External > Internal

We need to turn that into an exact algorithm.

Distance
If multiple eligible external pools exist:

nearest?

farthest?

structurally significant?

first opposing liquidity?

This needs to become mechanical.

Liquidity hierarchy
If we have:

Equal High

Structural High

Previous Day High

Previous Week High

which one wins if several are available?

Pools at approximately the same price
How are overlapping/equivalent pools ranked or consolidated?

Liquidity inside vs outside the dealing range
We need a precise positional definition relative to the active range.

Already-consumed liquidity
Confirm:

CONSUMED = ineligible

Liquidity behind current price
Should it ever qualify as the directional LRL?

LRL persistence
Once selected, does the LRL remain fixed until:

consumed,

setup invalidated,

BOS,

MSS,

range replacement,

or some other event?

LRL selection vs LRL sweep
These must remain separate:

Liquidity Pool

â†“

Eligible Pool

â†“

LRL Selection

â†“

#### LRL

â†“

Sweep

No-target condition
We need an exact definition of when:

LRL = NONE

One especially important issue

We should not jump directly into #25 FVG/IFVG yet.

#24 is what turns your liquidity engine from:

â€œHere are all the liquidity pools in the marketâ€

into:

â€œThis is the specific liquidity objective relevant to this structural context.â€

That distinction is essential for your reversal model:

LRL selected

â†“

LRL swept

â†“

Qualifying displacement

â†“

Protected swing violated

â†“

#### MSS

â†“

5M / 1M confirmation

â†“

#### FVG / IFVG

â†“

OTE confluence

So #24 â€” Exact Mechanical LRL / Target Selection is what I would lock next.

And I would keep the same standard we've used for #19â€“#23: no visual importance, no â€œlooks significant,â€ no discretionary target selection, and no hidden assumptions. Every LRL decision should be reconstructable from the state and events available to the engine.

Yes. #24 should now turn the liquidity inventory into one deterministic target/reference. The key is that LRL selection must be context-dependent but not discretionary.
There is one important distinction I would lock before the algorithm:
LRL selection is not determined solely by whether the current structure is bullish or bearish. It is determined by the role of the liquidity in the active setup.

That matters because your continuation and reversal models use liquidity differently.
Continuation â†’ target liquidity in the direction of the trade.
Reversal â†’ liquidity on the opposing side that is swept before MSS.
With that distinction, #24 can be completely mechanical.
#24 â€” Exact Mechanical LRL / Target Selection

Definition of LRL

LRL (Liquidity Reference Level) is the single highest-priority eligible liquidity pool selected by the engine for the active setup context.

The engine must return exactly one:
LRL = LiquidityPoolID
or:
LRL = NONE
There is never an ambiguous list of LRLs.
The engine may retain all other liquidity pools as secondary/historical candidates, but only one is the active LRL.
2. LRL selection happens after liquidity identification

The sequence is:
Mechanical Swings
â†“
Structural Classification
â†“
Active Dealing Range
â†“
Liquidity Pools
â†“
Eligibility Filter
â†“
Directional / Setup Filter
â†“
External/Internal Priority
â†“
Distance / Structural Ranking
â†“
ONE LRL
Importantly:
Liquidity Pool â‰  LRL
A market can have 15 liquidity pools while having:
LRL = Pool #7
3. First filter: consumed liquidity

A liquidity pool is immediately ineligible if:
state âˆˆ {SWEPT, BROKEN, CONSUMED}
Therefore:
ACTIVE = eligible
CONSUMED = ineligible
Historical liquidity remains recorded but cannot become the active LRL.
4. Second filter: liquidity must be ahead of price

A directional LRL must be ahead of current price in the direction relevant to the setup.
For BSL:
LiquidityLevel > CurrentPrice
For LSL:
LiquidityLevel < CurrentPrice
A liquidity pool behind price cannot become the directional LRL.
This prevents the engine from selecting an already-passed liquidity objective.
5. Third filter: setup role

This is the most important rule.
The engine has two relevant LRL roles.
Continuation LRL
For a bullish continuation:
Bullish structure
â†“
BSL target
For a bearish continuation:
Bearish structure
â†“
LSL target
Therefore:
Setup Eligible LRL side
Bullish continuation BSL
Bearish continuation LSL

Reversal LRL
For a reversal, the LRL is the liquidity that must be swept before the reversal MSS.
Therefore:
Bearish â†’ Bullish reversal
Existing structure:
BEARISH
The reversal requires upside liquidity:
BSL
So:
Bearish structure
â†“
BSL LRL
â†“
BSL sweep
â†“
Bullish MSS
Bullish â†’ Bearish reversal
Existing structure:
BULLISH
The reversal requires downside liquidity:
LSL
So:
Bullish structure
â†“
LSL LRL
â†“
LSL sweep
â†“
Bearish MSS
Thus:
Continuation targets same-direction liquidity; reversal setups reference opposing-side liquidity.

This is now locked.
6. Protected swing as LRL

A protected swing does not automatically become the LRL.
However, it can become the LRL if it independently satisfies the liquidity eligibility rules.
For example:
Protected High = 5000
If it is a qualifying liquidity reference:
Protected High
â†“
BSL
â†“
eligible candidate
then it may be selected.
But:
Protected High
alone does not automatically mean:
LRL = Protected High
This keeps structural protection and liquidity selection separate.
7. Internal vs external liquidity

We now need a precise positional definition.
Given active dealing range:
Range High
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â”‚ â”‚
â”‚ INTERNAL â”‚
â”‚ LIQUIDITY â”‚
â”‚ â”‚
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Range Low
A liquidity pool is:
Internal
if its liquidity level lies strictly inside the active dealing range:
RangeLow < LiquidityLevel < RangeHigh
External
if its liquidity level lies outside the active dealing range:
LiquidityLevel > RangeHigh
or:
LiquidityLevel < RangeLow
A level exactly equal to a range boundary is classified as external structural boundary liquidity, because the boundary itself defines the range.
8. External liquidity has priority

The selection hierarchy begins:
EXTERNAL
â†“
INTERNAL
Therefore, if there is at least one eligible external candidate, internal liquidity is ignored for LRL selection.
Only if:
EligibleExternalCandidates = 0
does the engine consider internal liquidity.
This is a hard priority, not a preference.
9. Why external comes first

Because the system should not select a minor internal pool when a meaningful external objective exists.
Example:
Current Price = 5000

Internal BSL = 5010
External BSL = 5050
For bullish continuation:
LRL = 5050
not:
LRL = 5010
10. What if there are multiple external pools?

Now we need the exact ranking.
I recommend this hierarchy:

Setup-direction eligibility

Unconsumed

Ahead of current price

External over internal

Nearest qualifying liquidity

Structural/reference priority

Older pool creation time

Stable ID tie-breaker

The important point is:
Among equally eligible external liquidity pools, the nearest one wins.

This makes the engine deterministic and aligns with the idea of the first opposing liquidity objective being encountered.
11. Distance calculation

Distance is absolute price distance:
Distance = abs(LiquidityLevel - CurrentPrice)
For bullish continuation:
Distance = LiquidityLevel - CurrentPrice
because:
LiquidityLevel > CurrentPrice
For bearish continuation:
Distance = CurrentPrice - LiquidityLevel
For reversal, the same directional distance applies to the opposing liquidity.
12. Example â€” multiple BSL pools

Suppose:
Current Price = 5000

BSL A = 5010
BSL B = 5030
BSL C = 5060
All are:
ACTIVE
EXTERNAL
AHEAD OF PRICE
Then:
LRL = BSL A = 5010
The engine does not select 5060 simply because it is "more significant."
Nearest wins.
13. Liquidity hierarchy

You specifically asked:
Equal High vs Structural High vs Previous Day High vs Previous Week High â€” which wins?

The answer should not be based on label alone.
The engine first determines whether each candidate is eligible and external/internal.
Then distance determines the winner.
Therefore:
Previous Week High
does not automatically beat:
Equal High
simply because it is a previous-week high.
Likewise:
Equal High
does not automatically beat a structural high.
The hierarchy is based on objective location and eligibility, not discretionary importance.
14. But structural significance is retained

Although structural significance does not override a nearer valid candidate, it becomes the tie-breaker.
For candidates at effectively the same price:
Equal High
Structural High
Previous Day High
the engine uses reference priority.
I recommend:
Previous Week High/Low
â†“
Previous Day High/Low
â†“
Session High/Low
â†“
External Structural Swing
â†“
Equal High/Low
â†“
Internal Structural Swing
This is only used after price location/distance has tied.
It does not allow a farther liquidity pool to beat a nearer one.
15. Pools at approximately the same price

Because #23 already consolidated equal-price components into a pool, genuinely overlapping liquidity should normally already be one object.
Therefore:
BSL Pool A = 5000.00
BSL Pool B = 5000.25
with a one-tick equality tolerance should have already been consolidated if their qualifying components belong to the same pool.
So #24 does not create a second liquidity consolidation mechanism.
16. What if two distinct pools still have the same level?

Then they remain distinct objects because their formation histories differ.
If:
Pool A = 5000
Pool B = 5000
and both are eligible, use:
ReferencePriority
as the first tie-breaker.
If still tied:
Earlier confirmation_time
wins.
If still somehow identical:
lowest deterministic pool ID
wins.
This eliminates discretionary selection.
17. Liquidity inside vs outside range

Suppose:
Range High = 5100
Range Low = 4900
Current = 5000
and BSL candidates are:
5020 â†’ internal
5070 â†’ internal
5120 â†’ external
For bullish continuation:
LRL = 5120
because external liquidity has absolute priority.
18. What if there is no external liquidity?

Then the engine falls back:
External candidates = 0
â†“
Internal candidates
â†“
nearest eligible internal pool
â†“
LRL
Therefore:
No external liquidity
does not automatically mean:
LRL = NONE
Internal liquidity can still qualify.
19. What happens during TRANSITION?

This needs to be strict.
During structural transition after MSS:
The old directional LRL is terminated with the old structural range.

The engine must not continue carrying the previous regime's LRL forward as though nothing changed.
Therefore:
MSS
â†“
old range terminated
â†“
old LRL terminated
â†“
TRANSITION
â†“
new structural range established
â†“
new LRL selection
There is no active directional LRL inherited from the terminated regime.
20. LRL persistence

Once selected:
LRL = Pool X
it remains fixed.
It does not continuously reselect every candle.
It remains active until one of the following occurs:

LRL is consumed

LRL
â†“
SWEPT or BROKEN
â†“
LRL terminated
2. Setup invalidates

Setup invalidated
â†“
LRL terminated
3. Structural regime changes

MSS
â†“
LRL terminated
4. Active dealing range is replaced

Range replacement
â†“
LRL reevaluated
This prevents the target from moving around while a trade is developing.
21. Important distinction: LRL does not automatically reselect

Suppose:
LRL = 5050
and a new BSL appears at:
5025
The engine does not automatically change:
5050 â†’ 5025
The existing LRL remains 5050 until its lifecycle ends.
This is essential for backtesting consistency.
22. LRL selection vs sweep

These are separate state transitions:
Liquidity Pool
â†“
Eligible
â†“
LRL Selected
â†“
LRL Active
â†“
Sweep
â†“
LRL Consumed
A pool does not become an LRL because it was swept.
It must be selected before the sweep.
23. Reversal-specific LRL

For your Reversal Entry #1:
Existing bearish structure
Bearish Structure
â†“
candidate BSL pools
â†“
select LRL
â†“
LRL swept
â†“
bullish displacement
â†“
protected high broken
â†“
bullish MSS
Existing bullish structure
Bullish Structure
â†“
candidate LSL pools
â†“
select LRL
â†“
LRL swept
â†“
bearish displacement
â†“
protected low broken
â†“
bearish MSS
This makes the reversal sequence fully mechanical.
24. Continuation-specific LRL

For bullish continuation:
Bullish regime
â†“
BSL candidates
â†“
external first
â†“
nearest external
â†“
LRL
For bearish continuation:
Bearish regime
â†“
LSL candidates
â†“
external first
â†“
nearest external
â†“
LRL
The LRL is therefore the first qualifying directional liquidity objective.
25. LRL and 2R requirement

This is important for your risk engine.
The LRL is selected before the 2R test.
Therefore:
Entry
â†“
LRL selected
â†“
Distance to LRL calculated
â†“
Risk distance calculated
â†“
Potential R multiple calculated
If:
PotentialReward < 2R
then:
Setup = REJECTED
The engine does not move to the next farther liquidity pool simply to manufacture a 2R trade.
This is critical.
26. No-target condition

The engine returns:
LRL = NONE
when no liquidity pool satisfies every mandatory eligibility condition.
Specifically:
No ACTIVE pool
OR
no pool on required side of price
OR
no qualifying directional pool
OR
all candidates are consumed
Then:
LRL = NONE
and any setup requiring an LRL is invalid.
27. Does historical liquidity qualify?

No.
Historical liquidity remains useful for analysis but cannot become an active LRL if:
state != ACTIVE
So:
Historical = recorded
Active = selectable
Consumed = not selectable
28. Exact selection algorithm

The engine can now execute:
FUNCTION SelectLRL(context):

candidates = all liquidity pools

REMOVE pools where state != ACTIVE

DETERMINE required liquidity side:

IF setup = bullish continuation:

required_side = BSL

IF setup = bearish continuation:

required_side = LSL

IF setup = bearish â†’ bullish reversal:

required_side = BSL

IF setup = bullish â†’ bearish reversal:

required_side = LSL

REMOVE pools where side != required_side

REMOVE pools that are behind current price

CLASSIFY remaining pools:

#### INTERNAL

#### EXTERNAL

IF external candidates exist:

candidates = external candidates

#### ELSE:

candidates = internal candidates

IF candidates = empty:

RETURN LRL = NONE

CALCULATE distance from current price

SELECT nearest candidate

IF multiple candidates have equal distance:

SELECT highest reference priority

IF still tied:

SELECT earliest confirmation time

IF still tied:

SELECT deterministic pool ID

RETURN selected pool as LRL

That is the actual mechanical rule.
29. Reference priority tie-breaker

Locked as:

Previous Week High/Low

Previous Day High/Low

Session High/Low

External Structural Swing

Equal High/Low Pool

Internal Structural Swing

Again:
This hierarchy only resolves ties.

It does not allow a farther weekly high to beat a nearer external structural high.
30. Final LRL state machine

LIQUIDITY POOL
â”‚
â–¼
ELIGIBLE?
/ 
NO YES
â”‚ â”‚
â”‚ â–¼
â”‚ LRL CANDIDATE
â”‚ â”‚
â”‚ â–¼
â”‚ SELECTION
â”‚ â”‚
â”‚ â–¼
â”‚ ACTIVE LRL
â”‚ â”‚
â”‚ â”Œâ”€â”€â”€â”€â”´â”€â”€â”€â”€â”
â”‚ â”‚ â”‚
â”‚ â–¼ â–¼
â”‚ SWEPT BROKEN
â”‚ â”‚ â”‚
â”‚ â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”˜
â”‚ â–¼
â”‚ CONSUMED
â”‚
â–¼
NOT SELECTABLE
31. Final locked definition

LRL is the single active liquidity pool selected from all unconsumed liquidity according to the current setup's required liquidity side, current price position, active dealing range, and deterministic liquidity priority rules.

Candidate requirements
A candidate must:
Be an ACTIVE liquidity pool.
Be on the required side of current price.
Match the setup's required liquidity side.
Be associated with the active structural context.
Not already be consumed/broken/swept.
Direction
Bullish continuation â†’ BSL
Bearish continuation â†’ LSL

Bearish â†’ bullish reversal â†’ BSL
Bullish â†’ bearish reversal â†’ LSL
Range priority
External > Internal
Distance
Within the selected class:
Nearest qualifying liquidity wins.
Tie-break
Previous Week

Previous Day

Session

External Structural Swing

Equal High/Low

Internal Structural Swing
Then:
Earlier confirmation time

Deterministic ID
Persistence
Once selected:
LRL remains fixed
until:
consumed,
setup invalidated,
MSS/regime change,
or active dealing range replacement.
No target
No qualifying ACTIVE candidate
â†“
LRL = NONE
The dependency chain is now clean
#19 Mechanical Swings
â†“
#20 Structural Classification
â†“
#21 Dealing Range
â†“
#22 OTE
â†“
#23 Liquidity Pools / Sweeps
â†“
#24 LRL Selection
â†“
ONE LRL
â†“
#25 FVG / IFVG Interaction
â†“
#26 Setup Qualification
And the most important distinction is now locked:
#23 answers:
"What liquidity exists?"

#24 answers:
"Which ONE liquidity objective matters
for THIS setup?"

#25 will answer:
"How does FVG / IFVG interact
with that objective and entry model?"
That separation is what keeps the eventual engine from becoming discretionary.

Show more

Yes. #24 is now sufficiently defined to lock.

The architecture is now:

#19 Mechanical Swing Selection

â†“

#20 Structural Swing Classification

â†“

#21 Structural / Dealing Range

â†“

#22 OTE

â†“

#23 Liquidity Pools / Sweeps

â†“

#24 LRL Selection

â†“

#### ONE LRL

â†“

#25 FVG / IFVG Interaction

â†“

#26 Setup Qualification

The critical separation is:

#23: What liquidity exists?

#24: Which one liquidity objective is relevant to this setup?

#25: How does FVG/IFVG interact with the setup?

#24 locked rules

Continuation

Bullish â†’ BSL

Bearish â†’ LSL

Reversal

Bearish â†’ bullish â†’ BSL

Bullish â†’ bearish â†’ LSL

Eligibility

Pool must be ACTIVE

Must be on the required side of current price

Must match the setup role

Consumed/broken/swept pools are excluded

Location priority

#### EXTERNAL

>

#### INTERNAL

Within the selected class

Nearest qualifying liquidity

â†“

Reference-priority tie-break

â†“

Earlier confirmation time

â†“

Deterministic ID

Persistence
Once selected, the LRL does not move simply because a closer pool appears. It remains fixed until its defined termination event.

No target

No eligible candidate

â†“

LRL = NONE

And importantly:

LRL selection

â‰ 

LRL sweep

â‰ 

#### BOS

â‰ 

#### MSS

That gives us a deterministic target engine rather than a discretionary liquidity map.

What I need next

#25 â€” Exact Mechanical FVG / IFVG Interaction

This is the logical next primitive.

But I would not immediately define â€œconfluenceâ€ broadly. We should first lock the actual mechanics of:

FVG creation

Bullish vs bearish FVG

Exact three-candle geometry

FVG boundaries

FVG qualification

FVG lifecycle

FVG mitigation

FVG invalidation

IFVG creation

IFVG conversion

IFVG direction

FVG/IFVG interaction with OTE

FVG/IFVG interaction with LRL

Whether a single candle can create and/or convert an FVG

Timeframe ownership and lower-timeframe interaction

Historical immutability

Exact state machine

The dependency should become:

#21 Active Dealing Range

â†“

#22 OTE

â†“

#23 Liquidity

â†“

#24 LRL

â†“

#25 FVG / IFVG

â†“

#26 Confluence

â†“

#27 Setup Qualification

So the next thing to lock is #25 â€” Exact Mechanical FVG / IFVG Definition.

Yes. #25 should be the complete mechanical FVG/IFVG object model, before we define broad confluence in #26.
The important architectural rule is:
FVG/IFVG geometry and lifecycle are independent primitives. OTE, LRL, BOS, MSS, and setup logic may reference them, but none of those concepts changes what an FVG/IFVG is.

#25 â€” Exact Mechanical FVG / IFVG Definition

FVG is a three-candle imbalance

Every FVG is created from exactly three consecutive candles on the same originating timeframe:
Candle 1 â†’ Candle 2 â†’ Candle 3
The middle candle is Candle 2.
The FVG is determined exclusively by the relationship between Candle 1 and Candle 3.
Candle 2 does not define the boundaries.
2. Bullish FVG

A bullish FVG exists when:
Low(Candle 3) > High(Candle 1)
The zone is:
Upper Boundary = Low(Candle 3)

Lower Boundary = High(Candle 1)
Therefore:
Bullish FVG
[High(C1), Low(C3)]
Example:
C1 High = 100.00
C3 Low = 101.00

Bullish FVG = 100.00 â†’ 101.00
There is a genuine untraded price interval between the two extremes.
3. Bearish FVG

A bearish FVG exists when:
High(Candle 3) < Low(Candle 1)
The zone is:
Upper Boundary = Low(Candle 1)

Lower Boundary = High(Candle 3)
Therefore:
Bearish FVG
[High(C3), Low(C1)]
Example:
C1 Low = 100.00
C3 High = 99.00

Bearish FVG = 99.00 â†’ 100.00
4. Equality does NOT create an FVG

This is important.
Bullish:
Low(C3) > High(C1)
not:
Low(C3) >= High(C1)
Bearish:
High(C3) < Low(C1)
not:
High(C3) <= Low(C1)
Therefore:
High(C1) = Low(C3)
means:
NO FVG
There is zero gap.
5. Minimum FVG size

The minimum valid FVG is one minimum price increment/tick.
Define:
GapSize = Bullish: Low(C3) - High(C1)
GapSize = Bearish: Low(C1) - High(C3)
Qualification requires:
GapSize >= MinimumTick
Because prices are represented at instrument tick precision, this prevents a zero-width or numerically meaningless gap.
No arbitrary percentage or ATR minimum is introduced here.
6. Candle size does not determine FVG existence

An FVG does not require a large Candle 2 merely to exist.
Therefore:
Large C2 + valid geometry â†’ FVG
Small C2 + valid geometry â†’ FVG
However, this does not mean every FVG is equally meaningful.
The separate displacement qualification can later classify the FVG as being created by qualifying displacement.
Thus:
FVG existence
â‰ 
Displacement qualification
This preserves the architecture we established.
7. Does an FVG require displacement?

No for creation.
The geometric FVG exists whenever the three-candle relationship satisfies the exact rule.
So:
Valid geometry
â†“
FVG = TRUE
independently of:
QualifyingDisplacement
However, a particular setup may require:
FVG + QualifyingDisplacement
That is a setup qualification rule, not an FVG-definition rule.
8. FVG creation timestamp

The FVG does not exist until Candle 3 closes.
Therefore:
C1
â†“
C2
â†“
C3 closes
â†“
FVG confirmed
Creation/confirmation time:
FVG.confirmation_time = Candle3.close_time
This prevents look-ahead bias.
The engine cannot use the FVG during the unfinished Candle 3.
9. FVG object

The engine should create an immutable historical object:
FVG {
id
timeframe
direction
candle1_id
candle2_id
candle3_id

lower_boundary

upper_boundary

gap_size

creation_time

confirmation_time

displacement_qualified

state

mitigation_status

conversion_status

}
The original geometry never changes.
10. FVG boundaries

The boundaries are always the two Candle-1/Candle-3 extremes.
Bullish
lower = High(C1)
upper = Low(C3)
Bearish
lower = High(C3)
upper = Low(C1)
The boundaries never move.
If price later partially fills the FVG, the original zone remains historically recorded.
11. FVG touch

A touch occurs whenever traded price enters or reaches the zone.
Mechanically:
Price intersects [LowerBoundary, UpperBoundary]
A wick is sufficient.
A candle body is not required.
Therefore:
Wick enters FVG â†’ TOUCH
Body enters FVG â†’ TOUCH
Trade occurs inside FVG â†’ TOUCH
12. Partial mitigation

Partial mitigation occurs when price enters the FVG but does not reach the opposite boundary.
For a bullish FVG:
Upper
â”‚
â”‚
price enters
â†“
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â”‚
â”‚
Lower
For a bearish FVG, the geometry is reversed directionally but the principle is identical.
The FVG remains active after partial mitigation.
There is no arbitrary 50% mitigation threshold.
This is important because the engine should record the actual deepest penetration rather than inventing a special percentage.
13. Full mitigation

An FVG is fully mitigated when price reaches the opposite boundary from the entry side.
Example bullish FVG:
101.00 â”€ Upper
â”‚
â”‚
â”‚
100.00 â”€ Lower
If price enters from above and reaches:
100.00
the FVG is fully mitigated.
Similarly, if a bearish FVG is entered from below and price reaches its opposite boundary, it is fully mitigated.
Thus:
Full mitigation is determined by price reaching the far boundary, not by a candle close.

A wick reaching that boundary is sufficient for mitigation.
14. Wick through the entire FVG

A wick that traverses the entire FVG:
enters zone
â†“
crosses entire zone
â†“
reaches opposite boundary
means:
FULLY MITIGATED
It does not automatically mean IFVG.
That distinction is critical.
15. Candle close through the FVG

A body close through the entire zone is stronger than ordinary mitigation, but it still only becomes an IFVG when the IFVG conversion conditions are satisfied.
Therefore:
Close through zone
â‰  automatically IFVG
The conversion requires the exact rule below.
16. IFVG conversion

An FVG becomes an IFVG when its directional premise is mechanically violated by a qualifying opposing move.
Bullish FVG â†’ Bearish IFVG
A bullish FVG:
[High(C1), Low(C3)]
converts when:
Price closes below the lower boundary.
The violating move has qualifying opposing displacement.
Therefore:
Close < BullishFVG.LowerBoundary
+
Bearish QualifyingDisplacement

Bearish IFVG
A wick below the boundary alone is insufficient.
Bearish FVG â†’ Bullish IFVG
A bearish FVG:
[High(C3), Low(C1)]
converts when:
Price closes above the upper boundary.
The violating move has qualifying bullish displacement.
Therefore:
Close > BearishFVG.UpperBoundary
+
Bullish QualifyingDisplacement

Bullish IFVG
17. IFVG does NOT require BOS or MSS

This is an important separation.
IFVG conversion requires:
Opposing body close
+
Qualifying displacement
It does not require:
BOS
or:
MSS
Therefore an IFVG can exist entirely independently of structural change.
That prevents the FVG engine from becoming dependent on the structural engine.
18. IFVG inherits the original zone

When conversion occurs, the IFVG uses the same boundaries as the original FVG.
Example:
Original bullish FVG:

100 â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤ 101
Price closes below 100 with qualifying bearish displacement.
The resulting bearish IFVG remains:
100 â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤ 101
The geometry does not move.
Only:
direction
and:
state
change.
19. Direction after conversion

Bullish FVG
â†“
Bearish violation
â†“
Bearish IFVG
and:
Bearish FVG
â†“
Bullish violation
â†“
Bullish IFVG
Therefore the IFVG direction is always opposite the original FVG direction.
20. Can an FVG flip multiple times?

No.
This is a major state-machine rule.
An original FVG has at most one directional conversion:
BULLISH FVG
â†“
BEARISH IFVG
or:
BEARISH FVG
â†“
BULLISH IFVG
Once converted:
IFVG = terminal directional conversion
It cannot subsequently flip back into the original FVG direction.
This prevents pathological repeated flipping during choppy price action.
21. What happens after IFVG conversion?

The original FVG remains in historical records, but its active identity becomes the IFVG.
Conceptually:
Original FVG
â”‚
â”œâ”€â”€ historical geometry preserved
â”‚
â””â”€â”€ active state â†’ IFVG
The engine should never delete the original object.
22. Touch and rejection

Suppose bullish FVG:
Price
â†“
enters zone
â†“
rejects
â†“
moves higher
Result:
FVG = still bullish
No conversion occurs.
A touch is merely a touch.
A rejection does not create an IFVG.
23. Partial mitigation followed by reversal

Example:
Bullish FVG
â†“
price enters 30%
â†“
rejects
â†“
moves higher
State:
PARTIALLY_MITIGATED
and remains a bullish FVG.
Partial mitigation does not weaken the object's mathematical identity.
24. Fully mitigated FVG and IFVG

A fully mitigated FVG can still become an IFVG if it subsequently satisfies the conversion rule.
Example:
Bullish FVG
â†“
fully mitigated
â†“
later bearish qualifying displacement
â†“
body closes below lower boundary
â†“
Bearish IFVG
So:
Fully mitigated â‰  permanently incapable of conversion
unless the FVG has already reached its terminal lifecycle state for another reason.
25. What if price completely traverses the FVG without qualifying displacement?

Then:
FVG = FULLY MITIGATED
but:
IFVG = FALSE
There is no automatic flip.
This is another important separation:
Mitigation
â‰ 
Invalidation
â‰ 
IFVG conversion
26. Can one candle create an FVG and convert another?

Yes.
A single candle can participate in multiple independent events.
For example, Candle 3 can:
create a new bullish FVG
while the same candle's movement can:
close through an older bearish FVG
+
qualifying bullish displacement
causing:
older bearish FVG â†’ bullish IFVG
Events are evaluated independently.
27. Can one candle create and convert the same FVG?

No.
A three-candle FVG only becomes known when Candle 3 closes.
That same Candle 3 cannot retroactively violate the FVG that it has just created because the FVG did not exist before Candle 3 closed.
Therefore:
New FVG
and:
conversion of pre-existing FVG
are separate objects/events.
28. Multiple FVGs created by one displacement leg

A single displacement leg can create multiple FVGs.
The engine must preserve every valid FVG.
Example:
Displacement leg
â†“
FVG #1
FVG #2
FVG #3
No FVG is automatically discarded merely because another FVG was created later.
Their lifecycles remain independent.
29. Overlapping FVGs

Overlapping FVGs remain separate objects if they were generated by separate three-candle structures.
For example:
FVG A: 100â€“102
FVG B: 101â€“103
They overlap, but:
FVG A â‰  FVG B
Each retains:
its own candles,
timestamp,
timeframe,
boundaries,
mitigation state,
conversion state.
The confluence layer can later recognize their overlap.
30. Nested FVGs

Same rule.
A smaller FVG inside a larger FVG remains a distinct object.
Large FVG
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Small FVG â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
Neither replaces the other.
31. FVG + OTE

The FVG engine does not determine whether an FVG is in OTE.
That belongs to #26 Confluence.
The mathematical test will be:
FVG âˆ© OTE â‰  âˆ…
If there is any positive overlap:
OTE_CONFLUENCE = TRUE
This follows the rule we previously locked.
32. FVG + LRL

Likewise, the FVG engine does not decide whether an FVG is relevant to the LRL.
The LRL remains a liquidity object.
The confluence layer can later ask questions such as:
Is the FVG located before the LRL?
Is the FVG overlapping an entry region?
Is the FVG associated with the displacement toward/away from LRL?
But #25 itself does not alter LRL selection.
33. Timeframe ownership

Every FVG has an originating timeframe:
FVG.timeframe = 15M / 5M / 1M / etc.
A lower timeframe can interact with a higher-timeframe FVG.
For example:
5M FVG
â†‘
1M price trades into it
That is a legitimate price interaction.
However:
A lower timeframe cannot create, redefine, or structurally replace the higher-timeframe FVG.

The 5M FVG remains a 5M object.
34. Timeframe isolation

A:
1M FVG
cannot become:
5M FVG
and a:
5M IFVG
cannot become:
15M IFVG
Every timeframe owns its own FVG state.
Therefore:
15M FVG engine
5M FVG engine
1M FVG engine
operate independently.
Cross-timeframe interaction occurs only through the confluence/setup layers.
35. Lower-timeframe interaction with higher-timeframe FVG

Lower timeframe data may provide more granular evidence of:
touch,
penetration,
mitigation,
eventual violation.
But the higher-timeframe object retains its originating identity.
Thus:
5M FVG
â†“
1M price enters
â†“
5M FVG interaction recorded
does not turn the event into:
1M FVG
36. FVG state machine

The cleanest state machine is:
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ CREATED â”‚
â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
â”‚
â–¼
ACTIVE
â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ â”‚
â–¼ â–¼
PARTIALLY MITIGATED FULLY MITIGATED
â”‚ â”‚
â”‚ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â”‚
â–¼
OPPOSING CLOSE +
QUALIFYING DISPLACEMENT
â”‚
â–¼
IFVG
â”‚
â–¼
TERMINAL
But there is an important distinction:
FULLY MITIGATED
does not itself mean:
TERMINAL
because it can still subsequently satisfy IFVG conversion.
37. More precise state model

I would implement the state as:
direction:
BULLISH
BEARISH

lifecycle:
ACTIVE
PARTIALLY_MITIGATED
FULLY_MITIGATED
CONVERTED_IFVG
and separately:
conversion_direction:
NONE
BULLISH
BEARISH
This avoids mixing "how much has price interacted with the zone" with "what directional object the zone has become."
38. Exact bullish FVG algorithm

FOR each confirmed Candle3:

C1 = candle[i-2]

C2 = candle[i-1]

C3 = candle[i]

IF Low(C3) > High(C1):

gap_size = Low(C3) - High(C1)

IF gap_size >= minimum_tick:

#### CREATE FVG

direction = BULLISH

lower = High(C1)

upper = Low(C3)

timeframe = originating timeframe

creation_time = C3 close

state = ACTIVE

C2 participates in the three-candle sequence but does not define the gap boundaries.
39. Exact bearish FVG algorithm

FOR each confirmed Candle3:

C1 = candle[i-2]

C2 = candle[i-1]

C3 = candle[i]

IF High(C3) < Low(C1):

gap_size = Low(C1) - High(C3)

IF gap_size >= minimum_tick:

#### CREATE FVG

direction = BEARISH

lower = High(C3)

upper = Low(C1)

timeframe = originating timeframe

creation_time = C3 close

state = ACTIVE

Exact IFVG conversion algorithm

Bullish â†’ Bearish
IF FVG.direction == BULLISH
AND Close(current_candle) < FVG.lower_boundary
AND current_move qualifies as bearish displacement:

CONVERT FVG â†’ BEARISH IFVG

Bearish â†’ Bullish
IF FVG.direction == BEARISH
AND Close(current_candle) > FVG.upper_boundary
AND current_move qualifies as bullish displacement:

CONVERT FVG â†’ BULLISH IFVG

No wick-only conversion.
No BOS requirement.
No MSS requirement.
No second flip.
41. What displacement does in #25

We deliberately do not redefine displacement here.
#16 already establishes the concept of:
QualifyingDisplacement
Therefore #25 simply references it:
QualifyingDisplacement = TRUE
The exact displacement mechanics remain owned by #16.
This avoids two different definitions of displacement.
42. Historical immutability

Nothing gets deleted.
If an FVG:
ACTIVE
becomes:
PARTIALLY_MITIGATED
the historical object remains.
If it becomes:
FULLY_MITIGATED
it remains.
If it becomes:
BEARISH IFVG
the original bullish FVG geometry remains permanently recorded.
So:
Historical FVG objects are immutable records; lifecycle state is what changes.

Final locked definition

FVG
A Fair Value Gap is a three-consecutive-candle price imbalance where Candle 3 fails to overlap the relevant extreme of Candle 1, producing a minimum one-tick price interval between Candle 1 and Candle 3.

Bullish
Low(C3) > High(C1)
Zone:
[High(C1), Low(C3)]
Bearish
High(C3) < Low(C1)
Zone:
[High(C3), Low(C1)]
FVG existence
Geometry only
Displacement is not required for existence.
Mitigation
Touch/penetration â†’ partial interaction
Far boundary reached â†’ fully mitigated
Wick penetration counts.
IFVG
Original FVG
+
opposite-side candle BODY CLOSE beyond far boundary
+
qualifying opposing displacement

IFVG
IFVG direction
Bullish FVG â†’ Bearish IFVG
Bearish FVG â†’ Bullish IFVG
IFVG geometry
Original FVG boundaries are retained.
Reversal
One FVG can convert only once.
Timeframes
FVGs are timeframe-owned and isolated.
Lower timeframes can interact with higher-timeframe FVGs but cannot redefine their identity.
OTE
Handled later through:
OTE âˆ© FVG â‰  âˆ…
or:
OTE âˆ© IFVG â‰  âˆ…
LRL
LRL remains an independent liquidity object. FVG/IFVG does not alter LRL selection.
The architecture is now
#21 Active Dealing Range
â†“
#22 OTE
â†“
#23 Liquidity Pools / Sweeps
â†“
#24 LRL Selection
â†“
#25 FVG / IFVG
â†“
#26 Confluence
â†“
#27 Setup Qualification

Show more

Yes. #25 is now sufficiently locked.

Yes. #29.6 should be strictly a lifecycle/state-management primitive. It should not re-evaluate setup logic, execution logic, or exit causality.
#29.6 â€” Exact Mechanical Position Lifecycle Definition

Ownership

The ownership boundary is:
#29.1 â†’ Entry execution
#29.2 â†’ Position quantity
#29.3 â†’ Protective orders
#29.4 â†’ Exit resolution
#29.5 â†’ Execution costs
#29.6 â†’ Position lifecycle
#29.7 â†’ P&L / account accounting
Therefore:
#29.6 determines whether a position exists, what lifecycle state it is in, and when that lifecycle terminates. It does not determine why the position entered or exited.

Position creation

A Position is created only after the entry order has been mechanically confirmed as filled.
The sequence is:
SETUP QUALIFIED
â†“
ENTRY ORDER ACTIVE
â†“
ENTRY FILL CONFIRMED
â†“
POSITION CREATED
â†“
POSITION = OPEN
There is no position object while the entry order is merely:
PENDING
ACTIVE
UNFILLED
CANCELLED
Therefore:
EntryZone touched
â‰ 
Position exists

EntryOrder created
â‰ 
Position exists

EntryOrder triggered
â‰ 
Position exists

EntryOrder filled

Position exists
3. Required position inputs

When the fill occurs, #29.6 receives the already-resolved information from upstream.
Minimum required fields:
Position {
id

setup_id

direction

quantity

entry_order_id

entry_price

opened_time

stop_order_id

stop_price

target_order_id

target_price

entry_execution_id

state

}
#29.6 does not recalculate:
entry price
quantity
stop
target
slippage
commission
exit price
Those belong upstream.
4. Position states

I recommend the strict three-state model:
NOT_OPEN
â†“
OPEN
â†“
CLOSED
There is no CLOSING state in the base architecture.
Why?
Because #29.4 already resolves the exit event mechanically.
Once #29.4 determines:
EXIT_EVENT_DETECTED
â†“
EXIT_ORDER_RESOLVED
the position can transition directly:
OPEN
â†“
CLOSED
A CLOSING state would introduce an unnecessary intermediate state without representing a distinct trading condition in the base model.
5. NOT_OPEN

NOT_OPEN means:
No live position currently exists for this setup/strategy instance.

This includes both:
BEFORE ENTRY
and:
AFTER POSITION CLOSED
However, for historical clarity, I recommend that NOT_OPEN not be stored as the terminal state of a Position object.
A Position object comes into existence only when it becomes OPEN.
Therefore:
No Position object
â†“
OPEN Position
â†“
CLOSED Position
rather than:
Position
state = NOT_OPEN
This makes the lifecycle cleaner.
6. OPEN

A position enters OPEN only when:
ENTRY_FILL_CONFIRMED = TRUE
At that moment:
position.opened_time

entry_fill.confirmed_time
and:
position.entry_price

confirmed mechanical fill price
The position is now live.
7. Protective orders

Once the position is open, the position references its protective orders.
Conceptually:
POSITION OPEN
â”‚
â”œâ”€â”€ STOP ORDER
â”‚
â””â”€â”€ TARGET ORDER
#29.6 does not recreate their logic.
It simply maintains the relationship:
position.stop_order_id
position.target_order_id
The actual order definitions originate from #29.3.
The actual exit resolution originates from #29.4.
8. Protective-order activation

The lifecycle transition is:
ENTRY_FILL_CONFIRMED
â†“
POSITION_CREATED
â†“
POSITION_OPEN
â†“
PROTECTIVE_ORDERS_ACTIVE
The important architectural distinction is:
Protective orders are properties of the open position, but #29.6 does not decide their prices or execution behavior.

Those were already determined by #29.3 and #29.4.
9. Position monitoring

While:
position.state = OPEN
the position remains live.
The lifecycle engine waits for the upstream execution engine to produce a resolved exit.
Conceptually:
OPEN
â”‚
â”œâ”€â”€ no exit â†’ remain OPEN
â”‚
â””â”€â”€ exit resolved â†’ CLOSED
#29.6 does not independently scan OHLC data to decide whether SL or TP occurred.
That is #29.4.
10. Exit resolution

When #29.4 produces a terminal exit:
EXIT_RESOLVED = TRUE
#29.6 receives:
exit_price
exit_time
exit_reason
exit_execution_id
and transitions:
OPEN
â†“
CLOSED
The exit reason is preserved but not determined by #29.6.
For example:
STOP_LOSS
TARGET
STOP_LOSS_GAP
OHLC_AMBIGUOUS_STOP_PRIORITY
remain #29.4's responsibility.
11. Closing timestamp

The position's closing timestamp is:
position.closed_time

resolved_exit_time
It cannot be independently generated by #29.6.
Likewise:
position.opened_time

confirmed_entry_fill_time
This prevents lifecycle timestamps from drifting away from actual execution chronology.
12. Position closure

Once #29.4 resolves the exit:
OPEN
â†“
CLOSED
The following become immutable:
entry_price
entry_time
quantity
stop_price
target_price
exit_price
exit_time
exit_reason
No later candle can modify them.
13. OCO relationship after closure

When the position reaches:
CLOSED
there must be:
NO ACTIVE PROTECTIVE ORDERS
The winning order has executed.
The remaining OCO order is cancelled.
Conceptually:
POSITION OPEN
â”‚
OCO ACTIVE
/ 
SL TP
â”‚ â”‚
â†“ â†“
CLOSED CLOSED
â”‚ â”‚
cancel TP cancel SL
#29.6 records the resulting lifecycle state.
#29.4 remains the authority for which order executed.
14. One-position rule

The base strategy permits:
At most one live position at a time.

Therefore:
OPEN_POSITION_COUNT â‰¤ 1
A new entry cannot create another position while:
ExistingPosition.state = OPEN
The attempted new entry must therefore be rejected or remain ineligible according to the setup/order rules.
It must not create a second live position.
15. No pyramiding

The one-position rule also means:
OPEN
â†“
additional qualifying signal
â†“
NO SECOND POSITION
There is no:
Position #1
Position #2
Position #3
simultaneously under the base strategy.
Pyramiding would require a separately defined primitive.
16. No duplicate entry fill

A position can have exactly one entry fill.
Invariant:
EntryFillCount = 1
After the position exists:
another entry fill
cannot be attached to the same position.
17. No duplicate terminal exit

A position can have exactly one terminal exit.
Invariant:
TerminalExitCount = 1
Once:
state = CLOSED
another SL/TP event cannot close it again.
This is especially important for OCO processing.
18. No reopening

A closed position is permanently terminal:
CLOSED
X
â†“
OPEN
is prohibited.
If a new setup subsequently generates a valid trade, it creates a new position object.
19. Setup relationship

The position retains its originating setup:
position.setup_id
This provides the permanent relationship:
Setup
â†“
Entry Order
â†“
Position
â†“
Exit
The position also retains:
entry_order_id
stop_order_id
target_order_id
This allows complete reconstruction of the trade.
20. Setup completion

I recommend that the setup and position remain separate state machines.
Do not make:
POSITION CLOSED
automatically equal:
SETUP COMPLETED
because the two objects have different responsibilities.
Instead:
SETUP STATE
â”‚
â””â”€â”€ setup lifecycle

POSITION STATE
â”‚
â””â”€â”€ position lifecycle
However, for the base one-shot setup model, once the position has been opened and subsequently closed, the originating setup becomes terminal/non-reusable.
So:
SETUP ARMED
â†“
ENTRY FILLED
â†“
POSITION OPEN
â†“
POSITION CLOSED
â†“
SETUP COMPLETED
is the correct relationship for the base strategy.
The important distinction is:
The position closing does not itself determine why the setup completed; it establishes that the setup's single permitted execution lifecycle has ended.

No automatic re-entry

After:
POSITION CLOSED
the original setup cannot produce another entry.
Even if:
Price returns to EQ
or:
FVG remains active
or:
LRL remains unconsumed
or:
the original setup conditions appear again
there is no automatic re-entry.
A new trade requires a new setup instance.
22. Post-close market information

After closure:
new candles
new FVGs
new sweeps
new MSS
new BOS
new liquidity
belong to the subsequent market-analysis process.
They do not mutate the historical position.
23. Position immutability

After:
state = CLOSED
the position becomes immutable.
The engine cannot modify:
entry
quantity
stop
target
exit
timestamps
exit reason
setup association
Historical records therefore remain reproducible.
24. Exact lifecycle state machine

The complete state machine is:
ENTRY FILL
â”‚
â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ OPEN â”‚
â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜
â”‚
#29.4 resolves
terminal exit
â”‚
â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ CLOSED â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â”‚
X
NO REOPENING
There is deliberately no CLOSING state.
25. Exact transition conditions

Transition 1
NO POSITION
â†“
OPEN
requires:
EntryFill.confirmed = TRUE
and:
Quantity > 0
and:
Setup exists
Transition 2
OPEN
â†“
CLOSED
requires:
ExitResolution.confirmed = TRUE
from #29.4.
No other transitions
Invalid:
OPEN â†’ OPEN
is simply continued monitoring.
Invalid:
CLOSED â†’ OPEN
Invalid:
CLOSED â†’ CLOSED
as a new lifecycle transition.
Invalid:
OPEN â†’ NOT_OPEN
without a resolved exit.
26. Position lifecycle invariants

The engine must enforce:

A Position cannot exist without a setup_id.

A Position cannot exist without a confirmed entry fill.

A Position has exactly one entry fill.

A Position has exactly one quantity.

A Position cannot have more than one live instance under the
one-position strategy rule.

An OPEN Position must have its protective-order references.

An OPEN Position cannot exist after #29.4 resolves its exit.

A CLOSED Position has exactly one terminal exit.

A CLOSED Position cannot reopen.

A CLOSED Position cannot have active OCO orders.

#29.6 cannot change the exit reason.

#29.6 cannot change the exit price.

#29.6 cannot change quantity.

#29.6 cannot move SL or TP.

A historical Position is immutable.

A closed Position cannot automatically generate a new entry.

Position object

The final object can therefore be:
Position {
id

setup_id

state

direction

quantity

entry_order_id

entry_execution_id

entry_price

opened_time

stop_order_id

stop_price

target_order_id

target_price

exit_execution_id

exit_price

exit_reason

closed_time

execution_cost_record_id

created_time

closed

}
The key point is that fields such as exit_price and exit_reason are populated from #29.4, not calculated by #29.6.
28. Final locked definition

#29.6 â€” Exact Mechanical Position Lifecycle Definition: A Position object is created only after a valid entry order has received a mechanically confirmed fill. Its lifecycle consists of exactly two persistent states: OPEN and CLOSED; no CLOSING state exists in the base model. Upon confirmed entry, the Position records its originating setup_id, entry order/execution, quantity, entry price, protective-order references, and opening timestamp. While OPEN, the position remains active until #29.4 produces a mechanically resolved terminal exit. #29.6 does not determine the exit cause, exit price, stop, target, slippage, or costs; it consumes those results from the upstream primitives. When #29.4 resolves the exit, the Position transitions directly from OPEN to CLOSED, records the resolved exit information and closing timestamp, and the remaining OCO order is no longer active. A closed Position is immutable and can never reopen, receive another entry fill, receive another terminal exit, or retain an active protective-order pair. The base strategy permits at most one live Position at a time, and a completed Position cannot automatically generate another entry. Any subsequent trade must originate from a new setup instance.**

So the complete execution architecture is now clean:
#27 SETUP
â†“
#28 ENTRY-ZONE SELECTION
â†“
#29.1 ENTRY EXECUTION
â†“
#29.2 POSITION SIZING
â†“
#29.3 PROTECTIVE ORDERS
â†“
#29.4 EXIT RESOLUTION
â†“
#29.5 EXECUTION COSTS
â†“
#29.6 POSITION LIFECYCLE
â†“
#29.7 TRADE / ACCOUNTING

Show more

Exactly. #29.6 is now locked, and the architecture has reached the point where execution ends and accounting begins.

The next definition should therefore be:

#29.7 â€” Exact Mechanical Trade & Account Accounting

This should be the first layer that is allowed to translate the completed execution into financial consequences.

The ownership boundary is:

#27     SETUP QUALIFICATION

â†“

#28     ENTRY-ZONE SELECTION

â†“

#29.1   ENTRY EXECUTION

â†“

#29.2   POSITION SIZING

â†“

#29.3   PROTECTIVE ORDERS

â†“

#29.4   EXIT RESOLUTION

â†“

#29.5   EXECUTION COSTS

â†“

#29.6   POSITION LIFECYCLE

â†“

#29.7   TRADE / ACCOUNTING

â†“

#### ACCOUNT STATE

What #29.7 should own

I would lock the scope as:

#29.7 owns

Gross P&L

Execution-cost deduction

Net P&L

Realized account-equity change

Pre-trade equity â†’ post-trade equity

Realized R

Winning/losing/breakeven classification

Trade-level accounting record

Account-level equity update

Cumulative performance state

#29.7 does NOT own

Setup qualification

Entry-zone selection

Entry price determination

Stop determination

Target determination

Position sizing

Exit selection

SL/TP chronology

Slippage modeling

Commission modeling

Position lifecycle

Those have already been resolved upstream.

The critical distinction

We now have three different financial concepts that should not be collapsed:

#### MECHANICAL EXECUTION

â†“

#29.4

Mechanical Entry / Exit

â†“

#### EXECUTION FRICTION

â†“

#29.5

Economic Entry / Exit + Costs

â†“

#### ACCOUNTING

â†“

#29.7

Gross P&L â†’ Costs â†’ Net P&L â†’ Equity

For example:

Mechanical Entry = 5018

Mechanical Exit  = 5014

Economic Entry   = 5018.25

Economic Exit    = 5013.75

Quantity         = 4

#29.7 should not ask why those prices occurred.

It simply consumes the resolved execution information.

The first thing we should define in #29.7

I recommend that our next exact definition be:

29.7.1 â€” Exact Mechanical P&L Calculation

Before we define account equity, trade classification, expectancy, drawdown, etc., we should lock the primitive that converts:

Economic Entry

Economic Exit

Direction

Quantity

Contract Multiplier

into:

Gross P&L

Then:

Gross P&L

â†“

Total Execution Costs

â†“

Net P&L

And only after that:

Net P&L

â†“

Account Equity Change

This keeps the accounting chain completely deterministic.

So the next definition I would lock down is:

#29.7.1 â€” Exact Mechanical Gross P&L & Net P&L Calculation

That should establish the exact formulas for long vs. short, multiplier, economic execution prices, costs, realized R, and account-equity transition, without introducing performance statistics yet.

After that, we can proceed mechanically through the remaining accounting primitives.

Agreed. #29.7.1 should be the exact accounting primitive that converts a completed economic execution into a deterministic financial result. It should not introduce expectancy, drawdown, win rate, or other performance statistics yet.
#29.7.1 â€” Exact Mechanical Gross P&L & Net P&L Calculation

Ownership boundary

The accounting chain is:
#29.4
Mechanical Execution
â†“
#29.5
Economic Execution + Costs
â†“
#29.7.1
Gross P&L
â†“
Execution Costs
â†“
Net P&L
â†“
Realized R
â†“
Account Equity Change
#29.7.1 consumes resolved values. It does not reinterpret them.
It cannot change:
entry
exit
quantity
stop
target
direction
execution chronology
slippage
commissions
2. Required inputs

A completed trade must provide:
TradeAccountingInput {
direction

quantity

economic_entry_price

economic_exit_price

contract_multiplier

total_execution_cost

maximum_allowed_risk

actual_risk_dollars

pre_trade_equity

}
The contract_multiplier comes from the instrument specification.
The economic_entry_price and economic_exit_price come from #29.5.
3. Long gross P&L

For a long:
GrossPnL =
(EconomicExitPrice - EconomicEntryPrice)
Ã— Quantity
Ã— ContractMultiplier
Example:
Entry = 5018.25
Exit = 5023.25
Quantity = 4
Multiplier = 1
Therefore:
GrossPnL =
(5023.25 - 5018.25)
Ã— 4
Ã— 1

= $20
4. Short gross P&L

For a short:
GrossPnL =
(EconomicEntryPrice - EconomicExitPrice)
Ã— Quantity
Ã— ContractMultiplier
Example:
Entry = 5018.25
Exit = 5013.75
Quantity = 4
Multiplier = 1
Therefore:
GrossPnL =
(5018.25 - 5013.75)
Ã— 4

= $18
The direction is therefore explicitly encoded rather than inferred from whether the result happens to be positive or negative.
5. Universal P&L formula

The engine can equivalently represent both directions as:
DirectionMultiplier:

LONG = +1
SHORT = -1
Then:
GrossPnL =
(EconomicExitPrice - EconomicEntryPrice)
Ã— DirectionMultiplier
Ã— Quantity
Ã— ContractMultiplier
This is the canonical implementation formula.
6. Contract multiplier

The multiplier must never be assumed to be 1.
The accounting engine receives:
ContractMultiplier
from InstrumentSpecification.
Therefore:
PriceDifference
Ã— Quantity
Ã— ContractMultiplier

Gross P&L
This allows the same accounting primitive to handle instruments whose quoted price does not directly equal one dollar of account P&L per unit.
7. Execution costs

#29.5 produces:
TotalExecutionCosts
#29.7.1 does not recalculate those costs.
It simply consumes them.
Therefore:
NetPnL =
GrossPnL - TotalExecutionCosts
This is the canonical net-P&L formula.
8. Cost sign convention

Execution costs must always be represented as a non-negative expense:
TotalExecutionCosts >= 0
Therefore the accounting formula remains:
NetPnL =
GrossPnL - TotalExecutionCosts
We should not store commissions as negative P&L and then subtract them again.
That would create double-counting.
9. Zero-cost case

If:
TotalExecutionCosts = 0
then:
NetPnL = GrossPnL
This gives us the clean mechanical baseline.
10. Account-equity transition

The account begins the trade with:
PreTradeEquity
After the completed trade:
PostTradeEquity =
PreTradeEquity + NetPnL
Therefore:
AccountEquityChange =
NetPnL
and:
PostTradeEquity =
PreTradeEquity + AccountEquityChange
11. Equity cannot update before the trade closes

The base accounting model uses realized accounting.
Therefore:
POSITION OPEN
â†“
No realized equity change
â†“
POSITION CLOSED
â†“
Net P&L calculated
â†“
Equity updated
Unrealized P&L is outside this primitive.
This prevents the account balance from changing every candle merely because an open position fluctuates.
12. Actual risk

We already established that #29.2 calculates:
ActualRiskDollars
after quantity rounding.
That value is the denominator for realized R.
Not:
MaximumAllowedRisk
unless they happen to be equal.
This distinction is important.
Example:
MaximumAllowedRisk = $100
ActualRisk = $75
A $150 profit is:
$150 / $75 = 2R
not:
$150 / $100 = 1.5R
13. Realized gross R

The mechanical gross R result is:
GrossR =
GrossPnL / ActualRiskDollars
provided:
ActualRiskDollars > 0
For a $75 actual risk and $150 gross profit:
GrossR = +2.00R
For a $75 actual risk and $75 gross loss:
GrossR = -1.00R
14. Realized net R

Because execution costs affect the actual account result, we should also record:
NetR =
NetPnL / ActualRiskDollars
Therefore a trade can have:
GrossR = +2.00R
NetR = +1.85R
after costs.
This is more informative than overwriting the gross result.
Both should be retained.
15. Risk invariant

ActualRiskDollars must come from #29.2.
#29.7.1 must not recompute the stop risk.
That ownership remains:
#29.2
Entry + Stop + Quantity
â†“
ActualRiskDollars
Then:
#29.7.1
ActualRiskDollars
â†“
Realized R
This prevents accounting from silently creating a second position-sizing methodology.
16. Maximum allowed risk vs actual risk

The trade record should preserve both:
MaximumAllowedRisk
ActualRisk
But only:
ActualRisk
is used for realized R.
This gives us an auditable distinction between:
Risk permitted
and:
Risk actually deployed
17. Breakeven classification

Trade classification should be based on Net P&L, because the accounting layer ultimately cares about the financial result after execution friction.
Use:
NetPnL > 0 â†’ WIN
NetPnL < 0 â†’ LOSS
NetPnL = 0 â†’ BREAKEVEN
No tolerance band should be invented.
Exact equality is the only breakeven condition.
18. Gross vs net classification

The canonical trade classification should therefore be:
TradeResult =
WIN if NetPnL > 0
LOSS if NetPnL < 0
BREAKEVEN if NetPnL = 0
We can still preserve:
GrossResult
for analysis, but the official realized account result is based on NetPnL.
19. Example â€” losing trade

Suppose:
Long
Economic Entry = 5018.25
Economic Exit = 5013.75
Quantity = 4
Multiplier = 1
Costs = $2
Actual Risk = $72
Gross:
(5013.75 - 5018.25) Ã— 4
= -$18
Net:
-$18 - $2
= -$20
Realized R:
GrossR = -18 / 72 = -0.25R

NetR = -20 / 72 = -0.2778R
Classification:
LOSS
20. Example â€” winning trade

Short
Economic Entry = 5018.25
Economic Exit = 5013.75
Quantity = 4
Multiplier = 1
Costs = $2
Actual Risk = $72
Gross:
(5018.25 - 5013.75) Ã— 4
= +$18
Net:
$18 - $2
= +$16
R:
GrossR = +0.25R
NetR = +0.2222R
Classification:
WIN
21. Account equity example

Suppose:
PreTradeEquity = $50,000
NetPnL = +$250
Then:
PostTradeEquity =
$50,000 + $250

= $50,250
The next trade's PreTradeEquity becomes:
$50,250
This creates the sequential account ledger.
22. Sequential equity state

The account therefore follows:
Initial Equity
â†“
Trade #1 Net P&L
â†“
Equity After Trade #1
â†“
Trade #2 Net P&L
â†“
Equity After Trade #2
â†“
Trade #3 Net P&L
â†“
...
For trade n:
PostTradeEquity[n] =
PreTradeEquity[n] + NetPnL[n]
and:
PreTradeEquity[n+1] =
PostTradeEquity[n]
assuming the account has no external deposits, withdrawals, or other capital flows.
External capital flows should be modeled separately later rather than hidden inside trading P&L.
23. Trade accounting object

I would lock the accounting record as:
TradeAccounting {
trade_id

position_id

setup_id

pre_trade_equity

direction

quantity

contract_multiplier

economic_entry_price

economic_exit_price

gross_pnl

total_execution_costs

net_pnl

maximum_allowed_risk

actual_risk

gross_r

net_r

result

account_equity_change

post_trade_equity

accounting_time

}
24. Historical immutability

Once the position is closed and accounting is finalized:
TradeAccounting
becomes immutable.
A later market event cannot change:
gross_pnl
net_pnl
gross_r
net_r
result
pre_trade_equity
post_trade_equity
If an accounting error is discovered, the architecture should create a corrected accounting record/version rather than silently mutating historical execution.
25. What #29.7.1 does NOT calculate

This primitive should explicitly not calculate:
Win rate
Loss rate
Expectancy
Profit factor
Maximum drawdown
Sharpe ratio
Sortino
Average R
Average win
Average loss
Streaks
Daily performance
Monthly performance
Strategy performance
Those are higher-level performance/account analytics.
#29.7.1 establishes only the atomic financial result of one completed trade and its immediate effect on account equity.
26. Exact algorithm

For every closed position:
INPUT
Direction
Quantity
EconomicEntry
EconomicExit
ContractMultiplier
TotalExecutionCosts
ActualRisk
PreTradeEquity
Step 1 â€” Direction
LONG â†’ DirectionMultiplier = +1
SHORT â†’ DirectionMultiplier = -1
Step 2 â€” Price differential
PriceDifference =
EconomicExit - EconomicEntry
Step 3 â€” Gross P&L
GrossPnL =
PriceDifference
Ã— DirectionMultiplier
Ã— Quantity
Ã— ContractMultiplier
Step 4 â€” Net P&L
NetPnL =
GrossPnL - TotalExecutionCosts
Step 5 â€” Gross R
GrossR =
GrossPnL / ActualRisk
Step 6 â€” Net R
NetR =
NetPnL / ActualRisk
Step 7 â€” Classification
IF NetPnL > 0:
WIN

ELSE IF NetPnL < 0:
LOSS

ELSE:
BREAKEVEN
Step 8 â€” Account change
AccountEquityChange =
NetPnL
Step 9 â€” Post-trade equity
PostTradeEquity =
PreTradeEquity + NetPnL
27. Division-by-zero protection

Because #29.2 requires:
ActualRiskDollars > 0
a valid executed trade should never reach #29.7.1 with zero risk.
Nevertheless, the accounting engine must enforce:
ActualRiskDollars <= 0
â†“
ACCOUNTING_ERROR
It must not silently produce:
âˆžR
NaNR
0R
This is an accounting invariant.
28. Important distinction: R is not P&L

The system should never collapse these:
+$500
and:
+2.0R
They answer different questions.
P&L measures:
dollars
R measures:
return relative to actual initial risk
Therefore both must be retained.
29. Final locked definition

#29.7.1 â€” Exact Mechanical Gross P&L & Net P&L Calculation: For every completed position, #29.7.1 consumes the immutable economic entry price and economic exit price established by #29.5, the executed quantity and contract multiplier established by upstream execution/sizing primitives, the total execution costs established by #29.5, the actual risk established by #29.2, and the account's pre-trade equity. For a long position, Gross P&L = (Economic Exit âˆ’ Economic Entry) Ã— Quantity Ã— Contract Multiplier. For a short position, Gross P&L = (Economic Entry âˆ’ Economic Exit) Ã— Quantity Ã— Contract Multiplier. Net P&L = Gross P&L âˆ’ Total Execution Costs. Realized Gross R = Gross P&L Ã· Actual Risk Dollars, and Realized Net R = Net P&L Ã· Actual Risk Dollars. Trade classification is based on Net P&L: positive = WIN, negative = LOSS, exactly zero = BREAKEVEN. Realized account-equity change equals Net P&L, and Post-Trade Equity = Pre-Trade Equity + Net P&L. #29.7.1 does not modify any upstream execution result, setup state, position state, quantity, stop, target, exit reason, or execution-cost calculation, and it does not calculate higher-level performance statistics.**

So we now have the complete atomic financial chain:
SETUP
â†“
ENTRY
â†“
SIZE
â†“
SL / TP
â†“
EXIT
â†“
COSTS
â†“
POSITION CLOSED
â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ #29.7.1 ACCOUNTING â”‚
â”‚ â”‚
â”‚ Gross P&L â”‚
â”‚ âˆ’ Execution Costs â”‚
â”‚ = Net P&L â”‚
â”‚ â”‚
â”‚ Gross P&L Ã· Actual Risk â”‚
â”‚ = Gross R â”‚
â”‚ â”‚
â”‚ Net P&L Ã· Actual Risk â”‚
â”‚ = Net R â”‚
â”‚ â”‚
â”‚ Pre-Trade Equity + Net P&L â”‚
â”‚ = Post-Trade Equity â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
#29.7.1 is now fully deterministic.

Show more

Agreed. #29.7.1 is now structurally complete, but there is one accounting boundary I would lock before moving to #29.7.2 because it affects the correctness of every future P&L calculation.

One critical consistency issue

Your #29.5 definition allows:

Mechanical Execution â†’ Economic Execution Price

while also producing:

Total Execution Costs

Then #29.7.1 does:

Gross P&L from Economic Entry/Exit
âˆ’ Total Execution Costs
= Net P&L

That creates a potential double-counting problem.

For example, suppose:

Mechanical entry = $100

Mechanical exit = $102

Entry slippage = $0.10

Exit slippage = $0.10

If #29.5 produces:

Economic entry = $100.10

Economic exit = $101.90

then the $0.20 price impact has already been incorporated into the economic execution.

If #29.5 also reports:

Total execution cost = $0.20

and #29.7.1 subtracts that again, the same friction is counted twice.

Therefore, I recommend this exact invariant

We should distinguish price-adjusting execution friction from cash-denominated execution expenses.

#### MECHANICAL EXECUTION

â†“

#29.5

â†“

Economic Execution Prices

+

Explicit Cash Costs

â†“

#29.7.1

â†“

Gross P&L

â†“

Cash Costs

â†“

Net P&L

Where:

Economic execution prices may incorporate:

spread

price-based slippage

tick-based slippage

other friction that changes the actual execution price

And explicit cash costs include:

commissions

exchange/transaction fees

fixed fees

other costs not already embedded in the economic execution price.

Then the accounting formula remains:

GrossPnL =

(EconomicExit âˆ’ EconomicEntry)

Ã— DirectionMultiplier

Ã— Quantity

Ã— ContractMultiplier

NetPnL =

GrossPnL âˆ’ ExplicitCashExecutionCosts

This preserves your intended architecture without double-counting.

One terminology change I would make

Instead of:

TotalExecutionCosts

being ambiguous between price-adjusted friction and cash expenses, I would lock #29.5 to producing something like:

ExecutionCostRecord {

mechanical_entry_price

mechanical_exit_price

economic_entry_price

economic_exit_price

entry_spread

exit_spread

entry_slippage

exit_slippage

commission

transaction_fees

explicit_cash_costs

cost_specification_id

}

Then #29.7.1 consumes:

EconomicEntryPrice

EconomicExitPrice

ExplicitCashCosts

rather than potentially subtracting slippage twice.

With that clarification, #29.7.1 is locked

Its responsibility is exactly:

#29.7.1

â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

Economic Entry

Economic Exit

Quantity

Multiplier

Actual Risk

Pre-Trade Equity

Explicit Cash Costs

â†“

Gross P&L

Net P&L

Gross R

Net R

Trade Result

Equity Change

Post-Trade Equity

â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

And it does not own:

setup qualification

entry selection

position sizing

SL/TP construction

exit chronology

exit causality

slippage modeling

commission modeling

performance statistics

drawdown

expectancy

win rate

That gives us a very clean boundary:

#29.5

WHAT DID EXECUTION FRICTION DO?

â†“

#29.7.1

WHAT WAS THE FINANCIAL RESULT OF THIS ONE TRADE?

â†“

#29.7.2

WHAT DOES THE COLLECTION OF TRADES TELL US?

So #29.7.1 is ready to be frozen, with the above anti-double-counting distinction added to the specification.

The logical next primitive is therefore #29.7.2 â€” Exact Mechanical Trade Performance / Statistical Aggregation. That is where we can formally define things like win rate, expectancy, profit factor, average R, drawdown, streaks, and equity-curve statisticsâ€”without contaminating the atomic accounting primitive.

#29.7.1 â€” Final Locked Boundary
The engine consumes only resolved economic execution data:
Mechanical Execution
â†“
#29.5 Execution Costs
â†“
Economic Entry Price
Economic Exit Price
Explicit Cash Costs
â†“
#29.7.1 Trade Accounting
â†“
Gross P&L
Net P&L
Gross R
Net R
Equity Change
Post-Trade Equity
Exact formulas
Direction multiplier
Long = +1
Short = -1
Gross P&L
GrossPnL =
(EconomicExitPrice - EconomicEntryPrice)
Ã— DirectionMultiplier
Ã— Quantity
Ã— ContractMultiplier
Net P&L
NetPnL =
GrossPnL - ExplicitCashCosts
Actual risk
This comes from the already-established #29.2 position-sizing calculation and is not recalculated or modified by #29.7.1.
Gross R
GrossR =
GrossPnL / InitialRiskDollars
Net R
NetR =
NetPnL / InitialRiskDollars
Account equity transition
PostTradeEquity =
PreTradeEquity + NetPnL
Critical invariant
If slippage, spread, or another price-based friction has already changed:
Mechanical Entry â†’ Economic Entry
Mechanical Exit â†’ Economic Exit
then that price adjustment must not also appear inside ExplicitCashCosts.
Only genuinely cash-denominated costs are subtracted separately.
Next: #29.7.2 â€” Exact Mechanical Performance Statistics
Now we can safely move from:
â€œWhat did this individual trade do?â€

to:
â€œWhat does the collection of completed trades tell us?â€

I would make #29.7.2 define, mechanically and without discretion:
Trade classification
WIN
LOSS
BREAKEVEN

Win-rate calculation

Loss-rate calculation

Breakeven-rate calculation

Average R
mean Net R
whether Gross R is retained separately

Expectancy
exact formula
whether based on R or dollars

Profit factor
gross winning P&L Ã· gross losing P&L

Cumulative P&L

Cumulative R

Equity curve

Peak equity

Drawdown
absolute
percentage
peak-to-trough methodology

Maximum drawdown

Maximum winning streak

Maximum losing streak

Average win / average loss

R distribution

Trade-count requirements
what happens with zero trades
one trade
insufficient observations

Time aggregationdaily
weekly
monthly
full-history

Historical immutabilitycompleted trade records cannot be rewritten by later trades

No look-ahead
statistics may only use trades whose accounting state is already finalized.
The important architectural distinction remains:
#29.7.1
INDIVIDUAL TRADE ACCOUNTING
â†“
#29.7.2
PORTFOLIO / PERFORMANCE STATISTICS
#29.7.2 should not modify any historical trade, execution, setup, position, or account transaction. It is a read-only analytical layer over finalized accounting records.

Show more

Agreed. The boundary is clean.

#29.7.1 is now locked as the atomic trade-accounting layer.
#29.7.2 should therefore be strictly a read-only aggregation and performance-statistics layer over finalized #29.7.1 records.

The key principle should be:

#29.7.2 observes completed accounting records; it never creates, modifies, or reinterprets them.

#29.7.2 â€” Exact Mechanical Performance Statistics

1. Ownership Boundary

The architecture is:

#29.7.1

#### INDIVIDUAL TRADE ACCOUNTING

â†“

Finalized TradeAccounting records

â†“

#29.7.2

#### PERFORMANCE STATISTICS

â†“

Win Rate

Loss Rate

Breakeven Rate

Average R

Expectancy

Profit Factor

Cumulative P&L

Cumulative R

Equity Curve

Drawdown

Streaks

Distribution

Time Aggregation

#29.7.2 owns:

trade classification aggregation

trade counts

win rate

loss rate

breakeven rate

average win

average loss

average R

expectancy

profit factor

cumulative P&L

cumulative R

equity curve

peak equity

drawdown

maximum drawdown

winning streaks

losing streaks

R distribution

time-based aggregation

full-history aggregation

It does not own:

setup qualification

entry selection

position sizing

SL/TP selection

exit resolution

execution costs

individual trade P&L calculation

account transaction creation

trade modification

2. Read-Only Principle

#29.7.2 is analytically read-only.

TradeAccounting #1 â”€â”

TradeAccounting #2 â”€â”¤

TradeAccounting #3 â”€â”¤

TradeAccounting #4 â”€â”¤

â†“

#29.7.2

â†“

Statistics

The statistics engine may read finalized records.

It may not:

modify trade

delete trade

rewrite trade

change P&L

change R

change classification

change equity

change execution

Therefore:

#29.7.1 = SOURCE OF TRUTH

#29.7.2 = DERIVED ANALYTICS

3. Finalized-Trade Requirement

Only finalized accounting records may enter the statistics population.

A trade must have:

AccountingState = FINALIZED

before it can be included.

Therefore:

#### OPEN POSITION

â†“

#### NO STATISTICS

#### CLOSED POSITION

â†“

#29.7.1 ACCOUNTING

â†“

#### NOT YET FINALIZED

â†“

#### NO STATISTICS

#### FINALIZED ACCOUNTING

â†“

#29.7.2 ELIGIBLE

This prevents partially completed trades from contaminating statistics.

4. No Look-Ahead

The statistics engine may only use information that existed at the statistical observation time.

For example:

Trade #1 finalized

Trade #2 finalized

Trade #3 OPEN

The current statistics population is:

Trade #1

Trade #2

Trade #3 cannot appear in the statistics simply because its eventual outcome is known later.

This gives:

Statistics(t)

=

function(finalized trades available at t)

and prevents future trades from influencing historical statistics.

5. Trade Population

Define:

N = number of finalized trades

Each finalized trade contributes exactly one observation.

Therefore:

Trade #1 â†’ 1 observation

Trade #2 â†’ 1 observation

Trade #3 â†’ 1 observation

A single trade cannot be counted twice.

6. Trade Classification

#29.7.1 already determines the official result:

NetPnL > 0

â†“

#### WIN

NetPnL < 0

â†“

#### LOSS

NetPnL = 0

â†“

#### BREAKEVEN

#29.7.2 does not recalculate or reinterpret this classification.

It simply aggregates the finalized classifications.

Define:

WinCount

LossCount

BreakevenCount

TotalTradeCount

with:

TotalTradeCount =

WinCount

+

LossCount

+

BreakevenCount

This must always hold.

7. Win Rate

Win rate is:

WinRate =

WinCount / TotalTradeCount

Expressed as a percentage:

WinRate% =

(WinCount / TotalTradeCount) Ã— 100

Example:

100 trades

60 wins

30 losses

10 breakevens

WinRate =

60 / 100

=

60%

Breakeven trades remain part of the total trade population.

They are not silently removed.

8. Loss Rate

LossRate =

LossCount / TotalTradeCount

or:

LossRate% =

(LossCount / TotalTradeCount) Ã— 100

9. Breakeven Rate

BreakevenRate =

BreakevenCount / TotalTradeCount

or:

BreakevenRate% =

(BreakevenCount / TotalTradeCount) Ã— 100

Therefore:

WinRate

+

LossRate

+

BreakevenRate

=

100%

subject to exact arithmetic/rounding conventions.

10. Zero-Trade Population

If:

TotalTradeCount = 0

the engine must not manufacture:

0%

0R

100%

for statistics whose denominator is zero.

The correct state is:

#### STATISTIC_UNAVAILABLE

or equivalent null/undefined representation.

For example:

WinRate = NULL

LossRate = NULL

BreakevenRate = NULL

AverageR = NULL

Expectancy = NULL

ProfitFactor = NULL

while:

TradeCount = 0

CumulativePnL = 0

CumulativeR = 0

can be represented as zero because no realized result exists.

11. One-Trade Population

A single finalized trade is sufficient to calculate atomic statistics.

For example:

N = 1

NetR = +2R

Then:

WinRate = 100%

AverageR = +2R

Expectancy = +2R

But statistics that conceptually describe variation or distributions should not invent information that does not exist.

For example:

Maximum drawdown

can mechanically be calculated from the resulting equity path, but the engine must not imply that one trade provides meaningful statistical confidence.

That distinction belongs to interpretation, not calculation.

12. Average Win

Average winning P&L:

AverageWinPnL =

Sum(NetPnL of winning trades)

/

WinCount

Average winning R:

AverageWinR =

Sum(NetR of winning trades)

/

WinCount

If:

WinCount = 0

then:

AverageWinPnL = NULL

AverageWinR = NULL

No artificial zero should be inserted.

13. Average Loss

Average losing P&L:

AverageLossPnL =

Sum(NetPnL of losing trades)

/

LossCount

Because losing P&L is negative, this produces a negative value.

Example:

Losses:

-$100

-$50

-$150

AverageLossPnL =

-$300 / 3

=

-$100

Average losing R:

AverageLossR =

Sum(NetR of losing trades)

/

LossCount

This similarly remains negative.

14. Average R

The canonical average R should use Net R.

AverageR =

Î£ NetR / N

Therefore:

AverageR =

mean(NetR)

Gross R remains available separately for analysis.

The engine should not replace:

GrossR

with:

NetR

They remain distinct measurements.

15. Expectancy

The canonical expectancy should be defined in R, because R normalizes trades according to their actual risk.

Therefore:

ExpectancyR =

Î£ NetR / N

which is mathematically equivalent to:

ExpectancyR = AverageNetR

Alternatively, using outcome probabilities:

ExpectancyR =

(Pwin Ã— AverageWinR)

+

(Ploss Ã— AverageLossR)

+

(Pbreakeven Ã— AverageBreakevenR)

Since breakeven R is exactly zero:

AverageBreakevenR = 0

so:

ExpectancyR =

(Pwin Ã— AverageWinR)

+

(Ploss Ã— AverageLossR)

The direct mean of finalized Net R should be the canonical implementation because it avoids unnecessary reconstruction.

16. Dollar Expectancy

The engine may additionally calculate:

ExpectancyPnL =

Î£ NetPnL / N

This answers:

How many dollars did the strategy make or lose per completed trade on average?

Therefore retain both:

ExpectancyR

ExpectancyPnL

They answer different questions.

17. Profit Factor

Profit factor measures:

Gross Winning P&L

------------------

Absolute Gross Losing P&L

Given that #29.7.1 defines Net P&L as the actual financial result after execution costs, the performance layer should use Net P&L for the canonical account-performance profit factor.

Therefore:

GrossProfit =

Î£ NetPnL for all winning trades

GrossLoss =

#### ABS(

Î£ NetPnL for all losing trades

)

Then:

ProfitFactor =

GrossProfit / GrossLoss

Example:

Winning trades = +$1,500

Losing trades  = -$1,000

ProfitFactor =

1500 / 1000

=

1.50

Important:

"GrossProfit" here means total positive realized P&L before subtracting the negative side, not #29.7.1's GrossPnL field.

To avoid terminology collision, the implementation should preferably use:

TotalWinningNetPnL

TotalLosingNetPnL

ProfitFactor

18. Profit-Factor Edge Cases

If:

TotalLosingNetPnL = 0

then division by zero occurs.

The engine must not return:

0

or:

1

Instead:

ProfitFactor = âˆž

when there are winning trades and no losses.

If there are:

0 wins

0 losses

then:

ProfitFactor = NULL

because there is no performance population.

19. Cumulative P&L

For chronological finalized trades:

CumulativePnL[n] =

Î£ NetPnL[1...n]

Example:

Trade 1: +100

Trade 2: -50

Trade 3: +200

Trade 4: -75

produces:

Trade 1 â†’ +100

Trade 2 â†’ +50

Trade 3 â†’ +250

Trade 4 â†’ +175

The cumulative series must preserve chronological order.

20. Cumulative R

Likewise:

CumulativeR[n] =

Î£ NetR[1...n]

Example:

+1.0R

-0.5R

+2.0R

-1.0R

produces:

+1.0R

+0.5R

+2.5R

+1.5R

Cumulative R is independent of dollar P&L.

21. Equity Curve

The canonical equity curve comes directly from #29.7.1:

PostTradeEquity

For each finalized trade:

Equity[n] =

PreTradeEquity[n] + NetPnL[n]

and:

PreTradeEquity[n+1]

=

PostTradeEquity[n]

assuming no external capital flows.

Therefore #29.7.2 does not reconstruct an alternative equity model.

It reads the finalized equity state.

22. Equity-Curve Ordering

The equity curve must be chronological.

Trade 1

â†“

Trade 2

â†“

Trade 3

â†“

Trade 4

not:

largest winner

â†“

largest loser

â†“

oldest trade

â†“

newest trade

Ordering is therefore a required input to all path-dependent statistics.

This is especially important for drawdown and streak calculations.

23. Peak Equity

At each point:

PeakEquity[n] =

#### MAX(

Equity[1],

Equity[2],

...

Equity[n]

)

Therefore the peak can remain unchanged or increase.

It can never decrease.

Example:

Equity:

50,000

50,500

50,300

51,000

50,700

Peak:

50,000

50,500

50,500

51,000

51,000

24. Absolute Drawdown

Drawdown at observation n:

DrawdownDollar[n] =

PeakEquity[n] - Equity[n]

Example:

Peak = $51,000

Current = $50,700

Drawdown = $300

Drawdown is therefore always:

>= 0

under this definition.

25. Percentage Drawdown

Percentage drawdown:

DrawdownPercent[n] =

(

PeakEquity[n] - Equity[n]

)

/

PeakEquity[n]

Ã— 100

Example:

Peak = $51,000

Current = $50,700

Drawdown =

300 / 51,000

=

0.5882%

The denominator is the applicable peak equity.

26. Maximum Drawdown

Maximum drawdown is the largest observed drawdown in the equity path.

Absolute:

MaximumDrawdownDollar =

MAX(DrawdownDollar)

Percentage:

MaximumDrawdownPercent =

MAX(DrawdownPercent)

The engine should retain both.

27. Peak-to-Trough Methodology

For every drawdown event:

#### PEAK

â†“

equity declines

â†“

#### TROUGH

The drawdown is:

PeakEquity - TroughEquity

The peak must occur chronologically before the trough.

The engine cannot select:

Trough first

Peak later

to manufacture a drawdown.

28. Drawdown Recovery

For the base statistics layer, the important distinction is:

Peak

â†“

Trough

â†“

Recovery

The maximum drawdown remains the largest peak-to-trough decline even after recovery.

A later recovery does not erase the historical drawdown.

29. Maximum Winning Streak

A winning streak is a consecutive sequence of:

#### WIN

#### WIN

#### WIN

...

Maximum winning streak:

#### MAXIMUM_CONSECUTIVE_WINS

Example:

#### W W L W W W L W

produces:

MaximumWinningStreak = 3

Breakeven interrupts the winning streak.

Therefore:

#### W W B W

contains a maximum winning streak of:

2

not 3.

30. Maximum Losing Streak

Likewise:

MaximumLosingStreak =

#### MAXIMUM_CONSECUTIVE_LOSSES

Breakeven interrupts a losing streak.

Example:

#### L L B L L L W

produces:

MaximumLosingStreak = 3

31. R Distribution

The statistics layer should retain the distribution of:

NetR

for every finalized trade.

Conceptually:

RDistribution = [

NetR1,

NetR2,

NetR3,

...

NetRn

]

This allows later analysis of:

frequency of outcomes

concentration

dispersion

positive/negative tails

consistency

But #29.7.2 should not invent additional distribution statistics unless explicitly defined as part of this primitive.

32. Trade-Count Requirements

Every statistic must declare its minimum data requirement.

Zero trades

N = 0

No rate, average, expectancy, or profit-factor statistic should fabricate a value.

One trade

N = 1

Atomic statistics may be calculated.

For example:

NetR = +2R

AverageR = +2R

ExpectancyR = +2R

WinRate = 100%

Multiple trades

All aggregate statistics are calculated normally.

The engine should not impose an arbitrary minimum sample size such as:

30 trades required

100 trades required

unless a separate statistical-validation primitive is later defined.

That would belong outside #29.7.2.

33. Daily Aggregation

The finalized trades can be grouped by trading date.

For each day:

DailyTradeCount

DailyWinCount

DailyLossCount

DailyBreakevenCount

DailyNetPnL

DailyNetR

DailyWinRate

DailyAverageR

The day grouping must use the strategy's explicitly defined trading/session timezone.

The engine must not silently use the computer's local timezone if a strategy timezone has been established elsewhere.

34. Weekly Aggregation

The same finalized records can be aggregated by week:

WeeklyTradeCount

WeeklyNetPnL

WeeklyNetR

WeeklyWinRate

...

Week boundaries must be deterministic.

The engine must use one defined calendar convention rather than dynamically changing the boundary.

35. Monthly Aggregation

Likewise:

MonthlyTradeCount

MonthlyNetPnL

MonthlyNetR

MonthlyWinRate

...

Month boundaries are calendar-defined.

36. Full-History Aggregation

Full-history statistics use:

#### ALL FINALIZED TRADES

within the requested historical range.

Example:

2026-01-01 â†’ 2026-12-31

The engine must include only finalized trades falling within that defined range.

37. Time Aggregation Must Not Double-Count

A trade belongs to exactly one aggregation bucket for a given time resolution.

For example:

Trade #101

2026-08-14

belongs to:

Daily: 2026-08-14

Weekly: corresponding week

Monthly: 2026-08

Full History: yes

It must not appear twice inside the same daily bucket.

38. Historical Immutability

Once:

TradeAccounting #101

has been finalized, later trades cannot modify it.

For example:

Trade #101 = +2R

If Trade #102 later loses:

Trade #101 remains +2R

The historical record is immutable.

#29.7.2 simply produces a new aggregate view:

After Trade #101:

CumulativeR = +2R

After Trade #102:

CumulativeR = +1R

The first result is not rewritten.

39. Statistics Are Derived, Not Stored as Trade Truth

The architecture should distinguish:

#### TRADE TRUTH

â†“

#29.7.1

from:

#### DERIVED STATISTICS

â†“

#29.7.2

For example:

TradeAccounting:

NetPnL = +250

NetR = +2.0R

is source data.

Whereas:

WinRate = 62%

AverageR = +0.43R

ProfitFactor = 1.74

are derived observations.

If the statistics engine is rerun against the same finalized population, it should produce the same result.

40. Determinism

Given identical finalized accounting records:

Same Inputs

â†“

#29.7.2

â†“

Same Statistics

No randomness.

No discretionary interpretation.

No future information.

No changing assumptions.

No hidden filtering.

41. No Reinterpretation of Trade Results

Suppose:

#29.7.1:

NetPnL = -$25

NetR   = -0.5R

Result = LOSS

#29.7.2 cannot say:

"But gross P&L was positive,

so classify it as WIN."

The official classification remains:

#### LOSS

because #29.7.1 established that:

NetPnL < 0

42. No Look-Ahead in Equity Statistics

Suppose the finalized sequence is:

Trade 1 +$100

Trade 2 -$200

Trade 3 +$300

After Trade #1, the equity curve is only allowed to know:

Trade #1

It cannot use the eventual Trade #2 or #3 result to determine historical drawdown at Trade #1.

Therefore:

Statistics at time t

=

function(finalized records available at t)

This rule is particularly important if the engine is later used for walk-forward testing.

43. Performance Snapshot Object

I recommend a deterministic aggregate object:

PerformanceStatistics {

population_id

start_time

end_time

trade_count

win_count

loss_count

breakeven_count

win_rate

loss_rate

breakeven_rate

average_win_pnl

average_loss_pnl

average_win_r

average_loss_r

average_net_pnl

average_net_r

expectancy_pnl

expectancy_r

total_winning_net_pnl

total_losing_net_pnl

profit_factor

cumulative_pnl

cumulative_r

peak_equity

current_equity

maximum_drawdown_dollars

maximum_drawdown_percent

maximum_winning_streak

maximum_losing_streak

r_distribution

generated_time

}

This object is derived from finalized accounting records.

It does not become the source of truth for the trades.

44. Equity-Curve Object

Because the equity curve is path-dependent, I would separately preserve:

EquityPoint {

trade_id

trade_time

pre_trade_equity

net_pnl

post_trade_equity

cumulative_pnl

cumulative_r

peak_equity

drawdown_dollars

drawdown_percent

}

This makes every point auditable.

For example:

Trade #42

â†“

Net P&L = -$150

â†“

Post Equity = $49,850

â†“

Peak Equity = $50,200

â†“

Drawdown = $350

â†“

Drawdown % = 0.697%

45. Exact Mechanical Algorithm

For a requested finalized trade population:

Step 1 â€” Load finalized records

Trades =

FINALIZED TradeAccounting records

Step 2 â€” Sort chronologically

Trades.sort(execution_time ASC)

Step 3 â€” Count outcomes

WinCount

LossCount

BreakevenCount

TradeCount

Step 4 â€” Calculate rates

WinRate

LossRate

BreakevenRate

Step 5 â€” Calculate averages

AverageWinPnL

AverageLossPnL

AverageWinR

AverageLossR

AverageNetPnL

AverageNetR

Step 6 â€” Calculate expectancy

ExpectancyPnL

ExpectancyR

Step 7 â€” Calculate profit factor

TotalWinningNetPnL

TotalLosingNetPnL

ProfitFactor

Step 8 â€” Construct cumulative series

CumulativePnL

CumulativeR

Step 9 â€” Construct equity curve

PreTradeEquity

PostTradeEquity

Step 10 â€” Calculate running peak

PeakEquity

Step 11 â€” Calculate drawdown

DrawdownDollar

DrawdownPercent

Step 12 â€” Calculate maximum drawdown

MaximumDrawdownDollar

MaximumDrawdownPercent

Step 13 â€” Calculate streaks

MaximumWinningStreak

MaximumLosingStreak

Step 14 â€” Preserve R distribution

NetR[1...N]

Step 15 â€” Generate requested time aggregations

Daily

Weekly

Monthly

Full History

Step 16 â€” Return read-only statistics

No underlying record is modified.

46. Critical Invariants

#29.7.2 must enforce:

Only finalized trades are included.

Each finalized trade is counted exactly once.

Trade classification comes from #29.7.1.

#29.7.2 cannot modify Net P&L.

#29.7.2 cannot modify Net R.

#29.7.2 cannot modify account equity.

#29.7.2 cannot modify execution costs.

#29.7.2 cannot modify trade timestamps.

#29.7.2 cannot modify historical trades.

Future trades cannot influence past statistics.

Equity calculations preserve chronological order.

Drawdown calculations use chronological peak-to-trough methodology.

Breakeven trades count toward total trade count.

Breakeven trades interrupt winning and losing streaks.

Zero denominators cannot produce fabricated statistics.

Profit factor cannot silently convert zero losses into zero.

Gross R and Net R remain separate.

Dollar P&L and R remain separate.

Daily, weekly, monthly, and full-history populations must be explicitly defined.

Identical finalized inputs must produce identical statistics.

47. What #29.7.2 Does NOT Calculate

This boundary should remain strict.

It does not calculate:

Sharpe ratio

Sortino ratio

Calmar ratio

recovery factor

risk of ruin

statistical significance

confidence intervals

Monte Carlo analysis

parameter optimization

strategy ranking

regime analysis

setup-quality analysis

market-condition analysis

predictive expectancy

future performance

parameter sensitivity

Those are higher-level analytical primitives.

For example, we can later define:

#29.7.3

#### RISK / DISTRIBUTION ANALYTICS

#29.7.4

#### STATISTICAL VALIDATION

#29.7.5

#### STRATEGY PERFORMANCE COMPARISON

without contaminating the atomic accounting architecture.

48. Final Locked Definition

#29.7.2 â€” Exact Mechanical Performance Statistics

#29.7.2 is a read-only analytical layer operating exclusively on finalized #29.7.1 trade-accounting records. It aggregates completed trades without modifying or reinterpreting any historical execution, cost, position, setup, P&L, R, or equity record. It mechanically determines trade counts and WIN/LOSS/BREAKEVEN rates from the finalized #29.7.1 classification, calculates average winning and losing P&L and R, average Net P&L and Net R, expectancy in dollars and R, profit factor from total positive and absolute total negative Net P&L, cumulative Net P&L, cumulative Net R, chronological equity curves, running peak equity, absolute and percentage peak-to-trough drawdown, maximum drawdown, maximum winning and losing streaks, R distributions, and daily, weekly, monthly, and full-history aggregations. Statistics are calculated only from trades whose accounting state is finalized and therefore cannot use future or unresolved trades. Zero-denominator conditions produce an explicit unavailable/null state rather than an invented value. Breakeven trades remain part of the trade population and interrupt winning and losing streaks. All path-dependent statistics preserve chronological trade order. Identical finalized accounting inputs must produce identical statistical outputs. #29.7.2 does not calculate or introduce higher-level metrics such as Sharpe, Sortino, risk of ruin, statistical significance, Monte Carlo analysis, optimization, or predictive performance; those belong to later analytical primitives.

Locked Architecture So Far

#27

#### SETUP

"What is the trade?"

â†“

#28

#### ENTRY-ZONE SELECTION

"Where is the entry zone?"

â†“

#29.1

#### ENTRY EXECUTION

"Where exactly did we enter?"

â†“

#29.2

#### POSITION SIZING

"How much did we trade?"

â†“

#29.3

#### PROTECTIVE ORDERS

"Where are the immutable SL / TP?"

â†“

#29.4

#### EXIT RESOLUTION

"Which exit happened, when, and at what

mechanical price?"

â†“

#29.5

#### EXECUTION COSTS

"What economic friction applied?"

â†“

#29.6

#### POSITION LIFECYCLE

"Is the position OPEN or CLOSED?"

â†“

#29.7.1

#### TRADE ACCOUNTING

"What did this completed trade

financially produce?"

â†“

#29.7.2

#### PERFORMANCE STATISTICS

"What does the completed trade

population tell us?"

The critical separation is now:

#### MARKET MODEL

â†“

#27â€“#28

#### EXECUTION MODEL

â†“

#29.1â€“#29.6

#### ACCOUNTING MODEL

â†“

#29.7.1

#### PERFORMANCE ANALYTICS

â†“

#29.7.2

That gives us a very strong foundation: a later performance statistic can never reach backward and silently alter the trade that produced it.

so what do you need next before we can upload all of this into claude code?

Yes. We are very close, but I would not upload everything into Claude Code yet. We should finish the specification first so Claude Code is implementing a locked system rather than making architectural decisions for us.

Based on everything we've established, I would do this in the following order.

1. Finish #29.7.2 â€” Performance Statistics

This is the next thing we should lock.

We need exact mechanical definitions for:

Trade statistics

#### WIN

#### LOSS

#### BREAKEVEN

Win rate

Loss rate

Breakeven rate

Trade count

Average Net R

Average Gross R

Average winning R

Average losing R

Average winning P&L

Average losing P&L

R distribution

Portfolio statistics

Expectancy in R

Expectancy in dollars

Profit factor

Cumulative Net P&L

Cumulative Net R

Equity curve

Peak equity

Absolute drawdown

Percentage drawdown

Maximum drawdown

Maximum drawdown percentage

Maximum winning streak

Maximum losing streak

Time aggregation

Exactly how statistics are calculated for:

Individual trade

Daily

Weekly

Monthly

Full history

Edge cases

We need deterministic rules for:

0 trades

1 trade

2 trades

no winning trades

no losing trades

all breakevens

zero gross losses â†’ profit factor

zero gross wins

missing accounting records

incomplete trades

partially finalized datasets

Most importantly

We need to lock whether all official performance statistics use Net P&L / Net R, while Gross P&L / Gross R remain analytical fields.

I recommend that they do.

2. Then perform a complete #27â€“#29.7.2 architecture audit

This is extremely important.

We've built these layers:

#27

#### SETUP

â†“

#28

#### ENTRY ZONE

â†“

#29.1

#### ENTRY EXECUTION

â†“

#29.2

#### POSITION SIZING

â†“

#29.3

#### PROTECTIVE ORDERS

â†“

#29.4

#### EXIT RESOLUTION

â†“

#29.5

#### EXECUTION COSTS

â†“

#29.6

#### POSITION LIFECYCLE

â†“

#29.7.1

#### TRADE ACCOUNTING

â†“

#29.7.2

#### PERFORMANCE STATISTICS

Before coding, I want to check every arrow.

For every module we should explicitly answer:

What does it receive?

What does it produce?

What is it allowed to modify?

What is it forbidden from modifying?

What happens if its input is invalid?

What state does it create?

What state does it consume?

That catches architectural leaks before Claude Code turns them into code.

3. We need the canonical data model

Before implementation, Claude needs to know exactly what objects exist.

At minimum we're now talking about:

MarketData

InstrumentSpecification

Setup

EntryZone

EntryOrder

EntryExecution

PositionSizing

ProtectiveOrder

OCOGroup

Position

ExecutionCostSpecification

ExecutionRecord

TradeAccounting

PerformanceStatistics

Account

We should define the exact fields for each.

For example:

Position

â”œâ”€â”€ id

â”œâ”€â”€ setup_id

â”œâ”€â”€ state

â”œâ”€â”€ direction

â”œâ”€â”€ quantity

â”œâ”€â”€ entry_order_id

â”œâ”€â”€ entry_execution_id

â”œâ”€â”€ entry_price

â”œâ”€â”€ opened_time

â”œâ”€â”€ stop_order_id

â”œâ”€â”€ stop_price

â”œâ”€â”€ target_order_id

â”œâ”€â”€ target_price

â”œâ”€â”€ exit_execution_id

â”œâ”€â”€ exit_price

â”œâ”€â”€ exit_reason

â”œâ”€â”€ closed_time

â””â”€â”€ execution_cost_record_id

Then Claude Code doesn't have to invent fields.

4. We need one canonical enum registry

This is another thing I want locked before implementation.

For example:

Direction

#### LONG

#### SHORT

Position state

#### OPEN

#### CLOSED

Exit reason

#### STOP_LOSS

#### TARGET

#### STOP_LOSS_GAP

#### OHLC_AMBIGUOUS_STOP_PRIORITY

Trade result

#### WIN

#### LOSS

#### BREAKEVEN

Commission models

#### PER_UNIT

#### PER_CONTRACT

#### PERCENT_NOTIONAL

#### FIXED_ORDER

#### FIXED_TRADE

#### ZERO

Slippage models

#### NONE

#### FIXED_TICKS

#### FIXED_PRICE

#### PERCENTAGE

#### INSTRUMENT_SPECIFIC

#### VOLATILITY_DEPENDENT

And so on.

No duplicate names and no slightly different names for the same concept.

5. We need the error/invalidation system

This is one of the biggest things missing before implementation.

For example, we've already established:

#### PROTECTIVE_ORDER_INVALID

#### TARGET_ORDER_INVALID

#### ACCOUNTING_ERROR

But we need a complete deterministic error taxonomy.

Something like:

#### SETUP_INVALID

#### ENTRY_INVALID

#### ENTRY_NOT_FILLED

#### POSITION_SIZE_INVALID

#### PROTECTIVE_ORDER_INVALID

#### TARGET_ORDER_INVALID

#### EXIT_RESOLUTION_INVALID

#### EXECUTION_COST_INVALID

#### POSITION_LIFECYCLE_INVALID

#### ACCOUNTING_ERROR

#### PERFORMANCE_DATA_INVALID

And each error needs:

#### ERROR CODE

#### WHEN IT OCCURS

#### WHETHER TRADE IS BLOCKED

#### WHETHER POSITION IS CLOSED

#### WHETHER RECORD IS CREATED

#### WHAT MODULE OWNS IT

6. We need the invariant/test specification

This is critical before Claude Code.

We're not just giving Claude a description of the strategy.

We're giving it a mechanical specification that should be testable.

For example:

Position invariant

CLOSED â†’ cannot reopen

Quantity invariant

Quantity > 0

Stop invariant

#### LONG:

Stop < Entry

#### SHORT:

Stop > Entry

Target invariant

#### LONG:

Target > Entry

#### SHORT:

Target < Entry

Accounting invariant

NetPnL = GrossPnL - ExplicitCashCosts

Equity invariant

PostTradeEquity =

PreTradeEquity + NetPnL

R invariant

ActualRisk > 0

OCO invariant

Exactly one terminal exit

One-position invariant

OpenPositionCount <= 1

These should eventually become automated unit/integration tests, not just documentation.

7. We need deterministic examples

I want Claude Code to have a collection of known-answer test cases.

For example:

Long winner

Entry = 5018

Exit = 5026

Quantity = 1

Multiplier = 1

Costs = 2

Risk = 8

Gross = +8

Net = +6

Gross R = +1.00R

Net R = +0.75R

Result = WIN

Long loser

Entry = 5018

Exit = 5010

Quantity = 1

Multiplier = 1

Costs = 2

Risk = 8

Gross = -8

Net = -10

Gross R = -1.00R

Net R = -1.25R

Result = LOSS

And especially the difficult cases:

SL and TP in same 1M candle

tick data resolves SL first

tick data resolves TP first

gap-through stop

target gap

entry and exit on same candle

entry occurs after price already touched SL

zero trades

one trade

all winners

all losers

no losing trades â†’ profit factor behavior

zero-cost configuration

quantity rounding

contract multiplier

These become our golden tests.

8. We need to resolve any remaining architecture above #27

This is probably the most important thing I need from you after #29.7.2.

We've been locking the execution/accounting architecture, but #27 and #28 are upstream dependencies.

Before Claude implements #29, it needs the final authoritative definitions of:

#27 SETUP

#28 ENTRY ZONE

Including the exact definitions you were recently locking for things such as:

Bullish FVG

Bearish FVG

Equilibrium

OTE swing selection

Trend/bias

Order-flow respect

Reversal

Approaching LRL

Indicator rules

#### CISD

MSS/BOS/etc., where applicable

The key is that these cannot remain ambiguous.

For example:

"Bullish FVG"

must have an exact mechanical test Claude can execute, not just a conceptual explanation.

9. We need the actual implementation contract

Only after the above is locked should we create the document Claude Code receives.

I want the final package to look approximately like:

#### TRADING ENGINE SPECIFICATION

â”‚

â”œâ”€â”€ 00 â€” SYSTEM ARCHITECTURE

â”‚

â”œâ”€â”€ 01 â€” DEFINITIONS

â”‚

â”œâ”€â”€ 02 â€” MARKET DATA

â”‚

â”œâ”€â”€ 03 â€” INSTRUMENT MODEL

â”‚

â”œâ”€â”€ 04 â€” MARKET STRUCTURE

â”‚

â”œâ”€â”€ 05 â€” LIQUIDITY

â”‚

â”œâ”€â”€ 06 â€” FVG / IFVG

â”‚

â”œâ”€â”€ ...

â”‚

â”œâ”€â”€ 27 â€” SETUP

â”œâ”€â”€ 28 â€” ENTRY ZONE

â”‚

â”œâ”€â”€ 29.1 â€” ENTRY EXECUTION

â”œâ”€â”€ 29.2 â€” POSITION SIZING

â”œâ”€â”€ 29.3 â€” PROTECTIVE ORDERS

â”œâ”€â”€ 29.4 â€” EXIT RESOLUTION

â”œâ”€â”€ 29.5 â€” EXECUTION COSTS

â”œâ”€â”€ 29.6 â€” POSITION LIFECYCLE

â”œâ”€â”€ 29.7.1 â€” TRADE ACCOUNTING

â”œâ”€â”€ 29.7.2 â€” PERFORMANCE STATISTICS

â”‚

â”œâ”€â”€ ENUMS

â”œâ”€â”€ DATA MODELS

â”œâ”€â”€ ERROR CODES

â”œâ”€â”€ INVARIANTS

â”œâ”€â”€ STATE MACHINES

â”œâ”€â”€ GOLDEN TEST CASES

â””â”€â”€ IMPLEMENTATION RULES

That becomes the source of truth.

#29.7.2.11 â€” Exact Mechanical Risk-Adjusted Performance Statistics
This layer should remain strictly analytical and read-only. It consumes finalized performance history and produces standardized risk-adjusted statistics. It must never alter trades, accounting, equity, or prior statistics.
The key principle is:
Risk-adjusted metrics are calculated from finalized, point-in-time equity/return observationsâ€”not from reconstructed trade assumptions.

Ownership

#29.7.2.11 OWNS
Return series used for risk-adjusted calculations
Mean return
Return volatility
Downside deviation
Sharpe Ratio
Sortino Ratio
Calmar Ratio
Risk-adjusted metric eligibility
Annualization
Edge-case handling
No-look-ahead behavior
Historical metric observations
#29.7.2.11 DOES NOT OWN
Trade execution
Position sizing
P&L
Equity
Drawdown calculation
Trade classification
Slippage
Commissions
Trade selection
Setup qualification
It consumes the finalized outputs of those layers.
2. Canonical Return Series

The engine needs one canonical return series.
Use periodic equity returns, not raw trade R, as the canonical risk-adjusted return input.
For consecutive equity observations:
[
Return_t =
\frac{Equity_t}{Equity_{t-1}}-1
]where:
Equity_t = finalized equity at observation t
Equity_(t-1) = immediately preceding equity observation.
Therefore:
Equity
100,000
101,000
100,500
102,000
produces:
+1.0000%
-0.4950%
+1.4925%
This prevents the risk-adjusted layer from inventing a separate return definition.
3. Return Observation Requirements

A return observation exists only when:
PreviousEquity exists
AND
CurrentEquity exists
AND
PreviousEquity > 0
AND
CurrentEquity is finite
The first equity observation produces no return, because there is no preceding equity observation.
Therefore:
Equity observations: 1
Return observations: 0
4. Canonical Time Basis

For risk-adjusted statistics, the canonical period is:
Daily finalized account equity.

The daily equity series established by #29.7.2.9 becomes the primary risk-adjusted return series.
This avoids mixing irregular trade durations with periodic return statistics.
Therefore:
Trade accounting
â†“
Daily finalized equity
â†“
Daily return series
â†“
Risk-adjusted statistics
5. Annualization

The canonical annualization factor is:
252 trading days per year.

Therefore:
[
AnnualizedReturn = MeanDailyReturn \times 252
]and:
[
AnnualizedVolatility =
StdDev(DailyReturns)\times\sqrt{252}
]This is the fixed base convention.
The engine must not silently switch between:
252
365
52
12
depending on the asset.
If another frequency is eventually supported, it must be explicitly configured as a separate specification.
6. Standard Deviation

Use sample standard deviation for the canonical Sharpe calculation.
For n daily returns:
[
\sigma =
\sqrt{
\frac{
\sum_{i=1}^{n}(r_i-\bar r)^2
}{
n-1
}
}
]Therefore:
n < 2 â†’ volatility = NULL
n â‰¥ 2 â†’ volatility is calculable.
This prevents a single observation from falsely producing zero volatility.
7. Risk-Free Rate

The canonical base model uses:
Risk-free rate = 0%

Therefore:
[
ExcessReturn_t = Return_t
]and:
[
Sharpe =
\frac{\bar r}{\sigma}\sqrt{252}
]This avoids introducing an external interest-rate data dependency into the core engine.
A non-zero risk-free rate can later be introduced as an explicit external parameter, but it must never silently change the canonical calculation.
8. Exact Mechanical Sharpe Ratio

Definition
[
Sharpe =
\frac{\bar r-r_f}{\sigma}
\sqrt{252}
]With the locked base assumption:
[
r_f=0
]therefore:
[
\boxed{
Sharpe =
\frac{\bar r}{\sigma}\sqrt{252}
}
]Edge cases
Condition Sharpe
0 returns NULL
1 return NULL
Mean = 0, volatility > 0 0
Mean > 0, volatility > 0 positive
Mean < 0, volatility > 0 negative
Volatility = 0, mean > 0 +âˆž
Volatility = 0, mean < 0 -âˆž
Volatility = 0, mean = 0 NULL

The final case is undefined rather than zero because the ratio is 0/0.
9. Downside Return

For Sortino, only negative returns contribute to downside risk.
Define:
[
d_t = \min(Return_t,0)
]Therefore:
+2% â†’ 0
+1% â†’ 0
0% â†’ 0
-1% â†’ -1%
-3% â†’ -3%
Positive returns do not contribute to downside deviation.
10. Downside Deviation

The canonical downside deviation is:
[
DD =
\sqrt{
\frac{
\sum_{i=1}^{n}d_i^2
}{
n
}
}
]where:
[
d_i=\min(r_i,0)
]The denominator is n, not n-1.
This is intentional: downside deviation measures downside observations relative to the zero target rather than estimating sample variance around a sample mean.
Annualized downside deviation:
[
AnnualizedDownsideDeviation =
DD\sqrt{252}
]11. Exact Mechanical Sortino Ratio
With a zero risk-free/minimum acceptable return:
[
\boxed{
Sortino =
\frac{\bar r}{DD}\sqrt{252}
}
]Edge cases
Condition Sortino
0 returns NULL
1 return NULL
Downside deviation > 0 normal calculation
Mean = 0, DD > 0 0
Mean > 0, DD = 0 +âˆž
Mean < 0, DD = 0 -âˆž
Mean = 0, DD = 0 NULL

A dataset with no negative returns therefore has zero downside deviation.
The engine must not arbitrarily report Sortino = 0 in that case.
12. Maximum Drawdown Input

Calmar requires maximum drawdown.
#29.7.2.11 does not recalculate drawdown.
It consumes:
MaximumDrawdown
from #29.7.2.7.
This preserves ownership.
13. Exact Mechanical Calmar Ratio

The canonical Calmar definition is:
[
\boxed{
Calmar =
\frac{AnnualizedReturn}{MaximumDrawdownPercentage}
}
]where:
[
AnnualizedReturn =
\bar r \times 252
]and:
[
MaximumDrawdownPercentage =
\frac{PeakEquity-TroughEquity}{PeakEquity}
]using the finalized #29.7.2.7 maximum drawdown result.
14. Calmar Edge Cases

Condition Calmar
No returns NULL
Maximum drawdown > 0 normal calculation
Annualized return = 0, DD > 0 0
Positive annualized return, DD = 0 +âˆž
Negative annualized return, DD = 0 -âˆž
Annualized return = 0, DD = 0 NULL

The engine must never convert an undefined 0/0 into zero.
15. Negative Equity

Risk-adjusted percentage-return calculations require positive starting equity.
Therefore:
PreviousEquity <= 0
â†“
Return = NULL
The observation is not silently transformed into a percentage return.
If the account reaches zero or negative equity, the risk-adjusted return series is considered non-computable from that point forward unless a separate explicitly defined account-return methodology is introduced.
This prevents meaningless percentage returns such as:
[
\frac{100}{0}-1
]from entering the statistics.
16. Zero Equity

Exactly:
PreviousEquity = 0
â†’ percentage return undefined
â†’ return = NULL
No division by zero is permitted.
17. Missing Equity Observations

Missing observations are not fabricated.
The engine must not:
interpolate equity,
assume zero return,
forward-fill equity,
reconstruct missing observations from trades.
Only finalized observations may be used.
18. Duplicate Observations

Duplicate observations with the same:
timestamp
+
equity observation ID
are invalid.
The engine must use the canonical immutable observation identifier.
If duplicate records represent the exact same observation:
retain one canonical record
ignore duplicate
If two observations have the same timestamp but different finalized values, this is a data integrity error, not a reason to choose one arbitrarily.
19. Chronological Ordering

Returns are calculated strictly in finalized chronological order:
Equity[t-1]
â†“
Equity[t]
â†“
Return[t]
No future equity observation can participate in an earlier statistic.
20. Point-in-Time / No-Look-Ahead Rule

At time T:
Risk-adjusted statistics may use only finalized equity observations available at or before T.

For example:
Monday
Tuesday
Wednesday
A Tuesday statistic cannot include Wednesday's return.
A Monday statistic cannot be revised merely because later trades become available.
21. Historical Immutability

Once a risk-adjusted statistic has been finalized for observation time T:
Statistic[T]
is immutable.
Later observations may create:
Statistic[T+1]
Statistic[T+2]
...
but may not rewrite:
Statistic[T]
unless an upstream finalized accounting record itself is formally corrected under an explicit versioning mechanism.
22. Minimum Data Requirements

The engine should expose explicit sample counts.
For example:
RiskAdjustedStatistics {
return_observation_count
mean_return
volatility
downside_deviation

annualized_return

annualized_volatility

annualized_downside_deviation

sharpe

sortino

calmar

maximum_drawdown

maximum_drawdown_pct

}
No metric should appear to be valid merely because the field exists.
23. Exact Calculation Order

The engine executes:
FINALIZED EQUITY OBSERVATIONS
â†“
Chronological validation
â†“
Remove invalid/duplicate observations
â†“
Construct daily return series
â†“
Calculate mean return
â†“
Calculate sample volatility
â†“
Calculate downside deviation
â†“
Annualize
â†“
Sharpe
â†“
Sortino
â†“
Consume Maximum Drawdown
â†“
Calmar
â†“
Immutable RiskAdjustedStatistics
24. Important Separation: R vs Percentage Return

The engine must not substitute Net R for percentage equity return in Sharpe/Sortino/Calmar.
These remain different analytical quantities:
Net R

trade-level risk-normalized performance

Percentage Return

account-equity change between periodic observations
Therefore:
expectancy â†’ Net R
profit factor â†’ P&L
cumulative R â†’ Net R
Sharpe â†’ periodic equity returns
Sortino â†’ periodic equity returns
Calmar â†’ annualized return / maximum drawdown
This keeps each statistic mathematically coherent.
25. Risk-Adjusted Statistics Are Read-Only

The following invariant is absolute:
Risk-adjusted statistics can observe history but can never modify history.

They cannot:
change P&L
change equity
change drawdown
change trade classification
change execution
change costs
change R
reopen trades
reject trades
alter setup qualification.
26. Exact Object

RiskAdjustedStatistics {

observation_time

return_observation_count

mean_daily_return

volatility_daily

volatility_annualized

downside_deviation_daily

downside_deviation_annualized

annualized_return

sharpe_ratio

sortino_ratio

maximum_drawdown_pct

calmar_ratio

source_equity_series_id

source_drawdown_series_id

calculation_specification_id

finalized

immutable

}
27. Hard Invariants

Invariant 1
Risk-adjusted statistics use only finalized observations.
Invariant 2
The first equity observation produces no return.
Invariant 3
Sharpe uses sample standard deviation.
Invariant 4
Sortino uses downside deviation relative to zero.
Invariant 5
Annualization uses 252 trading periods.
Invariant 6
Risk-free rate is 0% in the canonical model.
Invariant 7
Sharpe/Sortino do not use trade R as their return series.
Invariant 8
Calmar consumes the previously finalized maximum drawdown.
Invariant 9
Zero/negative equity cannot produce an invalid percentage return through division by zero.
Invariant 10
Undefined ratios are NULL, not silently converted to zero.
Invariant 11
No future observation may influence a historical statistic.
Invariant 12
The analytics layer cannot mutate upstream accounting.
28. Final Locked Definition

#29.7.2.11 â€” Exact Mechanical Risk-Adjusted Performance Statistics is the read-only analytical layer that calculates risk-adjusted performance from the finalized daily equity series and finalized maximum drawdown. The canonical metrics are Sharpe Ratio, Sortino Ratio, and Calmar Ratio. Daily equity returns are calculated from consecutive finalized positive equity observations, Sharpe uses sample standard deviation, Sortino uses downside deviation relative to a zero target, annualization uses 252 trading days, and the canonical risk-free rate is 0%. Calmar uses annualized return divided by the finalized maximum drawdown percentage. Undefined or mathematically non-computable cases return NULL or explicitly defined infinities rather than being silently converted to zero. All calculations are chronological, point-in-time, immutable, and incapable of modifying upstream trade or accounting records.**

That locks #29.7.2.11 without yet introducing confidence intervals, Monte Carlo, statistical significance, or strategy-level conclusions. Those should remain separate higher-order analytics rather than contaminating the atomic performance layer.

Show more

Locked.

#29.7.2.11 â€” Exact Mechanical Risk-Adjusted Performance Statistics is now the next atomic performance layer in the architecture.

The critical separation is preserved:

Expectancy â†’ Net R

Profit Factor â†’ P&L

Cumulative performance â†’ Net R / P&L

Sharpe â†’ periodic equity returns

Sortino â†’ periodic equity returns

Calmar â†’ annualized return Ã· finalized maximum drawdown

Drawdown itself remains owned by #29.7.2.7

Equity remains upstream

No confidence intervals, Monte Carlo, significance testing, or strategy conclusions are introduced here

Locked chain

#29.7.1

#### INDIVIDUAL TRADE ACCOUNTING

â†“

#29.7.2.1

#### RETURN STATISTICS

â†“

#29.7.2.2

#### EXPECTANCY

â†“

#29.7.2.3

#### PROFIT FACTOR

â†“

#29.7.2.4

#### CUMULATIVE P&L / R

â†“

#29.7.2.5

#### EQUITY CURVE

â†“

#29.7.2.6

#### DRAWDOWN

â†“

#29.7.2.7

#### STREAK STATISTICS

â†“

#29.7.2.8

#### TIME-SERIES / PERIOD STATISTICS

â†“

#29.7.2.9

#### DISTRIBUTION STATISTICS

â†“

#29.7.2.10

#### RISK-ADJUSTED PERFORMANCE STATISTICS

â†“

#29.7.2.11

[LOCKED]

One numbering issue is worth preserving from the sequence: your supplied definitions have Streak = .8, Time-Series = .9, Distribution = .10, Risk-Adjusted = .11. So the architecture should use that numbering consistently going forward.

#29.7.2.11 is locked.

Ready for #29.7.2.12.

whats next

Next is #29.7.2.12.

At this point, I would not jump directly into strategy conclusions. We should continue building the atomic performance layer in the same mechanical, read-only style.

Recommended next layer

#29.7.2.12 â€” Exact Mechanical Recovery / Time-to-Recovery Statistics

This would measure how the account/equity curve behaves after drawdowns, without interpreting why the drawdown happened.

It would mechanically define things such as:

Recovery Point

Recovery Time

Recovery Duration

Maximum Recovery Time

Average Recovery Time

Number of Drawdowns

Number of Recovered Drawdowns

Number of Unrecovered Drawdowns

Recovery Ratio

Peak-to-Recovery observations

Time underwater

Current underwater state

Current recovery status

Point-in-time recovery statistics

And it should consume the already-locked:

#29.7.2.5

#### EQUITY CURVE

â†“

#29.7.2.7

#### DRAWDOWN

â†“

#29.7.2.12

#### RECOVERY STATISTICS

Why this should come next

You've already established:

#### P&L / R

â†“

Equity

â†“

Drawdown

â†“

Streaks

â†“

Time-Series

â†“

Distributions

â†“

Risk-Adjusted Performance

Recovery statistics naturally extend Drawdown without contaminating it.

Importantly, #29.7.2.12 should not decide whether a strategy is good or bad. It only answers mechanically:

How long and how far did the account take to recover from each finalized drawdown?

Then, after recovery, we can move into other higher-order statistical layers.

Proposed next architecture

#29.7.2.11

#### RISK-ADJUSTED PERFORMANCE

â†“

#29.7.2.12

#### RECOVERY STATISTICS

â†“

#29.7.2.13

#### UNDERWATER / TIME-UNDERWATER STATISTICS

â†“

#29.7.2.14

#### TRADE SEQUENCE / PATH STATISTICS

â†“

#29.7.2.15

#### STRATEGY-LEVEL AGGREGATION

I would lock each one individually, exactly like you've been doing, rather than combining them.

So the immediate next step is #29.7.2.12 â€” Exact Mechanical Recovery Statistics.

Exact Ownership

#29.7.2.12 OWNS
Recovery-point identification
Recovery status
Recovery duration
Time-to-recovery
Maximum recovery duration
Average recovery duration
Number of drawdown episodes
Number of recovered drawdowns
Number of unrecovered drawdowns
Current recovery state
Current underwater state
Peak-to-recovery measurements
Recovery statistics
Point-in-time recovery statistics
#29.7.2.12 DOES NOT OWN
P&L
Equity calculation
Drawdown calculation
Trade classification
Trade execution
Position lifecycle
Setup qualification
Maximum drawdown calculation
Those already belong upstream.
2. What Is a Drawdown Episode?

A drawdown episode begins when finalized equity falls below the applicable prior peak.
Formally:
[
Equity_t < PeakEquity_t
]The episode begins at the peak observation immediately preceding the first observation below that peak.
Example:
Equity

100,000 â† Peak
101,000 â† New Peak
100,500 â† Drawdown begins
99,000
100,200
101,000 â† Recovery
The relevant drawdown episode is:
Peak = 101,000
Trough = 99,000
Recovery = 101,000
3. Peak Observation

The recovery engine consumes the peak already established by #29.7.2.7.
It must not create a competing peak definition.
Therefore:
Drawdown.peak_equity
Drawdown.peak_time
are authoritative.
4. Drawdown Start

A drawdown episode begins at:
The first finalized equity observation strictly below its preceding peak.

Therefore:
Peak:
101,000

Next:
101,000
does not begin a drawdown.
Likewise:
101,000
100,999.99
does begin one.
5. Trough

The trough is:
The lowest finalized equity observation occurring between drawdown start and recovery.

Example:
101,000 Peak
100,000
98,500
97,200 â† Trough
98,000
99,500
101,000 Recovery
Therefore:
TroughEquity = 97,200
TroughTime = timestamp of 97,200
If several observations have exactly the same minimum equity, the first occurrence is the canonical trough.
This makes the result deterministic.
6. Recovery Point

A drawdown is recovered when:
[
Equity_t \ge PeakEquity
]Therefore, returning exactly to the prior peak constitutes recovery.
Example:
Peak = 100,000
Trough = 95,000
Recovery = 100,000
is fully recovered.
The engine does not require a new all-time high.
7. Recovery Point Timestamp

The recovery timestamp is:
The earliest finalized equity observation at or above the drawdown's peak equity following the trough.

Example:
100,000 Peak
97,000
94,000 Trough
96,000
99,000
100,000 â† Recovery
101,000
Recovery time = timestamp of the 100,000 observation.
The later 101,000 observation is a new peak, not the recovery point.
8. Recovery Duration

Recovery duration is:
[
RecoveryDuration =
RecoveryTime - DrawdownStartTime
]This measures how long the account remained below its prior peak.
For example:
Drawdown start:
Monday 10:00

Recovery:
Thursday 14:00
Recovery duration:
3 days 4 hours
The calculation uses actual elapsed time between finalized timestamps.
9. Time-to-Recovery

For this layer:
Time-to-Recovery = Recovery Duration.

There should not be two competing definitions.
Therefore:
TimeToRecovery

RecoveryTime - DrawdownStartTime
10. Recovery Depth

The recovery layer may expose the already-established drawdown magnitude:
[
RecoveryDepth =
PeakEquity - TroughEquity
]However, it must consume the authoritative drawdown value from #29.7.2.7 rather than independently redefining it.
11. Recovery Percentage

Likewise:
[
RecoveryDepthPct =
\frac{PeakEquity-TroughEquity}
{PeakEquity}
]This is simply the finalized drawdown percentage associated with the episode.
It is informational, not a new drawdown calculation.
12. Recovered vs Unrecovered

Each drawdown episode has exactly one of two states:
RECOVERED
UNRECOVERED
RECOVERED
A finalized observation has reached:
[
Equity \ge PeakEquity
]UNRECOVERED
The available finalized history ends while:
[
Equity < PeakEquity
]No future recovery may be assumed.
13. Current Recovery State

At any point in time, the account can be:
AT_PEAK
IN_DRAWDOWN
RECOVERED
However, for the active episode, the more precise state is:
NO_ACTIVE_DRAWDOWN
UNDERWATER
RECOVERED
Once recovery occurs, that drawdown episode becomes immutable.
14. Recovery Status at Time T

At any historical observation T:
Recovery status may use only equity observations through T.

Example:
Monday:
Peak 100k

Tuesday:
98k

Wednesday:
96k
On Wednesday:
Status = UNRECOVERED
Even if Thursday eventually reaches 100k.
The Wednesday historical statistic must not retroactively say "recovered."
15. Number of Drawdowns

A drawdown episode is counted once when it begins.
Therefore:
[
NumberOfDrawdowns =
\text{count of distinct drawdown episodes}
]A prolonged drawdown with many lower lows remains:
1 drawdown
not:
10 drawdowns
16. Number of Recovered Drawdowns

[
RecoveredDrawdowns =
count(episodes\ with\ RecoveryTime)
]Only finalized recoveries count.
17. Number of Unrecovered Drawdowns

[
UnrecoveredDrawdowns =
NumberOfDrawdowns-RecoveredDrawdowns
]An active drawdown at the end of available history is unrecovered.
18. Average Recovery Time

Average recovery duration is calculated only across recovered drawdowns.
[
AverageRecoveryTime =
\frac{
\sum RecoveryDuration_i
}{
NumberOfRecoveredDrawdowns
}
]Unrecovered drawdowns are not assigned an artificial duration and are excluded from the numerator and denominator.
If:
RecoveredDrawdowns = 0
then:
AverageRecoveryTime = NULL
19. Maximum Recovery Time

Maximum recovery duration is:
[
MaximumRecoveryTime =
max(RecoveryDuration_i)
]using recovered episodes only.
If there are no recovered drawdowns:
MaximumRecoveryTime = NULL
An unrecovered drawdown does not receive an artificially infinite recovery duration.
Instead, it is explicitly recorded as:
recovered = FALSE
20. Longest Unrecovered Duration

This should also be exposed separately because treating an unrecovered drawdown as infinity would make the normal maximum recovery-time statistic unusable.
For an active unrecovered episode:
[
CurrentUnrecoveredDuration =
CurrentTime-DrawdownStartTime
]Therefore the engine can report:
MaximumRecoveredRecoveryTime
CurrentUnrecoveredDuration
without mixing the two concepts.
21. Recovery Ratio

The term "recovery ratio" is potentially ambiguous, so we need one exact definition.
Lock it as:
[
\boxed{
RecoveryRatio =
\frac{RecoveredDrawdowns}
{TotalDrawdowns}
}
]Thus:
10 drawdowns
8 recovered

RecoveryRatio = 0.80
or:
80%
Edge cases
0 drawdowns â†’ NULL
It must not be reported as 0%, because no drawdown population exists from which to calculate a recovery rate.
22. Peak-to-Recovery Observation

Each recovered episode must retain:
PeakEquity
PeakTime
TroughEquity
TroughTime
RecoveryEquity
RecoveryTime
Recovery equity is necessarily:
[
RecoveryEquity \ge PeakEquity
]because recovery occurs at or above the prior peak.
For the canonical recovery point, the engine records the first qualifying observation, so normally:
RecoveryEquity = PeakEquity
unless the available data jumps/gaps above the peak.
23. Gap Across Recovery

Example:
Peak = 100,000

99,000
98,000
103,000 â† first observation above peak
Recovery occurs at:
103,000
The engine must not invent a 100,000 observation.
Therefore:
RecoveryEquity = 103,000
RecoveryTime = timestamp of 103,000
24. Equal-Equity Behavior

If equity equals the prior peak:
Peak = 100,000
Current = 100,000
that is recovery.
If equity remains at the peak without first falling below it:
100,000
100,000
100,000
there is no drawdown and therefore no recovery event.
25. Breakeven Trades

A breakeven trade produces:
Equity unchanged
Therefore it:
does not create a drawdown
does not recover a drawdown by itself unless equity was already exactly at/above the peak
does not alter recovery duration except through its timestamp spacing
does not create a new peak
26. New Peak During Recovery

Suppose:
100,000 Peak
95,000 Trough
98,000
101,000
The first recovery occurs at:
101,000
Then 101,000 becomes a new peak according to the equity/drawdown engine.
It does not create another recovery event for the same drawdown.
The original episode is permanently:
Peak: 100,000
Trough: 95,000
Recovered: 101,000
27. What Happens After Recovery?

The recovered episode becomes immutable.
A future decline from the new peak creates a new drawdown episode.
Example:
100k Peak
95k Trough
101k Recovery/New Peak
98k
The second decline belongs to a new episode:
Episode #1:
100k â†’ 95k â†’ 101k

Episode #2:
101k â†’ ...
28. Nested Drawdowns

There is only one active drawdown episode per equity peak-to-recovery cycle.
Lower lows inside that episode do not create additional drawdowns.
Therefore:
100k
98k
96k
94k
95k
93k
99k
100k
is:
1 drawdown episode
with:
Peak = 100k
Trough = 93k
Recovery = 100k
29. Zero-Trade Dataset

With no finalized trades:
Drawdowns = 0
RecoveredDrawdowns = 0
UnrecoveredDrawdowns = 0
RecoveryRatio = NULL
AverageRecoveryTime = NULL
MaximumRecoveryTime = NULL
No artificial recovery episode is created from the initial account equity.
30. Initial Equity

The initial equity observation is a starting reference, not a drawdown.
Example:
Initial Equity = $100,000
If the next observation is:
$99,000
then the initial $100,000 can serve as the initial peak, and the decline creates the first drawdown.
This is consistent with #29.7.2.7's rule that initial equity can establish the first peak.
31. No-Look-Ahead Rule

At timestamp T, the engine knows only:
Equity observations <= T
Therefore:
CurrentRecoveryStatus[T]
CurrentUnderwaterDuration[T]
RecoveredDrawdowns[T]
UnrecoveredDrawdowns[T]
must all be calculated from information available at T.
Future recovery cannot be projected backward.
32. Historical Immutability

Once an episode is finalized as:
RECOVERED
its:
peak
trough
recovery
duration
recovery classification
cannot change.
An active:
UNRECOVERED
episode may receive new observations as time advances, but historical observations remain unchanged.
33. Exact Recovery Object

RecoveryEpisode {

id

peak_equity

peak_time

drawdown_start_time

trough_equity

trough_time

recovery_equity

recovery_time

recovery_depth

recovery_depth_pct

recovery_duration

recovered

status

source_drawdown_id

creation_time

finalized_time

immutable

}
For an unrecovered episode:
recovery_equity = NULL
recovery_time = NULL
recovery_duration = NULL
recovered = FALSE
The current elapsed underwater duration can be calculated separately.
34. Aggregate Recovery Statistics Object

RecoveryStatistics {

total_drawdowns

recovered_drawdowns

unrecovered_drawdowns

recovery_ratio

average_recovery_duration

maximum_recovery_duration

current_recovery_status

current_unrecovered_duration

current_drawdown_id

finalized_observation_time

source_equity_series_id

source_drawdown_series_id

immutable

}
35. Exact State Machine

NO_DRAWDOWN
â”‚
â”‚ Equity < Peak
â–¼
DRAWDOWN_ACTIVE
â”‚
â”œâ”€â”€ New lower equity
â”‚ â†“
â”‚ UPDATE TROUGH
â”‚
â”œâ”€â”€ Equity remains below peak
â”‚ â†“
â”‚ REMAIN ACTIVE
â”‚
â””â”€â”€ Equity >= Peak
â†“
RECOVERED
â”‚
â†“
EPISODE IMMUTABLE
â”‚
â†“
NEW PEAK MAY FORM
36. Exact Algorithm

Conceptually:
FOR each finalized equity observation in chronological order:

obtain authoritative drawdown state

IF no active drawdown:

IF current_equity < current_peak_equity:

create RecoveryEpisode

status = DRAWDOWN_ACTIVE

#### ELSE:

IF current_equity < trough_equity:

update trough

IF current_equity >= peak_equity:

recovery_equity = current_equity

recovery_time = current_time

recovery_duration =

current_time - drawdown_start_time

recovered = TRUE

status = RECOVERED

finalize episode

allow new peak logic to begin

AFTER processing:

total_drawdowns =

count(all episodes)

recovered_drawdowns =

count(recovered episodes)

unrecovered_drawdowns =

total - recovered

recovery_ratio =

recovered / total

Hard Invariants

Invariant 1
Every recovery episode originates from an actual drawdown.
Invariant 2
A drawdown episode is counted once.
Invariant 3
Nested lower lows do not create additional drawdown episodes.
Invariant 4
Recovery requires:
[
Equity \ge PeakEquity
]Invariant 5
Returning exactly to the prior peak counts as recovery.
Invariant 6
The first qualifying recovery observation is canonical.
Invariant 7
Unrecovered drawdowns are never assigned an artificial recovery time.
Invariant 8
Average and maximum recovery time use recovered episodes only.
Invariant 9
Future recovery cannot alter a historical point-in-time recovery status.
Invariant 10
A recovered episode cannot reopen.
Invariant 11
A subsequent decline from a new peak is a new drawdown episode.
Invariant 12
Recovery statistics cannot modify equity or drawdown records.
38. Final Locked Definition

#29.7.2.12 â€” Exact Mechanical Recovery / Time-to-Recovery Statistics is the read-only analytical layer that consumes the finalized equity curve and authoritative drawdown episodes to determine exactly how and when each drawdown recovers. A drawdown begins when finalized equity falls strictly below its preceding peak and is recovered at the first subsequent finalized observation whose equity is greater than or equal to that peak. Recovery duration is the elapsed time from drawdown initiation to that first recovery observation. Lower lows within the same peak-to-recovery cycle do not create additional drawdowns. Recovered and unrecovered episodes are explicitly distinguished; unrecovered episodes receive no artificial recovery duration. Average and maximum recovery duration are calculated only from recovered episodes. Recovery ratio equals recovered drawdowns divided by total drawdowns and is NULL when no drawdowns exist. All calculations are chronological, point-in-time, immutable, and incapable of modifying upstream accounting, equity, or drawdown history.**

That gives us a clean separation:
#29.7.2.6
EQUITY CURVE
â†“
#29.7.2.7
DRAWDOWN
â†“
#29.7.2.12
RECOVERY
â†“
HOW LONG DID THE ACCOUNT TAKE TO GET BACK?
The next proposed primitive, #29.7.2.13 â€” Exact Mechanical Underwater / Time-Underwater Statistics, can therefore focus specifically on the amount of time equity remains below its applicable peak, without redefining recovery or drawdown.

Auto

Show more

Yes. #29.7.2.12 is mechanically complete and locked.

The important separation is now:

#29.7.2.6  EQUITY CURVE

â†“

#29.7.2.7  DRAWDOWN

â†“

#29.7.2.12 RECOVERY / TIME-TO-RECOVERY

It answers one specific question:

After entering a drawdown, how long did it take to return to the applicable prior peak?

It does not redefine equity, drawdown, or maximum drawdown.

One important distinction going forward

Your proposed #29.7.2.13 Underwater / Time-Underwater Statistics should be kept separate from recovery:

Recovery: measures the elapsed time from drawdown start â†’ recovery.

Underwater: measures the account's state/time spent below its applicable peak, including an active unrecovered period.

Recovery duration: belongs to a completed recovery episode.

Current underwater duration: can exist even when recovery has not occurred.

That gives us a clean analytical separation rather than having #29.7.2.12 and .13 calculate the same thing under different names.

Current locked architecture

#29.7.1

#### INDIVIDUAL TRADE ACCOUNTING

â†“

#29.7.2.1

#### RETURN STATISTICS

â†“

#29.7.2.2

#### EXPECTANCY

â†“

#29.7.2.3

#### PROFIT FACTOR

â†“

#29.7.2.4

#### CUMULATIVE P&L / R

â†“

#29.7.2.5

#### EQUITY CURVE

â†“

#29.7.2.6

#### DRAWDOWN

â†“

#29.7.2.7

#### STREAK STATISTICS

â†“

#29.7.2.8

#### TIME-SERIES / PERIOD STATISTICS

â†“

#29.7.2.9

#### DISTRIBUTION STATISTICS

â†“

#29.7.2.10

#### RISK-ADJUSTED PERFORMANCE

â†“

#29.7.2.11

#### RECOVERY / TIME-TO-RECOVERY

â†“

#29.7.2.12

[LOCKED]

Again, the displayed numbering in the earlier architecture was offset; the actual definitions you've supplied establish Recovery as #29.7.2.12. From here, we should preserve your explicit numbering rather than introducing another renumbering.

Next: #29.7.2.13 â€” Exact Mechanical Underwater / Time-Underwater Statistics.

#29.7.2.13 â€” Exact Mechanical Underwater / Time-Underwater Statistics
This layer should sit directly on top of the finalized Equity Curve and Drawdown objects.
Its sole purpose is to answer:
At each point in finalized trading history, is the account below its most recent equity peak, and if so, for how long and by how much?

It does not calculate or reinterpret P&L, drawdown magnitude, recovery, or trade results. Those are upstream primitives.
29.7.2.13 â€” OWNERSHIP
Inputs
#29.7.2.6 Equity Curve
#29.7.2.7 Drawdown
#29.7.2.12 Recovery Statistics may be referenced for recovery status, but underwater status itself is determined from equity versus the applicable peak.
The layer may consume:
timestamp
equity
peak_equity
drawdown
drawdown_pct
drawdown_episode_id
recovery_time
recovered
finalized-trade status
It may calculate
underwater status
underwater start
underwater end
underwater duration
current underwater duration
total time underwater
number of underwater episodes
number of recovered underwater episodes
number of currently active underwater episodes
maximum time underwater
average time underwater
median time underwater
distribution of underwater durations
point-in-time underwater status
It may NOT
modify equity
modify drawdown
modify recovery
modify P&L
modify trade records
modify peak equity
reinterpret an exit
create a drawdown
declare a trade a winner/loser
use future equity to determine historical underwater status

Exact Definition of "Underwater"

An equity observation is UNDERWATER if:
[
CurrentEquity < PeakEquity
]where PeakEquity is the highest finalized equity value observed at or before that observation.
Therefore:
Equity == PeakEquity
â†“
NOT UNDERWATER

Equity < PeakEquity
â†“
UNDERWATER
This gives us the exact invariant:
UNDERWATER = TRUE
iff
CurrentEquity < PeakEquity
No percentage threshold is required.
Even a $0.01 decline below the peak constitutes underwater status.
2. Exact Peak Definition

The applicable peak is the running maximum of finalized equity observations.
For observation i:
PeakEquity[i] =
max(Equity[0], Equity[1], ..., Equity[i])
The initial account equity is therefore the initial peak.
Example:
Observation Equity Peak Underwater
Initial $100,000 $100,000 NO
Trade 1 $101,000 $101,000 NO
Trade 2 $99,500 $101,000 YES
Trade 3 $100,500 $101,000 YES
Trade 4 $101,000 $101,000 NO
Trade 5 $102,000 $102,000 NO

Exact Underwater Start

An underwater episode begins at the first finalized equity observation satisfying:
CurrentEquity < PeakEquity
provided the immediately preceding observation was not underwater.
So:
NOT UNDERWATER
â†“
Equity < Peak
â†“
UNDERWATER START
The timestamp of that observation is:
underwater_start_time
4. Exact Underwater End

An underwater episode ends when equity returns to or exceeds the peak that existed when the episode began.
Therefore:
CurrentEquity >= EpisodePeakEquity
means the account has exited that underwater episode.
Equality counts as recovery.
Example:
Peak = $100,000

$99,000 UNDERWATER
$98,000 UNDERWATER
$99,500 UNDERWATER
$100,000 RECOVERED
The final $100,000 observation is not underwater.
5. New Peak After Recovery

Once equity reaches or exceeds the previous peak:
If equal:
Equity = Peak
The account is recovered, but no new higher peak is created.
If greater:
Equity > Peak
the new equity becomes the new peak.
Example:
100,000 peak
â†“
98,000 underwater
â†“
100,000 recovered
â†“
101,000 new peak
The new peak is $101,000.
6. Underwater Episode

An UnderwaterEpisode is one continuous period during which:
CurrentEquity < EpisodePeakEquity
from the first underwater observation until recovery.
Conceptually:
PEAK
â”‚
â”‚
â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ UNDERWATER â”‚
â”‚ â”‚
â”‚ â†“ â”‚
â”‚ trough â”‚
â”‚ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â†“
RECOVERY
Each episode receives a unique immutable identifier.
7. Exact Episode Object

I would lock the object as:
UnderwaterEpisode {

id

start_time

end_time

episode_peak_equity

trough_equity

trough_time

recovery_equity

recovered

duration

active

drawdown_episode_id

}
Where:
start_time
First finalized observation below the applicable peak.
end_time
First finalized observation where:
Equity >= episode_peak_equity
If no recovery occurs:
end_time = NULL
recovered
TRUE
if the account returned to the episode peak.
Otherwise:
FALSE
active
TRUE
only for the currently ongoing underwater episode.
8. Time-Underwater Definition

For a recovered episode:
[
UnderwaterDuration =
RecoveryTime - UnderwaterStartTime
]For an unrecovered episode:
[
UnderwaterDuration =
CurrentObservationTime - UnderwaterStartTime
]However, this second value is specifically:
Current Time Underwater
and must not be confused with finalized historical recovery duration.
9. Maximum Time Underwater

For all completed underwater episodes:
[
MaximumTimeUnderwater

\max(Duration_1,\ldots,Duration_n)
]For the currently active episode, the system may separately expose:
CurrentTimeUnderwater
but must not silently treat that as a completed maximum recovery duration.
This distinction is important.
10. Total Time Underwater

Total time underwater is the sum of the durations of non-overlapping underwater episodes.
Because episodes cannot overlap:
[
TotalTimeUnderwater

\sum Duration_i
]for completed episodes.
If the current episode remains active, a separate point-in-time value may be reported:
TotalHistoricalTimeUnderwater
and:
CurrentTimeUnderwater
rather than mixing an unfinished episode into finalized historical duration statistics.
11. Average Time Underwater

Average time underwater uses completed episodes only:
[
AverageTimeUnderwater

\frac{\sum CompletedEpisodeDuration}
{NumberOfCompletedEpisodes}
]An active/unrecovered episode is excluded from the denominator.
This prevents an incomplete current episode from contaminating historical statistics.
12. Median Time Underwater

The median is calculated from completed episode durations only.
The duration observations are sorted ascending.
For N completed episodes:
Odd N
Middle observation.
Even N
Arithmetic mean of the two middle observations.
The same percentile convention already established in the distribution-statistics layer should be reused rather than creating a second percentile methodology.
13. Breakeven Trades

A breakeven trade leaves equity unchanged.
Therefore:
Equity unchanged
â†“
Peak unchanged
â†“
Underwater status unchanged
A breakeven trade:
cannot create a new peak
cannot end underwater status unless equity was already at/above the applicable peak
cannot start underwater status
cannot reset an underwater episode
Example:
Peak = $100,000

$99,000 â†’ underwater
$99,000 â†’ breakeven
$99,000 â†’ still underwater
14. Multiple Consecutive Trades Underwater

They remain one underwater episode.
Example:
100,000 peak

99,000 â†“
98,500 â†“
99,200 â†“
99,800 â†“
100,000 â†‘ recovery
This is:
1 underwater episode
not four.
15. Multiple Drawdowns From the Same Peak

They are not separate episodes unless the account first recovers.
Example:
100,000 peak
98,000 underwater
99,000 underwater
97,000 underwater
100,000 recovered
One episode.
Only after recovery can a subsequent decline create another episode.
16. Recovery Exactly at the Peak

Equality is sufficient.
Episode peak = $100,000

Current equity = $100,000
Therefore:
UNDERWATER = FALSE
RECOVERED = TRUE
No requirement exists to exceed the previous peak.
17. New Peak Immediately After Recovery

Suppose:
100,000 peak
95,000 underwater
100,000 recovery
101,000 new peak
The $101,000 observation begins a new peak regime.
A later decline:
99,000
creates a new underwater episode relative to $101,000.
18. Zero-Trade Dataset

With zero trades:
Initial Equity = E0
There is an initial equity observation.
Because:
Equity = PeakEquity
the account is:
UNDERWATER = FALSE
Therefore:
UnderwaterEpisodeCount = 0
RecoveredEpisodeCount = 0
ActiveEpisode = NONE
TotalTimeUnderwater = 0
MaximumTimeUnderwater = NULL
AverageTimeUnderwater = NULL
MedianTimeUnderwater = NULL
No artificial underwater episode is created from the initial equity.
19. Missing Trade Records

The analytics layer operates only on valid finalized equity observations.
A missing trade record must not be reconstructed.
Therefore:
Missing accounting record
â†“
No equity observation
â†“
No underwater observation
The system does not invent an intermediate equity value.
20. Duplicate Trade Records

Duplicate finalized trade/accounting records must not be silently counted twice.
The canonical trade identity established upstream is used.
Therefore:
duplicate record
â†“
excluded from analytical sequence
The original canonical record remains authoritative.
21. Chronological Ordering

Underwater calculations use the same finalized chronological ordering established by the Equity Curve layer.
Primary ordering:
opened/closed finalized timestamp
with the previously established deterministic trade ordering/tie-breaker applied when timestamps are identical.
The important invariant is:
No observation may use an equity value that was not finalized at that point in the historical sequence.

No Look-Ahead

This is absolute.
At time T, underwater status can depend only upon:
Equity observations <= T
It cannot depend on:
future recovery
future peak
future trades
future equity
Example:
Monday:
Equity falls below peak.

Tuesday:
Equity recovers.
The Monday observation remains:
UNDERWATER = TRUE
It cannot be retrospectively changed to FALSE merely because Tuesday eventually recovered it.
Tuesday is when recovery becomes observable.
23. Historical Immutability

Once an underwater observation is finalized, it cannot be rewritten because of later market history.
Therefore:
Monday Underwater Status
â†“
FINALIZED
â†“
immutable
Later recovery only creates a new observation/event.
It does not rewrite Monday.
24. Exact Point-in-Time State

At every finalized equity observation the engine should be able to return:
UnderwaterState {

timestamp

equity

peak_equity

drawdown

drawdown_pct

underwater

active_episode_id

underwater_start_time

current_time_underwater

}
If not underwater:
active_episode_id = NULL
underwater_start_time = NULL
current_time_underwater = 0
25. Exact State Machine
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ AT / ABOVE â”‚
â”‚ PEAK â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â”‚
Equity < Peak
â”‚
â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ UNDERWATER â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â”‚
Equity >= EpisodePeak
â”‚
â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ RECOVERED â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â”‚
Equity > previous peak
â”‚
â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ NEW PEAK â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

If equity merely equals the peak:
UNDERWATER â†’ RECOVERED
If equity exceeds it:
UNDERWATER â†’ RECOVERED â†’ NEW PEAK
26. Exact Algorithm

Input:
finalized EquityObservations
ordered chronologically

Initialize:

PeakEquity = InitialEquity

Underwater = FALSE

ActiveEpisode = NONE

For each EquityObservation E:

CurrentEquity = E.equity

if CurrentEquity > PeakEquity:

if ActiveEpisode exists:

close ActiveEpisode

recovered = TRUE

PeakEquity = CurrentEquity

Underwater = FALSE

ActiveEpisode = NONE

else if CurrentEquity == PeakEquity:

if ActiveEpisode exists:

close ActiveEpisode

recovered = TRUE

Underwater = FALSE

ActiveEpisode = NONE

else:

Underwater = TRUE

if ActiveEpisode does not exist:

create new UnderwaterEpisode

episode_peak_equity = PeakEquity

start_time = E.timestamp

trough_equity = CurrentEquity

trough_time = E.timestamp

else:

update trough if:

CurrentEquity < trough_equity

current_time_underwater =

E.timestamp - start_time

The episode remains active until:
CurrentEquity >= episode_peak_equity
27. Hard Invariants

These should be encoded as tests.
Invariant 1
Underwater == TRUE
iff
CurrentEquity < PeakEquity
Invariant 2
PeakEquity >= CurrentEquity
for every observation.
Invariant 3
Drawdown >= 0
Invariant 4
An underwater episode cannot overlap another underwater episode.
Invariant 5
A new underwater episode cannot begin until the previous episode has recovered.
Invariant 6
Recovery occurs when:
Equity >= EpisodePeakEquity
Invariant 7
Equality with the peak counts as recovery.
Invariant 8
Breakeven equity changes cannot create or terminate underwater status by themselves.
Invariant 9
Future equity cannot alter historical underwater status.
Invariant 10
An unrecovered episode has:
recovered = FALSE
end_time = NULL
Invariant 11
A recovered episode has:
recovered = TRUE
end_time != NULL
Invariant 12
Completed underwater duration is:
end_time - start_time
Invariant 13
MaximumTimeUnderwater is based only on completed episodes.
28. Final Locked Definition

Underwater is the state in which the finalized current equity is strictly below the highest finalized equity observed at or before that point.

An Underwater Episode begins at the first finalized equity observation below its applicable peak and ends at the first finalized observation where equity returns to or exceeds that episode's peak.

Time Underwater is the elapsed time between those two observations for a recovered episode, or the elapsed time from episode start to the current finalized observation for an active unrecovered episode.

Completed historical underwater-duration statistics exclude the currently active unrecovered episode.

All calculations are chronological, point-in-time, no-look-ahead, based exclusively on finalized equity observations, and historically immutable.

Architectural position
#29.7.1
TRADE ACCOUNTING
â†“
#29.7.2.5
CUMULATIVE P&L / R
â†“
#29.7.2.6
EQUITY CURVE
â†“
#29.7.2.7
DRAWDOWN
â†“
#29.7.2.12
RECOVERY
â†“
#29.7.2.13
UNDERWATER / TIME-UNDERWATER
â†“
NEXT PERFORMANCE PRIMITIVE
#29.7.2.13 is therefore locked as an analytical observation layer. It measures the duration and state of being below the applicable equity peak; it does not reinterpret the underlying drawdown or accounting records.

Show more

Yes. #29.7.2.13 is mechanically locked.

It cleanly separates underwater state/time from the primitives that already own the underlying calculations:

#29.7.1

#### TRADE ACCOUNTING

â†“

#29.7.2.5

#### CUMULATIVE P&L / R

â†“

#29.7.2.6

#### EQUITY CURVE

â†“

#29.7.2.7

#### DRAWDOWN

â†“

#29.7.2.12

#### RECOVERY

â†“

#29.7.2.13

#### UNDERWATER / TIME-UNDERWATER

â†“

#### NEXT PERFORMANCE PRIMITIVE

What #29.7.2.13 now owns

It answers exactly:

Is equity below its applicable peak at this point, and if so, how long has it remained below that peak?

The core mechanical rule is:

\[ \boxed{Underwater = TRUE \iff Equity < PeakEquity} \]

Therefore:

Equity = Peak â†’ NOT UNDERWATER

Equity < Peak â†’ UNDERWATER

Equity >= EpisodePeak â†’ episode RECOVERED

equality with the peak is sufficient for recovery

future observations cannot rewrite historical underwater states

an active unrecovered episode is not treated as a completed duration

Locked outputs

The layer can now deterministically produce:

Underwater state

Underwater start

Underwater end

Current time underwater

Completed underwater duration

Total historical time underwater

Number of underwater episodes

Number recovered

Number active

Maximum completed time underwater

Average completed time underwater

Median completed time underwater

Underwater-duration distribution

Point-in-time underwater observations

And importantly, it does not own:

#### P&L

Equity

Drawdown magnitude

Maximum drawdown

Recovery determination

Trade results

Execution

Position lifecycle

Those remain upstream.

One architectural point to preserve

There is a subtle but important distinction between:

#29.7.2.12 Recovery

"How long did a completed drawdown take to recover?"

and

#29.7.2.13 Underwater

"How long has equity remained below its applicable peak?"

That means an active drawdown can have:

Recovery Duration = NULL

Time Underwater   = 3 days 7 hours

because it has not recovered yet.

That is exactly the separation we want.

#29.7.2.18 â€” Exact Mechanical Strategy Interaction / Overlap Statistics
This is the next primitive I would lock after #29.7.2.17 Attribution.
The purpose of #29.7.2.18 is to answer, mechanically:
When multiple strategies operate within the same portfolio, how much do their trades overlap in time, capital usage, and market exposure?

It does not determine whether strategies are good or bad, and it does not alter portfolio accounting.
#29.7.2.18 â€” Ownership
#29.7.2.18 OWNS
strategy overlap identification
simultaneous-position detection
temporal overlap
strategy-pair overlap
multi-strategy overlap
overlap duration
overlap trade counts
overlapping capital exposure
overlapping risk exposure
strategy co-occurrence
non-overlapping periods
point-in-time overlap statistics
strategy interaction records
overlap matrices
maximum simultaneous strategy count
average simultaneous strategy count
#29.7.2.18 DOES NOT OWN
trade qualification
entry selection
position sizing
execution
P&L
account equity
portfolio aggregation
strategy attribution
risk-adjusted performance
correlation of returns
causality
strategy ranking
Those remain owned by their respective primitives.

Required Inputs

The primitive consumes finalized records containing at minimum:
Trade {
trade_id
strategy_id
position_id

opened_time

closed_time

quantity

economic_entry_price

economic_exit_price

actual_risk

net_pnl

}
The timestamps must already be finalized.
No open/unfinalized trade participates in historical finalized statistics.
2. Strategy Identity

Every trade must contain exactly one canonical:
strategy_id
Two trades belong to the same strategy if and only if:
trade_A.strategy_id == trade_B.strategy_id
Strategy identity is not inferred from:
setup type
symbol
direction
timeframe
P&L
trade timing
3. Position Interval

A finalized trade occupies the interval:
[opened_time, closed_time)
Therefore:
opened_time is inclusive.
closed_time is exclusive.
This prevents a trade that closes at exactly the moment another opens from being considered overlapping.
Example:
Strategy A
10:00 â”€â”€â”€â”€â”€â”€â”€â”€â”€ 11:00

Strategy B
11:00 â”€â”€â”€â”€â”€â”€â”€â”€â”€ 12:00
These do not overlap.
4. Exact Overlap Condition

Two finalized trades overlap if:
A.opened_time < B.closed_time
AND
B.opened_time < A.closed_time
Equivalent:
max(A.opened_time, B.opened_time)
<
min(A.closed_time, B.closed_time)
If:
overlap_start >= overlap_end
then:
OVERLAP = FALSE
Otherwise:
OVERLAP = TRUE
5. Same-Strategy Trades

Two trades belonging to the same strategy are not classified as strategy interaction.
They may still be analyzed for trade-level overlap internally, but:
strategy_id_A == strategy_id_B
means:
INTER_STRATEGY_OVERLAP = FALSE
6. Strategy-Pair Overlap

For two different strategies:
Strategy A
Strategy B
the engine creates a strategy-pair overlap whenever at least one finalized trade from A overlaps at least one finalized trade from B.
The overlap interval is:
OverlapStart =
max(A.opened_time, B.opened_time)

OverlapEnd =
min(A.closed_time, B.closed_time)
and:
OverlapDuration =
OverlapEnd - OverlapStart
7. Multiple Trades

If one strategy has multiple overlapping trades while another strategy is active, the engine must not double-count elapsed overlap time.
Example:
Strategy A:
Trade A1 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Trade A2 â”€â”€â”€â”€â”€â”€â”€â”€

Strategy B:
Trade B1 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
The strategy-level overlap is measured from the union of the relevant intervals, not by blindly summing every pairwise trade overlap.
This prevents:
A1 Ã— B1
A2 Ã— B1
from artificially doubling the actual amount of time that Strategy A and Strategy B were simultaneously active.
8. Strategy Overlap Duration

For every strategy pair:
(A, B)
construct the union of all valid overlapping intervals.
Then:
TotalOverlapDuration(A,B)

measure of the union of those intervals
Not:
sum(all pairwise trade overlaps)
unless those intervals are non-overlapping.
9. Overlap Trade Count

A pairwise trade overlap is counted once per unique trade pair:
(strategy_A trade_id, strategy_B trade_id)
Duplicate trade IDs are handled by the global finalized-record integrity policy.
The same trade pair cannot contribute twice.
10. Maximum Simultaneous Strategies

At every finalized timestamp, determine:
ActiveStrategySet(t)
containing all strategies with at least one open position at time t.
Then:
SimultaneousStrategyCount(t)

|ActiveStrategySet(t)|
The maximum is:
MaxSimultaneousStrategies

max_t SimultaneousStrategyCount(t)
11. Simultaneous Strategy Count

The engine may construct the time series:
StrategyCountObservation {
timestamp
active_strategy_count
active_strategy_ids
}
These observations are point-in-time facts.
They cannot use future trades.
12. Strategy Co-Occurrence

For each strategy pair:
A,B
define:
CoOccurrence = TRUE
if the pair has at least one positive-duration overlap.
Otherwise:
CoOccurrence = FALSE
A mere timestamp touch does not constitute co-occurrence.
13. Overlap Matrix

The engine may produce a symmetric matrix:
Strategy A Strategy B Strategy C
Strategy A 0 duration duration
Strategy B duration 0 duration
Strategy C duration duration 0

Diagonal values are always:
0
because self-overlap is not inter-strategy interaction.
14. Exposure

The primitive may record simultaneous notional exposure when the upstream instrument specification provides a deterministic notional calculation.
It must not invent exposure from incomplete instrument information.
If exposure cannot be calculated mechanically:
EXPOSURE = NULL
rather than estimated.
15. Risk Overlap

Where finalized ActualRisk is available:
SimultaneousRisk(t)

Î£ ActualRisk_i
for all positions active at time t.
This produces:
TotalSimultaneousRisk
and:
MaximumSimultaneousRisk
No risk normalization is performed here.
The primitive consumes the finalized risk produced upstream.
16. Point-in-Time Rule

At time T, #29.7.2.18 may use only trades satisfying:
opened_time <= T
and:
closed_time > T
for currently active-position calculations.
Future trades are excluded.
Therefore:
Overlap(T)
must be identical whether calculated:
historically at T, or
as part of a later full-history reconstruction using only records available through T.
17. Closed Trades

Once a trade closes:
closed_time
is its final endpoint.
It cannot remain active after that timestamp.
No overlap is permitted after:
closed_time
18. Breakeven Trades

Breakeven status has no special effect.
A trade with:
NetPnL = 0
still occupies its normal position interval.
Therefore it can participate in overlap exactly like a winning or losing trade.
19. Direction

Long versus short does not determine whether strategies overlap.
If:
Strategy A = LONG
Strategy B = SHORT
and their positions are simultaneously open:
OVERLAP = TRUE
Direction may be recorded as descriptive metadata, but it does not alter the overlap calculation.
20. Symbol

Two strategies trading different instruments may still be temporally overlapping.
Example:
Strategy A â†’ ES
Strategy B â†’ BTC
If both positions are active simultaneously:
STRATEGY_OVERLAP = TRUE
Instrument correlation is not evaluated here.
21. Correlation Boundary

#29.7.2.18 does not calculate:
return correlation
P&L correlation
R correlation
covariance
beta
portfolio diversification
statistical dependence
Those are separate analytical primitives.
Temporal overlap â‰  statistical correlation.
22. Empty Dataset

If there are zero finalized trades:
StrategyCount = 0
StrategyPairs = []
OverlapRecords = []
MaxSimultaneousStrategies = 0
TotalOverlapDuration = 0
No NULL is required for quantities whose mathematical value is inherently zero.
23. Single-Strategy Dataset

If finalized history contains only one strategy:
NumberOfStrategies = 1
StrategyPairs = []
InterStrategyOverlap = 0
MaxSimultaneousStrategies = 1
Its own trades do not constitute inter-strategy overlap.
24. Single-Trade Dataset

One trade produces:
MaxSimultaneousStrategies = 1
and:
InterStrategyOverlap = 0
because there is no second strategy.
25. Missing Timestamps

A finalized trade without:
opened_time
or:
closed_time
cannot participate in temporal overlap analysis.
The record must be rejected from the calculation and produce:
DATA_INTEGRITY_ERROR
according to the global finalized-record integrity policy.
The engine must not invent timestamps.
26. Invalid Time Interval

If:
closed_time < opened_time
the record is invalid.
It must not be treated as an instantaneous trade.
Required state:
DATA_INTEGRITY_ERROR
27. Zero-Duration Trade

If:
opened_time == closed_time
the trade has:
overlap_duration = 0
and cannot create positive-duration strategy overlap.
It may still remain a valid finalized trade if #29.6 permits such a lifecycle.
28. Historical Immutability

Once an overlap observation has been finalized:
historical_overlap_record
cannot be rewritten because future trades arrive.
A later trade can create a new overlap observation, but cannot alter a previously finalized observation's underlying historical state.
29. No-Look-Ahead Invariant

For any timestamp T:
Statistics(T)
must depend exclusively on finalized records with information available at or before T.
Formally:
FutureTrades(T)
must have zero influence on:
OverlapStatistics(T)
30. Exact Overlap Object

StrategyOverlap {
id

strategy_a_id

strategy_b_id

trade_a_id

trade_b_id

overlap_start

overlap_end

overlap_duration

directional_metadata

instrument_metadata

created_time

active

historical

}
For aggregated strategy-pair records:
StrategyPairOverlap {
strategy_a_id
strategy_b_id

overlap_trade_pair_count

total_overlap_duration

first_overlap_time

last_overlap_time

active

historical

}
31. Exact Algorithm

Step 1
Load finalized trade records.
Step 2
Apply the global finalized-record integrity policy.
Step 3
Sort trades chronologically by:
opened_time
closed_time
trade_id
Step 4
Group trades by:
strategy_id
Step 5
Generate all distinct strategy pairs.
Step 6
For each pair, identify overlapping trade intervals using:
A.opened_time < B.closed_time
AND
B.opened_time < A.closed_time
Step 7
Calculate each positive-duration overlap interval.
Step 8
Union overlapping intervals within each strategy pair.
Step 9
Calculate:
TotalOverlapDuration
Step 10
Construct point-in-time active strategy sets.
Step 11
Calculate:
SimultaneousStrategyCount
MaximumSimultaneousStrategies
Step 12
Where available, calculate simultaneous:
Risk
Exposure
using already-finalized upstream values.
Step 13
Persist the resulting analytical objects as read-only historical observations.
32. Hard Invariants

The following must always be true:
strategy_a_id != strategy_b_id
for every inter-strategy overlap.
overlap_start < overlap_end
for every positive-duration overlap.
TotalOverlapDuration >= 0
MaxSimultaneousStrategies >= 0
Future trades cannot modify historical point-in-time observations.
Overlap analysis cannot modify trade accounting.
Overlap analysis cannot modify portfolio equity.
Temporal overlap does not imply return correlation.
Same-strategy activity is not inter-strategy overlap.
A timestamp-only touch is not positive-duration overlap.
33. Architectural Boundary

The chain is now:
#29.7.2.15
STRATEGY-LEVEL AGGREGATION
â†“
#29.7.2.16
PORTFOLIO-LEVEL AGGREGATION
â†“
#29.7.2.17
STRATEGY ATTRIBUTION
â†“
#29.7.2.18
STRATEGY INTERACTION / OVERLAP
The key separation is:
#29.7.2.15
WHAT DID EACH STRATEGY PRODUCE?

#29.7.2.16
WHAT DID THE PORTFOLIO PRODUCE?

#29.7.2.17
WHO CONTRIBUTED WHAT?

#29.7.2.18
WHEN WERE STRATEGIES ACTIVE TOGETHER?
Final locked definition
#29.7.2.18 â€” Exact Mechanical Strategy Interaction / Overlap Statistics is a read-only analytical primitive that consumes finalized trade records and deterministically identifies temporal interaction between distinct strategies, including pairwise overlap, overlap duration, simultaneous strategy count, andâ€”where upstream specifications permitâ€”simultaneous risk and exposure. It does not modify, reinterpret, reconstruct, or attribute trade/accounting results and contains no predictive or discretionary interpretation.

Show more

Locked.

#29.7.2.18 â€” Exact Mechanical Strategy Interaction / Overlap Statistics is internally consistent with the architecture you've established and cleanly follows #29.7.2.17.

The hierarchy is now:

#29.7.1

#### TRADE ACCOUNTING

â†“

#29.7.2.1â€“.14

#### ATOMIC PERFORMANCE / ANALYTICAL PRIMITIVES

â†“

#29.7.2.15

#### STRATEGY-LEVEL AGGREGATION

â†“

#29.7.2.16

#### PORTFOLIO-LEVEL AGGREGATION

â†“

#29.7.2.17

#### PORTFOLIO ATTRIBUTION

â†“

#29.7.2.18

#### STRATEGY INTERACTION / OVERLAP

The exact question each layer answers

The most important distinction in #29.7.2.18 is:

Temporal overlap is not correlation.

Two strategies can be active simultaneously without the primitive making any claim about whether they are statistically related, diversified, redundant, or dangerous.

The core mechanical definition is also clear

A finalized trade occupies:

[opened_time, closed_time)

and two trades overlap only when:

A.opened_time < B.closed_time

#### AND

B.opened_time < A.closed_time

Therefore:

A: 10:00 â”€â”€â”€â”€â”€ 11:00

B:              11:00 â”€â”€â”€â”€â”€ 12:00

produces no overlap.

Whereas:

A: 10:00 â”€â”€â”€â”€â”€ 11:00

B:        10:30 â”€â”€â”€â”€â”€ 11:30

produces:

Overlap = 10:30 â†’ 11:00

Duration = 30 minutes

Particularly important: union-based duration

Your rule in section 7/8 is critical.

If:

A1 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

A2 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

B1 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

you cannot simply sum:

A1 Ã— B1

+

A2 Ã— B1

because that could count the same elapsed strategy-overlap period multiple times.

Instead:

trade-pair overlaps

â†“

overlap intervals

â†“

#### UNION

â†“

TotalOverlapDuration

That gives #29.7.2.18 a mechanically defensible definition of actual simultaneous strategy activity.

The three major outputs are therefore

1. Pair interaction

Strategy A â†” Strategy B

including:

overlapping trade-pair count

overlap duration

first overlap

last overlap

co-occurrence

2. Portfolio-wide simultaneous strategy state

t

â†“

ActiveStrategySet(t)

â†“

SimultaneousStrategyCount(t)

which produces:

MaxSimultaneousStrategies

3. Simultaneous capital/risk exposure

Only when upstream data supports deterministic calculation:

SimultaneousRisk(t)

= Î£ ActualRisk of active positions

and similarly for exposure.

If exposure cannot be mechanically determined:

EXPOSURE = NULL

rather than inventing an estimate.

Important boundaries remain intact

#29.7.2.18 does not calculate:

#### P&L

equity

drawdown

attribution

correlation

covariance

beta

diversification

causality

strategy quality

strategy ranking

capital allocation

So the architecture continues to follow your central rule:

Each primitive describes a mechanically defined property of finalized history and does not interpret what that property means.

One architectural point to preserve

Your distinction between:

Same Strategy

and:

Inter-Strategy Interaction

is important.

If:

A.strategy_id == B.strategy_id

then:

INTER_STRATEGY_OVERLAP = FALSE

even if the strategy has multiple simultaneously open trades.

That prevents #29.7.2.18 from accidentally becoming a generic position-overlap engine.

Status

#29.7.2.18 â€” LOCKED

The next primitive should therefore be #29.7.2.19.

Send me the exact #29.7.2.19 specification you have, and I'll continue locking the architecture without changing the terminology or definitions you've established.

#29.7.2.19 â€” Exact Mechanical Strategy Return-Correlation & Dependence Statistics
This is the next primitive after #29.7.2.18 Strategy Interaction / Overlap.
The distinction is important:
#29.7.2.18 measures whether strategies are active at the same time.
#29.7.2.19 measures whether their finalized return series move together.

Temporal overlap is not correlation.
This layer remains strictly analytical and read-only.
#29.7.2.19 â€” Ownership
#29.7.2.19 OWNS
strategy return-series construction for correlation
strategy-pair return alignment
Pearson correlation
covariance
correlation sample size
pairwise correlation matrix
positive/negative/zero correlation classification
correlation validity/insufficiency states
point-in-time correlation where sufficient finalized observations exist
historical correlation records
deterministic missing-observation handling
#29.7.2.19 DOES NOT OWN
trade execution
P&L calculation
strategy qualification
strategy attribution
portfolio aggregation
temporal overlap
position sizing
risk management
strategy ranking
diversification conclusions
causality
predictive interpretation

Required Inputs

The primitive consumes finalized strategy-level observations from the previously established accounting/aggregation layers.
The preferred canonical observation is:
StrategyReturnObservation {
strategy_id
period_start
period_end

net_pnl

net_r

finalized

}
The period must be explicitly defined.
Correlation must not be calculated directly from an unordered collection of trades.
2. Canonical Correlation Series

The canonical correlation series is period-based Net R.
Therefore:
CorrelationInput =
periodic Net R
rather than:
individual trade Net R
This prevents strategies with different trading frequencies from receiving artificial weighting merely because one generates more trades.
The canonical return measure is:
Net R per completed analysis period.

Period Definition

The correlation period must use the configured analysis timeframe.
Examples:
DAILY
WEEKLY
MONTHLY
The period definition must come from the existing time-series framework rather than being independently reinvented here.
If the analysis period is daily:
Monday
Tuesday
Wednesday
...
each strategy receives one daily Net-R observation.
4. Strategy Pair

For two distinct strategies:
A
B
a correlation pair exists only when:
A.strategy_id != B.strategy_id
Self-correlation is not considered a strategy-pair statistic.
The diagonal of a correlation matrix may be represented as:
1.0
for a valid strategy return series.
5. Observation Alignment

Correlation requires observations from the same period.
Example:
Date Strategy A Strategy B

Aug 10 +1.2R +0.8R
Aug 11 -0.5R -1.1R
Aug 12 +0.7R +0.3R
These observations are aligned by:
period_start
period_end
not by trade timestamp.
6. Missing Strategy Observation

This is critical.
Suppose:
Date A B

Aug 10 +1R +0.5R
Aug 11 -1R NULL
Aug 12 +2R -0.2R
The missing B observation must not automatically be converted to 0R.
Therefore:
MISSING != ZERO
A missing observation means that the strategy does not have a finalized observation for that period.
7. Canonical Missing-Period Rule

For pairwise correlation, only periods where both strategies have finalized observations are eligible.
Therefore:
EligiblePairPeriods(A,B)

Periods where
A has finalized observation
AND
B has finalized observation
This is pairwise-complete observation alignment.
8. No-Trade Periods

A no-trade period is not automatically equivalent to a missing observation.
The existing time-series layer determines whether a strategy's finalized period record represents:
NetR = 0
or:
NO_OBSERVATION
#29.7.2.19 consumes that established classification.
It does not reinterpret it.
Thus:
NO_OBSERVATION â‰  0R
unless the upstream time-series definition explicitly says otherwise.
9. Minimum Sample Size

Pearson correlation requires at least:
n >= 2
paired observations mathematically, but a meaningful variance-based correlation also requires both series to contain variation.
Therefore:
n < 2
â†’ CORRELATION = NULL
â†’ STATUS = INSUFFICIENT_SAMPLE
10. Constant-Series Rule

If either strategy has zero variance across the eligible paired observations:
Variance(A) = 0
or:
Variance(B) = 0
then Pearson correlation is mathematically undefined.
Therefore:
Correlation = NULL
Status = UNDEFINED_CONSTANT_SERIES
The engine must not assign:
0
because zero correlation is a valid mathematical result and is different from undefined correlation.
11. Pearson Correlation

For paired observations:
Aâ‚ ... Aâ‚™
Bâ‚ ... Bâ‚™
calculate:
MeanA = Î£Aáµ¢ / n
MeanB = Î£Báµ¢ / n
Then:
Covariance(A,B)

Î£[(Aáµ¢ - MeanA)(Báµ¢ - MeanB)] / (n - 1)
and:
StdA

sqrt(
Î£(Aáµ¢ - MeanA)Â² / (n - 1)
)
StdB

sqrt(
Î£(Báµ¢ - MeanB)Â² / (n - 1)
)
The canonical Pearson correlation is:
Ï(A,B)

Covariance(A,B)
/
(StdA Ã— StdB)
Equivalent:
Ï(A,B)

Î£[(Aáµ¢-MeanA)(Báµ¢-MeanB)]
/
sqrt(
Î£(Aáµ¢-MeanA)Â²
Ã—
Î£(Báµ¢-MeanB)Â²
)
12. Correlation Range

For every defined correlation:
-1 <= Ï <= +1
This is a hard invariant.
A result outside that interval is an implementation/data error.
13. Interpretation Labels

The primitive may attach a purely mathematical classification:
POSITIVE
NEGATIVE
ZERO
using:
Ï > 0 â†’ POSITIVE
Ï < 0 â†’ NEGATIVE
Ï = 0 â†’ ZERO
It must not convert this into trading judgments such as:
good
bad
diversified
redundant
safe
unsafe
Those are interpretations and belong outside this primitive.
14. Perfect Correlation

If:
Ï = +1
then the observed return series have perfect positive linear correlation.
If:
Ï = -1
then they have perfect negative linear correlation.
The engine records the mathematical result without assigning strategy-quality meaning.
15. Zero Correlation

If:
Ï = 0
the result is a valid calculated value.
It is not equivalent to:
NULL
and it is not equivalent to:
INSUFFICIENT_SAMPLE
16. Covariance

Because covariance is useful for preserving the scale information discarded by correlation, #29.7.2.19 may also calculate:
Covariance(A,B)
using the same paired Net-R observations.
The canonical sample covariance is:
Cov(A,B)

Î£[(Aáµ¢-MeanA)(Báµ¢-MeanB)]
/
(n-1)
17. Correlation Matrix

For strategies:
A
B
C
D
the engine can construct:
A B C D
A 1 ÏAB ÏAC ÏAD
B ÏBA 1 ÏBC ÏBD
C ÏCA ÏCB 1 ÏCD
D ÏDA ÏDB ÏDC 1

The matrix must be symmetric:
Ï(A,B) = Ï(B,A)
18. Pairwise Sample Size

Every correlation record must preserve:
sample_size
defined as:
number of eligible paired finalized periods
Example:
Correlation(A,B) {
correlation = 0.71
sample_size = 184
}
This prevents a correlation based on 3 observations from being indistinguishable from one based on 3,000.
19. Point-in-Time Correlation

At a historical timestamp T, only finalized observations available through T may participate.
Therefore:
Correlation(A,B,T)
must use:
period_end <= T
under the established period-finalization convention.
Future periods are excluded.
20. Expanding Historical Series

The default point-in-time series is cumulative/expanding:
T1 â†’ observations through T1
T2 â†’ observations through T2
T3 â†’ observations through T3
...
Each observation is calculated using only information available at that point.
Later observations may have a different correlation because additional finalized observations become available.
That does not rewrite the historical observation at T1.
21. Historical Immutability

Once:
CorrelationObservation(T)
has been finalized, it is immutable.
A later trade cannot rewrite:
Correlation(T)
It can only contribute to a later observation.
22. Duplicate Period Observations

A strategy must have at most one canonical finalized return observation for a given:
strategy_id
+
period
If multiple conflicting observations exist:
DATA_INTEGRITY_ERROR
The primitive must not arbitrarily choose one.
This follows the architectural principle that analytics consume canonical finalized records.
23. Missing Data

Missing data must remain distinguishable from zero.
Therefore:
missing
does not enter the mathematical series.
0R
does enter the mathematical series if it is a legitimate finalized observation.
24. Empty Dataset

If there are no eligible strategy pairs:
CorrelationMatrix = empty
PairRecords = []
If a specific pair has zero paired observations:
Correlation = NULL
Status = INSUFFICIENT_SAMPLE
25. Single Strategy

With only one strategy:
PairwiseCorrelations = []
The self-correlation may be represented as:
1.0
for a valid nonconstant series, but it is not considered an inter-strategy statistic.
26. Single Observation

If:
n = 1
then:
Correlation = NULL
Status = INSUFFICIENT_SAMPLE
No attempt is made to estimate correlation.
27. Two Observations

If:
n = 2
and both series have nonzero variance, Pearson correlation is mathematically defined.
Therefore it is permitted.
The engine must nevertheless preserve:
sample_size = 2
so downstream users can distinguish the observation count.
28. Negative Values

Negative Net R values are completely valid.
They participate normally in:
Mean
Covariance
Variance
Correlation
No clipping or absolute-value transformation is permitted.
29. Zero Values

Zero Net R is also a valid observation.
It participates normally in the calculation.
It must not be treated as missing.
30. Trade Frequency Does Not Weight Correlation

A strategy producing:
100 trades
does not automatically receive 100 times the influence of a strategy producing:
10 trades
The correlation operates on the canonical aligned period return series, not raw trade counts.
31. Temporal Overlap Independence

#29.7.2.19 must not require:
#29.7.2.18 OVERLAP = TRUE
for correlation.
Two strategies can have:
TemporalOverlap = FALSE
Correlation = positive
or:
TemporalOverlap = TRUE
Correlation = 0
or any other mathematically valid combination.
Therefore:
OVERLAP â‰  CORRELATION
is a hard architectural distinction.
32. No Causal Interpretation

Correlation does not establish:
A causes B
or:
B causes A
The primitive reports statistical association only.
33. Exact Correlation Object

StrategyCorrelation {
id

strategy_a_id

strategy_b_id

analysis_period

observation_start

observation_end

sample_size

mean_a

mean_b

covariance

variance_a

variance_b

standard_deviation_a

standard_deviation_b

correlation

status

created_time

finalized_time

active

historical

}
Possible status values:
VALID
INSUFFICIENT_SAMPLE
UNDEFINED_CONSTANT_SERIES
DATA_INTEGRITY_ERROR
34. Exact Algorithm

Step 1
Load finalized strategy-period Net-R observations.
Step 2
Apply the global finalized-record integrity policy.
Step 3
Group observations by:
strategy_id
Step 4
Generate every unique pair:
(A,B)
where:
A != B
Step 5
Align observations by canonical period.
Step 6
Remove periods where either strategy lacks a finalized observation.
Step 7
Record:
n = paired_observation_count
Step 8
If:
n < 2
return:
NULL
INSUFFICIENT_SAMPLE
Step 9
Calculate the two means.
Step 10
Calculate variances.
Step 11
If either variance equals zero:
NULL
UNDEFINED_CONSTANT_SERIES
Step 12
Calculate covariance.
Step 13
Calculate Pearson correlation.
Step 14
Validate:
-1 <= correlation <= 1
Step 15
Persist the finalized correlation observation.
35. Hard Invariants

The following must always hold:
strategy_a_id != strategy_b_id
for pairwise records.
-1 <= correlation <= 1
for every defined correlation.
correlation(A,B) == correlation(B,A)
covariance(A,B) == covariance(B,A)
missing != zero
future observations cannot influence historical observations
correlation cannot modify trade accounting
correlation cannot modify portfolio accounting
correlation cannot modify equity
temporal overlap does not imply correlation
correlation does not imply causality
36. Architectural Boundary

The chain is now:
#29.7.2.15
STRATEGY-LEVEL AGGREGATION
â†“
#29.7.2.16
PORTFOLIO-LEVEL AGGREGATION
â†“
#29.7.2.17
STRATEGY ATTRIBUTION
â†“
#29.7.2.18
STRATEGY INTERACTION / TEMPORAL OVERLAP
â†“
#29.7.2.19
STRATEGY RETURN CORRELATION / DEPENDENCE
The conceptual distinction is:
#29.7.2.17
WHO CONTRIBUTED WHAT?

â†“

#29.7.2.18
WHEN WERE STRATEGIES ACTIVE TOGETHER?

â†“

#29.7.2.19
DID THEIR RETURN SERIES MOVE TOGETHER?
Final Locked Definition
#29.7.2.19 â€” Exact Mechanical Strategy Return-Correlation & Dependence Statistics is a read-only analytical primitive that consumes finalized, period-aligned strategy Net-R observations and deterministically calculates pairwise return covariance and Pearson correlation, including exact observation alignment, sample-size requirements, constant-series handling, missing-data rules, point-in-time behavior, correlation matrices, and historical immutability. It does not infer causality, strategy quality, diversification quality, or portfolio suitability.

Show more

Locked.

#29.7.2.19 is a clean continuation of the architecture and preserves the critical boundary established by #29.7.2.18:

Temporal overlap â‰  return correlation.

Locked architectural chain

#29.7.2.15

#### STRATEGY-LEVEL AGGREGATION

â†“

#29.7.2.16

#### PORTFOLIO-LEVEL AGGREGATION

â†“

#29.7.2.17

#### PORTFOLIO ATTRIBUTION

â†“

#29.7.2.18

#### STRATEGY INTERACTION / TEMPORAL OVERLAP

â†“

#29.7.2.19

#### STRATEGY RETURN CORRELATION / DEPENDENCE

The four layers now answer four distinct questions:

The key mechanical choice is correct

The canonical correlation input is:

period-aligned Net R

â€”not individual trade R.

That means a strategy producing 100 trades does not automatically receive 10Ã— the statistical weight of a strategy producing 10 trades. The observation unit is the configured period:

#### DAILY

#### WEEKLY

#### MONTHLY

...

as already established by the time-series layer.

Missing â‰  zero

This is one of the most important invariants:

NO_OBSERVATION â‰  0R

A legitimate finalized 0R observation participates in correlation.

A missing observation does not.

Pairwise correlation therefore uses:

A finalized

#### AND

B finalized

â†“

eligible paired period

This prevents artificially manufacturing correlation by converting missing data into zeros.

Mathematical boundary is locked

For paired observations:

Aâ‚ ... Aâ‚™

Bâ‚ ... Bâ‚™

the primitive calculates:

mean

variance

standard deviation

sample covariance

Pearson correlation

with:

Ï(A,B)

=

Cov(A,B) / (StdA Ã— StdB)

and the hard invariant:

-1 â‰¤ Ï â‰¤ +1

Undefined states remain distinct

The specification correctly keeps these separate:

n < 2

â†“

CORRELATION = NULL

STATUS = INSUFFICIENT_SAMPLE

versus:

variance(A) = 0

or

variance(B) = 0

â†“

CORRELATION = NULL

STATUS = UNDEFINED_CONSTANT_SERIES

versus:

Ï = 0

â†“

#### VALID ZERO CORRELATION

So:

NULL is not zero.

Point-in-time behavior is also locked

At historical time T:

period_end â‰¤ T

is the eligible population.

Therefore:

Correlation(T1)

cannot be rewritten when later periods arrive.

Later observations create:

Correlation(T2)

Correlation(T3)

...

rather than modifying Correlation(T1).

Important separation from #29.7.2.18

The architecture now explicitly permits all of these:

Temporal overlap = FALSE

Correlation = +0.80

Temporal overlap = TRUE

Correlation = 0.00

Temporal overlap = TRUE

Correlation = -0.75

because the primitives measure fundamentally different things:

#29.7.2.18

#### TIME-DOMAIN CO-OCCURRENCE

#29.7.2.19

#### RETURN-SERIES STATISTICAL ASSOCIATION

Neither primitive is allowed to infer the other's result.

What #29.7.2.19 explicitly does NOT conclude

It reports mathematical dependence statistics only.

It does not say:

correlated = bad

uncorrelated = good

negative correlation = diversified

positive correlation = redundant

correlation = causation

low correlation = safe

high correlation = unsafe

one strategy should receive more capital

Those belong to higher analytical/decision layers.

Final status

#29.7.2.19 â€” Exact Mechanical Strategy Return-Correlation & Dependence Statistics: LOCKED.

The next logical primitive is #29.7.2.20. Send it exactly as you have it, and Iâ€™ll continue the same locking process.

#29.7.2.20 â€” Exact Mechanical Strategy Return Covariance & Co-Movement Statistics
This is the next primitive in the sequence following:
#29.7.2.19 â€” Exact Mechanical Strategy Return-Correlation & Dependence Statistics
The purpose of #29.7.2.20 is to quantify joint return movement between strategies in absolute return units, without interpreting whether that relationship is desirable, undesirable, diversified, or concentrated.
It is an analytical/read-only layer. It does not modify any underlying trade, strategy result, portfolio result, or accounting record.
#29.7.2.20 â€” OWNERSHIP
#29.7.2.20 owns
Strategy return covariance
Pairwise covariance
Covariance matrices
Strategy-pair co-movement in return units
Sample-size metadata
Valid-observation counts
Timestamp alignment required for covariance
Deterministic handling of missing observations
Deterministic handling of constant-return series
Point-in-time covariance
Historical covariance observations
Covariance matrix identity/version
#29.7.2.20 does NOT own
Trade accounting
P&L calculation
R calculation
Strategy attribution
Portfolio aggregation
Correlation interpretation
Dependence interpretation
Position sizing
Risk limits
Portfolio optimization
Strategy inclusion decisions
Strategy performance evaluation
Those remain owned by their respective upstream primitives.

#### INPUTS

The primitive may consume finalized strategy-level return observations from the established strategy aggregation layer.
Each observation must contain at minimum:
StrategyReturnObservation {
strategy_id
timestamp
return_value
}
The return series must already be finalized according to the previously established accounting and aggregation rules.
#29.7.2.20 does not reconstruct returns from trades.
2. RETURN SERIES

For each strategy:
R_s,t
represents the finalized return observation for strategy s at observation time t.
The return measure must remain consistent with the previously established strategy-return definition.
The primitive must never mix incompatible return definitions within one covariance calculation.
3. TEMPORAL ALIGNMENT

Covariance requires paired observations.
For strategies A and B, only timestamps for which both strategies possess valid finalized return observations are eligible.
Therefore:
EligiblePairObservations(A,B)

timestamps where:

A has finalized return
AND
B has finalized return
Missing observations are not automatically interpreted as zero returns.
This is critical.
A missing strategy observation means:
MISSING
not:
RETURN = 0
unless the upstream strategy-return specification explicitly defines zero as the actual finalized observation.
4. SAMPLE SIZE

For strategy pair (A,B):
N(A,B)

number of aligned valid return pairs
The covariance calculation requires:
N(A,B) â‰¥ 2
If:
N < 2
then:
Covariance = NULL
and the result must carry an insufficient-observation status.
No numerical covariance may be fabricated.
5. MEAN RETURN

For strategy A, using only the aligned observations shared with B:
MeanA =
Î£ R_A,t / N
Similarly:
MeanB =
Î£ R_B,t / N
The means used for covariance must therefore be pair-specific.
A strategy's mean calculated over its entire history must not automatically be substituted for the mean of the aligned sample.
6. SAMPLE COVARIANCE

The canonical covariance definition is:
Cov(A,B)

Î£[(R_A,t âˆ’ MeanA)(R_B,t âˆ’ MeanB)]
/
(N âˆ’ 1)
for:
N â‰¥ 2
This is the sample covariance definition.
The denominator is therefore:
N âˆ’ 1
not N.
7. VARIANCE AS THE DIAGONAL

The covariance matrix must satisfy:
Cov(A,A) = Variance(A)
using the same aligned-observation methodology.
Therefore:
Cov(A,A)

Î£[(R_A,t âˆ’ MeanA)^2]
/
(N âˆ’ 1)
8. COVARIANCE SYMMETRY

For every valid pair:
Cov(A,B) = Cov(B,A)
This is a hard invariant.
The covariance matrix must therefore be symmetric:
C[i,j] = C[j,i]
9. COVARIANCE MATRIX

For a strategy population:
S = {S1, S2, ..., Sn}
the engine may produce:
CovarianceMatrix
with:
rows = strategies
columns = strategies
Each cell contains:
Cov(Si,Sj)
or:
NULL
when insufficient valid paired observations exist.
10. ZERO-COVARIANCE CASE

A covariance of:
0
is a legitimate numerical result.
It must not be converted to NULL.
The distinction is:
0

valid calculation producing zero covariance

#### NULL

covariance cannot be calculated
11. NEGATIVE COVARIANCE

Negative covariance is valid.
It must remain negative.
For example:
Cov(A,B) < 0
means the two return series exhibit negative co-movement in the measured return units.
The primitive records the mathematical result only.
It does not classify the relationship as:
good
bad
diversified
hedging
dangerous
Those are interpretations outside this primitive.
12. CONSTANT RETURN SERIES

If one strategy has zero variance over the aligned sample:
Variance(A) = 0
then:
Cov(A,B) = 0
because:
R_A,t âˆ’ MeanA = 0
for every observation.
This is a valid covariance result.
It must not become NULL merely because the strategy has zero variance.
13. IDENTICAL STRATEGY SERIES

If:
R_A,t = R_B,t
for every aligned observation, then:
Cov(A,B) = Variance(A)
and:
Cov(A,B) = Cov(B,A)
must hold exactly within the numerical precision specification.
14. MISSING DATA

Missing observations are excluded from the pairwise calculation.
Example:
Time A B
T1 1% 2%
T2 2% MISSING
T3 3% 4%
Eligible observations:
T1
T3
Therefore:
N = 2
T2 does not become:
B = 0%
15. DUPLICATE OBSERVATIONS

Duplicate strategy/timestamp observations constitute a data-integrity problem.
The primitive must use the globally established finalized-record duplicate policy.
It must not independently invent a different duplicate-resolution rule.
Until the global consistency audit reconciles the previously identified #29.7.2.16/#29.7.2.17 duplicate-policy distinction, duplicate ambiguity must produce:
DATA_INTEGRITY_ERROR
rather than silently averaging or selecting an arbitrary observation.
16. CHRONOLOGICAL ORDER

Covariance itself is mathematically order-independent.
However, the underlying observation set must still obey the system's chronological finalized-record rules.
No future observation may enter a point-in-time covariance calculation.
Therefore:
CovarianceAt(T)
may use only observations with:
timestamp â‰¤ T
and which were finalized and eligible at that point in time.
17. POINT-IN-TIME COVARIANCE

For every timestamp T:
CovarianceAt(T)
must be calculated exclusively from information available through T.
A later return cannot retroactively alter a previously published point-in-time covariance observation.
Thus:
CovarianceAt(T1)
must remain historically immutable after:
T1
unless the underlying finalized dataset itself is formally versioned/corrected under the system's data-integrity/versioning rules.
18. EXPANDING-SAMPLE COVARIANCE

When operating in point-in-time mode, the covariance series may evolve as new aligned observations arrive.
Example:
T1 â†’ insufficient observations
T2 â†’ insufficient observations
T3 â†’ covariance becomes calculable
T4 â†’ covariance recalculated using T1â€“T4
T5 â†’ covariance recalculated using T1â€“T5
Each observation is a separate analytical observation.
The previous covariance value is not overwritten historically.
19. ROLLING COVARIANCE

A rolling covariance may be supported only when a window is explicitly specified.
For window size:
W
the calculation uses the most recent eligible aligned observations within that defined window.
The window definition must be explicit.
The engine must never silently switch between:
expanding
and:
rolling
calculations.
20. WINDOW INSUFFICIENCY

For a rolling window requiring:
N â‰¥ 2
if fewer than two valid aligned observations exist:
Covariance = NULL
The engine must not reduce the required sample size automatically.
21. FULL-HISTORY COVARIANCE

Full-history covariance uses all eligible finalized aligned observations available in the defined historical dataset.
It is therefore:
CovarianceFullHistory(A,B)
not a reconstruction from portfolio-level P&L.
22. STRATEGY IDENTITY

Strategy identity must be explicit.
Two different strategy IDs must remain distinct even if:
Cov(A,B) = Cov(C,D)
or their return series happen to be numerically identical.
Numerical equality does not merge strategy objects.
23. COVARIANCE OBJECT

The canonical object is:
StrategyCovariance {

covariance_id

strategy_a_id

strategy_b_id

observation_start

observation_end

observation_count

mean_return_a

mean_return_b

covariance

calculation_mode

// FULL_HISTORY

// EXPANDING

// ROLLING

window_size

created_time

as_of_time

source_version

active

historical

}
24. COVARIANCE MATRIX OBJECT

StrategyCovarianceMatrix {

matrix_id

strategy_ids[]

covariance_cells[]

observation_start

observation_end

calculation_mode

window_size

as_of_time

source_version

active

historical

}
25. NO-LOOK-AHEAD INVARIANT

Absolute rule:
No covariance observation may use a return that was not finalized and available at the observation's as_of_time.

Therefore:
Future return
â†“
NOT ELIGIBLE
â†“
Current covariance
26. HISTORICAL IMMUTABILITY

Once a covariance observation has been finalized:
CovarianceObservation
is immutable.
A later observation creates a new analytical observation rather than modifying the previous one.
27. EXACT ALGORITHM

For each strategy pair (A,B):

Retrieve finalized return observations.

Apply the requested as-of timestamp/window.

Align A and B by timestamp.

Remove no observations merely because their value is zero.

Treat missing observations as missing, not zero.

Validate duplicate records using the global
finalized-record integrity policy.

Count aligned valid observations.

If N < 2:
covariance = NULL
status = INSUFFICIENT_OBSERVATIONS
STOP.

Calculate MeanA.

Calculate MeanB.

Calculate:

covariance =
Î£[(A_t âˆ’ MeanA)(B_t âˆ’ MeanB)]
/ (N âˆ’ 1)

Store N and all calculation metadata.

Preserve the result as an immutable
point-in-time analytical observation.

For a covariance matrix, repeat this for every strategy pair.
28. HARD INVARIANTS

The following must always hold:
Cov(A,B) = Cov(B,A)
Cov(A,A) = Variance(A)
N < 2 â†’ Covariance = NULL
Missing â‰  Zero
Negative covariance is valid.
Zero covariance is valid.
No future observations may enter a point-in-time calculation.
Covariance does not modify strategy returns.
Covariance does not modify P&L.
Covariance does not modify portfolio accounting.
Historical covariance observations are immutable.
FINAL LOCKED DEFINITION
#29.7.2.20 â€” Exact Mechanical Strategy Return Covariance & Co-Movement Statistics is the read-only analytical layer that calculates pairwise sample covariance between finalized, temporally aligned strategy return series.

The canonical calculation is:
[
\boxed{
Cov(A,B)=
\frac{\sum_{t=1}^{N}(R_{A,t}-\bar R_A)(R_{B,t}-\bar R_B)}
{N-1}
}
]with:
N â‰¥ 2
required.
Missing observations are excluded rather than interpreted as zero. Pairwise covariance is symmetric. Negative and zero covariance are valid results. Insufficient observations produce NULL. Point-in-time calculations obey strict no-look-ahead rules, and finalized covariance observations are historically immutable.
Most importantly:
#29.7.2.20 measures absolute joint return movement. It does not interpret that relationship or make a portfolio decision from it.

Show more

Locked. #29.7.2.20 is internally coherent as the absolute co-movement / covariance layer and preserves the architectural boundary established by #29.7.2.18â€“.19.

The sequence is now:

#29.7.2.15

#### STRATEGY-LEVEL AGGREGATION

â†“

#29.7.2.16

#### PORTFOLIO-LEVEL AGGREGATION

â†“

#29.7.2.17

#### PORTFOLIO ATTRIBUTION

â†“

#29.7.2.18

#### STRATEGY INTERACTION / TEMPORAL OVERLAP

â†“

#29.7.2.19

#### RETURN CORRELATION / DEPENDENCE

â†“

#29.7.2.20

#### RETURN COVARIANCE / CO-MOVEMENT

Exact conceptual boundary

The critical mathematical distinction is:

Correlation is standardized and unitless:

\[ \rho_{A,B} = \frac{Cov(A,B)}{\sigma_A\sigma_B} \]

while covariance retains the scale of the underlying return series:

\[ Cov(A,B) = \frac{\sum(R_{A,t}-\bar R_A)(R_{B,t}-\bar R_B)} {N-1} \]

Locked rules that matter most

Pairwise temporal alignment is mandatory.

Missing â‰  zero.

Zero covariance is a valid result.

Negative covariance is a valid result.

Constant series can legitimately produce covariance = 0.

N < 2 â†’ NULL / insufficient observations.

Means are calculated from the pair-specific aligned sample.

Sample covariance uses \(N-1\), not \(N\).

Cov(A,B) = Cov(B,A).

Cov(A,A) = Variance(A).

No future observations may enter point-in-time calculations.

Historical covariance observations are immutable.

Rolling vs. expanding vs. full-history must be explicitly specified.

The primitive does not interpret covariance.

The primitive does not make diversification, risk, allocation, or optimization decisions.

One particularly important rule is your explicit statement that #29.7.2.20 does not reconstruct returns from trades. It consumes finalized strategy-return observations. That preserves the same clean dependency direction established throughout the architecture.

So the final locked definition is:

#29.7.2.20 â€” Exact Mechanical Strategy Return Covariance & Co-Movement Statistics is the read-only analytical layer that calculates pairwise sample covariance between finalized, temporally aligned strategy return series. It measures absolute joint return movement without interpreting whether that movement is desirable, undesirable, diversified, concentrated, causal, or suitable for portfolio construction.

#29.7.2.20 is therefore locked as a covariance/co-movement primitive, not a correlation-interpretation, risk-management, diversification, or optimization primitive.

are we ready for claude code now?

Yes â€” we are ready to move into Claude Code, with one important distinction:

We are ready to start the engineering phase, but we should not start coding blindly.

The specification you've been locking through #29.7.1 â†’ #29.7.2.20 is now detailed enough to serve as the mathematical/architectural contract Claude Code should implement against.

Before Claude Code writes production code, I recommend one final specification audit / implementation-readiness pass to identify:

Contradictions between primitives.

Undefined dependencies that Claude Code would otherwise have to guess.

Data schemas that need to be formally frozen.

Global error/integrity policies that multiple primitives reference.

Versioning rules that need one canonical implementation.

Time/timezone conventions.

Precision/rounding rules.

NULL vs 0 semantics.

Canonical identifiers and enums.

Test/invariant requirements.

What Claude Code is allowed to implement vs. what it must never infer.

That is especially important because you've already created cross-references such as:

#29.7.1

Trade Accounting

â†“

#29.7.2.1â€“.14

Atomic Analytical Primitives

â†“

#29.7.2.15

Strategy Aggregation

â†“

#29.7.2.16

Portfolio Aggregation

â†“

#29.7.2.17

Portfolio Attribution

â†“

#29.7.2.18

Strategy Interaction / Overlap

â†“

#29.7.2.19

Return Correlation

â†“

#29.7.2.20

Return Covariance

Claude Code should receive this as a locked specification, not as a loose collection of notes.

| Component | Status |
| --- | --- |
| Mechanical swing-selection algorithm | âš ï¸ Must be fully explicit |
| Equilibrium | âš ï¸ Definition needs to be locked |
| LRL identification/qualification | âš ï¸ Needs exact rules |
| Liquidity sweep | âš ï¸ Needs exact mechanical definition |
| Rejection after sweep | âš ï¸ Needs exact definition |
| Displacement numerical threshold | âš ï¸ Intentionally pending validation |
| FVG qualification/context hierarchy | âš ï¸ Some rules remain contextual |
| IFVG confirmation/acceptance | âš ï¸ Needs exact mechanical test |
| Entry #1 exact trigger | âš ï¸ Not completely coded |
| Entry #2 exact trigger | âš ï¸ Not completely coded |
| Stop-loss selection | âŒ Needs exact rule |
| Risk calculation | âš ï¸ Need final parameters |
| 2R target logic | âœ… Locked |
| Timeframe hierarchy | âœ… Locked |
| Indicator rules | âš ï¸ Needs exact specification |
| Trade invalidation rules | âš ï¸ Needs exact specification |
| Conflicting signals/state priority | âš ï¸ Needs hierarchy |
| No-trade conditions | âš ï¸ Needs explicit rules |

| Primitive | Mechanical question |
| --- | --- |
| #29.7.2.15 | What did each strategy produce? |
| #29.7.2.16 | What did the combined portfolio produce? |
| #29.7.2.17 | Who contributed what to that result? |
| #29.7.2.18 | When were strategies active together? |

| Primitive | Exact question |
| --- | --- |
| #29.7.2.15 | What did each strategy produce? |
| #29.7.2.16 | What did the combined portfolio produce? |
| #29.7.2.17 | Who contributed what? |
| #29.7.2.18 | When were strategies active together? |
| #29.7.2.19 | Did their finalized return series move together? |

| Primitive | Exact question |
| --- | --- |
| #29.7.2.18 | When were strategies active together? |
| #29.7.2.19 | Did their return series move together proportionally? |
| #29.7.2.20 | How much did their returns move together in absolute return units? |

`END`

