"""warehouse/duckdb: a real DuckDB engine over a frozen database file."""
from __future__ import annotations

from pathlib import Path

import duckdb

from .base import Flavor, read_text_ref
from .registry import register

MAX_ROWS = 200


@register
class DuckDBWarehouse(Flavor):
    kind = "warehouse"
    name = "duckdb"
    fidelity = "engine"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(target / "warehouse.duckdb"))
        try:
            for statement in spec.get("sql", []):
                con.execute(statement)
            for file in spec.get("sql_files", []):
                con.execute(read_text_ref(scenario, None, file))
        finally:
            con.close()

    def _connect(self):
        return duckdb.connect(str(self.dir / "warehouse.duckdb"), read_only=True)

    def tools(self):
        def warehouse_list_tables() -> dict:
            """List tables and views in the warehouse."""
            con = self._connect()
            try:
                rows = con.execute(
                    "select table_schema, table_name, table_type from information_schema.tables "
                    "where table_schema not in ('information_schema','pg_catalog') order by 1,2"
                ).fetchall()
            finally:
                con.close()
            return {"tables": [{"schema": s, "table": t, "type": k} for s, t, k in rows]}

        def warehouse_describe_table(table: str) -> dict:
            """Describe the columns of a table."""
            con = self._connect()
            try:
                rows = con.execute(
                    "select column_name, data_type, is_nullable from information_schema.columns "
                    "where table_name = ? order by ordinal_position",
                    [table],
                ).fetchall()
            finally:
                con.close()
            if not rows:
                return {"error": f"Table not found: {table}"}
            return {"table": table, "columns": [{"name": n, "type": t, "nullable": v == "YES"} for n, t, v in rows]}

        def warehouse_query(sql: str) -> dict:
            """Run a read-only SQL query (DuckDB dialect). At most 200 rows are returned."""
            con = self._connect()
            try:
                cursor = con.execute(sql)
                columns = [c[0] for c in cursor.description or []]
                rows = cursor.fetchmany(MAX_ROWS + 1)
                return {
                    "columns": columns,
                    "rows": [list(r) for r in rows[:MAX_ROWS]],
                    "truncated": len(rows) > MAX_ROWS,
                }
            except Exception as error:  # surfaced to the agent like a real warehouse error
                return {"error": str(error)}
            finally:
                con.close()

        return {f.__name__: f for f in (warehouse_list_tables, warehouse_describe_table, warehouse_query)}
