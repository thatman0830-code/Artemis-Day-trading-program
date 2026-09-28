from datetime import datetime,timezone
import hashlib,json
from types import SimpleNamespace

import pytest

from execution.btc_canonical_prelaunch_benchmark_v1 import (
    BTCCanonicalPrelaunchBenchmarkError,run_benchmark,
)
from execution.btc_canonical_strategy_worker_v1 import BTCStrategyWorkerState


NOW=datetime(2026,9,5,19,0,tzinfo=timezone.utc)


class Process:
    def is_alive(self):return True


class Worker:
    instances=[]
    def __init__(self,**kwargs):
        self.kwargs=kwargs;self._process=Process();self.calls=0;self.closed=False
        self.observation=SimpleNamespace(observation_id="a"*64,
            result=SimpleNamespace(id="b"*64),
            one_minute=SimpleNamespace(reference=SimpleNamespace(sha256="c"*64)),
            five_minute=SimpleNamespace(reference=SimpleNamespace(sha256="d"*64)),
            candle_count=2000,actionable=False)
        self.__class__.instances.append(self)
    def ready_observation(self,**_):
        self.calls+=1
        state=BTCStrategyWorkerState.IDLE if self.calls==1 else BTCStrategyWorkerState.READY
        return SimpleNamespace(state=state),(self.observation if state is BTCStrategyWorkerState.READY else None)
    def close(self):self.closed=True;self._process=None


def clock(values):
    iterator=iter(values)
    return lambda:next(iterator)


def test_benchmark_measures_isolated_ready_reuse_without_session_authority(tmp_path):
    Worker.instances.clear()
    document=run_benchmark(repository=tmp_path,output_path=tmp_path/"result.json",
        timeout_seconds=1,clock=clock([0,.1,.2,.3,.301,.302]),utc_reader=lambda:NOW,
        waiter=lambda _:None,worker_factory=Worker)
    body={key:value for key,value in document.items() if key!="benchmark_id"}
    assert document["benchmark_id"]==hashlib.sha256(json.dumps(body,sort_keys=True,
        separators=(",",":")).encode()).hexdigest()
    assert document["cold_ready_seconds"]==.3
    assert document["unchanged_reuse_seconds"]==.001
    assert document["process_isolated"] is True and document["worker_stopped"] is True
    assert document["paper_session_started"] is False and document["command_count"]==0
    assert document["reservation_created"] is False and document["trading_authority"] is False
    assert json.loads((tmp_path/"result.json").read_text())==document
    assert Worker.instances[0].closed and Worker.instances[0].calls==3


def test_benchmark_fails_closed_and_stops_failed_worker(tmp_path):
    class FailedWorker(Worker):
        instances=[]
        def ready_observation(self,**_):
            return SimpleNamespace(state=BTCStrategyWorkerState.FAILED),None
    with pytest.raises(BTCCanonicalPrelaunchBenchmarkError,match="failed"):
        run_benchmark(repository=tmp_path,output_path=tmp_path/"result.json",
            timeout_seconds=1,clock=clock([0,.1]),utc_reader=lambda:NOW,
            waiter=lambda _:None,worker_factory=FailedWorker)
    assert FailedWorker.instances[0].closed and not (tmp_path/"result.json").exists()


def test_benchmark_times_out_without_creating_evidence(tmp_path):
    Worker.instances.clear()
    with pytest.raises(BTCCanonicalPrelaunchBenchmarkError,match="timed out"):
        run_benchmark(repository=tmp_path,output_path=tmp_path/"result.json",
            timeout_seconds=1,clock=clock([0,1]),utc_reader=lambda:NOW,
            waiter=lambda _:None,worker_factory=Worker)
    assert Worker.instances[0].closed and Worker.instances[0].calls==0
    assert not (tmp_path/"result.json").exists()


def test_benchmark_has_no_order_provider_or_network_surface():
    source=__import__("inspect").getsource(
        __import__("execution.btc_canonical_prelaunch_benchmark_v1",fromlist=["*"])).lower()
    for prohibited in ("requests","urllib","websocket","private_key","place_order",
            "submit_order","paperexchangeadapter","paper_session_launcher"):
        assert prohibited not in source
    assert '"trading_authority":false' in source
