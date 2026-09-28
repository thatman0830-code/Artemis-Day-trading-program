# ES/NQ Trader Research Package

**Version:** 1.0  
**Research cutoff:** 2026-09-20  
**Purpose:** Source-backed research inputs for an ES/NQ intraday trading bot. This is a research specification, not a promise of profitability or a live-trading authorization.

## Executive decision

Do **not** copy any trader as a single master strategy. The strongest transferable material is a layered system:

1. **Regime classification** from Adam Grimes, Linda Raschke, and Al Brooks: trend, range, compression, expansion, or event-dislocated.
2. **Three independent setup families:**
   - opening-range continuation/failure (Mark Fisher + Raschke),
   - trend pullback/momentum resumption (Raschke + Brooks + Grimes),
   - sweep-and-reclaim toward equilibrium (Kyle Verhagen, treated as a hypothesis rather than verified edge).
3. **System-development discipline** from Kevin Davey and Andrea Unger: explicit rules, realistic costs, out-of-sample testing, walk-forward testing, Monte Carlo analysis, and a portfolio of low-correlated edges.
4. **Auction/order-flow confirmation** from Jim Dalton and Peter Davies: prior value, overnight inventory, acceptance/rejection, and executable order-flow evidence.
5. **Hard risk and operational controls** that override every signal. A trading idea is never allowed to bypass data-quality, connectivity, stale-feed, duplicate-order, or daily-loss controls.

The initial build should prioritize the **opening-range continuation/failure** and **trend-pullback** modules. They are the most definable, falsifiable, and compatible with ES/NQ. The squeeze and sweep/reclaim modules should begin as research-only challengers.

## Evidence standard

| Grade | Meaning | How the bot may use it |
|---|---|---|
| A | Official competition result, regulatory record, audited/clearing evidence, or a long public record with independently checkable transactions | May influence candidate priority, but still requires independent ES/NQ testing |
| B | Primary-source book, official site, detailed public rules, or sustained professional history; performance not fully audited | May supply hypotheses and rule structure |
| C | Self-reported results, educator marketing, interviews, public calls, or prop-profile evidence without a complete audited history | Research hypothesis only; never a performance prior |
| D | Secondary claim that could not be independently corroborated | Preserve as a lead only; do not encode as fact or edge |

**Important limitation:** competition returns often come from small, highly leveraged accounts, may include overnight trades, and do not establish scalability, repeatability, drawdown tolerance, or suitability for ES/NQ day trading. The official World Cup site also warns that a competition account may not represent all accounts controlled by the trader.

## Ranked roster of 15 traders

The roster includes the three previously named traders, then adds twelve traders or method developers relevant to equity-index futures. “Track record” below means the best public evidence found—not a blanket endorsement.

### 1. Linda Bradford Raschke — highest-priority method source

- **Markets/style:** short-term futures and derivatives; discretionary/systematic pattern recognition across multiple timeframes.
- **Strategy:** momentum bursts, first pullbacks, range contraction/expansion, failed tests, and mean-reversion structures. Her published work emphasizes a small playbook of recurring patterns rather than prediction.
- **Entry concept:** require context first, then a precise trigger: momentum expansion followed by an orderly pullback; a false break that re-enters a range; or volatility contraction that releases.
- **Exit concept:** exit when the pattern’s expected behavior fails; use time-based exits for short-term patterns; take profits into the move instead of converting a short-term trade into an investment.
- **Risk management:** longevity, daily preparation, small predefined loss, and immediate respect for invalidation. Separate trade idea from position size.
- **Evidence:** official biography reports exchange membership beginning in the 1980s, founding LBRGroup as a CTA, hedge-fund activity, and a career spanning more than four decades. Her books and interviews make the methods inspectable. Publicly accessible audited return series was not located in this review. **Grade B.**
- **Bot extraction:** volatility-regime filter; first-pullback continuation; failed-break reversal; time stop; no averaging down.

### 2. Stefano Serafini — retain, but downgrade prior claims

