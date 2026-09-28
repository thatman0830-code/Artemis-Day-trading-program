# BOT 2.1 R0 source registry

Access date for web sources: **2026-09-24**. “Peer reviewed” is asserted only when the publisher/conference source identifies a proceedings/journal publication. Preprints, vendor engineering releases and official reference material are labeled as such. Relevance means research relevance, not proof of trading profitability.

| ID | Title / authors / year / venue | Type, review status, URL / DOI | Demonstrated finding | Limitations and BOT 2.1 relevance |
|---|---|---|---|---|
| S01 | *An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling* — Shaojie Bai, J. Zico Kolter, Vladlen Koltun (2018) | arXiv preprint; peer-review venue not verified. https://arxiv.org/abs/1803.01271; DOI 10.48550/arXiv.1803.01271 | TCN outperformed canonical recurrent models on several sequence benchmarks and showed longer effective memory in those tasks. | Not financial or ES/NQ evidence. Supports a TCN baseline, not a winner. |
| S02 | *Long Short-Term Memory* — Sepp Hochreiter, Jürgen Schmidhuber (1997), Neural Computation 9(8) | Journal article; DOI https://doi.org/10.1162/neco.1997.9.8.1735 | Introduces gated memory for recurrent neural networks. | Foundational sequence method; no modern TSF/market comparative evidence. |
| S03 | *Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting* — Bryan Lim, Sercan Ö. Arık, Nicolas Loeff, Tomas Pfister (2021), International Journal of Forecasting 37(4) | Journal article, DOI https://doi.org/10.1016/j.ijforecast.2021.03.012 | Combines recurrent local processing, attention, gating/variable selection and multi-horizon forecasting. | Generic real-world forecasting, not ES/NQ; interpretability components do not prove causal explanations. |
| S04 | *Are Transformers Effective for Time Series Forecasting?* — Ailing Zeng, Muxi Chen, Lei Zhang, Qiang Xu (2023), AAAI-23 | Peer-reviewed conference paper, DOI https://doi.org/10.1609/aaai.v37i9.26317 | One-layer linear model beat several sophisticated Transformer forecasters on nine long-horizon benchmark datasets. | Specific LTSF task suite, not universal evidence against attention or financial models. Requires strong simple baselines. |
| S05 | *A Time Series is Worth 64 Words: Long-term Forecasting with Transformers (PatchTST)* — Yuqi Nie, Nam H. Nguyen, Phanwadee Sinthong, Jayant Kalagnanam (2023), ICLR | Peer-reviewed conference. https://openreview.net/forum?id=Jbdc0vTOcol | Patching and channel-independent Transformer design performed well on long-horizon datasets and supported self-supervised pretraining. | General benchmarks; channel independence may discard ES/NQ interaction. |
| S06 | *iTransformer: Inverted Transformers Are Effective for Time Series Forecasting* — Yong Liu et al. (2024), ICLR | Peer-reviewed conference. https://proceedings.iclr.cc/paper_files/paper/2024/file/2ea18fdc667e0ef2ad82b2b4d65147ad-Paper-Conference.pdf | Treats variates as tokens to model cross-variate relationships. | ETT/traffic/weather/energy/server tasks; cross-market timing/alignment can invalidate same-time inputs. |
| S07 | *TimesNet: Temporal 2D-Variation Modeling for General Time Series Analysis* — Haixu Wu et al. (2023), ICLR | Peer-reviewed conference. https://openreview.net/pdf/98c0a5bad8225b6d1baf5c74047c4d04bacfcfa1.pdf | Period mining plus 2-D convolution used for multiple TS tasks. | Periodic inductive bias may not survive intraday regime shifts; no ES/NQ evidence. |
| S08 | *Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting* — Haoyi Zhou et al. (2021), AAAI | Peer-reviewed conference; DOI https://doi.org/10.1609/aaai.v35i12.17325 | Sparse attention/distilling proposed for efficient long-sequence forecasts. | Generic benchmark claims; not evidence that long context helps this task. |
| S09 | *Autoformer: Decomposition Transformers with Auto-Correlation for Long-Term Series Forecasting* — Haixu Wu et al. (2021), NeurIPS | Peer-reviewed proceedings. https://proceedings.neurips.cc/paper/2021/hash/bcc0d400288793e8bdcd7c19a8ac0c2b-Abstract.html | Decomposition/autocorrelation architecture for long horizons. | Seasonal/decomposition assumptions may poorly match event-driven returns. |
| S10 | *FEDformer: Frequency Enhanced Decomposed Transformer for Long-term Series Forecasting* — Tian Zhou et al. (2022), ICML / PMLR 162 | Peer-reviewed proceedings. https://proceedings.mlr.press/v162/zhou22g.html | Frequency/decomposition model with reported efficiency and general benchmark gains. | Frequency filtering can discard transient market shocks; no futures proof. |
| S11 | *Crossformer: Transformer Utilizing Cross-Dimension Dependency for Multivariate Time Series Forecasting* — Yunhao Zhang, Junchi Yan (2023), ICLR | Peer-reviewed conference. https://openreview.net/forum?id=vSVLM2j9eie | Cross-time and cross-dimension hierarchical modeling. | General multivariate benchmarks; alignment and parameter costs require audit. |
| S12 | *Long Horizon Forecasting with TiDE: Time-series Dense Encoder* — Abhimanyu Das et al. (2023), Transactions on Machine Learning Research | Journal publication. https://research.google/pubs/long-horizon-forecasting-with-tide-time-series-dense-encoder/ | Dense encoder-decoder as a simpler long-horizon forecast family; paper reports speed and accuracy benefits on standard datasets. | No direct ES/NQ evidence; dense projection may scale poorly with many inputs. |
| S13 | *N-BEATS: Neural Basis Expansion Analysis for Interpretable Time Series Forecasting* — Boris N. Oreshkin et al. (2020), ICLR | Peer-reviewed conference. https://mlanthology.org/iclr/2020/oreshkin2020iclr-nbeats/ | Residual MLP/basis model for univariate point forecasts; evaluated on M3/M4/tourism. | Univariate competition tasks do not demonstrate high-frequency futures use. |
| S14 | *N-HiTS: Neural Hierarchical Interpolation for Time Series Forecasting* — Cristian Challu et al. (2023), AAAI 37(6) | Peer-reviewed conference; DOI https://doi.org/10.1609/aaai.v37i6.25854 | Multi-rate sampling and hierarchical interpolation; authors report strong accuracy/compute on LTSF data. | Smooth interpolation bias and nonfinancial long-horizon benchmarks limit transfer. |
| S15 | *Efficiently Modeling Long Sequences with Structured State Spaces* — Albert Gu, Karan Goel, Christopher Ré (2022), ICLR (S4) | Peer-reviewed conference. https://arxiv.org/abs/2111.00396 | Structured state-space sequence model showed long-context capability on sequence benchmarks. | Mostly nonfinancial tasks; specialized implementation; no ES/NQ edge. |
| S16 | *Mamba: Linear-Time Sequence Modeling with Selective State Spaces* — Albert Gu, Tri Dao (2024), COLM | Peer-reviewed conference. https://openreview.net/forum?id=tEYskw1VY2 | Selective SSM provides input-dependent state updates and linear-time sequence processing. | Language/audio/general sequence evidence; throughput claims are hardware/task-specific, no futures result. |
| S17 | *Mixture of Linear Experts for Long-Term Time Series Forecasting* — Fei Ni et al. (2024), AISTATS / PMLR 238 | Peer-reviewed conference. https://proceedings.mlr.press/v238/ni24a.html | Mixture-of-linear-experts results on standard LTSF tasks. | Does not prove MoE routing or regime adaptation helps ES/NQ. |
| S18 | *Chronos-2: From Univariate to Universal Forecasting* — Abdul Fatir Ansari et al. (2025), arXiv:2510.15821 | Preprint; peer-review venue not verified. https://arxiv.org/abs/2510.15821. Official overview: https://www.amazon.science/blog/introducing-chronos-2-from-univariate-to-universal-forecasting | Zero-shot univariate, multivariate and covariate-informed forecasting via in-context learning; reported generic-benchmark gains. | Vendor-affiliated evaluation, general benchmarks, no intraday ES/NQ trading/cost evidence. |
| S19 | *Time Series Foundation Models: Benchmarking Challenges and Requirements* — Marcel Meyer, Sascha Kaltenpoth, Kevin Zalipski, Oliver Müller (2025), arXiv:2510.13654 | Preprint; review status not verified. https://arxiv.org/abs/2510.13654 | Documents dataset overlap, split confusion, leakage and global-shock memorization risks in TSFM evaluation. | Methodological analysis; supports contamination audit, not model ranking. |
| S20 | *It’s TIME: Towards the Next Generation of Time Series Forecasting Benchmarks* — Zhongzheng Qiao et al. (2026), arXiv:2602.12147 | Preprint; peer-review status not verified. https://arxiv.org/abs/2602.12147 | Proposes 50 fresh datasets/98 tasks, human-in-loop data quality and pattern-level benchmark views. | Generic TSF tasks; not ES/NQ. Includes disclosed author-employer relation to one evaluated model. |
| S21 | *Pretrained Time-Series Foundation Models for Financial Return Forecasting* — Miquel Noguer i Alonso, Rodolfo Pereira Franklin (2026), arXiv:2606.27100 | Preprint; venue/review not verified. https://arxiv.org/abs/2606.27100 | On five U.S. equities under rolling-origin tests, reports small/sparse gains over random walk; no single TSFM wins universally. | Daily equity context, not intraday futures; not proof of alpha. |
| S22 | *Beyond Accuracy: Are Time Series Foundation Models Well-Calibrated?* — Coen Adler, Yuxin Chang, Samar Abdi, Felix Draxler, Padhraic Smyth (2026), ICLR | Peer-reviewed conference. https://proceedings.iclr.cc/paper_files/paper/2026/hash/9af2b1d6acf561af9c4cf70d52c7a49d-Abstract-Conference.html | Evaluates calibration of five TSFMs/two baselines and reports TSFMs better calibrated in tested tasks. | Not intraday financial calibration or conditional guarantees under drift. |
| S23 | *SEMPO: Lightweight Foundation Models for Time Series Forecasting* — Hui He et al. (2025), NeurIPS 38 | Peer-reviewed main conference. https://proceedings.neurips.cc/paper_files/paper/2025/hash/ecfb69ce6be017deb5a926c2718f6bc1-Abstract-Conference.html | Lightweight FM and prompt expert routing evaluated on 16 generic TS datasets. | Not market validation; architecture/scale claims remain task-specific. |
| S24 | *DeepLOB: Deep Convolutional Neural Networks for Limit Order Books* — Zihao Zhang, Stefan Zohren, Stephen Roberts (2019), IEEE Transactions on Signal Processing 67, 4573–4586 | Peer-reviewed journal; DOI https://doi.org/10.1109/TSP.2019.2907260 | CNN/LSTM model for LOB mid-price movement classification on FI-2010 and LSE sample. | Equities and labels, not ES/NQ net trading; benchmark small/preprocessed. Useful only as richer-input candidate. |
| S25 | *Adaptive Conformal Inference Under Distribution Shift* — Isaac Gibbs, Emmanuel Candès (2021), NeurIPS 34 | Peer-reviewed proceedings. https://papers.neurips.cc/paper_files/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html | Online wrapper seeks long-run coverage under arbitrary distribution changes; tested on two datasets. | Long-run marginal coverage is not conditional/finite-sample ES/NQ guarantee. |
| S26 | *On Calibration of Modern Neural Networks* — Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger (2017), ICML / PMLR 70 | Peer-reviewed proceedings. https://proceedings.mlr.press/v70/guo17a.html | Temperature scaling was effective on evaluated classification benchmarks. | Calibration can drift; source domains differ; calibrator needs separate temporal data. |
| S27 | *Selective Classification for Deep Neural Networks* — Yonatan Geifman, Ran El-Yaniv (2017), NeurIPS | Peer-reviewed proceedings. https://proceedings.neurips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html | Selective predictor trades coverage for risk on image-classification benchmarks. | Not market selective-prediction validation. |
| S28 | *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality* — David H. Bailey, Marcos López de Prado (2014), Journal of Portfolio Management 40(5), 94–107 | Journal paper DOI https://doi.org/10.2139/ssrn.2460551 | Adjusts Sharpe inference for selection bias, non-normality and number of trials. | Does not fix leakage, invalid costs, or protected-test reuse. |
| S29 | CME Group Holiday and Trading Hours | Official exchange reference, current page. https://www.cmegroup.com/trading-hours.html | Product calendars include regular hours and special holiday schedules; CME notes consolidated calendar updates for 2026–27. | Mutable; archive/version it for future experiments. |
| S30 | CME Group Equity Index Roll Dates | Official exchange reference. https://www.cmegroup.com/trading/equity-index/rolldates.html | Lists customary roll/expiry dates; lead month convention changes over roll. | Roll decision is not necessarily actual volume crossover; preserve contract identity. |
| S31 | CME E-mini Nasdaq-100 Futures and Options contract specifications | Official exchange product specs. https://www.cmegroup.com/trading/equity-index/files/emini-nasdaq-100-futures-options.pdf | Specifies NQ contract, tick and hours. | ES/NQ terms are distinct; verify current product-specific files. |
| S32 | CME MDP 3.0 Market by Price — Multiple Depth Book | Official CME Client Systems Wiki, updated 2024-12-26. https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457574047 | MBP aggregates quantity/order counts by price level and incremental add/change/delete updates. | Book reconstruction requires correct sequence/state recovery; MBP loses individual orders. |
| S33 | CME Market by Order FAQ | Official CME Group reference. https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html | MBO provides anonymous order-level/full-depth granularity; MBP summarizes top 10 levels. | Higher bandwidth/processing; details do not guarantee actionable predictability. |
| S34 | *Reassessing Liquidity: Beyond Order Book Depth* — CME Group (2025) | Exchange research/market note, not independent peer review. https://www.cmegroup.com/articles/2025/reassessing-liquidity-beyond-order-book-depth.html | Shows ES cash-open/close activity shape and April 2025 liquidity/price-dispersion changes. | Provider research, period-specific and ES-focused; not forecasting or independent trading alpha. |
| S35 | *Advances in Financial Machine Learning*, Chapter 3 “Labeling” — Marcos López de Prado (2018), Wiley | Book/practitioner methodology. https://www.oreilly.com/library/view/advances-in-financial/9781119482086/c03.xhtml | Describes fixed-horizon/triple-barrier/meta-labeling concepts. | Not proof one label works best; practitioner text, not ES/NQ validation. |
| S36 | *Strictly Proper Scoring Rules, Prediction, and Estimation* — Tilmann Gneiting, Adrian E. Raftery (2007), JASA 102(477), 359–378 | Peer-reviewed journal; DOI https://doi.org/10.1198/016214506000001437 | Defines proper scoring rules for probabilistic forecasts and calibration/sharpness tradeoff. | General statistical foundation, not market-specific. |
| S37 | *Multi-Task Learning Using Uncertainty to Weigh Losses for Scene Geometry and Semantics* — Alex Kendall, Yarin Gal, Roberto Cipolla (2018), CVPR | Peer-reviewed conference. https://openaccess.thecvf.com/content_cvpr_2018/html/Kendall_Multi-Task_Learning_Using_CVPR_2018_paper.html | Proposes task-loss weighting via homoscedastic uncertainty. | Computer-vision setting; not evidence of positive transfer among financial targets. |
| S38 | *DeepLOB benchmark dataset* — Nikolaos Ntakaris et al. (2018), Journal of Forecasting 37, 852–866 | Peer-reviewed journal; DOI https://doi.org/10.1002/for.2543 | FI-2010 benchmark for LOB mid-price prediction. | 5 Nordic equities, short period and preprocessing; weak transfer to ES/NQ. |
| S39 | PyTorch deterministic algorithms documentation | Official software docs. https://docs.pytorch.org/docs/main/generated/torch.use_deterministic_algorithms.html | Deterministic operations can be requested; unsupported nondeterministic ops can raise. | Same results not guaranteed across versions/platforms/hardware; deterministic can slow. |
| S40 | JAX installation documentation | Official docs. https://docs.jax.dev/en/latest/installation.html | Current platform table: Windows GPU no; WSL2 GPU experimental; Linux CUDA supported. | Version-specific; recheck if later authorized. |
| S41 | TensorFlow pip install documentation | Official docs. https://www.tensorflow.org/install/pip | Native Windows GPU support ended after TF 2.10; current GPU path requires WSL2/Linux. | Software status may change; recheck later. |
| S42 | NVIDIA CUDA GPU Compute Capability | Official hardware docs. https://developer.nvidia.com/cuda/gpus | Lists RTX 5060 Ti at compute capability 12.0. | Does not establish specific framework wheel/kernel compatibility. |
| S43 | *A Reality Check for Data Snooping* — Halbert White (2000), Econometrica 68, 1097–1126 | Peer-reviewed journal; DOI https://doi.org/10.1111/1468-0262.00152 | Bootstrap reality-check method addresses reuse of the same history across searched models. | Does not create clean OOS or correct bad data/costs. |
| S44 | *…and the Cross-Section of Expected Returns* — Campbell R. Harvey, Yan Liu, Heqing Zhu (2016), Review of Financial Studies 29(1), 5–68 | Peer-reviewed journal; DOI https://doi.org/10.1093/rfs/hhv059 | Multiple-testing hurdle for asset-pricing discoveries. | Cross-sectional anomalies, not minute futures neural models. |
| S45 | *The Probability of Backtest Overfitting* — David H. Bailey, Jonathan M. Borwein, Marcos López de Prado, Qiji Jim Zhu (2017 issue), Journal of Computational Finance 20(4), 39–69 | Peer-reviewed journal; DOI https://doi.org/10.21314/JCF.2016.322 | CSCV/PBO estimates selection fragility among tested strategies. | Not chronological deployment validation and not a leak cure. |
| S46 | *Testing the Zero-Process of Intraday Financial Returns for Non-Stationary Periodicity* (2025), Journal of Financial Econometrics 23(3), nbaf013 | Peer-reviewed journal; DOI https://doi.org/10.1093/jjfinec/nbaf013 | Reports nonstationary periodicity in liquid FX/equity intraday returns. | Not ES/NQ and does not establish an adaptation method. |
| S47 | *A High-Frequency Trade Execution Model for Supervised Learning* — Matthew F. Dixon (2018), High Frequency 1, 32–52 | Peer-reviewed journal; DOI https://doi.org/10.1002/hf2.10016 | Studies a trade-information matrix/fill-aware model using Level-II E-mini S&P futures. | Model assumptions and historical setting; not proof current simulator or strategy profitability. |
| S48 | *What You See Is Not What You Get: The Costs of Trading Market Anomalies* (2020), Journal of Financial Economics 137(2), 515–549 | Peer-reviewed journal; DOI https://doi.org/10.1016/j.jfineco.2020.02.012 | Demonstrates implementation costs can materially erode anomaly returns. | Equity fund/anomaly setting, not specific ES/NQ; establishes cost realism requirement. |
| S49 | *Empirical Asset Pricing via Machine Learning* — Shihao Gu, Bryan Kelly, Dacheng Xiu (2020), Review of Financial Studies 33(5), 2223–2273 | Peer-reviewed journal; DOI https://doi.org/10.1093/rfs/hhaa009 | Compares ML methods including neural nets for equity-premium prediction; nonlinear interactions matter in that setting. | Cross-sectional/daily equities, not intraday futures; prediction does not identify mechanism. |
| S50 | *Information Leakage in Financial Machine Learning Research* — Zachary David (2019), Algorithmic Finance 8(1–2), 1–4 | Editorial, DOI https://doi.org/10.3233/AF-190900 | Taxonomy/checklist perspective on leakage and survivorship. | Editorial, not empirical; use as checklist only. |
| S51 | *DeepLOB: Deep Convolutional Neural Networks for Limit Order Books* — Zihao Zhang, Stefan Zohren, Stephen Roberts (2019), IEEE TSP | Peer-reviewed, DOI https://doi.org/10.1109/TSP.2019.2907260 | LOB CNN/LSTM classification result. | Other equities/benchmark and movement classification; no net futures strategy proof. |
| S52 | *Chronos-2 Financial Follow-up: Multivariate Financial Forecasting using Chronos Time Series Foundation Models* — Sanjiv R. Das, Tarang Goyal, Mohini Yadav (2026) | arXiv preprint 2605.21504; https://arxiv.org/abs/2605.21504 | Reports that adding related equities/rates can reduce monthly forecast accuracy in tested series. | Preprint, markets/horizons differ; illustrates cross-market features can hurt. |
| S53 | *Financial Fine-Tuning a Large Time Series Model* (2025), IEEE CiFER | Peer-reviewed conference; DOI https://doi.org/10.1109/CIFER64978.2025.10975735 | Reports fine-tuning TimesFM on financial hourly/daily observations improved its tested prediction/mock-trading metrics. | Different instruments/horizons and mock trading; not ES/NQ evidence. |
| S54 | *A Foundation Model for the Language of Financial Markets (Kronos)* — Y. Shi et al. (2026), AAAI-26 | Peer-reviewed conference; DOI https://doi.org/10.1609/aaai.v40i30.39730 | Financial candle-data foundation model; claims broad financial-market pretraining/evaluations. | Pooled benchmarks do not prove target-instrument intraday ES/NQ economics. |
| S55 | *A Foundation Model for Financial Time-Series Forecasting (FinCast)* — Zhuohang Zhu et al. (2025) | arXiv:2508.19609 preprint. https://arxiv.org/abs/2508.19609 | Finance-specific pretrained model proposal and reported generic benchmark evaluation. | Preprint; no independent intraday ES/NQ validation. |
| S56 | *Time-MoE: Billion-Scale Time Series Foundation Models with Mixture of Experts* — Xiaoming Shi et al. (2025), ICLR | Peer-reviewed conference. https://proceedings.iclr.cc/paper_files/paper/2025/hash/558d48c1f08675daa636e09bfe94a89e-Abstract-Conference.html | MoE foundation-model scaling for general forecasting. | Compute/scale and generic benchmark results do not establish target utility. |
| S57 | Google Research: *TimesFM-3: A zero-shot foundation model for multivariate forecasting* — Ayush Jain, Rajat Sen (2026) | Official technical release, not peer-reviewed paper located. https://research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/ | Announces multivariate zero-shot model and pretraining scale. | Vendor claims require independent benchmark and corpus provenance; no ES/NQ validation. |
| S58 | CME E-mini S&P 500 futures contract specifications | Official CME product reference. https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.contractSpecs.html | Specifies ES multiplier, minimum tick and trading schedule. | Verify current contract month/product version; specifications do not imply strategy edge. |
| S59 | CME Equity Index futures product overview / contract details | Official CME product reference. https://www.cmegroup.com/markets/equities.html | Product-family reference for CME equity-index futures. | Use the individual current contract specs as authority for actual terms. |
| S60 | CME E-mini Nasdaq-100 futures contract specifications | Official CME product reference. https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.contractSpecs.html | Specifies NQ multiplier, minimum tick and schedule. | Verify current contract month/product version; specifications do not imply strategy edge. |
| S61 | *Trade Size Clustering in the E-Mini Index Futures Markets* — Q. Wang & J. Zhang (2016), Journal of Financial Research 39, 247–262 | Peer-reviewed journal, DOI https://doi.org/10.1111/jfir.12097 | Studies trade-size clustering in E-mini index futures. | Does not establish an intraday volatility curve or directional trading edge. |
| S62 | *Intraday Periodic Volatility Curves* (2024), Journal of the American Statistical Association | Peer-reviewed journal, DOI https://doi.org/10.1080/01621459.2023.2177546 | Uses ES data from 2005–2020 and studies changing intraday periodic volatility curves. | Historical ES sample; descriptive seasonality, not a trading rule. |
| S63 | U.S. Bureau of Labor Statistics release calendar | Official government schedule. https://www.bls.gov/schedule/ | Provides scheduled release dates/times including major labor releases. | Calendar revisions and release-specific timestamps should be versioned point-in-time; no directional inference from news. |
| S64 | Federal Reserve FOMC calendars | Official Federal Reserve schedule. https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm | Official scheduled FOMC meeting dates and related events. | Calendars can change; archive point-in-time versions if studied. Never infer trade direction from news. |
| S65 | *Trading and Information Diffusion in Futures and ETFs* — Hasbrouck (2003), Journal of Futures Markets | Peer-reviewed journal, DOI https://doi.org/10.1002/fut.10078 | Studies price discovery across futures and ETFs. | Not ES/NQ pair leadership; does not establish stable intraday cross-futures lead. |
| S66 | *Price Discovery in Stock Index Futures Markets: A Cross-Country Analysis* — Dimpfl & Schweikert (2015) | Peer-reviewed journal; cross-market price-discovery study. https://doi.org/10.1016/j.intfin.2015.06.004 | Compares price discovery in national index futures. | Country/index setting does not establish ES-to-NQ or NQ-to-ES lead-lag. |
| S67 | Databento knowledge base: OHLCV schema and aggregation guidance | Vendor technical documentation. https://databento.com/docs/knowledge-base | Describes OHLCV schema construction and nuances around trade breaks, bucket boundaries and intervals without trades. | Provider documentation, not a universal definition; freeze exact derivation/config/source schema in any dataset manifest. |
| S68 | *Intraday Periodicity and Volatility Persistence in Financial Markets* — Torben G. Andersen, Tim Bollerslev (1997), Journal of Empirical Finance 4(2–3) | Peer-reviewed journal, DOI https://doi.org/10.1016/S0927-5398(97)00004-2 | Analyzes intraday periodicity and volatility persistence. | General markets/historical sample; time-of-day volatility is not directional signal and may drift. |
| S69 | *Modeling and Forecasting Realized Volatility* — Andersen, Bollerslev, Diebold & Labys (2001), NBER Working Paper 8160 | Working paper. https://www.nber.org/papers/w8160 | Develops realized-volatility measurement/forecasting from high-frequency returns. | Not a peer-reviewed futures strategy result. |
| S70 | *How Often to Sample a Continuous-Time Process in the Presence of Market Microstructure Noise* — Yacine Aït-Sahalia, Per A. Mykland (2005), Review of Financial Studies 18(2), 351–416 | Peer-reviewed journal. https://www.nber.org/papers/w9611 | Shows sampling frequency under market microstructure noise involves a tradeoff and may have a finite optimum. | Statistical sampling result, not an ES/NQ bar-frequency recommendation. |
| S71 | *Autoregressive Conditional Duration: A New Model for Irregularly Spaced Transaction Data* — Robert F. Engle, Jeffrey R. Russell (1998), Econometrica 66(5), 1127–1162 | Peer-reviewed journal. https://doi.org/10.2307/2999632 | Models durations between irregularly spaced transactions. | Methodological support for event-time modeling, not proof to replace clock bars. |
| S72 | *Queue Imbalance as a One-Tick-Ahead Price Predictor in a Limit Order Book* — Alec N. Gould, Mason A. Bonart (2016), Market Microstructure and Liquidity 2(2) | Peer-reviewed journal. https://doi.org/10.1142/S2382626616500064 | Finds next-tick midprice prediction from queue imbalance in Nasdaq stocks. | Equity/next-tick result; not ES/NQ and not cost-adjusted economic utility. |
| S73 | *Deep Learning for Market by Order Data* — Zihao Zhang, Stefan Zohren, Stephen Roberts (2021), Applied Mathematical Finance 28(1), 79–95 | Peer-reviewed journal. https://doi.org/10.1080/1350486X.2021.1967767 | Studies LOB/MBO prediction on one year/five liquid LSE stocks; reports forecasting comparisons. | Equities and forecast outcomes; does not show MBO improves ES/NQ net trading. |
| S74 | *The Price Impact of Order Book Events* — Rama Cont, Arseniy Kukanov, Sasha Stoikov (2014), Journal of Financial Econometrics 12(1), 47–88 | Peer-reviewed journal. https://doi.org/10.1093/jjfinec/nbt003 | Relates short-interval price changes to best-quote order-flow imbalance and depth in NYSE equities. | Different market/microstructure; requires complete synchronized events; no direct ES/NQ proof. |
| S75 | *Trading and Information Diffusion in Futures and ETFs* — Joel Hasbrouck (2003), Journal of Futures Markets | Peer-reviewed journal. https://doi.org/10.1002/fut.10078 | Studies price discovery across futures and ETFs. | Not ES/NQ pair leadership; does not establish stable intraday cross-futures lead. |
| S76 | *Price Dynamics in the Regular and E-Mini Futures Markets* — Kurov & Lasser (2004), Journal of Financial and Quantitative Analysis 39(2), 365–384 | Peer-reviewed journal. https://doi.org/10.1017/S0022109000003112 | Studies S&P/Nasdaq index-futures price dynamics and price discovery/local order flow. | Historical and market-structure-specific; not proof of current ES↔NQ predictive edge. |
| S77 | *Cross-Asset Tandem Trading and Extraordinary Volatility* — Garrison, Jain & Paddrik (2024), Journal of Futures Markets 44(9), 1508–1542 | Peer-reviewed journal. https://doi.org/10.1002/fut.22532 | Studies synchronized cross-asset order flow and volatility/dislocation behavior. | Cross-asset, not direct ES/NQ leadership; extreme-regime association is not a trading rule. |
| S78 | *Temporal Hierarchies: Forecast Reconciliation with Hierarchical Time Series* — Athanasopoulos et al. (2017), European Journal of Operational Research | Peer-reviewed journal; author publication page: https://robjhyndman.com/publications/temporal-hierarchies/ | Evaluates forecast combinations across temporal aggregation levels in general demand forecasting. | Not markets or ES/NQ; motivates multi-scale comparison only. |
| S79 | *TimeMixer: Decomposable Multiscale Mixing for Time Series Forecasting* (2024), ICLR | Peer-reviewed conference. https://proceedings.iclr.cc/paper_files/paper/2024/hash/a7ac8a21e5a27e7ab31a5f42a0117bdb-Abstract-Conference.html | Mixes fine/coarse-scale information for generic forecasting benchmarks. | Not ES/NQ trading evidence; a later candidate only, not a selected architecture. |
| S80 | *Multi-timeframe Transformer for Futures Day Trading* (2026), KCI record, DOI 10.7840/kics.2026.51.2.363 | Indexed publication record; accessible record’s peer-review/method details require verification. https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003304330 | Abstract reports multi-timeframe futures day-trading results. | Underlying contracts, period, costs, split details and external replication are not established in reviewed record; treat as lead only. |
| S81 | *Multiscale forecasting for iron ore futures* (2026), Scientific Reports | Journal article. https://www.nature.com/articles/s41598-026-63484-1 | Evaluates multiscale forecasting including minute-level futures series. | Iron-ore futures do not establish ES/NQ index-futures transfer or trading utility. |
| S82 | *Modeling and Forecasting Realized Volatility* — Andersen, Bollerslev, Diebold & Labys (2003), Econometrica 71(2), 579–625 | Peer-reviewed journal. https://doi.org/10.1111/1468-0262.00418 | Develops realized-volatility modeling and distributional forecasting using high-frequency returns. | General method; does not select an intraday ES/NQ target or prove strategy performance. |
| S83 | *A Simple Long Memory Model of Realized Volatility* — Fulvio Corsi (2009), Journal of Financial Econometrics 7(2), 174–196 | Peer-reviewed journal; author-hosted PDF: https://statmath.wu.ac.at/~hauser/LVs/FinEtricsQF/References/Corsi2009JFinEtrics_LMmodelRealizedVola.pdf | HAR-RV combines realized volatility across multiple aggregation horizons. | Volatility forecast method; no directional or cost-adjusted ES/NQ strategy evidence. |
| S84 | *Measuring and Forecasting S&P 500 Index-Futures Volatility Using High-Frequency Data* — Martin Martens (2002), Journal of Futures Markets 22(6), 497–518 | Peer-reviewed journal record: https://ideas.repec.org/a/wly/jfutmk/v22y2002i6p497-518.html | Studies intraday and overnight volatility in S&P futures. | Historical ES setting; no NQ transfer or strategy-edge proof. |
| S85 | *Making and Evaluating Point Forecasts* — Tilmann Gneiting (2011), Journal of the American Statistical Association 106(494), 746–762 | Journal article; preprint https://arxiv.org/abs/0912.0902 | Connects point-forecast functionals to consistent scoring/losses. | General forecast methodology, not market-specific. |
| S86 | *Strictly Proper Scoring Rules, Prediction, and Estimation* — Gneiting & Raftery (2007), JASA 102(477), 359–378 | Peer-reviewed journal. https://doi.org/10.1198/016214506000001437 | Establishes proper scoring framework for probabilistic forecasts. | General statistical result; valid scoring does not establish economic utility. |
| S87 | *A Simple Nonparametric Test of Predictive Performance* — Hashem Pesaran & Allan Timmermann (1992), Journal of Business & Economic Statistics 10(4), 461–465 | Peer-reviewed journal. https://doi.org/10.1080/07350015.1992.10509922 | Tests directional predictive performance under specified assumptions. | Does not solve dependence, data-mining, leakage, costs or market transfer by itself. |
| S88 | *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle* — James D. Hamilton (1989), Econometrica 57(2), 357–384 | Peer-reviewed journal; working-paper PDF: https://www.nber.org/system/files/working_papers/w24697/w24697.pdf | Establishes a Markov-switching framework for latent regimes. | Macroeconomic series; filtered versus smoothed state distinction matters; not ES/NQ trading evidence. |
| S89 | *Dynamic Linear Models with Markov-Switching* — Chang-Jin Kim (1994), Journal of Econometrics 60(1–2), 1–22 | Peer-reviewed journal. https://doi.org/10.1016/0304-4076(94)90036-1 | Develops state-space inference with regime switching. | Methodological/econometric evidence; smoothing uses future observations and is invalid as historical real-time feature. |
| S90 | *Estimating and Testing Linear Models with Multiple Structural Changes* — Jushan Bai & Pierre Perron (1998), Econometrica 66(1), 47–78 | Peer-reviewed journal; author PDF: https://www.columbia.edu/~jb3064/papers/1998_Estimating_and_testing_linear_models_with_multiple_structural_changes.pdf | Methods for estimating/testing multiple structural breaks. | Retrospective break estimation is not itself an online signal or an ES/NQ strategy. |
| S91 | *Bayesian Online Changepoint Detection* — Ryan P. Adams & David J. C. MacKay (2007) | Technical research paper/preprint. https://lips.cs.princeton.edu/pdfs/adams2007changepoint.pdf | Maintains posterior over run length as new observations arrive. | Online method depends on model/hazard assumptions; false alarms and delay require task-specific calibration. |
| S92 | *A Survey on Concept Drift Adaptation* — João Gama et al. (2014), ACM Computing Surveys 46(4) | Peer-reviewed survey. https://doi.org/10.1145/2523813 | Reviews drift definitions, detection and adaptation methods. | Broad cross-domain survey; no ES/NQ false-alarm/latency guarantee. |
| S93 | *Hierarchical Mixtures of Experts and the EM Algorithm* — Michael I. Jordan & Robert A. Jacobs (1994), Neural Computation 6(2), 181–214 | Peer-reviewed journal. https://doi.org/10.1162/neco.1994.6.2.181 | Defines probabilistic hierarchical expert routing and learning. | Foundational general ML architecture; no market-specific benefit. |
| S94 | *Out-of-sample tests of forecasting accuracy: an analysis and review* — Allan E. Tashman (2000), International Journal of Forecasting 16(4), 437–450 | Peer-reviewed review. https://doi.org/10.1016/S0169-2070(00)00065-0 | Reviews rolling-origin and out-of-sample forecast evaluation design. | General forecasting methods; does not by itself ensure uncontaminated financial evaluation. |
| S95 | *Aleatoric and Epistemic Uncertainty in Machine Learning: An Introduction to Concepts and Methods* — Eyke Hüllermeier & Willem Waegeman (2021), Machine Learning 110, 457–506 | Peer-reviewed journal. https://doi.org/10.1007/s10994-021-05946-3 | Reviews conceptual distinctions and methods for aleatoric/epistemic uncertainty. | General ML; decomposition is model-dependent and not directly observable in ES/NQ. |
| S96 | *Probabilistic Time Series Forecasting with Deep Learning: Models and Algorithms* — Gruber et al. (2023) | Technical survey/preprint. https://arxiv.org/abs/2305.16703 | Surveys probabilistic deep forecasting methods. | General time-series evidence; not direct financial performance. |
| S97 | *Strictly Proper Scoring Rules, Prediction, and Estimation* — Gneiting & Raftery (2007), JASA 102(477), 359–378 | Peer-reviewed journal. https://doi.org/10.1198/016214506000001437 | Proper scores reward honest probabilistic distributions; supports calibration/sharpness evaluation. | General method, not economic utility. (See also S36.) |
| S98 | *Limits of Distribution-Free Conditional Predictive Inference* — Ryan J. Tibshirani et al. (2019), Information and Inference 10(2), 455–482 | Peer-reviewed journal. https://academic.oup.com/imaiai/article/10/2/455/5896927 | Establishes limits on exact distribution-free conditional coverage without assumptions. | Does not evaluate financial forecasts; marginal coverage is not per-regime guarantee. |
| S99 | *Conformal Prediction Under Covariate Shift* — Ryan J. Tibshirani et al. (2019) | Research paper/preprint. https://arxiv.org/abs/1904.06019 | Weighted conformal methods address covariate shift with suitable density-ratio assumptions. | Does not generally solve concept shift or misspecified weights. |
| S100 | *Conformal Inference for Online Prediction* — Isaac Gibbs & Emmanuel Candès (2024), Journal of Machine Learning Research 25 | Peer-reviewed journal. https://www.jmlr.org/papers/volume25/22-1218/22-1218.pdf | Develops online conformal procedures and coverage/regret analyses under stated assumptions. | Not ES/NQ-specific; guarantees differ from conditional or immediate post-shift coverage. |
| S101 | *Online Calibration under Covariate Shift, Concept Shift, and Temporal Dependence* — Huang, Ma & Michailidis (2026), UAI/PMLR 337 | Peer-reviewed conference proceedings. https://proceedings.mlr.press/v337/huang26b.html | Studies online certificate-driven calibration under temporal dependence and forms of shift. | General time-series method; no ES/NQ-specific validation. |
| S102 | *Evaluating time series forecasting models: An empirical study on performance estimation methods* — Cerqueira, Torgo & Mozetič (2022), Data Mining and Knowledge Discovery | Peer-reviewed journal. https://link.springer.com/article/10.1007/s10618-022-00894-5 | Reviews/compares forecasting performance estimation methods and recommends rolling-origin in suitable settings. | Cross-domain empirical method study; CV validity depends on data/error assumptions. |
| S103 | *A Note on the Validity of Cross-Validation for Evaluating Autoregressive Time Series Prediction* — Bergmeir, Hyndman & Koo (2018), Computational Statistics & Data Analysis | Peer-reviewed journal. https://doi.org/10.1016/j.csda.2017.11.003 | Establishes conditions under which CV can be valid for autoregressive forecasting with uncorrelated errors. | Conditions are specific; does not justify ordinary random CV for dependent nonstationary futures data. |
| S104 | *Rolling Window Selection for Out-of-Sample Forecasting with Time-Varying Parameters* — Atsushi Inoue, Yang Li & Barbara Rossi (2017), Journal of Econometrics | Peer-reviewed journal. https://doi.org/10.1016/j.jeconom.2016.12.001 | Studies rolling-window choice under potentially time-varying parameters. | Window choice is itself model selection; no universally optimal ES/NQ window. |
| S105 | *Comparing Predictive Accuracy* — Francis X. Diebold & Robert S. Mariano (1995), Journal of Business & Economic Statistics 13(3), 253–263 | Peer-reviewed journal. https://doi.org/10.1080/07350015.1995.10524599 | Provides predictive accuracy comparison for general loss with serially correlated forecast errors. | Small-sample/HAC assumptions matter; not a leakage correction or profitability guarantee. |
| S106 | *A Simple, Positive Semi-definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix* — Whitney K. Newey & Kenneth D. West (1987), Econometrica 55(3), 703–708 | Peer-reviewed journal. https://doi.org/10.2307/1913610 | Develops HAC covariance estimator. | Reliability depends on bandwidth/dependence assumptions and enough observations. |
| S107 | *The Stationary Bootstrap* — Dimitris N. Politis & Joseph P. Romano (1994), Journal of the American Statistical Association 89(428), 1303–1313 | Peer-reviewed journal. https://doi.org/10.1080/01621459.1994.10476870 | Resamples dependent observations using random block lengths. | Stationarity/weak dependence assumptions limit use under arbitrary structural breaks. |
| S108 | *A Test for Superior Predictive Ability* — Peter R. Hansen (2005), Journal of Business & Economic Statistics 23(4), 365–380 | Peer-reviewed journal. https://doi.org/10.1198/073500105000000063 | Tests superior predictive ability across a supplied set of forecast models. | Adjusts only the enumerated comparison universe and relies on inference assumptions. |
| S109 | Databento common fields, enums and types: timestamp semantics | Official vendor technical documentation. https://databento.com/docs/standards-and-conventions/common-fields-enums-types | Defines feed timestamp fields and conventions such as event/publisher/receive timestamps. | Provider/venue-specific; confirm exact dataset/schema clocks; not evidence of trading edge. |
| S110 | BLS CPI seasonal-adjustment revisions policy | Official U.S. government documentation. https://www.bls.gov/cpi/seasonal-adjustment/ | Describes historical CPI seasonal factor/index revision practices. | Illustrates point-in-time revision risk for macro data; not proof futures trades are revised similarly. |
| S111 | TradingView Pine Script v5 documentation: repainting | Official platform documentation. https://www.tradingview.com/pine-script-docs/v5/concepts/repainting/ | Explains historical/realtime differences, including higher-timeframe values and repainting behavior in Pine scripts. | Platform-specific documentation; exact bar-builder behavior must be independently specified. |
| S112 | *Higher Order Elicitability and Osband’s Principle* — Tobias Fissler & Johanna F. Ziegel (2016), Annals of Statistics 44(4), 1680–1707 | Peer-reviewed journal. https://doi.org/10.1214/16-AOS1439 | Establishes joint elicitability/scoring for pairs including Value-at-Risk and Expected Shortfall under stated conditions. | General forecast theory; not an ES/NQ trading strategy. |
| S113 | *Volatility Forecast Comparison Using Imperfect Volatility Proxies* — Andrew J. Patton (2011), Journal of Econometrics | Peer-reviewed journal; author paper: https://public.econ.duke.edu/~ap172/Patton_vol_proxies_JoE_2011.pdf | Derives conditions where QLIKE/MSE rankings are robust to noisy volatility proxies. | Assumptions on proxy unbiasedness and forecast target matter; microstructure noise or misspecified proxy can invalidate conclusions. |
| S114 | *TS2Vec: Towards Universal Representation of Time Series* — Jiezhong Yue et al. (2022), AAAI 36(8) | Peer-reviewed conference. https://ojs.aaai.org/index.php/AAAI/article/view/20881 | Self-supervised contrastive representation evaluated on general time-series benchmarks/downstream tasks. | Generic datasets; augmentation invariance does not establish useful ES/NQ forecasts. |
| S115 | *Decoupled Weight Decay Regularization* — Ilya Loshchilov & Frank Hutter (2019), ICLR | Peer-reviewed conference. https://arxiv.org/abs/1711.05101 | Shows Adam weight decay differs from L2 penalty and studies AdamW. | Reported benchmarks are not financial forecast or trading evidence. |
| S116 | *Learning to Trade via Direct Reinforcement* — John Moody & Matthew Saffell (2001), IEEE Transactions on Neural Networks 12(4) | Peer-reviewed journal. https://doi.org/10.1109/72.935097 | Studies direct reinforcement with trading-state and transaction-cost considerations. | Historical experimental setup; does not establish general profitability or authorize end-to-end policy learning. |
| S117 | *Time Series Prediction and Online Learning* — Vitaly Kuznetsov & Mehryar Mohri (2016), COLT / PMLR 49 | Peer-reviewed conference. https://proceedings.mlr.press/v49/kuznetsov16.html | Online prediction guarantees under specified nonstationary/mixing assumptions. | Theoretical assumptions do not guarantee neural ES/NQ deployment performance. |
| S118 | *Predictable Variation and Profitable Trading of U.S. Equities* — Kryzanowski et al. (1999), Journal of Banking & Finance | Peer-reviewed journal. https://doi.org/10.1016/S0378-4266(99)00037-4 | Distinguishes prediction claims from a tested trading framework in equities. | Historical equities context, not intraday ES/NQ; no direct transfer. |
| S119 | *Deep Learning for Financial Time Series: A Large-Scale Benchmark of Risk-Adjusted Performance* (2026), arXiv:2603.01820 | Preprint; https://arxiv.org/abs/2603.01820 | Benchmarks architectures on a daily multi-asset futures dataset from 2010–2025. | Preprint; daily horizon and broad futures set do not establish 1-minute ES/NQ performance; inspect exact protocol and costs before later use. |
| S120 | *A GCN-LSTM Approach for ES-mini and VX Futures Forecasting* — Nikolas Michael, Mihai Cucuringu & Sam Howison (2024), arXiv:2408.05659 | Preprint; https://arxiv.org/abs/2408.05659 | Studies graph/LSTM forecasting across ES and VIX futures expiries. | Different instruments/term structure and preprint status; not ES/NQ pairwise intraday evidence or proof of net value. |

