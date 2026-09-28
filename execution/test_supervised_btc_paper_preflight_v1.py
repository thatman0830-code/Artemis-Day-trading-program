from datetime import timedelta

from execution.supervised_btc_paper_preflight_v1 import evaluate_supervised_btc_paper_preflight
from execution.test_btc_canonical_paper_reservation_bridge_v1 import running,T


def values(tmp_path):
    assembly=running(tmp_path)
    return dict(repository_checkpoint="a"*64,repository_clean=True,expected_checkpoint="a"*64,
        session_root=tmp_path/"fresh-session",session_id="7"*32,archive_root=assembly.archive_root,
        evidence_path=tmp_path/"launch-evidence.json",confirmation=assembly.session.confirmation,
        economics_policy_path=tmp_path/"economics-policy.json",risk_policy_path=tmp_path/"risk.json",
        public_evidence_root=tmp_path/"public",
        public_evidence_receipt_path=next((tmp_path/"public").glob("*.receipt.json")),
        paper_specification_bundle_path=tmp_path/"paper-bundle.json",as_of=T)


def test_read_only_preflight_reports_all_current_gates_ready(tmp_path):
    args=values(tmp_path);result=evaluate_supervised_btc_paper_preflight(**args)
    assert result.ready and result.reasons==() and result.reservation_state=="NEW"
    assert result.archive_id and result.public_evidence_id and result.economic_gate_id
    assert result.trading_authority is False and not args["session_root"].exists()


def test_preflight_aggregates_dirty_repository_and_stale_market_evidence(tmp_path):
    args=values(tmp_path);args.update(repository_clean=False,as_of=T+timedelta(seconds=61))
    result=evaluate_supervised_btc_paper_preflight(**args)
    assert not result.ready
    assert "REPOSITORY_NOT_CLEAN" in result.reasons
    assert "PUBLIC_EVIDENCE_STALE" in result.reasons
    assert result.trading_authority is False
