"""Engine behaviour: ordering, short-circuit, aggregation, containment."""
from __future__ import annotations

import pytest

from capacity_engine.checks.base import BaseCheck
from capacity_engine.engine import DecisionEngine, evaluate_site
from capacity_engine.models import CheckStatus, Decision, Severity
from capacity_engine.registry import CHECK_REGISTRY, UnknownCheckError
from conftest import rules_from, site


def status_of(result, name: str) -> CheckStatus:
    return next(c.status for c in result.checks if c.name == name)


# --------------------------------------------------------- aggregation

class TestAggregation:
    def test_all_pass_is_approved(self, rules):
        r = evaluate_site(site(), rules)
        assert r.decision is Decision.APPROVED
        assert r.prerequisites == []

    def test_advisory_failure_still_approves_with_prerequisite(self, rules):
        """The brief: a transmission failure may proceed with a flag."""
        r = evaluate_site(site(backhaul_capacity_mbps=450), rules)
        assert r.decision is Decision.APPROVED
        assert r.prerequisites == ["BACKHAUL_UPGRADE"]
        assert status_of(r, "power") is CheckStatus.PASS  # it kept going

    def test_needs_review_beats_approved(self, rules):
        r = evaluate_site(site(power_headroom_kw=3.2), rules)
        assert r.decision is Decision.NEEDS_REVIEW

    def test_blocking_failure_beats_needs_review(self, rules):
        r = evaluate_site(
            site(power_headroom_kw=None, current_load_pct=40), rules
        )
        assert r.decision is Decision.REJECTED


# ------------------------------------------------------- short-circuit

class TestShortCircuit:
    def test_rnp_failure_stops_the_process(self, rules):
        """The brief: an RNP failure should stop the process immediately."""
        r = evaluate_site(site(current_load_pct=40), rules)
        assert r.decision is Decision.REJECTED
        assert status_of(r, "rnp") is CheckStatus.FAIL
        for name in ("transmission", "power", "civil_works"):
            assert status_of(r, name) is CheckStatus.SKIPPED

    def test_skipped_checks_are_reported_not_omitted(self, rules):
        """Audit trail: the reader must see why there is no power result."""
        r = evaluate_site(site(current_load_pct=40), rules)

        assert len(r.checks) == 4
        power = next(c for c in r.checks if c.name == "power")
        assert power.status is CheckStatus.SKIPPED
        assert "blocked by" in power.reason
        assert "rnp" in power.reason

    def test_last_check_blocking_failure_still_rejects(self, rules):
        """Regression: rejection must not be inferred from a SKIPPED result."""
        # civil_works is last in the rooftop list, so nothing follows it.
        cfg = rules.model_copy(deep=True)
        cfg.checks["civil_works"].severity = Severity.BLOCKING

        r = DecisionEngine(cfg).evaluate(site(floor_space_available=False))

        assert r.decision is Decision.REJECTED
        assert not any(c.status is CheckStatus.SKIPPED for c in r.checks)


# ----------------------------------------------------- reconfiguration

class TestReconfiguration:
    def test_severity_is_config_driven_not_hardcoded(self, rules):
        """A different operator can make transmission blocking - no code change."""
        cfg = rules.model_copy(deep=True)
        cfg.checks["rnp"].model_extra["min_load_pct"] = 99

        r = DecisionEngine(cfg).evaluate(site(current_load_pct=92))

        assert status_of(r, "rnp") is CheckStatus.FAIL

    def test_site_type_selects_which_checks_run(self, rules):
        """greenfield omits civil_works in the shipped rules."""
        r = evaluate_site(site(site_type="greenfield"), rules)
        assert [c.name for c in r.checks] == ["rnp", "transmission", "power"]

    def test_thresholds_come_from_config(self, rules):
        """Raising the threshold alone flips a passing site to failing."""
        cfg = rules.model_copy(deep=True)
        # 92% passes the shipped threshold of 80. Raise it well clear of
        # the 3% borderline band so this is an unambiguous FAIL.
        cfg.checks["rnp"].model_extra["min_load_pct"] = 99

        r = DecisionEngine(cfg).evaluate(site(current_load_pct=92))

        assert status_of(r, "rnp") is CheckStatus.FAIL

    def test_borderline_band_boundary_is_inclusive(self, rules):
        """Exactly `threshold - band` is borderline, not a failure."""
        cfg = rules.model_copy(deep=True)
        cfg.checks["rnp"].model_extra["min_load_pct"] = 95
        # band is 3, so 92 sits exactly on the lower edge of the band.
        r = DecisionEngine(cfg).evaluate(site(current_load_pct=92))
        assert status_of(r, "rnp") is CheckStatus.NEEDS_REVIEW


# ------------------------------------------------------------ fail-safe

class TestFailSafe:
    def test_unknown_site_type_needs_review(self, rules):
        r = evaluate_site(site(site_type="balloon"), rules)
        assert r.decision is Decision.NEEDS_REVIEW
        assert r.checks[0].name == "site_type"

    def test_site_type_matching_is_case_insensitive(self, rules):
        assert evaluate_site(site(site_type="RoofTop"), rules).decision \
            is Decision.APPROVED

    def test_a_crashing_check_degrades_to_review(self, rules, monkeypatch):
        """A bug in one check must not fail the whole evaluation."""
        class BoomCheck(BaseCheck):
            name = "power"
            def evaluate(self, site):
                raise RuntimeError("simulated bug")

        monkeypatch.setitem(CHECK_REGISTRY, "power", BoomCheck)
        r = evaluate_site(site(), rules)

        assert status_of(r, "power") is CheckStatus.NEEDS_REVIEW
        assert r.decision is Decision.NEEDS_REVIEW
        assert status_of(r, "civil_works") is CheckStatus.PASS  # others ran

    def test_unimplemented_check_fails_at_startup(self):
        """Config errors surface at construction, not at decision time."""
        cfg = rules_from({
            "site_types": {"rooftop": ["rnp", "does_not_exist"]},
            "checks": {"rnp": {}, "does_not_exist": {}},
        })
        with pytest.raises(UnknownCheckError):
            DecisionEngine(cfg)