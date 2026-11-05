"""fixture/recorded: declare tools whose responses are matched from the call input.

For systems that have no dedicated flavor. Each tool takes a free-form `input` string and
returns the first response whose `match` regex matches it (an empty match matches anything).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .base import Flavor
from .registry import register


@register
class Fixture(Flavor):
    kind = "fixture"
    name = "recorded"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        (target / "tools.json").write_text(json.dumps(spec.get("tools", []), indent=2, default=str))

    def tools(self):
        out = {}
        for spec in json.loads((self.dir / "tools.json").read_text()):

            def make(spec=spec):
                def fixture_tool(input: str = "") -> dict:
                    for response in spec.get("responses", []):
                        if re.search(response.get("match", ""), input):
                            return response["response"]
                    return {"error": "No recorded response for this input"}

                fixture_tool.__name__ = spec["name"]
                fixture_tool.__doc__ = spec.get("description", spec["name"])
                return fixture_tool

            out[spec["name"]] = make()
        return out
