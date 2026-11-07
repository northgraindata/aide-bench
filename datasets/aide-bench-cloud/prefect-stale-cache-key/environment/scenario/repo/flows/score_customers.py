from datetime import timedelta

from prefect import flow, task
from prefect.tasks import task_input_hash


@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=7))
def extract_features(table: str, date: str | None = None):
    # reads the feature table for the run date
    ...


@task
def score(features):
    ...


@flow
def score_customers(date: str):
    features = extract_features("features.customers")
    score(features)
