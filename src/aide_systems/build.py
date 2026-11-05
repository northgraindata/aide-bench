"""Freeze a scenario into a world.

    aide-build <scenario-dir> [--world /app/world]

The scenario directory holds `scenario.yaml` plus any files it references. The world is what
the agent's tools read at run time; the scenario itself is deleted from the image after the
build so that authoring files never sit next to the agent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from .flavors import get

RUNTIME_KEYS = {"writable", "actions"}


class System(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: str
    flavor: str


class Scenario(BaseModel):
    systems: list[System]

    @field_validator("systems")
    @classmethod
    def _unique(cls, systems: list[System]) -> list[System]:
        names = [s.flavor for s in systems]
        if len(names) != len(set(names)):
            raise ValueError("each flavor may appear once per scenario")
        return systems


def load_scenario(path: Path) -> Scenario:
    return Scenario.model_validate(yaml.safe_load((path / "scenario.yaml").read_text()))


def build_world(scenario_dir: Path, world: Path) -> None:
    scenario = load_scenario(scenario_dir)
    world.mkdir(parents=True, exist_ok=True)
    manifest = []
    for system in scenario.systems:
        spec = system.model_dump()
        get(system.kind, system.flavor).build(spec, scenario_dir, world)
        manifest.append(
            {"kind": system.kind, "flavor": system.flavor, "spec": {k: v for k, v in spec.items() if k in RUNTIME_KEYS}}
        )
    (world / "world.json").write_text(json.dumps({"systems": manifest}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="aide-build")
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--world", type=Path, default=Path("/app/world"))
    args = parser.parse_args()
    build_world(args.scenario, args.world)


if __name__ == "__main__":
    main()
