from __future__ import annotations
import json, math, time
from pathlib import Path
import numpy as np
from .contracts import ModelArtifact, ModelSpec, RegimePrediction, canonical_hash
from .model import MultiHeadMLP

def _entropy(p): return float(-sum(x*math.log(max(x,1e-12)) for x in p))

class RegimeModel:
    def __init__(self, artifact: ModelArtifact, *, entropy_threshold: float = 1.05, probability_threshold: float = .45):
        self.artifact=artifact; self.entropy_threshold=entropy_threshold; self.probability_threshold=probability_threshold
        state=artifact.weights; self.net=MultiHeadMLP(artifact.spec.sequence_length * artifact.preprocessing.get("feature_count",1), artifact.spec.hidden_width, artifact.spec.seed)
        self.net.w=np.asarray(state["w"]); self.net.b=np.asarray(state["b"]); self.net.heads={k:np.asarray(v) for k,v in state["heads"].items()}; self.net.bias={k:np.asarray(v) for k,v in state["bias"].items()}
    def predict(self, sequence: np.ndarray, *, timestamp: str, instrument: str) -> RegimePrediction:
        start=time.perf_counter(); x=np.asarray(sequence,dtype=float)
        if x.ndim != 2 or not np.isfinite(x).all():
            return RegimePrediction(timestamp,instrument,self.artifact.spec.model_id,{}, {}, {}, "UNCERTAIN",{},None,{"entropy":float("inf"),"disagreement":0},True,("INVALID_INPUT",),0.0)
        flat=x.reshape(1,-1); raw=self.net.predict(flat); distributions={k:{str(i):float(v) for i,v in enumerate(raw[k][0])} for k in raw}
        uncertainty={k:_entropy(raw[k][0]) for k in raw}; abstain=any(v>=self.entropy_threshold or max(raw[k][0])<self.probability_threshold for k,v in uncertainty.items())
        reason=("HIGH_ENTROPY",) if abstain else (); composite="UNCERTAIN" if abstain else max(distributions["direction"], key=distributions["direction"].get)
        return RegimePrediction(timestamp,instrument,self.artifact.spec.model_id,distributions["direction"],distributions["volatility"],distributions["structure"],composite,distributions,None,uncertainty,abstain,reason,(time.perf_counter()-start)*1000,False)

def load_artifact(path: str | Path) -> ModelArtifact:
    data=json.loads(Path(path).read_text(encoding="utf-8"));
    if data.get("schema_version") != "bot2-neural-model-artifact-v1" or data.get("trading_authority"):
        raise ValueError("unsupported or unauthorized model artifact")
    if canonical_hash(data["weights"]) != data["weights_sha256"] or canonical_hash(data["preprocessing"]) != data["preprocessing_sha256"]:
        raise ValueError("corrupted model artifact")
    s=data["spec"]; spec=ModelSpec(**s); return ModelArtifact(spec,data["weights"],data["preprocessing"],data["weights_sha256"],data["preprocessing_sha256"],data.get("framework","numpy"),data.get("dependency_versions",{}),data.get("git_commit","UNKNOWN"),data.get("calibration_sha256"),False)
