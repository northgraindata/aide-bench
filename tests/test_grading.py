"""Adversarial answers: they look plausible but must not earn the reward."""
import copy

from aide_cli.checks import trial

from .conftest import solution_of


def with_answer(task, **changes):
    solution = copy.deepcopy(solution_of(task))
    solution["answer"].update(changes)
    return solution


def test_correct_answer_passes(diagnose_task):
    assert trial(diagnose_task, solution_of(diagnose_task))["reward"] == 1.0


def test_wrong_category_fails(diagnose_task):
    wrong = "infrastructure" if "infrastructure" not in solution_of(diagnose_task)["answer"]["categories"] else "schema-drift"
    reward = trial(diagnose_task, with_answer(diagnose_task, categories=[wrong]))
    assert reward["reward"] == 0.0


def test_answer_without_evidence_fails(diagnose_task):
    reward = trial(diagnose_task, with_answer(diagnose_task, evidence=[]))
    assert reward["grounded"] == 0.0 and reward["reward"] == 0.0


def test_citing_a_trace_id_that_does_not_exist_fails(diagnose_task):
    solution = copy.deepcopy(solution_of(diagnose_task))
    solution["calls"].append({"id": "fake", "tool": "no_such_tool", "args": {}})  # no trace id comes back
    solution["answer"]["evidence"] = solution["answer"]["evidence"] + ["fake"]
    reward = trial(diagnose_task, solution)
    assert reward["grounded"] == 0.0 and reward["reward"] == 0.0


def test_citing_only_unrelated_calls_fails_evidence_recall(diagnose_task):
    if not _truth(diagnose_task).required_evidence:
        return
    listing = "docs_list" if "docs/markdown" in diagnose_task.flavors else "repo_list_files"
    solution = copy.deepcopy(solution_of(diagnose_task))
    solution["calls"] = [{"id": "unrelated", "tool": listing}]
    solution["answer"]["evidence"] = ["unrelated"]
    reward = trial(diagnose_task, solution)
    assert reward["evidence_recall"] < 1.0
    assert reward["reward"] == 0.0


def _truth(task):
    from aide_grade.schema import load_ground_truth

    return load_ground_truth(task.tests_dir / "ground_truth.yaml")


def test_wrong_verdict_fails(diagnose_task):
    truth = _truth(diagnose_task)
    flipped = "inconclusive" if truth.verdict == "supported" else "supported"
    assert trial(diagnose_task, with_answer(diagnose_task, verdict=flipped))["reward"] == 0.0


def test_do_nothing_scores_zero(diagnose_task):
    assert trial(diagnose_task, None)["reward"] == 0.0
