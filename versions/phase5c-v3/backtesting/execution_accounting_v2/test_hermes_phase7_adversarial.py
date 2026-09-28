"""Hermes independent adversarial audit tests for V2 Phase 7 reporting and validation.

Audit assignment: AUDIT-V2-PHASE7-REPORTING-VALIDATION

Covers all 7 audit scopes:
  1. Result identity and reconciliation
  2. Economic results
  3. Statistics
  4. Regimes and skip reasons
  5. Evidence partitions
  6. Stress and probability of ruin
  7. Promotion gates
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from backtesting.execution_accounting_v2.reporting_validation import (
    PHASE7_VERSION, BacktestResultV2, EconomicHurdleV2, EvidencePartition,
    FinalizedTradeV2, MetricSnapshotV2, Phase7Error, Phase7Reason,
    ProbabilityOfRuinV2, PromotionDecisionV2, PromotionOutcome,
    ReconciliationInputV2, ReconciliationRecordV2, RegimeLabelV2, SkipReason,
    StressKind, StressResultV2, StressScenarioV2, calculate_metrics,
    economic_hurdles, evaluate_promotion, probability_of_ruin, reconcile,
    run_stress, segment_trades_by_regime,
)
from backtesting.execution_accounting_v2.specifications import (
    canonical_json_bytes,
)


UTC = timezone.utc
T = datetime(2026, 1, 1, tzinfo=UTC)
H = lambda x: hashlib.sha256(x.encode()).hexdigest()
D = Decimal
ZERO = Decimal("0")
ONE = Decimal("1")


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def trade(i=0, *, market="ES", partition=EvidencePartition.UNTOUCHED_OOS,
          net=D("8"), gross=D("10"), funding=D("0"), rr=D("2"),
          run=H("run"), strategy="s1"):
    costs = D("2")
    return FinalizedTradeV2.create(
        run_id=run, market=market, instrument_id=market,
        contract_id=market + "M6",
        opened_at=T + timedelta(hours=i * 2),
        closed_at=T + timedelta(hours=i * 2 + 1),
        partition=partition, strategy_version=strategy,
        accounting_version="a1", quantity=D("1"),
        planned_risk=D("1"), planned_reward=rr,
        gross_pnl=gross, commission=D(".5"), fees=D(".5"),
        slippage=D("1"), funding=funding, settlement_cost=D("0"),
        rollover_friction=D("0"), infrastructure_cost=D("0"),
        net_pnl=net, entry_notional=D("100"), exit_notional=D("110"),
        source_ids=(H("source" + str(i)),),
    )


def recon(unresolved=()):
    return reconcile(ReconciliationInputV2(
        H("run"), *(H(str(i)) for i in range(8)), unresolved,
    ))


def metrics(ts, partition=EvidencePartition.UNTOUCHED_OOS):
    return calculate_metrics(
        trades=tuple(ts), run_id=H("run"), market="ES",
        partition=partition, as_of=T + timedelta(days=30),
    )


# ===========================================================================
# 1. Result identity and reconciliation
# ===========================================================================

class TestResultIdentity:
    """Immutable, content-addressed result records and eight-component lineage."""

    def test_trade_is_immutable(self):
        """FinalizedTradeV2 is frozen."""
        t = trade()
        with pytest.raises(FrozenInstanceError):
            t.net_pnl = D("0")

    def test_trade_id_is_deterministic(self):
        """Same inputs → same trade_id."""
        assert trade().trade_id == trade().trade_id

    def test_trade_id_is_content_addressed(self):
        """Different net_pnl → different trade_id."""
        assert trade(net=D("8")).trade_id != trade(
            net=D("7"), gross=D("9")).trade_id

    def test_reconciliation_complete(self):
        """Complete reconciliation → complete=True, OK."""
        r = recon()
        assert r.complete is True
        assert r.reason is Phase7Reason.OK

    def test_reconciliation_unresolved(self):
        """Unresolved state → complete=False, UNRESOLVED_UPSTREAM_STATE."""
        r = recon((H("open-roll"),))
        assert r.complete is False
        assert r.reason is Phase7Reason.UNRESOLVED_UPSTREAM_STATE

    def test_reconciliation_duplicate_lineage_rejected(self):
        """Duplicate fingerprints in lineage → RECONCILIATION_MISMATCH."""
        h = H("same")
        with pytest.raises(Phase7Error, match="RECONCILIATION"):
            reconcile(ReconciliationInputV2(H("run"), *(h for _ in range(8))))

    def test_reconciliation_id_deterministic(self):
        """Same inputs → same reconciliation_id."""
        assert recon().reconciliation_id == recon().reconciliation_id

    def test_reconciliation_immutable(self):
        """ReconciliationRecordV2 is frozen."""
        r = recon()
        with pytest.raises(FrozenInstanceError):
            r.complete = False

    def test_backtest_result_deterministic(self):
        """Same inputs → identical BacktestResultV2."""
        m = metrics((trade(),))
        kwargs = dict(
            run_id=H("run"),
            reconciliation_id=recon().reconciliation_id,
            metric_snapshot_ids=(m.snapshot_id,),
            stress_result_ids=(),
            promotion_decision_ids=(),
            skip_reasons=(SkipReason.NO_SETUP,),
            reporting_version=PHASE7_VERSION,
        )
        r1 = BacktestResultV2.create(**kwargs)
        r2 = BacktestResultV2.create(**kwargs)
        assert r1 == r2
        assert r1.result_id == r2.result_id

    def test_backtest_result_tamper_rejects(self):
        """Tampered result_id → ValueError at construction."""
        m = metrics((trade(),))
        r = BacktestResultV2.create(
            run_id=H("run"),
            reconciliation_id=recon().reconciliation_id,
            metric_snapshot_ids=(m.snapshot_id,),
            stress_result_ids=(),
            promotion_decision_ids=(),
            skip_reasons=(SkipReason.NO_SETUP,),
            reporting_version=PHASE7_VERSION,
        )
        with pytest.raises((ValueError, FrozenInstanceError)):
            replace(r, result_id=H("tamper"))

    def test_backtest_result_duplicate_lineage_rejected(self):
        """Duplicate metric_snapshot_ids → DUPLICATE_CONFLICT."""
        h = H("m")
        with pytest.raises(Phase7Error, match="DUPLICATE"):
            BacktestResultV2.create(
                run_id=H("run"), reconciliation_id=H("r"),
                metric_snapshot_ids=(h, h),
                stress_result_ids=(),
                promotion_decision_ids=(),
                skip_reasons=(),
                reporting_version=PHASE7_VERSION,
            )

    def test_backtest_result_wrong_version_rejects(self):
        """Wrong reporting_version → VERSION_MISMATCH."""
        with pytest.raises(Phase7Error, match="VERSION"):
            BacktestResultV2.create(
                run_id=H("run"), reconciliation_id=H("r"),
                metric_snapshot_ids=(),
                stress_result_ids=(),
                promotion_decision_ids=(),
                skip_reasons=(),
                reporting_version="wrong",
            )

    def test_reconciliation_eight_components(self):
        """Reconciliation lineage has exactly 8 components."""
        r = recon()
        assert len(r.lineage_ids) == 8

    def test_no_silent_reinterpretation_of_evidence(self):
        """Reconciliation does not modify upstream fingerprints."""
        r = recon()
        input_fingerprints = [H(str(i)) for i in range(8)]
        assert list(r.lineage_ids) == input_fingerprints


# ===========================================================================
# 2. Economic results
# ===========================================================================

class TestEconomicResults:
    """Exact Decimal gross and net P&L, cost attribution, symmetry."""

    def test_cost_reconciliation_exact(self):
        """gross - costs + funding = net."""
        t = trade(funding=D("1"), gross=D("10"), net=D("9"))
        expected = (D("10") - D(".5") - D(".5") - D("1") - D("0")
                    - D("0") - D("0") + D("1"))
        assert t.net_pnl == expected

    def test_cost_mismatch_rejects(self):
        """Wrong net_pnl → COST_RECONCILIATION_MISMATCH."""
        with pytest.raises(Phase7Error, match="COST_RECONCILIATION"):
            trade(net=D("999"))

    def test_no_double_charging(self):
        """Each cost component appears exactly once."""
        t = trade(gross=D("10"), net=D("8"), funding=D("0"))
        # gross=10, commission=.5, fees=.5, slippage=1, settlement=0,
        # rollover=0, infrastructure=0, funding=0
        # net = 10 - .5 - .5 - 1 - 0 - 0 - 0 + 0 = 8
        assert t.net_pnl == D("8")

    def test_funding_signed(self):
        """Positive funding adds to net; negative funding subtracts."""
        # net = gross - costs + funding = 10 - 2 + 2 = 10
        t_pos = trade(funding=D("2"), gross=D("10"), net=D("10"))
        assert t_pos.net_pnl == D("10")
        # net = 10 - 2 + (-2) = 6
        t_neg = trade(funding=D("-2"), gross=D("10"), net=D("6"))
        assert t_neg.net_pnl == D("6")

    def test_long_short_symmetry(self):
        """Long (positive gross) and short (negative gross) are symmetric."""
        t_long = trade(gross=D("10"), net=D("8"))
        t_short = trade(gross=D("-10"), net=D("-12"),
                       funding=D("0"), rr=D("2"))
        assert t_long.gross_pnl == -t_short.gross_pnl

    def test_decimal_only(self):
        """Float in net_pnl → ValueError."""
        with pytest.raises(ValueError):
            trade(net=8.0)

    def test_zero_quantities_nonnegative(self):
        """All cost components must be nonnegative."""
        with pytest.raises(ValueError):
            FinalizedTradeV2.create(
                run_id=H("run"), market="ES", instrument_id="ES",
                contract_id="ESM6",
                opened_at=T, closed_at=T + timedelta(hours=1),
                partition=EvidencePartition.UNTOUCHED_OOS,
                strategy_version="s1", accounting_version="a1",
                quantity=D("1"), planned_risk=D("1"), planned_reward=D("2"),
                gross_pnl=D("10"), commission=D("-1"), fees=D(".5"),
                slippage=D("1"), funding=D("0"), settlement_cost=D("0"),
                rollover_friction=D("0"), infrastructure_cost=D("0"),
                net_pnl=D("8"), entry_notional=D("100"),
                exit_notional=D("110"),
                source_ids=(H("a"),),
            )

    def test_economic_hurdle_pass(self):
        """Net return >= required → passed=True."""
        m = metrics((trade(),))
        hs = economic_hurdles(m, (D("100"),), D("0"))
        assert hs[0].passed is True
        # 8/100 = 0.08 >= 0

    def test_economic_hurdle_fail(self):
        """Net return < required → passed=False."""
        m = metrics((trade(),))
        hs = economic_hurdles(m, (D("100"),), D("1"))
        assert hs[0].passed is False
        # 8/100 = 0.08 < 1

    def test_economic_hurdle_zero_capital_rejects(self):
        """Zero capital → ValueError."""
        m = metrics(())
        with pytest.raises(ValueError):
            economic_hurdles(m, (D("0"),), D("0"))

    def test_hurdle_immutable(self):
        """EconomicHurdleV2 is frozen."""
        m = metrics((trade(),))
        h = economic_hurdles(m, (D("100"),), D("0"))[0]
        with pytest.raises(FrozenInstanceError):
            h.passed = False


# ===========================================================================
# 3. Statistics
# ===========================================================================

class TestStatistics:
    """Expectancy, profit factor, Sharpe, Sortino, drawdown, recovery, etc."""

    def test_normal_metrics(self):
        """Two trades: one win, one loss → correct stats."""
        m = metrics((trade(0), trade(1, net=D("-4"), gross=D("-2"))))
        assert (m.trade_count, m.wins, m.losses) == (2, 1, 1)
        assert m.net_pnl == D("4")
        assert m.expectancy == D("2")
        assert m.profit_factor == D("2")

    def test_empty_metrics(self):
        """Empty trades → null semantics."""
        m = metrics(())
        assert m.expectancy is None
        assert m.profit_factor is None
        assert m.tail_loss is None
        assert m.trade_count == 0

    def test_single_trade_sharpe_null(self):
        """Single trade → Sharpe/Sortino null (need n>=2)."""
        m = metrics((trade(),))
        assert m.sharpe is None
        assert m.sortino is None

    def test_zero_variance_sharpe_null(self):
        """Zero variance → Sharpe null."""
        m = metrics((trade(0), trade(1)))
        # Both have net=8 → variance=0 → Sharpe=None
        assert m.sharpe is None

    def test_drawdown_and_recovery(self):
        """Drawdown = peak - trough; recovery = trades to new peak."""
        m = metrics((
            trade(0),
            trade(1, net=D("-10"), gross=D("-8")),
            trade(2, net=D("12"), gross=D("14")),
        ))
        assert m.maximum_drawdown == D("10")
        assert m.tail_loss == D("-10")
        assert m.recovery_trades == 1

    def test_all_win_no_loss(self):
        """All wins → losses=0, profit_factor=None."""
        m = metrics((trade(0), trade(1)))
        assert m.losses == 0
        assert m.profit_factor is None

    def test_all_loss_no_win(self):
        """All losses → wins=0, profit_factor=0 (zero numerator)."""
        m = metrics((trade(0, net=D("-4"), gross=D("-2")),
                     trade(1, net=D("-4"), gross=D("-2"))))
        assert m.wins == 0
        # profit_factor = sum(wins=0) / -sum(losses=-8) = 0 / 8 = 0
        assert m.profit_factor == D("0")

    def test_zero_denominator_profit_factor(self):
        """Zero total losses → profit_factor=None."""
        m = metrics((trade(),))
        assert m.profit_factor is None

    def test_average_win(self):
        """Average win = sum(wins) / count(wins)."""
        m = metrics((trade(0, net=D("8")),
                     trade(1, net=D("4"), gross=D("6"))))
        # Both wins: avg = (8+4)/2 = 6
        assert m.average_win == D("6")

    def test_average_loss(self):
        """Average loss = sum(losses) / count(losses)."""
        m = metrics((trade(0, net=D("-4"), gross=D("-2")),
                     trade(1, net=D("-8"), gross=D("-6"))))
        assert m.average_loss == D("-6")

    def test_exposure(self):
        """Exposure = sum(exit_notional)."""
        m = metrics((trade(0), trade(1)))
        assert m.exposure == D("220")  # 110*2

    def test_turnover(self):
        """Turnover = sum(entry+exit notional)."""
        m = metrics((trade(0), trade(1)))
        assert m.turnover == D("420")  # (100+110)*2

    def test_metrics_no_lookahead(self):
        """Trade closed after as_of → LOOKAHEAD_REJECTED."""
        with pytest.raises(Phase7Error, match="LOOKAHEAD"):
            calculate_metrics(
                trades=(trade(),),
                run_id=H("run"), market="ES",
                partition=EvidencePartition.UNTOUCHED_OOS,
                as_of=T,
            )

    def test_metrics_duplicate_rejected(self):
        """Duplicate trade_id → DUPLICATE_CONFLICT."""
        t = trade()
        with pytest.raises(Phase7Error, match="DUPLICATE"):
            metrics((t, t))

    def test_metrics_ordering_byte_stable(self):
        """Different input order → same serialized output."""
        a = metrics((trade(1), trade(0)))
        b = metrics((trade(0), trade(1)))
        assert canonical_json_bytes(a) == canonical_json_bytes(b)

    def test_metrics_immutable(self):
        """MetricSnapshotV2 is frozen."""
        m = metrics((trade(),))
        with pytest.raises(FrozenInstanceError):
            m.net_pnl = D("0")

    def test_market_isolation(self):
        """Different market → IDENTITY_MISMATCH."""
        with pytest.raises(Phase7Error):
            metrics((trade(market="NQ"),))

    def test_strategy_version_mix_rejected(self):
        """Mixed strategy versions → VERSION_MISMATCH."""
        a = trade(0)
        b = trade(1, strategy="s2")
        with pytest.raises(Phase7Error, match="VERSION"):
            metrics((a, b))

    def test_partition_isolation(self):
        """Different partition → IDENTITY_MISMATCH."""
        with pytest.raises(Phase7Error, match="IDENTITY"):
            metrics((trade(partition=EvidencePartition.TRAINING),))


# ===========================================================================
# 4. Regimes and skip reasons
# ===========================================================================

class TestRegimes:
    """Point-in-time regime labels and skip reasons."""

    def test_regime_label_point_in_time(self):
        """known_at <= effective_from → valid."""
        r = RegimeLabelV2.create(
            market="ES", instrument_id="ES",
            effective_from=T, effective_to=T + timedelta(days=1),
            known_at=T, volatility="HIGH", trend="UP",
            liquidity="NORMAL", session="RTH",
            label_version="r1", source_ids=(H("x"),),
        )
        assert r.known_at == r.effective_from

    def test_regime_label_lookahead_rejected(self):
        """known_at > effective_from → LOOKAHEAD_REJECTED."""
        with pytest.raises(Phase7Error, match="LOOKAHEAD"):
            RegimeLabelV2.create(
                market="ES", instrument_id="ES",
                effective_from=T, effective_to=T + timedelta(days=1),
                known_at=T + timedelta(seconds=1),
                volatility="H", trend="U", liquidity="N",
                session="R", label_version="r",
                source_ids=(H("x"),),
            )

    def test_regime_label_immutable(self):
        """RegimeLabelV2 is frozen."""
        r = RegimeLabelV2.create(
            market="ES", instrument_id="ES",
            effective_from=T, effective_to=T + timedelta(days=1),
            known_at=T, volatility="H", trend="U",
            liquidity="N", session="R",
            label_version="r1", source_ids=(H("x"),),
        )
        with pytest.raises(FrozenInstanceError):
            r.volatility = "LOW"

    def test_regime_label_id_deterministic(self):
        """Same inputs → same label_id."""
        kwargs = dict(
            market="ES", instrument_id="ES",
            effective_from=T, effective_to=T + timedelta(days=1),
            known_at=T, volatility="H", trend="U",
            liquidity="N", session="R",
            label_version="r1", source_ids=(H("x"),),
        )
        assert (RegimeLabelV2.create(**kwargs).label_id
                == RegimeLabelV2.create(**kwargs).label_id)

    def test_regime_segmentation_preserves_identity(self):
        """Segmentation returns label→trade mapping without reclassifying."""
        label = RegimeLabelV2.create(
            market="ES", instrument_id="ES",
            effective_from=T, effective_to=T + timedelta(days=1),
            known_at=T, volatility="H", trend="U",
            liquidity="N", session="R",
            label_version="r1", source_ids=(H("x"),),
        )
        t = trade()
        result = segment_trades_by_regime(trades=(t,), labels=(label,))
        assert result == ((label.label_id, (t.trade_id,)),)

    def test_regime_missing_label_rejects(self):
        """No matching label → MISSING_REGIME_LABEL."""
        with pytest.raises(Phase7Error, match="MISSING"):
            segment_trades_by_regime(trades=(trade(),), labels=())

    def test_regime_overlap_rejects(self):
        """Multiple matching labels → MISSING_REGIME_LABEL (not exactly 1)."""
        label1 = RegimeLabelV2.create(
            market="ES", instrument_id="ES",
            effective_from=T, effective_to=T + timedelta(days=1),
            known_at=T, volatility="H", trend="U",
            liquidity="N", session="R",
            label_version="r1", source_ids=(H("x"),),
        )
        label2 = RegimeLabelV2.create(
            market="ES", instrument_id="ES",
            effective_from=T, effective_to=T + timedelta(days=1),
            known_at=T, volatility="H", trend="U",
            liquidity="N", session="R",
            label_version="r2", source_ids=(H("y"),),
        )
        with pytest.raises(Phase7Error, match="MISSING"):
            segment_trades_by_regime(
                trades=(trade(),), labels=(label1, label2),
            )

    def test_skip_reasons_are_stable(self):
        """SkipReason enum values are stable."""
        assert SkipReason.NONE.value == "NONE"
        assert SkipReason.NO_SETUP.value == "NO_SETUP"
        assert SkipReason.MISSING_DATA.value == "MISSING_DATA"

    def test_regime_no_post_hoc_relabeling(self):
        """Segmentation doesn't change trade outcomes."""
        t = trade(net=D("8"))
        label = RegimeLabelV2.create(
            market="ES", instrument_id="ES",
            effective_from=T, effective_to=T + timedelta(days=1),
            known_at=T, volatility="H", trend="U",
            liquidity="N", session="R",
            label_version="r1", source_ids=(H("x"),),
        )
        result = segment_trades_by_regime(trades=(t,), labels=(label,))
        # The trade's net_pnl is unchanged
        assert t.net_pnl == D("8")


