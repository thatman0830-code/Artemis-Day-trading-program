# Data Contract v1

Status: APPROVED
Governing document: 00_System/Daily Trading Brain - MASTER SCRIPT.md
Purpose: Canonical schemas for every layer of the Daily Trading Brain so that every meaningful trading decision — executed, planned, missed, cancelled, rejected, no-trade, invalidated, late entry, confirmation failure, execution-quality issue — becomes learnable, queryable data.

Core principle: a no-trade decision is data, not an absence of data. It is recorded with the same structural weight as an executed trade.

Core principle: preserve the distinction between Information / Analysis / Hypothesis / Recommendation / User Decision / Executed Trade, and between Trade Outcome / Decision Quality / Execution Quality / Process Quality, as explicit fields wherever applicable — not only in prose.

No numeric validation thresholds are invented beyond what the Master Script specifies. Where the Master Script leaves a threshold undefined (e.g., what counts as a "small sample" in Section 19), this contract resolves it qualitatively rather than inventing a number.

---

## 1. Daily Trading Records (01_Daily)

```
---
date: YYYY-MM-DD
type: trading-day
tags: [trading, daily]
regime: "[[03_Concepts/...]]"
records: ["[[06_Trades/...]]"]
patterns_touched: ["[[04_Patterns/...]]"]
---
```

Required: date, type.
Optional: regime, records, patterns_touched — populate progressively.
Body: unchanged from Master Script Section 14 (Pre-Market Context / Trade Plan / During Trade / Post-Trade).

Claude may write automatically: append to records: and patterns_touched: as new linked records are created during the session.
Requires confirmation: changing regime: after it has already been set for the day.
Never retroactively changed: the Pre-Market Context section once the session has started.

---

## 2. Trade Records (06_Trades)

One schema, one record_kind enum, covering every meaningful trading decision.

```
---
type: trade
record_kind: ""            # executed | planned | missed | cancelled | rejected_setup | invalidated_setup
trade_id: ""                # YYYY-MM-DD-INSTRUMENT-NN
date: YYYY-MM-DD
instrument: ""
direction: ""                # long | short
regime_at_decision: "[[03_Concepts/...]]"
pattern_setup: "[[04_Patterns/...]]"    # unvalidated/hypothesized setup reference
playbook_setup: "[[05_Playbook/...]]"   # validated setup reference
thesis_link: "[[01_Daily/...]]"

trigger: ""
required_confirmation: ""
confirmation_status: ""      # confirmed | partially_confirmed | unconfirmed | invalidated

invalidation: ""
entry_price:
stop_price:
target_price:
position_size:
expected_risk_reward:
risk_defined_before_entry: true|false

execution_state: ""          # planned_entry | triggered_entry | missed_entry | late_entry | cancelled_entry
execution_quality: ""

exit_price:
exit_date: YYYY-MM-DD
trade_outcome: ""             # win | loss | breakeven | not_applicable
r_multiple:
mfe:
mae:
decision_quality: ""          # sound | questionable | poor
process_quality: ""           # followed_plan | deviated | no_plan_existed

no_trade_reason: ""
no_trade_condition_ref: ""    # one of the Section 11 hard conditions, or "discretionary"
what_would_change_this: ""
monitoring_while_waiting: ""

pattern_links: ["[[04_Patterns/...]]"]
related_records: ["[[06_Trades/...]]"]

tags: [trade]
---

## Trade Plan
## During-Trade Notes
## Post-Trade Review
```

### record_kind values
- executed — a trade was actually taken (Sections 12-15)
- planned — a trade plan exists, not yet triggered (Section 12)
- missed — trigger/confirmation occurred but entry wasn't taken (Section 12)
- cancelled — plan voided before trigger (Section 12)
- rejected_setup — a candidate setup was evaluated and explicitly rejected, including deliberate no-trade decisions (Sections 07, 11)
- invalidated_setup — a setup hit a predefined invalidation condition before entry (Section 09)

The no_trade_reason / no_trade_condition_ref / what_would_change_this / monitoring_while_waiting fields apply specifically to record_kind: rejected_setup, per Master Script Section 11's requirement to state why there is no trade, what would make a trade valid, and what to monitor while waiting. no_trade_condition_ref references one of Section 11's seven existing hard no-trade conditions when applicable, or "discretionary" when the no-trade call falls outside that list — this preserves Section 11's rule that the hard list must not be silently altered.

Required for every record: type, record_kind, trade_id, date, instrument, regime_at_decision, thesis_link.
Required additionally when record_kind is planned, executed, or missed: invalidation, risk_defined_before_entry.
Required additionally once record_kind: executed reaches close: exit_price, trade_outcome, decision_quality, process_quality.
Optional always: mfe, mae, pattern_links, related_records, pattern_setup, playbook_setup.

Claude may write automatically: creating a new record when a trade is planned, executed, or rejected during an active session, populating fields from information already stated in conversation, appending during-trade notes.
Requires explicit confirmation: setting trade_outcome, decision_quality, or process_quality.
Never retroactively changed: trigger, invalidation, entry_price, stop_price, expected_risk_reward, and all no_trade_* fields as originally recorded. Plan changes are recorded as new dated entries under During-Trade Notes, not edits to the original plan fields.

