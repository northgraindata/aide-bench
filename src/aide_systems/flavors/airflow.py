"""orchestrator/airflow: Apache Airflow REST-style surface over recorded runs and task logs."""
from __future__ import annotations

from .orchestrator import Orchestrator
from .registry import register


@register
class Airflow(Orchestrator):
    name = "airflow"

    def mutating_tools(self) -> set[str]:
        return {"airflow_clear_task"} if self._state()["actions"] else set()

    def tools(self):
        def airflow_list_dags() -> dict:
            """List DAGs with their schedules."""
            return self._list_dags()

        def airflow_list_dag_runs(dag_id: str, limit: int = 10) -> dict:
            """List recent runs of a DAG, newest first, with state and logical date."""
            return self._list_runs(dag_id, limit)

        def airflow_get_task_instances(dag_id: str, run_id: str) -> dict:
            """List task instances of a DAG run with state and number of tries."""
            return self._task_instances(dag_id, run_id)

        def airflow_get_task_log(dag_id: str, run_id: str, task_id: str, try_number: int = 1, max_chars: int = 20000) -> dict:
            """Read the log of one task try."""
            return self._task_log(dag_id, run_id, task_id, try_number, max_chars)

        tools = {f.__name__: f for f in (airflow_list_dags, airflow_list_dag_runs, airflow_get_task_instances, airflow_get_task_log)}
        if self._state()["actions"]:

            def airflow_clear_task(dag_id: str, run_id: str, task_id: str) -> dict:
                """Clear a task instance so that it is rescheduled. This changes the live system."""
                return self._clear(dag_id, run_id, task_id)

            tools["airflow_clear_task"] = airflow_clear_task
        return tools
