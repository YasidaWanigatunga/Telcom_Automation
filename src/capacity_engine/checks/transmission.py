"""Transmission check: can the backhaul carry the upgraded capacity?"""
from __future__ import annotations

from ..models import CheckResult, SiteData
from ..registry import register
from .base import BaseCheck


@register
class TransmissionCheck(BaseCheck):
    name = "transmission"

    def evaluate(self, site: SiteData) -> CheckResult:
        missing = self._missing(
            site, "backhaul_capacity_mbps", "backhaul_required_mbps"
        )
        if missing:
            return missing

        spare_pct = float(self.config.param("spare_capacity_pct", 0))
        band_pct = float(self.config.param("borderline_band_pct", 0))

        capacity = float(site.backhaul_capacity_mbps)
        required = float(site.backhaul_required_mbps)
        target = required * (1 + spare_pct / 100)   # required + headroom

        if capacity >= target:
            return self._passed(
                f"Backhaul {capacity:.0f} Mbps covers {required:.0f} Mbps "
                f"plus {spare_pct:.0f}% spare (target {target:.0f} Mbps)"
            )
        if capacity >= target * (1 - band_pct / 100):
            return self._review(
                f"Backhaul {capacity:.0f} Mbps is marginally short of the "
                f"{target:.0f} Mbps target - borderline"
            )
        return self._failed(
            f"Backhaul {capacity:.0f} Mbps is below the {target:.0f} Mbps "
            f"target ({required:.0f} Mbps + {spare_pct:.0f}% spare)"
        )