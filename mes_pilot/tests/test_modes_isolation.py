"""Operating-mode isolation: only the simulator or the advisory outbox is reachable; LIVE_AUTO never is."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mes_pilot.alerts import AlertOutbox
from mes_pilot.modes import (AlertRoute, LiveAutoDisabled, OperatingMode, RouteViolation, SimulatorRoute,
                             build_route)
from mes_pilot.simulator import PaperSimulator

PKG = Path(__file__).resolve().parents[1]

FORBIDDEN = (
    "subprocess", "selenium", "playwright", "pyautogui", "keyboard", "pynput", "webbrowser", "win32api",
    "win32com", "ctypes", "socket", "requests", "httpx", "urllib.request", "websocket", "websockets",
    "ib_insync", "ibapi", "exchange", "integrations", "execution", "hyperliquid", "aiohttp", "http.client",
    "smtplib", "ftplib", "telnetlib",
)
NETWORK_DATA_ALLOWED = {"databento": {"live_feed.py"}}   # read-only market data, live feed module only
ORDER_WORDS = ("submit", "place", "order", "modify", "cancel", "buy", "sell", "flatten", "click", "hotkey", "send")


@pytest.fixture
def sim(cfg, tmp_path):
    return PaperSimulator(cfg, tmp_path / "sim.json")


@pytest.fixture
def outbox(tmp_path):
    return AlertOutbox(tmp_path / "alerts.jsonl")


# ---------------------------------------------------------------- routes
def test_paper_auto_builds_only_a_simulator_route(sim, outbox):
    route = build_route("PAPER_AUTO", simulator=sim)
    assert type(route) is SimulatorRoute and route.kind == "SIMULATOR"
    with pytest.raises(RouteViolation):
        build_route(OperatingMode.PAPER_AUTO, simulator=sim, outbox=outbox)
    with pytest.raises(RouteViolation):
        build_route(OperatingMode.PAPER_AUTO, simulator=None)
    with pytest.raises(RouteViolation):
        build_route(OperatingMode.PAPER_AUTO, simulator=object())


def test_paper_auto_refuses_simulator_subclass(cfg, tmp_path):
    """Regression: isinstance() accepted a subclass whose submit() could reach anything."""
    class Sneaky(PaperSimulator):
        def submit(self, intent, quote):  # pragma: no cover - must never be reachable
            raise AssertionError("external route")

    with pytest.raises(RouteViolation):
        build_route("PAPER_AUTO", simulator=Sneaky(cfg, tmp_path / "x.json"))


def test_prop_manual_alert_route_has_no_order_capability(sim, outbox):
    route = build_route("PROP_MANUAL_ALERTS", outbox=outbox)
    assert type(route) is AlertRoute and route.kind == "MANUAL_ALERT"
    public = [n for n in dir(route) if not n.startswith("_")]
    assert sorted(public) == ["emit", "kind", "mode"]
    for word in ORDER_WORDS:
        assert not any(word in n.lower() for n in dir(route) if not n.startswith("__")), word
    with pytest.raises(AttributeError):
        route.submit = lambda *a: None          # __slots__: cannot be monkey-patched in
    with pytest.raises(RouteViolation):
        build_route("PROP_MANUAL_ALERTS", simulator=sim, outbox=outbox)
    with pytest.raises(RouteViolation):
        build_route("PROP_MANUAL_ALERTS", outbox=None)


@pytest.mark.parametrize("flag", [False, True])
def test_live_auto_always_refused(sim, outbox, flag):
    with pytest.raises(LiveAutoDisabled):
        build_route("LIVE_AUTO", live_auto_enabled=flag)
    with pytest.raises(LiveAutoDisabled):
        build_route(OperatingMode.LIVE_AUTO, simulator=sim, outbox=outbox, live_auto_enabled=flag)


def test_checked_in_config_keeps_live_auto_disabled(cfg):
    assert cfg.live_auto_enabled is False and cfg.mode == "PAPER_AUTO"


def test_alert_outbox_exposes_no_order_methods():
    names = [n for n in dir(AlertOutbox) if not n.startswith("__")]
    for word in ("submit", "place", "order", "modify", "buy", "sell", "click", "hotkey", "send"):
        assert not any(word in n.lower() for n in names), (word, names)


# ---------------------------------------------------------------- static import scan
def _imports(tree: ast.AST) -> list[tuple[str, int]]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:            # relative import inside mes_pilot
                continue
            mod = node.module or ""
            out.append((mod, node.lineno))
            out += [(f"{mod}.{a.name}", node.lineno) for a in node.names]
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
            if name in ("__import__", "import_module"):
                arg = node.args[0] if node.args else None
                target = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else "<dynamic>"
                out.append((target, node.lineno))
    return out


def _matches(name: str, banned: str) -> bool:
    return name == banned or name.startswith(banned + ".")


def _sources():
    files = sorted(p for p in PKG.rglob("*.py") if "tests" not in p.relative_to(PKG).parts)
    assert any(p.name == "engine.py" for p in files)
    return files


def test_no_forbidden_imports_anywhere_in_mes_pilot():
    violations = []
    for path in _sources():
        for name, line in _imports(ast.parse(path.read_text(encoding="utf-8"), str(path))):
            if name == "<dynamic>":
                violations.append(f"{path.name}:{line} dynamic import")
                continue
            for banned in FORBIDDEN:
                if _matches(name, banned):
                    violations.append(f"{path.name}:{line} imports {name}")
            for allowed, files in NETWORK_DATA_ALLOWED.items():
                if _matches(name, allowed) and path.name not in files:
                    violations.append(f"{path.name}:{line} imports {name} (only allowed in {sorted(files)})")
    assert violations == []


def test_import_scanner_catches_known_bad_patterns():
    src = ("import subprocess\nfrom urllib import request\nimport urllib.request as r\nfrom exchange.client import X\n"
           "import importlib\nimportlib.import_module(name)\n__import__('socket')\nimport databento\n")
    names = [n for n, _ in _imports(ast.parse(src))]
    assert any(_matches(n, "subprocess") for n in names)
    assert sum(_matches(n, "urllib.request") for n in names) >= 2
    assert any(_matches(n, "exchange") for n in names)
    assert "<dynamic>" in names and "socket" in names and "databento" in names
