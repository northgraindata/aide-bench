# Flavor fidelity

Each flavor declares one of three levels.

- **engine**: a real engine runs over frozen data.
- **transpiled**: a dialect is translated onto an engine, with product metadata served from fixtures.
- **recorded**: frozen responses in the shape the product returns.

| Kind / flavor | Level | What it reproduces | What it does not |
| --- | --- | --- | --- |
| `warehouse/duckdb` | engine | Real DuckDB SQL on frozen tables, read-only. | Other dialects. Query history. Warehouse-specific errors. |
| `repo/git` | recorded | Files at HEAD, text search, commit log with diffs, patch validation. | Branches, blame, binary files. |
| `orchestrator/airflow` | recorded | DAGs, runs, task instances, per-try logs, an optional clear action. | The real REST schema, scheduling, XCom, sensors. |
| `orchestrator/dagster` | recorded | Jobs, runs, steps, per-attempt logs, an optional re-execute action. | Assets, sensors, the GraphQL API. |
| `transform/dbt` | recorded | Run results, model SQL and dependencies, test results. | Compilation, the full manifest, lineage graph. |
| `object_storage/s3-minio` | recorded | Buckets, listing, text objects, AccessDenied prefixes. | Versioning, ACLs, large or binary objects. |
| `lakehouse/iceberg` | recorded | Schema history and snapshots for a table. | Manifests, data files, time travel queries. |
| `docs/markdown` | recorded | Runbook pages with search. | |
| `fixture/recorded` | recorded | Any system, with responses matched on the call input. | Anything not declared. |

Tool names follow each product's vocabulary (`airflow_get_task_log`, `dagster_get_step_logs`) so that an agent that knows the product finds what it expects.
The same incident can be built on two orchestrators to test whether an agent understands the problem or only one tool.
`non-idempotent-retry` and `non-idempotent-retry-dagster` do exactly that.

Fidelity checks against real products are not part of 0.1.0.
Recording golden responses from real systems and comparing the emulators with them is future work.
