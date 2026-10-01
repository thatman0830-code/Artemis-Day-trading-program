"""Shared fixtures for the MES pilot tests (no network, no credentials)."""
from __future__ import annotations

import pytest

from mes_pilot.config import load_config


@pytest.fixture(scope="session")
def cfg():
    """The checked-in pilot config, unmodified."""
    return load_config()


@pytest.fixture(scope="session")
def cfg_no_vol():
    """Pilot config with the volatility-percentile filter disabled.

    That filter needs 60 prior sessions of M5 ATR history; engine tests that
    run a single hand-built session disable it (it changes config_hash).
    """
    return load_config(overrides={"strategy": {"volatility_filter_enabled": False}})
