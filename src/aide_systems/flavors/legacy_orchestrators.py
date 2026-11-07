"""orchestrator/cron and orchestrator/prefect over the shared orchestrator model."""
from __future__ import annotations

import json
from pathlib import Path

from .base import read_text_ref
from .orchestrator import Orchestrator
from .registry import register
from .util import clip


@register
class Cron(Orchestrator):
    """A host crontab: each job is a line, each run has its captured output and an exit code."""

    name = "cron"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        # A cron run has a single "task": the command. Reuse the DAG model with task_id "run".
        dags = []
        for job in spec.get("jobs", []):
            runs = []
            for run in job.get("runs", []):
                log = read_text_ref(scenario, run.get("output"), run.get("output_file"))
                exit_code = run.get("exit_code", 0)
                header = f"exit_code={exit_code}\n"
                state = "success" if exit_code == 0 else "failed"
                runs.append(
                    {
                        "run_id": run["run_id"],
                        "state": run.get("state", state),
                        "started": run.get("started"),
                        "exit_code": exit_code,
                        "tasks": [{"task_id": "run", "tries": [{"try_number": 1, "state": state, "log": header + log}]}],
                    }
                )
            dags.append({"dag_id": job["job_id"], "schedule": job["schedule"], "command": job["command"], "user": job.get("user", "root"), "runs": runs})
        spec = {**spec, "dags": dags}
        super().build(spec, scenario, world)
        target = world / cls.name
        (target / "syslog.txt").write_text(read_text_ref(scenario, spec.get("syslog"), spec.get("syslog_file")))
        (target / "env.json").write_text(json.dumps(spec.get("environment", {}), indent=2))

    def tools(self):
        def cron_list_jobs() -> dict:
            """List crontab entries: job id, schedule, command and user."""
            return {"jobs": [{"job_id": d["dag_id"], **{k: v for k, v in d.items() if k not in ("dag_id", "runs")}} for d in self._state()["dags"]]}

        def cron_list_runs(job_id: str, limit: int = 10) -> dict:
            """List recent runs of a job, newest first, with exit code."""
            return self._list_runs(job_id, limit)

        def cron_get_run_output(job_id: str, run_id: str, max_chars: int = 20000) -> dict:
            """Read the captured stdout and stderr of one run (the exit code is on the first line)."""
            return self._task_log(job_id, run_id, "run", 1, max_chars)

        def cron_read_syslog(pattern: str = "", max_chars: int = 20000) -> dict:
            """Read the host syslog lines that contain a text pattern (all lines if empty)."""
            text = (self.dir / "syslog.txt").read_text()
            lines = [line for line in text.splitlines() if pattern.lower() in line.lower()]
            return clip("\n".join(lines), max_chars)

        def cron_get_environment(user: str = "root") -> dict:
            """Show the environment variables cron gives to jobs of a user (not the login shell's)."""
            env = json.loads((self.dir / "env.json").read_text())
            return {"user": user, "environment": env.get(user, env.get("default", {}))}

        return {f.__name__: f for f in (cron_list_jobs, cron_list_runs, cron_get_run_output, cron_read_syslog, cron_get_environment)}


@register
class Prefect(Orchestrator):
    """Prefect 2 style flows, flow runs, task runs and task run logs."""

    name = "prefect"

    def mutating_tools(self) -> set[str]:
        return {"prefect_retry_flow_run"} if self._state()["actions"] else set()

    def tools(self):
        def prefect_list_flows() -> dict:
            """List flows with their schedules."""
            return {"flows": [{"name": d["dag_id"], **{k: v for k, v in d.items() if k not in ("dag_id", "runs")}} for d in self._list_dags()["dags"]]}

        def prefect_list_flow_runs(flow_name: str, limit: int = 10) -> dict:
            """List recent runs of a flow, newest first, with state name and parameters."""
            return self._list_runs(flow_name, limit)

        def prefect_get_task_runs(flow_name: str, flow_run_id: str) -> dict:
            """List the task runs of a flow run with their state and retries."""
            return self._task_instances(flow_name, flow_run_id)

        def prefect_get_task_run_logs(flow_name: str, flow_run_id: str, task_run: str, attempt: int = 1, max_chars: int = 20000) -> dict:
            """Read the logs of one task run attempt."""
            return self._task_log(flow_name, flow_run_id, task_run, attempt, max_chars)

        tools = {f.__name__: f for f in (prefect_list_flows, prefect_list_flow_runs, prefect_get_task_runs, prefect_get_task_run_logs)}
        if self._state()["actions"]:

            def prefect_retry_flow_run(flow_name: str, flow_run_id: str) -> dict:
                """Retry a flow run. This changes the live system."""
                return self._clear(flow_name, flow_run_id, "*")

            tools["prefect_retry_flow_run"] = prefect_retry_flow_run
        return tools
