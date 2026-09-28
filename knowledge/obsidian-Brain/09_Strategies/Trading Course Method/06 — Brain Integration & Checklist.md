---
type: strategy-integration
title: "Trading Course Method — 06 Brain Integration & Checklist"
status: reference-unvalidated
strategy: "Trading Course Method"
created: 2026-08-13
source: "Trading Course Project Guide — Chapters 1–15 (via 09_Strategies/Trading Course Method notes 01–05)"
tags:
  - strategy
  - trading-course-method
  - integration
---

> [!info] Integration/reference note — NOT a rule, signal, or validated edge
> This note describes *how* the Trading Course Method may be referenced inside the Daily Trading Brain. It is **reference material only**, isolated from the historical research layer, and it changes no governing document, template, or schema. Nothing here promotes anything, and **no edge is claimed for any course rule** until my own trading data validates it (Master Script §16–18; Data Contract v1 §4/§5). A/B/C is preserved: **A — Course Rule**, **B — Instructor Preference**, **C — Requires Validation**. C is never treated as a rule; B is never universalized.

## Purpose

A single place the morning process and trade-evaluation process can point at, operationalizing the approved integration proposal. Derived from [[01 — Direction & Structure]], [[02 — Areas of Interest]], [[03 — Entry & Confirmation]], [[04 — Risk & Targets]], and [[05 — Full Framework]].

## Where the method sits in the Brain

- It is a **technical lens layered *under*** the existing macro / regime / cross-asset process — **subordinate to current evidence** (Master Script §03: current evidence outranks any framework).
- **Morning process:** use the course's top-down read to describe SPX/ES structure (bullish HH/HL vs bearish LL/LH; protected HL/LH via the snake trick) and to pre-mark candidate **AOIs** as Key Levels / Watchlist entries. Marking an AOI is **analysis, not a setup** — no entry exists until price is inside it with a **closed** confirmation. Reference `[[05 — Full Framework]]`; do **not** copy course rules into the daily note as established facts, and make **no edge claim**.
- **Trade evaluation:** walk the pipeline **Direction → AOI → Entry → Confirmation → Stop → TP → R:R**. The method shapes the *plan's content*; it does **not** hold decision authority (Decision Capture Protocol §4/§9 — a record is created only at a meaningful decision, and `executed` only on an explicit fill).

## Pre-entry checklist — A (Course Rules), objective gates

All eight must be answerable **yes** before an entry is considered. (Mirrors the source Pre-trade checklist; all are Course Rules.)

- [ ] **1. Direction** established top-down — bullish HH/HL or bearish LL/LH?
- [ ] **2. Protected HL/LH** marked from a **meaningful turn** (snake trick), not every small swing?
- [ ] **3. Price is *inside* the predefined AOI**, with clear reaction history / **three touches**?
- [ ] **4. Confirmation candle has *closed* inside the AOI** — not a wick, not an unfinished candle, not anticipation?
- [ ] **5. Stop is *beyond the AOI*** (structural invalidation, not an arbitrary distance)?
- [ ] **6. Take-profit is at the *nearest structure checkpoint*** (makes structural sense)?
- [ ] **7. Risk-to-reward is *at least 1:2*** (entry-to-stop vs. entry-to-target)?
- [ ] **8. Entry, stop, target, timeframe, and thesis are *written before* placing the trade**?

If any gate is **no → not a valid course setup** (do not force it).

## Contextual reference — NOT pass/fail gates

- **Judgment guidance (A, but not binary):** wick interpretation; "confirmation, not a pattern name alone"; what qualifies as a "meaningful turn." Use as guidance, not a tick-box.
- **B — Instructor Preference (optional, never mandatory):** the instructor notes a preference for **4H stop placement, adjusted to the AOI's timeframe** ([[04 — Risk & Targets]]). Record it as an optional planning note only — **do not** make it a required gate (do not universalize B).
- **C — Requires Validation / conventions (not rules, no edge claim):** the source **Project Suggestions** — rank multiple AOIs; write an explicit invalidation sentence; use a **"No trade — insufficient room"** label when structure gives < 1:2; capture trade-plan fields; review outcomes as R-multiples. Also the **1:4 illustration and R-multiple arithmetic** are "arithmetic, not expected performance." Treat all of these as conventions/education, tracked in [[_Validation & Open Questions]] — never as gates or as proof of edge.

## Course element → existing trade-record field (no schema change)

The method maps onto the current `06_Trades` schema as-is:

| Course element | Existing field |
|---|---|
| Top-down bias | `direction` |
| Closed confirmation candle inside AOI, in bias direction | `trigger` |
| Candle-close confirmation (+ optional Brain cross-asset/breadth) | `required_confirmation` / `confirmation_status` |
| Stop beyond AOI (structural invalidation) | `invalidation`, `stop_price` |
| Nearest-structure checkpoint | `target_price` |
| ≥ 1:2 (course minimum) | `expected_risk_reward` |
| Stop/target/size set pre-entry | `risk_defined_before_entry` |

`playbook_setup` and `pattern_setup` stay **empty** — no Playbook entry or Pattern exists for this method (Decision Capture §14).

## Recording method adherence on a real trade (prose only, for now)

In the trade record's **Trade Plan / During-Trade Notes**, include a block like:

```
Course Method (reference: [[09_Strategies/Trading Course Method/05 — Full Framework]])
- Direction (HH/HL or LL/LH): ...
- Protected HL/LH (snake trick): ...
- AOI + timeframe / 3-touch: ...
- Closed confirmation candle inside AOI: yes/no
- Stop beyond AOI: ...
- TP nearest structure: ...
- Planned R:R (≥1:2?): ...
- Followed method / deviations: ...
```

- **Record deviations explicitly** — they are the most valuable validation data.
- `process_quality` (`followed_plan | deviated | no_plan_existed`) may capture adherence, but it is a **judgment field requiring explicit confirmation** (Decision Capture §10) — proposed, never auto-set.

## Feeding outcomes to validation (forward-only)

- Each **closed** method trade → a dated entry in the "Forward-only validation log" of [[_Validation & Open Questions]]: instrument, which gates were present/absent, followed/deviated, **R-multiple**, and a link to the source `[[06_Trades/...]]` record.
- **Source of truth stays in `06_Trades`** (Data Contract §7). The validation log **references** trade records; it does not hand-copy numbers as new truth.
- Accumulate **independent instances across conditions** before any conclusion (Master Script §19). **No edge claim until the data supports it.**

## No auto-promotion

- No A course rule auto-becomes a `05_Playbook` entry (Playbook writes are *never* automatic — Data Contract §5).
- No B preference becomes a universal rule.
- No C item becomes a Pattern, Playbook entry, or claimed edge.
- Method efficacy is not a Pattern until independent, cross-condition, live evidence meets §17. Referencing the method changes nothing's status (Decision Capture §13).

## Deferred governing changes (flag only — not made here)

Each requires separate approval; none is implemented by this note:
- **Data Contract §2:** an optional `strategy_ref:` and/or `method_adherence:` field to reference `09_Strategies` and make adherence queryable.
- **Data Contract §7:** method-level analytics depend on that field.
- **Master Script §11:** "No trade — insufficient room" stays a **discretionary/course** consideration; it must **not** be added to the seven hard no-trade conditions.
- **Daily template:** an optional "Course Method setup" subsection.

## Links

- [[_Index — Trading Course Method]]
- [[01 — Direction & Structure]] · [[02 — Areas of Interest]] · [[03 — Entry & Confirmation]] · [[04 — Risk & Targets]] · [[05 — Full Framework]]
- [[_Validation & Open Questions]]
