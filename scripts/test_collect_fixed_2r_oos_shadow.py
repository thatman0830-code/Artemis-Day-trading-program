from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from scripts.collect_fixed_2r_oos_shadow import signal_rows, source_days


def test_source_days_are_bounded_and_require_current_day(tmp_path):
    root = tmp_path / "ES"; root.mkdir()
    for day in ("2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11",
                "2026-09-13", "2026-09-14"):
        (root / f"{day}.jsonl").write_text("x")
    days = source_days(tmp_path, SimpleNamespace(value="ES"), "2026-09-14")
    assert days == ("2026-09-09", "2026-09-10", "2026-09-11", "2026-09-13", "2026-09-14")


def test_signal_target_is_exact_fixed_2r_and_oos_filtered():
    qualification = SimpleNamespace(id="q", entry=Decimal("100"), stop=Decimal("95"),
        direction=SimpleNamespace(value="BULLISH"))
    fact = SimpleNamespace(final_qualification=qualification,
        evaluation_time=datetime(2026, 9, 14, tzinfo=timezone.utc))
    state = SimpleNamespace(batch_results=(SimpleNamespace(setup_fact=fact),))
    rows = signal_rows(state, SimpleNamespace(value="ES"), {"2026-09-14"})
    assert len(rows) == 1 and rows[0]["target_price"] == "110"
    assert signal_rows(state, SimpleNamespace(value="ES"), {"2026-09-15"}) == ()


def test_collector_and_runner_expose_no_order_surface():
    root = Path(__file__).parents[1]
    source = (root / "scripts/collect_fixed_2r_oos_shadow.py").read_text()
    runner = (root / "scripts/run_fixed_2r_oos_shadow.ps1").read_text()
    assert "append_completed_shadow_trade" not in source
    for forbidden in ("SubmitOrder", "CreateOrder", "trading_authority=True"):
        assert forbidden not in source and forbidden not in runner
