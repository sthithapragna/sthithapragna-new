# Databricks notebook source
# MAGIC %md
# MAGIC # Board pack: September net sales by format
# MAGIC *Handed over by a contractor on his last day. "It works. Just run it. (I ran it again after fixing a typo, all fine.)"*

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Last episode's homework: the day behind the latest day

# COMMAND ----------

DSS = f"{CATALOG}.sandbox.daily_store_sales"
skipped = (spark.table(DSS)
           .filter("trading_date <= '2026-10-02'")
           .filter("trading_date <> '2026-10-01'"))      # Grace's table if 1 October had been skipped
display(skipped.agg(F.max("trading_date").alias("latest_day"),
                    F.count("*").alias("store_days"), F.sum("net_sales").alias("net_sales")))
days = spark.sql("SELECT explode(sequence(DATE'2026-09-01', DATE'2026-10-02', INTERVAL 1 DAY)) AS trading_date")
display(days.join(skipped, "trading_date", "left_anti"))         # the gap check: 2026-10-01

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

pos = (spark.read.option("header", True).schema(POS_SCHEMA).csv(POS)
       .filter(F.col("delivered").between("2026-09-01", "2026-09-30")))          # September

stores = spark.read.option("header", True).csv(f"{REFERENCE}/stores/stores_2026-09-23.csv")

pack = (pos.join(stores, "store_id")
           .groupBy("format")
           .agg(F.sum("line_total").alias("net_sales"))
           .withColumn("month", F.lit("2026-09"))
           .orderBy(F.desc("net_sales")))
display(pack)

# COMMAND ----------

pack.write.mode("append").saveAsTable(f"{CATALOG}.sandbox.board_pack")
print("Board pack updated")
