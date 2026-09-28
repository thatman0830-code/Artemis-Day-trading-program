from __future__ import annotations
import numpy as np

def _softmax(z):
    z = z - np.max(z, axis=1, keepdims=True); e = np.exp(z); return e / np.sum(e, axis=1, keepdims=True)

class MultiHeadMLP:
    """Small deterministic shared encoder with direction/volatility/structure heads."""
    def __init__(self, input_width: int, hidden_width: int = 8, seed: int = 0):
        rng=np.random.default_rng(seed); self.w=rng.normal(0,.05,(input_width,hidden_width)); self.b=np.zeros(hidden_width)
        self.heads={"direction": rng.normal(0,.05,(hidden_width,3)), "volatility": rng.normal(0,.05,(hidden_width,3)), "structure": rng.normal(0,.05,(hidden_width,3))}
        self.bias={k:np.zeros(3) for k in self.heads}
    def _forward(self,x):
        h=np.tanh(x@self.w+self.b); return h,{k:_softmax(h@w+self.bias[k]) for k,w in self.heads.items()}
    def predict(self,x): return self._forward(x)[1]
    def fit(self,x,targets,epochs=50,learning_rate=.01):
        y={k:np.eye(3)[np.asarray(v,dtype=int)] for k,v in targets.items()}
        for _ in range(epochs):
            h,p=self._forward(x); grad_h=np.zeros_like(h)
            for k in self.heads:
                grad=(p[k]-y[k])/len(x); grad_h += grad@self.heads[k].T
                self.heads[k]-=learning_rate*h.T@grad; self.bias[k]-=learning_rate*grad.sum(axis=0)
            grad_z=grad_h*(1-h*h); self.w-=learning_rate*x.T@grad_z; self.b-=learning_rate*grad_z.sum(axis=0)
        return self
    def state(self): return {"w":self.w.tolist(),"b":self.b.tolist(),"heads":{k:v.tolist() for k,v in self.heads.items()},"bias":{k:v.tolist() for k,v in self.bias.items()}}

class CausalTemporalConv:
    """Small causal temporal convolution candidate; no future timestep is read."""
    def __init__(self, input_width, seed=0): self.input_width=input_width; self.seed=seed
    def transform(self,x):
        if x.ndim != 3: raise ValueError("expected [batch, time, features]")
        return np.concatenate((x.mean(axis=1), x[:, -1, :], x[:, 1:, :].mean(axis=1) - x[:, :-1, :].mean(axis=1)), axis=1)
