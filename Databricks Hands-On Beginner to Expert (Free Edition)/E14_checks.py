# Databricks notebook source
# MAGIC %md
# MAGIC # Episode 14: is Grace's table fresh?
# MAGIC Run after each job run. Status tells you the code didn't crash; these tell you the data moved.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Last episode's homework: the next Sunday

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count_if(on_hand < 0 OR on_order < 0)                                AS quarantined_lines,
# MAGIC        COUNT(DISTINCT CASE WHEN on_hand < 0 OR on_order < 0 THEN store_id END) AS stores_to_recount,
# MAGIC        count_if(on_hand = 0)                                                AS out_of_stock_lines,
# MAGIC        count_if(greatest(on_hand, 0) = 0)                                   AS out_of_stock_if_clamped
# MAGIC FROM read_files('/Volumes/kestrel/landing/wms/stock_snapshots/delivered=2026-09-14/', format => 'parquet')

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 1. Freshness: the latest day, and the totals
# MAGIC SELECT MAX(trading_date) AS latest_day, COUNT(*) AS store_days, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 2. Any gaps between 1 September and the latest day?
# MAGIC SELECT d AS missing_day
# MAGIC FROM (SELECT explode(sequence(DATE'2026-09-01',
# MAGIC                               (SELECT MAX(trading_date) FROM kestrel.sandbox.daily_store_sales),
# MAGIC                               INTERVAL 1 DAY)) AS d)
# MAGIC WHERE d NOT IN (SELECT trading_date FROM kestrel.sandbox.daily_store_sales)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 3. The most recent days, one row each
# MAGIC SELECT trading_date, COUNT(*) AS stores, SUM(net_sales) AS net_sales
# MAGIC FROM kestrel.sandbox.daily_store_sales
# MAGIC WHERE trading_date >= DATE'2026-09-29'
# MAGIC GROUP BY trading_date
# MAGIC ORDER BY trading_date


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Imagine the morning after we fixed the job, **before its first catch-up run**:
# MAGIC
# MAGIC 1. A colleague uses **Run now with different settings** with `trading_date = 2026-10-02`.
# MAGIC 2. Then the job runs as normal, with `trading_date = latest`.
# MAGIC
# MAGIC Same data as this episode: deliveries up to 3 October, and Grace's table up to 30 September before these two runs.
# MAGIC **What does the second run print, what do the three checks above show, and how would you fix it?**
# MAGIC
# MAGIC To try it for real afterwards: delete 1 October (`DELETE FROM kestrel.sandbox.daily_store_sales WHERE trading_date = '2026-10-01'`), run the job, run the checks, then fix it.
# MAGIC
# MAGIC Put your answer in the comments. I'll show mine at the start of episode 15.

# COMMAND ----------

# Your answer here
