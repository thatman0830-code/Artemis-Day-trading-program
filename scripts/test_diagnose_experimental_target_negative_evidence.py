from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from scripts.diagnose_experimental_target_negative_evidence import analyze_signal, outcome

T = datetime(2026, 9, 8, tzinfo=timezone.utc)


def bar(i, low, high):
    return SimpleNamespace(open_time=T + timedelta(minutes=i),
                           low=Decimal(low), high=Decimal(high))


def test_stop_first_and_window_sensitivity_are_descriptive():
    bars = (bar(0, "99", "101"), bar(1, "94", "111"))
    assert outcome("LONG", Decimal("95"), Decimal("110"), bars) == ("STOP", 2, True)
    signal = {"signal_id": "a" * 64, "side": "LONG", "signal_time": T.isoformat(),
              "entry_price": "100", "stop_price": "95", "target_price": "110"}
    row = analyze_signal(signal, bars)
    assert row["entered"] and row["target_r_multiple"] == "2"
    assert row["eventual_first_outcome"] == "STOP" and row["ambiguous_stop_first"]
    assert row["fixed_2r_window_outcomes"]["30"] == "STOP"


def test_missing_entry_fails_closed():
    signal = {"signal_id": "b" * 64, "side": "SHORT", "signal_time": T.isoformat(),
              "entry_price": "100", "stop_price": "105", "target_price": "90"}
    row = analyze_signal(signal, (bar(0, "80", "90"),))
    assert not row["entered"] and row["eventual_first_outcome"] == "WAITING_ENTRY"
