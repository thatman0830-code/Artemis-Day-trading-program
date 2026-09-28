from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import hashlib
import json

import pytest

from backtesting.execution_accounting_v2.accounting import InstrumentAccountingLedgerV2
from backtesting.execution_accounting_v2.risk_sessions import PortfolioRiskContextV2, RiskLimitsV2, VerifiedSessionV2, RISK_POLICY_VERSION
from execution.btc_perpetual_paper_gateway_bridge_v1 import *
from execution.paper_exchange_adapter_checkpoint_v1 import PaperAdapterCheckpointStoreV1
from execution.paper_exchange_adapter_v1 import PaperExchangeAdapterV1, PaperAdapterReason
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from execution.strategy_paper_pretrade_v1 import PaperSizingPolicyV1, plan_strategy_paper_pretrade
from execution.test_btc_perpetual_strategy_intent_v1 import arguments
from execution.test_paper_performance_ledger_v1 import accounting, H
from execution.test_supervised_paper_workflow_v1 import initial

D=Decimal


def perpetual_components(tmp_path):
    strategy=arguments(tmp_path); now=strategy["now"]
    strategy.pop("quantity"); strategy.pop("quantity_evidence_sha256")
    original=accounting(); instrument=strategy["economics"].instrument
    policy=replace(original.policy,perpetual_capability_enabled=True)
    book=InstrumentAccountingLedgerV2.create(run_id=original.run_id,starting_cash=D(10000),
        instrument=instrument,policy=policy,margin_specification=strategy["margin"])
    strategy["run_id"]=book.run_id; gateway=initial().gateway
    performance=PaperPerformanceLedgerV1.create(book,gateway)
    context=PortfolioRiskContextV2.create(run_id=book.run_id,as_of=now,equity=book.snapshot.equity,
        gross_exposure_before=D(0),net_exposure_before=D(0),session_reference_equity=D(10000),
        session_peak_equity=D(10000),source_snapshot_ids=(book.snapshot.snapshot_id,))
    session=VerifiedSessionV2.create(market="BTC-PERP",instrument_id="BTC",contract_id="BTC-PERP",
        session_date=now.date(),timezone="UTC",open_time=now,close_time=now+timedelta(hours=1),
        effective_from=now,effective_to=now+timedelta(days=1),calendar_version="fixture",source_ids=(H("session"),))
    limits=RiskLimitsV2.create(run_id=book.run_id,market="BTC-PERP",instrument_id="BTC",contract_id="BTC-PERP",
        effective_from=now,effective_to=now+timedelta(hours=1),max_gross_exposure=D(200),max_net_exposure=D(200),
        max_position_quantity=D(2),max_concentration=D(1),max_leverage=D(1),max_initial_margin=D(100),
        max_session_loss=D(100),max_drawdown=D(100),flatten_buffer_seconds=60,
        risk_policy_version=RISK_POLICY_VERSION,source_ids=(H("limits"),))
    sizing=PaperSizingPolicyV1(now,now+timedelta(hours=1),D("0.001"),D(5),D(1),D("0.5"),H("sizing"))
    plan=plan_strategy_paper_pretrade(strategy_inputs=strategy,performance=performance,gateway=gateway,
        context=context,limits=limits,session=session,sizing_policy=sizing,source_bar_id=H("bar"))
    return plan,gateway,now,book


def prepared(tmp_path):
    plan,gateway,now,_=perpetual_components(tmp_path)
    return plan,gateway,now


def launch(now, **changes):
    body={"schema_version":"supervised-paper-launch-decision-envelope-v1","evaluated_at":now.isoformat(),
        "evidence_id":H("evidence"),"confirmation_id":H("confirmation"),"launch_id":H("launch"),
        "eligible":True,"reasons":[],"expires_at":(now+timedelta(minutes=5)).isoformat(),
        "permitted_markets":["BTC-PERP"],"maximum_session_seconds":300,"maximum_commands":5,
        "maximum_order_notional":"100","maximum_gross_exposure":"200","advisory_only":True,
        "live_trading_permitted":False,"trading_authority":False}
    body.update(changes)
    return {**body,"decision_envelope_id":hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()}


def command(tmp_path, **changes):
    plan,gateway,now=prepared(tmp_path)
    values=dict(plan=plan,launch=launch(now),expected_gateway_snapshot_id=gateway.snapshot_id,
        requested_at=now,market_data_at=now); values.update(changes)
    return prepare_btc_perpetual_paper_command(**values),plan,gateway,now


def test_creates_deterministic_paper_only_command(tmp_path):
    result,plan,gateway,now=command(tmp_path)
    assert result==command(tmp_path)[0]
    assert result.submission.intent==plan.strategy_intent.intent
    assert result.submission.authorized and not result.trading_authority and not result.submission.trading_authority
    assert result.expected_gateway_snapshot_id==gateway.snapshot_id


def test_durable_execution_and_replay_are_idempotent(tmp_path):
    result,_,gateway,_=command(tmp_path)
    store=PaperAdapterCheckpointStoreV1(tmp_path/"adapter.json")
    store.initialize(PaperExchangeAdapterV1.create(gateway))
    updated,receipt=store.execute(result)
    assert receipt.accepted and receipt.reason is PaperAdapterReason.SUBMISSION_APPLIED
    replayed,replay=store.execute(result)
    assert replay.reason is PaperAdapterReason.IDEMPOTENT_REPLAY
    assert replayed==updated==store.load() and len(updated.gateway.records)==1


@pytest.mark.parametrize("change",[
    {"permitted_markets":["BTC"]},{"eligible":False},{"reasons":["STALE_EVIDENCE"]},
    {"advisory_only":False},{"live_trading_permitted":True},{"trading_authority":True},
    {"maximum_order_notional":"99"},{"maximum_session_seconds":0},
])
def test_invalid_or_legacy_launch_decisions_fail_closed(tmp_path,change):
    plan,gateway,now=prepared(tmp_path)
    with pytest.raises(BTCPerpetualPaperGatewayBridgeError):
        prepare_btc_perpetual_paper_command(plan=plan,launch=launch(now,**change),
            expected_gateway_snapshot_id=gateway.snapshot_id,requested_at=now,market_data_at=now)


def test_tampering_stale_data_and_risk_rejection_fail_closed(tmp_path):
    plan,gateway,now=prepared(tmp_path); permit=launch(now); permit["maximum_commands"]=4
    with pytest.raises(BTCPerpetualPaperGatewayBridgeError,match="integrity"):
        prepare_btc_perpetual_paper_command(plan=plan,launch=permit,
            expected_gateway_snapshot_id=gateway.snapshot_id,requested_at=now,market_data_at=now)
    with pytest.raises(BTCPerpetualPaperGatewayBridgeError,match="market-data"):
        prepare_btc_perpetual_paper_command(plan=plan,launch=launch(now),
            expected_gateway_snapshot_id=gateway.snapshot_id,requested_at=now,
            market_data_at=now-timedelta(seconds=6))
    rejected=replace(plan,risk_eligible=False)
    with pytest.raises(BTCPerpetualPaperGatewayBridgeError,match="risk eligible"):
        prepare_btc_perpetual_paper_command(plan=rejected,launch=launch(now),
            expected_gateway_snapshot_id=gateway.snapshot_id,requested_at=now,market_data_at=now)
