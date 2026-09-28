from dataclasses import replace
from decimal import Decimal
import json

import pytest

from execution.paper_exchange_adapter_checkpoint_v1 import (
    PaperAdapterCheckpointError,PaperAdapterCheckpointStoreV1,adapter_checkpoint_bytes,
    adapter_from_bytes,
)
from execution.paper_exchange_adapter_v1 import (
    PaperAdapterCommandV1,PaperAdapterPairReceiptV1,PaperAdapterReason,PaperExchangeAdapterV1,
)
from execution.paper_gateway_v2 import PaperGatewayPolicyV1,PaperGatewaySnapshotV1
from execution.test_paper_gateway_contingent_v1 import pair
from execution.test_paper_gateway_v2 import NOW,sha
from datetime import timedelta


def adapter():
    policy=PaperGatewayPolicyV1(Decimal(500),Decimal(800),2,timedelta(seconds=5))
    return PaperExchangeAdapterV1.create(PaperGatewaySnapshotV1.create(policy))


def command(value,item=None,name="pair-command"):
    return PaperAdapterCommandV1(sha(name),value.gateway.snapshot_id,
        contingent_pair=item or pair())


def test_pair_command_is_one_adapter_transition_and_exact_replay():
    initial=adapter();cmd=command(initial)
    updated,receipt=initial.execute(cmd)
    assert type(receipt) is PaperAdapterPairReceiptV1 and receipt.accepted
    assert receipt.reason is PaperAdapterReason.CONTINGENT_PAIR_APPLIED
    assert len(updated.gateway.records)==2 and len(updated.receipts)==1
    replayed,replay=updated.execute(cmd)
    assert replayed is updated and replay.reason is PaperAdapterReason.IDEMPOTENT_REPLAY
    assert replay.paper_order_ids==receipt.paper_order_ids


def test_stale_or_rejected_pair_is_one_durable_negative_receipt():
    initial=adapter();cmd=command(initial)
    stale,receipt=initial.execute(replace(cmd,expected_gateway_snapshot_id=sha("old")))
    assert stale is initial and receipt.reason is PaperAdapterReason.STALE_GATEWAY_SNAPSHOT
    bad=pair();bad=type(bad).create(replace(bad.adverse,authorized=False),bad.favorable)
    updated,rejected=initial.execute(command(initial,bad,"bad-pair-command"))
    assert not rejected.accepted and len(updated.gateway.records)==0 and len(updated.receipts)==1
    replayed,replay=updated.execute(command(initial,bad,"bad-pair-command"))
    assert replayed is updated and replay.reason is PaperAdapterReason.IDEMPOTENT_REPLAY


def test_pair_checkpoint_round_trip_and_store_retry(tmp_path):
    initial=adapter();cmd=command(initial);updated,receipt=initial.execute(cmd)
    assert adapter_from_bytes(adapter_checkpoint_bytes(updated))==updated
    store=PaperAdapterCheckpointStoreV1(tmp_path/"adapter.json");store.initialize(initial)
    persisted,first=store.execute(cmd);replayed,replay=store.execute(cmd)
    assert persisted==replayed==store.load()
    assert len(persisted.gateway.records)==2 and len(persisted.receipts)==1
    assert first.accepted and replay.reason is PaperAdapterReason.IDEMPOTENT_REPLAY


def test_pair_receipt_tamper_fails_even_with_recomputed_outer_hash():
    import hashlib
    initial=adapter();updated,_=initial.execute(command(initial))
    doc=json.loads(adapter_checkpoint_bytes(updated));doc["payload"]["receipts"][0]["pair_id"]=sha("bad")
    canonical=lambda value:json.dumps(value,sort_keys=True,separators=(",",":")).encode()
    doc["payload_sha256"]=hashlib.sha256(canonical(doc["payload"])).hexdigest()
    with pytest.raises(PaperAdapterCheckpointError):adapter_from_bytes(canonical(doc))


def test_pair_command_conflict_does_not_mutate_adapter():
    initial=adapter();cmd=command(initial);updated,_=initial.execute(cmd)
    other=pair();other=type(other).create(other.adverse,
        replace(other.favorable,reference_price=Decimal("100.5")))
    same,receipt=updated.execute(replace(cmd,contingent_pair=other))
    assert same is updated and receipt.reason is PaperAdapterReason.COMMAND_CONFLICT
