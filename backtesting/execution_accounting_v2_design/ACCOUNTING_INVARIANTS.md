# Accounting v2 formulas and invariants

All quantities, prices, rates, amounts, and multipliers are finite `Decimal` or declared integer units.

1. Futures `UPNL = signed_qty * (mark - reference_price) * point_value`.
2. Close/reduce `RPNL = closed_qty * (fill - reference) * point_value * prior_side_sign`.
3. Add average = `(abs(old_qty)*old_average + abs(add_qty)*fill) / abs(new_qty)`.
4. Reduction leaves average unchanged. Cross-zero reversal sets residual average to reversal fill.
5. Flat means quantity, average, UPNL, exposure, and reserved margin are exactly zero.
6. Costs are accrued once from immutable fill/cost IDs; duplicate application is fatal.
7. Slippage affects the economic fill price once and is separately reported, never subtracted twice.
8. Variation settlement transfers UPNL to cash once and resets reference; pre/post equity is equal.
9. `equity = cash + unsettled_realized + UPNL - accrued_costs + signed_credits` under the declared model.
10. Initial/maintenance margin equals the exact sum of per-position requirements.
11. Available funds = eligible equity minus reserved initial margin; negative values trigger risk facts.
12. Spot BTC equity = quote cash + base quantity * verified valuation price.
13. Linear-perpetual P&L/funding uses only its frozen contract basis and verified mark/funding facts.
14. Market, contract, strategy, session, fee, funding, and rollover attribution sums exactly to portfolio totals.
15. Every snapshot links its predecessor and all causative fill, settlement, funding, fee, and risk facts.

Any nonzero reconciliation residual rejects snapshot publication.

