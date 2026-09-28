from datetime import datetime, timedelta, timezone

from .cadence import audit_cadence, is_contiguous_window
from .contracts import MarketEvent

UTC=timezone.utc
T0=datetime(2026,1,5,14,30,tzinfo=UTC)


def event(symbol, minute, *, session="S1", contract=None):
    timestamp=T0+timedelta(minutes=minute)
    return MarketEvent(symbol,"CME","BAR",timestamp,None,100+minute,1,event_id=f"{symbol}-{minute}",
        session_id=session,contract_id=contract or f"{symbol}M6",timestamp_source="HISTORICAL_EXCHANGE_EVENT")


def test_gap_audit_counts_missing_minutes_without_bridging_session_or_contract_boundary():
    rows=[event("ESM6",0),event("ESM6",1),event("ESM6",3),event("ESU6",4,contract="ESU6"),event("ESU6",5,session="S2",contract="ESU6")]
    report=audit_cadence(rows)
    assert report.observation_count==5
    assert report.checked_adjacent_pairs==2
    assert report.cadence_valid_pairs==1
    assert report.gap_count==1 and report.missing_interval_count==1
    assert report.gap_size_distribution=={"1":1}
    assert report.sessions_affected==1
    assert report.gaps[0].reason_code=="MISSING_INTERVALS"


def test_irregular_interval_is_distinct_from_exact_missing_minute():
    rows=[event("ESM6",0,contract="ESM6"), MarketEvent("ESM6","CME","BAR",T0+timedelta(seconds=90),None,101,1,
        session_id="S1",contract_id="ESM6",timestamp_source="HISTORICAL_EXCHANGE_EVENT")]
    report=audit_cadence(rows)
    assert report.gaps[0].actual_elapsed_seconds==90
    assert report.gaps[0].cadence_valid is False
    assert report.gaps[0].reason_code=="CADENCE_VIOLATION"
    assert report.gaps[0].missing_interval_count==1


def test_contiguous_window_uses_elapsed_time_not_row_adjacency():
    assert is_contiguous_window([T0,T0+timedelta(minutes=1),T0+timedelta(minutes=2)])
    assert not is_contiguous_window([T0,T0+timedelta(minutes=2),T0+timedelta(minutes=3)])


def test_archived_calendar_closure_is_not_misclassified_as_missing_data():
    rows=[event("ESM6",1,contract="ESM6"),event("ESM6",2,contract="ESM6"),
          event("ESM6",8,contract="ESM6"),event("ESM6",9,contract="ESM6")]
    intervals={"S1":((T0,T0+timedelta(minutes=2)),
                      (T0+timedelta(minutes=7),T0+timedelta(minutes=10)))}
    report=audit_cadence(rows,active_intervals=intervals)
    assert report.checked_adjacent_pairs==2
    assert report.cadence_valid_pairs==2
    assert report.gap_count==0 and report.missing_interval_count==0
    assert report.excluded_calendar_boundary_pairs==1
