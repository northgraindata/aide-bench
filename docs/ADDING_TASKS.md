# Adding a task

```bash
uv run aide new my-incident --difficulty medium          # diagnose track
uv run aide new fix-my-bug --track fix --difficulty easy  # fix track
```

`aide new` writes the generated boilerplate (Dockerfiles, `test.sh`, `solve.sh`) and stubs for the files you author.
Do not edit the generated files.
`aide sync` rewrites them and `aide lint` fails if they drift.

## Files you write

| File | Purpose |
| --- | --- |
| `task.toml` | Description, difficulty, tags, estimates. |
| `instruction.md` | The alert in the words a user would use. Do not name the cause. |
| `environment/scenario/scenario.yaml` | The systems and their data. |
| `environment/scenario/...` | Files the systems return: repo files, logs, objects, docs. |
| `tests/ground_truth.yaml` | What a correct answer contains. Never visible to the agent. |
| `solution/solution.yaml` | A reference investigation. It uses the same tools an agent uses. |

## Describing the world

`scenario.yaml` lists systems, each with a `kind` and a `flavor`, and the data for that flavor.

```yaml
systems:
  - kind: warehouse
    flavor: duckdb
    sql:
      - "create table raw_orders as select ..."
  - kind: orchestrator
    flavor: airflow
    dags:
      - dag_id: ingest_orders
        runs:
          - run_id: scheduled__2026-10-30
            state: failed
            tasks:
              - task_id: load_raw
                tries:
                  - {try_number: 1, state: failed, log: "ERROR ..."}
                  - {try_number: 2, state: success, log_file: logs/load_raw_2.log}
```

Use `aide-call` inside a container, or the tests in `tests/test_flavors.py`, to see which tools a flavor exposes.

## Ground truth

```yaml
track: diagnose
categories: [data-loss]
forbidden_categories: [infrastructure, no-issue]
verdict: supported
required_evidence:
  - {tool: repo_read_file, args_regex: 'stg_orders\.sql', result_regex: 'currency is not null'}
facts:
  - id: filter
    statement: stg_orders drops rows with a NULL currency.
    patterns: ['currency.{0,25}null']
```

Write required evidence so that every reasonable investigation path satisfies it.
Require the fact the agent must have seen, not the exact query it must have run.

## Good tasks

- Make the real cause discoverable but not announced.
  The alert should describe a symptom.
- Add realistic noise: a decoy error, an old failure, an unrelated commit.
- Prefer one behavior per task.
  A task that tests evidence use should not also depend on obscure product trivia.
- Include negative controls (a false alarm) and honest-uncertainty cases (evidence that cannot be read).
- Do not let the scenario files or the instruction contain the answer's key phrases outside the places an investigation would find them.

## Checking

```bash
uv run aide check my-incident   # lint, then oracle must score 1.0 and a do-nothing run 0.0
uv run pytest                   # adds adversarial answers for every diagnose task
uv run aide validate my-incident  # the same gate in containers through Harbor
```

Think about what a plausible wrong answer looks like and make sure the ground truth rejects it.
`tests/test_grading.py` already tries wrong categories, missing evidence, made-up trace ids, unrelated evidence and flipped verdicts on every diagnose task.

## Fix tasks

Add `writable: true` to the `repo/git` system, put the repository under `environment/scenario/repo`, a hidden test under `tests/hidden/` and a reference patch at `solution/fix.patch`.
`aide sync` copies the repository to `tests/base`, which the verifier patches.
The hidden test command receives `$AIDE_TESTS_DIR` and runs inside the patched copy.
