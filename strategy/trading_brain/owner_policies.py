from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from strategy.trading_brain.p27_setup_qualification import SetupModel


LEGACY_MIN_RR_POLICY_ID = "CANONICAL_MIN_RR_V1"
OWNER_MIN_RR_POLICY_ID = "OWNER_MIN_RR_V1"
OWNER_WIN_RATE_OBJECTIVE_ID = "OWNER_WIN_RATE_OBJECTIVE_V1"


@dataclass(frozen=True)
class MinimumRiskRewardPolicy:
    id: str
    version: str
    global_minimum: Decimal
    model_minimums: tuple[tuple[SetupModel, Decimal], ...]
    immutable: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.version.strip() or not self.immutable:
            raise ValueError("risk-to-reward policy identity is invalid")
        if not isinstance(self.global_minimum, Decimal) or not self.global_minimum.is_finite():
            raise TypeError("global minimum R must be a finite Decimal")
        if self.global_minimum < Decimal("1.0"):
            raise ValueError("no minimum R may be below the global hard minimum 1.0")
        models = [model for model, _ in self.model_minimums]
        if len(models) != len(set(models)):
            raise ValueError("duplicate entry-model minimum R")
        for model, minimum in self.model_minimums:
            if not isinstance(model, SetupModel):
                raise TypeError("entry model must be canonical")
            if not isinstance(minimum, Decimal) or not minimum.is_finite():
                raise TypeError("model minimum R must be a finite Decimal")
            if minimum < self.global_minimum:
                raise ValueError("model minimum R cannot be below the global hard minimum")

    def minimum_for(self, model: SetupModel) -> Decimal:
        matches = tuple(value for candidate, value in self.model_minimums if candidate == model)
        if len(matches) != 1:
            raise ValueError("entry model requires one explicit minimum R")
        return matches[0]


CANONICAL_MIN_RR_V1 = MinimumRiskRewardPolicy(
    LEGACY_MIN_RR_POLICY_ID, "1", Decimal("1.0"),
    ((SetupModel.CONTINUATION, Decimal("2.0")),
     (SetupModel.REVERSAL_1, Decimal("2.0"))),
)

OWNER_MIN_RR_V1 = MinimumRiskRewardPolicy(
    OWNER_MIN_RR_POLICY_ID, "1", Decimal("1.0"),
    ((SetupModel.CONTINUATION, Decimal("1.0")),
     (SetupModel.REVERSAL_1, Decimal("1.0"))),
)


def minimum_rr_policy(policy_id: str) -> MinimumRiskRewardPolicy:
    policies = {policy.id: policy for policy in (CANONICAL_MIN_RR_V1, OWNER_MIN_RR_V1)}
    try:
        return policies[policy_id]
    except KeyError as error:
        raise ValueError("unknown minimum risk-to-reward policy identity") from error


class MinimumRiskRewardPolicyRegistry:
    resolve = staticmethod(minimum_rr_policy)
