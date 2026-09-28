from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "enroll_databento_historical_credential.ps1"


def test_enrollment_is_hidden_owner_bound_and_outside_repository():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Read-Host" in text and "-AsSecureString" in text
    assert "ConvertFrom-SecureString" in text
    assert "LOCALAPPDATA" in text
    assert "icacls.exe" in text and "/inheritance:r" in text
    assert "hyperliquid-trading-bot" not in text
    assert "Write-Output $" not in text


def test_enrollment_refuses_silent_overwrite_and_cleans_temporary_file():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "already enrolled" in text
    assert "Move-Item" in text
    assert "finally" in text
    assert "Remove-Item -LiteralPath $temporary" in text
    assert "credential.dpapi" in text
