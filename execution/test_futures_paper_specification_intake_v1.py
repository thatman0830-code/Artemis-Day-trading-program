import json
from pathlib import Path

import pytest

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from execution.futures_paper_specification_intake_v1 import (
    FuturesPaperSpecificationIntakeError,
    create_futures_paper_specification_intake,
    write_futures_paper_specification_intake,
)


EVIDENCE = Path("backtesting/execution_accounting_v2/MACHINE_READABLE_SPECIFICATION_EVIDENCE.json")


@pytest.mark.parametrize("market,point,tick_value", [
    (FuturesCanonicalMarket.ES, "50", "12.50"),
    (FuturesCanonicalMarket.NQ, "20", "5.00"),
])
def test_retained_terms_admit_but_missing_economics_fail_readiness(market, point, tick_value):
    intake = create_futures_paper_specification_intake(EVIDENCE, market=market)
    terms = dict(intake.instrument_terms)
    assert terms["point_value"] == point and terms["tick_value"] == tick_value
    assert terms["minimum_price_increment"] == "0.25"
    assert intake.paper_specification_ready is False
    assert intake.owner_approved is False
    assert intake.paper_execution_permitted is False
    assert intake.live_trading_permitted is False
    assert intake.trading_authority is False
    assert "OWNER_BROKER_COMMISSION" in intake.missing_requirements
    assert any("MARGIN" in item for item in intake.missing_requirements)


def test_intakes_are_market_isolated_and_content_addressed(tmp_path):
    es = create_futures_paper_specification_intake(EVIDENCE, market=FuturesCanonicalMarket.ES)
    nq = create_futures_paper_specification_intake(EVIDENCE, market=FuturesCanonicalMarket.NQ)
    assert es.intake_id != nq.intake_id
    es_path = write_futures_paper_specification_intake(es, tmp_path)
    nq_path = write_futures_paper_specification_intake(nq, tmp_path)
    assert es_path.parent.name == "ES" and nq_path.parent.name == "NQ"
    assert write_futures_paper_specification_intake(es, tmp_path) == es_path


@pytest.mark.parametrize("mutation", ["tick", "margin", "policy", "default"])
def test_tampered_or_overstated_evidence_rejects(tmp_path, mutation):
    value = json.loads(EVIDENCE.read_text())
    if mutation == "tick": value["instruments"]["ES"]["minimum_price_increment"] = "0.50"
    elif mutation == "margin": value["unavailable_effective_dated_facts"].remove(
        "ES_CLEARING_INITIAL_AND_MAINTENANCE_MARGIN_HISTORY")
    elif mutation == "policy": value["production_policy"] = "ALLOW"
    else: value["economic_values_are_defaults"] = True
    path = tmp_path / "evidence.json"; path.write_text(json.dumps(value))
    with pytest.raises(FuturesPaperSpecificationIntakeError):
        create_futures_paper_specification_intake(path, market=FuturesCanonicalMarket.ES)


def test_cross_market_type_and_non_file_reject(tmp_path):
    with pytest.raises(TypeError):
        create_futures_paper_specification_intake(EVIDENCE, market="ES")
    with pytest.raises(FuturesPaperSpecificationIntakeError, match="unsafe or missing"):
        create_futures_paper_specification_intake(tmp_path, market=FuturesCanonicalMarket.ES)

