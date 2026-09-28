from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from strategy.trading_brain.p11_cisd_confirmation import (
    CISDDirection, CISDProcess, CISDState,
)
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralRegime, StructuralSwing,
)
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p22_ote import OTE
from strategy.trading_brain.p23_liquidity import LiquiditySide
from strategy.trading_brain.p24_lrl_selection import LRL, LRLRole
from strategy.trading_brain.p26_confluence import Confluence, ConfluenceType


class SetupModel(str, Enum):
    CONTINUATION = "CONTINUATION"
    REVERSAL_1 = "REVERSAL_1"


class ContinuationSetupState(str, Enum):
    CANDIDATE = "CANDIDATE"
    ARMED = "ARMED"
    REJECTED = "REJECTED"


class ReversalSetupState(str, Enum):
    MSS_CONFIRMED = "MSS_CONFIRMED"
    ENTRY_ZONE_ARMED = "ENTRY_ZONE_ARMED"
    REJECTED = "REJECTED"


class SetupQualificationErrorCode(str, Enum):
    SETUP_INVALID = "SETUP_INVALID"


@dataclass(frozen=True)
class Setup:
    id: str
    setup_candidate_id: str
    model: SetupModel
    direction: StructuralRegime
    state: ContinuationSetupState | ReversalSetupState
    qualification_time: int
    entry_zone_selection_eligible: bool
    qualified_prerequisites: tuple[str, ...]
    missing_prerequisites: tuple[str, ...]
    active_range_id: str | None
    protected_swing_id: str | None
    ote_id: str | None
    target_lrl_id: str | None
    cisd_confirmation_id: str | None
    qualifying_sweep_id: str | None
    confluence_ids: tuple[str, ...]
    eligible_zone_ids: tuple[str, ...]
    immutable: bool = True


@dataclass(frozen=True)
class PreZoneQualificationResult:
    setup: Setup

    @property
    def eligible_for_entry_zone_selection(self) -> bool:
        return self.setup.entry_zone_selection_eligible


@dataclass(frozen=True)
class FinalSetupQualification:
    id: str
    setup_id: str
    setup_candidate_id: str
    model: SetupModel
    direction: StructuralRegime
    phase_a_state: ContinuationSetupState | ReversalSetupState
    final_state: ContinuationSetupState | ReversalSetupState
    entry_zone_selection_id: str
    stop_selection_id: str
    target_lrl_id: str
    entry: Decimal
    stop: Decimal
    target: Decimal
    risk: Decimal
    reward: Decimal
    r_multiple: Decimal
    minimum_required_r: Decimal
    geometry_valid: bool
    executable: bool
    finalized_time: int
    immutable: bool = True
    policy_id: str = "CANONICAL_MIN_RR_V1"
    policy_version: str = "1"
    entry_model_identity: str = ""
    qualification_reason: str = ""
    source_version: str = "canonical-legacy"
    calculation_version: str = "canonical-legacy"


@dataclass(frozen=True)
class SetupQualificationError:
    id: str
    code: SetupQualificationErrorCode
    setup_id: str
    reason: str
    finalized_time: int
    immutable: bool = True


@dataclass(frozen=True)
class FinalQualificationResult:
    qualification: FinalSetupQualification | None
    error: SetupQualificationError | None

    @property
    def valid(self) -> bool:
        return self.qualification is not None and self.error is None