Registry is intentionally not exhaustive of all cited papers; sources are prioritized for primary methods, domain boundaries, safety/validation and current frontier. Any citation found not fully bibliographically verified is labeled with its known status rather than completed from memory.


## R0-B recovery batch 1 independent-source append — 2026-09-24

Provenance: verbatim source appendices from frozen independent R13, R14, R15 reports. Counts are per-report records (15, 14, 23), not 52 globally unique new works. Existing source records are preserved; repeated works retain specialist-local IDs. R16 was blocked by platform usage capacity and contributes no new records.

### Introduced by R13_NONSTATIONARITY.md

## Sources

All records introduced by fresh specialist R13; accessed 2026-09-24. Count: 15 unique works/pages. Repeated appearances of the same work are not extra sources. Limitations and relevance below are R13 assessments. Search snippets and source landing pages/abstracts support scope-level claims; selected accessible primary PDFs supplied further method context. This is not a claim to have audited every proof or reproduced any result.

### R13-S01
- Title: A Survey on Concept Drift Adaptation.
- Authors: Joao Gama, Indre Zliobaite, Albert Bifet, Mykola Pechenizkiy, Abdelhamid Bouchachia.
- Year/venue: 2014, ACM Computing Surveys 46(4), Article 44.
- URL/DOI: https://doi.org/10.1145/2523813
- Evidence type: Peer-reviewed methodological survey; publisher record and author university manuscript consulted.
- Limitations: Broad stream-learning literature; predates modern TTA and is not an ES/NQ trading study.
- BOT 2.1 relevance: Drift definitions, memory/recency tradeoffs, and evaluation framing.

