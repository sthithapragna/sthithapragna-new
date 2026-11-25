# Databricks notebook source
# MAGIC %md
# MAGIC # Season 2: designing the store sales lakehouse
# MAGIC **Asked by:** Meera Shah. A lakehouse the whole business can trust, rebuilt properly, layer by layer.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from pyspark.sql import functions as F, Window

# COMMAND ----------

# MAGIC %md ## Homework: September's delivered web sales (as at the 1 October delivery)

# COMMAND ----------

ECOM_SCHEMA = """
    event_id STRING, event_type STRING, event_ts STRING, order_id STRING, order_status STRING,
    channel STRING, app_version STRING,
    customer STRUCT<loyalty_id: BIGINT, email: STRING, postcode: STRING>,
    items    ARRAY<STRUCT<sku: STRING, qty: INT, unit_price: STRING>>,
    delivery STRUCT<type: STRING, store_id: STRING, slot_start: STRING, slot_end: STRING>,
    payment  STRUCT<method: STRING, amount: DECIMAL(10,2)>
"""
events = (spark.read.schema(ECOM_SCHEMA).json(ECOM)
          .filter(F.col("delivered") <= "2026-10-01")
          .withColumn("event_time", F.to_timestamp("event_ts")))
latest = (events.withColumn("rn", F.row_number().over(
              Window.partitionBy("order_id").orderBy(F.desc("event_time"))))
                .filter("rn = 1"))
display(latest.filter(F.col("order_status") == "DELIVERED")
              .groupBy("channel")
              .agg(F.count("*").alias("delivered_orders"), F.sum("payment.amount").alias("value"))
              .orderBy("channel"))

# COMMAND ----------

# MAGIC %md ## 1. The layers as they stand

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT schema_name, comment
# MAGIC FROM kestrel.information_schema.schemata
# MAGIC WHERE schema_name IN ('landing', 'bronze', 'silver', 'gold', 'ops', 'sandbox')
# MAGIC ORDER BY schema_name

# COMMAND ----------

# MAGIC %md ## 2. Write each layer's contract where everyone will see it

# COMMAND ----------

# MAGIC %sql
# MAGIC COMMENT ON SCHEMA kestrel.landing IS 'Raw files exactly as each source system sent them. Volumes only.';
# MAGIC COMMENT ON SCHEMA kestrel.bronze  IS 'Every row that arrived, unchanged, plus source file and arrival time. Never cleaned.';
# MAGIC COMMENT ON SCHEMA kestrel.silver  IS 'Typed, deduplicated and conformed. One row per business key. Decisions documented.';
# MAGIC COMMENT ON SCHEMA kestrel.gold    IS 'Business-ready facts, dimensions and metrics at a stated grain. Reads silver only.';
# MAGIC COMMENT ON SCHEMA kestrel.ops     IS 'Operational state: simulator state and pipeline checkpoints.';

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER SCHEMA kestrel.bronze SET TAGS ('layer' = 'bronze');
# MAGIC ALTER SCHEMA kestrel.silver SET TAGS ('layer' = 'silver');
# MAGIC ALTER SCHEMA kestrel.gold   SET TAGS ('layer' = 'gold');

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT s.schema_name, t.tag_value AS layer, s.comment
# MAGIC FROM kestrel.information_schema.schemata s
# MAGIC LEFT JOIN kestrel.information_schema.schema_tags t
# MAGIC   ON t.schema_name = s.schema_name AND t.tag_name = 'layer'
# MAGIC WHERE s.schema_name IN ('landing', 'bronze', 'silver', 'gold', 'ops')
# MAGIC ORDER BY s.schema_name

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE VOLUME IF NOT EXISTS kestrel.ops.checkpoints
# MAGIC COMMENT 'Auto Loader and streaming checkpoints and schema locations, from episode 17'

# COMMAND ----------

print(BRONZE, SILVER, GOLD, CHECKPOINTS)

# COMMAND ----------

# MAGIC %md ## 3. Why bronze never deduplicates

# COMMAND ----------

raw = (spark.read.option("header", True).schema(POS_SCHEMA).csv(POS)
       .filter(F.col("delivered") <= "2026-10-01")          # as at the 1 October delivery
       .filter(F.col("txn_id") != "txn_id"))
row_cols = [c for c in raw.columns if c != "delivered"]

print(raw.count(), "till lines received")
print(raw.dropDuplicates(row_cols).count(), "after dropDuplicates()")

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

display(raw.filter(F.col("txn_id") == "0001-20260901-01-00160")
           .select("txn_id", "txn_ts", "sku", "qty", "unit_price", "line_total"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Design decisions (Season 2)
# MAGIC - **Bronze** keeps every row that arrived, unchanged, plus `_source_file` and `_ingested_at`. Never cleaned.
# MAGIC - **Silver** decides, using evidence (file names, delivery dates), never "these two rows look the same".
# MAGIC - **Gold** states its grain in its name, its comment and its tests. Reads silver only.
# MAGIC - Tables: `bronze.pos_transactions` then `silver.sales_lines` then `gold.fact_sales_line` (frozen in LANDSCAPE.md).
# MAGIC - Checkpoints: `/Volumes/kestrel/ops/checkpoints`.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Scotland's till file for **16 September** arrived twice: `pos_SCO_2026-09-16.csv` in `delivered=2026-09-17`, and `pos_SCO_2026-09-16_resend.csv` in `delivered=2026-09-18`. The real day is the **4,067** lines of the original file.
# MAGIC
# MAGIC Filter `raw` to just those two files (`_metadata.file_name` starts with `pos_SCO_2026-09-16`) and run `dropDuplicates(row_cols)` on them.
# MAGIC 1. How many lines are left?
# MAGIC 2. How much of Scotland's net sales for 16 September (`line_total` where `is_void = 'N'`) has gone missing?
# MAGIC
# MAGIC Put your answer in the comments. The answer opens the next episode.

# COMMAND ----------

# Your answer here
