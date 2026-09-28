from __future__ import annotations
import importlib.util, os, platform, subprocess

def audit_environment() -> dict:
    gpu = "UNAVAILABLE"
    try:
        output = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True, stderr=subprocess.DEVNULL).strip()
        gpu = output or "NONE"
    except Exception: pass
    return {"python": platform.python_version(), "windows": platform.platform(), "cpu_logical": os.cpu_count(),
            "ram_bytes": "ACCESS_RESTRICTED", "gpu": gpu, "cuda_available": False, "torch_installed": bool(importlib.util.find_spec("torch")),
            "numpy_version": __import__("numpy").__version__, "decision": "NUMPY_ISOLATED_RESEARCH; DO_NOT_INSTALL_CUDA_OR_TORCH"}
