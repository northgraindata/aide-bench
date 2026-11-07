# both jobs read and write customers_gold
merge_customer_updates = DAG("merge_customer_updates", schedule="0 2 * * *")
rebuild_segments = DAG("rebuild_segments", schedule="0 2 * * *")
