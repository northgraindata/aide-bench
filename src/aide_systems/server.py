"""stdio MCP server exposing the task's systems to an agent."""
from __future__ import annotations

import functools

from mcp.server.fastmcp import FastMCP

from .session import Session
from .taxonomy import CATEGORIES

mcp = FastMCP("aide-systems")
session = Session()


def _register(name: str, fn) -> None:
    @functools.wraps(fn)
    def wrapper(**kwargs):
        return session.call(name, kwargs)

    mcp.add_tool(wrapper, name=name, description=fn.__doc__ or name)


for _name, (_system, _flavor, _fn, _mutating) in session.tools.items():
    _register(_name, _fn)

_CATEGORY_HELP = "; ".join(f"{k}: {v}" for k, v in CATEGORIES.items())
_SUBMIT_DOC = (
    "Submit the final diagnosis. Call it once, when you are done.\n\n"
    "categories: one or more of the categories below.\n"
    "root_cause: a short explanation of the cause in your own words.\n"
    "affected: names of the tables, models, jobs or files affected.\n"
    "verdict: 'supported' when the evidence establishes the cause, 'inconclusive' when it does not.\n"
    "confidence: 0 to 1.\n"
    "evidence: trace_id values returned by the tool calls that support your claim.\n\n"
    "Categories: " + _CATEGORY_HELP
)


@mcp.tool(description=_SUBMIT_DOC)
def submit_answer(
    categories: list[str],
    root_cause: str,
    affected: list[str],
    verdict: str,
    confidence: float,
    evidence: list[str],
) -> dict:
    return session.submit_answer(categories, root_cause, affected, verdict, confidence, evidence)



def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
