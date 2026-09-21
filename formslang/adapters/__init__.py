"""Target adapters package for FormsLang Modernization Intelligence Platform."""

from __future__ import annotations

from ..target_adapter import register_adapter
from .apex import Apex26TargetAdapter
from .generic import GenericModernizationAdapter


def register_builtin_adapters() -> None:
    """Register all built-in target adapters statically."""
    register_adapter(Apex26TargetAdapter())
    register_adapter(GenericModernizationAdapter())


__all__ = [
    "Apex26TargetAdapter",
    "GenericModernizationAdapter",
    "register_builtin_adapters",
]
