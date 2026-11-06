"""`aide`: author, check and run aide-bench tasks."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from . import templates
from .checks import lint, offline_problems
from .tasks import Task, discover, find_root

IMAGE = templates.BASE_IMAGE


# -- authoring ---------------------------------------------------------------
def cmd_new(args: argparse.Namespace) -> int:
    root = find_root()
    path = root / "datasets" / args.dataset / args.name
    if path.exists():
        print(f"{path} already exists", file=sys.stderr)
        return 1
    for sub in ("environment/scenario", "tests", "solution"):
        (path / sub).mkdir(parents=True)
    (path / "task.toml").write_text(templates.task_toml(args.name, args.track, args.difficulty, "TODO one sentence."))
    (path / "instruction.md").write_text(templates.instruction_stub())
    (path / "environment/scenario/scenario.yaml").write_text(templates.SCENARIO_STUB)
    truth = templates.GROUND_TRUTH_STUB
    if args.track == "fix":
        truth = truth.replace("track: diagnose\ncategories: [code-bug]\n", "track: fix\nfix:\n  test_command: python \"$AIDE_TESTS_DIR/hidden/check.py\" .\n  allowed_paths: []\n")
        (path / "tests/hidden").mkdir()
        (path / "environment/scenario/repo").mkdir()
    (path / "tests/ground_truth.yaml").write_text(truth)
    (path / "solution/solution.yaml").write_text(templates.SOLUTION_STUB)
    sync_task(Task(path))
    print(f"created {path.relative_to(root)}")
    return 0


def sync_task(task: Task) -> list[str]:
    changed = []
    for relative, content in templates.GENERATED.items():
        file = task.path / relative
        if not file.exists() or file.read_text() != content:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)
            changed.append(relative)
        if relative in templates.EXECUTABLE:
            file.chmod(0o755)
    if task.metadata.get("track") == "fix":
        base, repo = task.tests_dir / "base", task.scenario_dir / "repo"
        if repo.is_dir():
            shutil.rmtree(base, ignore_errors=True)
            shutil.copytree(repo, base)
            changed.append("tests/base")
    return changed


def cmd_sync(args: argparse.Namespace) -> int:
    for task in discover(find_root(), args.task):
        changed = sync_task(task)
        print(f"{task.id}: {', '.join(changed) if changed else 'up to date'}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    failed = 0
    for task in discover(find_root(), args.task):
        problems = lint(task)
        print(f"{'FAIL' if problems else 'ok  '} {task.id}")
        for problem in problems:
            print(f"     - {problem}")
        failed += bool(problems)
    return 1 if failed else 0


def cmd_check(args: argparse.Namespace) -> int:
    """Lint plus an offline oracle and nop run through the real graders. Fast, no containers."""
    failed = 0
    for task in discover(find_root(), args.task):
        problems = lint(task) or offline_problems(task)
        print(f"{'FAIL' if problems else 'ok  '} {task.id}")
        for problem in problems:
            print(f"     - {problem}")
        failed += bool(problems)
    return 1 if failed else 0


# -- running -----------------------------------------------------------------
def runtime() -> str:
    return "container" if shutil.which("container") and sys.platform == "darwin" else "docker"


def cmd_build_image(args: argparse.Namespace) -> int:
    root = find_root()
    tool = runtime()
    command = [tool, "build", "-t", IMAGE, "-f", "docker/base.Dockerfile", "."]
    print("+", " ".join(command))
    return subprocess.run(command, cwd=root).returncode


def harbor_env() -> str:
    return "apple-container" if runtime() == "container" else "docker"


def cmd_validate(args: argparse.Namespace) -> int:
    """Containerized gate: the oracle must pass every task and the nop agent must fail every task."""
    root = find_root()
    tasks = discover(root, args.task)
    if not tasks:
        print("no tasks selected", file=sys.stderr)
        return 1
    if not args.skip_build and cmd_build_image(args) != 0:
        return 1
    failed = 0
    for agent, expected in (("oracle", 1.0), ("nop", 0.0)):
        for task in tasks:
            job = f"validate-{agent}-{task.id}"
            subprocess.run(["rm", "-rf", str(root / "jobs" / job)])
            run = subprocess.run(
                ["harbor", "run", "-p", str(task.path), "-a", agent, "-e", harbor_env(), "-n", "1", "--job-name", job, "-o", str(root / "jobs"), "-q"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            rewards = [t["verifier_result"]["rewards"]["reward"] for t in load_trials(root / "jobs" / job) if t.get("verifier_result")]
            ok = run.returncode == 0 and rewards == [expected]
            print(f"{'ok  ' if ok else 'FAIL'} {agent:6} {task.id} reward={rewards}")
            if not ok:
                failed += 1
                print((run.stdout + run.stderr)[-1500:])
    return 1 if failed else 0


# -- reporting ---------------------------------------------------------------
def load_trials(job_dir: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(job_dir.glob("*/result.json"))]


def cmd_stats(args: argparse.Namespace) -> int:
    root = find_root()
    tasks = discover(root, args.task)
    by_dataset: dict[str, list[Task]] = defaultdict(list)
    for task in tasks:
        by_dataset[task.dataset].append(task)
    lines = ["| Dataset | Tasks | Diagnose | Fix | Easy / Medium / Hard | Stacks | Expert time (min) |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for dataset, items in sorted(by_dataset.items()):
        tracks = defaultdict(int)
        levels = defaultdict(int)
        flavors: set[str] = set()
        minutes = 0.0
        for task in items:
            tracks[task.metadata["track"]] += 1
            levels[task.metadata["difficulty"]] += 1
            flavors.update(task.flavors)
            minutes += task.metadata.get("expert_time_estimate_min", 0)
        lines.append(
            f"| `{dataset}` | {len(items)} | {tracks['diagnose']} | {tracks['fix']} | "
            f"{levels['easy']} / {levels['medium']} / {levels['hard']} | {', '.join(sorted(flavors))} | {minutes:g} |"
        )
    table = "\n".join(lines)
    if args.write:
        readme = root / "README.md"
        text = readme.read_text()
        block = f"<!-- stats:start -->\n{table}\n<!-- stats:end -->"
        text = re.sub(r"<!-- stats:start -->.*?<!-- stats:end -->", lambda _: block, text, flags=re.S)
        readme.write_text(text)
        print(f"updated {readme}")
    else:
        print(table)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Summarize a Harbor job: pass rate, pass@k, pass^k, errors, tokens and cost per passing task."""
    trials = load_trials(Path(args.job))
    if not trials:
        print("no trials found", file=sys.stderr)
        return 1
    per_task: dict[str, list[float]] = defaultdict(list)
    errors = 0
    cost = tokens_in = tokens_out = 0.0
    seconds = 0.0
    for trial in trials:
        result = trial.get("agent_result") or {}
        cost += result.get("cost_usd") or 0
        tokens_in += result.get("n_input_tokens") or 0
        tokens_out += result.get("n_output_tokens") or 0
        if trial.get("exception_info"):
            errors += 1
            continue
        verifier = trial.get("verifier_result") or {}
        per_task[trial["task_name"]].append((verifier.get("rewards") or {}).get("reward", 0.0))
        execution = trial.get("agent_execution") or {}
        if execution.get("started_at") and execution.get("finished_at"):
            from datetime import datetime

            fmt = lambda v: datetime.fromisoformat(v.replace("Z", "+00:00"))  # noqa: E731
            seconds += (fmt(execution["finished_at"]) - fmt(execution["started_at"])).total_seconds()
    graded = sum(len(v) for v in per_task.values())
    passes = sum(sum(v) for v in per_task.values())
    any_pass = sum(any(r == 1.0 for r in v) for v in per_task.values())
    all_pass = sum(all(r == 1.0 for r in v) for v in per_task.values())
    n = len(per_task)
    print(f"tasks graded      {n}")
    print(f"trials graded     {graded} (errors, not graded: {errors})")
    print(f"pass rate         {passes / graded:.1%}" if graded else "pass rate         n/a")
    if n:
        print(f"pass@k (any)      {any_pass / n:.1%}")
        print(f"pass^k (all)      {all_pass / n:.1%}")
    print(f"tokens in/out     {tokens_in:,.0f} / {tokens_out:,.0f}")
    print(f"cost (reported)   ${cost:.2f}" + (f"  per pass ${cost / passes:.2f}" if passes and cost else ""))
    print(f"agent time        {seconds:.0f}s")
    if cost == 0:
        print("note: agent reported no cost; compare with your provider invoice before quoting cost.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="aide", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="scaffold a task")
    new.add_argument("name")
    new.add_argument("--track", choices=["diagnose", "fix"], default="diagnose")
    new.add_argument("--dataset", default="aide-bench-core")
    new.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="medium")
    new.set_defaults(fn=cmd_new)

    for name, fn, help_text in (
        ("sync", cmd_sync, "rewrite generated boilerplate"),
        ("lint", cmd_lint, "static checks"),
        ("check", cmd_check, "lint + offline oracle and nop through the real graders"),
        ("stats", cmd_stats, "dataset statistics"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("task", nargs="?", help="task id, dataset name or path")
        if name == "stats":
            p.add_argument("--write", action="store_true", help="update the table in README.md")
        p.set_defaults(fn=fn)

    validate = sub.add_parser("validate", help="containerized oracle (must pass) and nop (must fail) via Harbor")
    validate.add_argument("task", nargs="?")
    validate.add_argument("--skip-build", action="store_true")
    validate.set_defaults(fn=cmd_validate)

    build = sub.add_parser("build-image", help="build the aide-systems base image")
    build.set_defaults(fn=cmd_build_image)

    report = sub.add_parser("report", help="summarize a Harbor job directory")
    report.add_argument("job")
    report.set_defaults(fn=cmd_report)

    args = parser.parse_args()
    raise SystemExit(args.fn(args))


if __name__ == "__main__":
    main()
