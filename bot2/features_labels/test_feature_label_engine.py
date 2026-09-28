from datetime import datetime, timedelta, timezone
import json

import pytest

from bot2.data_foundation.contracts import MarketEvent
from bot2.features_labels.contracts import (AMBIGUOUS_OUTCOME, INSUFFICIENT_FUTURE_DATA,
                                             SYNCHRONIZATION_UNAVAILABLE, FeatureConfig, LabelConfig)
from bot2.features_labels.features import generate_features
from bot2.features_labels.labels import generate_labels

UTC = timezone.utc


def events(instrument="ES", prices=(100, 101, 102, 103, 104, 105), session_id="S1", *, missing_minutes=()):
    start = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    rows = []
    for i, p in enumerate(prices):
        if i in missing_minutes:
            continue
        ts = start + timedelta(minutes=i)
        rows.append(MarketEvent(instrument, "CME", "trade", ts, ts + timedelta(milliseconds=1),
            float(p), 10 + i, session_id=session_id, contract_id=f"{instrument}M6"))
    return rows


def test_features_are_causal_under_future_mutation():
    base = generate_features({"ES": events()}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    changed = generate_features({"ES": events(prices=(100, 101, 102, 103, 999, 105))},
                                source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    for left, right in zip(base[:4], changed[:4]):
        assert left.values == right.values


def test_features_respect_cutoff_and_missing_history_is_explicit():
    rows = generate_features({"ES": events()}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    assert rows[0].values["log_return_1m"] is None
    assert "INSUFFICIENT_HISTORY" in rows[0].reason_codes
    assert all(r.cutoff_time == r.observation_time for r in rows)


def test_cross_market_future_cannot_leak_into_es():
    es = events("ES")
    nq = events("NQ", prices=(200, 201, 202, 203, 204, 205))
    altered = events("NQ", prices=(200, 201, 202, 203, 999, 205))
    a = generate_features({"ES": es, "NQ": nq}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    b = generate_features({"ES": es, "NQ": altered}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    assert a[2].values == b[2].values


def test_vwap_and_rolling_windows_are_past_only():
    rows = generate_features({"ES": events()}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    assert rows[2].values["session_vwap"] == pytest.approx((100*10 + 101*11 + 102*12) / 33)
    assert rows[3].values["rolling_price_range_3m"] == 3


def test_unavailable_cross_market_is_not_zero_filled():
    row = generate_features({"ES": events()}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")[1]
    assert row.values["cross_market_log_return_1m"] is None
    assert SYNCHRONIZATION_UNAVAILABLE in row.reason_codes


@pytest.mark.parametrize("missing_root", ["ES", "NQ"])
def test_either_market_missing_exact_minute_invalidates_pair_without_forward_fill(missing_root):
    es = events("ES", prices=tuple(range(100, 108)))
    nq = events("NQ", prices=tuple(range(200, 208)))
    source = {"ES": es, "NQ": nq}
    source[missing_root] = [row for index, row in enumerate(source[missing_root]) if index != 2]
    generated = generate_features(source, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    at_minute_3 = next(row for row in generated if row.instrument == "ES" and row.observation_time.endswith("14:33:00Z"))
    assert at_minute_3.values["cross_market_log_return_1m"] is None
    assert SYNCHRONIZATION_UNAVAILABLE in at_minute_3.reason_codes


def test_labels_use_future_and_are_separate_from_features():
    rows = generate_labels({"ES": events()}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    assert rows[0].uses_future_observations is True
    assert rows[0].validity == "VALID"
    assert rows[-1].validity == INSUFFICIENT_FUTURE_DATA


def test_ambiguous_barrier_is_quarantined():
    base = events(prices=(100, 100, 99, 100, 100, 100))
    rows = generate_labels({"ES": base}, source_dataset_id="d", source_dataset_sha256="h",
                           config=LabelConfig(horizons=(2,), favorable_barrier=0, adverse_barrier=0), code_commit="c")
    assert rows[0].validity == AMBIGUOUS_OUTCOME
    assert rows[0].forward_return is None


def test_generation_is_deterministic_and_serializable():
    a = generate_features({"ES": events()}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    b = generate_features({"ES": events()}, source_dataset_id="d", source_dataset_sha256="h", code_commit="c")
    assert [x.to_dict() for x in a] == [x.to_dict() for x in b]
    json.dumps([x.to_dict() for x in a], sort_keys=True)


def test_out_of_order_source_fails_closed():
    source = events()
    source[2], source[3] = source[3], source[2]
    with pytest.raises(ValueError):
        generate_features({"ES": source}, source_dataset_id="d", source_dataset_sha256="h")


def test_missing_minute_inside_elapsed_rolling_window_is_not_compressed():
    source = events(prices=tuple(range(100, 110)), missing_minutes=(4,))
    rows = generate_features({"ES": source}, source_dataset_id="d", source_dataset_sha256="h")
    at_minute_5 = rows[4]
    assert at_minute_5.values["rolling_price_range_3m"] is None
    assert "FEATURE_WINDOW_GAP" in at_minute_5.reason_codes


def test_elapsed_horizon_uses_exact_timestamp_not_row_offset():
    source = events(prices=(100, 101, 102, 103, 104, 105, 106), missing_minutes=(3,))
    rows = generate_features({"ES": source}, source_dataset_id="d", source_dataset_sha256="h")
    at_minute_4 = rows[3]
    assert at_minute_4.values["log_return_3m"] is None
    assert "FEATURE_WINDOW_GAP" in at_minute_4.reason_codes
    assert rows[4].values["log_return_1m"] == pytest.approx(__import__("math").log(105 / 104))
