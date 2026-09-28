from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from .models import OrderType, StrategyRequirements, fingerprint


@dataclass(frozen=True)
class EngineCapabilities:
    version: str = "core-v1-capabilities-1"
    supported_markets: tuple[str, ...] = ("BTC", "ES", "NQ")
    # Core v1 currently executes market orders only. Advertising more would let a
    # strategy pass preflight and fail later, which is an unsafe capability lie.
    supported_order_types: tuple[OrderType, ...] = (OrderType.MARKET,)
    funding_supported: bool = False
    rollover_supported: bool = False


@dataclass(frozen=True)
class CapabilityIssue:
    code: str
    detail: str


@dataclass(frozen=True)
class CapabilityReport:
    id: str
    accepted: bool
    requirements_id: str
    capabilities_version: str
    issues: tuple[CapabilityIssue, ...]


def validate_capabilities(requirements: StrategyRequirements, *, capabilities: EngineCapabilities,
                          has_volume: bool, has_funding: bool, has_rollover: bool) -> CapabilityReport:
    issues: list[CapabilityIssue] = []
    for market in requirements.markets:
        if market not in capabilities.supported_markets:
            issues.append(CapabilityIssue("UNSUPPORTED_MARKET", market))
    for order_type in requirements.order_types:
        if order_type not in capabilities.supported_order_types:
            issues.append(CapabilityIssue("UNSUPPORTED_ORDER_TYPE", order_type.value))
    if requirements.requires_volume_for_partial_fills and not has_volume:
        issues.append(CapabilityIssue("MISSING_VOLUME", "partial fills require volume"))
    if requirements.requires_funding and (not capabilities.funding_supported or not has_funding):
        issues.append(CapabilityIssue("MISSING_FUNDING", "BTC funding facts are required"))
    if requirements.requires_rollover and (not capabilities.rollover_supported or not has_rollover):
        issues.append(CapabilityIssue("MISSING_ROLLOVER", "futures rollover facts are required"))
    rid = fingerprint(requirements)
    ident = sha256((rid + capabilities.version + "|".join(i.code + i.detail for i in issues)).encode()).hexdigest()
    return CapabilityReport(ident, not issues, rid, capabilities.version, tuple(issues))
