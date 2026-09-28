from datetime import timedelta
from dataclasses import replace
import hashlib,json,threading,time

from execution.btc_canonical_strategy_observation_v1 import observe_btc_canonical_strategy
from execution.btc_canonical_strategy_worker_v1 import (
    BTCCanonicalStrategyWorkerV1,BTCStrategyWorkerState,PROBE_INTERVAL,_status,
)
from execution.test_btc_canonical_strategy_observation_v1 import archive


def wait_done(worker,as_of):
    # Windows spawn/import time varies under full-suite and recorder load.
    # Poll responsiveness has a separate strict assertion; this helper only
    # waits for the isolated child to finish its bounded replay.
    for _ in range(500):
        value=worker.poll(as_of=as_of)
        if value.state is not BTCStrategyWorkerState.EVALUATING:return value
        time.sleep(.01)
    raise AssertionError("worker did not finish")


def test_worker_never_blocks_poll_and_atomically_publishes_ready(tmp_path):
    as_of=archive(tmp_path/"archive");release=threading.Event()
    def evaluator(*,as_of):
        release.wait(2)
        return observe_btc_canonical_strategy(archive_root=tmp_path/"archive",
            snapshot_root=tmp_path/"snapshots",as_of=as_of)
    worker=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"status.json",evaluator=evaluator)
    before=time.monotonic();assert worker.poll(as_of=as_of).state is BTCStrategyWorkerState.IDLE
    assert time.monotonic()-before<.2
    assert worker.poll(as_of=as_of).state is BTCStrategyWorkerState.EVALUATING
    release.set();ready=wait_done(worker,as_of)
    assert ready.state is BTCStrategyWorkerState.READY and not ready.actionable
    assert ready.result_outcome=="NO_SETUP"
    assert ready.decision_reason=="OUTCOME_NO_SETUP"
    assert isinstance(ready.qualification_present,bool)
    assert isinstance(ready.entry_zone_present,bool)
    document=json.loads((tmp_path/"status.json").read_text())
    assert document["status_id"]==ready.status_id and document["trading_authority"] is False
    assert document["decision_reason"]=="OUTCOME_NO_SETUP"
    stable_status,stable_observation=worker.ready_observation(as_of=as_of)
    assert stable_status==ready and stable_observation.observation_id==ready.observation_id


def test_running_evaluation_does_not_repeat_archive_probe(tmp_path):
    as_of=archive(tmp_path/"archive");release=threading.Event();probes=[]
    baseline=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"baseline.json")
    def probe(*,as_of):probes.append(as_of);return baseline.probe(as_of=as_of)
    def evaluator(*,as_of):
        release.wait(2)
        return observe_btc_canonical_strategy(archive_root=tmp_path/"archive",
            snapshot_root=tmp_path/"snapshots",as_of=as_of)
    worker=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"status.json",
        evaluator=evaluator,probe=probe)
    assert worker.poll(as_of=as_of).state is BTCStrategyWorkerState.IDLE
    before=time.monotonic()
    for _ in range(10):assert worker.poll(as_of=as_of).state is BTCStrategyWorkerState.EVALUATING
    assert len(probes)==1 and time.monotonic()-before<.2
    release.set();worker._thread.join(timeout=5)


def test_probe_interval_begins_when_result_is_published(tmp_path,monkeypatch):
    as_of=archive(tmp_path/"archive");release=threading.Event();clock=[0.0]
    import execution.btc_canonical_strategy_worker_v1 as module
    monkeypatch.setattr(module.time,"monotonic",lambda:clock[0])
    observation=observe_btc_canonical_strategy(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",as_of=as_of)
    def evaluator(**_):release.wait(2);return observation
    worker=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"status.json",
        evaluator=evaluator,probe=lambda **_:(observation.one_minute.reference.sha256,
            observation.five_minute.reference.sha256))
    assert worker.poll(as_of=as_of).state is BTCStrategyWorkerState.IDLE
    clock[0]=PROBE_INTERVAL.total_seconds()+5;release.set();worker._thread.join(timeout=5)
    assert worker.poll(as_of=as_of).state is BTCStrategyWorkerState.READY


def test_failure_is_sanitized_and_never_actionable(tmp_path):
    as_of=archive(tmp_path/"archive")
    def fail(**_):raise RuntimeError("secret details must not persist")
    worker=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"status.json",evaluator=fail)
    worker.poll(as_of=as_of);failed=wait_done(worker,as_of)
    assert failed.state is BTCStrategyWorkerState.FAILED
    assert failed.failure_code=="RuntimeError" and not failed.actionable
    assert "secret details" not in (tmp_path/"status.json").read_text()


