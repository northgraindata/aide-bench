package com.acme

import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._

object SalesDaily {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder.appName("sales-daily").getOrCreate()
    val sales = spark.read.parquet(args(0))
      .na.fill(0, Seq("amount"))
    sales.groupBy("store_id").agg(sum("amount").as("revenue"))
      .write.mode("overwrite").parquet(args(1))
  }
}
