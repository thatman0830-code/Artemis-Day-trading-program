"""Deterministic historical-simulation boundaries; no replay engine."""

from backtesting.adapter import TradingBrainMarketDataAdapter
from backtesting.accounting import (
    EquitySizingPolicy, EquitySnapshot, SimulatedEquityLedger,
    SimulatedEquityLedgerEngine,
)
from backtesting.analytics import (
    AnalyticsCheckpoint, AnalyticsConfiguration, AnalyticsReference,
    BacktestResult, CanonicalAnalyticsOrchestrator,
)
from backtesting.manifests import BacktestRunManifest, DatasetManifest, RuntimeFacts
from backtesting.market_data import (
    CanonicalTimeframe,
    Gap,
    GapPolicy,
    HistoricalCandle,
    HistoricalDataset,
    MultiTimeframeView,
    ValidationStatus,
    normalize_historical_candle,
    normalize_hyperliquid_candle,
    validate_dataset,
)
from backtesting.replay import (
    AvailabilitySnapshot, ClockSnapshot, DeterministicReplay, ReplayBatch,
    ReplayCheckpoint, ReplayEvent, ReplayPublication, ReplayState, VisibleStream,
)
from backtesting.orchestrator import (
    BatchEvaluationResult, ContinuationEvaluationRequest, EvaluationContext,
    EvaluationOutcome, EvaluationTrace, MissingPrerequisite,
    OrchestrationCheckpoint, OrchestrationCommit, OrchestrationState,
    PrimitiveResultReference, RequestEvaluationState, ReversalEvaluationRequest,
    SetupStateFact, TradingBrainEvaluationOrchestrator,
)
from backtesting.simulation import (
    HistoricalTradeSimulator, LifecycleReference, SimulatedTrade,
    SimulationAccountInput, SimulationBatchResult, SimulationCheckpoint,
    SimulationCommit, SimulationInstrumentInput, SimulationMissingPrerequisite,
    TradeSimulationConfiguration, TradeSimulationState,
)
from backtesting.scientific_validation import (
    AntiOverfittingAssessment, BootstrapConfiguration, ChronologicalPartition,
    ConfidenceInterval, LockedStrategyConfiguration, MultipleTestingRecord,
    ParameterSensitivityObservation, ParameterSensitivityStudy, PartitionRole,
    RegimeKind, RegimeLabelFact, ScientificValidationEngine,
    ScientificValidationHistory, ScientificValidationSnapshot, ValidationOutcome,
    ValidationPlan, ValidationTradeFact, WalkForwardFold, WalkForwardFoldResult,
    bootstrap_intervals,
)
from backtesting.futures_canonical_lane_v1 import (
    FuturesCanonicalLaneV1, FuturesCanonicalMarket,
    admit_futures_canonical_lane, assert_distinct_futures_lanes,
)
from backtesting.futures_canonical_evaluation_v1 import (
    FuturesCanonicalEvaluationError, FuturesCanonicalEvaluationV1,
    assert_distinct_futures_evaluations, evaluate_futures_canonical_lane,
)
from backtesting.futures_canonical_history_v1 import (
    FuturesCanonicalHistoryError, FuturesCanonicalHistoryEventV1,
    append_futures_canonical_evaluation, read_futures_canonical_history,
)
from backtesting.futures_canonical_attribution_v1 import (
    FuturesCanonicalAttributionError, FuturesCanonicalAttributionV1,
    assert_distinct_futures_attributions, evaluate_futures_canonical_attribution,
    write_futures_canonical_attribution,
)

__all__ = (
    "BacktestRunManifest", "CanonicalTimeframe", "DatasetManifest", "Gap",
    "GapPolicy", "HistoricalCandle", "HistoricalDataset", "MultiTimeframeView",
    "RuntimeFacts", "TradingBrainMarketDataAdapter", "ValidationStatus",
    "normalize_historical_candle", "normalize_hyperliquid_candle", "validate_dataset",
    "AvailabilitySnapshot", "ClockSnapshot", "DeterministicReplay", "ReplayBatch",
    "ReplayCheckpoint", "ReplayEvent", "ReplayPublication", "ReplayState", "VisibleStream",
    "BatchEvaluationResult", "ContinuationEvaluationRequest", "EvaluationContext",
    "EvaluationOutcome", "EvaluationTrace", "MissingPrerequisite",
    "OrchestrationCheckpoint", "OrchestrationCommit", "OrchestrationState",
    "PrimitiveResultReference", "RequestEvaluationState", "ReversalEvaluationRequest",
    "SetupStateFact", "TradingBrainEvaluationOrchestrator",
    "HistoricalTradeSimulator", "LifecycleReference", "SimulatedTrade",
    "SimulationAccountInput", "SimulationBatchResult", "SimulationCheckpoint",
    "SimulationCommit", "SimulationInstrumentInput", "SimulationMissingPrerequisite",
    "TradeSimulationConfiguration", "TradeSimulationState",
    "EquitySizingPolicy", "EquitySnapshot", "SimulatedEquityLedger",
    "SimulatedEquityLedgerEngine",
    "AnalyticsCheckpoint", "AnalyticsConfiguration", "AnalyticsReference",
    "BacktestResult", "CanonicalAnalyticsOrchestrator",
    "AntiOverfittingAssessment", "BootstrapConfiguration",
    "ChronologicalPartition", "ConfidenceInterval", "LockedStrategyConfiguration",
    "MultipleTestingRecord", "ParameterSensitivityObservation",
    "ParameterSensitivityStudy", "PartitionRole", "RegimeKind", "RegimeLabelFact",
    "ScientificValidationEngine", "ScientificValidationHistory",
    "ScientificValidationSnapshot", "ValidationOutcome", "ValidationPlan",
    "ValidationTradeFact", "WalkForwardFold", "WalkForwardFoldResult",
    "bootstrap_intervals",
    "FuturesCanonicalLaneV1", "FuturesCanonicalMarket",
    "admit_futures_canonical_lane", "assert_distinct_futures_lanes",
    "FuturesCanonicalEvaluationError", "FuturesCanonicalEvaluationV1",
    "assert_distinct_futures_evaluations", "evaluate_futures_canonical_lane",
    "FuturesCanonicalHistoryError", "FuturesCanonicalHistoryEventV1",
    "append_futures_canonical_evaluation", "read_futures_canonical_history",
    "FuturesCanonicalAttributionError", "FuturesCanonicalAttributionV1",
    "assert_distinct_futures_attributions", "evaluate_futures_canonical_attribution",
    "write_futures_canonical_attribution",
)

BACKTESTING_CONTRACT_VERSION = "backtesting-phase5b-v1"
SCIENTIFIC_VALIDATION_CONTRACT_VERSION = "btc-scientific-validation-v1"
