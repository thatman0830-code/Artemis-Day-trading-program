from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from monitoring.paper_dashboard_v1 import PaperDashboardError, build_snapshot, main


FIELDS = "symbol,timeframe,open_time,close_time,open,high,low,close,volume,is_closed\n"
ROW = "BTC,15m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,100,102,99,101,12,true\n"


def paths(tmp_path):
    candle = tmp_path / "BTC_15m.csv"; candle.write_text(FIELDS + ROW, "utf-8")
    return dict(candle_path=candle, launch_decision_path=tmp_path / "launch.json",
                adapter_checkpoint_path=tmp_path / "adapter.json",
                session_health_path=tmp_path / "health.json",
                performance_checkpoint_path=tmp_path / "performance.json",
                observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc))


def test_snapshot_is_explicitly_read_only_and_does_not_invent_performance(tmp_path):
    result = build_snapshot(**paths(tmp_path))
    assert result["trading_authority"] is False
    assert result["live_trading_permitted"] is False
    assert result["advisory_only"] is True
    assert result["performance"]["available"] is False
    assert result["performance"]["integrity"] == "MISSING"
    assert result["paper"]["available"] is False
    assert len(result["snapshot_id"]) == 64


def test_snapshot_id_is_deterministic(tmp_path):
    value = paths(tmp_path)
    assert build_snapshot(**value) == build_snapshot(**value)


def test_adapter_checksum_and_authority_are_verified(tmp_path):
    value = paths(tmp_path)
    gateway = {"connected": True, "kill_switch_active": False,
        "reconciliation_required": False, "records": [], "trading_authority": False}
    payload = {"gateway_checkpoint": {"payload": gateway}, "receipts": [],
               "trading_authority": False}
    raw = {"schema_version": "paper-exchange-adapter-checkpoint-v1", "payload": payload,
           "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True,
           separators=(",", ":")).encode()).hexdigest()}
    value["adapter_checkpoint_path"].write_text(json.dumps(raw), "utf-8")
    assert build_snapshot(**value)["paper"]["connected"] is True
    raw["payload_sha256"] = "0" * 64
    value["adapter_checkpoint_path"].write_text(json.dumps(raw), "utf-8")
    with pytest.raises(PaperDashboardError, match="checkpoint is invalid"):
        build_snapshot(**value)


@pytest.mark.parametrize("row", [
    "ETH,15m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,1,1,1,1,1,true\n",
    "BTC,5m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,1,1,1,1,1,true\n",
    "BTC,15m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,1,1,1,1,1,false\n",
])
def test_unsupported_candle_evidence_fails_closed(tmp_path, row):
    value = paths(tmp_path); value["candle_path"].write_text(FIELDS + row, "utf-8")
    with pytest.raises(PaperDashboardError, match="unsupported evidence"):
        build_snapshot(**value)


def test_symlinked_evidence_rejects(tmp_path):
    value = paths(tmp_path); target = value["candle_path"]
    link = tmp_path / "link.csv"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    value["candle_path"] = link
    with pytest.raises(PaperDashboardError, match="unsafe"):
        build_snapshot(**value)


def test_non_loopback_binding_rejects():
    with pytest.raises(PaperDashboardError, match="loopback"):
        main(["--host", "0.0.0.0"])


def test_module_has_no_execution_or_outbound_client_imports():
    source = Path(__file__).with_name("paper_dashboard_v1.py").read_text("utf-8")
    assert "from execution" not in source
    assert "import requests" not in source
    assert "urllib.request" not in source


def test_verified_performance_checkpoint_is_projected(tmp_path):
    from execution.paper_performance_checkpoint_v1 import checkpoint_bytes
    from execution.test_paper_performance_checkpoint_v1 import filled_ledger
    value = paths(tmp_path)
    value["performance_checkpoint_path"].write_bytes(checkpoint_bytes(filled_ledger()))
    performance = build_snapshot(**value)["performance"]
    assert performance["available"] is True
    assert performance["integrity"] == "VERIFIED"
    assert performance["cash"] == "4997.0"
    assert performance["equity"] == "10097.0"
    assert performance["position"]["quantity"] == "0.1"
    assert len(performance["trade_markers"]) == 1
    assert performance["trading_authority"] is False


def test_tampered_performance_checkpoint_fails_dashboard_closed(tmp_path):
    from execution.paper_performance_checkpoint_v1 import checkpoint_bytes
    from execution.test_paper_performance_checkpoint_v1 import filled_ledger
    value = paths(tmp_path)
    raw = bytearray(checkpoint_bytes(filled_ledger())); raw[-10] ^= 1
    value["performance_checkpoint_path"].write_bytes(raw)
    with pytest.raises(PaperDashboardError, match="integrity validation"):
        build_snapshot(**value)
