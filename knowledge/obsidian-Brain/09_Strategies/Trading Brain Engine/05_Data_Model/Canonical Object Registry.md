---
title: Canonical Object Registry
type: data-model-registry
---

# Canonical Object Registry

One canonical schema per concept. No duplicate schema names. Status: `LOCKED`, `LOCKED_PENDING_REGISTRY` (owner-authorized, needs formal registry insertion), `CONFIGURATION_DEPENDENT`, `CONFLICTED` (none).

| Object | Owning primitive | Status |
|---|---|---|
| MechanicalSwing | [[#19 Mechanical Swing Selection]] | LOCKED |
| StructuralSwing | [[#20 Structural Classification]] | LOCKED |
| StructuralRange (ActiveDealingRange) | [[#21 Active Dealing Range]] | LOCKED |
| OTE | [[#22 OTE]] | LOCKED |
| LiquidityPool | [[#23 Liquidity — Sweeps]] | LOCKED |
| LiquiditySweep | [[#23 Liquidity — Sweeps]] | LOCKED |
| LRL | [[#24 LRL Selection]] | LOCKED |
| FVG | [[#25 FVG — IFVG]] | LOCKED |
| IFVG | [[#25 FVG — IFVG]] | LOCKED |
| Confluence | [[#26 Confluence]] | LOCKED |
| Setup | [[#27 Setup Qualification]] | LOCKED |
| CISDConfirmation | [[#11 CISD — 1M Confirmation]] | LOCKED |
| EntryZoneSelection | [[#28 Entry-Zone Selection]] | LOCKED |
| StopSelection | [[#13 Stop-Loss Selection]] | LOCKED |
| ExecutionEligibilityEvaluation | [[#29.0 Execution Eligibility]] | LOCKED |
| Trade | [[Execution Entity Hierarchy]] | LOCKED |
| Order | [[Execution Entity Hierarchy]] | LOCKED |
| Fill | [[Execution Entity Hierarchy]] | LOCKED |
| EntryOrder | [[#29.1 Entry Execution]] | LOCKED |
| PositionSizing | [[#29.2 Position Sizing]] | LOCKED |
| ProtectiveOrder | [[#29.3 Protective Orders]] | LOCKED |
| OCOGroup | [[#29.3 Protective Orders]] | LOCKED |
| ExecutionRecord | [[#29.4 Exit Resolution]] | LOCKED |
| ExecutionCostRecord | [[#29.5 Execution Costs]] | CONFIGURATION_DEPENDENT |
| Position | [[#29.6 Position Lifecycle]] | LOCKED |
| TradeAccounting | [[#29.7.1 Trade Accounting]] | LOCKED |
| ReturnStatistics | [[#29.7.2.2 Return Statistics]] | LOCKED |
| EquityPoint | [[#29.7.2.6 Equity Curve]] | LOCKED |
| Drawdown | [[#29.7.2.7 Drawdown]] | LOCKED |
| RecoveryEpisode / RecoveryStatistics | [[#29.7.2.12 Recovery]] | LOCKED |
| UnderwaterEpisode / UnderwaterState | [[#29.7.2.13 Underwater — Time Underwater]] | LOCKED |
| ResultRun | [[#29.7.2.14 Trade Sequence — Path]] | LOCKED |
| TradeSequenceSnapshot | [[#29.7.2.14 Trade Sequence — Path]] | LOCKED |
| StrategyPerformance | [[#29.7.2.15 Strategy-Level Aggregation]] | LOCKED |
| StrategyPeriodReturnObservation | [[#29.7.2.15 Strategy-Level Aggregation]] | LOCKED → [[StrategyPeriodReturnObservation]] |
| PortfolioDefinition | [[#29.7.2.16 Portfolio-Level Aggregation]] | LOCKED |
| PortfolioPerformance | [[#29.7.2.16 Portfolio-Level Aggregation]] | LOCKED |
| PortfolioAttribution | [[#29.7.2.17 Portfolio Attribution]] | LOCKED |
| StrategyContribution | [[#29.7.2.16 Portfolio-Level Aggregation]] | LOCKED |
| StrategyOverlap / StrategyPairOverlap | [[#29.7.2.18 Strategy Interaction — Overlap]] | LOCKED |
| StrategyCorrelation | [[#29.7.2.19 Strategy Return Correlation]] | LOCKED |
| StrategyCovariance / StrategyCovarianceMatrix | [[#29.7.2.20 Strategy Return Covariance]] | LOCKED |
| CandidateEvent | [[#16 Conflict Resolution — State Priority]] | LOCKED_PENDING_REGISTRY |
| ConflictResolution | [[#16 Conflict Resolution — State Priority]] | LOCKED_PENDING_REGISTRY |
| ErrorRecord | [[Canonical Error Registry]] | LOCKED |
| ExecutionQualityObservation | [[Execution Quality EOD Metrics]] | LOCKED |

Policies: [[Identity — Versioning Policy]] · [[Time — Period Policy]] · [[Precision — Rounding Policy]].
