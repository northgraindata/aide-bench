"""Flavor registry with entry-point discovery for out-of-tree flavors."""
from __future__ import annotations

from importlib.metadata import entry_points

from .base import Flavor

_FLAVORS: dict[tuple[str, str], type[Flavor]] = {}
_LOADED = False


def register(cls: type[Flavor]) -> type[Flavor]:
    _FLAVORS[(cls.kind, cls.name)] = cls
    return cls


def _load() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    from . import docs, dbt, fixture, iceberg, airflow, dagster, duckdb, repo, s3  # noqa: F401

    for entry in entry_points(group="aide_bench.flavors"):
        entry.load()


def get(kind: str, name: str) -> type[Flavor]:
    _load()
    try:
        return _FLAVORS[(kind, name)]
    except KeyError:
        known = ", ".join(f"{k}/{n}" for k, n in sorted(_FLAVORS))
        raise KeyError(f"Unknown flavor {kind}/{name}. Known: {known}") from None


def all_flavors() -> dict[tuple[str, str], type[Flavor]]:
    _load()
    return dict(_FLAVORS)
