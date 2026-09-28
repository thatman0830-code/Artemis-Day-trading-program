"""Read-only validation of proposed protection after a partial exit.

No new order ledger, reservation, activation or submission is created.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderState
from backtesting.execution_accounting_v2.ohlc_execution import OHLCBarV2
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint, _utc
from backtesting.execution_accounting_v2.validation import validate_order_against_instrument
from execution.paper_oco_execution_v1 import PaperOCOError


@dataclass(frozen=True, slots=True)
class PaperOCOReplacementReviewV1:
    review_id: str
    predecessor_checkpoint_id: str
    accounting_id: str
    stop_order_id: str
    target_order_id: str
    quantity: Decimal
    cancellation_completed_at: datetime
    reviewed_at: datetime
    source_bar_id: str
    requires_gap_review: bool = True
    rearm_authorized: bool = False
    trading_authority: bool = False

    def __post_init__(self):
        if self.requires_gap_review is not True or self.rearm_authorized is not False or self.trading_authority is not False:
            raise PaperOCOError("replacement review grants no authority")


def review_protective_replacement(*, predecessor, expected_checkpoint_id,
                                  accounting, stop, target, source_bar, reviewed_at):
    """Reload durable cancellation evidence, then validate quantity-only replacement.

    Caller supplies exact current accounting and a finalized post-cancellation
    source bar. This cannot attest to gateway state or price continuity in the
    unprotected interval; a positive review is not permission to rearm.
    """
    _utc(reviewed_at, "reviewed_at")
    document, old = predecessor.load()
    if document["checkpoint_id"] != expected_checkpoint_id:
        raise PaperOCOError("stale predecessor checkpoint")
    if old.state != "CANCELLED_REQUIRES_REARM" or any(o.state is not OrderState.CANCELLED for o in old.ledger.orders):
        raise PaperOCOError("verified partial-exit cancellation required")
    accounting.verify_integrity()
    if accounting != old.acknowledged_accounting:
        raise PaperOCOError("replacement accounting changed")
    quantity = accounting.snapshot.position.signed_quantity
    cancelled_at = max(e.event_time for e in old.ledger.events)
    if quantity <= 0 or reviewed_at < cancelled_at or reviewed_at < accounting.snapshot.as_of:
        raise PaperOCOError("invalid replacement position or chronology")
    if type(source_bar) is not OHLCBarV2:
        raise PaperOCOError("verified closed source bar required")
    source_bar.__post_init__()
    if (any(getattr(source_bar, name) is not True for name in
            ("finalized", "session_eligible", "data_quality_valid", "contract_eligible"))
            or source_bar.open_time < cancelled_at or source_bar.available_at > reviewed_at
            or (reviewed_at - source_bar.close_time).total_seconds() > 90
            or (source_bar.market, source_bar.instrument_id, source_bar.contract_id) !=
               (accounting.market, accounting.instrument_id, accounting.contract_id)):
        raise PaperOCOError("ineligible or stale replacement source")
    instrument = accounting.instrument
    if instrument.effective_from > source_bar.open_time or (
            instrument.effective_to is not None and reviewed_at >= instrument.effective_to):
        raise PaperOCOError("instrument coverage missing")
    old_stop = old.ledger.order(old.group.adverse_order_id).intent
    old_target = old.ledger.order(old.group.favorable_order_id).intent
    previous_ids = {o.intent.order_id for o in old.ledger.orders}
    previous_actions = {o.intent.action_id for o in old.ledger.orders}
    if type(stop) is not OrderIntentV2 or type(target) is not OrderIntentV2:
        raise PaperOCOError("typed replacement intents required")
    if stop.order_id == target.order_id or stop.action_id == target.action_id:
        raise PaperOCOError("replacement identities must be distinct")
    # This version permits quantity reduction only, not a new risk policy,
    # breakeven move, wider stop, different target or changed execution semantics.
    unchanged = ("run_id", "market", "instrument_id", "contract_id", "side",
                 "order_type", "time_in_force", "limit_price", "stop_price",
                 "parent_order_id", "configuration_version", "execution_policy_version")
    for candidate, previous in ((stop, old_stop), (target, old_target)):
        candidate.__post_init__()
        if (candidate.order_id in previous_ids or candidate.action_id in previous_actions
                or candidate.quantity != quantity or candidate.replaces_order_id != previous.order_id
                or candidate.submitted_at != reviewed_at or candidate.activation_at != reviewed_at
                or candidate.expires_at is not None
                or any(getattr(candidate, name) != getattr(previous, name) for name in unchanged)
                or not validate_order_against_instrument(candidate, instrument).valid):
            raise PaperOCOError("replacement must be fresh, grid-valid and quantity-only")
    if not stop.stop_price < source_bar.close < target.limit_price:
        raise PaperOCOError("latest source price is outside replacement protection")
    identity = canonical_fingerprint("paper-oco-replacement-review-v1", document["checkpoint_id"],
        accounting.ledger_fingerprint, stop, target, source_bar, reviewed_at)
    # Recheck after validation; no read-only review can reserve the checkpoint.
    if predecessor.load()[0]["checkpoint_id"] != document["checkpoint_id"]:
        raise PaperOCOError("predecessor changed during review")
    return PaperOCOReplacementReviewV1(identity, document["checkpoint_id"],
        accounting.ledger_fingerprint, stop.order_id, target.order_id, quantity,
        cancelled_at, reviewed_at, source_bar.bar_id)
