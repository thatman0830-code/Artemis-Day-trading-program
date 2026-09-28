# CONSERVATIVE_OHLC_1M_V1 truth tables

All rows assume a later eligible bar, valid session/data, positive remaining quantity, volume budget,
and adverse tick rounding. `S` is stop, `L` limit, and `slip` is adverse slippage.

## Market and limit

| Side/type | Bar condition | Outcome | Economic basis |
|---|---|---|---|
| Buy market | any eligible bar | fill | open + slip |
| Sell market | any eligible bar | fill | open - slip |
| Buy limit | open <= L or low <= L | fill | L; no improvement |
| Buy limit | low > L | no fill | carry/cancel/expire by TIF |
| Sell limit | open >= L or high >= L | fill | L; no improvement |
| Sell limit | high < L | no fill | carry/cancel/expire by TIF |

Buy limit never exceeds L; sell limit never falls below L. A favorable opening gap still records L.

## Stop-market

| Side | Condition | Trigger/fill |
|---|---|---|
| Buy | open >= S | gap trigger; open + slip |
| Buy | open < S and high >= S | intrabar trigger; S + slip |
| Buy | high < S | no trigger |
| Sell | open <= S | gap trigger; open - slip |
| Sell | open > S and low <= S | intrabar trigger; S - slip |
| Sell | low > S | no trigger |

## Stop-limit

| Side | Trigger bar | Later eligible bar | Outcome |
|---|---|---|---|
| Buy | open/high >= S | open/low <= L | fill at L |
| Buy | open/high >= S | low > L | triggered, unfilled |
| Sell | open/low <= S | open/high >= L | fill at L |
| Sell | open/low <= S | high < L | triggered, unfilled |

The trigger bar never fills the stop-limit, even if it also touches L.

## Collision and gaps

| Facts in one bar | Default outcome |
|---|---|
| Long stop and target both touched | adverse long stop wins |
| Short stop and target both touched | adverse short stop wins |
| Two thresholds without declared adverse ownership | reject ambiguity |
| Gap through stop | next observable open plus adverse slip |
| Gap beyond limit in nonmarketable direction | no limit fill |
| Missing/closure/maintenance bar | no trigger and no fill |
| Signal and threshold on same source bar | ineligible; evaluate later bar only |

