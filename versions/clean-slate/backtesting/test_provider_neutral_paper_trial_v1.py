from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_shadow_profile_comparison_v1 import CompletedShadowTradeV1, ShadowSide
from backtesting.provider_neutral_paper_trial_v1 import build_provider_neutral_trial, snapshot_document

T = datetime(2026, 9, 14, tzinfo=timezone.utc)


def trade(i, market=FuturesCanonicalMarket.ES):
    return CompletedShadowTradeV1(str(i) * 64, market, ShadowSide.LONG,
        T + timedelta(days=i), T + timedelta(days=i, minutes=1),
        Decimal("100"), Decimal("95"), Decimal("110"), "r" * 64)


def test_trial_starts_three_profiles_at_fifty_thousand_and_is_non_executable():
    snapshot = build_provider_neutral_trial(trades=(trade(1), trade(2, FuturesCanonicalMarket.NQ)),
                                             evaluated_at=T + timedelta(days=3))
    assert snapshot.completed_sessions == 2
    assert len(snapshot.ledgers) == 3
    assert all(x.starting_equity_usd == Decimal("50000") for x in snapshot.ledgers)
    assert snapshot.comparison_only and snapshot.paper_execution_permitted is False
    assert snapshot.live_trading_permitted is snapshot.trading_authority is False


def test_snapshot_document_is_json_serializable_and_preserves_authority_flags():
    snapshot = build_provider_neutral_trial(trades=(trade(1),), evaluated_at=T + timedelta(days=2))
    document = snapshot_document(snapshot)
    json.dumps(document)
    assert document["configured_sessions"] == 15
    assert document["trading_authority"] is False
