from backtesting.tradersync_style_adherence_v1 import build_adherence_report


def test_report_is_fail_closed_without_taken_outcomes():
    report = build_adherence_report([
        {"decision_class": "SKIPPED", "lane": "BASELINE", "execution_quality": {"quality": "NO_ORDER"}},
        {"decision_class": "VETOED", "lane": "ADAPTIVE_COMPARISON", "execution_quality": {"quality": "VETOED_BEFORE_ORDER"}},
    ])
    assert report["metric_status"] == "INSUFFICIENT_REVIEWED_TAKEN_SAMPLE"
    assert report["what_if_status"] == "INSUFFICIENT_COMPLETED_OUTCOMES"
    assert report["plan_adherence_rate"] is None
    assert report["trading_authority"] is False


def test_report_scores_only_explicitly_reviewed_taken_rows():
    report = build_adherence_report([
        {"decision_class": "TAKEN", "lane": "BASELINE", "execution_quality": {"rule_adherence": True}, "outcome": "WIN"},
        {"decision_class": "TAKEN", "lane": "BASELINE", "execution_quality": {"rule_adherence": False}, "outcome": "LOSS"},
        {"decision_class": "TAKEN", "lane": "BASELINE", "execution_quality": {"rule_adherence": None}},
    ])
    assert report["metric_status"] == "READY"
    assert report["adherence_reviewed_count"] == 2
    assert report["plan_adherence_rate"] == 0.5
    assert report["what_if_outcome_count"] == 2
