# R16 — Session calendar and ES/NQ synchronization

**Status:** coordinator synthesis; independent specialist pass pending. Read-only.

## Session contract

Use official CME product trading-hours and holiday schedules as the source of truth; convert to a canonical timezone while retaining exchange-local session date and calendar-version provenance. Model maintenance breaks, special closes, daylight-saving changes, holidays, and contract-specific session rules explicitly. A bar’s clock timestamp alone does not imply it belongs to the same session across products. Contract month and roll are first-class identity; continuous-adjusted price series should not silently mix contracts or apply future roll information.

The earlier read-only BOT 2.0 review flagged an important semantic issue: `session_open` had been derived from the first observed row, which can mislabel session phase if opening bars are missing. This R0 report records that as a preservation-boundary observation, not a request to edit BOT 2.0. It requires later audit against current CME schedules and data coverage. CME’s current pages are mutable and must be versioned/snapshotted for any future experiment [S29,S30].

## Synchronization contract

For joint ES/NQ inputs, the safest baseline is same-as-of, as-received causal alignment. Where exact timestamps are unavailable, use a one-sided backward as-of join with explicit maximum age, source clock precision, receipt time, missingness/staleness flags, and documented tie-breaking. Never nearest-neighbor matching that can choose a later event; never interpolate future values. Exact same-time alignment is conservative but may discard valid asynchronous information; relaxed max-skew matching is a distinct hypothesis requiring an ablation and no lookahead. Historical archives without local receipt timestamps cannot prove live availability latency.

**Recommendation — STANDARD_METHODOLOGY / BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** preserve both exchange event time and local receipt time, define exact vs backward as-of synchronization before model comparison, and keep instrument/session/contract IDs attached to every sample. R0 does not change synchronization code. No strategy inference is made.
