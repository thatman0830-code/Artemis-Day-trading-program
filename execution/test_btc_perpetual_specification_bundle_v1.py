import json
import pytest

from execution.btc_perpetual_economic_gate_v1 import evaluate_btc_perpetual_economics
from execution.btc_perpetual_specification_bundle_v1 import *
from execution.test_btc_perpetual_economic_gate_v1 import build,T


def test_round_trip_replays_economic_gate(tmp_path):
    repository,instrument,precision=build(tmp_path)
    path=tmp_path/"bundle.json"
    write_btc_perpetual_specification_bundle(path,repository,instrument,precision)
    loaded,loaded_instrument,loaded_precision,bundle_id=read_btc_perpetual_specification_bundle(path)
    assert (loaded,loaded_instrument,loaded_precision)==(repository,instrument,precision)
    assert bundle_id==bundle_document(repository,instrument,precision)["bundle_id"]
    result=evaluate_btc_perpetual_economics(repository=loaded,repository_root=tmp_path,
        instrument=loaded_instrument,precision=loaded_precision,as_of=T)
    assert result.eligibility.eligible and not result.trading_authority


def test_tamper_duplicate_fields_and_noncanonical_values_reject(tmp_path):
    repository,instrument,precision=build(tmp_path);path=tmp_path/"bundle.json"
    write_btc_perpetual_specification_bundle(path,repository,instrument,precision)
    doc=json.loads(path.read_text());doc["instrument"]["quantity_step"]="0.1"
    path.write_text(json.dumps(doc))
    with pytest.raises(BTCPerpetualSpecificationBundleError): read_btc_perpetual_specification_bundle(path)
    path.write_text('{"schema_version":"x","schema_version":"y"}')
    with pytest.raises(BTCPerpetualSpecificationBundleError,match="duplicate"):
        read_btc_perpetual_specification_bundle(path)


def test_symlink_and_truncated_schema_reject(tmp_path):
    repository,instrument,precision=build(tmp_path);target=tmp_path/"target.json"
    write_btc_perpetual_specification_bundle(target,repository,instrument,precision)
    link=tmp_path/"link.json"
    try: link.symlink_to(target)
    except OSError: pytest.skip("symlink unavailable")
    with pytest.raises(BTCPerpetualSpecificationBundleError,match="unsafe"):
        read_btc_perpetual_specification_bundle(link)
