package com.acme

import org.apache.spark.sql.SparkSession

object Clickstream {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder.appName("etl_clickstream").getOrCreate()
    spark.read.parquet(args(0)).select("user_id", "page", "ts").write.mode("overwrite").parquet(args(1))
  }
}
