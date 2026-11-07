# Contributing

Tasks, flavors and graders are welcome.

1. Look at an existing task under `datasets/` or a flavor under `src/aide_systems/flavors/`.
2. Run `uv run aide check` and `uv run pytest`.
3. Run `uv run aide validate` for any task you add or change.
4. Describe what behavior the task tests and what a plausible wrong answer looks like.

A task is accepted only when the reference solution scores 1.0, a do-nothing agent scores 0.0, and the adversarial tests in `tests/test_grading.py` pass for it.

Do not post task solutions or ground truth in issues, pull requests or elsewhere in public.
Report suspected leaks or unfair tasks privately to the maintainers.
