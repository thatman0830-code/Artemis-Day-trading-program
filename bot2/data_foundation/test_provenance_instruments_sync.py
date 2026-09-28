from datetime import datetime, timedelta, timezone
import pytest

from .contracts import MarketEvent
from .instruments import normalize_contract
from .sync import synchronize_contract_roots
from .validation import DataQualityError, validate_events

UTC = timezone.utc
T0 = datetime(2026, 6, 1, 14, 30, tzinfo=UTC)


def historical(symbol, minute=0, price=5000, session="2026-06-01", contract_id="cid"):
    stamp = T0 + timedelta(minutes=minute)
    return MarketEvent(symbol, "CME", "BAR_CLOSE", stamp, None, price, 1,
        event_id=contract_id, session_id=session, timestamp_source="HISTORICAL_EXCHANGE_EVENT")


def test_historical_event_clock_is_valid_but_receipt_latency_unavailable():
    event = historical("ESM6")
    rows, quality = validate_events([event], as_of=T0 + timedelta(minutes=1), max_age=timedelta(minutes=2))
    assert rows[0].event_timestamp == T0 and rows[0].receive_timestamp is None
    assert rows[0].receive_timestamp_available is False
    assert quality.max_latency_seconds is None


def test_historical_records_cannot_claim_a_receive_clock():
    with pytest.raises(ValueError, match="historical exchange-only"):
        MarketEvent("ESM6", "CME", "BAR_CLOSE", T0, T0, 5000, 1,
            timestamp_source="HISTORICAL_EXCHANGE_EVENT")
    with pytest.raises(ValueError, match="availability must match"):
        MarketEvent("ESM6", "CME", "BAR_CLOSE", T0, None, 5000, 1,
            receive_timestamp_available=True)


def test_live_capture_preserves_genuine_distinct_event_and_receipt_times():
    live = MarketEvent("ESM6", "CME", "TRADE", T0, T0 + timedelta(milliseconds=8), 5000, 1,
                       timestamp_source="LIVE_PROVIDER_CAPTURE")
    _, quality = validate_events([live], as_of=T0 + timedelta(seconds=1))
    assert live.receive_timestamp_available and quality.max_latency_seconds == pytest.approx(.008)


@pytest.mark.parametrize("ticker,root,expiry", [("ESM5", "ES", "2025-06"), ("NQU6", "NQ", "2026-09")])
def test_canonical_contract_identity_retains_root_symbol_and_expiry(ticker, root, expiry):
    identity = normalize_contract(ticker, "full-source-contract-id", reference_date=datetime.fromisoformat(expiry + "-15").date())
    assert (identity.root_symbol, identity.contract_symbol, identity.expiry, identity.venue,
            identity.instrument_id) == (root, ticker, expiry, "CME", "full-source-contract-id")


def test_root_sync_exact_pairs_without_forward_fill_across_expiries():
    es = [historical("ESU6", 0, contract_id="esu6-id"), historical("ESU6", 1, contract_id="esu6-id")]
    nq = [historical("NQZ6", 0, 20000, contract_id="nqz6-id")]
    pairs, report = synchronize_contract_roots(es, nq)
    assert pairs == ((es[0], nq[0]),)
    assert report.exact_matches == 1 and report.es_unmatched == 1 and report.nq_unmatched == 0
    assert report.contract_expiry_mismatch_pairs == 1 and report.no_forward_fill


def test_root_sync_rejects_duplicate_exact_observation():
    row = historical("ESU6")
    with pytest.raises(ValueError, match="duplicate root"):
        synchronize_contract_roots([row, row], [historical("NQU6")])
