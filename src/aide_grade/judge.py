"""Optional LLM judge for atomic facts. Disabled unless AIDE_JUDGE=1 and an API key are present.

The judge only decides which ground-truth facts the root cause states. It never sees
categories, verdicts or evidence, and it answers with JSON so the result is machine-checked.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

from .schema import Fact

DEFAULT_MODEL = "claude-haiku-5-5"
API_URL = "https://api.anthropic.com/v1/messages"

Transport = Callable[[dict, dict], dict]


def _post(payload: dict, headers: dict) -> dict:
    request = urllib.request.Request(API_URL, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https URL
        return json.loads(response.read())


def enabled() -> bool:
    return os.environ.get("AIDE_JUDGE") == "1" and bool(os.environ.get("ANTHROPIC_API_KEY"))


def judge_facts(root_cause: str, facts: list[Fact], votes: int = 3, transport: Transport = _post) -> dict[str, bool]:
    """Return {fact_id: stated}, by majority over `votes` independent judgements."""
    listing = "\n".join(f"- {f.id}: {f.statement}" for f in facts)
    prompt = (
        "You grade a data incident diagnosis. For each fact below decide whether the diagnosis "
        "states it, explicitly or by clear implication. Be strict: a vague mention does not count.\n\n"
        f"Diagnosis:\n{root_cause}\n\nFacts:\n{listing}\n\n"
        'Reply with JSON only: {"<fact id>": true|false, ...}'
    )
    headers = {
        "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": os.environ.get("AIDE_JUDGE_MODEL", DEFAULT_MODEL),
        "max_tokens": 400,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    tally = {f.id: 0 for f in facts}
    for _ in range(votes):
        text = transport(payload, headers)["content"][0]["text"]
        verdict = json.loads(text[text.index("{") : text.rindex("}") + 1])
        for fact in facts:
            tally[fact.id] += bool(verdict.get(fact.id))
    return {fid: count * 2 > votes for fid, count in tally.items()}
