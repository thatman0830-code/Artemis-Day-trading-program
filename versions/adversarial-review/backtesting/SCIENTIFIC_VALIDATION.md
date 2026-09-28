# BTC Scientific Validation Contract

Status: advisory research infrastructure only. This contract cannot authorize
trading or change strategy, risk, sizing, orders, execution, or accounts.

## Locked protocol

`LockedStrategyConfiguration` freezes the Trading Brain contract, strategy and
model configurations, owner risk-to-reward policy, modeled execution-cost
configuration, BTC dataset identity/fingerprint, and source/calculation
versions before evaluation. Version 1 rejects non-BTC scope.

`ValidationPlan` owns exactly three contiguous UTC half-open partitions in
chronological order: `TRAIN`, `VALIDATION`, and the final untouched `TEST`.
The plan must be created no later than the training boundary. Immutable
`WalkForwardFold` definitions may use only pre-test history and must train
strictly before their validation interval. `WalkForwardFoldResult` preserves
the disjoint trade lineage and finalized metric for every fold.

Final evaluation includes a trade only when its canonical close time lies in
the locked `[TEST.start, TEST.end)` interval. The complete test interval must
have closed by `as_of`. Future, duplicated, mutable, incomplete, incorrectly
ordered, out-of-scope, or version-mismatched facts fail closed.

## Inputs and advisory records

- `ValidationTradeFact` is a one-way research projection of immutable canonical
  #29.7.1 accounting. It preserves canonical WIN/LOSS/BREAKEVEN, net PnL,
  net R, close time, and source identities. Planned R:R is an explicit frozen
  upstream setup fact; it is never inferred from accounting.
- `RegimeLabelFact` is descriptive only, becomes available no earlier than its
  source interval close, and does not enter the owner objective formula.
- `ParameterSensitivityStudy` requires the owner baseline plus observations on
  both sides. It is restricted to pre-test observations and cannot apply a
  parameter automatically.
- `MultipleTestingRecord` records the complete hypothesis family and an exact
  Decimal Bonferroni threshold.
- `AntiOverfittingAssessment` records finalized walk-forward degradation against
  an explicitly locked research bound. It does not modify the owner objective
  or strategy.
- `BootstrapConfiguration` produces deterministic 95% percentile intervals for
  win rate, net expectancy, and mean net R with a recorded seed and resample
  count. Economic inputs and outputs use exact `Decimal`; floats are rejected.

## Owner objective

`ScientificValidationEngine` evaluates only finalized out-of-sample BTC test
trades and emits one immutable point-in-time snapshot:

- fewer than 200 trades: `INSUFFICIENT_EVIDENCE`;
- otherwise any of win rate below 0.60, net expectancy after modeled costs not
  positive, or any planned R:R below 1.0: `FAIL`;
- all four requirements satisfied: `PASS`.

The snapshot always has `advisory_only=True`,
`trading_authorized=False`, and `strategy_modified=False`. Neither a `PASS`
nor any confidence interval permits live/testnet execution or production use.

## Assumptions and limits

Version 1 uses trade-level deterministic percentile bootstrap resampling. It
does not model serial dependence; block bootstrap or another predeclared method
may be added later under a new validation version when sufficient BTC history
exists. Regime labels are accepted only as precomputed descriptive facts;
regime construction is not owned here. Parameter candidates and degradation
bounds must be owner-authored before the untouched test is evaluated. No ES/NQ,
portfolio aggregation, optimization, automatic selection, internet access, or
archive mutation is part of this contract.
