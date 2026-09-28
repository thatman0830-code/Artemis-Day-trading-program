"""Lazy canonical-strategy input binding for one active BTC paper session."""
from __future__ import annotations

import hashlib,json
from pathlib import Path

from execution.btc_canonical_paper_cycle_input_v1 import BTCCanonicalPaperCycleInputV1
from execution.btc_canonical_strategy_worker_v1 import BTCCanonicalStrategyWorkerV1
from execution.supervised_btc_paper_session_assembly_v1 import SupervisedBTCPaperSessionAssemblyV1
from execution.supervised_paper_launch_decision_v1 import DECISION_ENVELOPE_VERSION


class BTCCanonicalPaperLauncherInputError(RuntimeError):pass


def _envelope(assembly,evidence_id):
    decision=assembly.session.launch_decision;confirmation=assembly.session.confirmation
    if decision is None or decision.eligible is not True:
        raise BTCCanonicalPaperLauncherInputError("active eligible launch decision required")
    body={"schema_version":DECISION_ENVELOPE_VERSION,
        "evaluated_at":decision.evaluated_at.isoformat(),"evidence_id":evidence_id,
        "confirmation_id":confirmation.confirmation_id,"launch_id":decision.launch_id,
        "eligible":True,"reasons":[],"expires_at":decision.expires_at.isoformat(),
        "permitted_markets":list(decision.permitted_markets),
        "maximum_session_seconds":int(decision.maximum_session_duration.total_seconds()),
        "maximum_commands":decision.maximum_commands,
        "maximum_order_notional":str(decision.maximum_order_notional),
        "maximum_gross_exposure":str(decision.maximum_gross_exposure),
        "advisory_only":decision.advisory_only,
        "live_trading_permitted":decision.live_trading_permitted,
        "trading_authority":decision.trading_authority}
    identity=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),
        default=str).encode()).hexdigest()
    return {**body,"decision_envelope_id":identity}


class BTCCanonicalPaperLauncherInputV1:
    """Start the worker before launch, but bind commands only after launch eligibility."""
    def __init__(self,*,assembly,evidence_id,status_path,prime_status_path=None,worker=None):
        if (not isinstance(assembly,SupervisedBTCPaperSessionAssemblyV1)
                or not isinstance(evidence_id,str)or len(evidence_id)!=64
                or any(char not in "0123456789abcdef" for char in evidence_id)):
            raise BTCCanonicalPaperLauncherInputError("launcher input identity is invalid")
        self.assembly=assembly;self.evidence_id=evidence_id
        self.status_path=Path(status_path).absolute()
        worker_status_path=Path(prime_status_path or status_path).absolute()
        self.worker=(worker or BTCCanonicalStrategyWorkerV1(archive_root=assembly.archive_root,
            snapshot_root=assembly.snapshot_root,status_path=worker_status_path))
        if (not isinstance(self.worker,BTCCanonicalStrategyWorkerV1)
                or self.worker.archive_root!=Path(assembly.archive_root).absolute()
                or self.worker.snapshot_root!=Path(assembly.snapshot_root).absolute()):
            raise BTCCanonicalPaperLauncherInputError("canonical worker paths differ")
        self.reader=None

    def prime(self,*,as_of):
        """Warm the isolated observer without creating any paper command."""
        if self.reader is not None:
            raise BTCCanonicalPaperLauncherInputError("active reader cannot be primed")
        return self.worker.poll(as_of=as_of)

    def __call__(self,*,assembly,as_of):
        if assembly is not self.assembly:
            raise BTCCanonicalPaperLauncherInputError("launcher assembly identity changed")
        if self.reader is None:
            self.worker.status_path=self.status_path
            self.reader=BTCCanonicalPaperCycleInputV1(assembly=assembly,worker=self.worker,
                launch=_envelope(assembly,self.evidence_id))
        return self.reader(assembly=assembly,as_of=as_of)

    def close(self):self.worker.close()
