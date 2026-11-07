"""compute/spark and compute/yarn: recorded cluster state for legacy batch stacks.

Both flavors freeze what a person would read from the Spark UI / history server and the YARN
ResourceManager: applications, stages, executors, nodes and container logs. Nothing is executed.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import Flavor, read_text_ref
from .registry import register
from .util import clip


def _freeze_logs(items: list[dict], scenario: Path) -> list[dict]:
    out = []
    for item in items:
        item = dict(item)
        item["log"] = read_text_ref(scenario, item.pop("log", None), item.pop("log_file", None))
        out.append(item)
    return out


@register
class Spark(Flavor):
    kind = "compute"
    name = "spark"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        apps = []
        for app in spec.get("applications", []):
            app = dict(app)
            app["driver_log"] = read_text_ref(scenario, app.pop("driver_log", None), app.pop("driver_log_file", None))
            app["executors"] = _freeze_logs(app.get("executors", []), scenario)
            apps.append(app)
        (target / "state.json").write_text(json.dumps({"applications": apps}, indent=2, default=str))

    def _apps(self) -> list[dict]:
        return json.loads((self.dir / "state.json").read_text())["applications"]

    def _app(self, app_id: str) -> dict | None:
        return next((a for a in self._apps() if a["app_id"] == app_id), None)

    def tools(self):
        def spark_list_applications(limit: int = 20) -> dict:
            """List Spark applications, newest first, with name, state and duration."""
            keys = ("app_id", "name", "user", "state", "start", "duration_s")
            return {"applications": [{k: a.get(k) for k in keys} for a in self._apps()[:limit]]}

        def spark_get_application(app_id: str) -> dict:
            """Get one application: state, the Spark configuration it ran with and the failure reason."""
            app = self._app(app_id)
            if app is None:
                return {"error": f"Unknown application: {app_id}"}
            return {k: app.get(k) for k in ("app_id", "name", "user", "state", "start", "duration_s", "spark_version", "conf", "failure_reason")}

        def spark_list_stages(app_id: str) -> dict:
            """List the stages of an application with status, task counts and failed tasks."""
            app = self._app(app_id)
            if app is None:
                return {"error": f"Unknown application: {app_id}"}
            keys = ("stage_id", "name", "status", "num_tasks", "failed_tasks", "duration_s")
            return {"stages": [{k: s.get(k) for k in keys} for s in app.get("stages", [])]}

        def spark_get_stage(app_id: str, stage_id: int) -> dict:
            """Get stage details: task duration quantiles, input and shuffle sizes, spill and failure reason."""
            app = self._app(app_id)
            stage = next((s for s in (app or {}).get("stages", []) if s["stage_id"] == stage_id), None)
            if stage is None:
                return {"error": f"Unknown stage: {app_id}/{stage_id}"}
            return stage

        def spark_get_driver_log(app_id: str, max_chars: int = 20000) -> dict:
            """Read the driver log of an application."""
            app = self._app(app_id)
            if app is None:
                return {"error": f"Unknown application: {app_id}"}
            return clip(app["driver_log"], max_chars)

        def spark_get_executor_log(app_id: str, executor_id: str, max_chars: int = 20000) -> dict:
            """Read the stderr log of one executor."""
            app = self._app(app_id)
            executor = next((e for e in (app or {}).get("executors", []) if str(e["id"]) == str(executor_id)), None)
            if executor is None:
                return {"error": f"Unknown executor: {app_id}/{executor_id}"}
            return {"host": executor.get("host"), "status": executor.get("status"), **clip(executor["log"], max_chars)}

        fns = (spark_list_applications, spark_get_application, spark_list_stages, spark_get_stage, spark_get_driver_log, spark_get_executor_log)
        return {f.__name__: f for f in fns}


@register
class Yarn(Flavor):
    kind = "compute"
    name = "yarn"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        apps = []
        for app in spec.get("applications", []):
            app = dict(app)
            app["containers"] = _freeze_logs(app.get("containers", []), scenario)
            apps.append(app)
        (target / "state.json").write_text(json.dumps({"nodes": spec.get("nodes", []), "applications": apps}, indent=2, default=str))

    def _state(self) -> dict:
        return json.loads((self.dir / "state.json").read_text())

    def tools(self):
        def yarn_list_nodes() -> dict:
            """List cluster nodes with state, health report and disk usage."""
            return {"nodes": self._state()["nodes"]}

        def yarn_list_applications(limit: int = 20) -> dict:
            """List applications, newest first, with final status and diagnostics."""
            keys = ("app_id", "name", "user", "queue", "state", "final_status", "diagnostics", "start")
            return {"applications": [{k: a.get(k) for k in keys} for a in self._state()["applications"][:limit]]}

        def yarn_get_application(app_id: str) -> dict:
            """Get one application with its attempts and container list (exit codes, no logs)."""
            app = next((a for a in self._state()["applications"] if a["app_id"] == app_id), None)
            if app is None:
                return {"error": f"Unknown application: {app_id}"}
            containers = [{k: c.get(k) for k in ("container_id", "node", "exit_code", "state")} for c in app.get("containers", [])]
            return {**{k: v for k, v in app.items() if k != "containers"}, "containers": containers}

        def yarn_get_container_log(app_id: str, container_id: str, max_chars: int = 20000) -> dict:
            """Read the aggregated log of one container."""
            app = next((a for a in self._state()["applications"] if a["app_id"] == app_id), None)
            container = next((c for c in (app or {}).get("containers", []) if c["container_id"] == container_id), None)
            if container is None:
                return {"error": f"Unknown container: {app_id}/{container_id}"}
            return {"node": container.get("node"), "exit_code": container.get("exit_code"), **clip(container["log"], max_chars)}

        return {f.__name__: f for f in (yarn_list_nodes, yarn_list_applications, yarn_get_application, yarn_get_container_log)}
