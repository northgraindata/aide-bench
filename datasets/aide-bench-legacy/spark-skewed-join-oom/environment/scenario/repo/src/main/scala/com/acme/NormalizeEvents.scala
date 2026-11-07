package com.acme

import org.apache.spark.sql.{DataFrame, SparkSession}
import org.apache.spark.sql.functions._

object NormalizeEvents {
  def load(spark: SparkSession, path: String): DataFrame =
    spark.read.parquet(path)
      .withColumn("customer_id", coalesce(col("customer_id"), lit("ANON")))
      .withColumn("event_date", to_date(col("event_ts")))
}
