"""BOT 2.0 Phase 5 research-only neural Model A contracts and NumPy runner."""
from .contracts import ModelSpec, ModelArtifact, RegimePrediction
from .sequences import build_sequences
from .model import MultiHeadMLP, CausalTemporalConv
from .inference import RegimeModel, load_artifact

__all__ = ["ModelSpec", "ModelArtifact", "RegimePrediction", "build_sequences", "MultiHeadMLP", "CausalTemporalConv", "RegimeModel", "load_artifact"]
