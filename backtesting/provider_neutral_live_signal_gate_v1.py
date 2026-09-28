"""Warm-up gate preventing live signals before sufficient canonical bars exist."""
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class LiveSignalGateV1:
    minimum_bars: int = 30
    comparison_only: bool = True
    trading_authority: bool = False

    def evaluate(self, bar_count: int) -> dict:
        ready = int(bar_count) >= self.minimum_bars
        return {"schema_version": "provider-neutral-live-signal-gate-v1",
                "bar_count": int(bar_count), "minimum_bars": self.minimum_bars,
                "signal_generation_permitted": ready,
                "status": "READY" if ready else "WARMUP_REQUIRED",
                "comparison_only": True, "trading_authority": False}
