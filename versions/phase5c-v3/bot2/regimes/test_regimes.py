from datetime import datetime, timedelta, timezone
import pytest
from bot2.data_foundation.contracts import MarketEvent
from bot2.features_labels.features import generate_features
from .assign import assign_regime, assign_sequence
from .analytics import conditional_outcomes, duration_statistics, transition_matrix, cross_market_relationship

UTC = timezone.utc


def events(instrument="ES", prices=(100, 101, 102, 103, 103, 103, 102, 101, 100), session="S1"):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [MarketEvent(instrument, "CME", "trade", start + timedelta(minutes=i), start + timedelta(minutes=i, seconds=1), float(p), 10, session_id=session) for i, p in enumerate(prices)]


def feature_rows(): return generate_features({"ES": events()}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")


def test_known_fixture_assigns_causally_and_future_mutation_does_not_change_prefix():
    base = feature_rows(); changed = generate_features({"ES": events(prices=(100,101,102,103,103,103,999,101,100))}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    a = assign_sequence(base, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    b = assign_sequence(changed, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    assert [x.to_dict() for x in a.assignments[:6]] == [x.to_dict() for x in b.assignments[:6]]


def test_missing_data_is_uncertain_not_forced():
    assignment = assign_regime(feature_rows()[0], source_dataset_id="d", source_dataset_sha256="h")
    assert assignment.primary_state == "UNCERTAIN" and assignment.validity == "UNCERTAIN"


def test_duration_and_transition_calculations():
    sequence = assign_sequence(feature_rows(), source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    durations = duration_statistics(sequence.assignments); matrix = transition_matrix(sequence.assignments)
    assert durations and sum(value for source, row in matrix.items() for target, value in row.items() if source != target) == sequence.transition_count


def test_regime_assignment_is_deterministic():
    rows = feature_rows(); a = assign_sequence(rows, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    b = assign_sequence(rows, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    assert [x.to_dict() for x in a.assignments] == [x.to_dict() for x in b.assignments]


def test_cross_market_cutoff_integrity_and_no_lead_claim():
    es = assign_sequence(feature_rows(), source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    nq = assign_sequence(generate_features({"NQ": events("NQ", (200,201,202,203,203,203,202,201,200))}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c"), source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    result = cross_market_relationship({"ES": es.assignments, "NQ": nq.assignments})
    assert result["lag_direction_claim"] == "NOT_ESTABLISHED"


def test_conditional_outcomes_exclude_uncertain_and_invalid():
    sequence = assign_sequence(feature_rows(), source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    assert conditional_outcomes(sequence.assignments, ()) == {}
