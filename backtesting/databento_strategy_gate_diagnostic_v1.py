"""Read-only attribution of the first canonical gate preventing setup creation."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

VERSION = "databento-strategy-gate-diagnostic-v1"


@dataclass(frozen=True)
class StrategyGateDiagnosticV1:
    first_blocking_gate: str
    batch_count: int
    non_no_setup_count: int
    classification_ready_count: int
    displacement_evaluation_count: int
    qualified_displacement_count: int
    structural_break_qualification_count: int
    conflict_resolution_count: int
    accepted_conflict_count: int
    accepted_five_minute_conflict_count: int
    displacement_outcomes: tuple[tuple[str, int], ...]
    displacement_reasons: tuple[tuple[str, int], ...]
    qualified_displacement_timeframes: tuple[tuple[str, int], ...]
    conflict_timeframes: tuple[tuple[str, int], ...]
    setup_outcomes: tuple[tuple[str, int], ...]
    setup_reasons: tuple[tuple[str, int], ...]
    missing_prerequisites: tuple[tuple[str, int], ...]
    active_range_available_count: int
    active_ote_available_count: int
    target_available_count: int
    confluence_available_count: int
    phase_a_evaluation_count: int
    phase_a_eligible_count: int
    entry_zone_selection_count: int
    entry_zone_selected_count: int
    stop_selection_count: int
    stop_selected_count: int
    finalization_count: int
    armed_count: int
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


def diagnose_strategy_gates(state) -> StrategyGateDiagnosticV1:
    outcomes = Counter(); reasons = Counter(); qualified_frames = Counter(); conflict_frames = Counter()
    setup_outcomes = Counter(); setup_reasons = Counter(); missing = Counter()
    ready = displacement = qualified = breaks = conflicts = accepted = accepted_5m = non_no = 0
    active_range = active_ote = target = confluence = phase_a = phase_a_eligible = 0
    entry_selection = entry_selected = stop_selection = stop_selected = finalization = armed = 0
    for batch in state.batch_results:
        setup_outcomes[batch.outcome.value] += 1
        if batch.setup_fact.canonical_reason:
            setup_reasons[batch.setup_fact.canonical_reason] += 1
        for item in batch.trace.missing_prerequisites:
            missing[item.prerequisite] += 1
        if batch.outcome.value != "NO_SETUP":
            non_no += 1
        if batch.outcome.value in {"ARMED_CONTINUATION", "ENTRY_ZONE_ARMED_REVERSAL"}:
            armed += 1
        for trace in batch.trace.primitive_results:
            entry = trace.entry_point
            if entry.endswith("StructuralStateProducer.ingest") and trace.canonical_reason != "INITIALIZING":
                ready += 1
            elif entry.endswith("DisplacementQualificationProducer.evaluate"):
                displacement += 1
                outcome = trace.canonical_state or "UNKNOWN"
                outcomes[outcome] += 1
                if outcome == "QUALIFIED":
                    qualified += 1
                    qualified_frames[trace.result.timeframe] += 1
                if trace.canonical_reason:
                    reasons[trace.canonical_reason] += 1
            elif entry.endswith("StructuralBreakQualifier.qualify"):
                breaks += 1
            elif entry.endswith("ConflictResolver.resolve"):
                conflicts += 1
                conflict_frames[trace.result.timeframe] += 1
                accepted_here = len(trace.result.accepted_events)
                accepted += accepted_here
                if trace.result.timeframe.lower() == "5m":
                    accepted_5m += accepted_here
            elif entry.endswith("ActiveDealingRangeEngine.update"):
                active_range += int(getattr(trace.result, "active_range", None) is not None)
            elif entry.endswith("OTEEngine.update"):
                active_ote += int(getattr(trace.result, "active_ote", None) is not None)
            elif entry.endswith("LRLSelectionEngine.select"):
                target += int(getattr(trace.result, "active_lrl", None) is not None)
            elif entry.endswith("ConfluenceEngine.evaluate_ote"):
                confluence += int(getattr(trace.result, "confluence", None) is not None)
            elif entry.endswith("SetupQualificationEngine.qualify_continuation") or entry.endswith("SetupQualificationEngine.qualify_reversal_1"):
                phase_a += 1
                phase_a_eligible += int(getattr(trace.result, "eligible_for_entry_zone_selection", False) is True)
            elif entry.endswith("EntryZoneSelectionEngine.select"):
                entry_selection += 1
                entry_selected += int(getattr(trace.result, "selected_zone_id", None) is not None)
            elif entry.endswith("StopLossSelectionEngine.select"):
                stop_selection += 1
                stop_selected += int(getattr(trace.result, "stop", None) is not None)
            elif entry.endswith("SetupQualificationEngine.finalize"):
                finalization += 1
    if ready == 0:
        gate = "STRUCTURE_CLASSIFICATION_READINESS"
    elif qualified == 0:
        gate = "DISPLACEMENT_QUALIFICATION"
    elif breaks == 0:
        gate = "STRUCTURAL_BREAK_QUALIFICATION"
    elif conflicts == 0:
        gate = "CONFLICT_RESOLUTION_OR_SAME_BATCH_ELIGIBILITY"
    elif accepted == 0:
        gate = "STRUCTURAL_EVENT_ACCEPTANCE"
    elif accepted_5m == 0:
        gate = "FIVE_MINUTE_EVENT_REQUIREMENT"
    elif non_no == 0:
        gate = "SETUP_REQUEST_CREATION"
    elif active_range == 0:
        gate = "ACTIVE_DEALING_RANGE"
    elif target == 0:
        gate = "TARGET_LIQUIDITY_SELECTION"
    elif phase_a == 0 or phase_a_eligible == 0:
        gate = "PHASE_A_PREREQUISITES"
    elif entry_selected == 0:
        gate = "ENTRY_ZONE_SELECTION"
    elif stop_selected == 0:
        gate = "STOP_SELECTION"
    elif armed == 0:
        gate = "FINAL_RISK_REWARD_QUALIFICATION"
    else:
        gate = "ARMED_SETUP_AVAILABLE"
    return StrategyGateDiagnosticV1(
        first_blocking_gate=gate, batch_count=len(state.batch_results),
        non_no_setup_count=non_no, classification_ready_count=ready,
        displacement_evaluation_count=displacement, qualified_displacement_count=qualified,
        structural_break_qualification_count=breaks, conflict_resolution_count=conflicts,
        accepted_conflict_count=accepted, accepted_five_minute_conflict_count=accepted_5m,
        displacement_outcomes=tuple(sorted(outcomes.items())),
        displacement_reasons=tuple(sorted(reasons.items())),
        qualified_displacement_timeframes=tuple(sorted(qualified_frames.items())),
        conflict_timeframes=tuple(sorted(conflict_frames.items())),
        setup_outcomes=tuple(sorted(setup_outcomes.items())),
        setup_reasons=tuple(sorted(setup_reasons.items())),
        missing_prerequisites=tuple(sorted(missing.items())),
        active_range_available_count=active_range, active_ote_available_count=active_ote,
        target_available_count=target, confluence_available_count=confluence,
        phase_a_evaluation_count=phase_a, phase_a_eligible_count=phase_a_eligible,
        entry_zone_selection_count=entry_selection, entry_zone_selected_count=entry_selected,
        stop_selection_count=stop_selection, stop_selected_count=stop_selected,
        finalization_count=finalization, armed_count=armed,
    )
