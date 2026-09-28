"""Fail-closed admission of a risk-approved BTC perpetual plan to durable paper state."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from decimal import InvalidOperation
import hashlib
import json

from backtesting.execution_accounting_v2.contracts import RiskDecision
from backtesting.execution_accounting_v2.risk_sessions import RiskDecisionRecordV2
from execution.btc_perpetual_strategy_intent_v1 import BTCPerpetualStrategyIntentV1
from execution.paper_exchange_adapter_checkpoint_v1 import PaperAdapterCheckpointStoreV1
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1
from execution.paper_gateway_v2 import PaperSubmissionV1
from execution.strategy_paper_pretrade_v1 import PaperPretradePlanV1
from execution.supervised_paper_launch_decision_v1 import DECISION_ENVELOPE_VERSION

VERSION = "btc-perpetual-paper-gateway-bridge-v1"
_FIELDS = {"schema_version","evaluated_at","evidence_id","confirmation_id","launch_id",
    "eligible","reasons","expires_at","permitted_markets","maximum_session_seconds",
    "maximum_commands","maximum_order_notional","maximum_gross_exposure","advisory_only",
    "live_trading_permitted","trading_authority","decision_envelope_id"}


class BTCPerpetualPaperGatewayBridgeError(ValueError): pass


def _sha(value, name):
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise BTCPerpetualPaperGatewayBridgeError(f"{name} must be lowercase SHA-256")


def _utc(value, name):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset()!=timedelta(0):
        raise BTCPerpetualPaperGatewayBridgeError(f"{name} must be UTC")


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


def prepare_btc_perpetual_paper_command(*, plan: PaperPretradePlanV1, launch: dict,
        expected_gateway_snapshot_id: str, requested_at: datetime,
        market_data_at: datetime) -> PaperAdapterCommandV1:
    """Create a paper-only adapter command; no provider or submission transport exists here."""
    _utc(requested_at,"requested_at"); _utc(market_data_at,"market_data_at")
    _sha(expected_gateway_snapshot_id,"expected_gateway_snapshot_id")
    if type(plan) is not PaperPretradePlanV1:
        raise BTCPerpetualPaperGatewayBridgeError("typed pretrade plan required")
    plan.__post_init__()
    strategy=plan.strategy_intent
    risk=plan.risk_decision
    if (type(strategy) is not BTCPerpetualStrategyIntentV1
            or type(risk) is not RiskDecisionRecordV2):
        raise BTCPerpetualPaperGatewayBridgeError("typed BTC perpetual plan evidence required")
    strategy.__post_init__(); risk.__post_init__()
    intent=strategy.intent
    if (not plan.risk_eligible or risk.event.decision is not RiskDecision.ALLOW
            or plan.submission_authorized or plan.trading_authority
            or strategy.submission_authorized or strategy.trading_authority):
        raise BTCPerpetualPaperGatewayBridgeError("plan is not risk eligible and advisory-only")
    if (intent.market,intent.instrument_id,intent.contract_id)!=("BTC-PERP","BTC","BTC-PERP"):
        raise BTCPerpetualPaperGatewayBridgeError("canonical BTC perpetual identity required")
    if risk.event.market!=intent.market or risk.event.instrument_id!=intent.instrument_id:
        raise BTCPerpetualPaperGatewayBridgeError("risk decision identity mismatch")
    if not isinstance(launch,dict) or set(launch)!=_FIELDS:
        raise BTCPerpetualPaperGatewayBridgeError("launch decision fields do not match schema")
    body={key:launch[key] for key in launch if key!="decision_envelope_id"}
    _sha(launch["decision_envelope_id"],"decision_envelope_id")
    if _hash(body)!=launch["decision_envelope_id"]:
        raise BTCPerpetualPaperGatewayBridgeError("launch decision integrity failure")
    for key in ("evidence_id","confirmation_id","launch_id"): _sha(launch[key],key)
    try:
        evaluated=datetime.fromisoformat(launch["evaluated_at"])
        expires=datetime.fromisoformat(launch["expires_at"])
        order_limit=Decimal(launch["maximum_order_notional"])
        gross_limit=Decimal(launch["maximum_gross_exposure"])
    except (TypeError,ValueError,InvalidOperation) as exc:
        raise BTCPerpetualPaperGatewayBridgeError("launch decision values are invalid") from exc
    _utc(evaluated,"evaluated_at"); _utc(expires,"expires_at")
    if (launch["schema_version"]!=DECISION_ENVELOPE_VERSION or launch["eligible"] is not True
            or launch["reasons"]!=[] or launch["permitted_markets"]!="BTC-PERP".split()
            or launch["advisory_only"] is not True or launch["live_trading_permitted"] is not False
            or launch["trading_authority"] is not False):
        raise BTCPerpetualPaperGatewayBridgeError("launch decision does not permit BTC perpetual paper")
    seconds=launch["maximum_session_seconds"]; commands=launch["maximum_commands"]
    if (type(seconds) is not int or not 0<seconds<=1800 or type(commands) is not int or not 0<commands<=10
            or not evaluated<=requested_at<=expires<=evaluated+timedelta(minutes=5)
            or requested_at>evaluated+timedelta(seconds=seconds)
            or intent.expires_at is None or requested_at>intent.expires_at
            or market_data_at>requested_at or requested_at-market_data_at>timedelta(seconds=5)):
        raise BTCPerpetualPaperGatewayBridgeError("launch, intent, or market-data window is invalid")
    reference=intent.limit_price
    if reference is None or reference<=0 or plan.quantity*reference>order_limit or plan.quantity*reference>gross_limit:
        raise BTCPerpetualPaperGatewayBridgeError("launch exposure limit exceeded")
    authorization=_hash([VERSION,"authorization",launch["decision_envelope_id"],plan.plan_id])
    idempotency=_hash([VERSION,"submission",authorization,intent.order_id])
    submission=PaperSubmissionV1(idempotency,intent,reference,requested_at,market_data_at,
        authorization,True,False)
    command_id=_hash([VERSION,"command",expected_gateway_snapshot_id,submission.fingerprint])
    return PaperAdapterCommandV1(command_id,expected_gateway_snapshot_id,submission=submission)


def execute_btc_perpetual_paper_command(*, store: PaperAdapterCheckpointStoreV1, **values):
    """Atomically persist the paper command and its receipt through the checkpoint store."""
    if type(store) is not PaperAdapterCheckpointStoreV1:
        raise BTCPerpetualPaperGatewayBridgeError("typed durable adapter store required")
    command=prepare_btc_perpetual_paper_command(**values)
    return store.execute(command)
