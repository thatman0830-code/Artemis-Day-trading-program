"""Evidence ledger: hash chain, tamper detection, restart-safe dedupe, label discipline."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest

from mes_pilot.ledger import EVIDENCE_LABELS, EvidenceLedger
from mes_pilot.tests.helpers import DAY, et


def test_chain_verifies_and_links(tmp_path):
    led = EvidenceLedger(tmp_path, "SYNTHETIC_TEST", "run-1")
    a = led.append("A", x=1, at=et(DAY, 9, 30))
    b = led.append("B", y=[1, 2], nested={"k": (1, 2)})
    assert a["prev_hash"] == "0" * 64 and b["prev_hash"] == a["hash"]
    assert [r["seq"] for r in led.records()] == [1, 2]
    assert led.records("A")[0]["at"] == et(DAY, 9, 30).isoformat()
    assert led.verify_chain()


@pytest.mark.parametrize("mode", ["edit_field", "delete_middle", "reorder"])
def test_tampering_detected(tmp_path, mode):
    led = EvidenceLedger(tmp_path, "SYNTHETIC_TEST", "run-1")
    for i in range(3):
        led.append("POSITION_CLOSED", net_pnl=10.0 * i)
    lines = led.path.read_text(encoding="utf-8").splitlines()
    if mode == "edit_field":
        rec = json.loads(lines[1]); rec["net_pnl"] = 999.0
        lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    elif mode == "delete_middle":
        del lines[1]
    else:
        lines[0], lines[1] = lines[1], lines[0]
    led.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert led.verify_chain() is False


def test_dedupe_keys_survive_reopen(tmp_path):
    led = EvidenceLedger(tmp_path, "AUTONOMOUS_PAPER", "run-1")
    assert led.append("FILL", dedupe_key="FILL:F1", price=5000.25) is not None
    assert led.append("FILL", dedupe_key="FILL:F1", price=5000.25) is None
    led2 = EvidenceLedger(tmp_path, "AUTONOMOUS_PAPER", "run-2")     # restart / replay
    assert led2.has("FILL:F1")
    assert led2.append("FILL", dedupe_key="FILL:F1", price=5000.25) is None
    rec = led2.append("FILL", dedupe_key="FILL:F2", price=5001.0)
    assert rec["seq"] == 2 and rec["prev_hash"] == led.records()[0]["hash"]
    assert len(led2.records("FILL")) == 2 and led2.verify_chain()


def test_evidence_labels_restricted_and_never_pooled(tmp_path):
    with pytest.raises(ValueError):
        EvidenceLedger(tmp_path, "BACKTEST_GOOD_ENOUGH", "r")
    assert {"SYNTHETIC_TEST", "AUTONOMOUS_PAPER", "MANUAL_PROP", "PERSONAL_LIVE", "PROTECTED_OOS"} <= EVIDENCE_LABELS
    a = EvidenceLedger(tmp_path, "SYNTHETIC_TEST", "r")
    b = EvidenceLedger(tmp_path, "AUTONOMOUS_PAPER", "r")
    a.append("X", dedupe_key="K")
    assert a.path != b.path and b.records() == [] and not b.has("K")
    assert a.records()[0]["evidence_label"] == "SYNTHETIC_TEST"


@pytest.mark.parametrize("field", ["evidence_label", "prev_hash", "seq", "hash", "type"])
def test_fields_cannot_override_chain_metadata(tmp_path, field):
    """Regression: **fields used to be merged last, so a field could rewrite the label or break the chain."""
    led = EvidenceLedger(tmp_path, "SYNTHETIC_TEST", "run-1")
    with pytest.raises(ValueError):
        led.append("X", **{field: "PERSONAL_LIVE"})
    with pytest.raises(ValueError):
        led.append("X", run_id="someone-else")
    led.append("X", run_id="run-1")                # same run id is allowed (RUN_MANIFEST)
    assert led.verify_chain()


def test_non_string_keys_and_tuples_still_verify(tmp_path):
    """Regression: hashing must use the same JSON that is read back (int keys sort differently as strings)."""
    led = EvidenceLedger(tmp_path, "SYNTHETIC_TEST", "run-1")
    led.append("SESSION_SUMMARY", counts={2: "a", 10: "b"}, zone=(5000.25, 5001.0), when=et(DAY, 9, 30) + timedelta(seconds=1))
    assert led.verify_chain()
