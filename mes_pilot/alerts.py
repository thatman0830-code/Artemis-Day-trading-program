"""Advisory manual-prop alerts (master spec pages 11-12).

The outbox writes alert documents to a local JSONL file (and optionally the
console). It has no order, broker, browser, hotkey or UI capability. Frank's
actual decision and fills are recorded separately and never replaced by paper
fills. An unresolved alert blocks further entry alerts.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

UTC = timezone.utc
RESOLUTIONS = {"ENTERED", "SKIPPED", "EXPIRED", "MISSED"}


@dataclass(frozen=True)
class EntryAlert:
    alert_id: str
    signal_id: str
    strategy_version: str
    config_hash: str
    contract: str
    side: str
    setup: str
    detected_at: str
    expires_at: str
    entry_zone: tuple[float, float]
    current_price: float
    stop: float
    target: float
    suggested_quantity: int
    worst_case_risk_usd: float
    gross_reward_risk: float
    account_rule_status: str
    invalidation: str
    instruction: str = ("ADVISORY ONLY. Not an order. Skip if stale or past expiry. "
                        "If you enter, place native platform stop and target yourself.")
    kind: str = "ENTRY"


@dataclass(frozen=True)
class ManagementAlert:
    alert_id: str
    position_ref: str
    action: str          # EXIT_AT_TARGET | EXIT_AT_STOP | TIME_EXIT | EVENT_FLATTEN | EMERGENCY_FLATTEN | CANCEL_ENTRY
    reason: str
    issued_at: str
    urgent: bool = True
    instruction: str = "ADVISORY ONLY. Perform this action yourself on the prop platform, then record what you did."
    kind: str = "MANAGEMENT"


class AlertOutbox:
    def __init__(self, path: Path, echo: bool = False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.echo = echo

    def _all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def unresolved(self, now: datetime | None = None) -> list[dict]:
        docs = self._all()
        resolved = {d["alert_id"] for d in docs if d.get("kind") == "RESOLUTION"}
        return [d for d in docs if d.get("kind") == "ENTRY" and d["alert_id"] not in resolved]

    def emit(self, alert) -> dict:
        doc = asdict(alert)
        if any(d.get("alert_id") == doc["alert_id"] and d.get("kind") == doc["kind"] for d in self._all()):
            return {"emitted": False, "reason": "DUPLICATE_ALERT_ID"}
        if doc["kind"] == "ENTRY" and self.unresolved():
            return {"emitted": False, "reason": "PRIOR_ALERT_UNRESOLVED"}
        doc["delivered_at"] = datetime.now(UTC).isoformat()
        with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(doc, sort_keys=True) + "\n")
        if self.echo:
            print("ALERT", json.dumps(doc, sort_keys=True))
        return {"emitted": True, "alert": doc}

    def resolve(self, alert_id: str, decision: str, *, actual_fill_price: float | None = None,
                actual_fill_time: str | None = None, actual_qty: int | None = None,
                actual_stop: float | None = None, actual_target: float | None = None, note: str = "",
                source: str = "MANUAL_ENTRY_BY_FRANK") -> dict:
        if decision not in RESOLUTIONS:
            raise ValueError(f"decision must be one of {sorted(RESOLUTIONS)}")
        docs = self._all()
        if not any(d["alert_id"] == alert_id and d.get("kind") == "ENTRY" for d in docs):
            raise KeyError(alert_id)
        prior = [d for d in docs if d.get("kind") == "RESOLUTION" and d["alert_id"] == alert_id]
        # One operator resolution per alert; an automatic EXPIRED may be followed by
        # Frank's own record (e.g. he did enter late), never the other way round.
        if any(d.get("source") == "MANUAL_ENTRY_BY_FRANK" for d in prior):
            raise ValueError(f"alert {alert_id} already resolved by the operator")
        if prior and source != "MANUAL_ENTRY_BY_FRANK":
            raise ValueError(f"alert {alert_id} already resolved")
        if decision == "ENTERED" and (actual_fill_price is None or not actual_qty):
            raise ValueError("ENTERED requires Frank's actual fill price and quantity")
        doc = {"kind": "RESOLUTION", "alert_id": alert_id, "decision": decision, "recorded_at": datetime.now(UTC).isoformat(),
               "actual_fill_price": actual_fill_price, "actual_fill_time": actual_fill_time, "actual_qty": actual_qty,
               "actual_stop": actual_stop, "actual_target": actual_target, "note": note,
               "source": source, "supersedes_auto_expiry": bool(prior)}
        with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(doc, sort_keys=True) + "\n")
        return doc

    def expire_stale(self, now: datetime) -> list[str]:
        """Auto-record EXPIRED for entry alerts past expiry that Frank never resolved (logged, not hidden)."""
        out = []
        for d in self.unresolved():
            if datetime.fromisoformat(d["expires_at"]) < now - timedelta(minutes=5):
                self.resolve(d["alert_id"], "EXPIRED", note="auto: no operator resolution recorded before expiry+5m",
                             source="AUTO_EXPIRY")
                out.append(d["alert_id"])
        return out
