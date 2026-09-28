from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import hashlib
import json

import pytest

from execution.bounded_paper_session_v1 import BoundedPaperSessionV1, BoundedPaperSessionError
from execution.supervised_paper_launch_evidence_v1 import OwnerSupervisionConfirmationV1
from execution.supervised_paper_workflow_v1 import SupervisedPaperCycleV1
from execution.supervised_paper_performance_v1 import VerifiedPaperFillV1, SupervisedPaperPerformanceError
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1
from execution.paper_gateway_v2 import PaperSubmissionV1, PaperOrderEventV1, PaperEventKind
from execution.test_supervised_paper_launch_evidence_v1 import document
from execution.test_supervised_paper_workflow_v1 import initial
from execution.test_paper_performance_ledger_v1 import T, H, accounting, gateway_fill
from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderType, TimeInForce, OrderSide
from backtesting.execution_accounting_v2.accounting import PriceEvidenceV2


def driver(tmp_path, change=None, *, initial_adapter=None, initial_accounting=None, as_of=T):
    root = tmp_path / "session"; root.mkdir()
    value = document()
    value.update(collected_at=as_of.isoformat(), btc_heartbeat_at=as_of.isoformat())
    if change:
        value.update(change)
    value.pop("evidence_id")
    value["evidence_id"] = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = tmp_path / "evidence.json"; path.write_text(json.dumps(value))
    confirm = OwnerSupervisionConfirmationV1.create(confirmed_at=as_of, expires_at=as_of+timedelta(minutes=5),
        repository_checkpoint="a"*64, owner_supervision_confirmed=True, stop_control_verified=True,
        maximum_session_seconds=300, maximum_commands=5,
        maximum_order_notional=Decimal("100"), maximum_gross_exposure=Decimal("100"))
    return BoundedPaperSessionV1(root=root, initial_adapter=initial() if initial_adapter is None else initial_adapter,
        initial_accounting=accounting() if initial_accounting is None else initial_accounting,
        evidence_path=path, confirmation=confirm, expected_checkpoint="a"*64, session_id="1"*32)


def test_btc_perpetual_session_accepts_only_matching_bounded_paper_command(tmp_path):
    from execution.test_btc_perpetual_paper_gateway_bridge_v1 import perpetual_components, launch
    from execution.btc_perpetual_paper_gateway_bridge_v1 import prepare_btc_perpetual_paper_command
    from execution.paper_exchange_adapter_v1 import PaperExchangeAdapterV1
    plan,gateway,now,book=perpetual_components(tmp_path)
    item=driver(tmp_path,initial_adapter=PaperExchangeAdapterV1.create(gateway),initial_accounting=book,as_of=now)
    item.start(now)
    reservation=item.reservation.load()
    assert reservation["body"]["state"]=="EMPTY"
    assert reservation["body"]["submission_authorized"] is False
    assert reservation["body"]["trading_authority"] is False
    command=prepare_btc_perpetual_paper_command(plan=plan,launch=launch(now),
        expected_gateway_snapshot_id=item.workflow.store.load().gateway.snapshot_id,
        requested_at=now,market_data_at=now)
    adapter,receipt,health,_=item.step(SupervisedPaperCycleV1(now,now,command))
    assert receipt.accepted and len(adapter.gateway.records)==1
    assert adapter.gateway.records[0].market=="BTC-PERP"
    assert health.state.value=="HEALTHY" and not health.trading_authority
    result=item.stop(now)
    assert result.state=="STOPPED" and not result.trading_authority


def submit(item, name="one", quantity="0.001", price="50000", market="BTC"):
    intent = OrderIntentV2("order-intent-v2-1", H(name), H("run"), H(name+"action"),
        market, "BTC", None, OrderSide.BUY, Decimal(quantity), OrderType.MARKET,
        TimeInForce.IOC, None, None, T, T, None, None, None, "config", "execution")
    req = PaperSubmissionV1(H(name+"key"), intent, Decimal(price), T, T, H("auth"), True, False)
    return PaperAdapterCommandV1(H(name+"cmd"), item.workflow.store.load().gateway.snapshot_id, submission=req)


