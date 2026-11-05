"""Shared snapshot model for orchestrators. Product flavors only rename the tools."""
from __future__ import annotations

import json
from pathlib import Path

from .base import Flavor, read_text_ref
from .util import clip


class Orchestrator(Flavor):
    kind = "orchestrator"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        dags = []
        for dag in spec.get("dags", []):
            runs = []
            for run in dag.get("runs", []):
                tasks = []
                for task in run.get("tasks", []):
                    tries = [
                        {
                            "try_number": t.get("try_number", index + 1),
                            "state": t.get("state", "success"),
                            "log": read_text_ref(scenario, t.get("log"), t.get("log_file")),
                        }
                        for index, t in enumerate(task.get("tries") or [{"state": task.get("state", "success"), "log": task.get("log"), "log_file": task.get("log_file")}])
                    ]
                    tasks.append({"task_id": task["task_id"], "state": tries[-1]["state"], "tries": tries})
                runs.append({**{k: v for k, v in run.items() if k != "tasks"}, "tasks": tasks})
            dags.append({**{k: v for k, v in dag.items() if k != "runs"}, "runs": runs})
        (target / "state.json").write_text(json.dumps({"dags": dags, "actions": bool(spec.get("actions"))}, indent=2, default=str))

    def _state(self) -> dict:
        return json.loads((self.dir / "state.json").read_text())

    def _dag(self, dag_id: str) -> dict | None:
        return next((d for d in self._state()["dags"] if d["dag_id"] == dag_id), None)

    # shared implementations ------------------------------------------------
    def _list_dags(self) -> dict:
        return {"dags": [{k: v for k, v in d.items() if k != "runs"} for d in self._state()["dags"]]}

    def _list_runs(self, dag_id: str, limit: int = 10) -> dict:
        dag = self._dag(dag_id)
        if dag is None:
            return {"error": f"Unknown DAG/job: {dag_id}"}
        runs = [{k: v for k, v in r.items() if k != "tasks"} for r in dag["runs"]]
        return {"runs": runs[:limit]}

    def _task_instances(self, dag_id: str, run_id: str) -> dict:
        dag = self._dag(dag_id)
        run = next((r for r in (dag or {}).get("runs", []) if r["run_id"] == run_id), None)
        if run is None:
            return {"error": f"Unknown run: {dag_id}/{run_id}"}
        return {"task_instances": [{"task_id": t["task_id"], "state": t["state"], "tries": [{"try_number": x["try_number"], "state": x["state"]} for x in t["tries"]]} for t in run["tasks"]]}

    def _task_log(self, dag_id: str, run_id: str, task_id: str, try_number: int = 1, max_chars: int = 20000) -> dict:
        dag = self._dag(dag_id)
        run = next((r for r in (dag or {}).get("runs", []) if r["run_id"] == run_id), None)
        task = next((t for t in (run or {}).get("tasks", []) if t["task_id"] == task_id), None)
        attempt = next((x for x in (task or {}).get("tries", []) if x["try_number"] == try_number), None)
        if attempt is None:
            return {"error": f"No log for {dag_id}/{run_id}/{task_id} try {try_number}"}
        return {"state": attempt["state"], **clip(attempt["log"], max_chars)}

    def _clear(self, dag_id: str, run_id: str, task_id: str) -> dict:
        return {"cleared": True, "note": "Task cleared and rescheduled."}
