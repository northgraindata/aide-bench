"""Flavors added for the legacy and cloud suites: spark, yarn, cron, prefect, cloud warehouses, delta."""
import yaml
import pytest

from aide_systems.build import build_world
from aide_systems.session import Session


def make_session(tmp_path, monkeypatch, systems, files=None):
    scenario = tmp_path / "scenario"
    scenario.mkdir()
    for name, text in (files or {}).items():
        (scenario / name).write_text(text)
    (scenario / "scenario.yaml").write_text(yaml.safe_dump({"systems": systems}))
    monkeypatch.setenv("AIDE_WORLD_DIR", str(tmp_path / "world"))
    monkeypatch.setenv("AIDE_OUT_DIR", str(tmp_path / "out"))
    build_world(scenario, tmp_path / "world")
    return Session()


def test_spark_exposes_stages_conf_and_logs(tmp_path, monkeypatch):
    app = {
        "app_id": "application_1_0001", "name": "nightly", "state": "FAILED", "conf": {"spark.sql.shuffle.partitions": "200"},
        "failure_reason": "Job aborted", "driver_log": "driver says boom",
        "stages": [{"stage_id": 3, "name": "join", "status": "FAILED", "num_tasks": 200, "failed_tasks": 1, "task_duration_s": {"median": 20, "max": 2400}}],
        "executors": [{"id": 7, "host": "w1", "status": "dead", "log": "java.lang.OutOfMemoryError: Java heap space"}],
    }
    session = make_session(tmp_path, monkeypatch, [{"kind": "compute", "flavor": "spark", "applications": [app]}])
    assert session.call("spark_get_application", {"app_id": "application_1_0001"})["conf"]["spark.sql.shuffle.partitions"] == "200"
    assert session.call("spark_get_stage", {"app_id": "application_1_0001", "stage_id": 3})["task_duration_s"]["max"] == 2400
    assert "OutOfMemoryError" in session.call("spark_get_executor_log", {"app_id": "application_1_0001", "executor_id": "7"})["content"]
    assert "error" in session.call("spark_get_stage", {"app_id": "application_1_0001", "stage_id": 99})


def test_yarn_nodes_and_container_logs(tmp_path, monkeypatch):
    spec = {
        "kind": "compute", "flavor": "yarn",
        "nodes": [{"host": "w7", "state": "UNHEALTHY", "disk_used_pct": 100}],
        "applications": [{"app_id": "application_9_1", "name": "job", "state": "FAILED", "containers": [{"container_id": "c1", "node": "w7", "exit_code": 1, "log": "No space left on device"}]}],
    }
    session = make_session(tmp_path, monkeypatch, [spec])
    assert session.call("yarn_list_nodes", {})["nodes"][0]["disk_used_pct"] == 100
    assert "No space" in session.call("yarn_get_container_log", {"app_id": "application_9_1", "container_id": "c1"})["content"]
    assert "log" not in session.call("yarn_get_application", {"app_id": "application_9_1"})["containers"][0]


def test_cron_runs_output_syslog_and_environment(tmp_path, monkeypatch):
    spec = {
        "kind": "orchestrator", "flavor": "cron",
        "jobs": [{"job_id": "nightly", "schedule": "30 2 * * *", "command": "/opt/run.sh", "runs": [{"run_id": "2026-10-30", "exit_code": 0, "output": "psql: command not found"}]}],
        "syslog": "Oct 30 02:30:01 host CRON[1]: (root) CMD (/opt/run.sh)\nOct 30 02:31:00 host other: noise",
        "environment": {"default": {"PATH": "/usr/bin:/bin"}},
    }
    session = make_session(tmp_path, monkeypatch, [spec])
    assert session.call("cron_list_jobs", {})["jobs"][0]["schedule"] == "30 2 * * *"
    out = session.call("cron_get_run_output", {"job_id": "nightly", "run_id": "2026-10-30"})
    assert "exit_code=0" in out["content"] and "command not found" in out["content"]
    assert "CMD" in session.call("cron_read_syslog", {"pattern": "cmd"})["content"]
    assert session.call("cron_get_environment", {})["environment"]["PATH"] == "/usr/bin:/bin"


def test_prefect_reads_task_run_logs_and_offers_retry_only_with_actions(tmp_path, monkeypatch):
    dag = {"dag_id": "etl", "runs": [{"run_id": "r1", "state": "Completed", "tasks": [{"task_id": "load", "tries": [{"state": "Cached", "log": "Finished in state Cached"}]}]}]}
    session = make_session(tmp_path, monkeypatch, [{"kind": "orchestrator", "flavor": "prefect", "dags": [dag]}])
    assert "Cached" in session.call("prefect_get_task_run_logs", {"flow_name": "etl", "flow_run_id": "r1", "task_run": "load"})["content"]
    assert "error" in session.call("prefect_retry_flow_run", {"flow_name": "etl", "flow_run_id": "r1"})


@pytest.mark.parametrize(
    "flavor,query,history_tool,columns_tool",
    [
        ("snowflake", "select iff(amount > 5, 'big', 'small') as size, count(*) as n from orders group by 1 order by 1", "snowflake_query_history", "snowflake_describe_table"),
        ("bigquery", "select if(amount > 5, 'big', 'small') as size, count(*) as n from orders group by 1 order by 1", "bigquery_list_jobs", "bigquery_describe_table"),
        ("databricks-sql", "select if(amount > 5, 'big', 'small') as size, count(*) as n from orders group by 1 order by 1", "databricks_sql_query_history", "databricks_sql_describe_table"),
    ],
)
def test_cloud_warehouses_translate_dialect_and_serve_history(tmp_path, monkeypatch, flavor, query, history_tool, columns_tool):
    spec = {
        "kind": "warehouse", "flavor": flavor,
        "sql": ["create table orders as select * from (values (1, 3), (2, 9)) t(id, amount)"],
        "query_history": [{"query_id": "q1", "status": "FAILED", "error": "Insufficient privileges"}, {"query_id": "q2", "status": "SUCCESS"}],
    }
    session = make_session(tmp_path, monkeypatch, [spec])
    tool = {"snowflake": "snowflake_query", "bigquery": "bigquery_query", "databricks-sql": "databricks_sql_query"}[flavor]
    assert session.call(tool, {"sql": query})["rows"] == [["big", 1], ["small", 1]]
    assert "error" in session.call(tool, {"sql": "drop table orders"})
    assert [q["query_id"] for q in session.call(history_tool, {"status": "failed"})["queries"]] == ["q1"]
    assert session.call(columns_tool, {"table": "ORDERS"})["columns"][0]["name"] == "id"


def test_delta_history_is_newest_first(tmp_path, monkeypatch):
    tables = {"sales": {"history": [{"version": 1, "operation": "MERGE"}, {"version": 2, "operation": "WRITE"}], "commits": {"2": "remove part-0"}}}
    session = make_session(tmp_path, monkeypatch, [{"kind": "lakehouse", "flavor": "delta", "tables": tables}])
    assert [h["version"] for h in session.call("delta_describe_history", {"table": "sales"})["history"]] == [2, 1]
    assert "remove" in session.call("delta_read_commit", {"table": "sales", "version": 2})["content"]
    assert "error" in session.call("delta_describe_history", {"table": "nope"})
