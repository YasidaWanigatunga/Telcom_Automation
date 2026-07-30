"""Each check is tested in isolation: no engine, no other checks."""
from __future__ import annotations

import pytest

from capacity_engine.models import CheckStatus
from capacity_engine.registry import build_check
from conftest import site


def run(name: str, rules, **overrides):
    return build_check(name, rules.config_for(name)).evaluate(site(**overrides))


# ------------------------------------------------------------------ RNP

class TestRnpCheck:
    def test_high_load_passes(self, rules):
        assert run("rnp", rules, current_load_pct=92).status is CheckStatus.PASS

    def test_low_load_fails(self, rules):
        r = run("rnp", rules, current_load_pct=40)
        assert r.status is CheckStatus.FAIL
        assert "40.0%" in r.reason  # the reason must carry the actual value

    @pytest.mark.parametrize("load", [77.0, 78.5, 79.9])
    def test_borderline_load_needs_review(self, rules, load):
        # threshold 80, band 3 -> [77, 80) is borderline
        assert run("rnp", rules, current_load_pct=load).status is CheckStatus.NEEDS_REVIEW

    def test_no_spectrum_fails_regardless_of_load(self, rules):
        r = run("rnp", rules, current_load_pct=99, spectrum_available=False)
        assert r.status is CheckStatus.FAIL

    def test_missing_data_needs_review(self, rules):
        r = run("rnp", rules, current_load_pct=None)
        assert r.status is CheckStatus.NEEDS_REVIEW
        assert "current_load_pct" in r.reason


# --------------------------------------------------------- Transmission

class TestTransmissionCheck:
    def test_ample_capacity_passes(self, rules):
        # required 600 + 20% spare -> target 720
        assert run("transmission", rules,
                   backhaul_capacity_mbps=800).status is CheckStatus.PASS

    def test_shortfall_fails_with_prerequisite(self, rules):
        r = run("transmission", rules, backhaul_capacity_mbps=450)
        assert r.status is CheckStatus.FAIL
        # The prerequisite comes from config, not from the check's code.
        assert r.prerequisite == "BACKHAUL_UPGRADE"

    def test_marginal_shortfall_needs_review(self, rules):
        # target 720, band 5% -> [684, 720) is borderline
        assert run("transmission", rules,
                   backhaul_capacity_mbps=700).status is CheckStatus.NEEDS_REVIEW

    def test_missing_data_needs_review(self, rules):
        assert run("transmission", rules,
                   backhaul_required_mbps=None).status is CheckStatus.NEEDS_REVIEW


# ---------------------------------------------------------------- Power

class TestPowerCheck:
    def test_sufficient_headroom_passes(self, rules):
        # required 2.8 + 0.5 margin -> target 3.3
        assert run("power", rules, power_headroom_kw=5.0).status is CheckStatus.PASS

    def test_insufficient_headroom_fails(self, rules):
        assert run("power", rules, power_headroom_kw=2.0).status is CheckStatus.FAIL

    def test_marginal_headroom_needs_review(self, rules):
        # target 3.3, band 0.2 -> [3.1, 3.3) is borderline
        assert run("power", rules,
                   power_headroom_kw=3.2).status is CheckStatus.NEEDS_REVIEW

    def test_missing_data_needs_review(self, rules):
        assert run("power", rules,
                   power_headroom_kw=None).status is CheckStatus.NEEDS_REVIEW


# ---------------------------------------------------------- Civil works

class TestCivilWorksCheck:
    def test_space_available_passes(self, rules):
        assert run("civil_works", rules,
                   floor_space_available=True).status is CheckStatus.PASS

    def test_no_space_fails_with_prerequisite(self, rules):
        r = run("civil_works", rules, floor_space_available=False)
        assert r.status is CheckStatus.FAIL
        assert r.prerequisite == "CIVIL_WORKS_REQUIRED"

    def test_missing_field_needs_review(self, rules):
        # The assumed field is absent - the fail-safe must engage.
        assert run("civil_works", rules,
                   floor_space_available=None).status is CheckStatus.NEEDS_REVIEW