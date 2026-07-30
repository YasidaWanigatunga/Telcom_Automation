"""Base class and shared helpers for all checks."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..config import CheckConfig
from ..models import CheckResult, CheckStatus, SiteData, Severity


class BaseCheck(ABC):
    """
    One unit of decision logic.

    A check knows how to evaluate itself and nothing else. It does not
    know about other checks, ordering, or how the final decision is
    aggregated - that is the engine's job.
    """

    name: str = "unnamed"

    def __init__(self, config: CheckConfig) -> None:
        self.config = config

    # ------------------------------------------------------ contract

    @abstractmethod
    def evaluate(self, site: SiteData) -> CheckResult:
        """Evaluate this check against a site. Must never raise."""

    @property
    def severity(self) -> Severity:
        return self.config.severity

    # ------------------------------------------------------ helpers

    def _passed(self, reason: str) -> CheckResult:
        return CheckResult(name=self.name, status=CheckStatus.PASS, reason=reason)

    def _failed(self, reason: str) -> CheckResult:
        """A FAIL carries the configured prerequisite, if the rules define one."""
        return CheckResult(
            name=self.name,
            status=CheckStatus.FAIL,
            reason=reason,
            prerequisite=self.config.on_fail_prerequisite,
        )

    def _review(self, reason: str) -> CheckResult:
        return CheckResult(
            name=self.name, status=CheckStatus.NEEDS_REVIEW, reason=reason
        )

    def _missing(self, site: SiteData, *fields: str) -> Optional[CheckResult]:
        """
        Guard for absent input. Returns a NEEDS_REVIEW result if any
        required field is None, otherwise None (meaning: carry on).
        """
        absent = [f for f in fields if getattr(site, f, None) is None]
        if absent:
            return self._review(f"Missing input data: {', '.join(absent)}")
        return None