from pathlib import Path


def test_guard_task_is_restricted_and_non_authoritative():
    source = Path(__file__).parents[1] / "scripts" / "install_provider_neutral_supervisor_guard_task.ps1"
    text = source.read_text(encoding="utf-8")
    assert "RunLevel Limited" in text
    assert "MultipleInstances IgnoreNew" in text
    assert "No live or trading authority" in text