### R13-S02
- Title: Learning from Time-Changing Data with Adaptive Windowing.
- Authors: Albert Bifet, Ricard Gavalda.
- Year/venue: 2007, SIAM International Conference on Data Mining, 443–448; accessible author manuscript dated 2006.
- URL/DOI: https://doi.org/10.1137/1.9781611972771.42 ; https://www.cs.upc.edu/~Gavalda/papers/adwin06.pdf
- Evidence type: Peer-reviewed algorithm and theory with empirical demonstrations.
- Limitations: Assumption-dependent guarantees; market dependence and unbounded losses need separate treatment.
- BOT 2.1 relevance: Adaptive windows and distinguishing detection from revision.

### R13-S03
- Title: On Calibration of Modern Neural Networks.
- Authors: Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger.
- Year/venue: 2017, ICML, PMLR 70:1321–1330.
- URL: https://proceedings.mlr.press/v70/guo17a.html
- Evidence type: Peer-reviewed empirical calibration study.
- Limitations: Image/document tasks; no guarantee of calibration under future market shifts.
- BOT 2.1 relevance: Separates post-hoc probability calibration from representation fitting.

### R13-S04
- Title: Reversible Instance Normalization for Accurate Time-Series Forecasting against Distribution Shift.
- Authors: Taesung Kim, Jinhee Kim, Yunwon Tae, Cheonbok Park, Jang-Ho Choi, Jaegul Choo.
- Year/venue: 2022, ICLR.
- URL: https://openreview.net/pdf?id=cGDAkQo1C0p
- Evidence type: Peer-reviewed time-series normalization method and benchmarks.
- Limitations: Benchmark forecasting is not trading utility; potentially informative scale can be removed.
- BOT 2.1 relevance: Causal input-window normalization as a distinct adaptation mechanism.

