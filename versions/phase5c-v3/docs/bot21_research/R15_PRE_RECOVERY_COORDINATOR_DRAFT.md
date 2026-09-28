# R15 — GPU and ML systems research

**Status:** coordinator technical research synthesis; no installation, environment creation or code. Hardware values (RTX 5060 Ti ~16 GB, 32 logical CPUs) are user-provided, not benchmarked here.

| Stack | Current documented constraint | R0 implication |
|---|---|---|
| PyTorch | Mainstream CUDA research tooling; reproducibility controls are available but same-output guarantees are constrained to particular software/hardware/platform combinations; deterministic operations can fail closed when unavailable [S39]. | Best default to *evaluate later* due ecosystem, not installed now. Pin versions, CUDA/runtime, driver, seeds, deterministic flags; log nondeterministic ops. |
| JAX | Official docs support GPU on Linux; Windows CUDA is unsupported natively and WSL2 experimental in current docs [S40]. | Additional platform friction for this Windows PC; no demonstrated Phase R0 need. |
| TensorFlow | Official install docs state native Windows GPU support stopped after TF 2.10; current GPU use is WSL2/Linux [S41]. | Not first choice unless an existing, justified dependency appears. |

NVIDIA lists RTX 5060 Ti as Blackwell compute capability 12.0 and CUDA 12.8 as Blackwell baseline support [S42]. This does not by itself prove current framework wheel/kernels (including custom Mamba/flash-attention operations) support the card; validate exact stack versions later. 16 GB VRAM is likely sufficient for modest experiments but not a performance claim. CPU baselines and deterministic small-model research remain important.

**Future environment specification (TECHNICAL_CONSTRAINT):** isolated BOT 2.1 environment; exact OS/WSL choice decided only after framework-wheel compatibility check; fixed Python/framework/CUDA/driver dependencies; lockfile/constraints; artifact/checkpoint metadata; deterministic-mode smoke tests; CPU fallback; benchmark latency/memory only on permitted synthetic/training data; no secret credentials or broker packages. **No package installation authorized in R0.**
