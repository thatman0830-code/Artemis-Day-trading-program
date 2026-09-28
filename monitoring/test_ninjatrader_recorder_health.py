from datetime import datetime, timezone
from pathlib import Path

from monitoring.ninjatrader_recorder_health import evaluate


def test_module_is_read_only_and_non_authoritative():
    source = Path(__file__).with_name("ninjatrader_recorder_health.py").read_text("utf-8")
    assert "SessionCalendar" in source and "IntervalClassification.OPEN" in source
    assert '"trading_authority": False' in source
    for prohibited in ("place_order", "submitorder", "Start-ScheduledTask", "write_text", "write_bytes"):
        assert prohibited not in source


def test_requires_utc():
    try:
        evaluate(archive_root=Path("missing"), bridge_root=Path("missing"), as_of=datetime.now())
    except ValueError as exc:
        assert "UTC as_of" in str(exc)
    else:
        raise AssertionError("naive time accepted")
