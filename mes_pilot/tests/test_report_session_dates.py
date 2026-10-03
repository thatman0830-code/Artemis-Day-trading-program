from mes_pilot.report import collapse_session_dates


def row(day, classification="TRADED", window_bars=1):
    return {"session_date": day, "classification": classification, "window_bars": window_bars}


def test_duplicate_restarts_count_one_eligible_date():
    result = collapse_session_dates([row("2026-09-01")] + [row("2026-09-28", window_bars=0) for _ in range(19)])
    assert result["summary_rows"] == 20
    assert result["trading_dates"] == 2
    assert result["eligible_count"] == 1
    assert result["eligible_span_days"] == 1


def test_three_healthy_summaries_same_date_count_once():
    result = collapse_session_dates([row("2026-09-10") for _ in range(3)])
    assert result["eligible_count"] == 1
    assert result["duplicate_summary_rows"] == 2


def test_restart_without_window_data_is_neutral():
    result = collapse_session_dates([row("2026-09-10"), row("2026-09-10", "NO_SESSION_DATA_IN_WINDOW", 0)])
    assert result["eligible_count"] == 1
    assert result["mixed_dates"] == []


def test_fault_and_healthy_run_same_date_is_ineligible_and_mixed():
    result = collapse_session_dates([row("2026-09-10"), row("2026-09-10", "OPERATIONAL_FAULT")])
    assert result["eligible_count"] == 0
    assert result["mixed_dates"] == ["2026-09-10"]


def test_ineligible_dates_do_not_stretch_eligible_calendar_span():
    result = collapse_session_dates([row("2026-09-01", "CALENDAR_UNAVAILABLE_OPERATIONAL_LIMITATION"),
                                     row("2026-09-28"), row("2026-09-29")])
    assert result["eligible_count"] == 2
    assert result["eligible_span_days"] == 2


def test_genuine_distinct_eligible_dates_keep_their_span():
    result = collapse_session_dates([row("2026-09-01"), row("2026-09-02"), row("2026-09-28")])
    assert result["eligible_count"] == 3
    assert result["eligible_span_days"] == 28