- **Markets/style:** futures; a 2026 magazine profile characterizes his approach as systematic/statistical arbitrage.
- **Strategy/entries/exits:** no sufficiently detailed primary rule set was located. Do not infer pair selection, lookback, z-score thresholds, hedge ratio, or exits.
- **Risk management:** no independently inspectable risk specification located.
- **Evidence:** the official World Cup historical standings show **second place in the 2022 futures championship with 19.9%**. The earlier magazine profile claims multiple titles and a 136% competition return, but this review did not locate matching official records or audit documents for those specific claims. **Grade A for the 2022 result; Grade D for the larger claims and undisclosed method.**
- **Bot extraction:** none yet. Create a research placeholder for cross-market relative-value signals, but do not train on invented Serafini rules.

### 3. Kyle Verhagen — ES/NQ-specific hypothesis source

- **Markets/style:** ES and NQ, 1-minute through 4-hour charts; daily/weekly bias; current-market-structure sweeps.
- **Strategy:** consistently define current highs/lows and multi-timeframe trend. Look for a sweep that confirms a transition between uptrend and downtrend. Buy in “discount” and target equilibrium, or sell in “premium” and cover at equilibrium.
- **Entry concept:** candle close after a confirmed swing high/low and sweep, preferably with ES/NQ agreement and higher-timeframe alignment.
- **Exit concept:** structural thesis target—often the 50% equilibrium of the active range—not a fixed R multiple. Stop sits where the thesis is structurally invalid.
- **Risk management:** normal size relative to account; do not increase risk merely because nominal funding increases; wait for the highest valid timeframe to confirm. His interview also documents prior account blowups when he lacked hard stops, which is evidence for mandatory automated loss limits.
- **Evidence:** detailed first-person JoinProp profile says he first became funded through Topstep in November 2023 and labels its receipts “verified funded,” but it does not provide a complete independently audited return, drawdown, payout, or transaction history. **Grade C.**
- **Bot extraction:** multi-timeframe swing-state machine; sweep/reclaim signal; equilibrium target; cross-index confirmation. Treat all thresholds as unknown parameters to be tested, not copied.

### 4. Andrea Unger — highest-priority system architecture source

- **Markets/style:** systematic multi-strategy futures trading.
- **Strategy:** portfolio of rule-based systems across markets rather than one universal setup; trend, countertrend, bias, and pattern components are selected by instrument and regime.
- **Entry/exit concept:** fully specified rules, market-specific logic, and diversified systems. Stops, session exits, and profit exits are strategy variables tested as part of the whole system.
- **Risk management:** position sizing, strategy diversification, market diversification, and avoidance of single-system dependence.
- **Evidence:** official World Cup standings show first-place results in 2008 (671.9%), 2009 (115.4%), and 2010 (239.6%), plus a 2012 quarterly win (82.8%). Competition evidence is real-money and official, but not equivalent to a scalable institutional track record. **Grade A for competition results; Grade B for methodology.**
- **Bot extraction:** ensemble architecture; multiple small edges; market/regime-specific parameter sets; capital allocator that caps correlated exposure.

### 5. Kevin Davey — highest-priority validation source

- **Markets/style:** algorithmic futures systems, including stock-index futures.
- **Strategy:** generate simple hypotheses, reject most of them, and advance only robust candidates through a staged development pipeline.
- **Entry/exit concept:** explicit and testable; no special allegiance to one indicator. Entry, stop, target, sizing, and session logic must be defined before testing.
- **Risk management:** realistic commissions/slippage, out-of-sample data, walk-forward testing, Monte Carlo analysis, incubation, small initial live size, and multiple low-correlated systems.
- **Evidence:** official World Cup standings show second in 2005 (148.0%), first in 2006 (106.7%), and second in 2007 (111.6%). His site describes the process and distinguishes hypothetical from live performance. **Grade A for competition results; Grade B for method.**
- **Bot extraction:** research governance, not a signal. Every strategy in this package must pass a Davey-style funnel before deployment.

