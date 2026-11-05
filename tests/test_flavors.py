import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from aide_systems.build import build_world
from aide_systems.session import Session


@pytest.fixture()
def session(tmp_path, monkeypatch):
    scenario = tmp_path / "scenario"
    (scenario / "repo").mkdir(parents=True)
    (scenario / "repo" / "a.txt").write_text("hello\n")
    (scenario / "bucket").mkdir()
    (scenario / "bucket" / "k.txt").write_text("data")
    (scenario / "scenario.yaml").write_text(
        yaml.safe_dump(
            {
                "systems": [
                    {"kind": "warehouse", "flavor": "duckdb", "sql": ["create table t(a integer)", "insert into t values (1)"]},
                    {"kind": "repo", "flavor": "git", "files": "repo", "writable": True, "history": []},
                    {"kind": "object_storage", "flavor": "s3-minio", "buckets": {"b": "bucket"}, "denied": ["b/secret"]},
                ]
            }
        )
    )
    monkeypatch.setenv("AIDE_WORLD_DIR", str(tmp_path / "world"))
    monkeypatch.setenv("AIDE_OUT_DIR", str(tmp_path / "out"))
    build_world(scenario, tmp_path / "world")
    return Session()


def test_warehouse_is_read_only(session):
    assert "error" in session.call("warehouse_query", {"sql": "drop table t"})
    assert session.call("warehouse_query", {"sql": "select a from t"})["rows"] == [[1]]


def test_repo_blocks_path_traversal(session):
    assert "error" in session.call("repo_read_file", {"path": "../scenario.yaml"})
    assert session.call("repo_read_file", {"path": "a.txt"})["content"] == "hello\n"


def test_storage_denied_prefix(session):
    assert "AccessDenied" in session.call("s3_get_object", {"bucket": "b", "key": "secret/x"})["error"]
    assert session.call("s3_get_object", {"bucket": "b", "key": "k.txt"})["content"] == "data"


def test_every_call_is_traced(session):
    result = session.call("repo_read_file", {"path": "a.txt"})
    trace = [json.loads(line) for line in session.trace_path.read_text().splitlines()]
    assert trace[-1]["trace_id"] == result["trace_id"] and trace[-1]["tool"] == "repo_read_file"


def test_unknown_tool_and_bad_arguments_are_errors_not_crashes(session):
    assert "error" in session.call("nope", {})
    assert "error" in session.call("repo_read_file", {"wrong": 1})


def test_propose_patch_validates_and_records(session):
    bad = session.call("propose_patch", {"diff": "not a patch"})
    assert bad["applies"] is False
    good = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-hello\n+bye\n"
    assert session.call("propose_patch", {"diff": good})["applies"] is True
    assert (session.out / "patch.diff").read_text() == good


def test_submit_answer_is_validated(session):
    base = dict(categories=["data-loss"], root_cause="x", affected=[], verdict="supported", confidence=0.5, evidence=[])
    assert "ok" in session.submit_answer(**base)
    assert "error" in session.submit_answer(**{**base, "categories": ["made-up"]})
    assert "error" in session.submit_answer(**{**base, "verdict": "maybe"})
    assert "error" in session.submit_answer(**{**base, "confidence": 2})


def test_scenario_rejects_duplicate_flavors(tmp_path):
    (tmp_path / "scenario.yaml").write_text(
        yaml.safe_dump({"systems": [{"kind": "warehouse", "flavor": "duckdb"}, {"kind": "warehouse", "flavor": "duckdb"}]})
    )
    with pytest.raises(Exception):
        build_world(tmp_path, tmp_path / "w")


def test_catalog_and_repo_export_do_not_touch_the_trace(session):
    from aide_systems import call

    names = {tool["name"] for tool in call.catalog()}
    assert {"warehouse_query", "repo_read_file", "propose_patch", "s3_get_object"} <= names
    assert next(t for t in call.catalog() if t["name"] == "warehouse_query")["inputSchema"]["properties"]["sql"]
    assert call.repo_files() == {"a.txt": "hello\n"}
    assert not session.trace_path.exists() or session.trace_path.read_text() == ""
