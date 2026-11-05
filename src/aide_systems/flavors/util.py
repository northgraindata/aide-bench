from __future__ import annotations

TEXT_LIMIT = 20000


def clip(text: str, limit: int = TEXT_LIMIT) -> dict:
    """Return text and a flag saying whether it was cut, so agents know evidence is partial."""
    if len(text) <= limit:
        return {"content": text, "truncated": False}
    return {"content": text[:limit], "truncated": True, "total_chars": len(text)}
