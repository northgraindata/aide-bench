# Running agents

## Prerequisites

- `uv`, and either Apple's `container` CLI (macOS) or Docker.
- `uv tool install harbor==0.25.0`.
- `uv run aide build-image` once, and again whenever `src/` changes.

## Run

```bash
harbor run -p datasets/aide-bench-core -a claude-code -m <model> -e apple-container -k 3 -n 4
uv run aide report jobs/<job-name>
```

Use `-e docker` where you do not have Apple containers.
`-k` is the number of attempts per task and `-n` the concurrency.
Any agent Harbor supports works, because the tools arrive through the MCP server declared in each `task.toml`.
Check the agent's trial output for the registered `aide` server before trusting a run.

## Results

Harbor writes one directory per trial under `jobs/<job-name>/`.
`result.json` holds the reward components, tokens, cost and any exception.
`artifacts/app/aide-out/` holds the answer, the trace and any patch.
`aide report` summarizes: tasks graded, pass rate, `pass@k`, `pass^k`, errored trials, tokens and cost.

## The optional judge

```bash
harbor run ... --ve AIDE_JUDGE=1 --ve ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY --ve AIDE_JUDGE_MODEL=claude-haiku-5-5
```

Harbor asks you to confirm before it passes variables to the verifier.
Check `harbor run --help` for the exact flag in your Harbor version.
Judged and pattern-matched `facts_recall` values are not comparable.

## Gates for contributors

```bash
uv run aide check      # fast, offline
uv run aide validate   # containers: oracle passes, nop fails
```
