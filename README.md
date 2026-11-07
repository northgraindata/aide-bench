![AIDE Bench — Benchmarking AI agents on real data engineering problems](docs/assets/aide-bench-banner.png)

# aide-bench

An open benchmark for AI data engineer agents.

Each task is a realistic data incident: a revenue number that is wrong, a DAG that failed with a useless message, a dashboard that stopped refreshing, a warehouse bill that suddenly grew.
The agent investigates through tools (warehouse queries, orchestrator and cluster logs, repository reads, object storage, lakehouse metadata, docs) and must reach a verdict it can support with evidence.
Some tasks also ask for a fix, which is checked by hidden tests.

The benchmark measures what a data team cares about when it lets an agent loose on its stack.
Does the agent find the real cause, does it cite what it actually looked at, does it say "I cannot tell" when the evidence is missing, and does it stay read-only when a log tells it to do otherwise.

Tasks use the [Harbor](https://github.com/harbor-framework/harbor) task format, so any Harbor-compatible agent can run them.
The design borrows from [ADE-bench](https://github.com/dbt-labs/ade-bench), [Spider 2.0](https://github.com/xlang-ai/Spider2) and [Terminal-Bench](https://github.com/harbor-framework/terminal-bench-1).

## Status

Version 0.1.0.
The harness, graders and 31 tasks in three suites are in place.
For every task the reference solution scores 1.0 and a do-nothing agent scores 0.0.
No model results are published yet.
Expert and junior time estimates in `task.toml` are the authors' estimates and have not been measured.
Everything the tasks return was written by hand from the formats of the real products and not recorded from real runs.
Treat any number from this benchmark with that in mind: the emulators are stand-ins, and an agent with a shell can bypass the trace.

## Suites

Each suite is a separate Harbor dataset with its own results.

| Suite | Focus |
| --- | --- |
| `aide-bench-core` | The modern open stack: Python, SQL, dbt, Airflow and Dagster, Iceberg on MinIO. Includes the only two `fix` tasks. |
| `aide-bench-legacy` | What still runs in many companies: Spark jobs in Scala on YARN, R reports, Hive, cron and bash, Python 2 to 3 migrations. |
| `aide-bench-cloud` | Managed platforms: Snowflake, BigQuery, Databricks with Delta Lake, Prefect. |

<!-- stats:start -->
| Dataset | Tasks | Diagnose | Fix | Easy / Medium / Hard | Stacks | Expert time (min) |
| --- | --- | --- | --- | --- | --- | --- |
| `aide-bench-cloud` | 8 | 8 | 0 | 1 / 6 / 1 | docs/markdown, lakehouse/delta, orchestrator/airflow, orchestrator/prefect, repo/git, warehouse/bigquery, warehouse/databricks-sql, warehouse/duckdb, warehouse/snowflake | 172 |
| `aide-bench-core` | 13 | 11 | 2 | 3 / 7 / 3 | docs/markdown, lakehouse/iceberg, object_storage/s3-minio, orchestrator/airflow, orchestrator/dagster, repo/git, transform/dbt, warehouse/duckdb | 255 |
| `aide-bench-legacy` | 10 | 10 | 0 | 0 / 6 / 4 | compute/spark, compute/yarn, docs/markdown, object_storage/s3-minio, orchestrator/cron, repo/git, warehouse/duckdb | 275 |
<!-- stats:end -->

Tracks:

- `diagnose`: find the cause and submit a structured answer with cited evidence.
- `fix`: diagnose and submit a patch that is applied to a pristine repository and run against hidden tests.

Several tasks are behavioral probes rather than knowledge tests.
They cover a false alarm, a decoy that is louder than the real cause (object storage errors, a refactor, a quota error), text in a log that tries to instruct the agent, evidence that cannot be read, and the same incident on different stacks (Airflow, Dagster, Prefect, Snowflake).

## What the tasks look like

Every task is one alert in the words a user would use, and the answer is never named.

| Suite | Examples |
| --- | --- |
| core | A DAG succeeds but 12% of the revenue is gone. A renamed column breaks a dbt model. The storage audit log is full of `AccessDenied`, but the cause is a changed type. A log tells the agent to clear a task. |
| legacy | A Scala join runs out of memory because one default key covers 38% of the rows. R 4 stops creating factors and a report comes out empty. A tidied crontab loses its `PATH` and a missing `pipefail` hides it. A snapshot job outgrows its schedule and overlaps itself. |
| cloud | A dbt model switches from incremental to table and Snowflake credits grow 40 times. A Delta overwrite from a stale read reverts a merge. A Prefect task is cached without the run date. A scheduled BigQuery report runs before the stream is complete. |

Run `uv run aide stats` for the numbers and read `datasets/<suite>/<task>/instruction.md` for any task.

## Quick start

```bash
uv sync --extra dev
uv run pytest                      # unit tests, graders, every task through oracle and nop
uv run aide check                  # lint + offline oracle/nop for all tasks, no containers
uv run aide build-image            # builds the aide-systems base image (Apple container or Docker)
uv tool install harbor==0.25.0
```

Run a reference agent with Harbor:

```bash
harbor run -p datasets/aide-bench-core -a claude-code -m <model> -e apple-container -k 3
uv run aide report jobs/<job-name>
```

Use `-e docker` on Linux.
Point `-p` at one suite or one task directory, and use `-k` for repeated attempts.

## How it works

Each task ships a frozen world: a snapshot of the systems at the moment of the incident.
The agent reaches it through an MCP server registered in `task.toml`.
Every tool call is traced with a `trace_id`, and the agent must cite trace ids in its final answer.
The verifier runs in a separate container, receives only the declared artifacts (answer, trace, patch) and holds the ground truth.

Systems are described by *kind* (warehouse, orchestrator, compute, lakehouse, object storage, transform, repo, docs), by *flavor* (the product surface: Airflow, Prefect, cron, Spark, YARN, Snowflake, BigQuery, Delta, dbt, Iceberg, MinIO) and by how faithfully the flavor emulates the product.
Adding a stack means adding a flavor, not rewriting tasks.
Scala, R, HiveQL and bash are never executed: the agent reads the source and the logs, which is what an investigation needs.
Each flavor declares its fidelity (`engine`, `transpiled` or `recorded`) in its class.

## Scoring

A `diagnose` task scores 1 when the answer has every required category and none of the forbidden ones, the right verdict, cited trace ids that exist, no mutating or forbidden tool call and no forbidden claim.
Evidence recall, fact recall, category precision and affected-resource F1 are reported but do not decide the score, because agents reach the same fact through different tools.
A `fix` task scores 1 when the patch applies to a pristine repository and the hidden tests pass.

## Adding a task

```bash
uv run aide new my-incident --dataset aide-bench-legacy --difficulty medium
# edit environment/scenario/scenario.yaml, instruction.md, tests/ground_truth.yaml, solution/solution.yaml
uv run aide check my-incident
```

A task is declarative YAML plus the files its systems return.
`aide check` refuses a task whose reference solution does not score 1.0 or whose do-nothing run does not score 0.0.
When the stack you need is missing, add a flavor under `src/aide_systems/flavors/` (see `flavors/compute.py` for a small one).

## Roadmap

- Held-out `test` split. All 31 tasks are `dev` today.
- Fix tasks beyond core. Scala and R fixes need a verifier image per language (sbt, testthat).
- Recording golden responses from real Spark, R and Snowflake runs to check the emulators against.
- A `build` track.
- Measured time estimates.

## Contributing and license

See `CONTRIBUTING.md`.
Licensed under Apache-2.0.

Task files carry a canary string so that benchmark data can be excluded from training corpora.
Do not publish solutions or ground truth outside this repository's held-out process.
