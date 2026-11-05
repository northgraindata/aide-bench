# aide-bench

An open benchmark for AI data engineer agents.

Each task is a realistic data incident: a revenue number that is wrong, a DAG that failed with a useless message, a dashboard that stopped refreshing.
The agent investigates through tools (warehouse queries, orchestrator logs, repository reads, object storage, lakehouse metadata, docs) and must reach a verdict it can support with evidence.
Some tasks also ask for a fix, which is checked by hidden tests.

The benchmark measures what a data team cares about when it lets an agent loose on its stack.
Does the agent find the real cause, does it cite what it actually looked at, does it say "I cannot tell" when the evidence is missing, and does it stay read-only when a log tells it to do otherwise.

Tasks use the [Harbor](https://github.com/harbor-framework/harbor) task format, so any Harbor-compatible agent can run them.
The design borrows from [ADE-bench](https://github.com/dbt-labs/ade-bench), [Spider 2.0](https://github.com/xlang-ai/Spider2) and [Terminal-Bench](https://github.com/harbor-framework/terminal-bench-1).

## Status

Version 0.1.0.
The harness, graders and 13 tasks are in place and validated: the reference solution passes every task and a do-nothing agent fails every task, both offline and in containers.
No model results are published yet.
Expert and junior time estimates in `task.toml` are the authors' estimates and have not been measured.
Read `docs/METHODOLOGY.md` and `docs/THREAT_MODEL.md` before quoting any number from this benchmark.

## What is in it

<!-- stats:start -->
| Dataset | Tasks | Diagnose | Fix | Easy / Medium / Hard | Stacks | Expert time (min) |
| --- | --- | --- | --- | --- | --- | --- |
| `aide-bench-core` | 13 | 11 | 2 | 3 / 7 / 3 | docs/markdown, lakehouse/iceberg, object_storage/s3-minio, orchestrator/airflow, orchestrator/dagster, repo/git, transform/dbt, warehouse/duckdb | 255 |
<!-- stats:end -->

Tracks:

- `diagnose`: find the cause and submit a structured answer with cited evidence.
- `fix`: diagnose and submit a patch that is applied to a pristine repository and run against hidden tests.

Several tasks are behavioral probes rather than knowledge tests.
They cover a false alarm, a decoy error that is louder than the real one, text in a log that tries to instruct the agent, evidence that cannot be read, and the same incident on two different orchestrators.

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
See `docs/RUNNING.md` for agents, repeated attempts, the optional LLM judge and reading results.

## How it works

Each task ships a frozen world: a snapshot of the systems at the moment of the incident.
The agent reaches it through an MCP server registered in `task.toml`.
Every tool call is traced with a `trace_id`, and the agent must cite trace ids in its final answer.
The verifier runs in a separate container, receives only the declared artifacts (answer, trace, patch) and holds the ground truth.

Systems are described by *kind* (warehouse, orchestrator, lakehouse, object storage, transform, repo, docs), by *flavor* (the product surface: Airflow, Dagster, DuckDB, dbt, Iceberg, MinIO) and by how faithfully the flavor emulates the product.
Adding a stack means adding a flavor, not rewriting tasks.
See `docs/FIDELITY.md` for what each flavor does and does not reproduce.

## Adding a task

```bash
uv run aide new my-incident --difficulty medium
# edit environment/scenario/scenario.yaml, instruction.md, tests/ground_truth.yaml, solution/solution.yaml
uv run aide check my-incident
```

A task is declarative YAML plus the files its systems return.
`aide check` refuses a task whose reference solution does not score 1.0 or whose do-nothing run does not score 0.0.
See `docs/ADDING_TASKS.md`.

## Contributing and license

See `CONTRIBUTING.md`.
Licensed under Apache-2.0.

Task files carry a canary string so that benchmark data can be excluded from training corpora.
Do not publish solutions or ground truth outside this repository's held-out process.
