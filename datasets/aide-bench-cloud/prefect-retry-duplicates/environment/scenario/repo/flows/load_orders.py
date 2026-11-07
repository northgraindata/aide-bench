from prefect import flow, task


@task(retries=1, retry_delay_seconds=30)
def load_orders_fact(date: str):
    rows = extract_orders(date)
    insert_into("orders_fact", rows)          # plain insert
    write_audit("orders_fact", date, len(rows))


@task
def publish_daily(date: str):
    refresh("daily_orders", date)


@flow
def load_orders(date: str):
    load_orders_fact(date)
    publish_daily(date)
