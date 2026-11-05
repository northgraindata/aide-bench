"""Command line access to the tools, for solutions, debugging and adapters. Not for agents.

    aide-call <tool> '<json args>'   call a tool (traced like any agent call)
    aide-call --catalog              list tools with kind, flavor, mutating flag and JSON schema (not traced)
    aide-call --repo-files           dump the repository snapshot as {path: content} (not traced)

The last two exist so that adapters for agents with their own tool model can mirror the world
without adding noise to the trace.
"""
from __future__ import annotations

import asyncio
import json
import sys


def catalog() -> list[dict]:
    from .server import mcp, session

    schemas = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    out = []
    for name, (system, flavor, _fn, mutating) in sorted(session.tools.items()):
        tool = schemas.get(name)
        out.append(
            {
                "name": name,
                "kind": system,
                "flavor": flavor,
                "mutating": mutating,
                "description": tool.description if tool else name,
                "inputSchema": tool.inputSchema if tool else {"type": "object"},
            }
        )
    return out


def repo_files() -> dict[str, str]:
    from .world import world_dir

    root = world_dir() / "git" / "files"
    if not root.is_dir():
        return {}
    return {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob("*")) if p.is_file()}


def main() -> None:
    if sys.argv[1:2] == ["--catalog"]:
        print(json.dumps(catalog()))
    elif sys.argv[1:2] == ["--repo-files"]:
        print(json.dumps(repo_files()))
    else:
        from .session import Session

        tool = sys.argv[1]
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        print(json.dumps(Session().call(tool, args), default=str))


if __name__ == "__main__":
    main()
