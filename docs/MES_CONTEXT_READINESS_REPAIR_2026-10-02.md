# MES paper runner — context bridge and readiness repair (2026-10-02)

Status: implemented, tested and provider-checked under the existing Databento plan. It has **not** yet run
through an open-market live session; the first such run is the scheduled Monday 2026-10-05 session.
No forward trades exist. Paper only; live orders remain disabled; prop remains manual.

## What was wrong on 2026-10-02 (reproduced on the pre-repair engine)

`outputs/mes_pilot/repair_2026-10-02/old_behavior_reproduction.json`:

* Warmup ended 2026-10-01 21:00Z; the first live bar was 2026-10-02 12:58Z. That left
  **898 scheduled open minutes** (plus 60 maintenance minutes) with no data, including the whole
  Asia and London windows. Nothing backfilled them.
* Partial buckets were passed to structure as if complete: the first H1 after the gap
  (08:00 ET) had 2 of 60 minutes; the 06:00–10:00 ET H4 had 62 of 240.
* The session was classified `NO_VALID_SETUP` (eligible), with a recorded maximum in-window gap of 0.
* Reconstruction (`oct02_c1_displacement_reconstruction.json`, matches the original record exactly):
  the one live setup (C1 LONG, gap 14:10Z) failed displacement on `BODY_BELOW_ATR_MULT`. Its body was
  10.75 against a prior ATR of 13.59 (ratio 0.79); the ATR was inflated by a true range spanning the
  missing overnight. With complete history (diagnostic rerun) the ATR is 9.09 and displacement passes,
  but efficiency is 0.306, below the 0.35 minimum, so the setup is rejected `C1_EFFICIENCY_BELOW_MIN`.
  No trade either way.

## What changed

| File | Change |
|---|---|
| `mes_pilot/history_bridge.py` (new) | Bounded, read-only context. Layers: ES archive proxy (deep warmup), then native MES historical for the last 5 sessions (downloaded only after `metadata.get_cost == 0.0`; raw contract mapped `MES.c.0 → instrument_id → MESZ6`; future bars dropped; identical overlap dropped; conflicts rejected). Archive zero-volume minutes are certified only when the manifest's declared count exactly equals the minutes missing from that file. |
| `mes_pilot/live_feed.py` | The bar schema is subscribed with intraday replay `start` = the last context bar end; quotes stay live-only. Bars before the provider's `replay_completed` (or the first on-time bar) are delivered as context: no quote, no decisions. `end_of_interval` messages bracketing a no-trade minute are forwarded as zero-trade evidence. Identical overlap is dropped and conflicting duplicates are rejected and reported. Reconnect resubscribes from the last delivered bar end. Gap tracking is seeded from the context end. Also fixes an existing bug: `SystemMsg.is_heartbeat` is a method, so every system message had been counted as a heartbeat and discarded. |
| `mes_pilot/coverage.py` (new) | CoverageTracker: scheduled closures, evidence-backed zero-trade minutes, unexpected gaps and a coverage watermark. `evaluate_readiness`: 21 complete bars per TF with no gap in lookback; prior **trading** session (Monday → Friday); current overnight; Asia/London windows; volatility `UNAVAILABLE` blocks when the filter is enabled. |
| `mes_pilot/engine.py` | Coverage on every bar. An unexpected gap resets all structure. Incomplete buckets are excluded **before** structure. New entries abstain with `CONTEXT_INCOMPLETE:<reason>`. Sessions with any not-ready (or replayed-only) window minute are classified `CONTEXT_INCOMPLETE`. Context **and warmup** bars never execute: no quote, simulator bar, time exit, equity mark or persisted risk roll. Fresh live quotes still protect positions. Conflicting duplicate bars are a fault. ES/MES series match on explicit root and expiry. Session summaries gain `readiness`, `coverage`, `status_layers` and `funnel`. |
| `mes_pilot/risk.py` | `roll_session` never rewinds, so a same-day restart keeps its daily loss and entry usage. |
| `mes_pilot/evidence.py` (new) | Append-only correction registry anchored to the immutable SESSION_SUMMARY hash-chain value. Survives later appends; stops matching if the original records are altered. |
| `mes_pilot/report.py` | `CONTEXT_INCOMPLETE` is ineligible. Reports raw and qualified eligibility; evidence progress uses the qualified count; a ledger whose chain fails qualifies nothing. |
| `mes_pilot/structure.py`, `setups.py` | Displacement diagnostics: every subcondition and the first failing reason, with an unchanged boolean (grid-tested). C1 keeps the detail. Funnel counters. |
| `mes_pilot/portfolios.py` | Pass-throughs for context/evidence/events; configurable evidence label; qualification and status layers in the comparison. |
| `scripts/run_mes_paper_pilot.py` | `live-portfolios` builds context via the bridge, then replays from its end. New `bridge-check` diagnostic. |
| Dashboard (Codex workspace) | Qualified vs raw sessions, CONTEXT_INCOMPLETE reason, status layers, the shared signal shown once, displacement detail, diagnostics shown separately. |

Thresholds, risk limits, floors, reserve, the 1/2/3 MES caps and config hashes are unchanged
(`3fc1bea49c29`, `8213444c425b`, `6b467573e97b`).

## Evidence produced (all diagnostic or synthetic, none is forward evidence)

| Output | Shows |
|---|---|
| `outputs/mes_pilot/repair_2026-10-02/provider_preflight/` | Read-only provider captures: Oct 2 missing interval 898/898 minutes available; `replay_completed` and `end_of_interval` message formats; ES vs MES overlap ≤ 2 ticks. |
| `outputs/mes_pilot/diagnostic_bridge_check/*/bridge-check.json` | Integrated adapter: historical 6,900 MES bars at $0.00; replay from 21:00Z ended on the provider `replay_completed`. |
| `outputs/mes_pilot/diagnostic_oct02_complete_context/*/` | Oct 2 rerun with complete context: ready from 13:00Z, 120/120 window minutes ready, one C1 setup, rejected on efficiency. |
| `outputs/mes_pilot/diagnostic_synthetic_lifecycle/*/` | Three books: signal → 1/2/3 MES → fill → crash/restart reconciliation → context replay without a duplicate position → target exit, fees and P&L. Labelled `SYNTHETIC_TEST`. |
| `outputs/mes_pilot/evidence_qualification/corrections.jsonl` | Oct 2 reclassified `CONTEXT_INCOMPLETE` for qualification (3 books). Raw ledgers are unchanged and hashed in `evidence_snapshots/`. |

## Known limits

* `end_of_interval` timestamp semantics were checked only in a closed market; a minute counts as
  zero-trade only when both bracketing messages arrive (the conservative reading).
* The historical `get_cost` warns that estimates for unfinalized recent metadata may be high. A
  non-zero quote skips the historical layer, and the live replay plus archive still cover a normal
  weekday. It never downloads at a cost.
* ES archive bars remain a proxy for deep warmup (volatility history). Native MES covers the last 5 sessions.
