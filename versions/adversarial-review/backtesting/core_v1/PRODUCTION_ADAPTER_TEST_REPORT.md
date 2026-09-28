# Production archive adapter test report

- Focused Core v1 and adapter tests: 36 passed (including 14 production-adapter tests).
- Complete backtesting suite: 185 passed.
- Full offline repository suite: 1,126 passed.
- Production validation: complete ES and NQ chains passed; BTC completed partial slice passed.
- ES/NQ archive tree before/after: `405ff5602600fbe361c7136b85be0b26d46567c1c080dfefab2e506e109a775b`.
- Verified ES/NQ normalized rows: 877,679.
- Strategy simulations and performance calculations: none.
- Network calls, credential access, archive writes, recorder control, and scheduled-task control: none.

The tests cover chain/hash conflicts, plan and market identity, missing links, unpromoted artifacts,
duplicate/out-of-order/session-conflicting rows, active-window mismatch, raw lineage, exact Decimal and
nanosecond handling, sparse gaps, market isolation, iterator exhaustion, BTC completion boundaries,
partial eligibility, changed-file rejection, and static read-only/network-free behavior.