### R13-S05
- Title: Tent: Fully Test-Time Adaptation by Entropy Minimization.
- Authors: Dequan Wang, Evan Shelhamer, Shaoteng Liu, Bruno Olshausen, Trevor Darrell.
- Year/venue: 2021, ICLR.
- URL: https://openreview.net/pdf?id=uXl3bZLkr3c
- Evidence type: Peer-reviewed unsupervised test-time adaptation research.
- Limitations: Primarily vision corruption/domain settings; confidence need not identify correct market direction.
- BOT 2.1 relevance: Defines an experimental adaptation mechanism and its transfer risk.

### R13-S06
- Title: Continual Test-Time Domain Adaptation.
- Authors: Qin Wang, Olga Fink, Luc Van Gool, Dengxin Dai.
- Year/venue: 2022, IEEE/CVF CVPR, 7201–7211.
- URL: https://openaccess.thecvf.com/content/CVPR2022/html/Wang_Continual_Test-Time_Domain_Adaptation_CVPR_2022_paper.html
- Evidence type: Peer-reviewed CoTTA method and vision experiments.
- Limitations: Pseudo-label assumptions and visual shifts do not establish financial applicability.
- BOT 2.1 relevance: Error accumulation and forgetting during continual adaptation.

### R13-S07
- Title: Overcoming catastrophic forgetting in neural networks.
- Authors: James Kirkpatrick, Razvan Pascanu, Neil Rabinowitz, Joel Veness, Guillaume Desjardins, Andrei A. Rusu, Kieran Milan, John Quan, Tiago Ramalho, Agnieszka Grabska-Barwinska, Demis Hassabis, Claudia Clopath, Dharshan Kumaran, Raia Hadsell.
- Year/venue: 2016 arXiv manuscript; published PNAS 2017.
- URL: https://arxiv.org/abs/1612.00796
- Evidence type: Primary EWC study, archival manuscript of peer-reviewed research.
- Limitations: Sequential benchmark tasks differ from unlabeled market regimes; retention can conflict with forgetting obsolete signals.
- BOT 2.1 relevance: Establishes the plasticity/retention problem.

### R13-S08
- Title: Layerwise Proximal Replay: A Proximal Point Method for Online Continual Learning.
- Authors: Jinsoo Yoo, Yunpeng Liu, Frank Wood, Geoff Pleiss.
- Year/venue: 2024, ICML, PMLR 235:57199–57216.
- URL: https://proceedings.mlr.press/v235/yoo24a.html
- Evidence type: Peer-reviewed online continual-learning study.
- Limitations: Benchmark results; replay improvement does not prove financial robustness.
- BOT 2.1 relevance: Replay does not by itself eliminate optimization instability.

### R13-S09
- Title: Adaptive Conformal Inference Under Distribution Shift.
- Authors: Isaac Gibbs, Emmanuel Candes.
- Year/venue: 2021, NeurIPS 34.
- URL: https://papers.neurips.cc/paper_files/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html
- Evidence type: Peer-reviewed theory and real-data demonstrations.
- Limitations: Long-run coverage does not guarantee local conditional coverage, useful width, or profit.
- BOT 2.1 relevance: Adaptive uncertainty calibration with explicit interpretation limits.

### R13-S10
- Title: Conformal Inference for Online Prediction with Arbitrary Distribution Shifts.
- Authors: Isaac Gibbs, Emmanuel J. Candes.
- Year/venue: 2024, Journal of Machine Learning Research 25.
- URL: https://www.jmlr.org/papers/v25/22-1218.html
- Evidence type: Peer-reviewed online conformal theory and methodology.
- Limitations: Forecast usefulness and application-specific feedback delays require separate assessment.
- BOT 2.1 relevance: Extends adaptation of conformal tuning; does not remove causal-label constraints.

### R13-S11
- Title: Proactive Model Adaptation Against Concept Drift for Online Time Series Forecasting.
- Authors: Lifan Zhao, Yanyan Shen.
- Year/venue: KDD 2025; arXiv first posted 2024, version 5 revised 2025-12-18.
- URL/DOI: https://arxiv.org/abs/2412.08435 ; https://doi.org/10.1145/3690624.3709210
- Evidence type: Primary forecasting research, accepted venue stated in author manuscript record.
- Limitations: Five forecasting datasets and synthetic drift training do not validate ES/NQ utility or universal proactive adaptation.
- BOT 2.1 relevance: Explicit delayed-ground-truth gap; motivates maturity-aware research.

### R13-S12
- Title: Recovery Guarantees for Continual Learning of Dependent Tasks: Memory, Data-Dependent Regularization, and Data-Dependent Weights.
- Authors: Liangzu Peng, Uday Kiran Reddy Tadipatri, Ziqing Xu, Eric Eaton, Rene Vidal.
- Year/venue: 2026, AISTATS, PMLR 300:3592–3600.
- URL: https://proceedings.mlr.press/v300/peng26a.html
- Evidence type: Peer-reviewed theoretical study.
- Limitations: Nonlinear task-transformation assumptions are not demonstrated for market sequences.
- BOT 2.1 relevance: Current 2026 evidence that continual-learning guarantees remain explicitly assumption-dependent.

### R13-S13
- Title: Tackling Time-Series Forecasting Generalization via Mitigating Concept Drift.
- Authors: Zhiyuan Zhao, Haoxin Liu, B. Aditya Prakash.
- Year/venue: 2025 arXiv preprint, version 2 revised 2026-03-25; no peer-reviewed venue established from inspected record.
- URL: https://arxiv.org/abs/2510.14814
- Evidence type: Primary preprint, ShifTS forecasting framework.
- Limitations: Preliminary evidence; no ES/NQ production conclusion and no independently verified causal deployment protocol here.
- BOT 2.1 relevance: Current research distinguishes temporal shift from concept drift; merits cautious scrutiny.

### R13-S14
- Title: Ranked Entropy Minimization for Continual Test-Time Adaptation.
- Authors: Jisu Han, Jaemin Na, Wonjun Hwang.
- Year/venue: 2025, ICML; OpenReview publication record dated 2025-05-01.
- URL: https://openreview.net/forum?id=lHaGLJ65J9
- Evidence type: Primary peer-reviewed conference record/abstract retrieved through search; subsequent direct page access encountered browser verification.
- Limitations: Vision evidence, not financial forecasts; limited retrieved content used only for the stated collapse concern.
- BOT 2.1 relevance: Documents a concrete failure mode of continual entropy minimization.

