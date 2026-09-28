from pathlib import Path


def test_monday_boundary_scripts_are_non_executing_and_fail_closed():
    root = Path(__file__).parent
    text = (root / "establish_monday_canonical_boundary.py").read_text().lower()
    text += (root / "evaluate_monday_canonical_readiness.py").read_text().lower()
    assert "2026, 9, 14" in text
    assert "owner_confirmation_required" not in text or "evaluate_canonical_paper_readiness" in text
    for prohibited in ("submitorder", "createorder", "start-scheduledtask", "paper_execution_permitted=true"):
        assert prohibited not in text
