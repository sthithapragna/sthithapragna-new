# Databricks notebook source
# MAGIC %md
# MAGIC # Which products are rising in London?
# MAGIC **Asked by:** Aisha Rahman, Supply Chain. **Question:** top 10 products by units sold in London stores,
# MAGIC week 1 (1 to 7 September) against week 2 (8 to 14 September).

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Episode 05's homework: the busiest trading day in September

# COMMAND ----------

display(spark.sql(f"""
    SELECT left(txn_ts, 10)       AS trading_day,
           COUNT(DISTINCT txn_id) AS baskets
    FROM read_files('{POS}/', format => 'csv')
    WHERE txn_ts LIKE '%/09/2026%'
    GROUP BY 1
    ORDER BY baskets DESC
    LIMIT 3"""))

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md ## 1. Reading is lazy

# COMMAND ----------

lon_raw = (spark.read
           .option("header", True)
           .option("basePath", POS)
           .csv(f"{POS}/delivered=*/pos_LON_*.csv"))

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

lon.explain()

# COMMAND ----------

# MAGIC %md ## 2. Actions do the work

# COMMAND ----------

print(lon.count(), "London till lines, voids excluded")

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Both weeks in a loop
# MAGIC Delivered dates are one day after trading, so week 1 is delivered 2 to 8 September.

# COMMAND ----------

weeks = {"week 1": ("2026-09-02", "2026-09-08"),
         "week 2": ("2026-09-09", "2026-09-15")}
results = {}
for week, (start, end) in weeks.items():
    lon.filter(F.col("delivered").between(start, end)).createOrReplaceTempView("pos_week")
    results[week] = spark.sql("""
        SELECT sku, SUM(qty) AS units
        FROM pos_week
        GROUP BY sku
        ORDER BY units DESC, sku
        LIMIT 10""")

# COMMAND ----------

display(results["week 1"])

# COMMAND ----------

display(results["week 2"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. The fix: no shared view name
# MAGIC A function that returns a DataFrame. Each call builds its own plan.

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

display(top_products("2026-09-02", "2026-09-08"))

# COMMAND ----------

display(top_products("2026-09-09", "2026-09-15"))

# COMMAND ----------

# MAGIC %md ## 5. Errors wait for the action

# COMMAND ----------

typo = lon.filter(F.col("fromat") == "Local")

# COMMAND ----------

typo.count()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Caching on serverless: DataFrames yes, tables no
# MAGIC `df.cache()` and `persist()` work on serverless today. Table-level caching (`CACHE TABLE`,
# MAGIC `spark.catalog.cacheTable`) still raises an error, so leave it out of older tutorials' code.

# COMMAND ----------

lon.cache()
lon.count()

# COMMAND ----------

# Expect an error: table-level caching isn't supported on serverless
spark.sql("CACHE TABLE samples.nyctaxi.trips")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Aisha (London, units sold, voids excluded)
# MAGIC | Product | Week 1 | Week 2 |
# MAGIC |---|---|---|
# MAGIC | Ashby Dog Food 1 each | 8,706 | 8,367 |
# MAGIC | Penrose Eggs 12 pack | 4,695 | 4,781 |
# MAGIC | Ridgeway Pizza 6 pack | 3,139 | 3,319 |
# MAGIC | Penrose Muffins x2 | 1,420 | 1,562 |
# MAGIC
# MAGIC The same products lead both weeks. Pizza (+180) and muffins (+142) are rising; dog food fell by 339.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Aisha wants **week 3** as well: trading **15 to 21 September**.
# MAGIC
# MAGIC Use `top_products` to get London's top 10 for week 3. **How many units of Ashby Dog Food (SKU `176968`) did London sell in week 3?**
# MAGIC
# MAGIC Put your answer in the comments. The answer is at the start of episode 07.

# COMMAND ----------

# Your answer here
