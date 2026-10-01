"""Explicit operating modes and the only routes each mode may reach.

PAPER_AUTO          -> SimulatorRoute (in-process simulator; no network, no broker)
PROP_MANUAL_ALERTS  -> AlertRoute (writes advisory alerts; cannot submit, prefill,
                       modify or cancel any order, nor drive any UI)
LIVE_AUTO           -> always refused in this version. No personal-live adapter
                       has been qualified, and implementing one must not enable it.
"""
from __future__ import annotations

from enum import Enum


class OperatingMode(str, Enum):
    PAPER_AUTO = "PAPER_AUTO"
    PROP_MANUAL_ALERTS = "PROP_MANUAL_ALERTS"
    LIVE_AUTO = "LIVE_AUTO"


class LiveAutoDisabled(RuntimeError):
    pass


class RouteViolation(RuntimeError):
    pass


class SimulatorRoute:
    kind = "SIMULATOR"
    mode = OperatingMode.PAPER_AUTO

    def __init__(self, simulator):
        from mes_pilot.simulator import PaperSimulator

        # Exact type: a subclass could override submit() with an external route.
        if type(simulator) is not PaperSimulator:
            raise RouteViolation("PAPER_AUTO may only route to the in-process PaperSimulator")
        self._simulator = simulator

    def submit(self, intent, quote):
        return self._simulator.submit(intent, quote)


class AlertRoute:
    """Advisory only. Deliberately exposes nothing but ``emit``."""

    kind = "MANUAL_ALERT"
    mode = OperatingMode.PROP_MANUAL_ALERTS
    __slots__ = ("_outbox",)

    def __init__(self, outbox):
        from mes_pilot.alerts import AlertOutbox

        if type(outbox) is not AlertOutbox:
            raise RouteViolation("PROP_MANUAL_ALERTS may only route to the advisory AlertOutbox")
        self._outbox = outbox

    def emit(self, alert):
        return self._outbox.emit(alert)


def build_route(mode: OperatingMode | str, *, simulator=None, outbox=None, live_auto_enabled: bool = False):
    mode = OperatingMode(mode)
    if mode is OperatingMode.PAPER_AUTO:
        if outbox is not None:
            raise RouteViolation("PAPER_AUTO does not take an alert outbox")
        return SimulatorRoute(simulator)
    if mode is OperatingMode.PROP_MANUAL_ALERTS:
        if simulator is not None:
            raise RouteViolation("PROP_MANUAL_ALERTS has no execution route; shadow paper runs as a separate PAPER_AUTO engine")
        return AlertRoute(outbox)
    # LIVE_AUTO: refused regardless of the flag. The flag is read only to make
    # the refusal reason explicit in logs.
    reason = (
        "LIVE_AUTO is disabled: no qualified personal-live broker adapter exists in this version"
        if not live_auto_enabled
        else "LIVE_AUTO flag is set but no qualified adapter or explicit activation record exists; refusing"
    )
    raise LiveAutoDisabled(reason)
