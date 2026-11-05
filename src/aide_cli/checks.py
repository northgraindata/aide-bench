"""Static and offline checks for a task: `aide lint` and `aide check`."""
from __future__ import annotations

import filecmp
import json
import os
import shutil
import tempfile
from pathlib import Path

import yaml
from pydantic import ValidationError

from aide_grade.runner import grade
from aide_grade.schema import load_ground_truth
from aide_systems.build import build_world
from aide_systems.taxonomy import CATEGORIES

from .tasks import Task
from .templates import GENERATED, ORG

DIFFICULTIES = {"easy", "medium", "hard"}
SPLITS = {"dev", "test"}
REQUIRED_METADATA = ("difficulty", "track", "split", "tags", "expert_time_estimate_min", "junior_time_estimate_min")


def lint(task: Task) -> list[str]:
    problems: list[str] = []
    add = problems.append
    try:
        toml = task.toml
    except Exception as error:
        return [f"task.toml does not parse: {error}"]
    meta = task.metadata
    if toml.get("task", {}).get("name") != f"{ORG}/{task.id}":
        add(f"task.name must be {ORG}/{task.id}")
    for key in REQUIRED_METADATA:
        if key not in meta:
            add(f"metadata.{key} is missing")
    if meta.get("difficulty") not in DIFFICULTIES:
        add(f"metadata.difficulty must be one of {sorted(DIFFICULTIES)}")
    if meta.get("split") not in SPLITS:
        add(f"metadata.split must be one of {sorted(SPLITS)}")
    for key in ("expert_time_estimate_min", "junior_time_estimate_min"):
        if not meta.get(key, 0) > 0:
            add(f"metadata.{key} must be positive (set a real estimate)")
    description = toml.get("task", {}).get("description", "")
    if not description or "TODO" in description:
        add("task.description must be a real one-sentence summary")
    if len(meta.get("tags", [])) < 2:
        add("metadata.tags needs at least two tags")
    if toml.get("verifier", {}).get("environment_mode") != "separate":
        add("verifier.environment_mode must be 'separate' so the agent cannot reach the tests")
    servers = toml.get("environment", {}).get("mcp_servers", [])
    if not any(s.get("command") == "python" and s.get("args") == ["-m", "aide_systems.server"] for s in servers):
        add("environment.mcp_servers must register the aide_systems MCP server")
    artifacts = toml.get("artifacts", [])
    if "/app/aide-out/trace.jsonl" not in artifacts:
        add("artifacts must include /app/aide-out/trace.jsonl")

    for relative, content in GENERATED.items():
        file = task.path / relative
        if not file.exists():
            add(f"{relative} is missing (run `aide sync`)")
        elif file.read_text() != content:
            add(f"{relative} differs from the template (run `aide sync`)")

    for relative in ("task.toml", "instruction.md", "tests/ground_truth.yaml", "solution/solution.yaml", *GENERATED):
        file = task.path / relative
        if file.exists() and "aide-bench canary GUID" not in file.read_text(errors="ignore"):
            add(f"{relative} has no canary string")

    if not (task.path / "instruction.md").exists():
        add("instruction.md is missing")

    try:
        truth = load_ground_truth(task.tests_dir / "ground_truth.yaml")
    except (ValidationError, FileNotFoundError, yaml.YAMLError) as error:
        add(f"tests/ground_truth.yaml invalid: {error}")
        return problems
    if truth.track != meta.get("track"):
        add(f"ground_truth.track ({truth.track}) != metadata.track ({meta.get('track')})")
    if any(c not in CATEGORIES for c in truth.categories):
        add("ground truth uses a category outside the taxonomy")

    if truth.track == "fix":
        base, repo = task.tests_dir / "base", task.scenario_dir / "repo"
        if not base.is_dir():
            add("fix tasks need tests/base (run `aide sync`)")
        elif not _same_tree(base, repo):
            add("tests/base differs from environment/scenario/repo (run `aide sync`)")
        if not (task.path / "solution" / "fix.patch").exists():
            add("fix tasks need solution/fix.patch")
    return problems


def _same_tree(a: Path, b: Path) -> bool:
    comparison = filecmp.dircmp(a, b)
    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, comparison.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(_same_tree(a / d, b / d) for d in comparison.common_dirs)


def trial(task: Task, solution: dict | None = None) -> dict[str, float]:
    """Grade one offline trial. `solution` is the agent's behavior; None means a do-nothing agent."""
    from aide_systems.oracle import run as run_oracle

    with tempfile.TemporaryDirectory() as scratch:
        world, out = Path(scratch) / "world", Path(scratch) / "out"
        previous = {k: os.environ.get(k) for k in ("AIDE_WORLD_DIR", "AIDE_OUT_DIR")}
        os.environ["AIDE_WORLD_DIR"], os.environ["AIDE_OUT_DIR"] = str(world), str(out)
        try:
            build_world(task.scenario_dir, world)
            out.mkdir()
            if solution is not None:
                run_oracle(task.path / "solution" / "solution.yaml", solution)
            return grade(task.tests_dir, out)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def offline(task: Task) -> dict[str, dict[str, float] | str]:
    """Run the reference solution and a do-nothing agent against the real graders, without containers."""
    from aide_systems.oracle import run as run_oracle

    results: dict[str, dict[str, float] | str] = {}
    for label in ("oracle", "nop"):
        with tempfile.TemporaryDirectory() as scratch:
            world, out = Path(scratch) / "world", Path(scratch) / "out"
            previous = {k: os.environ.get(k) for k in ("AIDE_WORLD_DIR", "AIDE_OUT_DIR")}
            os.environ["AIDE_WORLD_DIR"], os.environ["AIDE_OUT_DIR"] = str(world), str(out)
            try:
                build_world(task.scenario_dir, world)
                out.mkdir()
                if label == "oracle":
                    run_oracle(task.path / "solution" / "solution.yaml")
                results[label] = grade(task.tests_dir, out)
            except BaseException as error:  # report any authoring mistake as a result, not a crash
                results[label] = f"{type(error).__name__}: {str(error)[:300]}"
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
    return results


def offline_problems(task: Task) -> list[str]:
    results = offline(task)
    problems = []
    oracle, nop = results["oracle"], results["nop"]
    if isinstance(oracle, str):
        problems.append(f"oracle failed to run: {oracle}")
    elif oracle["reward"] != 1.0:
        problems.append(f"oracle must score 1.0, got {json.dumps(oracle)}")
    if isinstance(nop, str):
        problems.append(f"nop failed to run: {nop}")
    elif nop["reward"] != 0.0:
        problems.append(f"nop must score 0.0, got {json.dumps(nop)}")
    return problems
