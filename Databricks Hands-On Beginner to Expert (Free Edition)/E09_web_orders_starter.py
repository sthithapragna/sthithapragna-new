# Databricks notebook source
# MAGIC %md
# MAGIC # Web orders: how many, how many cancelled, and is the app worse?
# MAGIC **Asked by:** Tom Ashworth, Store Operations. September 2026, as at the 1 October delivery.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Episode 08's homework: September net sales by region

# COMMAND ----------

hw_lines = (spark.read
            .option("header", True)
            .schema(POS_SCHEMA)
            .csv(POS)
            .filter(F.col("txn_id") != "txn_id")
            .filter(~F.col("_metadata.file_name").contains("resend"))
            .withColumn("trading_date", F.to_date("txn_ts", POS_TS_FORMAT))
            .filter(F.col("trading_date").between("2026-09-01", "2026-09-30"))
            .filter(F.col("is_void") == "N"))
hw_stores = (spark.read.option("header", True)
             .csv(f"{REFERENCE}/stores/stores_2026-09-23.csv")
             .select("store_id", "region_code"))
display(hw_lines.join(hw_stores, on="store_id", how="left")
        .groupBy("region_code")
        .agg(F.countDistinct("store_id").alias("stores"),
             F.sum("line_total").alias("net_sales"))
        .orderBy(F.desc("net_sales")))

# COMMAND ----------

from pyspark.sql import functions as F, Window

# COMMAND ----------

# MAGIC %md ## 1. A declared schema for nested JSON
# MAGIC Prices are read as text on purpose: app 5.2 sends them as strings (episode 07). We cast them later.

# COMMAND ----------

ECOM_SCHEMA = """
    event_id STRING, event_type STRING, event_ts STRING, order_id STRING, order_status STRING,
    channel STRING, app_version STRING,
    customer STRUCT<loyalty_id: BIGINT, email: STRING, postcode: STRING>,
    items    ARRAY<STRUCT<sku: STRING, qty: INT, unit_price: STRING>>,
    delivery STRUCT<type: STRING, store_id: STRING, slot_start: STRING, slot_end: STRING>,
    payment  STRUCT<method: STRING, amount: DECIMAL(10,2)>
"""

# COMMAND ----------

events = (spark.read
          .schema(ECOM_SCHEMA)
          .json(ECOM)
          .filter(F.col("delivered") <= "2026-10-01")          # as at the 1 October delivery
          .withColumn("event_time", F.to_timestamp("event_ts")))
events.printSchema()

# COMMAND ----------

# MAGIC %md ## 2. Reaching inside: structs and arrays

# COMMAND ----------

display(events
        .filter(F.col("order_id") == "W2026090100014")
        .select("event_type", "event_time", "channel",
                "customer.loyalty_id", "delivery.type",
                F.size("items").alias("items"), "payment.amount")
        .orderBy("event_time"))

# COMMAND ----------

# MAGIC %md ## 3. Rows are not orders

# COMMAND ----------

print(events.count(), "rows")
print(events.select("order_id").distinct().count(), "orders")
display(events.groupBy("event_type").count().orderBy(F.desc("count")))

# COMMAND ----------

# MAGIC %md ## 4. Each order's latest event

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

# MAGIC %md ## 5. Orders and items in one go

# COMMAND ----------

order_lines = latest.select("order_id", "order_status", "channel", F.explode("items").alias("item"))
display(order_lines
        .groupBy("order_status")
        .agg(F.countDistinct("order_id").alias("orders"))
        .orderBy(F.desc("orders")))

# COMMAND ----------

display(events
        .filter(F.col("order_id") == "W2026090100559")
        .select("event_type", "event_time", F.size("items").alias("items"))
        .orderBy("event_time"))

# COMMAND ----------

# MAGIC %md ## 6. Count orders before exploding anything

# COMMAND ----------

display(latest.groupBy("order_status").count().orderBy(F.desc("count")))

# COMMAND ----------

display(latest
        .groupBy("channel")
        .agg(F.count("*").alias("orders"),
             F.sum(F.when(F.col("order_status") == "CANCELLED", 1).otherwise(0)).alias("cancelled"))
        .withColumn("cancel_rate_pct", F.round(F.col("cancelled") / F.col("orders") * 100, 2))
        .orderBy("channel"))

# COMMAND ----------

display(latest.select("order_id", "order_status", F.explode_outer("items").alias("item"))
              .groupBy("order_status")
              .agg(F.countDistinct("order_id").alias("orders"))
              .orderBy(F.desc("orders")))

# COMMAND ----------

# MAGIC %md ## 7. Items: explode the order as it was created

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

print(items.filter(F.col("unit_price").isNull()).count(), "prices failed to cast")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Tom
# MAGIC **44,711 web orders** created in September; **1,781 cancelled (3.98%)**.
# MAGIC App 4.03% (996 of 24,685), website 3.92% (785 of 20,026): **the app is not meaningfully worse.**
# MAGIC As at the 1 October delivery, 1,280 orders were picked and 903 just created, awaiting delivery.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC **Which product appeared in the most web orders placed in September, and in how many orders?**
# MAGIC
# MAGIC - Use the web order events as at the 1 October delivery (`delivered <= '2026-10-01'`), as this notebook does.
# MAGIC - Count each order once, including orders that were later cancelled.
# MAGIC - Look the product's name up in `products_2026-08-31.csv` in the reference volume (`REFERENCE` in `_config`).
# MAGIC
# MAGIC Put your answer in the comments. I'll show mine at the start of episode 10.

# COMMAND ----------

# Your answer here
