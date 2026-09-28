import json
import numpy as np
import pytest
from .contracts import ModelArtifact, ModelSpec, canonical_hash
from .hardware import audit_environment
from .inference import RegimeModel, load_artifact
from .model import MultiHeadMLP, CausalTemporalConv
from .sequences import build_sequences

def fixture_rows(n=12):
    return [{"observation_time": f"2026-01-01T00:{i:02d}:00Z", "session_id":"S1", "instrument":"ES",
             "values":{"f1":float(i),"f2":float(i%3)}, "targets":{"direction":i%3,"volatility":(i+1)%3,"structure":(i+2)%3}} for i in range(n)]

def artifact(tmp_path):
    net=MultiHeadMLP(4,4,seed=2); state=net.state(); prep={"feature_count":2,"means":[0,0],"scales":[1,1]}
    spec=ModelSpec("m1","MLP_MULTIHEAD","f1","r1","d1",2,4,seed=2); return tmp_path/"model.json", {"schema_version":"bot2-neural-model-artifact-v1","spec":spec.to_dict(),"weights":state,"preprocessing":prep,"weights_sha256":canonical_hash(state),"preprocessing_sha256":canonical_hash(prep),"framework":"numpy","dependency_versions":{"numpy":np.__version__},"git_commit":"c","trading_authority":False}

def test_sequence_tensor_and_boundary_isolation():
    batch=build_sequences(fixture_rows(),sequence_length=3,feature_names=("f1","f2")); assert batch.x.shape==(10,3,2)
    broken=fixture_rows(); broken[4]["session_id"]="S2"; assert build_sequences(broken,sequence_length=3,feature_names=("f1","f2")).x.shape[0] < 10
    assert build_sequences(broken,sequence_length=3,feature_names=("f1","f2")).rejection_counts["SESSION_BOUNDARY"] > 0

def test_sequence_gap_is_not_compressed_and_eligibility_is_deterministic():
    rows=fixture_rows()
    rows[5]["observation_time"]="2026-01-01T00:07:00Z"
    first=build_sequences(rows,sequence_length=3,feature_names=("f1","f2"))
    second=build_sequences(rows,sequence_length=3,feature_names=("f1","f2"))
    assert first.x.shape[0] < 10
    assert first.rejection_counts["SEQUENCE_GAP"] > 0
    assert first.rejection_counts == second.rejection_counts
    assert np.array_equal(first.x,second.x)

def test_sequence_rejects_contract_change_and_irregular_cadence():
    rows=fixture_rows()
    for row in rows: row["contract_id"]="ESM6"
    rows[4]["contract_id"]="ESU6"
    assert build_sequences(rows,sequence_length=3,feature_names=("f1",)).rejection_counts["CONTRACT_BOUNDARY"] > 0
    rows=fixture_rows(); rows[4]["observation_time"]="2026-01-01T00:03:30Z"
    assert build_sequences(rows,sequence_length=3,feature_names=("f1",)).rejection_counts["CADENCE_VIOLATION"] > 0

def test_future_mutation_does_not_change_prefix_sequences():
    a=build_sequences(fixture_rows(),sequence_length=3,feature_names=("f1","f2")); changed=fixture_rows(); changed[-1]["values"]["f1"]=999
    b=build_sequences(changed,sequence_length=3,feature_names=("f1","f2")); assert np.array_equal(a.x[:-1],b.x[:-1])

def test_training_only_normalization_and_deterministic_inference(tmp_path):
    net=MultiHeadMLP(4,4,seed=3); x=np.ones((4,4)); y={"direction":np.array([0,1,2,1]),"volatility":np.array([0,1,2,1]),"structure":np.array([0,1,2,1])}; net.fit(x,y,epochs=2)
    assert np.allclose(net.predict(x)["direction"],net.predict(x)["direction"])
    path,data=artifact(tmp_path); path.write_text(json.dumps(data)); model=RegimeModel(load_artifact(path)); p=model.predict(np.zeros((2,2)),timestamp="t",instrument="ES"); assert p.model_id=="m1"

def test_corrupt_artifact_rejected_and_interface_serializes(tmp_path):
    path,data=artifact(tmp_path); data["weights_sha256"]="bad"; path.write_text(json.dumps(data))
    with pytest.raises(ValueError): load_artifact(path)

def test_abstention_invalid_input_and_entropy(tmp_path):
    path,data=artifact(tmp_path); path.write_text(json.dumps(data)); model=RegimeModel(load_artifact(path)); p=model.predict(np.array([[np.nan,0],[0,0]]),timestamp="t",instrument="ES"); assert p.abstain and "INVALID_INPUT" in p.reason_codes

def test_temporal_conv_is_causal_and_hardware_audit_is_safe():
    x=np.arange(24,dtype=float).reshape(2,4,3); conv=CausalTemporalConv(3); out=conv.transform(x)
    prefix=conv.transform(x[:, :3, :]); assert out.shape==(2,9) and prefix.shape==(2,9); assert "decision" in audit_environment()
