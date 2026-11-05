"""Run a reference solution: `aide-oracle /solution/solution.yaml`.

A solution lists tool calls with ids, then an answer whose evidence refers to those ids. This
drives the exact tools an agent uses, so the trace the verifier sees is a real trace.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from .session import Session


def run(path: Path, override: dict | None = None) -> None:
    """Run the solution at `path`; `override` replaces its content (used by tests to try bad answers)."""
    solution = override if override is not None else yaml.safe_load(path.read_text())
    session = Session()
    ids: dict[str, str] = {}
    for step in solution.get("calls", []):
        result = session.call(step["tool"], step.get("args", {}))
        if "error" in result:
            print(f"oracle step {step.get('id')} returned an error: {result['error']}", file=sys.stderr)
        ids[step["id"]] = result.get("trace_id", "")
    if "patch_file" in solution:
        diff = (path.parent / solution["patch_file"]).read_text()
        result = session.call("propose_patch", {"diff": diff})
        if not result.get("applies"):
            raise SystemExit(f"oracle patch does not apply: {result}")
    answer = solution.get("answer")
    if answer:
        answer = dict(answer)
        answer["evidence"] = [ids[ref] for ref in answer.get("evidence", [])]
        result = session.submit_answer(**answer)
        if "error" in result:
            raise SystemExit(f"oracle answer rejected: {result['error']}")


def main() -> None:
    run(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