@pytest.mark.parametrize("mark_price", ["51000", "300000"])
def test_submission_fill_mark_and_stop_or_exposure_halt_are_durable(tmp_path, mark_price):
    item = driver(tmp_path); item.start(T)
    cmd = submit(item)
    adapter, receipt, _, _ = item.step(SupervisedPaperCycleV1(T, T, cmd))
    assert receipt.accepted
    _, _, source, costs = gateway_fill()
    fill = replace(source, order_id=cmd.submission.intent.order_id, quantity=Decimal("0.001"))
    event = PaperOrderEventV1(H("driver-fill"), adapter.gateway.records[0].paper_order_id,
        PaperEventKind.FILL, fill.fill_time, 0, fill.quantity, False)
    fill_cmd = PaperAdapterCommandV1(H("fillcmd"), adapter.gateway.snapshot_id, event=event)
    item.step(SupervisedPaperCycleV1(fill.fill_time, fill.fill_time, fill_cmd),
        verified_fill=VerifiedPaperFillV1(event, fill, costs))
    mark_time = T + timedelta(seconds=2)
    mark = PriceEvidenceV2("price-evidence-v2-1", H("driver-mark"), "BTC", "BTC", None,
        mark_time, mark_time, Decimal(mark_price), "MARK", H("mark-spec"), "btc-15m-archive-v1")
    if mark_price == "300000":
        with pytest.raises(BoundedPaperSessionError, match="marked gross exposure"):
            item.step(SupervisedPaperCycleV1(mark_time, mark_time), closed_mark=mark)
        assert item.bridge.store.load().snapshot.position.mark_price == Decimal(mark_price)
        assert item.workflow.store.load().gateway.kill_switch_active
        assert not item.workflow.lock_path.exists()
        return
    item.step(SupervisedPaperCycleV1(mark_time, mark_time), closed_mark=mark)
    result = item.stop(mark_time)
    assert result.commands == 2 and result.state == "STOPPED"
    assert not result.trading_authority
    ledger = item.bridge.store.load()
    assert ledger.snapshot.position.signed_quantity == Decimal("0.001")
    assert ledger.snapshot.total_costs == Decimal("3")
    assert ledger.snapshot.position.mark_price == Decimal("51000")
    assert ledger.gateway_snapshot_id == item.workflow.store.load().gateway.snapshot_id
    assert not item.workflow.lock_path.exists()
    with pytest.raises(BoundedPaperSessionError, match="single-use"):
        item.start(mark_time)


@pytest.mark.parametrize("change", [{"repository_clean":False}, {"btc_recorder_health":"BAD"},
    {"repository_checkpoint":"b"*64}])
def test_launch_blocked_before_session_mutation(tmp_path, change):
    item = driver(tmp_path, change)
    with pytest.raises((BoundedPaperSessionError, ValueError)):
        item.start(T)
    assert list(item.workflow.root.iterdir()) == []


@pytest.mark.parametrize("quantity,market", [("0.003", "BTC"), ("0.001", "ES")])
def test_submission_risk_and_market_limits_halt(tmp_path, quantity, market):
    item = driver(tmp_path); item.start(T)
    with pytest.raises(BoundedPaperSessionError):
        item.step(SupervisedPaperCycleV1(T, T, submit(item, quantity=quantity, market=market)))
    assert item.workflow.store.load().gateway.kill_switch_active
    assert not item.workflow.store.load().gateway.records
    assert not item.active


def test_cumulative_notional_not_recycled(tmp_path):
    item = driver(tmp_path); item.start(T)
    item.step(SupervisedPaperCycleV1(T, T, submit(item, "one", quantity="0.002")))
    with pytest.raises(BoundedPaperSessionError, match="notional"):
        item.step(SupervisedPaperCycleV1(T, T, submit(item, "two", quantity="0.002")))
    assert len(item.workflow.store.load().gateway.records) == 1


