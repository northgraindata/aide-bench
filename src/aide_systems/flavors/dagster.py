"""orchestrator/dagster: Dagster-style surface (jobs, runs, steps) over the same recorded model."""
from __future__ import annotations

from .orchestrator import Orchestrator
from .registry import register


@register
class Dagster(Orchestrator):
    name = "dagster"

    def mutating_tools(self) -> set[str]:
        return {"dagster_reexecute_step"} if self._state()["actions"] else set()

    def tools(self):
        def dagster_list_jobs() -> dict:
            """List jobs with their schedules."""
            return {"jobs": [{"job_name": d["dag_id"], **{k: v for k, v in d.items() if k not in ("dag_id", "runs")}} for d in self._list_dags()["dags"]]}

        def dagster_list_runs(job_name: str, limit: int = 10) -> dict:
            """List recent runs of a job, newest first."""
            return self._list_runs(job_name, limit)

        def dagster_get_run_steps(job_name: str, run_id: str) -> dict:
            """List the steps of a run with their status and attempts."""
            return self._task_instances(job_name, run_id)

        def dagster_get_step_logs(job_name: str, run_id: str, step_key: str, attempt: int = 1, max_chars: int = 20000) -> dict:
            """Read the event log of one step attempt."""
            return self._task_log(job_name, run_id, step_key, attempt, max_chars)

        tools = {f.__name__: f for f in (dagster_list_jobs, dagster_list_runs, dagster_get_run_steps, dagster_get_step_logs)}
        if self._state()["actions"]:

            def dagster_reexecute_step(job_name: str, run_id: str, step_key: str) -> dict:
                """Re-execute a step. This changes the live system."""
                return self._clear(job_name, run_id, step_key)

            tools["dagster_reexecute_step"] = dagster_reexecute_step
        return tools
