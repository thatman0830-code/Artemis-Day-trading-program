from datetime import datetime, timedelta, timezone

from bot2.data_foundation.contracts import MarketEvent
from .features import generate_features
from .targets_v3 import generate_future_targets

UTC = timezone.utc
T0 = datetime(2026, 6, 1, 14, 30, tzinfo=UTC)


def events(future, *, gap_at=None, split_session_at=None):
    prices = [100 + (0.25 if i % 2 else 0) for i in range(31)] + list(future)
    rows = []
    for i, price in enumerate(prices):
        minute = i + (1 if gap_at is not None and i > gap_at else 0)
        sid = "S2" if split_session_at is not None and i >= split_session_at else "S1"
        rows.append(MarketEvent("ESM6", "CME", "BAR_CLOSE", T0 + timedelta(minutes=minute), None,
            price, 10, event_id=f"bar-{i}", contract_id="es-2026-06-id", session_id=sid,
            timestamp_source="HISTORICAL_EXCHANGE_EVENT"))
    return rows


def test_target_v3_uses_strict_future_window_and_causal_reference():
    rows = events([100.5, 101, 101.5, 102, 102.5, 103])
    target = generate_future_targets({"ESM6": rows}, horizons=(5,))[30]
    assert generate_future_targets({"ESM6": rows}, horizons=(5,))[30] == target
    assert target.validity == "VALID" and target.future_direction == "UP"
    assert target.future_structure == "TREND"
    assert target.label_information_start == T0.isoformat().replace("+00:00", "Z")
    assert target.observation_time == (T0 + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    assert target.future_window_start == (T0 + timedelta(minutes=31)).isoformat().replace("+00:00", "Z")
    assert target.label_end_time == (T0 + timedelta(minutes=35)).isoformat().replace("+00:00", "Z")


def test_v3_future_mutation_changes_target_not_features_at_t():
    baseline = events([100.25, 100, 100.25, 100, 100.25])
    changed = events([100.25, 100, 100.25, 100, 103])
    kwargs = dict(source_dataset_id="d", source_dataset_sha256="h", code_commit="test")
    features_a = generate_features({"ESM6": baseline}, **kwargs)
    features_b = generate_features({"ESM6": changed}, **kwargs)
    assert features_a[30].values == features_b[30].values
    targets_a = generate_future_targets({"ESM6": baseline}, horizons=(5,))
    targets_b = generate_future_targets({"ESM6": changed}, horizons=(5,))
    assert targets_a[30].future_structure != targets_b[30].future_structure


def test_v3_future_gap_or_session_boundary_never_fills():
    gapped = events([100.25, 100.5, 100.75, 101, 101.25], gap_at=32)
    assert generate_future_targets({"ESM6": gapped}, horizons=(5,))[30].validity == "FUTURE_WINDOW_GAP"
    boundary = events([100.25, 100.5, 100.75, 101, 101.25], split_session_at=33)
    assert generate_future_targets({"ESM6": boundary}, horizons=(5,))[30].validity == "SESSION_BOUNDARY"


def test_v3_horizon_rejects_irregular_interval_and_exact_contract_change():
    irregular=events([100.25, 100.5, 100.75, 101, 101.25])
    irregular[33]=MarketEvent("ESM6","CME","BAR_CLOSE",T0+timedelta(minutes=33,seconds=30),None,
        irregular[33].price,10,event_id="irregular",contract_id="es-2026-06-id",session_id="S1",
        timestamp_source="HISTORICAL_EXCHANGE_EVENT")
    target=generate_future_targets({"ESM6":irregular},horizons=(5,))[30]
    assert target.validity=="FUTURE_WINDOW_GAP"
    changed=events([100.25, 100.5, 100.75, 101, 101.25])
    changed[33]=MarketEvent("ESM6","CME","BAR_CLOSE",changed[33].exchange_time,None,changed[33].price,10,
        event_id="roll",contract_id="es-2026-09-id",session_id="S1",timestamp_source="HISTORICAL_EXCHANGE_EVENT")
    assert generate_future_targets({"ESM6":changed},horizons=(5,))[30].validity=="CONTRACT_BOUNDARY"


def test_v3_volatility_state_uses_fixed_causal_reference_not_sample_balance():
    rows = events([100.25, 100.5, 100.75, 101, 101.25])
    target = generate_future_targets({"ESM6": rows}, horizons=(5,))[30]
    assert target.reference_realized_volatility is not None
    assert target.future_volatility_ratio is not None
    assert target.future_volatility_state in {"LOW", "NORMAL", "HIGH"}