def test_command_budget_counts_attempts(tmp_path):
    item = driver(tmp_path); item.start(T)
    # Use cancel events to free gateway order slots, never session reservations.
    for index in range(5):
        if index % 2 == 0:
            command = submit(item, str(index), price="100")
        else:
            adapter = item.workflow.store.load()
            event = PaperOrderEventV1(H(str(index)), adapter.gateway.records[-1].paper_order_id,
                PaperEventKind.CANCEL, T, 0, None, False)
            command = PaperAdapterCommandV1(H(str(index)+"cancel"), adapter.gateway.snapshot_id, event=event)
        item.step(SupervisedPaperCycleV1(T, T, command))
    with pytest.raises(BoundedPaperSessionError, match="budget"):
        item.step(SupervisedPaperCycleV1(T, T, submit(item, "six", price="100")))


@pytest.mark.parametrize("seconds", [-1, 300])
def test_time_regression_or_expiry_halts(tmp_path, seconds):
    item = driver(tmp_path); item.start(T)
    now = T + timedelta(seconds=seconds)
    with pytest.raises(BoundedPaperSessionError, match="chronology"):
        item.step(SupervisedPaperCycleV1(now, now))
    assert item.workflow.store.load().gateway.kill_switch_active


def test_external_stop_control_stops_and_releases(tmp_path):
    item = driver(tmp_path); item.start(T)
    item.workflow.stop_path.write_text(json.dumps({"session_id":"1"*32,"stop":True,"trading_authority":False}))
    _, _, health, ledger = item.step(SupervisedPaperCycleV1(T,T))
    assert health.state.value == "STOPPED"
    assert ledger.gateway_snapshot_id == item.workflow.store.load().gateway.snapshot_id
    assert not item.active and not item.workflow.lock_path.exists()


def test_duplicate_command_halts_before_replay(tmp_path):
    item = driver(tmp_path); item.start(T)
    cmd = submit(item)
    item.step(SupervisedPaperCycleV1(T, T, cmd))
    with pytest.raises(BoundedPaperSessionError, match="replay"):
        item.step(SupervisedPaperCycleV1(T, T, cmd))
    assert len(item.workflow.store.load().gateway.records) == 1


def test_tampered_confirmation_rejects(tmp_path):
    item = driver(tmp_path)
    item.confirmation = replace(item.confirmation, confirmation_id="f"*64)
    with pytest.raises(BoundedPaperSessionError, match="confirmation"):
        item.start(T)


def test_nonempty_directory_is_not_reused(tmp_path):
    item = driver(tmp_path)
    retained = item.workflow.root / "retained.txt"
    retained.write_text("preserve")
    with pytest.raises(BoundedPaperSessionError, match="empty"):
        item.start(T)
    assert retained.read_text() == "preserve"
    assert not item.workflow.lock_path.exists()


def test_stop_write_failure_still_halts(tmp_path):
    item = driver(tmp_path); item.start(T)
    item.workflow.stop_path.mkdir()
    with pytest.raises(SupervisedPaperPerformanceError):
        item.stop(T)
    assert item.workflow.store.load().gateway.kill_switch_active
    assert not item.workflow.lock_path.exists()


def test_stale_launch_heartbeat_blocks_each_step(tmp_path):
    item = driver(tmp_path); item.start(T)
    before = item.bridge.store.path.read_bytes()
    now = T + timedelta(seconds=91)
    with pytest.raises(BoundedPaperSessionError, match="BTC_RECORDER_NOT_HEALTHY"):
        item.step(SupervisedPaperCycleV1(now, now))
    assert item.bridge.store.path.read_bytes() == before
    assert item.workflow.store.load().gateway.kill_switch_active
    assert not item.workflow.lock_path.exists()