# ===========================================================================
# 5. Evidence partitions
# ===========================================================================

class TestEvidencePartitions:
    """Strict partition isolation."""

    def test_all_partition_values(self):
        """All 6 partition values exist."""
        assert {EvidencePartition.TRAINING, EvidencePartition.VALIDATION,
                EvidencePartition.UNTOUCHED_OOS, EvidencePartition.FORWARD_RECORDED,
                EvidencePartition.PAPER, EvidencePartition.LIVE} == set(EvidencePartition)

    def test_promotion_rejects_training(self):
        """TRAINING partition for promotion → BLENDED_EVIDENCE_PROHIBITED."""
        m = calculate_metrics(
            trades=(), run_id=H("run"), market="ES",
            partition=EvidencePartition.TRAINING, as_of=T,
        )
        with pytest.raises(Phase7Error, match="BLENDED"):
            evaluate_promotion(
                metrics=m, trades=(), hurdles=(),
                reconciliation=recon(),
            )

    def test_promotion_rejects_validation(self):
        """VALIDATION partition → BLENDED_EVIDENCE_PROHIBITED."""
        m = calculate_metrics(
            trades=(), run_id=H("run"), market="ES",
            partition=EvidencePartition.VALIDATION, as_of=T,
        )
        with pytest.raises(Phase7Error, match="BLENDED"):
            evaluate_promotion(
                metrics=m, trades=(), hurdles=(),
                reconciliation=recon(),
            )

    def test_promotion_rejects_paper(self):
        """PAPER partition → BLENDED_EVIDENCE_PROHIBITED."""
        m = calculate_metrics(
            trades=(), run_id=H("run"), market="ES",
            partition=EvidencePartition.PAPER, as_of=T,
        )
        with pytest.raises(Phase7Error, match="BLENDED"):
            evaluate_promotion(
                metrics=m, trades=(), hurdles=(),
                reconciliation=recon(),
            )

    def test_promotion_rejects_live(self):
        """LIVE partition → BLENDED_EVIDENCE_PROHIBITED."""
        m = calculate_metrics(
            trades=(), run_id=H("run"), market="ES",
            partition=EvidencePartition.LIVE, as_of=T,
        )
        with pytest.raises(Phase7Error, match="BLENDED"):
            evaluate_promotion(
                metrics=m, trades=(), hurdles=(),
                reconciliation=recon(),
            )

    def test_promotion_rejects_forward_recorded(self):
        """FORWARD_RECORDED partition → BLENDED_EVIDENCE_PROHIBITED."""
        m = calculate_metrics(
            trades=(), run_id=H("run"), market="ES",
            partition=EvidencePartition.FORWARD_RECORDED, as_of=T,
        )
        with pytest.raises(Phase7Error, match="BLENDED"):
            evaluate_promotion(
                metrics=m, trades=(), hurdles=(),
                reconciliation=recon(),
            )

    def test_partition_cannot_mix_in_metrics(self):
        """Mixed partitions in metrics → IDENTITY_MISMATCH."""
        with pytest.raises(Phase7Error, match="IDENTITY"):
            metrics((trade(partition=EvidencePartition.TRAINING),))


