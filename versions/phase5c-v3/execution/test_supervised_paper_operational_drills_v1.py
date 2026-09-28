from datetime import datetime, timezone
from pathlib import Path

import pytest

from execution.supervised_paper_operational_drills_v1 import run_supervised_operational_drills


NOW = datetime(2026, 9, 1, 20, tzinfo=timezone.utc)


def test_all_isolated_operational_drills_pass(tmp_path):
    report = run_supervised_operational_drills(tmp_path / "drills", observed_at=NOW)
    assert len(report.observations) == 11
    assert all(item.passed for item in report.observations)
    assert len({item.name for item in report.observations}) == 11
    assert len({item.evidence_id for item in report.observations}) == 11
    assert not report.physical_outage_claimed
    assert not report.recorder_operation_claimed
    assert not report.trading_authority


def test_report_is_deterministic_and_content_addressed(tmp_path):
    first = run_supervised_operational_drills(tmp_path / "one", observed_at=NOW)
    second = run_supervised_operational_drills(tmp_path / "two", observed_at=NOW)
    assert first == second
    assert len(first.report_id) == 64


def test_existing_or_non_utc_drill_root_rejects(tmp_path):
    existing = tmp_path / "existing"; existing.mkdir()
    with pytest.raises(ValueError, match="new path"):
        run_supervised_operational_drills(existing, observed_at=NOW)
    with pytest.raises(ValueError, match="UTC"):
        run_supervised_operational_drills(tmp_path / "naive", observed_at=NOW.replace(tzinfo=None))


def test_drill_module_has_no_live_or_recorder_control_surface():
    source = Path(__file__).with_name("supervised_paper_operational_drills_v1.py").read_text("utf-8").lower()
    for prohibited in ("requests", "httpx", "socket", "websocket", "private_key", "api_key",
                       "place_order", "submit_live", "subprocess", "scheduledtask", "start-process"):
        assert prohibited not in source
