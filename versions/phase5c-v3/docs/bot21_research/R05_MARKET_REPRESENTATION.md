# R5 — Market-data representations

**Status:** independent specialist first pass completed (R5); coordinator synthesis pending. No data purchase/download is proposed.

| Representation | Information captured | Limitation / prospective use |
|---|---|---|
| One-minute OHLCV | Causal compact baseline, price range/close and traded activity | Loses intrabar path, spread, queue, order-flow and exact event timing. Keep as minimum common foundation for comparable tests; bar construction must define timezone, bucket edges, breaks, empty periods and roll/session treatment [S67]. |
| Returns / normalized price / range / realized volatility | Scale-robust changes and dispersion | Normalization must be fitted on past-only data; session/contract transitions can cause discontinuities. Volatility periodicity motivates context, not directionality [S68,S69]. |
| VWAP relation, relative volume, session context | Relative state and clock-time activity | All denominators/windows must be causal and session/calendar-aware; time-of-day patterns can drift. |
| Multi-timeframe summaries | Broader context with lower-rate histories | Resampling must use completed bars only; no partial future-containing bar or alignment leakage. |
| Trades / tick events | Event order, aggressor/volume changes subject to feed semantics | Trade-only flow omits unexecuted quotes/cancels; event-time intensity is endogenous. Higher sampling is not automatically better under microstructure noise [S70,S71]. |
| Quotes / top-of-book / MBP | Spread, depth by level, quote changes | Aggregation loses individual order identity; stale/locked/crossed quotes and recovery semantics matter. Queue imbalance has next-midprice-tick evidence on Nasdaq equities, not ES/NQ net PnL [S72]. |
| MBO / full depth / microprice / order flow | Queue-level events, cancellation/insertions, imbalance | Highest data/compute/validation burden; fragile under missing messages and latency; not required to prove bar baseline. LSE/Nasdaq LOB work and NYSE OFI findings motivate ablations only, not an ES/NQ deployment claim [S24,S73,S74]. |
| Cross-market inputs (e.g. ES/NQ together) | Potential conditional context and price-discovery relationships | Must enforce same contract/session and as-of receipt-time joins. Pair/cross-asset studies do not prove stable ES↔NQ leadership; synchronization errors can create apparent predictive power [S75–S77]. |

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** start future research on OHLCV plus causally computed return/range/volatility and explicit time/session metadata; test richer representations as isolated additions only when source provenance, event/receipt timestamps, licensing, sequence recovery and storage are validated. Never treat derived order-flow/volume indicators as authoritative labels or guaranteed alpha. **INSUFFICIENT_EVIDENCE:** whether microstructure inputs improve net ES/NQ decisions.

**Representation decision:** preserve clock-time one-minute OHLCV and causal returns/range/volatility/session context as the common baseline. Event/tick/volume bars, trades, quotes, MBP/MBO and order-flow are distinct candidate data products, not drop-in upgrades. No evidence reviewed justifies replacing clock-time bars or expanding feed scope in R0.

Sources: CME MDP specifications [S32,S33]; Databento bar-semantics documentation [S67]; volatility/sampling and order-flow papers [S68–S74]; cross-market sources [S75–S77]. Nearly all short-horizon directional LOB findings use equities and next-tick/midprice targets; statistical forecast lift is not net ES/NQ tradability.
