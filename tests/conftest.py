"""Shared fixtures and builders for the test suite."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import capacity_engine.checks  # noqa: F401 - populates CHECK_REGISTRY
from capacity_engine.config import RulesConfig, load_rules
from capacity_engine.models import SiteData

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# A site that passes every check cleanly. Tests override one field at a
# time so each test states exactly what it is exercising.
GOOD_SITE: dict[str, Any] = {
    "site_id": "SITE-TEST",
    "site_type": "rooftop",
    "current_load_pct": 92,
    "spectrum_available": True,
    "backhaul_capacity_mbps": 800,
    "backhaul_required_mbps": 600,
    "power_headroom_kw": 5.0,
    "power_required_kw": 2.8,
    "floor_space_available": True,
}


def site(**overrides: Any) -> SiteData:
    """Build a SiteData from the healthy baseline with fields replaced."""
    return SiteData(**{**GOOD_SITE, **overrides})


@pytest.fixture
def rules() -> RulesConfig:
    """The real shipped rules file - tests exercise the actual config."""
    return load_rules(PROJECT_ROOT / "config" / "rules.yaml")


def rules_from(data: dict[str, Any]) -> RulesConfig:
    """Build an in-memory rules config for testing reconfiguration."""
    return RulesConfig(**data)