"""Single-use actionable strategy admission for the supervised BTC paper runtime."""
from __future__ import annotations

from pathlib import Path

from execution.btc_canonical_strategy_worker_v1 import (
    BTCCanonicalStrategyWorkerV1,BTCStrategyWorkerState,
)
from execution.btc_canonical_paper_reservation_bridge_v1 import (
    prepare_btc_canonical_paper_reservation,prepare_reserved_btc_paper_runtime_input,
)
from execution.supervised_btc_paper_session_assembly_v1 import SupervisedBTCPaperSessionAssemblyV1


class BTCCanonicalPaperCycleInputError(RuntimeError):pass


class BTCCanonicalPaperCycleInputV1:
    """Return no-signal cycles until one fresh actionable observation is ready."""
    def __init__(self,*,assembly,worker,launch):
        if (not isinstance(assembly,SupervisedBTCPaperSessionAssemblyV1)
                or not isinstance(worker,BTCCanonicalStrategyWorkerV1)
                or not isinstance(launch,dict)
                or worker.archive_root!=Path(assembly.archive_root).absolute()
                or worker.snapshot_root!=Path(assembly.snapshot_root).absolute()):
            raise BTCCanonicalPaperCycleInputError("cycle input dependencies or paths differ")
        self.assembly=assembly;self.worker=worker;self.launch=dict(launch)
        self.issued_observation_id=None

    def __call__(self,*,assembly,as_of):
        if assembly is not self.assembly or assembly.assembly_id!=self.assembly.assembly_id:
            raise BTCCanonicalPaperCycleInputError("cycle assembly identity changed")
        status,observation=self.worker.ready_observation(as_of=as_of)
        if status.state is BTCStrategyWorkerState.FAILED:
            raise BTCCanonicalPaperCycleInputError("canonical strategy evaluation failed")
        if observation is None or not status.actionable:
            return assembly.no_signal_input(as_of=as_of)
        if self.issued_observation_id is not None:
            if observation.observation_id!=self.issued_observation_id:
                raise BTCCanonicalPaperCycleInputError("second actionable observation requires a new session")
            return assembly.no_signal_input(as_of=as_of)
        empty=assembly.session.reservation.load()
        if empty["body"]["state"]!="EMPTY":
            raise BTCCanonicalPaperCycleInputError("fresh empty reservation required")
        reservation=prepare_btc_canonical_paper_reservation(assembly=assembly,
            observation=observation,as_of=as_of,
            expected_reservation_checkpoint_id=empty["checkpoint_id"])
        result=prepare_reserved_btc_paper_runtime_input(assembly=assembly,reservation=reservation,
            launch=self.launch,requested_at=as_of)
        self.issued_observation_id=observation.observation_id
        return result
