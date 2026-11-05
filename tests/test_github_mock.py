"""Drive the mock the way DSUI's publishGitHub does, then grade the resulting patch."""
import json
import urllib.request
from pathlib import Path

import pytest

from aide_cli.tasks import discover
from aide_grade.fix import grade_fix
from aide_grade.schema import load_ground_truth
from aide_systems.github_mock import GithubMock, load_repo

from .conftest import ROOT

TASK = next(t for t in discover(ROOT) if t.id == "fix-null-currency-filter")


def call(base, method, path, token="t", body=None):
    request = urllib.request.Request(
        base + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"{}")


@pytest.fixture()
def mock(tmp_path):
    server = GithubMock(load_repo("acme", "retail", TASK.scenario_dir / "repo"), tmp_path / "patch.diff")
    url = server.start()
    yield server, url, tmp_path / "patch.diff"
    server.stop()


def open_pr(url, repo, path, new_content):
    root = f"/repos/acme/retail"
    ref = call(url, "GET", f"{root}/git/ref/heads/main")
    tree = call(url, "GET", f"{root}/git/trees/{ref['object']['sha']}?recursive=1")
    assert tree["truncated"] is False
    blob = call(url, "POST", f"{root}/git/blobs", body={"content": new_content, "encoding": "utf-8"})
    next_tree = call(url, "POST", f"{root}/git/trees", body={"base_tree": ref["object"]["sha"], "tree": [{"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}]})
    commit = call(url, "POST", f"{root}/git/commits", body={"message": "fix", "tree": next_tree["sha"], "parents": [ref["object"]["sha"]]})
    call(url, "POST", f"{root}/git/refs", body={"ref": "refs/heads/dsui/fix", "sha": commit["sha"]})
    assert call(url, "GET", f"{root}/pulls?state=open&head=acme:dsui/fix") == []
    return call(url, "POST", f"{root}/pulls", body={"title": "Fix", "body": "", "draft": True, "head": "dsui/fix", "base": "main"})


def test_requires_authentication(mock):
    _, url, _ = mock
    with pytest.raises(urllib.error.HTTPError) as error:
        call(url, "GET", "/repos/acme/retail", token=None)
    assert error.value.code == 401


def test_pull_request_becomes_a_patch_that_passes_the_hidden_tests(mock):
    _, url, patch = mock
    pr = open_pr(url, None, "models/staging/stg_orders.sql", "select order_id, order_date, currency, amount\nfrom raw_orders\n")
    assert pr["draft"] is True and pr["html_url"].endswith("/pull/1")
    diff = patch.read_text()
    assert "-where currency is not null" in diff
    reward = grade_fix(load_ground_truth(TASK.tests_dir / "ground_truth.yaml"), diff, TASK.tests_dir, [])
    assert reward["reward"] == 1.0, reward


def test_unrelated_change_is_graded_as_failing(mock):
    _, url, patch = mock
    open_pr(url, None, "models/marts/daily_revenue.sql", "select 1 as order_date, 0 as orders, 0 as revenue\n")
    reward = grade_fix(load_ground_truth(TASK.tests_dir / "ground_truth.yaml"), patch.read_text(), TASK.tests_dir, [])
    assert reward["patch_applies"] == 1.0 and reward["reward"] == 0.0
