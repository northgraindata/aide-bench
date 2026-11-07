package com.acme

import org.apache.spark.sql.SparkSession

object SessionJoin {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder.appName("nightly-session-join").getOrCreate()
    val events = NormalizeEvents.load(spark, args(0))
    val customers = spark.read.parquet(args(1))
    // attach the customer segment to every event
    val joined = events.join(customers, Seq("customer_id"), "left")
    joined.groupBy("segment", "event_date").count()
      .write.mode("overwrite").parquet(args(2))
  }
}
