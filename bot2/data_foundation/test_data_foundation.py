from datetime import datetime, timedelta, timezone
import pytest

from bot2.data_foundation import MarketEvent, build_manifest, deterministic_replay, synchronize_es_nq, validate_events
from bot2.data_foundation.validation import DataQualityError

UTC = timezone.utc
T0 = datetime(2026, 1, 2, 14, 30, tzinfo=UTC)


def event(symbol="ESZ6", seconds=0, price=5000.0, volume=1, sequence=None):
    stamp = T0 + timedelta(seconds=seconds)
    return MarketEvent(symbol, "CME", "TRADE", stamp, stamp + timedelta(milliseconds=2), price, volume, sequence=sequence)


def test_valid_events_and_manifest_are_reproducible():
    rows, report = validate_events([event(seconds=0, sequence=1), event(seconds=1, price=5001, sequence=2)], as_of=T0 + timedelta(seconds=2))
    first = build_manifest(dataset_id="d1", source="fixture", events=rows, quality_report=report, schema_version="bot2-normalized-v1", configuration={"x": 1}, code_commit="abc")
    second = build_manifest(dataset_id="d1", source="fixture", events=rows, quality_report=report, schema_version="bot2-normalized-v1", configuration={"x": 1}, code_commit="abc")
    assert first.to_dict() == second.to_dict()


def test_duplicate_and_regression_fail_closed():
    with pytest.raises(DataQualityError) as exc:
        validate_events([event(seconds=1, sequence=2), event(seconds=1, sequence=2), event(seconds=0, sequence=1)], as_of=T0 + timedelta(seconds=2))
    assert "DUPLICATE_EVENT" in exc.value.report.reasons
    assert "TIMESTAMP_REGRESSION" in exc.value.report.reasons


@pytest.mark.parametrize("bad", [event(price=0), event(volume=-1)])
def test_invalid_price_or_volume_fails_closed(bad):
    with pytest.raises(DataQualityError):
        validate_events([bad], as_of=T0 + timedelta(seconds=1))


def test_stale_and_sequence_gap_are_machine_readable():
    with pytest.raises(DataQualityError) as exc:
        validate_events([event(seconds=0, sequence=1), event(seconds=2, sequence=3)], as_of=T0 + timedelta(seconds=10), max_age=timedelta(seconds=5), expected_interval=timedelta(seconds=1), require_contiguous_sequence=True)
    assert {"STALE_EVENT", "INTERVAL_GAP", "SEQUENCE_GAP"}.issubset(exc.value.report.reasons)


def test_cross_market_sync_is_deterministic_and_no_forward_fill():
    es = (event("ESZ6", 0), event("ESZ6", 1))
    nq = (event("NQZ6", 0, 20000), event("NQZ6", 1, 20001))
    assert synchronize_es_nq(es, nq, max_skew=timedelta(milliseconds=1)) == tuple(zip(es, nq))
    with pytest.raises(DataQualityError):
        synchronize_es_nq(es, (event("NQZ6", 10, 20000),), max_skew=timedelta(milliseconds=1))


def test_replay_excludes_future_information_and_is_identical():
    rows = [event(seconds=0), event(seconds=1), event(seconds=2)]
    first = deterministic_replay(rows, cutoff=T0 + timedelta(seconds=1))
    second = deterministic_replay(rows, cutoff=T0 + timedelta(seconds=1))
    assert first == second
    assert first["event_count"] == 2
    assert first["future_events_excluded"] == 1


def test_receipt_before_exchange_is_rejected():
    stamp = event()
    bad = MarketEvent(stamp.instrument, stamp.venue, stamp.event_type, stamp.exchange_time,
                      stamp.exchange_time - timedelta(seconds=1), stamp.price, stamp.volume)
    with pytest.raises(DataQualityError):
        validate_events([bad], as_of=T0 + timedelta(seconds=1))
