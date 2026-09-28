from datetime import date, timedelta
import json

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_boundary_v1 import (
    establish_boundary, evaluate_canonical_paper_readiness,
)
from backtesting.test_ninjatrader_closed_bar_dataset_v1 import NOW, build


def test_boundary_quarantines_prior_gaps_without_mutating_archives(tmp_path):
    for market in FuturesCanonicalMarket:
        build(tmp_path, market)
        manifest = tmp_path / market.value / "manifest.json"
        body = json.loads(manifest.read_text())
        body["unresolved_gap_count"] = 312
        manifest.write_text(json.dumps(body))
    before = sorted((path, path.read_bytes()) for path in tmp_path.rglob("*.*"))
    boundary = establish_boundary(
        archive_root=tmp_path, target_day=date(2026, 9, 14), as_of=NOW)
    after = sorted((path, path.read_bytes()) for path in tmp_path.rglob("*.*"))
    assert before == after
    assert boundary.state == "ESTABLISHED_PRIOR_ARCHIVES_QUARANTINED"
    assert {row.inherited_unresolved_gap_count for row in boundary.prior_archives} == {312}
    assert boundary.paper_execution_permitted is boundary.trading_authority is False


def test_readiness_waits_then_requires_clean_synchronized_window(tmp_path):
    for market in FuturesCanonicalMarket: build(tmp_path, market)
    boundary = establish_boundary(
        archive_root=tmp_path, target_day=NOW.date(), as_of=NOW - timedelta(minutes=1))
    ready = evaluate_canonical_paper_readiness(
        boundary=boundary, archive_root=tmp_path, as_of=NOW + timedelta(minutes=4),
        minimum_bars_per_market=3)
    assert ready.state == "READY_FOR_OWNER_CONFIRMATION"
    assert ready.inherited_gaps_quarantined and ready.owner_confirmation_required
    assert ready.paper_execution_permitted is ready.trading_authority is False


def test_boundary_rejects_past_target(tmp_path):
    for market in FuturesCanonicalMarket: build(tmp_path, market)
    try:
        establish_boundary(archive_root=tmp_path, target_day=NOW.date() - timedelta(days=1), as_of=NOW)
    except ValueError as exc:
        assert "past" in str(exc)
    else:
        raise AssertionError("past boundary accepted")
