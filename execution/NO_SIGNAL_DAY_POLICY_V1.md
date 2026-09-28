# No-signal day policy v1

This policy applies to the provider-neutral ES/NQ paper simulator.

- A session with verified ES/NQ bars and zero validated signals is recorded as `NO_SIGNALS`.
- `NO_SIGNALS` is a valid observation, not a loss, win, or missing-data event.
- A signal that qualifies after UTC midnight is attributed to its immutable signal date and labeled `COVERED_NEXT_ENTRY_SESSION`; entry accounting remains on the actual entry date.
- A session with signals but no completed lifecycle outcome remains `NO_COMPLETED_TRADES` and cannot advance the performance sample.
- Missing bars are `MISSING_FEED` and block qualification until repaired.
- No status in this policy permits orders or changes strategy parameters automatically.

The coverage artifact is the gate: `outputs/provider_neutral_paper_trial/coverage.json`.