### 6. Larry Williams — strong evidence, lower day-trading fit

- **Markets/style:** futures; seasonal, sentiment/Commitment of Traders, volatility, momentum, and short-term patterns.
- **Strategy:** combine market structure with recurring calendar/seasonal and sentiment effects; use volatility-aware stops and money management.
- **Entry/exit concept:** published rules vary by setup; many are not intraday and should not be transplanted into ES/NQ without redefinition.
- **Risk management:** volatility-responsive placement and aggressive position sizing are prominent in his historical work; the latter is unsuitable as a bot default.
- **Evidence:** official World Cup standings show a 1987 first-place result of 11,376%. This extraordinary leveraged competition outcome is verifiable as a contest result but is not an appropriate risk target. **Grade A for competition result; Grade B for published methods.**
- **Bot extraction:** day-of-week/seasonality features and volatility-normalized risk only. Do not copy championship leverage.

### 7. Al Brooks — strong ES price-action vocabulary, limited performance proof

- **Markets/style:** E-mini S&P 500 price action, usually five-minute charts.
- **Strategy:** classify trend vs trading range; trade breakouts, failed breakouts, pullbacks, wedges, and measured moves. Most bars are interpreted in context rather than as standalone candlestick patterns.
- **Entry concept:** second-entry pullbacks in a trend, breakouts with follow-through, or failed breakouts at range extremes.
- **Exit concept:** exit when follow-through fails or opposing structure appears; scalp in ranges and allow wider targets in strong trends.
- **Risk management:** stop beyond structural invalidation; position size must shrink as stop distance expands; avoid low-quality middle-of-range entries.
- **Evidence:** large body of ES-specific books, courses, and daily analysis, but no independently audited return series located. **Grade B for method; Grade C for performance.**
- **Bot extraction:** trend/range classifier, second-entry feature, breakout follow-through test, measured-move target, and “middle-of-range no-trade” zone.

### 8. John F. Carter — volatility-compression method source

- **Markets/style:** futures and options, including equity-index products.
- **Strategy:** the TTM Squeeze identifies volatility compression when Bollinger Bands contract inside Keltner Channels, then looks for momentum-backed expansion.
- **Entry concept:** enter on/after squeeze release when momentum and higher-timeframe direction agree; avoid taking every squeeze blindly.
- **Exit concept:** momentum deterioration, opposite signal, predefined structural/ATR stop, or target tied to expansion.
- **Risk management:** defined risk and multi-timeframe confirmation; options implementations are not directly portable to futures.
- **Evidence:** the method is published and widely inspectable through *Mastering the Trade* and official educational material; no audited trader-level return series located. **Grade B for method; Grade C for performance.**
- **Bot extraction:** compression ratio and release event as a feature; require regime, volume, and cost filters before treating it as an entry.

### 9. Mark B. Fisher — opening-range architecture source

- **Markets/style:** liquid, volatile futures and stocks; ACD opening-range method.
- **Strategy:** define an opening range, then calculate A-up/A-down confirmation distances and B/D invalidation exits. A failed A signal may become a C reversal.
- **Entry concept:** for the historical S&P example, monitor the first 15 minutes; require movement beyond the opening range by a volatility-informed amount and persistence/confirmation.
- **Exit concept:** B exit back through the opening range; C reversal if price breaks the opposite side; day traders generally flatten by session end.
- **Risk management:** choose markets/regimes with sufficient liquidity and volatility; avoid low-volatility ranges. The published source notes Fisher did not consider the S&P his best ACD market, so ES/NQ use must be independently validated.
- **Evidence:** published in *The Logical Trader* and summarized with specific rules in a sourced technical article. No public audited personal series located. **Grade B.**
- **Bot extraction:** opening-range continuation and failed-break reversal; use ATR/realized-volatility offsets rather than fixed legacy points.

### 10. Adam Grimes — context and falsification source

