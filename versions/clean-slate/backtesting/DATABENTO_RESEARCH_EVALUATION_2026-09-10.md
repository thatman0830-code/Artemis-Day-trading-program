# Databento Research Evaluation — 2026-09-10 UTC

State: complete five-active-day normalization; insufficient signal sample.

The provider-consistent window now covers September 4, 7, 8, 9, and 10.
September 7 is retained and labeled as a shortened holiday session. Exact
decimal normalization admitted 6,540 source 1-minute candles per market. The
corrected adapter also derived 1,308 complete, aligned 5-minute candles per
market without filling incomplete buckets, for 7,848 total candles and ten
recorded gap facts per lane.

The corrected deterministic evaluation produced 6,276 `CANDIDATE` and 264
`NO_SETUP` outcomes for ES, and 6,436 `CANDIDATE` and 104 `NO_SETUP` outcomes
for NQ. Neither market produced a fully armed opportunity or completed signal
lifecycle. The conservative, moderate, and aggressive comparison therefore
remains `INSUFFICIENT_SAMPLE` with no candidate profile.

This comparison may rank a risk profile only after retained, completed,
identical-signal lifecycles exist. A five-day data window alone cannot justify a
winner.

## Gate diagnostic

The initial condition-level audit found `FIVE_MINUTE_EVENT_REQUIREMENT` because
the adapter exposed only the source 1-minute stream. After deterministic
five-minute construction, ES produced 710 qualified 5-minute displacements and
43 accepted 5-minute structural events; NQ produced 726 and 67 respectively.
The first blocker consequently moved to `DOWNSTREAM_SETUP_QUALIFICATION`, and
setup candidates are now created. No strategy threshold or timeframe rule was
changed. This is an architecture correction, not a trade result.

## Downstream qualification diagnostic

The next condition-level audit isolated `TARGET_LIQUIDITY_SELECTION` as the
first downstream blocker in both lanes. Active ranges and active OTEs were
available for all 6,276 ES candidates and all 6,436 NQ candidates, but the LRL
selector returned zero active continuation targets. ES recorded 6,026 cases
missing only `ACTIVE_CONTINUATION_TARGET_LRL` and 250 also missing directional
OTE/imbalance confluence. NQ recorded 5,341 and 1,095 respectively. Because a
target is a mandatory Phase A prerequisite, entry-zone selection, stop
selection, and final risk/reward qualification were correctly not invoked.

The liquidity engine separates clustered pools from single references, while
the current LRL handoff selects from pools only. Whether single structural or
prior-period references should become target candidates is a strategy-policy
question and was not changed by this diagnostic.
Synthetic signals, forced trades, cross-provider volume mixing, and execution
authority remain prohibited.
