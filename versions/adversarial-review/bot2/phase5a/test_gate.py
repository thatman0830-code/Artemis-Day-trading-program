import json
from pathlib import Path

from .gate import phase5a_blockers


def _manifest():
    path = Path(__file__).resolve().parents[2] / "config" / "bot2_phase5a_experiment_manifest_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_archive_gaps_fail_closed_for_supervised_claims():
    reasons = phase5a_blockers(manifest=_manifest(), source_has_receipt_timestamps=False,
        independent_targets_available=False, synchronized_cross_market_coverage=0.0)
    assert reasons == ("SOURCE_RECEIPT_TIMESTAMP_UNAVAILABLE",
                       "TARGET_SELF_LABEL_IMITATION", "CROSS_MARKET_FEATURE_COVERAGE_UNAVAILABLE")


def test_gate_allows_evaluation_only_when_independent_inputs_are_supplied():
    assert phase5a_blockers(manifest=_manifest(), source_has_receipt_timestamps=True,
        independent_targets_available=True, synchronized_cross_market_coverage=0.99) == ()