### R13-S15
- Title: TimeSeriesSplit.
- Authors/organization: scikit-learn developers.
- Year/venue: Living official documentation, stable page accessed in 2026.
- URL: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Evidence type: Official framework API documentation.
- Limitations: Split utility is not a financial leakage proof; row-count gap and regular spacing assumptions require interpretation.
- BOT 2.1 relevance: Chronological expanding splits and explicit gap semantics; highlights need for availability-aware evaluation.

### Introduced by R14_ENSEMBLES.md

## Sources

All records introduced independently by R14; accessed 2026-09-24. Distinct work count: 14. A proceedings version and its arXiv version count once. Bibliographic URLs below are primary proceedings, author/university or author-submitted research records.

### R14-S01
- Title: Forecast combinations: an over 50-year review.
- Authors: Xiaoqian Wang, Rob J. Hyndman, Feng Li, Yanfei Kang.
- Year / venue: 2023, International Journal of Forecasting 39(4), 1518–1547; preprint 2022.
- URL / DOI: https://fpp.robjhyndman.com/publications/combinations/ ; https://doi.org/10.1016/j.ijforecast.2022.11.005
- Evidence type: Peer-reviewed methodological review; author-hosted metadata/summary verified.
- Limitations: Broad synthesis, not direct ES/NQ evidence or a universal guarantee for equal weighting.
- BOT 2.1 relevance: Combination uncertainty, correlation, simple versus estimated weights and probabilistic combinations.

### R14-S02
- Title: Stacked Regressions.
- Author: Leo Breiman.
- Year / venue: 1992, UC Berkeley Statistics Technical Report 367; institutional page references later Machine Learning publication with uncertainty, so this record cites the verified report.
- URL: https://statistics.berkeley.edu/tech-reports/367
- Evidence type: Primary university research report.
- Limitations: General regression methodology; temporal market dependence requires additional safeguards.
- BOT 2.1 relevance: Cross-validated predictions and constrained fitting of combination weights; foundational stacking evidence.

### R14-S03
- Title: Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles.
- Authors: Balaji Lakshminarayanan, Alexander Pritzel, Charles Blundell.
- Year / venue: 2017, NeurIPS 30.
- URL: https://papers.nips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html
- Evidence type: Peer-reviewed classification/regression benchmark research.
- Limitations: No ES/NQ trading evidence; disagreement is not complete uncertainty and compute increases with members.
- BOT 2.1 relevance: Independent neural fits and probabilistic ensemble uncertainty.

### R14-S04
- Title: Can you trust your model's uncertainty? Evaluating predictive uncertainty under dataset shift.
- Authors: Yaniv Ovadia, Emily Fertig, Jie Ren, Zachary Nado, D. Sculley, Sebastian Nowozin, Joshua Dillon, Balaji Lakshminarayanan, Jasper Snoek.
- Year / venue: 2019, NeurIPS 32.
- URL: https://proceedings.neurips.cc/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html
- Evidence type: Peer-reviewed empirical uncertainty benchmark.
- Limitations: Studied shifts and classification tasks do not reproduce financial nonstationarity.
- BOT 2.1 relevance: Calibration can degrade under shift even when validation calibration was good.

### R14-S05
- Title: On Calibration of Modern Neural Networks.
- Authors: Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger.
- Year / venue: 2017, ICML, PMLR 70:1321–1330.
- URL: https://proceedings.mlr.press/v70/guo17a.html
- Evidence type: Peer-reviewed classification calibration research.
- Limitations: Image/document classification; temperature scaling does not ensure market-shift calibration.
- BOT 2.1 relevance: Evaluate confidence separately from discrimination and fit calibration causally.

### R14-S06
- Title: Principles and algorithms for forecasting groups of time series: Locality and globality.
- Authors: Pablo Montero-Manso, Rob J. Hyndman.
- Year / venue: 2021, International Journal of Forecasting; university working paper 2020.
- URL / DOI: https://doi.org/10.1016/j.ijforecast.2021.03.004 ; https://www.monash.edu/business/ebs/research/publications/ebs/wp45-2020.pdf
- Evidence type: Peer-reviewed theory/methodology and forecasting research, institutional paper record.
- Limitations: General groups of time series; two futures and short-horizon conditional returns are a narrower problem.
- BOT 2.1 relevance: Pooling versus separate models is an empirical question; shared learning can be valid without identical series.

### R14-S07
- Title: A Time Series is Worth 64 Words: Long-term Forecasting with Transformers.
- Authors: Yuqi Nie, Nam H. Nguyen, Phanwadee Sinthong, Jayant Kalagnanam.
- Year / venue: 2022 arXiv preprint (PatchTST); later ICLR 2023 paper, abstract record used here.
- URL: https://arxiv.org/abs/2211.14730
- Evidence type: Primary forecasting architecture research.
- Limitations: Long-horizon benchmark results; channel independence does not establish separate ES/NQ-model superiority.
- BOT 2.1 relevance: Shared-weight channel-independent representation and patching as alternatives to joint encoding.

### R14-S08
- Title: iTransformer: Inverted Transformers Are Effective for Time Series Forecasting.
- Authors: Yong Liu, Tengge Hu, Haoran Zhang, Haixu Wu, Shiyu Wang, Lintao Ma, Mingsheng Long.
- Year / venue: 2024, ICLR; preprint 2023.
- URL: https://arxiv.org/abs/2310.06625 ; https://proceedings.iclr.cc/paper_files/paper/2024/file/2ea18fdc667e0ef2ad82b2b4d65147ad-Paper-Conference.pdf
- Evidence type: Peer-reviewed multivariate forecasting architecture research.
- Limitations: Benchmark correlations need not persist in financial conditional predictions; attention is not causality.
- BOT 2.1 relevance: Explicit interaction between per-variate representations supplies a competing fusion hypothesis.

### R14-S09
- Title: TimeXer: Empowering Transformers for Time Series Forecasting with Exogenous Variables.
- Authors: Yuxuan Wang, Haixu Wu, Jiaxiang Dong, Guo Qin, Haoran Zhang, Yong Liu, Yunzhong Qiu, Jianmin Wang, Mingsheng Long.
- Year / venue: 2024, author-submitted arXiv research record (2402.19072); venue not needed for claims here.
- URL: https://arxiv.org/abs/2402.19072
- Evidence type: Primary architectural and benchmark research.
- Limitations: Exogenous-variable framing does not prove economic exogeneity, causal availability or trading usefulness.
- BOT 2.1 relevance: Cross-attention to combine endogenous and external representations.

### R14-S10
- Title: TimeMixer: Decomposable Multiscale Mixing for Time Series Forecasting.
- Authors: Shiyu Wang, Haixu Wu, Xiaoming Shi, Tengge Hu, Huakun Luo, Lintao Ma, James Y. Zhang, Jun Zhou.
- Year / venue: 2024, ICLR.
- URL: https://arxiv.org/abs/2405.14616
- Evidence type: Peer-reviewed architecture and forecasting benchmarks; paper identifies ICLR 2024.
- Limitations: Generic multiscale forecasting, not proof that redundant market bars add independent information.
- BOT 2.1 relevance: Fine/coarse mixing and multiple predictors; motivation for careful timeframe ablation.

### R14-S11
- Title: Switch Transformers: Scaling to Trillion Parameter Models with Simple and Efficient Sparsity.
- Authors: William Fedus, Barret Zoph, Noam Shazeer.
- Year / venue: 2022, Journal of Machine Learning Research 23(120):1–39.
- URL: https://jmlr.org/papers/volume23/21-0998/21-0998.pdf
- Evidence type: Peer-reviewed sparse MoE systems/ML research.
- Limitations: Large language-model setting and hardware; active compute differs from total memory and actual small-batch latency.
- BOT 2.1 relevance: Conditional activation, training instability, routing and systems tradeoffs.

### R14-S12
- Title: Time-MoE: Billion-Scale Time Series Foundation Models with Mixture of Experts.
- Authors: Xiaoming Shi, Shiyu Wang, Yuqi Nie, Dianqi Li, Zhou Ye, Qingsong Wen, Ming Jin.
- Year / venue: 2025, ICLR; preprint 2024.
- URL: https://arxiv.org/abs/2409.16040 ; https://proceedings.iclr.cc/paper_files/paper/2025/file/558d48c1f08675daa636e09bfe94a89e-Paper-Conference.pdf
- Evidence type: Peer-reviewed time-series foundation-model research.
- Limitations: Massive multidomain pretraining and forecasting evaluation; no ES/NQ after-cost or local hardware guarantee.
- BOT 2.1 relevance: Current time-series MoE feasibility and the scale mismatch to a small market-specific system.

### R14-S13
- Title: Timer-S1: A Billion-Scale Time Series Foundation Model with Serial Scaling.
- Authors: Yong Liu, Xingjian Su, Shiyu Wang, Haoran Zhang, Haixuan Liu, Yuxuan Wang, Zhou Ye, Yang Xiang, Jianmin Wang, Mingsheng Long.
- Year / venue: 2026, arXiv preprint submitted March 5.
- URL: https://arxiv.org/abs/2603.04791
- Evidence type: Current primary preprint; abstract and metadata reviewed.
- Limitations: Author-reported results, no independent reproduction here; large-scale generic forecasting is not trading validation.
- BOT 2.1 relevance: 2026 sparse MoE scaling trajectory, with total versus activated capacity distinction.

### R14-S14
- Title: MoHETS: Long-term Time Series Forecasting with Mixture-of-Heterogeneous-Experts.
- Authors: Evandro S. Ortigossa, Guy Lutsker, Eran Segal.
- Year / venue: 2026, arXiv preprint submitted January 29.
- URL: https://arxiv.org/abs/2601.21866
- Evidence type: Current primary preprint; abstract and metadata reviewed.
- Limitations: Author-reported multivariate benchmarks; no ES/NQ result or verified latency/robustness claim for this setting.
- BOT 2.1 relevance: Heterogeneous expert routing and covariate cross-attention as experimental fusion directions.

## Completion attestation

First-pass research is complete and frozen. Only R14_ENSEMBLES.md and its exact-byte preserved predecessor were written by this specialist, both under docs/bot21_research. No registry edit was made by me; the source appendix is available for provenance-preserving coordinator append. No tests, training, inference, backtests, trading, installations, environment edits or Git mutations were performed. No protected material was accessed. No synthesis, architectural selection, implementation, R17–R20 or red-team work was performed.

### Introduced by R15_GPU_ML_SYSTEMS.md

## Sources

All URLs were researched on 2026-09-24. Living documentation is identified by retrieval year rather than invented publication dates. These are 23 unique primary-source documents; no peer-reviewed study is needed to establish an operating-system wheel support matrix. Conclusions about market performance are deliberately absent.

