# R1 — Modern neural architectures

**Status:** independent first pass completed by one specialist agent; accessed 2026-09-24. This is literature comparison, not an ES/NQ experiment. No winner selected.

## Evidence summary

| Family | Useful inductive bias | Main costs / failure modes | ES/NQ evidence and transfer |
|---|---|---|---|
| Causal TCN / residual CNN | Ordered, causal local filters; dilation expands receptive field; parallel training and direct multi-horizon heads | Fixed receptive field, aliasing/stride sensitivity; no intrinsic drift or uncertainty solution | TCN beat canonical RNNs on several non-financial sequence tasks in Bai et al.; not futures evidence [S01] |
| LSTM / GRU | Stateful sequential memory, natural streaming; gated compression | Sequential training; memory compression/forgetting; autoregressive error accumulation | Foundational general sequence models; no direct proof of ES/NQ advantage. TCN-vs-RNN evidence is task-specific [S01,S02] |
| CNN–RNN / TCN–RNN hybrids | Local filters followed by recurrent summary | More parameters, interfaces, tuning and leakage opportunities; stacking does not itself prove complementarity | Finance literature contains heterogeneous hybrids but weak apples-to-apples evidence [S24] |
| Transformer encoder / TFT | Global token interactions; TFT combines local recurrent processing, variable selection/gates, attention, known-future/static context and quantiles | Attention/memory costs; positional/casual design; data hunger and complex interpretation | TFT general forecasting evidence, not ES/NQ. LTSF-Linear’s counter-result makes simple baselines mandatory [S03,S04] |
| PatchTST | Patches reduce token count and retain subseries motifs; shared channel-independent encoder | Channel independence may discard cross-market interactions; attention cost in number of patches | General long-horizon benchmark evidence only [S05] |
| iTransformer | Treats variables as tokens, attention across variates; temporal history projected per variable | Requires carefully aligned variables; asynchronous ES/NQ can create spurious relations; cost grows with channels | ICLR benchmark evidence across ETT, traffic, weather, solar etc.; not intraday futures [S06] |
| TimesNet | Period detection and 2-D intra/inter-period convolution | Assumed periodicity may break under shocks; period selection may discard transients | General time-series tasks; no direct market validation [S07] |
| Informer / Autoformer / FEDformer / Crossformer | Sparse attention, decomposition/autocorrelation, frequency selection, or cross-time/cross-dimension hierarchy | Added assumptions (smooth trend/periodicity, sparse relevance, alignment); complexity and implementation differ | Long-horizon non-financial benchmark claims, not trading evidence [S08–S11] |
| TiDE / N-BEATS / N-HiTS | Dense residual MLPs; direct horizons; hierarchical/multi-rate interpolation | Fixed projection size; smoothness/interpolation can suppress abrupt bars; input dimensional growth | Strong general forecast baselines, not financial alpha evidence [S12–S14] |
| S4 / Mamba-like SSM | Structured state and efficient long-sequence processing; Mamba input-selective state | Specialized kernels/runtime, state compression and implementation complexity | Sequence-modeling evidence (language/audio/general TS), no ES/NQ edge [S15,S16] |
| MoE / ensembles / hybrids | Conditional specialization or error diversification | Router collapse/chasing noise, expert underuse, more trials/compute; ensemble spread ≠ calibrated uncertainty | General benchmark results do not justify market deployment; require strict ablations [S17] |

Architecture-derived properties in this table are hypotheses about inductive bias, not comparative measured performance. For short windows, asymptotic attention/SSM advantages may be irrelevant; report wall-clock latency and memory only in an authorized later phase.

## Findings

- **FOUNDATIONAL_EVIDENCE:** Causal convolutions, recurrent networks, attention, state-space models, dense MLP forecasts, and mixture methods each encode different assumptions; a benchmark winner is conditional on dataset, horizon, and input construction.
- **RECENT_EMPIRICAL_EVIDENCE:** Modern 2023–26 benchmark activity is strong, but most public leaderboards are non-financial or long horizon. No retrieved peer-reviewed direct head-to-head test establishes a winner for ES/NQ one-minute intraday prediction.
- **BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** Keep a small causal CNN/TCN and simple non-neural/statistical baseline in any future shortlist; compare one recurrent model, one patch-based attention model, and one state-space model only if R1 is authorized and the protocol freezes dimensions, context budget, data splits, and metrics beforehand.
- **INSUFFICIENT_EVIDENCE:** Hybrid, MoE, learned regime routing, and foundation-model claims have not demonstrated an incremental ES/NQ intraday benefit over simple causal baselines.

## Recommendations / non-recommendations

Do not remain “TCN-only” by assumption; retain TCN as a baseline and investigate recurrent/attention/SSM alternatives prospectively. PatchTST and iTransformer are plausible candidates for distinct patch-vs-variable-token biases. TimesNet is lower priority because explicit periodicity may be unstable. Do not start with TFT/MoE/large hybrids: their component count increases multiplicity and complicates attribution. Do not transfer reported long-horizon accuracy to expected trading returns.

Sources and limitations are indexed in [source registry](BOT21_RESEARCH_SOURCE_REGISTRY.md).
