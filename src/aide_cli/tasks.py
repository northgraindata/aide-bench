"""Find and inspect tasks on disk."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml


def find_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "datasets").is_dir() and (candidate / "pyproject.toml").exists():
            return candidate
    raise SystemExit("Run aide from inside the aide-bench repository.")


@dataclass
class Task:
    path: Path

    @property
    def id(self) -> str:
        return self.path.name

    @property
    def dataset(self) -> str:
        return self.path.parent.name

    @property
    def toml(self) -> dict:
        return tomllib.loads((self.path / "task.toml").read_text())

    @property
    def metadata(self) -> dict:
        return self.toml.get("metadata", {})

    @property
    def scenario_dir(self) -> Path:
        return self.path / "environment" / "scenario"

    @property
    def tests_dir(self) -> Path:
        return self.path / "tests"

    @property
    def flavors(self) -> list[str]:
        scenario = yaml.safe_load((self.scenario_dir / "scenario.yaml").read_text())
        return [f"{s['kind']}/{s['flavor']}" for s in scenario["systems"]]


def discover(root: Path, selector: str | None = None) -> list[Task]:
    """All tasks, or those matching a task id, a dataset name or a path."""
    tasks = [Task(p.parent) for p in sorted(root.glob("datasets/*/*/task.toml"))]
    if not selector:
        return tasks
    path = Path(selector)
    if path.exists():
        resolved = path.resolve()
        return [t for t in tasks if t.path == resolved or resolved in t.path.parents]
    return [t for t in tasks if selector in (t.id, t.dataset)]
