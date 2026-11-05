"""Every shipped task must lint clean and respect the oracle-passes, nop-fails gate."""
import pytest

from aide_cli.checks import lint, offline_problems

from .conftest import TASKS


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_task_is_valid(task):
    assert lint(task) == []
    assert offline_problems(task) == []


def test_task_ids_are_unique():
    ids = [t.id for t in TASKS]
    assert len(ids) == len(set(ids))