# ===========================================================================
# 6. Stress and probability of ruin
# ===========================================================================

class TestStressAndRuin:
    """Deterministic stress categories and probability of ruin."""

    @pytest.mark.parametrize("kind", list(StressKind))
    def test_all_stress_kinds_deterministic(self, kind):
        """Each stress kind produces deterministic results."""
        s = StressScenarioV2.create(
            kind=kind, loss_multiplier=D(".25"),
            additional_cost_per_trade=D("1"),
            cluster_size=1, ruin_floor=D("0"),
            scenario_version="v1",
        )
        assert (run_stress(trades=(trade(),), scenario=s,
                           starting_capital=D("100"))
                == run_stress(trades=(trade(),), scenario=s,
                             starting_capital=D("100")))

    def test_stress_clustered_loss_ruin(self):
        """Clustered loss with high multiplier → ruin observed."""
        s = StressScenarioV2.create(
            kind=StressKind.CLUSTERED_LOSS, loss_multiplier=D("2"),
            additional_cost_per_trade=D("20"),
            cluster_size=2, ruin_floor=D("90"),
            scenario_version="v1",
        )
        r = run_stress(
            trades=(trade(), trade(1)),
            scenario=s, starting_capital=D("100"),
        )
        assert r.ruin_observed is True

    def test_stress_no_float(self):
        """Float in stress scenario → ValueError."""
        with pytest.raises(ValueError):
            StressScenarioV2.create(
                kind=StressKind.GAP, loss_multiplier=.2,
                additional_cost_per_trade=D("0"),
                cluster_size=1, ruin_floor=D("0"),
                scenario_version="v",
            )

    def test_stress_immutable(self):
        """StressScenarioV2 is frozen."""
        s = StressScenarioV2.create(
            kind=StressKind.GAP, loss_multiplier=D(".25"),
            additional_cost_per_trade=D("0"),
            cluster_size=1, ruin_floor=D("0"),
            scenario_version="v",
        )
        with pytest.raises(FrozenInstanceError):
            s.loss_multiplier = D("1")

    def test_stress_result_immutable(self):
        """StressResultV2 is frozen."""
        s = StressScenarioV2.create(
            kind=StressKind.GAP, loss_multiplier=D(".25"),
            additional_cost_per_trade=D("0"),
            cluster_size=1, ruin_floor=D("0"),
            scenario_version="v",
        )
        r = run_stress(trades=(trade(),), scenario=s,
                       starting_capital=D("100"))
        with pytest.raises(FrozenInstanceError):
            r.ruin_observed = False

    def test_probability_of_ruin_exact(self):
        """Exact empirical ruin frequency."""
        r = probability_of_ruin(
            paths=((D("-11"),), (D("1"), D("1"))),
            starting_capital=D("10"), ruin_floor=D("0"),
        )
        assert r.probability == D("0.5")
        assert r.ruined_paths == 1

    def test_probability_of_ruin_empty_rejects(self):
        """Empty paths → EMPTY_SAMPLE."""
        with pytest.raises(Phase7Error, match="EMPTY"):
            probability_of_ruin(
                paths=(), starting_capital=D("10"),
                ruin_floor=D("0"),
            )

    def test_probability_of_ruin_immutable(self):
        """ProbabilityOfRuinV2 is frozen."""
        r = probability_of_ruin(
            paths=((D("1"),),),
            starting_capital=D("10"), ruin_floor=D("0"),
        )
        with pytest.raises(FrozenInstanceError):
            r.probability = D("1")

    def test_probability_of_ruin_no_ruin(self):
        """No ruined paths → probability=0."""
        r = probability_of_ruin(
            paths=((D("1"),), (D("1"),)),
            starting_capital=D("10"), ruin_floor=D("0"),
        )
        assert r.probability == D("0")
        assert r.ruined_paths == 0

    def test_probability_of_ruin_all_ruin(self):
        """All paths ruined → probability=1."""
        r = probability_of_ruin(
            paths=((D("-11"),), (D("-11"),)),
            starting_capital=D("10"), ruin_floor=D("0"),
        )
        assert r.probability == D("1")
        assert r.ruined_paths == 2

    def test_stress_cluster_size_must_be_positive(self):
        """cluster_size < 1 → ValueError."""
        with pytest.raises(ValueError):
            StressScenarioV2.create(
                kind=StressKind.GAP, loss_multiplier=D("0"),
                additional_cost_per_trade=D("0"),
                cluster_size=0, ruin_floor=D("0"),
                scenario_version="v",
            )

    def test_stress_deterministic_replay(self):
        """Same inputs → identical stress result."""
        s = StressScenarioV2.create(
            kind=StressKind.GAP, loss_multiplier=D(".5"),
            additional_cost_per_trade=D("1"),
            cluster_size=1, ruin_floor=D("0"),
            scenario_version="v1",
        )
        trades = (trade(0), trade(1, net=D("-4"), gross=D("-2")))
        r1 = run_stress(trades=trades, scenario=s, starting_capital=D("100"))
        r2 = run_stress(trades=trades, scenario=s, starting_capital=D("100"))
        assert r1 == r2


