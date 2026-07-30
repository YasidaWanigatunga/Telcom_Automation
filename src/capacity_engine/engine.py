"""Orchestration: run the configured checks and aggregate one decision."""
from __future__ import annotations

import logging

from .config import RulesConfig
from .models import (
    CheckResult,
    CheckStatus,
    Decision,
    DecisionResult,
    Severity,
    SiteData,
)
from .registry import CHECK_REGISTRY, UnknownCheckError, build_check

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Runs the checks configured for a site's type and aggregates the result.

    The engine owns three things and nothing else:
      1. which checks run, and in what order  (read from config)
      2. when to stop early                   (a blocking FAIL)
      3. how per-check results roll up        (precedence rules below)

    It contains no domain logic. Every threshold lives in the rules file
    and every rule about a specific check lives in that check's class.
    """

    def __init__(self, rules: RulesConfig) -> None:
        self.rules = rules
        self._validate_implementations()

    # ------------------------------------------------------- startup

    def _validate_implementations(self) -> None:
        """Fail fast: every check named in the rules must have a class."""
        referenced = {
            name for names in self.rules.site_types.values() for name in names
        }
        missing = sorted(referenced - set(CHECK_REGISTRY))
        if missing:
            raise UnknownCheckError(
                f"Rules reference check(s) with no implementation: {missing}. "
                f"Registered: {sorted(CHECK_REGISTRY)}"
            )

    # ---------------------------------------------------- public API

    def evaluate(self, site: SiteData) -> DecisionResult:
        """Evaluate one site. Never raises on bad input data."""
        check_names = self.rules.checks_for(site.site_type)

        # An unrecognised site type is an unknown, not an error: we do not
        # know which checks apply, so we cannot approve or reject it.
        if check_names is None:
            return DecisionResult(
                site_id=site.site_id,
                site_type=site.site_type,
                decision=Decision.NEEDS_REVIEW,
                checks=[
                    CheckResult(
                        name="site_type",
                        status=CheckStatus.NEEDS_REVIEW,
                        reason=(
                            f"Unrecognised site_type {site.site_type!r}; "
                            f"known types: {sorted(self.rules.site_types)}"
                        ),
                    )
                ],
            )

        results = self._run_checks(check_names, site)
        decision, prerequisites = self._aggregate(results)

        return DecisionResult(
            site_id=site.site_id,
            site_type=site.site_type,
            decision=decision,
            prerequisites=prerequisites,
            checks=results,
        )

    # ------------------------------------------------------ internals

    def _run_checks(
        self, check_names: list[str], site: SiteData
    ) -> list[CheckResult]:
        """Run checks in order, short-circuiting on a blocking failure."""
        results: list[CheckResult] = []
        blocked_by: str | None = None

        for name in check_names:
            if blocked_by is not None:
                results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.SKIPPED,
                        reason=f"Not evaluated: blocked by failed '{blocked_by}' check",
                    )
                )
                continue

            result = self._run_one(name, site)
            results.append(result)

            if (
                result.status is CheckStatus.FAIL
                and self.rules.config_for(name).severity is Severity.BLOCKING
            ):
                blocked_by = name

        return results

    def _run_one(self, name: str, site: SiteData) -> CheckResult:
        """
        Run a single check, containing any unexpected error.

        A crashing check must not take down the whole evaluation - it
        degrades to NEEDS_REVIEW so a human sees the site.
        """
        try:
            return build_check(name, self.rules.config_for(name)).evaluate(site)
        except Exception:  # noqa: BLE001 - deliberate containment boundary
            logger.exception("Check %r raised on site %s", name, site.site_id)
            return CheckResult(
                name=name,
                status=CheckStatus.NEEDS_REVIEW,
                reason=f"Check {name!r} could not be evaluated; manual review required",
            )

    def _aggregate(self, results: list[CheckResult]) -> tuple[Decision, list[str]]:
        """
        Roll per-check results into one decision.

        Precedence: REJECTED > NEEDS_REVIEW > APPROVED.
        Advisory failures do not change the decision; they surface as
        prerequisites the upgrade is conditional on.
        """
        prerequisites = [
            r.prerequisite
            for r in results
            if r.status is CheckStatus.FAIL and r.prerequisite
        ]

        blocking_failure = any(
            r.status is CheckStatus.FAIL
            and self.rules.config_for(r.name).severity is Severity.BLOCKING
            for r in results
        )
        if blocking_failure:
            return Decision.REJECTED, prerequisites

        if any(r.status is CheckStatus.NEEDS_REVIEW for r in results):
            return Decision.NEEDS_REVIEW, prerequisites

        return Decision.APPROVED, prerequisites


def evaluate_site(site: SiteData, rules: RulesConfig) -> DecisionResult:
    """Convenience wrapper - the single entry point an API would call."""
    return DecisionEngine(rules).evaluate(site)