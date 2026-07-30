"""Name -> check class mapping, populated by decorator at import time."""
from __future__ import annotations

from .checks.base import BaseCheck
from .config import CheckConfig

CHECK_REGISTRY: dict[str, type[BaseCheck]] = {}


class UnknownCheckError(KeyError):
    """A rules file referenced a check that no class implements."""


def register(cls: type[BaseCheck]) -> type[BaseCheck]:
    """Class decorator: make a check discoverable by its `name`."""
    if cls.name in CHECK_REGISTRY:
        raise ValueError(f"Duplicate check name registered: {cls.name!r}")
    CHECK_REGISTRY[cls.name] = cls
    return cls


def build_check(name: str, config: CheckConfig) -> BaseCheck:
    """Instantiate the check registered under `name`."""
    try:
        cls = CHECK_REGISTRY[name]
    except KeyError as exc:
        raise UnknownCheckError(
            f"No implementation registered for check {name!r}. "
            f"Available: {sorted(CHECK_REGISTRY)}"
        ) from exc
    return cls(config)