"""transform/dbt: dbt artifacts (run results, manifest nodes, test results) from a recorded invocation."""
from __future__ import annotations

import json
from pathlib import Path

from .base import Flavor, read_text_ref
from .registry import register
from .util import clip


@register
class Dbt(Flavor):
    kind = "transform"
    name = "dbt"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        models = []
        for model in spec.get("models", []):
            models.append({**{k: v for k, v in model.items() if k not in ("sql", "sql_file")}, "sql": read_text_ref(scenario, model.get("sql"), model.get("sql_file"))})
        (target / "state.json").write_text(json.dumps({"models": models, "tests": spec.get("tests", [])}, indent=2, default=str))

    def _state(self) -> dict:
        return json.loads((self.dir / "state.json").read_text())

    def tools(self):
        def dbt_run_results() -> dict:
            """Result of the last dbt invocation: status, message and timing per model."""
            return {"results": [{k: m.get(k) for k in ("name", "status", "message", "execution_time", "rows_affected")} for m in self._state()["models"]]}

        def dbt_get_model(name: str) -> dict:
            """Get a model's compiled SQL, upstream dependencies and columns."""
            model = next((m for m in self._state()["models"] if m["name"] == name), None)
            if model is None:
                return {"error": f"Unknown model: {name}"}
            return {"name": name, "path": model.get("path"), "depends_on": model.get("depends_on", []), "columns": model.get("columns", []), "sql": clip(model["sql"])}

        def dbt_test_results() -> dict:
            """Result of dbt tests from the last invocation."""
            return {"tests": self._state()["tests"]}

        return {f.__name__: f for f in (dbt_run_results, dbt_get_model, dbt_test_results)}
