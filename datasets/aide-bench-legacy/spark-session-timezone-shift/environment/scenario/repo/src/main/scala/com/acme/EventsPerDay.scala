package com.acme

import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._

object EventsPerDay {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder.appName("events-per-day").getOrCreate()
    spark.read.parquet(args(0))
      .withColumn("event_date", to_date(col("event_ts")))   // event_ts is stored in UTC
      .groupBy("event_date").count()
      .write.mode("overwrite").parquet(args(1))
  }
}