- **Markets/style:** professional multi-asset trader/system developer; futures and index futures among his markets.
- **Strategy:** trend integrity, pullbacks, failure tests, reversal complexes, volatility/volume expansion, and explicit comparison against a baseline.
- **Entry concept:** trade only when imbalance is observable: short-term range/volume expansion, trending bars, consolidation near an extreme, breakout/failure with momentum, or an exhaustion/reversal complex.
- **Exit concept:** conservative partial profits (he gives an example of taking partials at 1R), then manage remaining exposure using trend integrity or invalidation.
- **Risk management:** quantify “context,” test every occurrence, compare with an appropriate baseline, and stand aside when noise dominates.
- **Evidence:** official biography documents professional roles since 1995 and extensive published primary material; no complete audited return series located. **Grade B for career/method; Grade C for performance.**
- **Bot extraction:** regime features, failure-test logic, relative volume/range filters, 1R partial study, and explicit no-trade state.

### 11. Jim Dalton — auction-market context source

- **Markets/style:** Market Profile/auction-market theory and futures.
- **Strategy:** distinguish balance from imbalance using value area, point of control, excess, poor highs/lows, and acceptance/rejection outside prior value.
- **Entry concept:** responsive trade back toward value after rejection outside value; initiative trade when price gains acceptance outside value with continuation.
- **Exit concept:** opposite side/center of value for responsive trades; developing value and structural references for initiative trades.
- **Risk management:** do not use profile levels mechanically; context and acceptance matter. Stops belong beyond the auction premise, not at arbitrary tick counts.
- **Evidence:** detailed published books and educational history; no public audited return series located. **Grade B for method; Grade C for performance.**
- **Bot extraction:** prior-day value area/POC, overnight inventory, initial balance, acceptance-time metric, and responsive-vs-initiative classifier.

### 12. Peter Davies — execution and order-flow source

- **Markets/style:** futures order flow/DOM; founder of Jigsaw Trading.
- **Strategy:** use depth, traded volume, pace, absorption, and liquidity behavior to confirm or reject a contextual trade.
- **Entry concept:** order flow is a trigger/confirmation around known context, not a standalone prediction engine.
- **Exit concept:** exit when expected participation fails, absorption flips, or liquidity/pace no longer supports the thesis.
- **Risk management:** preparation, execution review, and detailed journaling; beware spoofable resting depth and overreaction to microstructure noise.
- **Evidence:** inspectable educational framework and platform, but no audited personal performance record located. **Grade B for execution framework; Grade C for performance.**
- **Bot extraction:** use trades/volume/imbalance and fill-quality features only after a higher-level setup fires. Never use raw DOM size alone.

### 13. Tom Hougaard — behavioral execution and public-call source

- **Markets/style:** very active index/FX day trading and swing trading; price action.
- **Strategy:** trade obvious price-action structures, press favorable trades, and focus on asymmetric behavior rather than a secret indicator.
- **Entry concept:** discretionary live calls based on price action and market context.
- **Exit concept:** cut losing trades and hold/add to winners when the thesis strengthens; exact rules are not fully mechanical.
- **Risk management:** extensive trade journaling and psychological rehearsal; his public materials emphasize that behavioral errors dominate.
- **Evidence:** his official site offers free time-stamped live channels and a read-only Excel track record, improving transparency, but the data was not independently audited in this review. **Grade C.**
- **Bot extraction:** post-trade error taxonomy and “add only to profitable/confirmed positions” research. Do not encode discretionary aggression without strict exposure caps.

### 14. Rob Hoffman — order-flow/inventory hypothesis source

- **Markets/style:** intraday and swing trading across futures, forex, stocks, options, and ETFs.
- **Strategy:** public descriptions emphasize institutional order flow and an “Inventory Retracement Bar.” Detailed proprietary thresholds were not independently available.
- **Entry/exit/risk:** insufficient public rule precision for faithful automation. Do not reverse-engineer from marketing language.
- **Evidence:** his official site claims seven international trading championships and the 2026 magazine profile cites a 147% competition return, but the reviewed World Cup historical page does not list him and no independent audit document was located. **Grade C/D.**
- **Bot extraction:** none under his name until rules and contest records are independently verified. Generic inventory/mean-reversion ideas may be tested without attributing them to him.

