from pathlib import Path
import json
import pytest

from execution.ninjatrader_closed_bar_recorder_v1 import _canonical
from scripts.repair_ninjatrader_duplicate_tail_v1 import repair


def test_non_duplicate_tail_fails_closed(tmp_path: Path):
    chain=tmp_path/"x.jsonl";chain.write_bytes(b"a\nb\n")
    with pytest.raises(ValueError,match="duplicate tail"):
        repair(chain=chain,manifest=tmp_path/"manifest.json",quarantine=tmp_path/"q",report=tmp_path/"r.json")


def test_source_contains_process_level_lock():
    source=(Path(__file__).parents[1]/"execution"/"ninjatrader_closed_bar_recorder_v1.py").read_text("utf-8")
    assert "msvcrt.LK_NBLCK" in source
    assert ".single-writer.lock" in source
