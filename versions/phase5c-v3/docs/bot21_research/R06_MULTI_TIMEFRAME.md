# R6 — Multi-timeframe representation

**Status:** independent specialist first pass completed (R6); coordinator synthesis pending.

1m-only is simple and retains fine timing, but cannot directly distinguish a local setup from broader session context unless the network learns that from a sufficiently long sequence. Candidate context scales (8/15/30/60/120 minutes and session-to-date) are hypotheses, not selected values. Keep separate (a) bar timeframes, (b) sampling/aggregation resolutions, and (c) forecast horizons: changing one does not imply a change to the others.

Temporal hierarchies support the general method of combining scales, and TimeMixer is a modern multiscale candidate; their published evidence is general forecasting, not current ES/NQ intraday net performance [S78,S79]. One 2026 indexed multi-timeframe futures-day-trading abstract and a 2026 iron-ore-futures multiscale study are leads, not validation: instrument, cost, split and replication details are insufficient for transfer [S80,S81].

**Causal contract for future study:** at decision time `t`, each 5m/15m/30m/hourly input must be computed only from bars whose close is no later than `t`; no partially completed aggregate unless its exact as-of fields are available. Session/day aggregates reset per official product calendar. Freeze timezone, holiday, maintenance, early-close, daylight-saving and session identifiers before dataset split. Missing bars must carry explicit missingness/source-quality information rather than synthetic forward-fill unless separately justified.

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** first compare a 1m-only common baseline with an additive, predeclared multi-resolution representation under the same sample/time split and effective context budget. Do not rank 8 vs 120 minutes from familiar trading heuristics. **INSUFFICIENT_EVIDENCE:** optimal context or multi-timeframe gain for ES/NQ one-minute targets.

Source basis: patching and multirate methods [S05,S14,S79]; temporal hierarchy and futures/multiscale leads [S78,S80,S81]. Causal-bar boundary is standard methodology, not an empirical ES/NQ result. **INSUFFICIENT_EVIDENCE:** multi-timeframe edge for ES/NQ.
