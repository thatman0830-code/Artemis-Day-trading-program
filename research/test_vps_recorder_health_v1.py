from datetime import datetime, timezone
from hashlib import sha256
import json

from research.vps_recorder_health_v1 import healthy


def test_health_requires_fresh_recording_and_verified_archive(tmp_path):
    data = b"verified\n"; (tmp_path / "BTC_1m.csv").write_bytes(data)
    manifest = {"state":"RECORDING","source":"hyperliquid-public-mainnet",
                "updated_at":"2026-09-11T18:00:00Z",
                "checksums":{"BTC_1m.csv":sha256(data).hexdigest()}}
    path = tmp_path / "archive_manifest.json"; path.write_text(json.dumps(manifest))
    now = datetime(2026, 9, 11, 18, 4, tzinfo=timezone.utc)
    assert healthy(path, now=now)
    (tmp_path / "BTC_1m.csv").write_bytes(b"changed")
    assert not healthy(path, now=now)
