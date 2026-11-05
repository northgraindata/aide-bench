"""lakehouse/iceberg: table metadata, schema history and snapshots."""
from __future__ import annotations

import json
from pathlib import Path

from .base import Flavor
from .registry import register


@register
class Iceberg(Flavor):
    kind = "lakehouse"
    name = "iceberg"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        (target / "tables.json").write_text(json.dumps(spec.get("tables", []), indent=2, default=str))

    def _tables(self) -> list[dict]:
        return json.loads((self.dir / "tables.json").read_text())

    def tools(self):
        def iceberg_list_tables() -> dict:
            """List Iceberg tables with their locations."""
            return {"tables": [{"name": t["name"], "location": t.get("location")} for t in self._tables()]}

        def iceberg_table_metadata(table: str) -> dict:
            """Table metadata: current schema, all schema versions and the current snapshot id."""
            found = next((t for t in self._tables() if t["name"] == table), None)
            return found and {k: v for k, v in found.items() if k != "snapshots"} or {"error": f"NoSuchTable: {table}"}

        def iceberg_list_snapshots(table: str) -> dict:
            """List snapshots of a table (commit time, operation and summary)."""
            found = next((t for t in self._tables() if t["name"] == table), None)
            return {"snapshots": found.get("snapshots", [])} if found else {"error": f"NoSuchTable: {table}"}

        return {f.__name__: f for f in (iceberg_list_tables, iceberg_table_metadata, iceberg_list_snapshots)}