- **R15-S01 — CUDA GPU Compute Capability.** NVIDIA; living documentation, 2026 retrieval; NVIDIA Developer. URL: https://developer.nvidia.com/cuda/gpus . Type: official hardware table. Limitation: capability is not framework/operator certification. Relevance: identifies RTX 5060 Ti as CC 12.0.
- **R15-S02 — Get Started / Start Locally.** PyTorch Foundation; living documentation, 2026 retrieval; pytorch.org. URL: https://pytorch.org/get-started/locally/ . Type: official installation guide. Limitation: retrieved selector is stale relative to dated releases. Relevance: Windows CUDA and Python compatibility.
- **R15-S03 — Blackwell Architecture Compatibility.** NVIDIA; living guide, 2026 retrieval; CUDA Blackwell Compatibility Guide. URL: https://docs.nvidia.com/cuda/blackwell-compatibility-guide/index.html . Type: official compatibility specification. Limitation: runtime libraries and framework packages require separate checks. Relevance: cubin/PTX and architecture compatibility.
- **R15-S04 — PyTorch 2.14 Release Blog.** PyTorch Foundation; 2026; PyTorch official release announcement, September 2 (updated September 17). URL: https://pytorch.org/blog/pytorch-2-14-release-blog/ . Type: dated release evidence. Limitation: release-wide features do not certify the user's driver or workload. Relevance: current version and CUDA/cuDNN build families.
- **R15-S05 — PyTorch 2.10 Release Blog.** PyTorch Foundation; 2026; official release announcement, January 21. URL: https://pytorch.org/blog/pytorch-2-10-release-blog/ . Type: dated release evidence. Limitation: performance improvements are workload-dependent. Relevance: determinism, numerical debugging and TorchScript deprecation.
- **R15-S06 — PyTorch 2.7 Release.** PyTorch Team; 2025; official release announcement, April 23. URL: https://pytorch.org/blog/pytorch-2-7/ . Type: historical release evidence. Limitation: initial Blackwell support labeled prototype and not a 2026 platform guarantee. Relevance: CUDA 12.8/Blackwell support origin.
- **R15-S07 — Previous PyTorch Versions.** PyTorch Foundation; living documentation, 2026 retrieval; pytorch.org. URL: https://pytorch.org/get-started/previous-versions/ . Type: official binary distribution instructions. Limitation: availability does not establish numerical acceptance. Relevance: version-specific Windows/Linux CUDA families.
- **R15-S08 — Support Matrix.** NVIDIA; living documentation, 2026 retrieval; cuDNN Backend documentation. URL: https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/support-matrix.html . Type: official library support matrix. Limitation: moving latest page; generic driver minima may not cover device introduction. Relevance: Blackwell CUDA and Windows conditions.
- **R15-S09 — CUDA Installation Guide for Microsoft Windows.** NVIDIA; living documentation, 2026 retrieval; CUDA Toolkit documentation. URL: https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html . Type: official toolkit installation reference. Limitation: toolkit/compiler prerequisites differ from prebuilt wheel dependencies. Relevance: separates host tooling from packaged runtime.
- **R15-S10 — Automatic Mixed Precision package, torch.amp.** PyTorch contributors; 2026 retrieval; PyTorch 2.14 API documentation. URL: https://docs.pytorch.org/docs/2.14/amp.html . Type: official API/numerical guidance. Limitation: operation coverage and numerical suitability vary. Relevance: autocast, FP16/BF16 and GradScaler.
- **R15-S11 — CUDA semantics.** PyTorch contributors; 2026 retrieval; PyTorch 2.14 developer notes. URL: https://docs.pytorch.org/docs/2.14/notes/cuda.html . Type: official semantics. Limitation: controls are version-specific and do not establish trading decision stability. Relevance: TF32, reductions, asynchronous execution and memory.
- **R15-S12 — Performance Tuning Guide.** PyTorch tutorial contributors; 2026 retrieval; PyTorch Tutorials. URL: https://docs.pytorch.org/tutorials/recipes/recipes/tuning_guide.html . Type: official engineering guidance. Limitation: recommendations require workload measurement. Relevance: transfer, loader and compiler tradeoffs.
- **R15-S13 — How to use torch.compile on Windows CPU/XPU.** PyTorch tutorial contributors; 2026 retrieval; PyTorch Tutorials, unstable tutorial collection. URL: https://docs.pytorch.org/tutorials/unstable/inductor_windows.html . Type: official platform tutorial. Limitation: CPU/XPU scope does not prove NVIDIA support or impossibility. Relevance: prevents conflating Windows CUDA and Inductor support.
- **R15-S14 — triton-windows README.** triton-windows maintainers; living repository, 2026 retrieval; triton-lang GitHub project. URL: https://github.com/triton-lang/triton-windows/blob/readme/README.md . Type: project-maintainer primary documentation. Limitation: separate packaging/support path, no host verification. Relevance: identifies a conditional native Windows compiler route without prescribing installation.
- **R15-S15 — CUDA on WSL User Guide.** NVIDIA; living documentation, 2026 retrieval; CUDA documentation. URL: https://docs.nvidia.com/cuda/wsl-user-guide/index.html . Type: official platform guide. Limitation: WSL adds environmental and tooling constraints. Relevance: host driver usage and future Linux alternative.
- **R15-S16 — Reproducibility.** PyTorch contributors; 2026; PyTorch 2.14 developer notes, page updated May 14. URL: https://docs.pytorch.org/docs/2.14/notes/randomness.html . Type: official reproducibility guidance. Limitation: no cross-release/platform bitwise guarantee. Relevance: seeds, deterministic operations and cuDNN controls.
- **R15-S17 — Saving and Loading Models.** PyTorch tutorial contributors; 2026 retrieval; PyTorch Tutorials. URL: https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html . Type: official persistence tutorial. Limitation: full application/data traversal recovery needs additional state. Relevance: state_dict and optimizer checkpoint distinction.
- **R15-S18 — torch.utils.checkpoint.** PyTorch contributors; 2026 retrieval; PyTorch 2.14 API documentation. URL: https://docs.pytorch.org/docs/2.14/checkpoint.html . Type: official API specification. Limitation: recomputation and RNG caveats; no measured benefit here. Relevance: activation-memory tradeoffs.
- **R15-S19 — torch.utils.data.** PyTorch contributors; 2026 retrieval; PyTorch 2.14 API documentation. URL: https://docs.pytorch.org/docs/2.14/data.html . Type: official data-loading specification. Limitation: dataset-specific throughput and memory unknown. Relevance: Windows spawn, seeds, worker duplication and ordering.
- **R15-S20 — torch.profiler.** PyTorch contributors; 2026 retrieval; PyTorch 2.14 API documentation. URL: https://docs.pytorch.org/docs/2.14/profiler.html . Type: official instrumentation specification. Limitation: overhead and CUPTI/platform coverage affect traces. Relevance: CPU/GPU timing and memory diagnosis.
- **R15-S21 — Installation.** JAX authors; living documentation, 2026 retrieval; JAX documentation. URL: https://docs.jax.dev/en/latest/installation.html . Type: official platform/package matrix. Limitation: WSL2 NVIDIA path experimental; no actual-machine verification. Relevance: native Windows NVIDIA unsupported and CUDA package choices.
- **R15-S22 — Install TensorFlow with pip.** TensorFlow authors/Google; living documentation, 2026 retrieval; TensorFlow installation guide. URL: https://www.tensorflow.org/install/pip . Type: official installation matrix. Limitation: some version examples retrieved are older, not a Blackwell certification. Relevance: native Windows GPU cutoff and WSL2 route.
- **R15-S23 — Compute Capabilities.** NVIDIA; living documentation, 2026 retrieval; CUDA Programming Guide, appendix 5.1. URL: https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/compute-capabilities.html . Type: official architecture feature reference. Limitation: hardware instructions do not guarantee framework dispatch/performance. Relevance: precision hardware context.


## R0-B recovery batch 2 independent-source append — 2026-09-24

Provenance: verbatim source appendices from frozen R16, R17, R18, and R19 reports. Counts are specialist-local records and are not asserted to be globally unique. Existing records and prior appends are preserved.

### Introduced by R16_SESSION_SYNCHRONIZATION.md

## Sources

All URLs below were searched/opened on 2026-09-24. Living documentation years are reported as undated/current rather than fabricated publication years. Citations identify source facts; the twelve answers and proposed evidence gates are the specialist's reasoning, not claims that CME prescribes a neural design.

### R16-S01
- Title: CME Group Holiday and Trading Hours.
- Organization/year/venue: CME Group; living page with 2026 schedules; CME official website.
- URL: https://www.cmegroup.com/trading-hours.html
- Type/review: exchange primary operational documentation; not academic peer review.
- Finding: dated platform/product holiday schedules differ from normal hours and can change.
- Limitation: dynamic tables; this review did not extract and verify every ES/NQ daily exception.
- Relevance: authoritative starting point for dated session evidence, not generic weekday arithmetic.

### R16-S02
- Title: E-mini S&P 500 Futures Overview.
- Organization/year/venue: CME Group; current 2026 view; CME product website.
- URL: https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.timeAndSales.html?videoId=6400720213112
- Type/review: official product documentation; not peer reviewed.
- Finding: ES normal Globex hours and maintenance window are explicitly separated from other trading facilities.
- Limitation: overview is not a complete historical exception calendar.
- Relevance: normal ES session envelope.

### R16-S03
- Title: E-mini Nasdaq-100 Futures Overview.
- Organization/year/venue: CME Group; current September 2026 view; CME product website.
- URL: https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.timeAndSales.html?videoId=6396076863112
- Type/review: official product documentation; not peer reviewed.
- Finding: NQ normal Globex hours include the daily maintenance break.
- Limitation: product overview does not prove every historical halt/holiday boundary.
- Relevance: independent NQ product confirmation instead of assuming all ES rules transfer.

### R16-S04
- Title: Equity Index Roll Dates.
- Organization/year/venue: CME Group; living page with 2025–2028 table; CME website.
- URL: https://www.cmegroup.com/trading/equity-index/rolldates.html
- Type/review: exchange primary reference; not peer reviewed.
- Finding: customary roll and expiration are distinct; 2026 June dates are June 15 and June 18.
- Limitation: customary lead month does not specify an individual research continuous-series method.
- Relevance: contract identity and exception-aware roll provenance.

### R16-S05
- Title: Common fields, enums and types.
- Organization/year/venue: Databento; undated living documentation current at access; Databento Docs.
- URL: https://databento.com/docs/standards-and-conventions/common-fields-enums-types
- Type/review: provider primary technical documentation; not peer reviewed.
- Finding: event, send and receive timestamps have different semantics; publisher clock differences can remain in data.
- Limitation: documentation does not establish the actual archive or local application latency.
- Relevance: timestamp meanings and clock uncertainty must survive normalization.

### R16-S06
- Title: Aggregate bars (OHLCV).
- Organization/year/venue: Databento; undated living documentation current at access; Databento Docs.
- URL: https://databento.com/docs/schemas-and-data-formats/ohlcv
- Type/review: provider primary schema documentation; not peer reviewed.
- Finding: start labels, receipt-time interval basis, no record for no trades, and UTC daily aggregation.
- Limitation: archive schema version/custom transformations unverified; publication timing is not guaranteed by the label.
- Relevance: bar availability, missingness and session identity cannot be inferred from timestamp names.

### R16-S07
- Title: MDP 3.0 - Trade Summary.
- Organization/year/venue: CME Group; undated living documentation; CME Client Systems Wiki.
- URL: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457418925
- Type/review: official technical documentation; not peer reviewed.
- Finding: TransactTime denotes event-processing start in epoch nanoseconds; messages identify instruments and update actions.
- Limitation: field semantics do not prove synchronized gateway clocks or subscriber availability.
- Relevance: exchange event time and subsequent receipt/correction history are distinct evidence.

### R16-S08
- Title: Time Zones.
- Organization/year/venue: IANA; living page, 2026d release displayed at access; IANA.
- URL: https://www.iana.org/time-zones
- Type/review: official technical database documentation; not academic peer review.
- Finding: timezone data encode historical local offsets and DST rules and are updated.
- Limitation: civil timezone rules do not supply exchange schedules.
- Relevance: pin timezone provenance separately from market calendar provenance.

### R16-S09
- Title: On covariance estimation of non-synchronously observed diffusion processes.
- Authors/year/venue: Takaki Hayashi and Nakahiro Yoshida; 2005; Bernoulli 11(2), 359–379.
- URL: https://www.ms.u-tokyo.ac.jp/~nakahiro/mypapers_for_personal_use/hayyos03.pdf
- Type/review: original journal research, author-hosted paper; peer reviewed.
- Finding: covariance can be estimated while accounting for nonsynchronous observation intervals.
- Limitation: model assumptions and covariance objective do not validate neural prediction, real latency, or a specific ES/NQ join.
- Relevance: principled warning against treating synchronization as an innocuous preprocessing detail.

### R16-S10
- Title: Estimation of the lead-lag parameter from non-synchronous data.
- Authors/year/venue: Marc Hoffmann, Mathieu Rosenbaum and Nakahiro Yoshida; 2013; Bernoulli 19, author-listed journal publication; arXiv:1303.4871 author manuscript.
- URLs: https://arxiv.org/abs/1303.4871 ; https://www.ceremade.dauphine.fr/~hoffmann/static3/research
- Type/review: original statistical research; journal publication peer reviewed, arXiv copy itself not a separate review.
- Finding: lead/lag estimation accounts for nonsynchronous sampling and sampling sparsity.
- Limitation: theoretical inference does not establish a usable ES/NQ trading edge or permit future shifting in inputs.
- Relevance: distinguish acquisition artifacts and retrospective estimation from causal forecasting.

### R16-S11
- Title: Equity Index Later Close for CME Globex Trading Day, Daily Price Limits; Advisory 12-423.
- Organization/year/venue: CME Clearing; 2012, notice October 1 effective November 18; CME advisory archive.
- URL: https://www.cmegroup.com/tools-information/lookups/advisories/clearing/Chadv12-423.html
- Type/review: historical exchange primary notice; not peer reviewed.
- Finding: historical hours, halts and trade-date transition were changed explicitly.
- Limitation: historical, not authority for present hours.
- Relevance: reject timeless session templates and record effective dates.

### R16-S12
- Title: Juneteenth Holiday 6/19/2026 Settlement Times.
- Organization/year/venue: CME Group; 2026; official holiday-calendar PDF.
- URL: https://www.cmegroup.com/tools-information/holiday-calendar/files/2026/juneteenth-day-settlement-times-2026.pdf
- Type/review: exchange primary notice; not peer reviewed.
- Finding: June 19 settlement dissemination exception is explicitly specified.
- Limitation: settlement notice is not the product's full trading-hours schedule.
- Relevance: settlement calendar must not be substituted for tradability or expiry evidence.

### R16-S13
- Title: BOT2_CURRENT_STATE_MASTER_AUDIT.md.
- Organization/year/venue: prior BOT2 audit coordinator; supplied local 2026 audit; repository docs.
- Location: C:/Users/fjone/hyperliquid-trading-bot-phase5c-v3/docs/BOT2_CURRENT_STATE_MASTER_AUDIT.md
- Type/review: permitted local static-audit context; not peer reviewed or independently revalidated here.
- Finding: identifies first-row session origin, dual synchronization concepts and receipt-time uncertainty.
- Limitation: report assertions do not certify actual archives or runtime behavior; tool output was lengthy/truncated, relevant audit sections and handoff were visible.
- Relevance: establishes the bounded questions addressed without inspecting protected data.

## Independence, safety and freeze attestation

I read the full current user request and the permitted audit context. I did not read existing R16 conclusions, old R17–R19, the master synthesis, any newly generated specialist report, or the source registry. No R1–R15 content was needed. The existing R16 was copied without reading its content to R16_PRE_BATCH2_COORDINATOR_DRAFT.md; both source and copy hashed CD82844DA9729BD7BD7EE76ABC4F497F335D6874C9FAECCEEC24E8E58F3C4B78 before replacement.

This specialist wrote only these two authorized research documents under docs/bot21_research. No BOT2 source, datasets, features, labels, manifests, Phase 5C, risk, execution, environments or Git state were changed. No protected output/OOS was accessed; no model inference, training, tests, experiments, backtests, trading, broker connections or installations occurred. Public browsing and document copy/write/hash operations are the only research operations beyond reading the request/audit. These attestations apply to this specialist's actions, not unknowable project history.

Frozen on completion; SHA-256 is returned separately to avoid a self-referential hash. Later critique may challenge these conclusions but should not silently rewrite the frozen report. No R20 or X1–X8 work was performed.

### Introduced by R17_DECISION_ARCHITECTURE.md

