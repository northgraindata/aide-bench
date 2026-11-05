"""Locations and manifest of a frozen world."""
from __future__ import annotations

import json
import os
from pathlib import Path


def world_dir() -> Path:
    return Path(os.environ.get("AIDE_WORLD_DIR", "/app/world"))


def out_dir() -> Path:
    return Path(os.environ.get("AIDE_OUT_DIR", "/app/aide-out"))


def read_manifest() -> dict:
    return json.loads((world_dir() / "world.json").read_text())
