"""Loading and validation of the operator rules file."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import Severity


class ConfigError(Exception):
    """Raised when the rules file is missing, malformed, or inconsistent."""


class CheckConfig(BaseModel):
    """Configuration for a single check."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    severity: Severity = Severity.BLOCKING
    on_fail_prerequisite: Optional[str] = None

    def param(self, key: str, default: Any = None) -> Any:
        """Read a check-specific tuning parameter."""
        if key in (self.model_extra or {}):
            return self.model_extra[key]
        return getattr(self, key, default)


class RulesConfig(BaseModel):
    """The whole rules file, validated."""
    version: int = 1
    operator: str = "unknown"
    site_types: dict[str, list[str]] = Field(default_factory=dict)
    checks: dict[str, CheckConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_references(self) -> "RulesConfig":
        """Fail fast: every check named in site_types must be declared."""
        declared = set(self.checks)
        for site_type, names in self.site_types.items():
            unknown = [n for n in names if n not in declared]
            if unknown:
                raise ValueError(
                    f"site_type '{site_type}' references undeclared "
                    f"check(s): {unknown}"
                )
            if len(set(names)) != len(names):
                raise ValueError(
                    f"site_type '{site_type}' lists a check more than once"
                )
        return self

    def checks_for(self, site_type: str) -> Optional[list[str]]:
        """Ordered check names for a site type, or None if unrecognised."""
        return self.site_types.get(site_type.strip().lower())

    def config_for(self, check_name: str) -> CheckConfig:
        return self.checks[check_name]


def load_rules(path: str | Path) -> RulesConfig:
    """Load, merge defaults into, and validate the rules file."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Rules file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Rules file must be a mapping: {path}")

    defaults = raw.pop("defaults", None) or {}
    raw["checks"] = {
        name: {**defaults, **(cfg or {})}
        for name, cfg in (raw.get("checks") or {}).items()
    }

    raw["site_types"] = {
        str(k).strip().lower(): v
        for k, v in (raw.get("site_types") or {}).items()
    }

    try:
        return RulesConfig(**raw)
    except Exception as exc:
        raise ConfigError(f"Invalid rules file {path}: {exc}") from exc