## Sources

All accessed 2026-09-24. The 12 records below are unique works/documentation records; multiple URLs for a work do not increase the count. Search snippets and publisher/author abstracts were used where full text was unnecessary for the bounded claim; claims do not imply full-paper replication. No public source establishes BOT 2.1 performance.

### R17-S01
- Title: Task-based End-to-end Model Learning in Stochastic Optimization.
- Authors: Priya Donti, Brandon Amos, J. Zico Kolter.
- Year/venue: 2017; NIPS 30. Type/status: primary conference research, peer-reviewed.
- URL: https://proceedings.neurips.cc/paper/2017/hash/3fc2c60b5782f641f76bcefc39fb2392-Abstract.html
- Finding: Downstream task-based learning can outperform conventional modeling and black-box policy optimization in studied tasks.
- Limitation: Inventory, grid scheduling and energy storage applications; not ES/NQ or authority governance.
- BOT 2.1 relevance: Substantive reason to investigate objective alignment without assuming unrestricted autonomy.

### R17-S02
- Title: On Calibration of Modern Neural Networks.
- Authors: Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger.
- Year/venue: 2017; ICML, PMLR 70:1321–1330. Type/status: primary research, peer-reviewed.
- URL: https://proceedings.mlr.press/v70/guo17a.html
- Finding: Modern networks can be miscalibrated; temperature scaling was effective on many studied datasets.
- Limitation: Classification benchmarks, not a universal shifted-market calibration result.
- BOT 2.1 relevance: Output confidence needs independent interpretation and evaluation.

### R17-S03
- Title: Can You Trust Your Model's Uncertainty? Evaluating Predictive Uncertainty Under Dataset Shift.
- Authors: Yaniv Ovadia, Emily Fertig, Jie Ren, Zachary Nado, D. Sculley, Sebastian Nowozin, Joshua V. Dillon, Balaji Lakshminarayanan, Jasper Snoek.
- Year/venue: 2019; NeurIPS 32. Type/status: primary benchmark research, peer-reviewed.
- URL: https://papers.neurips.cc/paper_files/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html
- Finding: Uncertainty methods, including post-hoc calibration, can degrade under dataset shift.
- Limitation: Benchmark findings are not guarantees for market regimes.
- BOT 2.1 relevance: Shift reliability cannot be inferred from nominal calibration.

### R17-S04
- Title: SelectiveNet: A Deep Neural Network with an Integrated Reject Option.
- Authors: Yonatan Geifman, Ran El-Yaniv.
- Year/venue: 2019; ICML, PMLR 97:2151–2159. Type/status: primary research, peer-reviewed.
- URL: https://proceedings.mlr.press/v97/geifman19a.html
- Finding: Jointly learned prediction and rejection improved benchmark risk–coverage tradeoffs.
- Limitation: Selective prediction risk is not trading loss or a capital constraint.
- BOT 2.1 relevance: Abstention is compatible with end-to-end learning.

### R17-S05
- Title: Conformal prediction beyond exchangeability.
- Authors: Rina Foygel Barber, Emmanuel J. Candès, Aaditya Ramdas, Ryan J. Tibshirani.
- Year/venue: 2023; Annals of Statistics 51(2). Type/status: primary statistical research, peer-reviewed.
- URL/DOI: https://doi.org/10.1214/23-AOS2276 ; author text https://arxiv.org/abs/2202.13415
- Finding: Weighted/randomized extensions address coverage degradation under nonexchangeability.
- Limitation: Guarantees depend on mathematical conditions and do not guarantee selected-trade tails or profits.
- BOT 2.1 relevance: Makes assumptions behind uncertainty coverage explicit.

### R17-S06
- Title: Conservative Q-Learning for Offline Reinforcement Learning.
- Authors: Aviral Kumar, Aurick Zhou, George Tucker, Sergey Levine.
- Year/venue: 2020; NeurIPS 33. Type/status: primary research, peer-reviewed.
- URL: https://proceedings.neurips.cc/paper/2020/hash/0d2b2061826a5df3221116a5085a6052-Abstract.html
- Finding: Dataset-to-policy shift can cause value overestimation; conservative learning addresses it under studied assumptions.
- Limitation: Control benchmarks and theoretical conditions do not certify a financial policy.
- BOT 2.1 relevance: Highlights unsupported-action risk if an action model uses offline RL.

### R17-S07
- Title: Hidden Technical Debt in Machine Learning Systems.
- Authors: D. Sculley, Gary Holt, Daniel Golovin, Eugene Davydov, Todd Phillips, Dietmar Ebner, Vinay Chaudhary, Michael Young, Jean-François Crespo, Dan Dennison.
- Year/venue: 2015; NIPS 28. Type/status: primary systems experience paper, peer-reviewed conference.
- URL: https://proceedings.neurips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html
- Finding: Entanglement, feedback, dependencies and configuration create system-level maintenance risks.
- Limitation: Qualitative systems evidence, not a controlled A/B trading comparison.
- BOT 2.1 relevance: Neither fewer modules nor more boundaries guarantees maintainability.

### R17-S08
- Title: Artificial Intelligence Risk Management Framework (AI RMF 1.0).
- Author/organization: Elham Tabassi; NIST.
- Year/venue: 2023; NIST AI 100-1. Type/status: official voluntary framework; not a peer-reviewed experiment.
- URL/DOI: https://doi.org/10.6028/NIST.AI.100-1
- Finding: Organizes lifecycle risk work around governance, mapping, measurement and management.
- Limitation: Use-case agnostic and voluntary; no specific trading architecture or permission is established.
- BOT 2.1 relevance: Accountability and evaluation must extend beyond a model score.

### R17-S09
- Title: Pre-Trade Risk Management.
- Organization: CME Group.
- Year/venue: Undated live official documentation, checked in 2026. Type/status: primary exchange documentation; not academic peer review.
- URL: https://www.cmegroup.com/solutions/market-access/globex/trade-on-globex/pre-trade-risk-management.html
- Finding: Documents risk limits, permissions, monitoring and audit trails administered for market participants.
- Limitation: Access and protection depend on actual participant setup; not complete bot safety evidence.
- BOT 2.1 relevance: Illustrates separation between a trade-generating system and permission/risk administration.

### R17-S10
- Title: CME Globex Credit Controls (GC2), with What's New revision record.
- Organization: CME Group.
- Year/venue: Live documentation; revision record includes 2026-05-13. Type/status: primary exchange operational documentation; not academic peer review.
- URLs: https://www.cmegroup.com/tools-information/webhelp/globex-credit-controls/Content/CME-Globex-Credit-Controls-Management.html ; https://www.cmegroup.com/tools-information/webhelp/globex-credit-controls/Content/Whats-New.html
- Finding: Documents administrator-controlled pre-execution exposure/quantity settings and current weekday/weekend updates.
- Limitation: Clearing-level tooling does not establish which controls BOT 2.1 would have or guarantee prevention of all loss.
- BOT 2.1 relevance: Current through-2026 evidence that authority is a distinct operational concern.

### R17-S11
- Title: Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead.
- Author: Cynthia Rudin.
- Year/venue: 2019; Nature Machine Intelligence 1:206–215. Type/status: scholarly Perspective, accepted journal publication; not an ES/NQ experiment.
- URL/DOI: https://doi.org/10.1038/s42256-019-0048-x
- Finding: Distinguishes inherent interpretability from potentially unfaithful explanations of black boxes.
- Limitation: Argument and examples do not prove interpretable models dominate this financial task.
- BOT 2.1 relevance: Intermediate outputs and saliency should not be mistaken for faithful reasons.

### R17-S12
- Title: Online Decision-Focused Learning.
- Authors: Aymeric Capitaine, Maxime Haddouche, Eric Moulines, Michael I. Jordan, Etienne Boursier, Alain Durmus.
- Year/venue: 2025 initial preprint; v3 revised 2026-03-07; arXiv 2505.13564.
- Type/status: primary academic preprint; peer-review status not established from consulted record.
- URL: https://arxiv.org/abs/2505.13564v3
- Finding: Studies evolving objectives/distributions with static/dynamic regret results and a knapsack example.
- Limitation: Assumption-dependent theory and a nonmarket application; no evidence of trading readiness.
- BOT 2.1 relevance: Keeps the decision-focused comparison current through 2026 without overstating maturity.


### Introduced by R18_ADVERSARIAL_REVIEW.md

## Sources

All accessed 2026-09-24. Fifteen distinct public primary records; multiple URLs/versions of one work count once. Landing pages/abstracts support bounded claims; selected primary manuscript text was inspected. No full-proof/code audit or replication is claimed. The register is R18's conditional reasoning against local reports, not literature-measured BOT failure frequencies. Snn in the text means R18-Snn. Source entries are available for coordinator provenance-preserving registry append; R18 did not edit the registry.

### R18-S01
- Title: On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation.
- Authors/year/venue: Gavin C. Cawley, Nicola L. C. Talbot; 2010, JMLR 11:2079–2107.
- URL: https://www.jmlr.org/papers/v11/cawley10a.html
- Type/review: original peer-reviewed methodology.
- Finding: finite-sample selection criteria can themselves overfit.
- Limitation: general ML evidence, not ES/NQ incidence.
- Relevance: selection accounting extends beyond fitted weights.

### R18-S02
- Title: The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.
- Authors/year/venue: David H. Bailey, Marcos López de Prado; 2014, Journal of Portfolio Management 40(5):94–107; author manuscript inspected.
- URL: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Type/review: primary journal methodology, peer-reviewed publication.
- Finding: adjusts Sharpe assessment for selection and nonnormality.
- Limitation: trial/moment assumptions remain; does not repair leakage.
- Relevance: corrected performance is not universal approval.

### R18-S03
- Title: The Probability of Backtest Overfitting.
- Authors/year/venue: David H. Bailey, Jonathan M. Borwein, Marcos López de Prado, Qiji Jim Zhu; author manuscript revised February 2015; later publication not relied on.
- URL: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- Type/review: primary manuscript; review status of this copy not independently established.
- Finding: combinatorial assessment addresses selection overfitting.
- Limitation: candidate universe and time structure matter; no local result examined.
- Relevance: distinguish selection diagnostics from causal deployment evidence.

### R18-S04
- Title: Aggregate bars (OHLCV).
- Organization/year/venue: Databento; living official provider schema, 2026 retrieval.
- URL: https://databento.com/docs/schemas-and-data-formats/ohlcv
- Type/review: primary technical documentation, not academic peer review.
- Finding: start labels, ts_recv aggregation basis, missing no-trade bars and UTC daily basis differ from simplistic assumptions.
- Limitation: actual repository archive lineage/version unverified.
- Relevance: field names/clean bars do not certify decision availability.

### R18-S05
- Title: TSFMAudit: Data Contamination Auditing in Forecasting Time Series Foundation Models.
- Authors: Hongkai Li, Shifeng Xie, Lefei Shen, Zhuo Li, Mouxiang Chen, Xiaobin Zhang, Han Fu, Jianling Sun, Xiaoxue Ren, Chenghao Liu.
- Year/venue: 2026, arXiv:2605.26161v1.
- URL: https://arxiv.org/abs/2605.26161
- Type/review: original preprint; peer review not established.
- Finding: proposes adaptation-dynamics auditing, studied across six TSFMs and 187 datasets.
- Limitation: documented-source supervision and empirical detection are not universal non-exposure proof.
- Relevance: opaque pretraining remains a separate contemporary validity surface.

### R18-S06
- Title: It's TIME: Towards the Next Generation of Time Series Forecasting Benchmarks.
- Authors: Zhongzheng Qiao, Sheng Pan, Anni Wang, Viktoriya Zhukova, Yong Liu, Xudong Jiang, Qingsong Wen, Mingsheng Long, Ming Jin, Chenghao Liu.
- Year/venue: 2026, ICML acceptance declared in camera-ready arXiv v4, June 3.
- URL: https://arxiv.org/abs/2602.12147
- Type/review: primary conference research; acceptance verified from author record.
- Finding: fresh task-centric benchmark addresses legacy-data/integrity weaknesses.
- Limitation: author-described integrity and generic tasks do not establish ES/NQ profitability or every checkpoint's cleanliness.
- Relevance: updates R02 publication status without changing transfer limits.

### R18-S07
- Title: On Calibration of Modern Neural Networks.
- Authors/year/venue: Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger; 2017, ICML/PMLR 70.
- URL: https://proceedings.mlr.press/v70/guo17a.html
- Type/review: primary peer-reviewed empirical research.
- Finding: confidence calibration differs from predictive accuracy.
- Limitation: classification benchmarks/post-processing do not guarantee shifted-market reliability.
- Relevance: calibration and action confidence need separate interpretation.

### R18-S08
- Title: Conformal prediction beyond exchangeability.
- Authors/year/venue: Rina Foygel Barber, Emmanuel J. Candès, Aaditya Ramdas, Ryan J. Tibshirani; 2023, Annals of Statistics; arXiv:2202.13415.
- URL: https://arxiv.org/abs/2202.13415
- Type/review: primary peer-reviewed statistical methodology, author copy.
- Finding: develops coverage methodology beyond exchangeability.
- Limitation: guarantee scope/assumptions do not imply selected-trade tail control.
- Relevance: marginal, temporal and conditional promises differ.

### R18-S09
- Title: CME Group Holiday and Trading Hours.
- Organization/year/venue: CME Group; living exchange documentation with 2026 schedules.
- URL: https://www.cmegroup.com/trading-hours.html
- Type/review: official operational source, not academic peer review.
- Finding: product/platform-specific dated schedules and exceptions matter.
- Limitation: no complete historical ES/NQ calendar reconstruction here.
- Relevance: session identity cannot follow surviving rows.

### R18-S10
- Title: Equity Index Roll Dates.
- Organization/year/venue: CME Group; living exchange reference, 2026 access.
- URL: https://www.cmegroup.com/trading/equity-index/rolldates.html
- Type/review: primary exchange reference, not academic peer review.
- Finding: customary roll differs from expiry; June 2026 expiry is June 18.
- Limitation: customary dates do not choose a research continuous-series rule.
- Relevance: reject timeless expiry arithmetic and hindsight contract selection.

### R18-S11
- Title: Conformal Inference for Online Prediction with Arbitrary Distribution Shifts.
- Authors/year/venue: Isaac Gibbs, Emmanuel J. Candès; 2024, JMLR 25(162):1–36.
- URL: https://www.jmlr.org/papers/v25/22-1218.html
- Type/review: primary peer-reviewed theory/methodology.
- Finding: online adjustment addresses distribution shifts with specified regret properties.
- Limitation: no per-trade profit guarantee or automatic delayed-feedback solution.
- Relevance: adaptive uncertainty remains a chronological fitted process.

### R18-S12
- Title: SelectiveNet: A Deep Neural Network with an Integrated Reject Option.
- Authors/year/venue: Yonatan Geifman, Ran El-Yaniv; 2019, ICML/PMLR 97:2151–2159.
- URL: https://proceedings.mlr.press/v97/geifman19a.html
- Type/review: primary peer-reviewed research.
- Finding: joint prediction/rejection trades risk against coverage.
- Limitation: benchmark selective loss is not economic utility.
- Relevance: accepted-set evidence needs denominators and separate validation.

### R18-S13
- Title: Can you trust your model's uncertainty? Evaluating predictive uncertainty under dataset shift.
- Authors: Yaniv Ovadia, Emily Fertig, Jie Ren, Zachary Nado, D. Sculley, Sebastian Nowozin, Joshua Dillon, Balaji Lakshminarayanan, Jasper Snoek.
- Year/venue: 2019, NeurIPS 32.
- URL: https://papers.neurips.cc/paper_files/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html
- Type/review: primary peer-reviewed empirical study.
- Finding: uncertainty under shift needs distinct assessment.
- Limitation: benchmark shifts do not establish futures calibration.
- Relevance: agreement/validation calibration cannot certify new regimes.

### R18-S14
- Title: About Paper Trading Accounts.
- Organization/year/venue: Interactive Brokers, Broker Portal User Guide; updated October 9, 2025, retrieved 2026.
- URL: https://www.ibkrguides.com/brokerportal/aboutpapertradingaccounts.htm
- Type/review: official provider documentation, not academic peer review.
- Finding: top-of-book simulation, stops and partials can differ from production.
- Limitation: IBKR-specific; not an assertion that BOT uses it.
- Relevance: primary counterexample to treating paper as realized execution evidence.

### R18-S15
- Title: CME Globex Matching Algorithms.
- Organization/year/venue: CME Group Client Systems Wiki; living technical documentation, 2026 access.
- URL: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457316046
- Type/review: official exchange specification, not academic peer review.
- Finding: allocation/matching follows explicit priority procedures.
- Limitation: product/date-specific rules and actual queue history need independent evidence; no queue reconstruction performed.
- Relevance: touched/traded prices alone cannot establish a particular order's fill.

## Frozen dependency SHA-256

These identify the exact report versions reviewed, not clean data or non-exposure. R01–R15 remain unmodified by R18; coordinator baseline comparison establishes batch-wide integrity. R16/R17/R19 were read after freeze and never rewritten. Paths are relative to docs/bot21_research/.
| Report | SHA-256 |
|---|---|
| R01_NEURAL_ARCHITECTURES.md | D54719AB05F0E43F3BF66DC0CDA10809BA7EBFDB33CBDBBC11E1014D86B87721 |
| R02_2025_2026_FRONTIER.md | 0E7AFF96113DBD10F5EE540104BFA36D4897A96150F708658C9BBEA2D1E4C691 |
| R03_FINANCIAL_ML.md | EA903271702FC666D507A7A383042A60D76D8002B92A7D94BD50E9A1CC107421 |
| R04_ES_NQ_MICROSTRUCTURE.md | 32842EB4A22BA8B4D88C2AE8EB141041F48C04B95E0EC5C8590D253F51FE6E47 |
| R05_MARKET_REPRESENTATION.md | 9EED9426070E9F374E0754742A43C71591AC375BC10D16E23376DFFBB423C919 |
| R06_MULTI_TIMEFRAME.md | 3EC4703C07D3887CCE55D340241DA42499BEEE51A18ED8FC1521CB9BD9E63325 |
| R07_TARGETS.md | 3C97EF4EAD741E6BF41BB57CDE34093AC645083BEB8AA241D2411372A40A2DCF |
| R08_REGIMES.md | EC25739C877895FDD96CD247ABC2F678727AA6BC13A0C099798004B5FAE6A6DE |
| R09_UNCERTAINTY.md | A9CA1C3F6C1AE7439760C49A8F9408F62852C05E5FEBE19B01848E7426518972 |
| R10_VALIDATION.md | 84B50653796003218A3C8B27569C7079C7F779FEE719198C6258BD9AD0E68FFA |
| R11_LEAKAGE.md | 0D350D044356BCA49DCFE14D9DEA6E686FADBF9E791BD8B5ABC6FF4B20FED5F4 |
| R12_LOSS_OPTIMIZATION.md | B3B9469F0FB55694A8B3FAAB86B0B2D098BA451EDD17C24719347400D20E303E |
| R13_NONSTATIONARITY.md | 955E576244E4947F1C790298F912C96740327A925B57BB0EF5F674E34562DE6A |
| R14_ENSEMBLES.md | A77B7B38BBD4716E9DA061885280C15CF2674852005AF1A19780627988ADC22C |
| R15_GPU_ML_SYSTEMS.md | C02A624A29E1B6BB3C98FCC24A7DC7DB48B57F2700578D6E343C381E7B118D9A |
| R16_SESSION_SYNCHRONIZATION.md | 8CA2503D197A25FE9752029D94EF41F45EDC89E290753750C08CC7F0C6EC0A3E |
| R17_DECISION_ARCHITECTURE.md | CF1B2BA158DBE74436D2389EC6926B58C22EBDA3F0312D9E43CDE3810870B01F |
| R19_BOT20_PRESERVATION.md | 4A259DCC761FF976D0799CC2041A0925AF85CDF9B3FB491A2D62A360B67895EC |
## Completion and safety attestation

COMPLETE — FROZEN. Failure-mode count 52; public sources 15; local report dependencies 18. Only R18_ADVERSARIAL_REVIEW.md and its unread exact-byte predecessor R18_PRE_BATCH2_COORDINATOR_DRAFT.md were written in the authorized research directory. No registry/sibling edits. Final hash returned externally to avoid self-reference.

No BOT 2.0 source/configuration, dataset, labels, feature artifacts, manifests, Phase 5C artifacts, risk/execution/paper/ledger material, protected outputs or OOS were opened or modified. No training, inference, tests, experiments, backtests, scoring, trading, broker connection, installation, environment/CUDA/driver change or Git mutation occurred. Only document reading/copying/writing/hashing and public research. No R18 subagents. Branch/HEAD and dirty-tree baseline were not independently inspected by R18; coordinator custody governs the batch audit.

No R01–R19 disagreements were resolved, architecture selected, strategy or implementation designed, or R20/X1–X8 started. Research completion is an adversarial challenge document, not empirical validation. Stop at handoff.

### Introduced by R19_BOT20_PRESERVATION.md

## Sources

All public sources below were consulted on 2026-09-24. Official living documentation was checked as available through that date; older foundational documents are retained where applicable. No claim is made of an exhaustive survey or 2026 experimental validation. No peer-reviewed empirical paper is required to infer this preservation boundary; the six public sources are official methodology/technical documentation, not BOT-specific validation.

### R19-S01
- Title: BOT 2.0 — Current-State Master Architecture & Capability Audit.
- Author/organization: local BOT 2.0 audit coordinator; individual author not independently verified.
- Year/date and venue: 2026-09-24; repository internal audit.
- Location: `C:/Users/fjone/hyperliquid-trading-bot-phase5c-v3/docs/BOT2_CURRENT_STATE_MASTER_AUDIT.md`.
- Type/review status: internal static architecture audit, not peer reviewed; some market-data review delegated per its own account.
- Finding: mixed adjacent research/operational components, dirty baseline, protected Phase 5C paused, uncertain runtime readiness and provenance; identifies preservation and reuse zones.
- Limitation: no present execution verification, no protected artifact access, no proof of effective runtime permissions or historical non-exposure; R19 relies on audit rather than raw source.
- Relevance: sole internal factual basis for the component map and local risk assessment.

### R19-S02
- Title: venv — Creation of virtual environments.
- Author/organization: Python Software Foundation and Python documentation contributors.
- Year/version and venue: living Python 3 standard-library documentation, accessed 2026; no fixed article year asserted.
- URL: https://docs.python.org/3/library/venv.html
- Type/review status: official technical documentation; not an academic peer-reviewed study.
- Finding: virtual environments have independent installed packages and a base interpreter; environments are generally recreated rather than moved/copied.
- Limitation: package isolation is not a claim of filesystem, credential, network or kernel containment.
- Relevance: separate dependency environments are necessary hygiene but cannot establish the preservation boundary alone.

### R19-S03
- Title: Zero Trust Architecture, NIST SP 800-207.
- Authors/organization: Scott Rose, Oliver Borchert, Stu Mitchell, Sean Connelly; NIST.
- Year/venue: 2020, final 11 August; NIST Special Publication.
- URL/DOI: https://csrc.nist.gov/pubs/sp/800/207/final ; https://doi.org/10.6028/NIST.SP.800-207
- Type/review status: official government architecture guidance; public standards-development review, not a journal experiment.
- Finding: location or ownership alone confers no implicit trust; resource access requires distinct authentication and authorization.
- Limitation: enterprise architecture guidance does not certify BOT permissions or prescribe this project's process topology.
- Relevance: supports independent resource-authority boundaries rather than trusting repository/package membership.

### R19-S04
- Title: Bulkhead pattern.
- Author/organization: Microsoft Azure Architecture Center.
- Year/venue: living official architecture guidance, consulted 2026; fixed original publication year not established.
- URL: https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead
- Type/review status: official engineering pattern documentation; not academic peer reviewed.
- Finding: separating workload/resource pools can prevent a failing or overloaded consumer from causing cascading resource failure.
- Limitation: architectural pattern and tradeoffs, not a measured guarantee for this machine or application.
- Relevance: motivates independent resource and failure domains, including logs, storage and feed consumers.

### R19-S05
- Title: Language Guide (proto 3), Updating A Message Type.
- Author/organization: Google / Protocol Buffers documentation contributors.
- Year/venue: living official Protocol Buffers documentation, consulted 2026; fixed article year not established.
- URL: https://protobuf.dev/programming-guides/proto3/#updating
- Type/review status: official format/language documentation, not peer-reviewed empirical research.
- Finding: wire compatibility and application compatibility differ; safe changes depend on format and consumer behavior.
- Limitation: Protobuf-specific rules do not directly govern existing JSON/Python contracts or establish scientific semantic equivalence.
- Relevance: evidence for reviewing versioned interface meaning and consumer behavior, without selecting a serialization technology.

### R19-S06
- Title: Secure Windows containers.
- Author/organization: Microsoft Learn, Windows containers documentation.
- Year/venue: living official technical documentation, consulted 2026; fixed article year not established.
- URL: https://learn.microsoft.com/en-us/virtualization/windowscontainers/manage-containers/container-security
- Type/review status: official security documentation; not academic peer reviewed.
- Finding: process-isolated containers share host-kernel exposure; hypervisor-isolated containers provide a stronger security boundary.
- Limitation: container guidance does not prove platform support, deployment fitness or operational isolation on the audited Windows host.
- Relevance: prevents overstating a separate process/container as complete containment; technology choice remains future work.

### R19-S07
- Title: PROV-Overview — An Overview of the PROV Family of Documents.
- Editors/organization: Paul Groth and Luc Moreau; W3C Provenance Working Group.
- Year/venue: 2013-04-30, W3C Working Group Note.
- URL: https://www.w3.org/TR/prov-overview/
- Type/review status: official non-normative standards-family overview; Working Group Note, not itself a W3C Recommendation or academic peer-reviewed result.
- Finding: provenance describes entities, activities and agents and supports representation of attribution, derivation, versioning and provenance of provenance.
- Limitation: representing provenance cannot prove the truth or completeness of an asserted custody/contamination history.
- Relevance: a new manifest namespace or matching digest cannot, by itself, repair BOT 2.0's unresolved scientific-source authority.

## Independence, safety and freeze attestation

I read the current user instruction attachment and the mandatory audit. I did not read the old R16–R19 reports, any new R16/R17/R18 report, any master synthesis, or frozen R1–R15. The existing R19 draft was preserved using a byte copy without text inspection; both original and preservation copy matched SHA-256 `E702BC49C9AE455BC4F344990DBD98F77F6ACCAC65C34A1A6528C30223B73702` before replacement. The preservation copy is `R19_PRE_BATCH2_COORDINATOR_DRAFT.md`; it is not evidence for these conclusions.

Research-document writes were limited to that preservation copy and this report under `docs/bot21_research/`. No source/configuration/data/model/manifest/risk/execution/paper/ledger/protected output was modified or inspected directly. No protected OOS or protected scoring, training, inference, tests, experiments, backtests, trading, broker connections, package installation, environment/CUDA/driver changes, Git mutation, adapter creation, or BOT 2.1 implementation occurred. Web research visited public documentation only. No subagent was spawned by R19.

Completion is an independent conceptual first-pass completion, not a certification of operational safety or readiness. The report is frozen on final save. Its SHA-256 is computed externally after saving and returned in the specialist handoff, avoiding a self-referential embedded digest. No source registry or other report was modified by R19. R20 and X1–X8 remain unauthorized and unstarted.
