from datetime import datetime, timedelta, timezone

from bot2.data_foundation.contracts import MarketEvent
from .features import generate_features
from .targets_v2 import generate_future_targets

UTC = timezone.utc
T0 = datetime(2026, 6, 1, 14, 30, tzinfo=UTC)


def bars(prices, *, contract="ESM6", session_id="S1", gap_after=None):
    output = []
    for index, price in enumerate(prices):
        minute = index + (1 if gap_after is not None and index > gap_after else 0)
        stamp = T0 + timedelta(minutes=minute)
        output.append(MarketEvent(contract, "CME", "BAR_CLOSE", stamp, None, price, 10,
            event_id="source-contract-id", session_id=session_id,
            timestamp_source="HISTORICAL_EXCHANGE_EVENT"))
    return output


def test_future_target_known_trend_and_exact_label_interval():
    data = bars([100, 101, 102, 103, 104, 105, 106])
    row = generate_future_targets({"ESM6": data}, horizons=(5,))[0]
    assert row.validity == "VALID" and row.future_direction == "UP"
    assert row.future_structure == "TREND" and row.label_end_time == (T0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    assert row.label_information_start == (T0 + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")


def test_future_mutation_changes_label_but_not_features_at_t():
    original = bars([100, 100.25, 100, 100.25, 100, 100.25, 100.5])
    changed = bars([100, 100.25, 100, 100.25, 100, 100.25, 103])
    kwargs = dict(source_dataset_id="d", source_dataset_sha256="h", code_commit="test")
    feature_a = generate_features({"ESM6": original}, **kwargs)[0]
    feature_b = generate_features({"ESM6": changed}, **kwargs)[0]
    label_a = generate_future_targets({"ESM6": original}, horizons=(6,))[0]
    label_b = generate_future_targets({"ESM6": changed}, horizons=(6,))[0]
    assert feature_a.values == feature_b.values
    assert label_a.future_structure != label_b.future_structure


def test_future_target_rejects_missing_minute_without_filling():
    data = bars([100, 101, 102, 103, 104, 105, 106], gap_after=1)
    row = generate_future_targets({"ESM6": data}, horizons=(5,))[0]
    assert row.validity == "FUTURE_WINDOW_GAP" and row.future_direction is None


def test_future_target_does_not_cross_session_or_contract_boundary():
    data = bars([100, 101, 102, 103], session_id="S1")
    for index, price in enumerate([104, 105, 106], start=4):
        data.append(MarketEvent("ESM6", "CME", "BAR_CLOSE", T0 + timedelta(minutes=index), None,
            price, 10, event_id="source-contract-id", session_id="S2",
            timestamp_source="HISTORICAL_EXCHANGE_EVENT"))
    row = generate_future_targets({"ESM6": data}, horizons=(5,))[0]
    assert row.validity == "SESSION_BOUNDARY" and row.label_end_time is None


def test_contract_aware_cross_market_features_require_exact_pairs():
    es = bars([100, 101, 102], contract="ESM6")
    nq = bars([200, 199, 198], contract="NQU6")
    features = generate_features({"ESM6": es, "NQU6": nq},
        source_dataset_id="d", source_dataset_sha256="h", code_commit="test",
        root_groups={"ESM6": "ES", "NQU6": "NQ"})
    row = next(item for item in features if item.instrument == "ESM6" and item.observation_time.endswith("14:32:00Z"))
    assert row.values["cross_market_log_return_1"] is not None
    assert row.values["cross_market_relative_return_1"] is not None
    # Removing the exact NQ timestamp must not silently forward-fill it.
    no_pair = generate_features({"ESM6": es, "NQU6": nq[:2]},
        source_dataset_id="d", source_dataset_sha256="h", code_commit="test",
        root_groups={"ESM6": "ES", "NQU6": "NQ"})
    unmatched = next(item for item in no_pair if item.instrument == "ESM6" and item.observation_time.endswith("14:32:00Z"))
    assert unmatched.values["cross_market_log_return_1"] is None
