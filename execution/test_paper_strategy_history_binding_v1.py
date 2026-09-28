import json
import pytest

from execution.paper_session_attribution_v1 import write_attribution
from execution.paper_strategy_history_binding_v1 import (
    PaperStrategyHistoryBindingError,build_binding,read_binding,write_binding,
)
from execution.test_paper_session_attribution_v1 import session


def test_legacy_attribution_and_history_are_bound_without_rewrite(tmp_path):
    root=tmp_path/"canonical-a";session(root);write_attribution(root,attempt_exit_code=0)
    before=(root/"session-attribution-v2.json").read_bytes();path=write_binding(root)
    document=json.loads(path.read_text());assert document["payload"]["history_summary"]["event_count"]==1
    assert read_binding(root/"session-attribution-v2.json")
    assert (root/"session-attribution-v2.json").read_bytes()==before


def test_history_tampering_or_binding_conflict_fails_closed(tmp_path):
    root=tmp_path/"canonical-b";session(root);write_attribution(root,attempt_exit_code=0);write_binding(root)
    history=root.parent/(root.name+"-canonical-strategy-history.jsonl");history.write_text("{}\n")
    with pytest.raises(PaperStrategyHistoryBindingError):read_binding(root/"session-attribution-v2.json")
    history.unlink();session_history=root.parent/(root.name+"-canonical-strategy-history.jsonl")
    # The source helper cannot be replayed into an existing directory; a forged binding still rejects.
    (root/"strategy-history-binding-v1.json").write_text("{}")
    with pytest.raises(PaperStrategyHistoryBindingError):build_binding(root)


def test_missing_attribution_or_history_rejects(tmp_path):
    root=tmp_path/"missing";root.mkdir()
    with pytest.raises(PaperStrategyHistoryBindingError):build_binding(root)
