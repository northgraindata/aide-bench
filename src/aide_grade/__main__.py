"""Verifier entrypoint: `python -m aide_grade`. Reads artifacts, writes /logs/verifier/reward.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .runner import grade

OUT = Path(os.environ.get("AIDE_OUT_DIR", "/app/aide-out"))
TESTS = Path(os.environ.get("AIDE_TESTS_DIR", "/tests"))
REWARD = Path(os.environ.get("AIDE_REWARD_PATH", "/logs/verifier/reward.json"))


def main() -> None:
    reward = grade(TESTS, OUT)
    REWARD.parent.mkdir(parents=True, exist_ok=True)
    REWARD.write_text(json.dumps(reward, indent=2))
    print(json.dumps(reward, indent=2))


if __name__ == "__main__":
    main()
