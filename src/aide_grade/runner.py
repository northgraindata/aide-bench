"""Grade one trial directory. Shared by the verifier entrypoint and by `aide check`."""
from __future__ import annotations

import json
from pathlib import Path

from . import judge
from .diagnose import grade_diagnose
from .fix import grade_fix
from .schema import load_ground_truth


def grade(tests: Path, out: Path) -> dict[str, float]:
    truth = load_ground_truth(tests / "ground_truth.yaml")
    trace_path, answer_path, patch_path = out / "trace.jsonl", out / "answer.json", out / "patch.diff"
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    answer = json.loads(answer_path.read_text()) if answer_path.exists() else None
    if truth.track == "fix":
        return grade_fix(truth, patch_path.read_text() if patch_path.exists() else None, tests, trace)
    hits = None
    if answer and truth.facts and judge.enabled():
        try:
            hits = judge.judge_facts(answer.get("root_cause", ""), truth.facts)
        except Exception as error:  # a judge outage must not silently change scores
            print(f"judge failed, falling back to patterns: {error}")
    return grade_diagnose(truth, answer, trace, hits)
