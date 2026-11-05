"""The tools an agent can call, with a trace of every call.

The same Session backs the MCP server and the oracle CLI, so a reference solution produces
a trace through exactly the code path a real agent uses.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Callable

from .flavors import get
from .taxonomy import CATEGORIES, VERDICTS
from .world import out_dir, read_manifest, world_dir

RESULT_LIMIT = 30000


class Session:
    def __init__(self) -> None:
        self.out = out_dir()
        self.out.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.out / "trace.jsonl"
        self.tools: dict[str, tuple[str, str, Callable, bool]] = {}
        for system in read_manifest()["systems"]:
            flavor = get(system["kind"], system["flavor"])(world_dir(), system.get("spec", {}))
            mutating = flavor.mutating_tools()
            for name, fn in flavor.tools().items():
                self.tools[name] = (system["kind"], system["flavor"], fn, name in mutating)

    # -- tracing ------------------------------------------------------------
    def _record(self, tool: str, system: str, flavor: str, args: dict, result: object, mutating: bool) -> str:
        trace_id = uuid.uuid4().hex[:12]
        with self.trace_path.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "trace_id": trace_id,
                        "ts": time.time(),
                        "tool": tool,
                        "system": system,
                        "flavor": flavor,
                        "args": args,
                        "result": json.dumps(result, default=str)[:RESULT_LIMIT],
                        "mutating": mutating,
                    }
                )
                + "\n"
            )
        return trace_id

    def call(self, tool: str, args: dict) -> dict:
        if tool == "submit_answer":
            return self.submit_answer(**args)
        if tool not in self.tools:
            return {"error": f"Unknown tool: {tool}"}
        system, flavor, fn, mutating = self.tools[tool]
        try:
            result = fn(**args)
        except TypeError as error:
            result = {"error": f"Invalid arguments: {error}"}
        result = dict(result)
        result["trace_id"] = self._record(tool, system, flavor, args, result, mutating)
        return result

    # -- answer -------------------------------------------------------------
    def submit_answer(
        self,
        categories: list[str],
        root_cause: str,
        affected: list[str],
        verdict: str,
        confidence: float,
        evidence: list[str],
    ) -> dict:
        unknown = [c for c in categories if c not in CATEGORIES]
        if unknown or not categories:
            return {"error": f"categories must be non-empty and from {sorted(CATEGORIES)}; got {unknown or categories}"}
        if verdict not in VERDICTS:
            return {"error": f"verdict must be one of {VERDICTS}"}
        if not 0 <= confidence <= 1:
            return {"error": "confidence must be between 0 and 1"}
        answer = {
            "categories": categories,
            "root_cause": root_cause,
            "affected": affected,
            "verdict": verdict,
            "confidence": confidence,
            "evidence": evidence,
        }
        (self.out / "answer.json").write_text(json.dumps(answer, indent=2))
        self._record("submit_answer", "harness", "harness", answer, {"ok": True}, False)
        return {"ok": True}