---

## 3. No-Trade / Rejected / Missed / Cancelled Decision Records

Not a separate schema. These are 06_Trades records using record_kind values rejected_setup, missed, cancelled, or invalidated_setup, per Section 2 above. This ensures no-trade decisions live in the same queryable table as executed trades rather than a separate, easily-omitted location.

---

## 4. Pattern Records (04_Patterns)

```
---
type: pattern
pattern_name: ""
status: ""          # observation | candidate_pattern | recurring_pattern | under_review | validated_pattern | playbook_rule
first_observed: YYYY-MM-DD
last_observed: YYYY-MM-DD
regimes: []
instruments: []
occurrence_count:
confidence: ""
supporting_records: ["[[06_Trades/...]]"]
contradictory_records: ["[[06_Trades/...]]"]
tags: [pattern]
---

## Conditions Observed
## Expected Behavior
## Actual Behavior
## Potential Explanation
## Evidence For
## Evidence Against
## Applicable Regimes
## Known Limitations
## Validation Status
## Next Evidence Required
```

Required: type, pattern_name, status, first_observed.
Never retroactively changed: first_observed.
Claude may write automatically: creating a new observation-status entry when a genuinely novel pattern surfaces in conversation.
Requires confirmation: any status advancement (e.g., candidate_pattern to recurring_pattern). Claude proposes advancement when Section 17's evidence criteria appear met; the user decides.

Status values follow the single canonical lifecycle defined in Master Script Sections 16-17:
observation -> candidate_pattern -> recurring_pattern -> under_review -> validated_pattern -> playbook_rule

---

## 5. Playbook Records (05_Playbook)

```
---
type: playbook_entry
name: ""
category: ""    # hard_rule | validated_pattern | preferred_setup | heuristic
applicable_regimes: []
required_conditions: []
confirmation: ""
invalidation: ""
preferred_instruments: []
typical_risk_characteristics: ""
validation_status: ""
last_reviewed: YYYY-MM-DD
source_pattern: "[[04_Patterns/...]]"
tags: [playbook]
---

## Description
## Historical Evidence
## Known Failure Conditions
## Examples
## Counterexamples
```

Required: type, name, category, validation_status, last_reviewed, source_pattern.
Claude may write automatically: never. Every write here is a promotion or demotion event. Claude proposes; the user confirms before the write occurs.
Never retroactively changed: source_pattern.

---

## 6. Concept Records (03_Concepts)

```
---
title: ""
type: concept
status: ""
created: YYYY-MM-DD
tags: [concept, ...]
---
```

Adopts the existing Templates/Concept Note/03_concepts.md structure as canonical. No redesign.
Note: 03_Concepts/Market Regime.md does not currently conform to this schema. This is flagged, not corrected, pending explicit approval for that specific change.

---

## 7. Analytics Inputs/Outputs (07_Analytics)

Inputs: 06_Trades frontmatter exclusively, queried live via Dataview. Never hand-copied into Analytics notes.

Outputs, limited to the list in Master Script Section 19: number of trades, win rate, average win, average loss, expectancy, profit factor, average risk/reward, maximum drawdown, average holding time; performance by setup, regime, instrument, direction, catalyst environment; execution quality; rule violations; no-trade decisions; missed opportunities.

Queries for count-based statistics (no-trade decisions, missed opportunities, rule violations) must query the full 06_Trades record set across all record_kind values. Queries for outcome-based statistics (win rate, expectancy, profit factor) are correctly scoped to record_kind: executed only, since those statistics are inherently defined over completed trades.

Sample-size handling: no numeric threshold is defined. Every Analytics output states sample size in words (e.g., "based on 3 observations" or "based on 40+ observations") rather than asserting a fixed numeric cutoff for reliability, per Master Script Section 19's caution against treating small samples as reliable conclusions.

Claude's write authority: may create and update queries; may never assert an interpretive conclusion (e.g., "this setup has an edge") as fact — only the query and its raw output. Interpretation remains with the user.

---

## Resolved Design Decisions

1. Setup reference fields: two separate fields, pattern_setup and playbook_setup, both optional. Keeps validated and unvalidated setup influences distinct in the data itself.
2. Pattern status advancement: Claude proposes when Section 17 criteria appear met; the user decides. No automatic advancement.
3. Small-sample handling: qualitative description only, no invented numeric threshold.
4. Stale planned trades: manual reclassification only. No automatic expiry.
5. 06_Trades folder structure: flat folder, trade_id naming convention YYYY-MM-DD-INSTRUMENT-NN.

---

## Boundaries Carried Forward From the Master Script (Section 23)

No execution of real trades or financial transactions through this system.
No deletion, bulk replacement, or large-scale restructuring without explicit user approval.
No rewriting of historical trade, pattern, or journal records.
No manufactured statistics when the underlying sample is insufficient.
Read before write. Search before create. Targeted writes over destructive replacement.
Explain materially significant changes before making them, including Playbook promotions and Pattern status advancements.
Final authority for actual trading decisions remains with the user.
