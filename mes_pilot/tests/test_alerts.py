"""Advisory manual-prop alerts: blocking, expiry, Frank's actual fills recorded separately."""
from __future__ import annotations

from datetime import timedelta

import pytest

from mes_pilot.alerts import AlertOutbox, EntryAlert, ManagementAlert
from mes_pilot.tests.helpers import DAY, et

T = et(DAY, 9, 41)


def entry(aid="ALR-1", expires=T + timedelta(seconds=60)):
    return EntryAlert(alert_id=aid, signal_id="SIG-" + aid, strategy_version="v", config_hash="h", contract="MES",
                      side="LONG", setup="REVERSAL_R1", detected_at=T.isoformat(), expires_at=expires.isoformat(),
                      entry_zone=(5000.25, 5001.0), current_price=5001.25, stop=4998.25, target=5005.0,
                      suggested_quantity=1, worst_case_risk_usd=21.7, gross_reward_risk=1.08,
                      account_rule_status="UNCONFIGURED", invalidation="below 4998.25")


@pytest.fixture
def box(tmp_path):
    return AlertOutbox(tmp_path / "prop-alerts.jsonl")


def test_unresolved_entry_alert_blocks_next_entry_alert(box):
    assert box.emit(entry("A1"))["emitted"] is True
    assert box.emit(entry("A2")) == {"emitted": False, "reason": "PRIOR_ALERT_UNRESOLVED"}
    # Management alerts (exit instructions) are never blocked.
    mgmt = ManagementAlert("M1", "A1", "EXIT_AT_STOP", "stop", T.isoformat())
    assert box.emit(mgmt)["emitted"] is True
    box.resolve("A1", "SKIPPED", note="too fast")
    assert box.emit(entry("A2"))["emitted"] is True


def test_duplicate_alert_id_not_reemitted(box):
    box.emit(entry("A1"))
    box.resolve("A1", "SKIPPED")
    assert box.emit(entry("A1")) == {"emitted": False, "reason": "DUPLICATE_ALERT_ID"}


def test_expiry_auto_records_expired_only_after_grace(box):
    box.emit(entry("A1", expires=T + timedelta(seconds=60)))
    assert box.expire_stale(T + timedelta(minutes=6)) == []           # expiry 09:42 + 5 min grace = 09:47
    assert box.expire_stale(T + timedelta(minutes=6, seconds=1)) == ["A1"]
    (res,) = [d for d in box._all() if d["kind"] == "RESOLUTION"]
    assert res["decision"] == "EXPIRED" and res["source"] == "AUTO_EXPIRY"
    assert box.unresolved() == []
    assert box.expire_stale(T + timedelta(hours=1)) == []             # not recorded twice


def test_resolution_records_franks_actual_fill_separately(box):
    box.emit(entry("A1"))
    doc = box.resolve("A1", "ENTERED", actual_fill_price=5001.75, actual_fill_time=(T + timedelta(seconds=20)).isoformat(),
                      actual_qty=1, actual_stop=4998.0, actual_target=5005.0, note="filled 1 tick worse")
    assert doc["source"] == "MANUAL_ENTRY_BY_FRANK" and doc["actual_fill_price"] == 5001.75
    alert_doc = [d for d in box._all() if d["kind"] == "ENTRY"][0]
    assert alert_doc["current_price"] == 5001.25 and "actual_fill_price" not in alert_doc   # alert untouched


def test_entered_requires_actual_fill(box):
    box.emit(entry("A1"))
    with pytest.raises(ValueError):
        box.resolve("A1", "ENTERED")
    with pytest.raises(ValueError):
        box.resolve("A1", "MAYBE")
    with pytest.raises(KeyError):
        box.resolve("NOPE", "SKIPPED")


def test_operator_resolution_is_final_but_may_follow_auto_expiry(box):
    box.emit(entry("A1"))
    box.expire_stale(T + timedelta(hours=1))
    late = box.resolve("A1", "ENTERED", actual_fill_price=5002.0, actual_qty=1)
    assert late["supersedes_auto_expiry"] is True
    with pytest.raises(ValueError):
        box.resolve("A1", "SKIPPED")


def test_entry_alert_is_advisory_text(box):
    doc = box.emit(entry("A1"))["alert"]
    assert doc["instruction"].startswith("ADVISORY ONLY. Not an order.")
