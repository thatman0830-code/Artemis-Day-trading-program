"""BOT 2.0 Phase 4 causal market-regime research plane."""
from .contracts import RegimeConfig, RegimeAssignment, RegimeSequence
from .assign import assign_regime, assign_sequence
from .analytics import duration_statistics, transition_matrix, conditional_outcomes, cross_market_relationship

__all__ = ["RegimeConfig", "RegimeAssignment", "RegimeSequence", "assign_regime", "assign_sequence",
           "duration_statistics", "transition_matrix", "conditional_outcomes", "cross_market_relationship"]
