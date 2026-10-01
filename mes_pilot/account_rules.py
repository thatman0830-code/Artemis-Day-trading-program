"""Versioned prop account-rule profile interface (master spec page 13).

No firm profile is selected: Frank's Apex/Tradovate product, size and
purchase cohort are unknown, so the active profile status is UNCONFIGURED and
prop recommendations are blocked. Independent paper work is unaffected.
Profiles are data (JSON) with provenance; the synthetic fixture below exists
only to test boundary behavior and is NOT an Apex rule set.

Boundary convention: equality counts as a breach (equity == floor breaches,
day loss == daily limit breaches) unless a verified profile states otherwise.
Prop mode is advisory alerts only; a profile asking for any other automation
is never allowed to emit prop alerts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date

ACTIVE_PROFILE_STATUS = "UNCONFIGURED"
FLOOR_TYPES = ("STATIC", "EOD_TRAILING", "INTRADAY_TRAILING")
STAGES = ("EVALUATION", "FUNDED", "PAYOUT")
ADVISORY_ONLY = "ADVISORY_ALERTS_ONLY"
_EPS = 1e-9


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class AccountRuleProfile:
    profile_id: str
    firm: str
    product: str
    platform: str
    account_size: float
    purchase_cohort: str
    stage: str                       # EVALUATION | FUNDED | PAYOUT
    effective_date: date
    source: str
    last_verified: date
    floor_type: str                  # STATIC | EOD_TRAILING | INTRADAY_TRAILING
    drawdown_allowance: float
    floor_lock_at: float | None
    daily_loss_limit: float | None
    open_pnl_counts_intraday: bool
    max_contracts_micro: int
    flat_by_local: str | None
    profit_target: float | None
    consistency_max_day_share: float | None
    automation: str                  # must be ADVISORY_ALERTS_ONLY for the pilot
    synthetic_fixture: bool = False
    rule_version: str = "1"
    extra: dict = field(default_factory=dict)


def validate_profile(p: AccountRuleProfile) -> AccountRuleProfile:
    if p.floor_type not in FLOOR_TYPES:
        raise ProfileError(f"floor_type must be one of {FLOOR_TYPES}")
    if p.stage not in STAGES:
        raise ProfileError(f"stage must be one of {STAGES}")
    if p.account_size <= 0 or p.drawdown_allowance <= 0 or p.drawdown_allowance >= p.account_size:
        raise ProfileError("account_size and 0 < drawdown_allowance < account_size required")
    if p.max_contracts_micro < 1:
        raise ProfileError("max_contracts_micro must be >= 1")
    if p.daily_loss_limit is not None and p.daily_loss_limit <= 0:
        raise ProfileError("daily_loss_limit must be positive when set")
    if p.floor_lock_at is not None and p.floor_lock_at < p.account_size - p.drawdown_allowance:
        raise ProfileError("floor_lock_at below the initial floor")
    if p.last_verified < p.effective_date:
        raise ProfileError("last_verified precedes effective_date")
    if not p.rule_version:
        raise ProfileError("rule_version required")
    return p


def profile_from_dict(raw: dict) -> AccountRuleProfile:
    """Parse a JSON profile (dates as ISO strings). Unknown keys are rejected."""
    known = {f.name for f in fields(AccountRuleProfile)}
    unknown = set(raw) - known
    if unknown:
        raise ProfileError(f"unknown profile keys {sorted(unknown)}")
    data = dict(raw)
    for key in ("effective_date", "last_verified"):
        if isinstance(data.get(key), str):
            data[key] = date.fromisoformat(data[key])
    return validate_profile(AccountRuleProfile(**data))


def active_profile() -> AccountRuleProfile | None:
    """No exact Apex product/size/cohort has been selected; prop alerts stay blocked."""
    return None


@dataclass
class TrailingFloor:
    """Tracks a loss floor along the path.

    INTRADAY_TRAILING: every mark (including open P&L when the profile counts it)
    can raise the peak; a later retracement never lowers the floor.
    EOD_TRAILING: only end-of-day marks raise the peak; intraday marks are
    still checked for breach. STATIC: never trails. Once the floor reaches
    ``floor_lock_at`` it stops trailing (floor lock). ``floor``/``peak`` may be
    passed explicitly to restore persisted state after a restart.
    """
    profile: AccountRuleProfile
    start_balance: float
    floor: float | None = None
    peak: float | None = None

    def __post_init__(self):
        if self.floor is None:
            self.floor = self.start_balance - self.profile.drawdown_allowance
        if self.peak is None:
            self.peak = self.start_balance

    @property
    def locked(self) -> bool:
        lock = self.profile.floor_lock_at
        return lock is not None and self.floor >= lock - _EPS

    def update(self, equity_mark: float, *, end_of_day: bool = False) -> float:
        p = self.profile
        trails = p.floor_type == "INTRADAY_TRAILING" or (p.floor_type == "EOD_TRAILING" and end_of_day)
        if trails and equity_mark > self.peak:
            self.peak = equity_mark
            candidate = self.peak - p.drawdown_allowance
            if p.floor_lock_at is not None:
                candidate = min(candidate, p.floor_lock_at)
            self.floor = max(self.floor, candidate)
        return self.floor

    def breached(self, equity_mark: float) -> bool:
        # Equality counts as a breach (conservative) unless a profile states otherwise.
        return equity_mark <= self.floor + _EPS

    def to_dict(self) -> dict:
        return {"profile_id": self.profile.profile_id, "rule_version": self.profile.rule_version,
                "start_balance": self.start_balance, "floor": self.floor, "peak": self.peak}

    @classmethod
    def from_dict(cls, profile: AccountRuleProfile, d: dict) -> "TrailingFloor":
        if d["profile_id"] != profile.profile_id or d.get("rule_version") != profile.rule_version:
            raise ProfileError("persisted floor belongs to a different profile/version")
        return cls(profile, d["start_balance"], floor=d["floor"], peak=d["peak"])


def check_trade(profile: AccountRuleProfile | None, *, contracts_micro: int, day_loss_after_worst: float,
                equity_after_worst: float, floor: float) -> dict:
    """Advisory pre-alert check. ``day_loss_after_worst`` is a positive loss amount."""
    if profile is None:
        return {"status": ACTIVE_PROFILE_STATUS, "allowed_for_prop_alert": False,
                "reason": "No exact Apex product/size/cohort profile selected"}
    results = {
        "contracts": contracts_micro <= profile.max_contracts_micro,
        "daily_loss": profile.daily_loss_limit is None or day_loss_after_worst < profile.daily_loss_limit - _EPS,
        "floor": equity_after_worst > floor + _EPS,
        "automation_advisory_only": profile.automation == ADVISORY_ONLY,
    }
    return {"status": "CONFIGURED" if not profile.synthetic_fixture else "SYNTHETIC_FIXTURE",
            "profile_id": profile.profile_id, "rule_version": profile.rule_version,
            "allowed_for_prop_alert": all(results.values()) and not profile.synthetic_fixture,
            "checks": results}


def synthetic_fixture() -> AccountRuleProfile:
    return AccountRuleProfile(
        profile_id="SYNTHETIC-INTRADAY-TRAIL-TEST", firm="SYNTHETIC", product="TEST", platform="NONE",
        account_size=50000.0, purchase_cohort="N/A", stage="EVALUATION", effective_date=date(2026, 1, 1),
        source="test fixture only", last_verified=date(2026, 9, 30), floor_type="INTRADAY_TRAILING",
        drawdown_allowance=2500.0, floor_lock_at=50100.0, daily_loss_limit=1000.0, open_pnl_counts_intraday=True,
        max_contracts_micro=3, flat_by_local="16:59", profit_target=3000.0, consistency_max_day_share=0.5,
        automation=ADVISORY_ONLY, synthetic_fixture=True, rule_version="synthetic-1")
