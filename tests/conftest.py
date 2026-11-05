from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from aide_cli.tasks import Task, discover

ROOT = Path(__file__).resolve().parents[1]
TASKS = discover(ROOT)


def solution_of(task: Task) -> dict:
    return yaml.safe_load((task.path / "solution" / "solution.yaml").read_text())


@pytest.fixture(params=[t for t in TASKS if t.metadata["track"] == "diagnose"], ids=lambda t: t.id)
def diagnose_task(request) -> Task:
    return request.param
