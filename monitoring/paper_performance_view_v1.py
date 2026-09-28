"""Sanitized read-only projection of a verified paper-performance checkpoint."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtesting.execution_accounting_v2.accounting import AccountingEventKind
from execution.paper_performance_checkpoint_v1 import (
    MAX_CHECKPOINT_BYTES, PaperPerformanceCheckpointError, ledger_from_bytes,
)


class PaperPerformanceViewError(ValueError):
    pass


def load_performance_view(path: Path, *, observed_at: datetime) -> dict:
    path = Path(path)
    if not path.exists():
        return {"available": False, "integrity": "MISSING", "reason":
            "VERIFIED_PAPER_PERFORMANCE_CHECKPOINT_UNAVAILABLE"}
    if path.is_symlink() or not path.is_file():
        raise PaperPerformanceViewError("performance checkpoint is unsafe")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise PaperPerformanceViewError("observed_at must be timezone-aware")
    try:
        size = path.stat().st_size
        if not 0 < size <= MAX_CHECKPOINT_BYTES:
            raise PaperPerformanceViewError("performance checkpoint size is invalid")
        ledger = ledger_from_bytes(path.read_bytes())
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except PaperPerformanceViewError:
        raise
    except (OSError, PaperPerformanceCheckpointError) as exc:
        raise PaperPerformanceViewError("performance checkpoint failed integrity validation") from exc
    snapshot = ledger.snapshot
    position = snapshot.position
    equity_curve = [{"as_of": item.as_of.isoformat(), "equity": str(item.equity),
                     "net_result": str(item.net_result),
                     "unrealized_pnl": str(item.unrealized_pnl)}
                    for item in ledger.accounting.snapshots[-500:]]
    markers = []
    for event in ledger.accounting.events:
        if event.kind is AccountingEventKind.FILL and event.fill is not None:
            markers.append({"fill_id": event.fill.fill_id, "order_id": event.fill.order_id,
                "time": event.fill.fill_time.isoformat(), "side": event.fill.side.value,
                "quantity": str(event.fill.quantity), "price": str(event.fill.economic_price)})
    age = max(0, int((observed_at.astimezone(timezone.utc) - modified_at).total_seconds()))
    return {"available": True, "integrity": "VERIFIED", "reason": None,
        "checkpoint_modified_at": modified_at.isoformat(), "checkpoint_age_seconds": age,
        "ledger_id": ledger.ledger_id, "accounting_ledger_fingerprint": ledger.accounting.ledger_fingerprint,
        "gateway_snapshot_id": ledger.gateway_snapshot_id, "as_of": snapshot.as_of.isoformat(),
        "cash": str(snapshot.cash), "equity": str(snapshot.equity),
        "gross_realized_pnl": str(snapshot.gross_realized_pnl),
        "unrealized_pnl": str(snapshot.unrealized_pnl), "net_result": str(snapshot.net_result),
        "commissions": str(snapshot.commissions), "exchange_fees": str(snapshot.exchange_fees),
        "slippage_costs": str(snapshot.slippage_costs), "total_costs": str(snapshot.total_costs),
        "position": {"quantity": str(position.signed_quantity),
            "average_entry_price": None if position.average_entry_price is None else str(position.average_entry_price),
            "mark_price": None if position.mark_price is None else str(position.mark_price)},
        "equity_curve": equity_curve, "trade_markers": markers,
        "advisory_only": True, "live_trading_permitted": False, "trading_authority": False}