def test_actionable_ready_status_explains_complete_admission(tmp_path):
    from execution.test_btc_canonical_paper_reservation_bridge_v1 import actionable,running,T
    observation=actionable(running(tmp_path))
    status=_status(BTCStrategyWorkerState.READY,T,observation)
    assert status.actionable is True
    assert status.result_outcome=="ARMED_CONTINUATION"
    assert status.qualification_present is True and status.entry_zone_present is True
    assert status.decision_reason=="ACTIONABLE"


def test_nonactionable_status_retains_exact_canonical_reason(tmp_path):
    from backtesting.orchestrator import EvaluationOutcome
    as_of=archive(tmp_path/"archive")
    observation=observe_btc_canonical_strategy(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",as_of=as_of)
    fact=replace(observation.result.setup_fact,
        outcome=EvaluationOutcome.CANDIDATE,canonical_reason="MISSING_ACTIVE_OTE")
    result=replace(observation.result,outcome=EvaluationOutcome.CANDIDATE,setup_fact=fact)
    status=_status(BTCStrategyWorkerState.READY,as_of,replace(observation,result=result))
    assert status.actionable is False
    assert status.decision_reason=="OUTCOME_CANDIDATE:MISSING_ACTIVE_OTE"


def test_stale_observation_is_not_published_ready(tmp_path):
    as_of=archive(tmp_path/"archive")
    worker=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"status.json")
    worker.poll(as_of=as_of);wait_done(worker,as_of)
    stale=worker.poll(as_of=as_of+timedelta(seconds=91))
    assert stale.state in {BTCStrategyWorkerState.IDLE,BTCStrategyWorkerState.FAILED}
    assert not stale.actionable
    worker.close()


def test_worker_has_no_order_or_network_surface():
    source=__import__("inspect").getsource(
        __import__("execution.btc_canonical_strategy_worker_v1",fromlist=["*"])).lower()
    for prohibited in ("requests","urllib","websocket","private_key","place_order","submit_order"):
        assert prohibited not in source
    assert "daemon=true" in source and "trading_authority: bool=false" in source


def test_process_result_receiver_drains_before_process_completion(tmp_path):
    """Large child messages must be consumed without blocking the control poller."""
    as_of=archive(tmp_path/"archive")
    worker=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"status.json")
    worker.poll(as_of=as_of)
    assert worker._receiver is not None and worker._receiver.name==(
        "btc-canonical-strategy-result-receiver")
    ready=wait_done(worker,as_of)
    assert ready.state is BTCStrategyWorkerState.READY
    assert worker._receiver.is_alive() and worker._process.is_alive()
    worker.close()
    assert worker._receiver is None and worker._process is None and worker._pipe is None


def test_process_worker_reuses_unchanged_snapshot_without_second_replay(tmp_path):
    as_of=archive(tmp_path/"archive")
    worker=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"status.json")
    worker.poll(as_of=as_of);ready=wait_done(worker,as_of)
    assert ready.state is BTCStrategyWorkerState.READY
    process=worker._process;commands=worker._commands
    completed=worker._completed_monotonic
    # Expire only the cheap probe interval.  The immutable source pair is
    # unchanged, so polling must refresh reuse without sending another job.
    worker._completed_monotonic=completed-PROBE_INTERVAL.total_seconds()-1
    assert worker.poll(as_of=as_of).state is BTCStrategyWorkerState.IDLE
    assert worker._process is process and worker._commands is commands
    assert worker._evaluating is False
    reused=worker.poll(as_of=as_of)
    assert reused.state is BTCStrategyWorkerState.READY
    assert reused.observation_id==ready.observation_id
    worker.close()


def test_status_history_is_durable_hash_chained_and_non_authoritative(tmp_path):
    as_of=archive(tmp_path/"archive");history=tmp_path/"history.jsonl"
    worker=BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots",status_path=tmp_path/"status.json",
        status_history_path=history)
    worker.poll(as_of=as_of);wait_done(worker,as_of);worker.close()
    events=[json.loads(line) for line in history.read_text().splitlines()]
    assert len(events)>=2
    previous=None
    for sequence,event in enumerate(events):
        event_id=event.pop("event_id")
        assert event["sequence"]==sequence and event["previous_event_id"]==previous
        assert event["trading_authority"] is False
        if event["state"]=="READY":
            assert event["result_outcome"]=="NO_SETUP"
            assert event["decision_reason"]=="OUTCOME_NO_SETUP"
        assert event_id==hashlib.sha256(json.dumps(event,sort_keys=True,
            separators=(",",":")).encode()).hexdigest()
        previous=event_id
    with __import__("pytest").raises(Exception,match="history already exists"):
        BTCCanonicalStrategyWorkerV1(archive_root=tmp_path/"archive",
            snapshot_root=tmp_path/"snapshots-2",status_path=tmp_path/"status-2.json",
            status_history_path=history)
