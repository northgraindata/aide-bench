# Contributing

Tasks, flavors and graders are welcome.

## Developer setup

From a local checkout with `uv` installed:

```bash
uv sync --extra dev
uv run pytest         # unit tests, graders, every task through oracle and nop
uv run aide check     # lint + offline oracle/nop; no containers
```

For container validation, follow the [evaluation setup](docs/RUNNING.md#evaluation-setup) to install Harbor and build the task image.
This developer setup is separate from [running an evaluation](docs/RUNNING.md).

## Submitting changes

1. Read `docs/ADDING_TASKS.md` or `docs/ADDING_FLAVORS.md`.
2. Run `uv run aide check` and `uv run pytest`.
3. Run `uv run aide validate` for any task you add or change.
4. Describe what behavior the task tests and what a plausible wrong answer looks like.

A task is accepted only when the reference solution scores 1.0, a do-nothing agent scores 0.0, and the adversarial tests in `tests/test_grading.py` pass for it.

Do not post task solutions or ground truth in issues, pull requests or elsewhere in public.
Report suspected leaks or unfair tasks privately to the maintainers.