class SetupQualificationEngine:
    """Canonical #27 Phase A pre-zone decisions only.

    This phase never selects a zone, computes EQ or R, selects a stop, arms or
    rejects a setup, authorizes risk, sizes, places orders, or executes.
    """

    _CONTINUATION_CONFLUENCE = {
        ConfluenceType.OTE_FVG,
        ConfluenceType.OTE_IFVG,
    }
    MINIMUM_R = Decimal("2")

    @staticmethod
    def _setup_id(
        *, candidate_id: str, model: SetupModel,
        direction: StructuralRegime,
    ) -> str:
        key = f"trading-brain:#27:{candidate_id}:{model.value}:{direction.value}"
        return str(uuid5(NAMESPACE_URL, key))

    @staticmethod
    def _required_target_side(direction: StructuralRegime) -> LiquiditySide:
        return LiquiditySide.BSL if direction == StructuralRegime.BULLISH else LiquiditySide.LSL

    @classmethod
    def _target_valid(
        cls, *, target_lrl: LRL | None, direction: StructuralRegime,
        evaluation_time: int,
    ) -> bool:
        return bool(
            target_lrl is not None
            and target_lrl.active
            and not target_lrl.historical
            and target_lrl.role == LRLRole.CONTINUATION_TARGET
            and target_lrl.regime == direction
            and target_lrl.side == cls._required_target_side(direction)
            and target_lrl.selected_time <= evaluation_time
        )

    @staticmethod
    def _validate_common(
        *, setup_candidate_id: str, direction: StructuralRegime,
        evaluation_time: int,
    ) -> None:
        if not setup_candidate_id.strip():
            raise ValueError("setup_candidate_id is required.")
        if direction not in {StructuralRegime.BULLISH, StructuralRegime.BEARISH}:
            raise ValueError("Pre-zone setup qualification requires a directional regime.")
        if int(evaluation_time) < 0:
            raise ValueError("evaluation_time cannot be negative.")

    def qualify_continuation(
        self, *, setup_candidate_id: str,
        state: ContinuationSetupState, direction: StructuralRegime,
        protected_swing: StructuralSwing | None,
        active_range: StructuralRange | None, ote: OTE | None,
        target_lrl: LRL | None,
        confluences: tuple[Confluence, ...], evaluation_time: int,
    ) -> PreZoneQualificationResult:
        self._validate_common(
            setup_candidate_id=setup_candidate_id,
            direction=direction, evaluation_time=evaluation_time,
        )
        if state != ContinuationSetupState.CANDIDATE:
            raise ValueError("#27 Phase A continuation requires CANDIDATE, never ARMED or REJECTED.")
        ids = [fact.id for fact in confluences]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate confluence identity.")

        expected_swing_type = (
            MechanicalSwingType.L
            if direction == StructuralRegime.BULLISH else MechanicalSwingType.H
        )
        structural_context = bool(
            protected_swing is not None
            and protected_swing.protected
            and protected_swing.type == expected_swing_type
            and active_range is not None
            and active_range.active
            and not active_range.historical
            and active_range.regime == direction
            and protected_swing.timeframe == active_range.timeframe
        )
        ote_valid = bool(
            structural_context
            and ote is not None
            and ote.active
            and not ote.historical
            and ote.range_id == active_range.id
            and ote.direction == direction
            and ote.timeframe.lower() == "5m"
            and ote.timeframe.lower() == active_range.timeframe.lower()
            and ote.confirmation_time <= evaluation_time
        )
        target_valid = self._target_valid(
            target_lrl=target_lrl, direction=direction,
            evaluation_time=evaluation_time,
        )
        if target_valid and active_range is not None:
            target_valid = target_lrl.active_range_id == active_range.id

        active_confluences = tuple(sorted(
            (
                fact for fact in confluences
                if fact.type in self._CONTINUATION_CONFLUENCE
                and fact.active and not fact.historical
                and fact.directional_compatibility
                and ote is not None
                and fact.primary_object_id == ote.id
                and fact.primary_timeframe.lower() == "5m"
                and fact.secondary_timeframe.lower() == "5m"
                and fact.created_time <= evaluation_time
            ),
            key=lambda fact: fact.id,
        ))
        confluence_valid = bool(active_confluences)

        checks = (
            ("DIRECTIONAL_PROTECTED_STRUCTURE_AND_ACTIVE_RANGE", structural_context),
            ("ACTIVE_5M_OTE", ote_valid),
            ("ACTIVE_DIRECTIONAL_OTE_IMBALANCE_CONFLUENCE", confluence_valid),
            ("ACTIVE_CONTINUATION_TARGET_LRL", target_valid),
        )
        qualified = tuple(name for name, valid in checks if valid)
        missing = tuple(name for name, valid in checks if not valid)
        setup = Setup(
            id=self._setup_id(
                candidate_id=setup_candidate_id,
                model=SetupModel.CONTINUATION, direction=direction,
            ),
            setup_candidate_id=setup_candidate_id,
            model=SetupModel.CONTINUATION, direction=direction,
            state=ContinuationSetupState.CANDIDATE,
            qualification_time=int(evaluation_time),
            entry_zone_selection_eligible=not missing,
            qualified_prerequisites=qualified,
            missing_prerequisites=missing,
            active_range_id=active_range.id if active_range is not None else None,
            protected_swing_id=protected_swing.id if protected_swing is not None else None,
            ote_id=ote.id if ote is not None else None,
            target_lrl_id=target_lrl.id if target_lrl is not None else None,
            cisd_confirmation_id=None, qualifying_sweep_id=None,
            confluence_ids=tuple(fact.id for fact in active_confluences),
            eligible_zone_ids=tuple(sorted({
                fact.secondary_object_id for fact in active_confluences
            })),
        )
        return PreZoneQualificationResult(setup)

    def qualify_reversal_1(
        self, *, setup_candidate_id: str,
        state: ReversalSetupState, direction: StructuralRegime,
        cisd_process: CISDProcess, target_lrl: LRL | None,
        evaluation_time: int,
    ) -> PreZoneQualificationResult:
        self._validate_common(
            setup_candidate_id=setup_candidate_id,
            direction=direction, evaluation_time=evaluation_time,
        )
        if state != ReversalSetupState.MSS_CONFIRMED:
            raise ValueError("#27 Phase A reversal requires MSS_CONFIRMED, never ENTRY_ZONE_ARMED.")
        expected_cisd = (
            CISDDirection.BULLISH
            if direction == StructuralRegime.BULLISH else CISDDirection.BEARISH
        )
        confirmation = cisd_process.confirmation
        cisd_valid = bool(
            cisd_process.state == CISDState.CISD_CONFIRMED
            and confirmation is not None
            and confirmation.valid
            and confirmation.active_for_setup
            and not confirmation.historical
            and confirmation.setup_candidate_id == setup_candidate_id
            and confirmation.direction == expected_cisd
            and confirmation.associated_mss_id == cisd_process.sequence.mss_id
            and confirmation.associated_sweep_id == cisd_process.sequence.sweep_id
            and confirmation.confirmation_time <= evaluation_time
        )
        target_valid = self._target_valid(
            target_lrl=target_lrl, direction=direction,
            evaluation_time=evaluation_time,
        )
        checks = (
            ("ACTIVE_SETUP_SPECIFIC_1M_CISD_CONFIRMATION", cisd_valid),
            ("POST_MSS_ACTIVE_CONTINUATION_TARGET_LRL", target_valid),
        )
        qualified = tuple(name for name, valid in checks if valid)
        missing = tuple(name for name, valid in checks if not valid)
        setup = Setup(
            id=self._setup_id(
                candidate_id=setup_candidate_id,
                model=SetupModel.REVERSAL_1, direction=direction,
            ),
            setup_candidate_id=setup_candidate_id,
            model=SetupModel.REVERSAL_1, direction=direction,
            state=ReversalSetupState.MSS_CONFIRMED,
            qualification_time=int(evaluation_time),
            entry_zone_selection_eligible=not missing,
            qualified_prerequisites=qualified,
            missing_prerequisites=missing,
            active_range_id=None, protected_swing_id=None, ote_id=None,
            target_lrl_id=target_lrl.id if target_lrl is not None else None,
            cisd_confirmation_id=confirmation.id if confirmation is not None else None,
            qualifying_sweep_id=(
                confirmation.associated_sweep_id if confirmation is not None else None
            ),
            confluence_ids=(), eligible_zone_ids=(),
        )
        return PreZoneQualificationResult(setup)

    @staticmethod
    def _final_error_id(setup: Setup, reason: str, finalized_time: int) -> str:
        key = f"trading-brain:#27:final-error:{setup.id}:{reason}:{finalized_time}"
        return str(uuid5(NAMESPACE_URL, key))

    @classmethod
    def _final_invalid(
        cls, *, setup: Setup, reason: str, finalized_time: int,
    ) -> FinalQualificationResult:
        return FinalQualificationResult(
            qualification=None,
            error=SetupQualificationError(
                id=cls._final_error_id(setup, reason, finalized_time),
                code=SetupQualificationErrorCode.SETUP_INVALID,
                setup_id=setup.id, reason=reason,
                finalized_time=int(finalized_time),
            ),
        )

    @staticmethod
    def _final_id(
        *, setup: Setup, entry_zone_id: str,
        stop_id: str, target_id: str, finalized_time: int,
        policy_id: str = "CANONICAL_MIN_RR_V1",
    ) -> str:
        key = (
            f"trading-brain:#27:final:{setup.id}:{entry_zone_id}:"
            f"{stop_id}:{target_id}:{finalized_time}"
        )
        # Preserve historical canonical identities exactly. Explicit owner
        # policies are identity-bearing and cannot conflict with legacy replay.
        if policy_id != "CANONICAL_MIN_RR_V1":
            key += f":{policy_id}"
        return str(uuid5(NAMESPACE_URL, key))

    def finalize(
        self, *, phase_a_setup: Setup, entry_zone_selection,
        stop_selection, target_lrl: LRL | None, finalized_time: int,
        risk_reward_policy=None, source_version: str = "canonical-legacy",
        calculation_version: str = "canonical-legacy",
    ) -> FinalQualificationResult:
        """Phase B: consume one frozen Entry, Stop, and Target without reselection."""

        setup = phase_a_setup
        if not setup.entry_zone_selection_eligible:
            return self._final_invalid(
                setup=setup, reason="PHASE_A_NOT_ENTRY_ZONE_SELECTION_ELIGIBLE",
                finalized_time=finalized_time,
            )
        if setup.model == SetupModel.CONTINUATION:
            if setup.state != ContinuationSetupState.CANDIDATE:
                return self._final_invalid(
                    setup=setup, reason="CONTINUATION_PHASE_A_STATE_INVALID",
                    finalized_time=finalized_time,
                )
        elif setup.model == SetupModel.REVERSAL_1:
            if setup.state != ReversalSetupState.MSS_CONFIRMED:
                return self._final_invalid(
                    setup=setup, reason="REVERSAL_PHASE_A_STATE_INVALID",
                    finalized_time=finalized_time,
                )
        else:
            return self._final_invalid(
                setup=setup, reason="SETUP_MODEL_INVALID",
                finalized_time=finalized_time,
            )

        if entry_zone_selection is None:
            return self._final_invalid(
                setup=setup, reason="FROZEN_ENTRY_MISSING",
                finalized_time=finalized_time,
            )
        if (
            getattr(entry_zone_selection.state, "value", None) != "SELECTED"
            or entry_zone_selection.setup_id != setup.id
            or entry_zone_selection.model != setup.model
            or entry_zone_selection.direction != setup.direction
            or entry_zone_selection.selected_zone_id is None
            or entry_zone_selection.eq_normalized is None
        ):
            return self._final_invalid(
                setup=setup, reason="FROZEN_ENTRY_INVALID",
                finalized_time=finalized_time,
            )
        if stop_selection is None:
            return self._final_invalid(
                setup=setup, reason="IMMUTABLE_STOP_MISSING",
                finalized_time=finalized_time,
            )
        if (
            stop_selection.setup_id != setup.id
            or stop_selection.entry_zone_selection_id != entry_zone_selection.id
            or stop_selection.model != setup.model
            or stop_selection.direction != setup.direction
            or stop_selection.frozen_entry_price != entry_zone_selection.eq_normalized
        ):
            return self._final_invalid(
                setup=setup, reason="IMMUTABLE_STOP_INVALID",
                finalized_time=finalized_time,
            )
        if target_lrl is None:
            return self._final_invalid(
                setup=setup, reason="FROZEN_TARGET_MISSING",
                finalized_time=finalized_time,
            )
        if (
            target_lrl.id != setup.target_lrl_id
            or target_lrl.role != LRLRole.CONTINUATION_TARGET
            or target_lrl.regime != setup.direction
            or target_lrl.side != self._required_target_side(setup.direction)
            or not target_lrl.active
            or target_lrl.historical
        ):
            return self._final_invalid(
                setup=setup, reason="FROZEN_TARGET_INVALID",
                finalized_time=finalized_time,
            )
        latest_input_time = max(
            setup.qualification_time,
            entry_zone_selection.selection_time or entry_zone_selection.eligibility_time,
            stop_selection.selection_time,
            target_lrl.selected_time,
        )
        if finalized_time < latest_input_time:
            return self._final_invalid(
                setup=setup, reason="FINAL_VALIDATION_PRECEDES_FROZEN_INPUT",
                finalized_time=finalized_time,
            )

        entry = Decimal(entry_zone_selection.eq_normalized)
        stop = Decimal(stop_selection.stop_price)
        target = Decimal(target_lrl.level)
        if setup.direction == StructuralRegime.BULLISH:
            geometry_valid = stop < entry < target
        else:
            geometry_valid = target < entry < stop
        if not geometry_valid:
            return self._final_invalid(
                setup=setup, reason="DIRECTIONAL_ENTRY_STOP_TARGET_GEOMETRY_INVALID",
                finalized_time=finalized_time,
            )

        with localcontext() as context:
            context.prec = max(context.prec, 28)
            risk = abs(entry - stop)
            reward = abs(target - entry)
            if risk <= 0:
                return self._final_invalid(
                    setup=setup, reason="RISK_DISTANCE_INVALID",
                    finalized_time=finalized_time,
                )
            r_multiple = reward / risk
        if risk_reward_policy is None:
            required_minimum = self.MINIMUM_R
            policy_id, policy_version = "CANONICAL_MIN_RR_V1", "1"
        else:
            required_minimum = risk_reward_policy.minimum_for(setup.model)
            policy_id, policy_version = risk_reward_policy.id, risk_reward_policy.version
        passes = r_multiple >= required_minimum
        if setup.model == SetupModel.CONTINUATION:
            final_state = (
                ContinuationSetupState.ARMED
                if passes else ContinuationSetupState.REJECTED
            )
        else:
            final_state = (
                ReversalSetupState.ENTRY_ZONE_ARMED
                if passes else ReversalSetupState.REJECTED
            )
        record = FinalSetupQualification(
            id=self._final_id(
                setup=setup, entry_zone_id=entry_zone_selection.id,
                stop_id=stop_selection.id, target_id=target_lrl.id,
                finalized_time=finalized_time, policy_id=policy_id,
            ),
            setup_id=setup.id, setup_candidate_id=setup.setup_candidate_id,
            model=setup.model, direction=setup.direction,
            phase_a_state=setup.state, final_state=final_state,
            entry_zone_selection_id=entry_zone_selection.id,
            stop_selection_id=stop_selection.id,
            target_lrl_id=target_lrl.id,
            entry=entry, stop=stop, target=target,
            risk=risk, reward=reward, r_multiple=r_multiple,
            minimum_required_r=required_minimum,
            geometry_valid=True, executable=passes,
            finalized_time=int(finalized_time),
            policy_id=policy_id, policy_version=policy_version,
            entry_model_identity=setup.model.value,
            qualification_reason=("MINIMUM_R_SATISFIED" if passes else "BELOW_MINIMUM_R_REJECTED"),
            source_version=source_version,
            calculation_version=calculation_version,
        )
        return FinalQualificationResult(record, None)
