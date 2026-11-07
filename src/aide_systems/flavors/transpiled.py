"""Cloud warehouses emulated by translating their SQL dialect onto DuckDB, plus Delta table history.

The data lives in a real DuckDB file. Queries are translated with sqlglot from the product's
dialect, so an agent can write Snowflake, BigQuery or Spark SQL. Product metadata that DuckDB has
no equivalent for (query history, job history, Delta history) is served from recorded fixtures.
This is a translation, not the product: dialect quirks beyond what sqlglot maps will differ.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import sqlglot

from .base import Flavor, read_text_ref
from .registry import register
from .util import clip

MAX_ROWS = 200


class TranspiledWarehouse(Flavor):
    kind = "warehouse"
    fidelity = "transpiled"
    dialect = ""

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
        (target / "history.json").write_text(json.dumps(spec.get("query_history", []), indent=2, default=str))

    def _connect(self):
        return duckdb.connect(str(self.dir / "warehouse.duckdb"), read_only=True)

    def _translate(self, sql: str) -> str:
        statements = sqlglot.transpile(sql, read=self.dialect, write="duckdb")
        if len(statements) != 1:
            raise ValueError("send one statement at a time")
        return statements[0]

    def _query(self, sql: str) -> dict:
        try:
            translated = self._translate(sql)
        except Exception as error:
            return {"error": f"SQL compilation error: {error}"}
        con = self._connect()
        try:
            cursor = con.execute(translated)
            columns = [c[0] for c in cursor.description or []]
            rows = cursor.fetchmany(MAX_ROWS + 1)
            return {"columns": columns, "rows": [list(r) for r in rows[:MAX_ROWS]], "truncated": len(rows) > MAX_ROWS}
        except Exception as error:
            return {"error": str(error)}
        finally:
            con.close()

    def _tables(self) -> dict:
        con = self._connect()
        try:
            rows = con.execute(
                "select table_schema, table_name, table_type from information_schema.tables "
                "where table_schema not in ('information_schema','pg_catalog') order by 1,2"
            ).fetchall()
        finally:
            con.close()
        return {"tables": [{"schema": s, "table": t, "type": k} for s, t, k in rows]}

    def _describe(self, table: str) -> dict:
        con = self._connect()
        try:
            rows = con.execute(
                "select column_name, data_type, is_nullable from information_schema.columns where lower(table_name) = lower(?) order by ordinal_position",
                [table.split(".")[-1]],
            ).fetchall()
        finally:
            con.close()
        if not rows:
            return {"error": f"Object does not exist or not authorized: {table}"}
        return {"table": table, "columns": [{"name": n, "type": t, "nullable": v == "YES"} for n, t, v in rows]}

    def _history(self, limit: int, status: str | None) -> dict:
        history = json.loads((self.dir / "history.json").read_text())
        if status:
            history = [h for h in history if str(h.get("status", "")).lower() == status.lower()]
        return {"queries": history[:limit]}


@register
class Snowflake(TranspiledWarehouse):
    name = "snowflake"
    dialect = "snowflake"

    def tools(self):
        def snowflake_query(sql: str) -> dict:
            """Run one read-only SQL statement in the Snowflake dialect (translated onto DuckDB). At most 200 rows are returned."""
            return self._query(sql)

        def snowflake_list_tables() -> dict:
            """List tables and views."""
            return self._tables()

        def snowflake_describe_table(table: str) -> dict:
            """Describe the columns of a table."""
            return self._describe(table)

        def snowflake_query_history(limit: int = 50, status: str = "") -> dict:
            """Read ACCOUNT_USAGE.QUERY_HISTORY: user, role, warehouse, seconds, bytes scanned, credits, status and error."""
            return self._history(limit, status or None)

        return {f.__name__: f for f in (snowflake_query, snowflake_list_tables, snowflake_describe_table, snowflake_query_history)}


@register
class BigQuery(TranspiledWarehouse):
    name = "bigquery"
    dialect = "bigquery"

    def tools(self):
        def bigquery_query(sql: str) -> dict:
            """Run one read-only GoogleSQL statement (translated onto DuckDB). At most 200 rows are returned."""
            return self._query(sql)

        def bigquery_list_tables() -> dict:
            """List tables and views of the dataset."""
            return self._tables()

        def bigquery_describe_table(table: str) -> dict:
            """Describe the schema of a table."""
            return self._describe(table)

        def bigquery_list_jobs(limit: int = 50, status: str = "") -> dict:
            """Read INFORMATION_SCHEMA.JOBS: user, statement, bytes processed, status and error."""
            return self._history(limit, status or None)

        return {f.__name__: f for f in (bigquery_query, bigquery_list_tables, bigquery_describe_table, bigquery_list_jobs)}


@register
class DatabricksSql(TranspiledWarehouse):
    name = "databricks-sql"
    dialect = "databricks"

    def tools(self):
        def databricks_sql_query(sql: str) -> dict:
            """Run one read-only Databricks SQL statement (translated onto DuckDB). At most 200 rows are returned."""
            return self._query(sql)

        def databricks_sql_list_tables() -> dict:
            """List tables and views."""
            return self._tables()

        def databricks_sql_describe_table(table: str) -> dict:
            """Describe the columns of a table."""
            return self._describe(table)

        def databricks_sql_query_history(limit: int = 50, status: str = "") -> dict:
            """Read the SQL warehouse query history: user, statement, duration and status."""
            return self._history(limit, status or None)

        return {f.__name__: f for f in (databricks_sql_query, databricks_sql_list_tables, databricks_sql_describe_table, databricks_sql_query_history)}


@register
class Delta(Flavor):
    """lakehouse/delta: DESCRIBE HISTORY and commit files of Delta tables."""

    kind = "lakehouse"
    name = "delta"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        (target / "tables.json").write_text(json.dumps(spec.get("tables", {}), indent=2, default=str))

    def _tables(self) -> dict:
        return json.loads((self.dir / "tables.json").read_text())

    def tools(self):
        def delta_describe_history(table: str, limit: int = 30) -> dict:
            """DESCRIBE HISTORY: version, timestamp, user, operation, parameters and metrics, newest first."""
            entry = self._tables().get(table)
            if entry is None:
                return {"error": f"Table not found: {table}"}
            return {"table": table, "history": sorted(entry.get("history", []), key=lambda h: -h["version"])[:limit]}

        def delta_describe_detail(table: str) -> dict:
            """DESCRIBE DETAIL: location, partition columns, number of files, size and table properties."""
            entry = self._tables().get(table)
            if entry is None:
                return {"error": f"Table not found: {table}"}
            return {"table": table, **entry.get("detail", {})}

        def delta_read_commit(table: str, version: int) -> dict:
            """Read the add/remove actions of one commit in the transaction log."""
            entry = self._tables().get(table)
            commit = (entry or {}).get("commits", {}).get(str(version))
            if commit is None:
                return {"error": f"No commit {version} for {table}"}
            return clip(commit if isinstance(commit, str) else json.dumps(commit, indent=2))

        return {f.__name__: f for f in (delta_describe_history, delta_describe_detail, delta_read_commit)}
