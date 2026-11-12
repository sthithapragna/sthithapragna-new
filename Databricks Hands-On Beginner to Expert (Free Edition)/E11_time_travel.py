# Databricks notebook source
# MAGIC %md
# MAGIC # Someone deleted Tuesday
# MAGIC **Raised by:** Grace Liu, Finance, Thursday 11:30. Tuesday 15 September has vanished from her dashboard.
# MAGIC Uses `kestrel.sandbox.daily_store_sales` from episode 10.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Last episode's homework: the replaceWhere slip

# COMMAND ----------

day = spark.table(TABLE).filter("trading_date = '2026-09-29'")      # 29 September's 401 rows
try:
    (day.write
        .mode("overwrite")
        .option("replaceWhere", "trading_date = '2026-09-30'")      # the slip: still the 30th
        .saveAsTable(TABLE))
except Exception as e:
    print(str(e)[:300])
display(spark.sql(f"SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales FROM {TABLE}"))

# COMMAND ----------

from pyspark.sql import functions as F

TABLE = f"{CATALOG}.sandbox.daily_store_sales"

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Where episode 10 left it: 12,011 store-days, 7,329,830.18
# MAGIC SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %md
# MAGIC ## Thursday morning (run these two cells to act it out)
# MAGIC **09:12:** a clean-up script is tested against the wrong table.

# COMMAND ----------

# MAGIC %sql
# MAGIC DELETE FROM kestrel.sandbox.daily_store_sales
# MAGIC WHERE trading_date = '2026-09-15'

# COMMAND ----------

# MAGIC %md **10:05:** store operations correct Solihull's name. A legitimate change.

# COMMAND ----------

# MAGIC %sql
# MAGIC UPDATE kestrel.sandbox.daily_store_sales
# MAGIC SET store_name = 'Kestrel Solihull High Street Local'
# MAGIC WHERE store_id = '0413'

# COMMAND ----------

# MAGIC %md ## 1. 11:30: what Grace sees

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Which September days have no rows at all?
# MAGIC SELECT d AS missing_day
# MAGIC FROM (SELECT explode(sequence(DATE'2026-09-01', DATE'2026-09-30', INTERVAL 1 DAY)) AS d)
# MAGIC WHERE d NOT IN (SELECT trading_date FROM kestrel.sandbox.daily_store_sales)

# COMMAND ----------

# MAGIC %md ## 2. What happened?

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY kestrel.sandbox.daily_store_sales

# COMMAND ----------

history = spark.sql(f"DESCRIBE HISTORY {TABLE}")
v_delete = history.filter(F.col("operation") == "DELETE").agg(F.max("version")).first()[0]
v_before = v_delete - 1
v_now = history.agg(F.max("version")).first()[0]
print(f"version before the delete: {v_before}   the delete: {v_delete}   current: {v_now}")

# COMMAND ----------

# MAGIC %md ## 3. Travel back

# COMMAND ----------

display(spark.sql(f"""
    SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
    FROM {TABLE} VERSION AS OF {v_before}"""))

# COMMAND ----------

ts_before = history.filter(F.col("version") == v_before).first()["timestamp"]
display(spark.sql(f"""
    SELECT COUNT(*) AS store_days
    FROM {TABLE} TIMESTAMP AS OF '{ts_before}'"""))

# COMMAND ----------

# MAGIC %md ## 4. Compare before fixing anything

# COMMAND ----------

changed = spark.sql(f"""
    SELECT * FROM {TABLE} VERSION AS OF {v_before}
    EXCEPT
    SELECT * FROM {TABLE}""")
display(changed
        .withColumn("change", F.when(F.col("trading_date") == "2026-09-15", "Tuesday deleted")
                               .otherwise("renamed since"))
        .groupBy("change").count())

# COMMAND ----------

# MAGIC %md ## 5. The tempting fix

# COMMAND ----------

display(spark.sql(f"RESTORE TABLE {TABLE} TO VERSION AS OF {v_before}"))

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT DISTINCT store_name
# MAGIC FROM kestrel.sandbox.daily_store_sales
# MAGIC WHERE store_id = '0413'

# COMMAND ----------

# MAGIC %md ## 6. Undo the restore, then put back only Tuesday

# COMMAND ----------

spark.sql(f"RESTORE TABLE {TABLE} TO VERSION AS OF {v_now}")
spark.sql(f"""
    INSERT INTO {TABLE}
    SELECT * FROM {TABLE} VERSION AS OF {v_before}
    WHERE trading_date = '2026-09-15'""")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS store_days,
# MAGIC        SUM(net_sales) AS net_sales,
# MAGIC        MAX(CASE WHEN store_id = '0413' THEN store_name END) AS solihull_name
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

display(spark.sql(f"""
    SELECT * FROM {TABLE} VERSION AS OF {v_before}
    EXCEPT
    SELECT * FROM {TABLE}""").groupBy("store_id").count())

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Grace
# MAGIC Tuesday 15 September was deleted at 09:12 by a clean-up script run against the wrong table. All 400 rows are back,
# MAGIC copied from the version before the delete. September is again **7,329,830.18** across 12,011 store-days, and
# MAGIC store operations' correction to Solihull's name has been kept.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Section 4 compared *the version before the delete* EXCEPT *Thursday's version* and found 411 rows. Turn it round:
# MAGIC
# MAGIC ```python
# MAGIC display(spark.sql(f"""
# MAGIC     SELECT * FROM {TABLE} VERSION AS OF {v_now}
# MAGIC     EXCEPT
# MAGIC     SELECT * FROM {TABLE} VERSION AS OF {v_before}"""))
# MAGIC ```
# MAGIC
# MAGIC `v_now` (Thursday, after the delete and the rename) and `v_before` come from the version lookup cell in section 2.
# MAGIC **How many rows come back, and which ones?**
# MAGIC
# MAGIC Put your answer in the comments. I'll show mine at the start of episode 12.

# COMMAND ----------

# Your answer here
