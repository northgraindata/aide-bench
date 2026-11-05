# Adding a flavor

A flavor teaches the benchmark about one product.
It lives in `src/aide_systems/flavors/` or in your own package.

```python
from aide_systems.flavors import Flavor, register


@register
class Prefect(Flavor):
    kind = "orchestrator"
    name = "prefect"
    fidelity = "recorded"

    @classmethod
    def build(cls, spec, scenario, world):
        ...  # freeze the scenario data into world/<name>/

    def tools(self):
        def prefect_get_flow_run_logs(flow_run_id: str) -> dict:
            """Read the logs of a flow run."""
            ...

        return {"prefect_get_flow_run_logs": prefect_get_flow_run_logs}

    def mutating_tools(self):
        return set()  # names of tools that change a live system
```

Rules:

- Tool functions need type hints and a docstring: they become the MCP tool schema and description.
- Return JSON-serializable dicts.
  Return `{"error": "..."}` for failures the way the product would, never raise.
- Mark every tool that would change a live system as mutating.
  The trace records it and any call fails the `safety` component.
- Cut large outputs with `clip` from `flavors/util.py` and say so, so that the agent knows its evidence is partial.
- Declare the fidelity level honestly and add the flavor to `docs/FIDELITY.md`.

Out-of-tree flavors register through the `aide_bench.flavors` entry point group.
Orchestrators can subclass `flavors/orchestrator.py` to reuse the run, task and log model.
