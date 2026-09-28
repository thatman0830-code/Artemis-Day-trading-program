# Decision Capture Protocol v1

Status: Draft, pending approval to activate
Governing documents: 00_System/Daily Trading Brain - MASTER SCRIPT.md, 00_System/DATA CONTRACT v1.md
This protocol does not modify either governing document. It operationalizes them.

---

## 1. Purpose

This document defines exactly how the Daily Trading Brain converts real trading activity into structured 06_Trades records during actual use. It governs Claude's behavior — what Claude may write automatically, what requires user confirmation, and what must never be inferred or invented. It does not introduce new trading rules, new record_kind values, or new statistics beyond what the Master Script and Data Contract v1 already define.

---

## 2. Governing Principles

- A meaningful trading decision is data, whether or not a trade occurs. A no-trade decision is captured with the same structural weight as an executed trade.
- Claude analyzes and recommends. The user decides. These are never the same event.
- Nothing is recorded as executed unless execution was explicitly established.
- Judgment fields (decision_quality, process_quality, trade_outcome interpretation) are proposed by Claude and confirmed by the user — never asserted unilaterally.
- Historical decision fields are never rewritten to reflect information that arrived later. What was known at the time is preserved permanently.
- Not every market comment is a trade record. Only meaningful decisions are captured.

---

## 3. The Information -> Analysis -> Hypothesis -> Recommendation -> User Decision -> Executed Trade Distinction

These are six distinct states. Claude must keep them visibly separate in conversation and in any record created, and must never collapse one into another.

| State | What it is | Who produces it | Example |
|---|---|---|---|
| Information | Raw market data or facts | Market / data sources | "SPX closed at 7,754." |
| Analysis | Interpretation of information against the Master Script's engines (regime, cross-asset, confirmation) | Claude | "This is consistent with a stalling uptrend given elevated dispersion." |
| Hypothesis | An explanation or scenario that may account for observed behavior | Claude | "If CPI is cool, yields likely fall and equities extend." |
| Recommendation | A specific setup or course of action Claude proposes | Claude | "A long SPX setup exists above 7,794 with invalidation at 7,743." |
| User Decision | The user's explicit choice to act, reject, or wait | User | "Take it," "Pass," "Not yet." |
| Executed Trade | An actual position has been entered | User (confirmed) | "Filled at 7,796." |

Claude must never:
- present a hypothesis as settled fact
- present a recommendation as though the user already accepted it
- present a planned trade as an executed trade
- present a setup (an opportunity) as a trade (an action taken)
- treat a profitable outcome as proof the decision was good
- treat a losing outcome as proof the decision was bad

---

## 4. What Counts as a Meaningful Decision (Capture Trigger)

Create or update a structured 06_Trades record when at least one of the following occurs:

- a setup is seriously evaluated (not just mentioned in passing)
- a trade plan is formed
- confirmation is assessed against a specific setup
- risk/invalidation is explicitly defined
- Claude makes a specific trade recommendation
- the user accepts a trade idea
- the user rejects a trade idea
- the user deliberately chooses not to trade a meaningful setup
- a planned setup is cancelled
- a setup's trigger/confirmation occurred but was not acted on (missed)
- a setup reaches a predefined invalidation condition
- an actual trade is entered
- an actual trade is exited
- an important execution deviation occurs (e.g., late entry, size deviation, plan not followed)

Do not create a record for:
- casual market commentary with no setup attached
- general regime discussion with no specific instrument/trigger under evaluation
- hypothetical "what if" discussion not tied to a real developing decision

If it is unclear whether something rises to the level of a meaningful decision, Claude should ask rather than assume either way.

---

## 5. Decision Lifecycle

The full lifecycle a decision passes through, mapped to the Master Script's engines:

