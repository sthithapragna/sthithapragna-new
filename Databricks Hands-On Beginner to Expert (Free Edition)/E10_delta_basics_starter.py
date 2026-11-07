# Databricks notebook source
# MAGIC %md
# MAGIC # Daily sales as a Delta table
# MAGIC **Asked by:** Grace Liu, Finance. Keep daily net sales by store in a table her team can query,
# MAGIC updated every morning with yesterday's trading.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Last episode's homework: the most-ordered product

# COMMAND ----------

created_items = (spark.read
                 .schema("event_type STRING, order_id STRING, items ARRAY<STRUCT<sku: STRING, qty: INT>>")
                 .json(ECOM)
                 .filter(F.col("delivered") <= "2026-10-01")
                 .filter(F.col("event_type") == "CREATED")          # the basket as it was created
                 .select("order_id", F.explode("items").alias("item")))
products = (spark.read.option("header", True)
            .csv(f"{REFERENCE}/products/products_2026-08-31.csv")
            .select("sku", "product_name"))
display(created_items
        .groupBy(F.col("item.sku").alias("sku"))
        .agg(F.countDistinct("order_id").alias("orders"), F.sum("item.qty").alias("units"))
        .join(products, "sku")
        .orderBy(F.desc("orders"))
        .limit(3))

# COMMAND ----------

from pyspark.sql import functions as F

TABLE = f"{CATALOG}.sandbox.daily_store_sales"

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS kestrel.sandbox
# MAGIC COMMENT 'Season 1 practice tables. The real pipeline starts in Season 2.'

# COMMAND ----------

# MAGIC %md ## 1. Episode 08's logic, as a function
# MAGIC A function that returns a DataFrame for any date range. No shared view names (episode 06).

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md ## 2. Create the table: 1 to 29 September

# COMMAND ----------

daily_sales("2026-09-01", "2026-09-29").write.mode("overwrite").saveAsTable(TABLE)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE DETAIL kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %md ## 3. The morning job: append yesterday

# COMMAND ----------

day = daily_sales("2026-09-30", "2026-09-30")
day.write.mode("append").saveAsTable(TABLE)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %md ## 4. The job is retried

# COMMAND ----------

day.write.mode("append").saveAsTable(TABLE)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %sql
# MAGIC -- The grain is one row per store per day. Any day where that breaks?
# MAGIC SELECT trading_date, COUNT(*) AS rows_, COUNT(DISTINCT store_id) AS stores
# MAGIC FROM kestrel.sandbox.daily_store_sales
# MAGIC GROUP BY trading_date
# MAGIC HAVING COUNT(*) <> COUNT(DISTINCT store_id)

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %md ## 5. The fix: replace the day, don't add it

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %md Run the fix cell again, then this check. Safe to rerun means the numbers do not move.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %md ## 6. Delta enforces the schema

# COMMAND ----------

(day.withColumn("region_code", F.lit("LON"))
    .write.mode("append")
    .saveAsTable(TABLE))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Grace
# MAGIC Table: **`kestrel.sandbox.daily_store_sales`**, one row per store per trading day.
# MAGIC September 2026: 12,011 store-days, net sales **7,329,830.18**, matching the board pack.
# MAGIC The morning update replaces yesterday's rows, so a retried job cannot double a day.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Grace wants **29 September restated**. A colleague copies the fix cell and changes the day, but not the condition:
# MAGIC
# MAGIC ```python
# MAGIC day = daily_sales("2026-09-29", "2026-09-29")
# MAGIC (day.write
# MAGIC     .mode("overwrite")
# MAGIC     .option("replaceWhere", "trading_date = '2026-09-30'")   # still the 30th
# MAGIC     .saveAsTable(TABLE))
# MAGIC ```
# MAGIC
# MAGIC **What happens, and how many store-days and how much net sales does the table hold afterwards?**
# MAGIC Start from the table as this notebook leaves it: 12,011 store-days, 7,329,830.18. Write down what you expect, then run it and check.
# MAGIC
# MAGIC Put your answer in the comments. I'll show mine at the start of episode 11.

# COMMAND ----------

# Your answer here
