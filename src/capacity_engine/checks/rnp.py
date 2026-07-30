"""Radio Network Planning check: is an upgrade justified and possible?"""
from __future__ import annotations

from ..models import CheckResult, SiteData
from ..registry import register
from .base import BaseCheck


@register
class RnpCheck(BaseCheck):
    name = "rnp"

    def evaluate(self, site: SiteData) -> CheckResult:
        missing = self._missing(site, "current_load_pct", "spectrum_available")
        if missing:
            return missing

        # Spectrum is a hard gate: without it, extra capacity is impossible.
        if self.config.param("require_spectrum", True) and not site.spectrum_available:
            return self._failed("No spectrum available at this site")

        threshold = float(self.config.param("min_load_pct", 80))
        band = float(self.config.param("borderline_band_pct", 0))
        load = float(site.current_load_pct)

        if load >= threshold:
            return self._passed(
                f"Load {load:.1f}% meets the {threshold:.1f}% upgrade threshold"
            )
        if load >= threshold - band:
            return self._review(
                f"Load {load:.1f}% is within {band:.1f}% of the "
                f"{threshold:.1f}% threshold - borderline"
            )
        return self._failed(
            f"Load {load:.1f}% does not justify an upgrade "
            f"(threshold {threshold:.1f}%)"
        )