### 15. David Trullas Vila — verified result, undisclosed edge

- **Markets/style:** futures day trading; public strategy details were not located.
- **Strategy/entries/exits/risk:** unknown—do not invent them.
- **Evidence:** official World Cup standings show first place in 2025 Q2 (712.1%), Q3 (800.6%), Q4 (930.7%), 2026 Q1 (585.4%), and 2026 Q2 (2,222.6%); he was leading 2026 Q3 at the research cutoff, but that quarter was still in progress. These are extraordinary competition results, not proof of scalable or low-drawdown trading. **Grade A for listed competition results; Grade D for method.**
- **Bot extraction:** none. Use as a reminder that verified results and extractable method are separate questions.

## What survives the evidence filter

| Candidate module | Source lineage | ES/NQ fit | Rule clarity | Evidence use | Priority |
|---|---|---:|---:|---:|---:|
| Opening-range continuation/failure | Fisher, Raschke, Brooks | High | High | Method evidence, not return evidence | 1 |
| Trend pullback after expansion | Raschke, Brooks, Grimes | High | Medium-high | Long published history | 1 |
| Auction rejection/acceptance | Dalton + Davies | High | Medium | Strong conceptual, weak audited performance | 2 |
| Volatility squeeze release | Carter + Grimes | High | High | Published method | 2 |
| Multi-timeframe sweep to equilibrium | Verhagen | High | Medium | Self-reported profile only | 3 |
| System ensemble/allocator | Unger + Davey | High | High | Official competition + published process | 1 |
| Seasonality/COT | Williams | Low for intraday trigger; medium as context | Medium | Official contest + published work | 3 |
| Statistical arbitrage attributed to Serafini | Serafini profile | Unknown | Low | Unverified method claims | Hold |

## Bot-ready strategy specifications

These are **research hypotheses derived from public concepts**, not claims that the named traders use these exact formulas.

### Module OR-1: Opening-range continuation

**Intent:** capture initiative activity after the cash-session open.

- Instruments: ES, NQ; test separately.
- Session: CME equity-index regular trading hours, 09:30–16:00 America/New_York. Store timestamps in UTC and convert using an exchange calendar/DST-aware library.
- Opening range: test 5, 15, and 30 minutes; choose one only through nested walk-forward selection.
- Features:
  - OR high, low, width;
  - OR width / 20-day median OR width;
  - distance to overnight high/low, prior high/low, prior value area;
  - VWAP slope and distance;
  - first-30-minute relative volume;
  - ES/NQ directional agreement;
  - scheduled-event flag.
- Long trigger: close above `OR_high + k * ATR_1m(20)`; next bar does not close back inside OR; VWAP slope positive; relative volume above threshold; no stale-data flag.
- Short trigger: symmetric.
- Initial stop: below breakout structure or `entry - s * ATR_1m`, whichever produces the smaller permitted risk while remaining outside normal noise. Reject trade if valid stop exceeds max dollar risk.
- Exit candidates: 1R partial plus trailing structure; session close; return inside OR; time stop after `N` bars without favorable excursion.
- No trade: OR abnormally wide/narrow, spread or slippage spike, conflicting ES/NQ state, tier-1 news lockout, or price immediately enters prior balance with no acceptance.

### Module OR-2: Failed opening-range breakout

**Intent:** capture trapped breakout inventory and return toward equilibrium.

- Preconditions: initial break outside OR by a volatility-normalized buffer.
- Failure trigger: price closes back inside OR within `M` bars and order-flow/volume fails to confirm the breakout.
- Entry: first retest that cannot reclaim the failed side, or close through a short-term swing in the reversal direction.
- Target sequence: OR midpoint/VWAP, then opposite OR boundary only if value is migrating.
- Stop: beyond failed-break extreme plus buffer.
- Abort: strong trend-day evidence, expanding relative volume in breakout direction, or acceptance outside OR.