1. Market Information — raw data (Sections 03-05)
2. Market Analysis — regime, cross-asset read (Sections 04-05)
3. Thesis / Hypothesis — Bull/Bear/Most-Likely (Section 06)
4. Setup Identification — Section 07
5. Confirmation Evaluation — Section 08
6. Risk / Invalidation Definition — Sections 09-10
7. Recommendation — Claude's proposed course of action (Section 07, "setup does not automatically authorize a trade")
8. User Decision — the user's explicit accept/reject/wait
9. Execution or No-Trade Outcome — Sections 11-12
10. Post-Decision Review — Section 15 (for executed trades) or the no-trade equivalent (Section 11's "why/what would change/what to monitor")
11. Structured Record Update — the 06_Trades record is created or updated to reflect the above

Stages 1-7 may occur entirely in conversation without a structured record if no meaningful decision point (Section 4 above) is reached. A structured record is created at or after the point a meaningful decision actually occurs, and is updated as the decision progresses through the remaining stages.

---

## 6. record_kind Definitions (Canonical — No Additions)

Exactly six values exist. This protocol does not add, rename, or infer additional values.

- executed — an actual position was entered. Never inferred from discussion alone; requires explicit confirmation that entry occurred.
- planned — a trade idea has been developed enough to warrant structured tracking (setup, trigger, invalidation defined) but has not yet triggered. Not an executed trade.
- missed — the setup's trigger/confirmation condition occurred, but the user did not enter.
- cancelled — the planned setup became invalid or conditions changed before the intended trigger/entry occurred (the trigger never happened; the plan was voided).
- rejected_setup — a candidate setup was evaluated and explicitly declined, including a deliberate no-trade decision. This is the sole no-trade record type (see Section 7).
- invalidated_setup — a predefined invalidation condition was reached before entry.

missed vs. cancelled vs. invalidated_setup are not interchangeable:
- missed: the trigger occurred; the user simply did not act on it.
- cancelled: the trigger never occurred; the plan was voluntarily withdrawn because conditions changed.
- invalidated_setup: a specific, predefined invalidation condition (Section 09) was hit before entry — a more specific case than a general "conditions changed" cancellation.

---

## 7. No-Trade Protocol

There is no separate no-trade schema. A deliberate no-trade decision is captured as:

record_kind: rejected_setup

with the four no-trade fields populated:
- no_trade_reason — why there is no trade
- no_trade_condition_ref — the specific Master Script Section 11 hard condition that applied (CPI volatility before confirmation / oil accelerating while yields rise / SPX breaking support without confirmation / BTC losing 50-day support / VIX toward or above 17.27 / conflicting macro signals pre-catalyst / forcing a position without a defined setup), or the literal value "discretionary" if none of the seven hard conditions applies
- what_would_change_this — what condition would make the trade valid
- monitoring_while_waiting — what should be watched in the meantime

The seven Section 11 hard conditions are never altered, added to, or reworded by this protocol or by any individual no-trade record. "discretionary" is the only allowed value outside that fixed list.

---

## 8. Planned / Missed / Cancelled / Invalidated — Operating Rules

- A planned record is not an executed trade and must never be described as one.
- Claude does not automatically convert planned -> cancelled or planned -> missed. Reclassification happens only when there is actual evidence the trigger occurred (-> missed, if not acted on) or that the plan was voluntarily withdrawn (-> cancelled) or that a specific invalidation condition was hit (-> invalidated_setup).
- A planned record with no further evidence simply remains planned. No automatic expiry (consistent with Data Contract v1's Resolved Design Decision 4).
- Reclassification is a state change to an existing record (updating record_kind and appending context to During-Trade Notes), not a rewrite of the original plan fields.

---

## 9. User Decision Boundary

- Claude may analyze, form a thesis, and recommend a setup. Claude may not claim the user decided to trade unless the user actually communicated that decision.
- Claude may not claim a trade was executed unless execution was explicitly established (e.g., the user states a fill, or confirms entry).
- If the user's intent is ambiguous ("I'm thinking about it," "maybe"), Claude leaves the record state unresolved (or does not yet create one) rather than guessing planned vs. rejected_setup vs. nothing. Claude asks for clarification when a structured record is about to be created and the classification is unclear.

---

## 10. Judgment-Field Rules

The following fields are judgment calls, not automatic outputs of price movement, and must never be inferred solely from profit or loss:

- decision_quality
- process_quality
- trade_outcome (the classification win/loss/breakeven/not_applicable is usually mechanical from price, but the interpretation of what that outcome means about the decision is not — see below)

Rule: trade_outcome (win/loss/breakeven) may be set from the mechanical entry/exit prices once a trade closes, since that is an objective fact, not a judgment. decision_quality and process_quality are always proposed by Claude and require explicit user confirmation before being written, per Data Contract v1 Section 2. A profitable trade is not automatically "sound" decision_quality, and a losing trade is not automatically "questionable" or "poor" — the Post-Trade Review (Master Script Section 15) is the actual basis for these fields, not the P&L alone.

---

## 11. Execution Quality — Kept Separate from Outcome

execution_quality is evaluated independently of trade_outcome, per Master Script Section 12 ("Execution quality must be evaluated separately from whether the trade eventually made money"). A profitable trade can carry poor execution_quality (e.g., chased entry, ignored the plan and got lucky). A losing trade can carry excellent execution_quality (e.g., entry/exit exactly per plan, stopped out cleanly on a valid invalidation). Claude proposes execution_quality based on how closely the actual entry/exit matched the planned trigger/invalidation/target — not based on the dollar result.

---

## 12. Daily <-> Trades Relationship

- The 01_Daily note remains the narrative/context record for the session (Master Script Section 14).
- The 06_Trades record is the structured decision data for one specific decision.
- When a structured record is created, the daily note's records: frontmatter field is updated to link to it. The full trade record is not duplicated into the daily note's prose.
- The 06_Trades record's thesis_link: field links back to the originating daily note, when the decision arose from a specific day's session.
- If a decision touches an existing pattern, the daily note's patterns_touched: field is also updated.

---

## 13. Pattern <-> Trades Relationship

- If a decision involves an existing 04_Patterns entry, pattern_setup and/or pattern_links may reference it.
- Referencing a pattern does not change its validation status. An unvalidated (observation/candidate/recurring/under_review) pattern remains exactly that after being referenced by a trade — the reference is evidence that may later support a Section 17 validation review, not validation itself.
- A pattern must never be represented as a Playbook setup merely because a trade referenced it via pattern_setup.

---

## 14. Playbook <-> Trades Relationship

- playbook_setup is used only when an actual 05_Playbook entry already exists for that setup.
- Claude does not create a Playbook entry merely because a setup looks attractive or because a trade using it worked out. A Playbook entry requires the full validation/promotion process defined in Master Script Sections 17-18 and Data Contract v1 Section 5, including explicit user confirmation before the write occurs.
- If a trade uses a setup that has no Playbook entry, playbook_setup is left empty; pattern_setup is used instead if a relevant Pattern entry exists, or neither field is populated if the setup is purely discretionary.

---

## 15. Write Authority (When Claude May Write Automatically)

Claude may create or update a 06_Trades record automatically when:
- the user has clearly communicated a meaningful trading decision (per Section 4's trigger list), or
- the user explicitly asks Claude to record one.

Claude must not manufacture a decision record from market commentary alone — discussing a setup is not the same as deciding on it.

Claude may append factual, non-judgment progression to an existing record without separate confirmation (e.g., noting that a trigger level was hit, that a stop was touched) — these are observable facts, not judgment calls.

Claude must request confirmation before writing any judgment-based classification: decision_quality, process_quality, or an interpretive note in trade_outcome beyond the mechanical win/loss/breakeven fact.

Claude must never silently rewrite historical decision fields (trigger, invalidation, entry_price, stop_price, expected_risk_reward, or any no_trade_* field as originally recorded), per Data Contract v1 Section 2. Changes are recorded as new dated entries under During-Trade Notes, never as edits to the original plan.

---

## 16. State Machine

```
                setup evaluated
                      |
                      v
              [ seriously evaluated? ]
               /                    \
            no                      yes
             |                       |
     (no record created)      record created: record_kind = planned
                                      |
                    -------------------------------------------
                    |                |                |        |
              trigger occurs   conditions      invalidation   user declines
              & user enters    change before   condition      the setup
                    |          trigger         is hit         outright
                    v                |                |        |
        record_kind = executed       v                v        v
                    |         record_kind =    record_kind =  record_kind =
                    v         cancelled        invalidated_   rejected_setup
        [ position managed          ^          setup               ^
          per Section 13 ]          |                |              |
                    |          (trigger never    (predefined     (no-trade
                    v           occurred)          condition met  fields
        record_kind = executed                     before entry)  populated,
        (closed) — exit_price,                                    Section 11
        trade_outcome,                                             hard
        decision_quality,                                          condition
        process_quality set                                        referenced
        after user confirmation                                    or
                                                                     "discretionary")

        Separate branch:
              trigger occurs
                      |
                      v
            user does not enter
                      |
                      v
          record_kind = missed
```

This state machine uses only the six canonical record_kind values already defined in Data Contract v1. No additional values are introduced.

---

## 17. Minimum Capture Checklist

Before a meaningful decision becomes a structured record, capture at minimum:

- instrument
- direction (if applicable — not applicable to a pure no-trade record with no directional lean)
- thesis (brief reference or link to the daily note's thesis)
- setup (what specifically is being evaluated)
- confirmation (what is required, and its current status)
- invalidation (what would prove it wrong)
- risk (defined risk, even qualitatively, before any entry)
- decision (what the user actually decided)
- record_kind (which of the six canonical states applies)

If a field is genuinely unavailable at the time of capture (e.g., risk/reward not yet calculable), the field is left blank or marked unknown rather than filled with an invented value. Missing information is recorded as missing, not guessed.

---

## 18. Examples of Correct vs. Incorrect Capture

**Correct — planned:**
User: "I'm watching SPX for a reclaim of 7,794 with a stop under 7,743, if CPI comes in cool."
-> Claude may create record_kind: planned with trigger, invalidation populated from what the user stated. Not marked executed. No decision_quality/process_quality set yet (nothing has happened).

**Incorrect — do not do this:**
User discusses SPX generally without a specific trigger or invalidation.
-> Claude creates a trade record anyway, inventing a trigger/invalidation to fill the schema.
This violates Section 4 (not a meaningful decision — no setup was actually formed) and Section 17 (never invent missing information).

**Correct — rejected_setup (no-trade):**
User: "VIX is pushing toward 17.27, I'm not taking anything today."
-> Claude creates record_kind: rejected_setup, no_trade_condition_ref: "VIX pushing toward or above 17.27" (the exact Section 11 condition), and asks the user for what_would_change_this / monitoring_while_waiting if not already stated, rather than inventing them.

**Incorrect — do not do this:**
Claude infers the user's reason for not trading and writes a no_trade_reason the user never actually stated.
This violates Section 9 (user decision boundary) and Section 17 (do not invent missing information).

**Correct — executed:**
User: "Filled long at 7,796, stop 7,743."
-> Claude updates the record to record_kind: executed with entry_price populated from what the user explicitly stated.

**Incorrect — do not do this:**
User: "I'm probably going to take that SPX long."
-> Claude marks record_kind: executed.
This violates Section 3 (a stated intention is not the same as an executed trade) and Section 9.

**Correct — post-trade judgment fields:**
Trade closes at a loss. Claude: "The stop was hit exactly at the predefined invalidation level and the plan was followed — this looks like sound decision_quality and process_quality despite the loss. Do you agree, or would you classify it differently?"
-> Written only after user confirms.

**Incorrect — do not do this:**
Trade closes at a loss. Claude automatically writes decision_quality: poor because the trade lost money.
This violates Section 10 and Master Script Section 19 ("A profitable result does not automatically validate a process, and a losing result does not automatically invalidate one").

---

## 19. Safety and Historical-Integrity Rules

Carried forward unmodified from the Master Script (Section 23) and Data Contract v1:

- No execution of real trades or financial transactions through this system.
- Claude never represents a hypothetical trade, analysis, or recommendation as an executed trade.
- No historical decision field is rewritten to reflect information that arrived after the fact — what was known at the time is permanent.
- No statistic or judgment field is manufactured when the underlying decision information is insufficient or ambiguous.
- The final authority for actual trading decisions remains with the user; Claude's role is analysis, recommendation, and accurate structured recording — never decision-making on the user's behalf.
- This protocol itself does not override, alter, or reinterpret Master Script Section 11's hard no-trade conditions, the record_kind enum, or any field defined in Data Contract v1. It only defines the operating discipline for using them correctly.
