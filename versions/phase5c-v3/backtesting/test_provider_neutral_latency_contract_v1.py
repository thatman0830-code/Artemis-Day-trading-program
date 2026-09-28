from pathlib import Path


def test_capture_and_cockpit_publish_latency_contract():
    root = Path(__file__).parents[1]
    capture = (root / "scripts" / "capture_databento_live_es_nq.py").read_text(encoding="utf-8")
    cockpit = (root / "scripts" / "publish_provider_neutral_cockpit.py").read_text(encoding="utf-8")
    assert 'contract_version": "provider-neutral-latency-v1"' in capture
    assert 'stale_sample_count' in capture
    assert 'capture.get("latency"' in cockpit