### Module TP-1: Trend pullback and resumption

**Intent:** combine Raschke/Brooks/Grimes trend logic.

- Trend state requires at least three of: rising/falling session VWAP; directional efficiency ratio; aligned 5/15/60-minute swing structure; price outside prior value; positive/negative cumulative delta slope; expanding range/volume.
- Pullback: 2–8 bars, lower range and volume than impulse, retracing 25–65% of impulse without breaking structural invalidation.
- Trigger: break of pullback micro-swing with renewed volume/range and no opposing ES/NQ divergence.
- Stop: beyond pullback extreme.
- Exit: partial at 1R is a test branch, not a fixed assumption; runner trails behind confirmed swings or VWAP band; time stop if resumption does not occur.
- No trade: middle of a balanced range, trend efficiency below threshold, pullback volume exceeds impulse volume, or event risk is imminent.

### Module AR-1: Auction rejection vs acceptance

**Intent:** turn Market Profile context into measurable states.

- Reference levels: prior value-area high/low, prior POC, overnight high/low, initial-balance high/low, weekly VWAP.
- Rejection: excursion through a level followed by return within `T` minutes, low time-at-price outside, and inability to build volume outside.
- Acceptance: at least `T_accept` minutes or `V_accept` fraction of session volume outside, with developing POC/value migrating in breakout direction.
- Responsive trade: fade rejection toward VWAP/POC.
- Initiative trade: enter first controlled pullback after acceptance.
- DOM/flow can confirm but never override the auction state.

### Module SQ-1: Compression expansion

- Compute Bollinger Band width, Keltner width, realized volatility percentile, and range compression.
- Squeeze state requires multi-bar compression below a percentile threshold.
- Release requires close outside compression range, rising relative volume, momentum agreement, and acceptable spread/slippage.
- Direction filter: higher-timeframe trend or successful auction acceptance.
- Exit: momentum decay, failed release back inside range, ATR trail, or session cutoff.
- Guard against look-ahead: indicators use only completed bars.

### Module MS-1: Multi-timeframe sweep to equilibrium

**Intent:** test the Verhagen concept without assuming its profitability.

- Define swing highs/lows algorithmically with a causal pivot rule; never use future bars to confirm a historical pivot unless entry is delayed until confirmation.
- Higher-timeframe state: daily/4h/1h; execution state: 30m/5m/1m.
- Sweep: trade beyond confirmed swing, then close back through it and produce opposite micro-structure break.
- Entry: confirmation close or first retest.
- Target: midpoint of the active structural range, then VWAP/POC if aligned.
- Stop: beyond sweep extreme plus volatility buffer.
- This module stays in research until it passes the same out-of-sample standard as OR-1 and TP-1.

## Shared risk engine — mandatory and non-bypassable

All percentages are starting research defaults and must be calibrated to the account, broker, and empirical drawdown distribution.

1. **Per-trade risk:** begin paper testing at 0.10%–0.25% of allocated strategy equity. Live deployment should start at the lowest feasible contract size (MES/MNQ before ES/NQ).
2. **Daily stop:** hard stop at the smaller of 3R or 0.75% of strategy equity; flatten, cancel all orders, and lock until next session.
3. **Consecutive-loss brake:** after three full-risk losses, lock the strategy for the session. Do not “win it back.”
4. **Portfolio heat:** aggregate worst-case stop loss across ES and NQ. Because correlation can spike, do not treat simultaneous ES and NQ positions as diversified.
5. **Event lockouts:** configurable no-entry window around CPI, FOMC decisions/press conferences, NFP, and exchange-halting events. Existing-position policy must be explicit.
6. **Slippage circuit breaker:** stop new entries when realized slippage or bid/ask spread exceeds a rolling percentile/budget.
7. **Data-quality circuit breaker:** no trading on stale quotes, sequence gaps, clock drift, missing bars, crossed markets, or feed disagreement.
8. **Execution idempotency:** every intent has a unique ID; retries query broker state before resubmission; unknown order state means freeze and reconcile, never duplicate.
9. **Position reconciliation:** broker position is authoritative. Compare internal/broker state on every fill and heartbeat.
10. **Flat-by-policy:** unless a separately approved overnight strategy exists, flatten before the session cutoff and confirm at broker.

