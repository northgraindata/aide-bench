"""repo/git: a repository snapshot with commit history. Optionally accepts a proposed patch."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from aide_systems.world import out_dir

from .base import Flavor
from .registry import register
from .util import clip


@register
class GitRepo(Flavor):
    kind = "repo"
    name = "git"
    fidelity = "recorded"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        files = scenario / spec.get("files", "repo")
        shutil.copytree(files, target / "files", dirs_exist_ok=True)
        history = spec.get("history", [])
        if isinstance(history, str):
            import yaml

            history = yaml.safe_load((scenario / history).read_text())
        (target / "history.json").write_text(json.dumps(history, indent=2, default=str))

    @property
    def _files(self) -> Path:
        return self.dir / "files"

    def mutating_tools(self) -> set[str]:
        return set()  # propose_patch only records a patch; it never touches the world

    def tools(self):
        def repo_list_files(prefix: str = "") -> dict:
            """List files in the repository, optionally under a path prefix."""
            paths = sorted(
                str(p.relative_to(self._files)) for p in self._files.rglob("*") if p.is_file()
            )
            return {"files": [p for p in paths if p.startswith(prefix)]}

        def repo_read_file(path: str) -> dict:
            """Read a file from the repository (HEAD), e.g. models/staging/stg_orders.sql."""
            root = self._files.resolve()
            target = (root / path).resolve()
            if root not in target.parents or not target.is_file():
                return {"error": f"No such file: {path}"}
            return {"path": path, **clip(target.read_text())}

        def repo_search(pattern: str) -> dict:
            """Search file contents with a regular expression. Returns path, line number and line."""
            try:
                rx = re.compile(pattern)
            except re.error as error:
                return {"error": f"Invalid pattern: {error}"}
            hits = []
            for p in sorted(self._files.rglob("*")):
                if not p.is_file():
                    continue
                try:
                    lines = p.read_text().splitlines()
                except UnicodeDecodeError:
                    continue
                for number, line in enumerate(lines, 1):
                    if rx.search(line):
                        hits.append({"path": str(p.relative_to(self._files)), "line": number, "text": line[:300]})
                        if len(hits) >= 100:
                            return {"matches": hits, "truncated": True}
            return {"matches": hits, "truncated": False}

        def repo_log(path: str = "", limit: int = 20) -> dict:
            """Show commit history (newest first), optionally only commits touching a path. Includes diffs."""
            history = json.loads((self.dir / "history.json").read_text())
            if path:
                history = [c for c in history if any(f.startswith(path) for f in c.get("files", []))]
            return {"commits": history[:limit]}

        tools = {f.__name__: f for f in (repo_list_files, repo_read_file, repo_search, repo_log)}

        if self.spec.get("writable"):

            def propose_patch(diff: str) -> dict:
                """Propose a fix as a unified diff (git format) against the repository HEAD.

                The patch is validated and recorded; nothing is applied to any live system.
                Call it again to replace an earlier proposal.
                """
                with tempfile.TemporaryDirectory() as scratch:
                    shutil.copytree(self._files, scratch, dirs_exist_ok=True)
                    check = subprocess.run(
                        ["git", "apply", "--check", "-"], input=diff, text=True, cwd=scratch, capture_output=True
                    )
                if check.returncode != 0:
                    return {"applies": False, "error": check.stderr.strip()[:1000]}
                out = out_dir()
                out.mkdir(parents=True, exist_ok=True)
                (out / "patch.diff").write_text(diff)
                changed = re.findall(r"^\+\+\+ b/(.+)$", diff, flags=re.M)
                return {"applies": True, "files": changed}

            tools["propose_patch"] = propose_patch
        return tools
