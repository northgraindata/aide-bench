"""Run the models in order against data/raw_orders.csv and write out/warehouse.duckdb."""
import pathlib
import duckdb

root = pathlib.Path(__file__).parent
out = root / "out"
out.mkdir(exist_ok=True)
db = out / "warehouse.duckdb"
db.unlink(missing_ok=True)
con = duckdb.connect(str(db))
con.execute(f"create table raw_orders as select * from read_csv_auto('{root / 'data' / 'raw_orders.csv'}')")
for name, path in (("stg_orders", "models/staging/stg_orders.sql"), ("daily_revenue", "models/marts/daily_revenue.sql")):
    con.execute(f"create table {name} as {(root / path).read_text()}")
con.close()
