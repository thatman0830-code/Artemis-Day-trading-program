import inspect

from execution.btc_canonical_paper_launcher_input_v1 import BTCCanonicalPaperLauncherInputV1
from execution.test_btc_canonical_paper_reservation_bridge_v1 import running,actionable,T
from execution.test_paper_performance_ledger_v1 import H


def test_active_launch_is_bound_to_one_canonical_worker_observation(tmp_path):
    assembly=running(tmp_path);observation=actionable(assembly)
    from execution.btc_canonical_strategy_worker_v1 import BTCCanonicalStrategyWorkerV1
    worker=BTCCanonicalStrategyWorkerV1(archive_root=assembly.archive_root,
        snapshot_root=assembly.snapshot_root,status_path=tmp_path/"canonical-status.json",
        evaluator=lambda **_:observation,
        probe=lambda **_:(observation.one_minute.reference.sha256,
            observation.five_minute.reference.sha256))
    value=BTCCanonicalPaperLauncherInputV1(assembly=assembly,evidence_id=H("evidence"),
        status_path=tmp_path/"canonical-status.json",worker=worker)
    assert value(assembly=assembly,as_of=T).command is None
    value.close()
    value.worker._thread.join(timeout=5)
    admitted=value(assembly=assembly,as_of=T)
    assert admitted.command is not None and admitted.strategy_intent is not None
    assert assembly.session.reservation.load()["body"]["state"]=="PREPARED"
    assert value(assembly=assembly,as_of=T).command is None


def test_prime_warms_worker_without_reader_or_reservation(tmp_path):
    assembly=running(tmp_path);observation=actionable(assembly)
    from execution.btc_canonical_strategy_worker_v1 import (
        BTCCanonicalStrategyWorkerV1,BTCStrategyWorkerState,
    )
    worker=BTCCanonicalStrategyWorkerV1(archive_root=assembly.archive_root,
        snapshot_root=assembly.snapshot_root,status_path=tmp_path/"prime-status.json",
        evaluator=lambda **_:observation,
        probe=lambda **_:(observation.one_minute.reference.sha256,
            observation.five_minute.reference.sha256))
    value=BTCCanonicalPaperLauncherInputV1(assembly=assembly,evidence_id=H("prime-evidence"),
        status_path=tmp_path/"active-status.json",prime_status_path=tmp_path/"prime-status.json",
        worker=worker)
    assert value.prime(as_of=T).state is BTCStrategyWorkerState.IDLE
    worker._thread.join(timeout=5)
    assert value.prime(as_of=T).state is BTCStrategyWorkerState.READY
    assert value.reader is None
    assert assembly.session.reservation.load()["body"]["state"]=="EMPTY"
    value(assembly=assembly,as_of=T)
    assert worker.status_path==(tmp_path/"active-status.json").absolute()
    value.close()


def test_launcher_input_has_no_provider_or_live_transport_surface():
    source=inspect.getsource(__import__(
        "execution.btc_canonical_paper_launcher_input_v1",fromlist=["*"])).lower()
    for prohibited in ("requests","urllib","websocket","private_key","submit_order","place_order"):
        assert prohibited not in source
