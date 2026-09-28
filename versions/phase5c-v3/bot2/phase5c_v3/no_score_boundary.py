"""Runtime guard for code paths that must not perform inference or scoring."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_no_score = ContextVar("bot2_phase5c_no_score", default=False)
_blocked_operations = ContextVar("bot2_phase5c_blocked_scoring_operations", default=None)


class NoScoreBoundaryViolation(RuntimeError):
    pass


def no_score_active() -> bool:
    return _no_score.get()


def require_scoring_allowed(operation: str) -> None:
    if _no_score.get():
        operations = _blocked_operations.get()
        if operations is not None:
            operations.append(str(operation))
        raise NoScoreBoundaryViolation(f"PROTECTED_PREFLIGHT_SCORING_OPERATION_BLOCKED:{operation}")


@contextmanager
def protected_no_score_boundary():
    """Fail closed if an inference, prediction, calibration, or metric API is reached."""
    token = _no_score.set(True)
    operations: list[str] = []
    operations_token = _blocked_operations.set(operations)
    try:
        yield operations
    finally:
        _blocked_operations.reset(operations_token)
        _no_score.reset(token)
