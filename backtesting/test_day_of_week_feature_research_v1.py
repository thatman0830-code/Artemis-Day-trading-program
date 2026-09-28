from datetime import date
from decimal import Decimal

from backtesting.day_of_week_feature_research_v1 import CalendarSetup, extract_day_of_week_features
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.test_gap_feature_research_v1 import session


def test_first_session_of_week_records_prior_up_session_as_advisory_only():
    friday = session(date(2026, 1, 9), opening=Decimal("100"), high=Decimal("102"), low=Decimal("99"))
    # The shared fixture closes at its opening, so replace the final candle with
    # a valid higher close while retaining immutable identity coordinates.
    last = friday[-1]
    friday = friday[:-1] + (type(last)(
        last.id, last.dataset_id, last.schema_version, last.source, last.exchange,
        last.symbol, last.timeframe, last.open_time, last.close_time,
        Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"),
        last.volume, True),)
    monday = session(date(2026, 1, 12), opening=Decimal("101"), high=Decimal("103"), low=Decimal("100"))
    result = extract_day_of_week_features(friday + monday, market=FuturesCanonicalMarket.ES)[1]
    assert result.crossed_iso_week is True
    assert result.calendar_setup is CalendarSetup.LONG_OBSERVATION
    assert result.directional_signal_permitted is False
    assert result.trading_authority is False


def test_midweek_session_has_no_calendar_setup():
    monday = session(date(2026, 1, 12))
    tuesday = session(date(2026, 1, 13))
    result = extract_day_of_week_features(monday + tuesday, market=FuturesCanonicalMarket.ES)[1]
    assert result.calendar_setup is CalendarSetup.NONE
    assert result.reason_codes == ("SAME_ISO_WEEK",)


def test_incomplete_session_is_explicit_failure():
    friday = session(date(2026, 1, 9))
    monday = session(date(2026, 1, 12))[:-1]
    result = extract_day_of_week_features(friday + monday, market=FuturesCanonicalMarket.ES)[1]
    assert result.calendar_setup is CalendarSetup.DATA_QUALITY_FAILURE
    assert "INCOMPLETE_CURRENT_RTH_SESSION" in result.reason_codes
