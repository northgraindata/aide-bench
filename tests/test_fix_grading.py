import copy

from aide_cli.checks import trial
from aide_cli.tasks import discover

from .conftest import ROOT, solution_of

TASKS = {t.id: t for t in discover(ROOT) if t.metadata["track"] == "fix"}


def with_patch(task, diff: str):
    solution = copy.deepcopy(solution_of(task))
    path = task.path / "solution" / "_attempt.patch"
    path.write_text(diff)
    solution["patch_file"] = "_attempt.patch"
    return solution, path


def attempt(task, diff):
    solution, path = with_patch(task, diff)
    try:
        return trial(task, solution)
    finally:
        path.unlink(missing_ok=True)


def test_reference_patch_passes():
    for task in TASKS.values():
        assert trial(task, solution_of(task))["reward"] == 1.0


def test_patch_that_does_not_fix_fails_hidden_tests():
    task = TASKS["fix-null-currency-filter"]
    diff = """diff --git a/models/marts/daily_revenue.sql b/models/marts/daily_revenue.sql
--- a/models/marts/daily_revenue.sql
+++ b/models/marts/daily_revenue.sql
@@ -1,3 +1,3 @@
 select order_date, count(*) as orders, sum(amount) as revenue
 from stg_orders
-group by 1
+group by order_date
"""
    reward = attempt(task, diff)
    assert reward["patch_applies"] == 1.0 and reward["tests_pass"] == 0.0 and reward["reward"] == 0.0


def test_patch_outside_allowed_paths_fails():
    task = TASKS["fix-null-currency-filter"]
    diff = """diff --git a/data/raw_orders.csv b/data/raw_orders.csv
--- a/data/raw_orders.csv
+++ b/data/raw_orders.csv
@@ -1,2 +1,2 @@
-order_id,order_date,currency,amount
+order_id,order_date,currency,amount
 1,2026-10-30,USD,100.0
"""
    assert attempt(task, diff)["paths_ok"] == 0.0


def test_no_patch_scores_zero():
    for task in TASKS.values():
        assert trial(task, None)["reward"] == 0.0
