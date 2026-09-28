"""Canonical numbered Trading Brain primitives.

These modules are intentionally isolated from the earlier strategy scaffold.
Downstream code should migrate only after its complete dependency chain exists.
"""

# Machine-readable contract freeze. Values are import paths, not eager imports,
# so importing this package cannot create a dependency cycle or side effect.
PUBLIC_ENGINE_ENTRY_POINTS = {
    "#19": ("p19_mechanical_swings.MechanicalSwingEngine.detect",),
    "#20": ("p20_structural_state_producer.StructuralStateProducer.ingest", "p20_displacement.DisplacementQualificationProducer.context", "p20_displacement.DisplacementQualificationProducer.evaluate", "p20_displacement.DisplacementQualificationProducer.invalidate", "p20_structural_classification.StructuralSwingSelector.select", "p20_structural_classification.StructuralBreakQualifier.qualify", "p20_state_commit.StructuralStateCommitter.commit"),
    "#16": ("p16_conflict_resolution.ConflictResolver.resolve", "p16_conflict_resolution.ConflictResolver.finalize"),
    "#21": ("p21_active_dealing_range.ActiveDealingRangeEngine.update",),
    "#22": ("p22_ote.OTEEngine.create", "p22_ote.OTEEngine.update"),
    "#23": ("p23_liquidity_reference_producer.StructuralLiquidityReferenceProducer.derive", "p23_liquidity_reference_producer.StructuralLiquidityReferenceProducer.consume", "p23_prior_period_references.PriorPeriodLiquidityReferenceProducer.evaluate", "p23_prior_period_references.PriorPeriodLiquidityReferenceProducer.consume", "p23_prior_period_references.PriorPeriodLiquidityReferenceProducer.invalidate", "p23_liquidity.LiquidityPoolEngine.build_inventory", "p23_liquidity.LiquidityInteractionEngine.evaluate"),
    "#24": ("p24_lrl_selection.LRLSelectionEngine.select",),
    "#25": ("p25_fvg_ifvg.FVGEngine.detect", "p25_fvg_ifvg.FVGEngine.interact"),
    "#26": ("p26_confluence.ConfluenceEngine.evaluate_ote", "p26_confluence.ConfluenceEngine.evaluate_lrl", "p26_confluence.ConfluenceEngine.evaluate_event", "p26_confluence.ConfluenceEngine.reconcile"),
    "#11": ("p11_delivery_leg_producer.ReversalDeliveryLegProducer.form", "p11_delivery_leg_producer.ReversalDeliveryLegProducer.invalidate", "p11_cisd_confirmation.CISDEngine.start", "p11_cisd_confirmation.CISDEngine.identify_reference", "p11_cisd_confirmation.CISDEngine.wait_for_body_close", "p11_cisd_confirmation.CISDEngine.evaluate", "p11_cisd_confirmation.CISDEngine.terminate", "p11_cisd_confirmation.CISDEngine.zone_is_temporally_eligible"),
    "#27": ("p27_setup_qualification.SetupQualificationEngine.qualify_continuation", "p27_setup_qualification.SetupQualificationEngine.qualify_reversal_1", "p27_setup_qualification.SetupQualificationEngine.finalize"),
    "OWNER_MIN_RR_V1": ("owner_policies.MinimumRiskRewardPolicyRegistry.resolve",),
    "OWNER_WIN_RATE_OBJECTIVE_V1": ("p29_7_2_owner_performance_readiness.PerformanceReadinessEngine.evaluate",),
    "#28": ("p28_entry_zone_selection.EntryZoneSelectionEngine.select", "p28_entry_zone_selection.EntryZoneSelectionEngine.invalidate_and_fallback"),
    "#13": ("p13_stop_loss_selection.StopLossSelectionEngine.select",),
    "#29.1": ("p29_1_entry_execution.EntryExecutionEngine.create_order", "p29_1_entry_execution.EntryExecutionEngine.activate_order", "p29_1_entry_execution.EntryExecutionEngine.cancel_order", "p29_1_entry_execution.EntryExecutionEngine.evaluate_candle"),
    "#29.2": ("p29_2_position_sizing.PositionSizingEngine.calculate",),
    "#29.3": ("p29_3_protective_orders.ProtectiveOrderEngine.create", "p29_3_protective_orders.ProtectiveOrderEngine.activate"),
    "#29.4": ("p29_4_exit_resolution.ExitResolutionEngine.evaluate",),
    "#29.5": ("p29_5_execution_costs.ExecutionCostEngine.calculate",),
    "#29.6": ("p29_6_position_lifecycle.PositionLifecycleEngine.availability", "p29_6_position_lifecycle.PositionLifecycleEngine.open_boundary", "p29_6_position_lifecycle.PositionLifecycleEngine.open", "p29_6_position_lifecycle.PositionLifecycleEngine.close"),
    "#29.7.1": ("p29_7_1_trade_accounting.TradeAccountingEngine.calculate",),
    **{f"#29.7.2.{number}": (entry,) for number, entry in {
        1: "p29_7_2_1_trade_classification_count.TradeClassificationCountEngine.calculate",
        2: "p29_7_2_2_return_statistics.ReturnStatisticsEngine.calculate",
        3: "p29_7_2_3_expectancy.ExpectancyEngine.calculate",
        4: "p29_7_2_4_profit_factor.ProfitFactorEngine.calculate",
        5: "p29_7_2_5_cumulative_pnl_r.CumulativePnLREngine.calculate",
        6: "p29_7_2_6_equity_curve.EquityCurveEngine.calculate",
        7: "p29_7_2_7_drawdown.DrawdownEngine.calculate",
        8: "p29_7_2_8_streak_statistics.StreakStatisticsEngine.calculate",
        9: "p29_7_2_9_period_statistics.PeriodStatisticsEngine.calculate",
        10: "p29_7_2_10_distribution_statistics.DistributionStatisticsEngine.calculate",
        11: "p29_7_2_11_risk_adjusted_statistics.RiskAdjustedStatisticsEngine.calculate",
        12: "p29_7_2_12_recovery.RecoveryStatisticsEngine.calculate",
        13: "p29_7_2_13_underwater.UnderwaterStatisticsEngine.calculate",
        14: "p29_7_2_14_trade_sequence.TradeSequenceEngine.calculate",
        15: "p29_7_2_15_strategy_aggregation.StrategyAggregationEngine.calculate",
        16: "p29_7_2_16_portfolio_aggregation.PortfolioAggregationEngine.calculate",
        17: "p29_7_2_17_portfolio_attribution.PortfolioAttributionEngine.calculate",
        18: "p29_7_2_18_strategy_overlap.StrategyOverlapEngine.calculate",
        19: "p29_7_2_19_strategy_correlation.StrategyCorrelationEngine.calculate",
        20: "p29_7_2_20_strategy_covariance.StrategyCovarianceEngine.calculate",
    }.items()},
}

FORBIDDEN_BACKTESTER_DEPENDENCIES = (
    "exchange", "execution.paper_engine", "risk", "database", "config",
    "private_key", "signing", "mainnet", "exchange_submission",
)

INTERFACE_CONTRACT_VERSION = "trading-brain-interface-v1"
