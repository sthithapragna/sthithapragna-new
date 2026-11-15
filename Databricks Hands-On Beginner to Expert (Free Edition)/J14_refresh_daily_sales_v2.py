# Databricks notebook source
# MAGIC %md
# MAGIC # Job: refresh Grace's daily sales (catches up)
# MAGIC Run by the job **Refresh daily store sales**. Refreshes one trading day in
# MAGIC `kestrel.sandbox.daily_store_sales`, safely (episode 10's replaceWhere).

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from pyspark.sql import functions as F

TABLE = f"{CATALOG}.sandbox.daily_store_sales"

def daily_sales(start, end):
    lines = (spark.read.option("header", True).schema(POS_SCHEMA).csv(POS)
             .filter(F.col("txn_id") != "txn_id")
             .filter(~F.col("_metadata.file_name").contains("resend"))
             .withColumn("trading_date", F.to_date("txn_ts", POS_TS_FORMAT))
             .filter(F.col("trading_date").between(start, end))
             .filter(F.col("is_void") == "N"))
    stores = (spark.read.option("header", True)
              .csv(f"{REFERENCE}/stores/stores_2026-09-23.csv")
              .select("store_id", "store_name", "format"))
    return (lines.join(stores, on="store_id", how="left")
                 .groupBy("trading_date", "store_id", "store_name", "format")
                 .agg(F.countDistinct("txn_id").alias("baskets"),
                      F.sum("line_total").alias("net_sales")))

def refresh(day_str):
    day = daily_sales(day_str, day_str)
    if day.isEmpty():
        raise ValueError(f"No till data for {day_str}. Refusing to write: replaceWhere would delete the day.")
    (day.write.mode("overwrite")
        .option("replaceWhere", f"trading_date = '{day_str}'")
        .saveAsTable(TABLE))
    print(f"Refreshed {day_str}")

# COMMAND ----------

import json
from datetime import date, timedelta

dbutils.widgets.text("trading_date", "latest")
requested = dbutils.widgets.get("trading_date").strip()

if requested == "latest":
    # Every day after the table's last day, up to the latest day the simulator has delivered.
    with open(f"/Volumes/{CATALOG}/ops/sim/state.json") as f:
        latest = date.fromisoformat(json.load(f)["last_delivery"]) - timedelta(days=1)
    have = spark.table(TABLE).agg(F.max("trading_date")).first()[0]
    days = [str(have + timedelta(days=n)) for n in range(1, (latest - have).days + 1)]
else:
    days = [requested]

if not days:
    print("Already up to date: nothing to refresh.")
for d in days:
    refresh(d)
