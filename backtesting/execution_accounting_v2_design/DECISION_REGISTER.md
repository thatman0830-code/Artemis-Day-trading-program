# Economically Material Decision Register

All selections and every configured alternative change the configuration and result fingerprints.
An alternative is rejected as the default, not prohibited from a separately named future policy.

| ID | Decision | Selected fail-closed default | Alternative rejected as default | Bias / consequence | Configurable | Owner input before implementation |
|---|---|---|---|---|---|---|
| D01 | Same-bar execution | Signal bar cannot fill its order | Same-bar fill | Avoids look-ahead; may understate fills | No for v2 default | Alternative requires a separately versioned policy |
| D02 | Market price | Next eligible open plus adverse friction | Close/mid/favorable open | Conservative | Rates yes | Slippage/friction schedule |
| D03 | Limit improvement | Fill at limit, never favorable OHLC improvement | Assume best observed price | Conservative | Only by new policy | None |
| D04 | Stop gaps | Adverse open when beyond stop; otherwise stop plus friction | Fill at stop through gaps | Conservative | Policy-versioned | None |
| D05 | Stop-limit | Trigger bar cannot fill; later eligible bar required | Fill on trigger bar | Conservative | Policy-versioned | None |
| D06 | Intrabar collision | Adverse executable outcome; reject if adverse ordering cannot resolve | Favorable or invented path | Conservative | Policy-versioned | Whether an alternative collision policy is desired |
| D07 | Tick normalization | Buy prices round up; sell prices round down when adverse | Nearest/favorable rounding | Conservative | No | Tick specifications |
| D08 | Shared volume | Bar budget allocated by deterministic priority then order ID | Unlimited or iteration-order fills | Path dependent but reproducible | Rate yes | Participation limits |
| D09 | Missing/zero volume | No volume-constrained fill | Assume liquidity | Conservative | Policy-versioned | None |
| D10 | Session flatness | Reject/halt if verified flatten cannot be completed | Invent final-bar liquidation | Conservative | Deadlines yes | Per-market flatten deadline |
| D11 | Futures rollover | Close outgoing completely, then open incoming | Synthetic transfer/atomic spread assumption | No accidental spread exposure | No | Rollover participation cap |
| D12 | Futures margin | Owner-supplied versioned initial/maintenance schedules | Fixture/current-value guess | Cannot invent broker economics | Values yes | ES/NQ schedules and effective times |
| D13 | Futures settlement | Variation settlement is explicit; never silently changes trade PnL | Implicit cash reset | Auditability | No | Settlement-source policy |
| D14 | BTC profile | Unknown spot/perpetual semantics reject | Infer profile from symbol | Conservative | Profile selection yes | SPOT or PERPETUAL, multiplier, mark/funding/margin rules |
| D15 | Missing funding/mark | Reject a perpetual run crossing the affected boundary | Assume zero funding/last trade mark | Conservative | No | Canonical funding and mark sources |
| D16 | End of data | Residual position is an error unless explicit liquidation policy exists | Silent liquidation at last close | Avoids fabricated close | Yes, versioned | Owner end-of-data policy |
| D17 | Legacy | No migration or reinterpretation of Core v1 results | Silent conversion | Preserves provenance | No | None |

Every chosen value is included in configuration and result fingerprints. A configurable choice is not
permission for optimization; owner-authored configurations remain immutable for each evaluation.