Position size:

`contracts = floor(risk_budget_dollars / (stop_points * point_value + estimated_round_trip_cost))`

Reject the trade when the result is below one contract; never tighten the stop merely to force a larger position.

## Reliability and contingency controls

The trading engine must run as a state machine:

`BOOT -> WARMUP -> READY -> ARMED -> POSITION_OPEN -> EXITING -> RECONCILING -> READY`

Any integrity failure transitions to `SAFE_HALT`; only a verified recovery procedure may return it to `READY`.

Required heartbeats:

- primary and backup market-data timestamps;
- broker/order gateway;
- strategy process;
- recorder/event log;
- clock synchronization;
- disk/database availability;
- risk engine.

On failure:

1. Freeze new entries.
2. Determine broker-authoritative positions and working orders.
3. Cancel working orders if state is known and cancellation is safe.
4. Flatten only according to a pre-approved emergency policy; avoid blind duplicate flatten orders.
5. Persist an append-only incident record.
6. Restart the failed component with exponential backoff and a maximum retry count.
7. Require data warmup and state reconciliation before re-arming.

Daily incident log fields: incident ID, UTC time, component, symptom, detection source, market state, open exposure, automated action, broker-confirmed outcome, root cause, data lost/corrupted, fix, regression test, owner, and closure time.

## Research and validation protocol

### Data

- Use continuous and individual-contract data; roll logic must be explicit.
- For execution studies, retain tick/quote/trade data where licensed; bar-only backtests cannot validate fill quality or DOM rules.
- Adjust session calendars, holidays, early closes, DST, contract tick/point values, fees, and exchange rule changes.
- Preserve raw immutable data and checksum each ingest.

### Bias controls

- No future-confirmed pivots at entry time.
- No indicator values from incomplete future bars.
- No same-bar entry at a close unless the simulator models when the signal became observable and how the order filled.
- Include commissions, exchange/NFA fees, bid/ask spread, slippage, rejected orders, and partial fills.
- Keep a final untouched holdout period. Repeatedly checking it converts it into training data.

### Test funnel

1. Unit-test every feature and order rule.
2. Baseline test with fixed, economically reasonable parameters.
3. Sensitivity grid; require a broad stable region, not one sharp optimum.
4. Anchored and rolling walk-forward tests.
5. Purged/embargoed validation for overlapping labels.
6. Test ES and NQ separately, then combined with correlation-aware exposure.
7. Segment by year, volatility quartile, trend/range regime, time of day, news/non-news, and long/short.
8. Monte Carlo resample trades and slippage; size to the 95th/99th-percentile drawdown, not the backtest maximum.
9. Paper trade with the exact production code path.
10. Shadow trade against live broker data with orders disabled.
11. Micro-contract canary; scale only after minimum sample and execution-quality gates.

### Promotion gates

A candidate cannot reach live status unless all are true:

- positive net expectancy after conservative costs in aggregate and in multiple walk-forward folds;
- profit factor and Sharpe/Sortino reported with confidence intervals, not single-point claims;
- maximum drawdown within capital and psychological limits under Monte Carlo stress;
- no single day, month, or regime provides a dominant share of total profit;
- parameter stability across neighboring values;
- sufficient trade count for the claimed frequency;
- live-paper fills and latency remain inside the modeled envelope;
- kill switches, restart, reconciliation, and recorder-failure tests pass.

Reject or quarantine a strategy if live/paper divergence exceeds its control limits, feed quality degrades, or rolling expectancy falls outside the predeclared confidence band. Do not silently re-optimize a failing system.

