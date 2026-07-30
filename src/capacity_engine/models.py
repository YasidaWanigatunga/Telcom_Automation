from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SKIPPED = "SKIPPED" 


class Decision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Severity(str, Enum):
    """How a FAIL from a check affects the overall process."""
    BLOCKING = "blocking"        
    ADVISORY = "advisory"        


class SiteData(BaseModel):
    model_config = ConfigDict(extra="allow")

    site_id: str
    site_type: str

    # RNP
    current_load_pct: Optional[float] = None
    spectrum_available: Optional[bool] = None

    # Transmission
    backhaul_capacity_mbps: Optional[float] = None
    backhaul_required_mbps: Optional[float] = None

    # Power
    power_headroom_kw: Optional[float] = None
    power_required_kw: Optional[float] = None

    # Civil works (assumed field - see README)
    floor_space_available: Optional[bool] = None


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    reason: str
    prerequisite: Optional[str] = None


class DecisionResult(BaseModel):
    site_id: str
    site_type: str
    decision: Decision
    prerequisites: list[str] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )