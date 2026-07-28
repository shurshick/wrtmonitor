from typing import Any

from .command_catalog import DOMAIN_CATALOGS
from .command_reliability import apply_reliability_contract


def build_command_registry() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for catalog in DOMAIN_CATALOGS:
        overlap = set(registry) & set(catalog)
        if overlap:
            raise RuntimeError(f"duplicate command definitions: {sorted(overlap)}")
        registry.update(catalog)
    return apply_reliability_contract(registry)


COMMAND_REGISTRY = build_command_registry()