def test_launch_evidence_is_reloaded_not_cached(tmp_path):
    item = driver(tmp_path); item.start(T)
    item.evidence_path.write_text("corrupt")
    with pytest.raises(ValueError, match="unreadable"):
        item.step(SupervisedPaperCycleV1(T, T))
    assert item.workflow.store.load().gateway.kill_switch_active
    assert not item.active


@pytest.mark.parametrize("fault", ["side", "unknown_order", "future", "notional"])
def test_bad_fill_is_rejected_before_gateway_mutation(tmp_path, fault):
    item = driver(tmp_path); item.start(T)
    cmd = submit(item)
    adapter, _, _, _ = item.step(SupervisedPaperCycleV1(T, T, cmd))
    _, _, source, costs = gateway_fill()
    fill = replace(source, order_id=cmd.submission.intent.order_id, quantity=Decimal("0.001"))
    if fault == "side":
        fill = replace(fill, side=OrderSide.SELL)
    elif fault == "unknown_order":
        fill = replace(fill, order_id=H("unknown"))
    elif fault == "future":
        fill = replace(fill, fill_time=T + timedelta(seconds=2))
    else:
        fill = replace(fill, economic_price=Decimal("150000"))
    event = PaperOrderEventV1(H("bad-fill"), adapter.gateway.records[0].paper_order_id,
        PaperEventKind.FILL, fill.fill_time, 0, fill.quantity, False)
    command = PaperAdapterCommandV1(H("bad-fill-command"), adapter.gateway.snapshot_id, event=event)
    before = item.bridge.store.path.read_bytes()
    now = T + timedelta(seconds=1)
    with pytest.raises(BoundedPaperSessionError):
        item.step(SupervisedPaperCycleV1(now, now, command),
            verified_fill=VerifiedPaperFillV1(event, fill, costs))
    halted = item.workflow.store.load().gateway
    assert halted.records == adapter.gateway.records
    assert halted.records[0].filled_quantity == 0
    assert halted.kill_switch_active and not halted.connected
    assert item.bridge.store.path.read_bytes() == before


def test_expired_confirmation_blocks_start_without_checkpoint(tmp_path):
    item = driver(tmp_path)
    with pytest.raises(ValueError, match="not current"):
        item.start(T + timedelta(minutes=5))
    assert list(item.workflow.root.iterdir()) == []


def test_expired_session_can_still_be_stopped(tmp_path):
    item = driver(tmp_path); item.start(T)
    result = item.stop(T + timedelta(minutes=6))
    assert result.state == "STOPPED"
    assert not item.workflow.store.load().gateway.connected
    assert not item.workflow.lock_path.exists()


@pytest.mark.parametrize("operation", ["step", "stop"])
def test_halt_write_failure_is_explicit_and_disables_driver(tmp_path, monkeypatch, operation):
    item = driver(tmp_path); item.start(T)
    def failed_halt():
        raise OSError("injected halt persistence failure")
    monkeypatch.setattr(item.workflow.store, "halt", failed_halt)
    with pytest.raises(BoundedPaperSessionError, match="unconfirmed") as error:
        if operation == "step":
            item.step(SupervisedPaperCycleV1(T - timedelta(seconds=1), T))
        else:
            item.stop(T - timedelta(seconds=1))
    assert isinstance(error.value.__cause__, OSError)
    assert not item.active
    assert not item.workflow.store.load().gateway.kill_switch_active
    assert not item.workflow.lock_path.exists()
    with pytest.raises(BoundedPaperSessionError, match="not active"):
        item.step(SupervisedPaperCycleV1(T, T))


def test_automatic_recovery_input_rejects(tmp_path):
    item = driver(tmp_path); item.start(T)
    with pytest.raises(BoundedPaperSessionError, match="recovery"):
        item.step(SupervisedPaperCycleV1(T, T, reconciliation_observation=()))
    assert item.workflow.store.load().gateway.kill_switch_active
