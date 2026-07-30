"""Civil works check: is there physical space for new cabinets?

The brief mentions this check but the sample payload has no field for
it. See README > Assumptions for the field introduced here.
"""
from __future__ import annotations

from ..models import CheckResult, SiteData
from ..registry import register
from .base import BaseCheck


@register
class CivilWorksCheck(BaseCheck):
    name = "civil_works"

    def evaluate(self, site: SiteData) -> CheckResult:
        missing = self._missing(site, "floor_space_available")
        if missing:
            return missing

        if site.floor_space_available:
            return self._passed("Floor space is available for new cabinets")
        return self._failed("No floor space available for new cabinets")