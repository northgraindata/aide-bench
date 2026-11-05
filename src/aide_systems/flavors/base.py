"""Base class for system flavors.

A flavor emulates the surface of one product (Airflow, DuckDB, MinIO...) for one kind of
system (orchestrator, warehouse...) over a frozen snapshot. Authors describe the snapshot
declaratively in a scenario file, `build` freezes it into the world directory and `tools`
exposes read (and optionally mutating) operations to the agent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable


class Flavor:
    kind: str = ""
    name: str = ""
    #: How faithfully the product is emulated: "engine" (real engine), "transpiled"
    #: (dialect translated onto an engine) or "recorded" (frozen responses).
    fidelity: str = "recorded"

    def __init__(self, world: Path, spec: dict) -> None:
        self.world = world
        self.spec = spec
        self.dir = world / self.name

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        raise NotImplementedError

    def tools(self) -> dict[str, Callable]:
        raise NotImplementedError

    def mutating_tools(self) -> set[str]:
        return set()


def read_text_ref(scenario: Path, value: str | None, file: str | None) -> str:
    """Resolve text that is given inline or as a file next to the scenario."""
    if file:
        return (scenario / file).read_text()
    return value or ""
