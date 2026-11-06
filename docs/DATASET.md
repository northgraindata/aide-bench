# Dataset details

## Version 0.1.0

The harness, graders and 13 tasks are in place and validated: the reference solution passes every task and a do-nothing agent fails every task, both offline and in containers.
No model results are published yet.
All current tasks are public development tasks; there is no held-out test split.

<!-- stats:start -->
| Dataset | Tasks | Diagnose | Fix | Easy / Medium / Hard | Stacks | Expert time (min) |
| --- | --- | --- | --- | --- | --- | --- |
| `aide-bench-core` | 13 | 11 | 2 | 3 / 7 / 3 | docs/markdown, lakehouse/iceberg, object_storage/s3-minio, orchestrator/airflow, orchestrator/dagster, repo/git, transform/dbt, warehouse/duckdb | 255 |
<!-- stats:end -->

Regenerate this table with `uv run aide stats --write`. Print it without writing with `uv run aide stats`.
Expert and junior time estimates in `task.toml` are the authors' estimates and have not been measured.
They do not support claims about time saved. See the [methodology](METHODOLOGY.md) and [threat model](THREAT_MODEL.md) before quoting benchmark numbers.

## Tracks

- `diagnose`: find the cause and submit a structured answer with cited evidence.
- `fix`: diagnose and submit a patch that is applied to a pristine repository and run against hidden tests.

Several tasks are behavioral probes rather than knowledge tests: a false alarm, a decoy error louder than the real one, instructions planted in a log, unreadable evidence and the same incident on two orchestrators.

Task files carry a canary string so benchmark data can be excluded from training corpora.
Do not publish solutions or ground truth outside this repository's held-out process.
