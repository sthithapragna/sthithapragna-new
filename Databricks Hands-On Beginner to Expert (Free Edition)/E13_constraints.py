# Databricks notebook source
# MAGIC %md
# MAGIC # A stock table that refuses impossible data
# MAGIC **Asked by:** Aisha Rahman, Supply Chain. Load Sunday night's stock snapshot (6 September).
# MAGIC Rule: stock can never be negative.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Last episode's homework: the third morning

# COMMAND ----------

MEMBERS = f"{CATALOG}.sandbox.members"
feed = spark.read.json(f"{CRM_CHANGES}/delivered=2026-09-04")
display(feed.groupBy("op").count().orderBy("op"))                    # c 512, d 16, u 1539
m = (spark.sql(f"DESCRIBE HISTORY {MEMBERS}")
     .filter("operation = 'MERGE'").orderBy(F.desc("version")).first()["operationMetrics"])
print("latest merge: updated", m["numTargetRowsUpdated"], " inserted", m["numTargetRowsInserted"],
      " deleted", m["numTargetRowsDeleted"])
print(spark.table(MEMBERS).count(), "members")

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md ## 1. The snapshot

# COMMAND ----------

snapshot = (spark.read.parquet(f"{WMS}/delivered=2026-09-07/")
            .withColumn("store_id", F.lpad(F.col("store_id").cast("string"), 4, "0"))   # 1 -> '0001' (episode 07)
            .withColumn("last_counted_at", F.col("last_counted_at").cast("timestamp"))  # match the table's type
            .select("snapshot_date", "store_id", "sku", "on_hand", "on_order",
                    "reorder_point", "last_counted_at"))
snapshot.createOrReplaceTempView("e13_snapshot")
display(snapshot.agg(F.count("*").alias("lines"),
                     F.min("on_hand").alias("min_on_hand"),
                     F.count_if(F.col("on_hand") < 0).alias("negative_lines"),
                     F.count_if(F.col("on_hand") == 0).alias("out_of_stock_lines")))

# COMMAND ----------

# MAGIC %md ## 2. A table with rules

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE kestrel.sandbox.stock_levels (
# MAGIC   snapshot_date   DATE      NOT NULL,
# MAGIC   store_id        STRING    NOT NULL,
# MAGIC   sku             STRING    NOT NULL,
# MAGIC   on_hand         INT,
# MAGIC   on_order        INT,
# MAGIC   reorder_point   INT,
# MAGIC   last_counted_at TIMESTAMP
# MAGIC )

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE kestrel.sandbox.stock_levels ADD CONSTRAINT stock_on_hand_not_negative CHECK (on_hand >= 0);
# MAGIC ALTER TABLE kestrel.sandbox.stock_levels ADD CONSTRAINT stock_on_order_not_negative CHECK (on_order >= 0);

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW TBLPROPERTIES kestrel.sandbox.stock_levels

# COMMAND ----------

# MAGIC %md ## 3. Load it

# COMMAND ----------

# MAGIC %sql
# MAGIC INSERT INTO kestrel.sandbox.stock_levels
# MAGIC SELECT * FROM e13_snapshot

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS lines FROM kestrel.sandbox.stock_levels

# COMMAND ----------

# MAGIC %md ## 4. The quick fix

# COMMAND ----------

# MAGIC %sql
# MAGIC INSERT INTO kestrel.sandbox.stock_levels
# MAGIC SELECT snapshot_date, store_id, sku,
# MAGIC        greatest(on_hand, 0) AS on_hand,
# MAGIC        on_order, reorder_point, last_counted_at
# MAGIC FROM e13_snapshot

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Aisha's out-of-stock report
# MAGIC SELECT COUNT(*) AS lines, count_if(on_hand = 0) AS out_of_stock_lines
# MAGIC FROM kestrel.sandbox.stock_levels

# COMMAND ----------

# MAGIC %md ## 5. Quarantine instead

# COMMAND ----------

# MAGIC %sql
# MAGIC INSERT OVERWRITE kestrel.sandbox.stock_levels
# MAGIC SELECT * FROM e13_snapshot
# MAGIC WHERE on_hand >= 0 AND on_order >= 0

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE kestrel.sandbox.stock_quarantine AS
# MAGIC SELECT *, 'negative on_hand or on_order' AS reason, current_timestamp() AS quarantined_at
# MAGIC FROM e13_snapshot
# MAGIC WHERE on_hand < 0 OR on_order < 0

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   (SELECT COUNT(*) FROM kestrel.sandbox.stock_levels)                     AS good_lines,
# MAGIC   (SELECT COUNT(*) FROM kestrel.sandbox.stock_quarantine)                 AS quarantined_lines,
# MAGIC   (SELECT COUNT(DISTINCT store_id) FROM kestrel.sandbox.stock_quarantine) AS stores_to_recount,
# MAGIC   (SELECT COUNT(*) FROM e13_snapshot)                                     AS snapshot_lines,
# MAGIC   (SELECT count_if(on_hand = 0) FROM kestrel.sandbox.stock_levels)        AS out_of_stock_lines

# COMMAND ----------

# MAGIC %md ## 6. The lock still holds

# COMMAND ----------

# MAGIC %sql
# MAGIC INSERT INTO kestrel.sandbox.stock_levels
# MAGIC VALUES (DATE'2026-09-06', '0001', '999999', -5, 0, 2, current_timestamp())

# COMMAND ----------

# MAGIC %md ## 7. A primary key is a label, not a lock

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE kestrel.sandbox.stock_levels
# MAGIC ADD CONSTRAINT stock_levels_pk PRIMARY KEY (snapshot_date, store_id, sku)

# COMMAND ----------

# MAGIC %sql
# MAGIC INSERT INTO kestrel.sandbox.stock_levels
# MAGIC SELECT * FROM kestrel.sandbox.stock_levels WHERE store_id = '0001' AND sku = '176968'

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT snapshot_date, store_id, sku, COUNT(*) AS copies
# MAGIC FROM kestrel.sandbox.stock_levels
# MAGIC GROUP BY snapshot_date, store_id, sku
# MAGIC HAVING COUNT(*) > 1

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Put the table back to one row per product per store
# MAGIC INSERT OVERWRITE kestrel.sandbox.stock_levels
# MAGIC SELECT * FROM e13_snapshot
# MAGIC WHERE on_hand >= 0 AND on_order >= 0

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Aisha
# MAGIC **`kestrel.sandbox.stock_levels`**: 613,777 lines for 6 September. Stock can't go negative: a CHECK constraint refuses it.
# MAGIC **27,969** lines genuinely out of stock. **1,223** miscounted lines across **349** stores are in
# MAGIC `kestrel.sandbox.stock_quarantine`, as the warehouse recount list.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Next Sunday's snapshot is for **13 September**, in `delivered=2026-09-14`. Read it the way section 1 does (you don't need to load it into a table), then:
# MAGIC
# MAGIC 1. **How many lines would the CHECK constraints refuse?**
# MAGIC 2. **How many stores would need a recount?**
# MAGIC 3. **How many lines are genuinely out of stock?**
# MAGIC
# MAGIC Put your answer in the comments. I'll show mine at the start of episode 14.

# COMMAND ----------

# Your answer here
