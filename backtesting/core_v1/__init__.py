"""Provider-neutral, offline-only deterministic Backtesting Engine Core v1."""
from .adapters import ActiveContractWindow, BTCArchiveAdapter, ESArchiveAdapter, NQArchiveAdapter, VerifiedArchiveSlice
from .capabilities import CapabilityIssue, CapabilityReport, EngineCapabilities, validate_capabilities
from .engine import CalculationEngine, EngineRunConfiguration
from .models import *
from .splits import PartitionRole, SplitPlan, TimePartition, build_split_plan
from .strategy import DeterministicFixtureStrategy, NoOpStrategy, Strategy
from .production_adapters import (
    AdapterMetadata, ArchiveEligibility, BTCPhase7PartialAdapter, CoreMarketDataEvent,
    DataQualityEvent, EligibilityFlags, PassBV3ArchiveAdapter, SourceLineage,
)

__all__ = (
    "ActiveContractWindow", "BTCArchiveAdapter", "ESArchiveAdapter", "NQArchiveAdapter",
    "VerifiedArchiveSlice", "CapabilityIssue", "CapabilityReport", "EngineCapabilities",
    "validate_capabilities", "CalculationEngine", "EngineRunConfiguration", "PartitionRole",
    "SplitPlan", "TimePartition", "build_split_plan", "DeterministicFixtureStrategy",
    "NoOpStrategy", "Strategy",
    "AdapterMetadata", "ArchiveEligibility", "BTCPhase7PartialAdapter",
    "CoreMarketDataEvent", "DataQualityEvent", "EligibilityFlags",
    "PassBV3ArchiveAdapter", "SourceLineage",
)
