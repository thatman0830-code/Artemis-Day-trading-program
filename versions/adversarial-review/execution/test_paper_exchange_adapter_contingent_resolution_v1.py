from dataclasses import replace

import pytest

from execution.paper_exchange_adapter_checkpoint_v1 import (
    PaperAdapterCheckpointStoreV1,
    adapter_checkpoint_bytes,
    adapter_from_bytes,
)
from execution.paper_exchange_adapter_v1 import (
    PaperAdapterCommandV1,
    PaperAdapterPairReceiptV1,
    PaperAdapterReason,
)
from execution.paper_gateway_v2 import PaperContingentResolutionV1, PaperOrderState
from execution.test_paper_exchange_adapter_contingent_v1 import adapter, command
from execution.test_paper_gateway_contingent_resolution_v1 import resolution
from execution.test_paper_gateway_contingent_v1 import pair
from execution.test_paper_gateway_v2 import sha


def prepared(quantity="1"):
    initial = adapter()
    item = pair()
    admitted, pair_receipt = initial.execute(command(initial, item))
    records = tuple(
        next(record for record in admitted.gateway.records if record.paper_order_id == order_id)
        for order_id in pair_receipt.paper_order_ids
    )
    value = resolution(item, records, quantity)
    resolve_command = PaperAdapterCommandV1(
        sha(f"resolve-{quantity}"),
        admitted.gateway.snapshot_id,
        contingent_resolution=value,
    )
    return admitted, resolve_command


def with_pair_id(value, pair_id):
    return PaperContingentResolutionV1.create(
        pair_id=pair_id,
        paper_order_ids=value.paper_order_ids,
        fill=value.fill,
        cancellations=value.cancellations,
    )


@pytest.mark.parametrize("quantity", ["1", "0.4"])
def test_resolution_is_one_durable_adapter_transition(quantity):
    admitted, resolve_command = prepared(quantity)
    updated, receipt = admitted.execute(resolve_command)

    assert type(receipt) is PaperAdapterPairReceiptV1
    assert receipt.accepted
    assert receipt.reason is PaperAdapterReason.CONTINGENT_RESOLUTION_APPLIED
    assert len(updated.receipts) == len(admitted.receipts) + 1
    assert all(
        record.state in (PaperOrderState.FILLED, PaperOrderState.CANCELLED)
        for record in updated.gateway.records
    )

    replayed, replay = updated.execute(resolve_command)
    assert replayed is updated
    assert replay.reason is PaperAdapterReason.IDEMPOTENT_REPLAY
    assert replay.paper_order_ids == receipt.paper_order_ids


@pytest.mark.parametrize("change", ["pair", "order"])
def test_resolution_must_bind_to_previously_accepted_pair_receipt(change):
    admitted, resolve_command = prepared()
    value = resolve_command.contingent_resolution
    if change == "pair":
        foreign = with_pair_id(value, sha("foreign-pair"))
    else:
        foreign = PaperContingentResolutionV1.create(
            pair_id=value.pair_id,
            paper_order_ids=tuple(reversed(value.paper_order_ids)),
            fill=value.fill,
            cancellations=value.cancellations,
        )
    attempted, receipt = admitted.execute(
        replace(
            resolve_command,
            command_id=sha("foreign-resolution-command"),
            contingent_resolution=foreign,
        )
    )

    assert not receipt.accepted
    assert receipt.reason is PaperAdapterReason.GATEWAY_REJECTED
    assert attempted.gateway is admitted.gateway
    assert len(attempted.receipts) == len(admitted.receipts) + 1
    assert all(record.state is PaperOrderState.ACCEPTED for record in attempted.gateway.records)


def test_resolution_command_conflict_and_stale_snapshot_do_not_mutate_adapter():
    admitted, resolve_command = prepared()
    updated, _ = admitted.execute(resolve_command)
    changed = replace(
        resolve_command,
        contingent_resolution=with_pair_id(
            resolve_command.contingent_resolution, sha("different-pair")
        ),
    )
    same, conflict = updated.execute(changed)
    assert same is updated
    assert conflict.reason is PaperAdapterReason.COMMAND_CONFLICT

    stale, rejected = admitted.execute(
        replace(
            resolve_command,
            command_id=sha("stale-resolution"),
            expected_gateway_snapshot_id=sha("stale-snapshot"),
        )
    )
    assert stale is admitted
    assert rejected.reason is PaperAdapterReason.STALE_GATEWAY_SNAPSHOT


def test_resolved_adapter_checkpoint_round_trip_and_store_retry(tmp_path):
    admitted, resolve_command = prepared("0.4")
    updated, _ = admitted.execute(resolve_command)
    assert adapter_from_bytes(adapter_checkpoint_bytes(updated)) == updated

    store = PaperAdapterCheckpointStoreV1(tmp_path / "adapter.json")
    store.initialize(admitted)
    persisted, first = store.execute(resolve_command)
    replayed, replay = store.execute(resolve_command)
    assert first.accepted
    assert replay.reason is PaperAdapterReason.IDEMPOTENT_REPLAY
    assert persisted == replayed == store.load()
    assert all(
        record.state is PaperOrderState.CANCELLED
        for record in persisted.gateway.records
    )


def test_command_requires_exactly_one_action():
    admitted, resolve_command = prepared()
    with pytest.raises(ValueError, match="exactly one"):
        replace(resolve_command, contingent_pair=pair())
