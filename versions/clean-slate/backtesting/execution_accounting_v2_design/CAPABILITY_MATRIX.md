# V2 capability matrix

`Conditional` means all named authoritative inputs and matching policy versions are mandatory.

| Capability | ES | NQ | BTC spot | BTC linear perpetual | BTC unknown/partial |
|---|---|---|---|---|---|
| Market orders | Conditional | Conditional | Conditional | Conditional | No |
| Limit/stop/stop-limit | Conditional OHLC policy | Conditional | Conditional | Conditional | No |
| Partial fills | OHLCV required | OHLCV required | OHLCV required | OHLCV required | No |
| Session flatten | CME calendar required | CME calendar required | UTC/continuous policy required | policy required | No |
| Rollover | exact contracts/windows required | exact contracts/windows required | N/A | N/A | No |
| Futures margin/variation | owner specs required | owner specs required | N/A | N/A | No |
| Spot cash accounting | No | No | owner spec required | No | No |
| Perpetual margin | No | No | No | owner spec/mark required | No |
| Funding | No | No | No | verified series required | No |
| Mark prices | settlement/mark policy | settlement/mark policy | valuation series | mandatory | absent |
| Archive eligibility | verified Pass B | verified Pass B | requires finalized spot archive | requires finalized perp archive | smoke NoOp only |
| Final OOS acceptance | after split/gates | after split/gates | after finalized evidence/gates | after finalized evidence/gates | never |

Preflight rejects any requested cell marked No or any Conditional cell missing a required fact/version.

