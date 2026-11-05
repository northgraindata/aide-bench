"""docs/markdown: team runbooks and documentation the agent may consult."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .base import Flavor
from .registry import register
from .util import clip


@register
class Docs(Flavor):
    kind = "docs"
    name = "markdown"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(scenario / spec.get("dir", "docs"), target / "files", dirs_exist_ok=True)

    def tools(self):
        root = self.dir / "files"

        def docs_list() -> dict:
            """List documentation and runbook pages."""
            return {"pages": sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())}

        def docs_read(path: str) -> dict:
            """Read a documentation page."""
            target = (root / path).resolve()
            if root.resolve() not in target.parents or not target.is_file():
                return {"error": f"No such page: {path}"}
            return {"path": path, **clip(target.read_text())}

        def docs_search(query: str) -> dict:
            """Case-insensitive text search across pages."""
            rx = re.compile(re.escape(query), re.I)
            hits = []
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    for number, line in enumerate(p.read_text().splitlines(), 1):
                        if rx.search(line):
                            hits.append({"path": str(p.relative_to(root)), "line": number, "text": line[:300]})
            return {"matches": hits[:50]}

        return {f.__name__: f for f in (docs_list, docs_read, docs_search)}
