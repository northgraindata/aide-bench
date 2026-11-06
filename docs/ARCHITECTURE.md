# Architecture

## Frozen task environments

Each task ships a frozen world: a snapshot of the systems at the moment of the incident.
The agent reaches it through an MCP server registered in `task.toml`.
Every tool call is traced with a `trace_id`, and the agent must cite trace ids in its final answer.

The verifier runs in a separate container, receives only the declared artifacts (answer, trace, patch) and holds the ground truth.
See the [methodology](METHODOLOGY.md) for the answer schema, evidence requirements and scoring gates.

## Systems and fidelity

Systems are described by:

- **Kind:** warehouse, orchestrator, lakehouse, object storage, transform, repo or docs.
- **Flavor:** the product surface, such as Airflow, Dagster, DuckDB, dbt, Iceberg or MinIO.
- **Fidelity:** how faithfully the flavor emulates the product, from recorded responses to a real engine over frozen data.

Adding a stack means adding a flavor, not rewriting tasks.
See [flavor fidelity](FIDELITY.md) for what each flavor does and does not reproduce, and [adding flavors](ADDING_FLAVORS.md) for the implementation guide.