# ===========================================================================
# 7. Promotion gates
# ===========================================================================

class TestPromotionGates:
    """200 OOS trades, independent markets, advisory-only, no bypass."""

    def test_promotion_pass(self):
        """200 OOS trades, all pass → PASS."""
        ts = tuple(trade(i) for i in range(200))
        m = metrics(ts)
        hs = economic_hurdles(m, (D("1000"),), D("0"))
        d = evaluate_promotion(
            metrics=m, trades=ts, hurdles=hs,
            reconciliation=recon(),
        )
        assert d.outcome is PromotionOutcome.PASS
        assert d.advisory_only is True

    def test_promotion_insufficient_evidence(self):
        """< 200 trades → INSUFFICIENT_EVIDENCE."""
        ts = (trade(),)
        d = evaluate_promotion(
            metrics=metrics(ts), trades=ts,
            hurdles=economic_hurdles(metrics(ts), (D("100"),), D("0")),
            reconciliation=recon(),
        )
        assert d.outcome is PromotionOutcome.INSUFFICIENT_EVIDENCE

    def test_promotion_nonpositive_expectancy(self):
        """Negative expectancy → NONPOSITIVE_EXPECTANCY in reasons."""
        ts = tuple(trade(i, net=D("-2"), gross=D("0")) for i in range(200))
        m = metrics(ts)
        d = evaluate_promotion(
            metrics=m, trades=ts,
            hurdles=economic_hurdles(m, (D("100"),), D("-100")),
            reconciliation=recon(),
        )
        assert Phase7Reason.NONPOSITIVE_EXPECTANCY in d.reasons

    def test_promotion_rr_below_one(self):
        """R:R < 1 → PLANNED_RR_BELOW_MINIMUM in reasons."""
        ts = tuple(trade(i, rr=D(".9")) for i in range(200))
        m = metrics(ts)
        d = evaluate_promotion(
            metrics=m, trades=ts,
            hurdles=economic_hurdles(m, (D("100"),), D("0")),
            reconciliation=recon(),
        )
        assert Phase7Reason.PLANNED_RR_BELOW_MINIMUM in d.reasons

    def test_promotion_unresolved_reconciliation(self):
        """Unresolved reconciliation → UNRESOLVED_UPSTREAM_STATE."""
        ts = tuple(trade(i) for i in range(200))
        m = metrics(ts)
        d = evaluate_promotion(
            metrics=m, trades=ts,
            hurdles=economic_hurdles(m, (D("100"),), D("0")),
            reconciliation=recon((H("x"),)),
        )
        assert Phase7Reason.UNRESOLVED_UPSTREAM_STATE in d.reasons

    def test_promotion_blended_evidence_rejected(self):
        """Non-OOS partition → BLENDED_EVIDENCE_PROHIBITED."""
        m = calculate_metrics(
            trades=(), run_id=H("run"), market="ES",
            partition=EvidencePartition.TRAINING, as_of=T,
        )
        with pytest.raises(Phase7Error, match="BLENDED"):
            evaluate_promotion(
                metrics=m, trades=(), hurdles=(),
                reconciliation=recon(),
            )

    def test_promotion_mismatched_lineage(self):
        """Trade lineage != metrics lineage → RECONCILIATION_MISMATCH."""
        t = trade()
        m = metrics((t,))
        with pytest.raises(Phase7Error, match="RECONCILIATION"):
            evaluate_promotion(
                metrics=m, trades=(), hurdles=(),
                reconciliation=recon(),
            )

    def test_promotion_advisory_only(self):
        """Promotion is advisory only — no execution authority."""
        ts = tuple(trade(i) for i in range(200))
        m = metrics(ts)
        d = evaluate_promotion(
            metrics=m, trades=ts,
            hurdles=economic_hurdles(m, (D("100"),), D("0")),
            reconciliation=recon(),
        )
        assert d.advisory_only is True
        assert not hasattr(d, "order")
        assert not hasattr(d, "fill")
        assert not hasattr(d, "submit")

    def test_promotion_immutable(self):
        """PromotionDecisionV2 is frozen."""
        ts = tuple(trade(i) for i in range(200))
        m = metrics(ts)
        d = evaluate_promotion(
            metrics=m, trades=ts,
            hurdles=economic_hurdles(m, (D("100"),), D("0")),
            reconciliation=recon(),
        )
        with pytest.raises(FrozenInstanceError):
            d.outcome = PromotionOutcome.FAIL

    def test_promotion_id_deterministic(self):
        """Same inputs → same decision_id."""
        ts = tuple(trade(i) for i in range(200))
        m = metrics(ts)
        hs = economic_hurdles(m, (D("100"),), D("0"))
        d1 = evaluate_promotion(
            metrics=m, trades=ts, hurdles=hs, reconciliation=recon())
        d2 = evaluate_promotion(
            metrics=m, trades=ts, hurdles=hs, reconciliation=recon())
        assert d1.decision_id == d2.decision_id

    def test_promotion_hurdle_not_met(self):
        """Failing hurdle → ECONOMIC_HURDLE_NOT_MET."""
        ts = tuple(trade(i) for i in range(200))
        m = metrics(ts)
        # net_pnl = 200*8 = 1600; 1600/1 = 1600 >= 10000 → fail
        d = evaluate_promotion(
            metrics=m, trades=ts,
            hurdles=economic_hurdles(m, (D("1"),), D("10000")),
            reconciliation=recon(),
        )
        assert Phase7Reason.ECONOMIC_HURDLE_NOT_MET in d.reasons

    def test_promotion_no_profitability_guarantee(self):
        """BacktestResultV2 has no guarantee field."""
        assert "guarantee" not in BacktestResultV2.__dataclass_fields__
        assert not ({"submit", "authorize_trade", "wallet", "credential"}
                    & set(BacktestResultV2.__dataclass_fields__))

    def test_promotion_fail_outcome(self):
        """Failing all gates → FAIL outcome."""
        ts = tuple(trade(i, net=D("-2"), gross=D("0"),
                        rr=D(".5")) for i in range(200))
        m = metrics(ts)
        d = evaluate_promotion(
            metrics=m, trades=ts,
            hurdles=economic_hurdles(m, (D("1"),), D("100")),
            reconciliation=recon(),
        )
        # Multiple reasons but NOT insufficient trades
        assert d.outcome is PromotionOutcome.FAIL


# ===========================================================================
# 8. Schema and import isolation
# ===========================================================================

class TestSchemaAndIsolation:
    """Schema validation and import isolation."""

    def test_schema_is_machine_readable(self):
        """Schema file is valid JSON with $id."""
        p = Path(__file__).parent / "schemas" / "reporting-validation-v2.schema.json"
        data = json.loads(p.read_text())
        assert data["$id"]

    def test_all_reasons_present(self):
        """All expected reason codes exist."""
        expected = {
            "OK", "EMPTY_SAMPLE", "INCOMPLETE_TRADE", "IDENTITY_MISMATCH",
            "VERSION_MISMATCH", "DUPLICATE_CONFLICT", "CHRONOLOGY_ERROR",
            "LOOKAHEAD_REJECTED", "RECONCILIATION_MISMATCH",
            "COST_RECONCILIATION_MISMATCH", "BLENDED_EVIDENCE_PROHIBITED",
            "MISSING_REGIME_LABEL", "INSUFFICIENT_OOS_TRADES",
            "NONPOSITIVE_EXPECTANCY", "PLANNED_RR_BELOW_MINIMUM",
            "ECONOMIC_HURDLE_NOT_MET", "UNRESOLVED_UPSTREAM_STATE",
            "CHECKPOINT_TAMPERED", "UNSUPPORTED_PROBABILITY_MODEL",
        }
        actual = {r.value for r in Phase7Reason}
        assert expected.issubset(actual)

    def test_trade_chronology_invalid_rejects(self):
        """closed_at <= opened_at → ValueError."""
        t = trade()
        with pytest.raises(ValueError):
            replace(t, closed_at=t.opened_at)

    def test_trade_source_ids_unique(self):
        """Duplicate source_ids → ValueError."""
        with pytest.raises(ValueError, match="lineage"):
            FinalizedTradeV2.create(
                run_id=H("run"), market="ES", instrument_id="ES",
                contract_id="ESM6",
                opened_at=T, closed_at=T + timedelta(hours=1),
                partition=EvidencePartition.UNTOUCHED_OOS,
                strategy_version="s1", accounting_version="a1",
                quantity=D("1"), planned_risk=D("1"), planned_reward=D("2"),
                gross_pnl=D("10"), commission=D(".5"), fees=D(".5"),
                slippage=D("1"), funding=D("0"), settlement_cost=D("0"),
                rollover_friction=D("0"), infrastructure_cost=D("0"),
                net_pnl=D("8"), entry_notional=D("100"),
                exit_notional=D("110"),
                source_ids=(H("a"), H("a")),
            )

    def test_trade_zero_quantity_rejects(self):
        """Zero quantity → ValueError."""
        with pytest.raises(ValueError):
            FinalizedTradeV2.create(
                run_id=H("run"), market="ES", instrument_id="ES",
                contract_id="ESM6",
                opened_at=T, closed_at=T + timedelta(hours=1),
                partition=EvidencePartition.UNTOUCHED_OOS,
                strategy_version="s1", accounting_version="a1",
                quantity=D("0"), planned_risk=D("1"), planned_reward=D("2"),
                gross_pnl=D("10"), commission=D(".5"), fees=D(".5"),
                slippage=D("1"), funding=D("0"), settlement_cost=D("0"),
                rollover_friction=D("0"), infrastructure_cost=D("0"),
                net_pnl=D("8"), entry_notional=D("100"),
                exit_notional=D("110"),
                source_ids=(H("a"),),
            )

    def test_trade_planned_rr_property(self):
        """planned_rr = planned_reward / planned_risk."""
        t = trade(rr=D("3"))
        assert t.planned_rr == D("3")

    def test_trade_turnover_property(self):
        """turnover = entry_notional + exit_notional."""
        t = trade()
        assert t.turnover == D("210")

    def test_skip_reasons_all_present(self):
        """All skip reason values present."""
        expected = {"NONE", "NO_SETUP", "MISSING_DATA", "STALE_DATA",
                    "SESSION_INELIGIBLE", "RISK_REJECTED",
                    "UNRESOLVED_ROLLOVER", "MISSING_FUNDING"}
        actual = {r.value for r in SkipReason}
        assert expected.issubset(actual)

    def test_reconciliation_input_immutable(self):
        """ReconciliationInputV2 is frozen."""
        r = ReconciliationInputV2(
            H("run"), *(H(str(i)) for i in range(8)),
        )
        with pytest.raises(FrozenInstanceError):
            r.run_id = H("other")