## Metrics the bot must report

- net expectancy per trade in dollars, points, ticks, and R;
- win rate, average win/loss, payoff ratio;
- profit factor with bootstrap interval;
- Sharpe, Sortino, Calmar, and return/max-drawdown;
- maximum drawdown, duration, recovery time;
- MAE/MFE and time in trade;
- consecutive losses and tail loss;
- exposure by instrument, direction, hour, regime, and setup;
- slippage by order type/time/volatility;
- rejected/partial/duplicate-order counts;
- stale-feed time and recorder completeness;
- strategy correlation and combined portfolio heat;
- live-vs-simulated distribution drift.

## Recommended build order

1. Implement shared session/calendar, feature, cost, and risk infrastructure.
2. Implement OR-1 and OR-2 with causal signals and fixed baselines.
3. Implement TP-1 and the regime classifier.
4. Add auction context (AR-1) as a filter before using it as an independent strategy.
5. Add SQ-1 as a challenger.
6. Add MS-1 last because its swing/sweep definitions are easiest to overfit.
7. Run all modules through one validation pipeline and one production risk engine.

## Machine-ingestion instructions

The companion file `ES_NQ_Strategy_Specs.json` is the canonical structured input. The bot should:

- treat every module as `research_only`;
- refuse live orders while `deployment_status != approved_live`;
- preserve evidence grades and unresolved fields;
- never fill `unknown` strategy details using model inference;
- log the exact source, code version, data snapshot, parameters, and test run ID for every result;
- require a human-reviewed promotion record before changing deployment status.

## Sources

Accessed 2026-09-20 unless noted.

1. World Cup Trading Championships, official current standings and disclosures: https://www.worldcupchampionships.com/world-cup-trading-championship-standings
2. World Cup Trading Championships, official historical standings: https://www.worldcupchampionships.com/world-cup-trading-championship-historical-standings
3. Linda Bradford Raschke official site and biography: https://lindaraschke.net/
4. Raschke & Connors, *Street Smarts: High Probability Short-Term Trading Strategies* (book).
5. JoinProp, Kyle Verhagen profile, 2026-08-31: https://joinprop.com/one-prop-trader-a-day/one-prop-trader-a-day-kyle-verhagen/
6. Financial Trader Magazine 2026 ranking—the source of claims requiring independent corroboration: https://www.financialtradermagazine.com/articles/top-10-traders-2026
7. Unger Academy official methodology/resources: https://ungeracademy.com/
8. Kevin Davey/KJ Trading Systems official process description: https://kjtradingsystems.com/
9. Larry Williams official site: https://www.larrywilliams.com/
10. Al Brooks official course/daily ES analysis hub: https://www.brookstradingcourse.com/
11. John F. Carter, *Mastering the Trade* (book); Simpler Trading official site: https://www.simplertrading.com/
12. Mark B. Fisher, *The Logical Trader* (book); detailed ACD summary: https://www.investopedia.com/articles/technical/04/032404.asp
13. Adam Grimes, “How I Trade,” “When to Trade,” and S&P trade example: https://www.adamhgrimes.com/how-i-trade-part-1-of-2/ ; https://www.adamhgrimes.com/when-to-trade-and-when-to-stay-out/ ; https://www.adamhgrimes.com/patterns-context-and-a-clean-long-in-the-s-p/
14. James F. Dalton et al., *Mind Over Markets* and *Markets in Profile* (books).
15. Jigsaw Trading official order-flow and analytics site: https://www.jigsawtrading.com/
16. Tom Hougaard official site, live-channel and public-track-record description: https://tradertom.com/
17. Rob Hoffman official site: https://www.becomeabettertrader.com/

## Final warning

No profile, championship, book, or public call proves that a strategy will remain profitable. The package is designed to prevent authority bias: trader ideas generate hypotheses; only your own clean, cost-aware, out-of-sample ES/NQ evidence can promote them.
