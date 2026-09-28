from datetime import datetime, timezone
import json
import pytest

from research.oracle_shadow_lane_v1 import parse_oracle_observation


NOW = datetime(2026, 9, 11, 18, tzinfo=timezone.utc)


def payload(**changes):
    value = {"schema_version":"oracle-shadow-observation-v1","engine_id":"buddy-oracle-v1",
             "instrument":"BTC","timeframe":"5m","observed_at":"2026-09-11T17:59:00Z",
             "source_event_time":"2026-09-11T17:55:00Z","direction":"BULLISH",
             "confidence":"0.72"}
    value.update(changes)
    return json.dumps(value, sort_keys=True).encode()


def test_valid_observation_is_comparison_only_and_non_executable():
    result = parse_oracle_observation(payload(), received_at=NOW)
    assert result.direction == "BULLISH" and result.confidence is not None
    assert result.comparison_only is True
    assert result.canonical_strategy_influence_permitted is False
    assert result.order_influence_permitted is False and result.trading_authority is False


@pytest.mark.parametrize("change", (
    {"schema_version":"unknown"}, {"direction":"BUY"}, {"confidence":"1.1"},
    {"source_event_time":"2026-09-11T18:00:00Z"},
))
def test_invalid_or_future_or_action_like_observation_fails_closed(change):
    with pytest.raises(ValueError):
        parse_oracle_observation(payload(**change), received_at=NOW)
