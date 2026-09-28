"""Shared serialized position-state boundary; lifecycle ownership remains #29.6."""

from enum import Enum


class PositionState(str, Enum):
    NOT_OPEN = "NOT_OPEN"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
