from backtesting.provider_neutral_coverage_v1 import audit_coverage, coverage_document


def test_coverage_gate_distinguishes_no_signals_from_covered():
    rows = audit_coverage(
        configured_days=("2026-09-04", "2026-09-07"),
        feed_bars={"2026-09-04": {"ES": 10, "NQ": 10}, "2026-09-07": {"ES": 10, "NQ": 10}},
        signal_counts={"2026-09-04": {"ES": 0, "NQ": 0}, "2026-09-07": {"ES": 1, "NQ": 0}},
        completed_by_day={"2026-09-07": 1},
    )
    assert rows[0].status == "NO_SIGNALS"
    assert rows[1].status == "COVERED"
    document = coverage_document(evaluated_at="2026-09-15T00:00:00+00:00",
                                 configured_days=("2026-09-04", "2026-09-07"), rows=rows)
    assert document["covered_days"] == 2
    assert document["missing_or_unqualified_days"] == []


def test_coverage_marks_signal_that_enters_next_session():
    rows = audit_coverage(
        configured_days=("2026-09-08",),
        feed_bars={"2026-09-08": {"ES": 10, "NQ": 10}},
        signal_counts={"2026-09-08": {"ES": 0, "NQ": 1}},
        completed_by_day={"2026-09-09": 1},
        completed_by_signal_day={"2026-09-08": 1},
    )
    assert rows[0].status == "COVERED_NEXT_ENTRY_SESSION"
