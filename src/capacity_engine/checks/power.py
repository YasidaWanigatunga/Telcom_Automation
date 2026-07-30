"""Power check: can the site's supply carry the new equipment?"""
from __future__ import annotations

from ..models import CheckResult, SiteData
from ..registry import register
from .base import BaseCheck


@register
class PowerCheck(BaseCheck):
    name = "power"

    def evaluate(self, site: SiteData) -> CheckResult:
        missing = self._missing(site, "power_headroom_kw", "power_required_kw")
        if missing:
            return missing

        margin = float(self.config.param("safety_margin_kw", 0))
        band = float(self.config.param("borderline_band_kw", 0))

        headroom = float(site.power_headroom_kw)
        required = float(site.power_required_kw)
        target = required + margin

        if headroom >= target:
            return self._passed(
                f"Power headroom {headroom:.2f} kW covers {required:.2f} kW "
                f"plus a {margin:.2f} kW safety margin"
            )
        if headroom >= target - band:
            return self._review(
                f"Power headroom {headroom:.2f} kW is marginally short of the "
                f"{target:.2f} kW target - borderline"
            )
        return self._failed(
            f"Power headroom {headroom:.2f} kW is below the {target:.2f} kW "
            f"target ({required:.2f} kW + {margin:.2f} kW margin)"
        )