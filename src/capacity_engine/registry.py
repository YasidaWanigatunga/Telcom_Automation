"""Name -> check class mapping, populated by decorator at import time.

Layering note: this module must not import the `checks` package at
runtime. Checks depend on the registry (they use `@register`), so the
dependency has to point one way only - checks -> registry, never back.
The class reference below is needed for typing alone, so it lives under
TYPE_CHECKING and costs nothing at import time.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .config import CheckConfig

if TYPE_CHECKING:
    from .checks.base import BaseCheck

CHECK_REGISTRY: dict[str, type["BaseCheck"]] = {}


class UnknownCheckError(KeyError):
    """A rules file referenced a check that no class implements."""


def register(cls: type["BaseCheck"]) -> type["BaseCheck"]:
    """Class decorator: make a check discoverable by its `name`."""
    if cls.name in CHECK_REGISTRY:
        raise ValueError(f"Duplicate check name registered: {cls.name!r}")
    CHECK_REGISTRY[cls.name] = cls
    return cls


def build_check(name: str, config: CheckConfig) -> "BaseCheck":
    """Instantiate the check registered under `name`."""
    try:
        cls = CHECK_REGISTRY[name]
    except KeyError as exc:
        raise UnknownCheckError(
            f"No implementation registered for check {name!r}. "
            f"Available: {sorted(CHECK_REGISTRY)}"
        ) from exc
    return cls(config)