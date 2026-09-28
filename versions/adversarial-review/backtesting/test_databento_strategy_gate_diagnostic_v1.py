from types import SimpleNamespace
from backtesting.databento_strategy_gate_diagnostic_v1 import diagnose_strategy_gates
def trace(entry,state=None,reason=None,result=None):return SimpleNamespace(entry_point=entry,canonical_state=state,canonical_reason=reason,result=result)
def test_diagnostic_attributes_first_blocking_gate_without_authority():
 displacement=SimpleNamespace(timeframe='5m')
 batch=SimpleNamespace(outcome=SimpleNamespace(value='NO_SETUP'),setup_fact=SimpleNamespace(canonical_reason=None),trace=SimpleNamespace(missing_prerequisites=(),primitive_results=(trace('p20_structural_state_producer.StructuralStateProducer.ingest','BULLISH'),trace('p20_displacement.DisplacementQualificationProducer.evaluate','NOT_QUALIFIED','BODY_THRESHOLD_NOT_MET',displacement))))
 result=diagnose_strategy_gates(SimpleNamespace(batch_results=(batch,)))
 assert result.first_blocking_gate=='DISPLACEMENT_QUALIFICATION' and result.displacement_evaluation_count==1 and result.trading_authority is False


def test_diagnostic_stops_at_target_before_entry_or_risk_stages():
 displacement=SimpleNamespace(timeframe='5m')
 decision=SimpleNamespace(timeframe='5m',accepted_events=(object(),))
 batch=SimpleNamespace(outcome=SimpleNamespace(value='CANDIDATE'),setup_fact=SimpleNamespace(canonical_reason='ACTIVE_CONTINUATION_TARGET_LRL'),trace=SimpleNamespace(missing_prerequisites=(SimpleNamespace(prerequisite='ACTIVE_CONTINUATION_TARGET_LRL'),),primitive_results=(trace('p20_structural_state_producer.StructuralStateProducer.ingest','BULLISH'),trace('p20_displacement.DisplacementQualificationProducer.evaluate','QUALIFIED','OWNER_MECHANICAL_V1_ALL_RULES_SATISFIED',displacement),trace('p20_structural_classification.StructuralBreakQualifier.qualify'),trace('p16_conflict_resolution.ConflictResolver.resolve',result=decision),trace('p21_active_dealing_range.ActiveDealingRangeEngine.update',result=SimpleNamespace(active_range=object())),trace('p22_ote.OTEEngine.update',result=SimpleNamespace(active_ote=object())),trace('p24_lrl_selection.LRLSelectionEngine.select',result=SimpleNamespace(active_lrl=None)),trace('p27_setup_qualification.SetupQualificationEngine.qualify_continuation',result=SimpleNamespace(eligible_for_entry_zone_selection=False)))))
 result=diagnose_strategy_gates(SimpleNamespace(batch_results=(batch,)))
 assert result.first_blocking_gate=='TARGET_LIQUIDITY_SELECTION' and result.entry_zone_selection_count==0 and result.finalization_count==0 and result.trading_authority is False
