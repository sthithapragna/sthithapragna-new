# Databricks notebook source
# MAGIC %md
# MAGIC # Daily sales by store, for the board pack
# MAGIC **Asked by:** Grace Liu, Finance. Net sales per store per day for September 2026, with store name
# MAGIC and format, plus a summary by format. **Control:** Finance reconciles to the till system's Z reports.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Episode 07's homework: when the web prices turn to text

# COMMAND ----------

for day in ["2026-09-09", "2026-09-10", "2026-09-11", "2026-09-12"]:
    events = spark.read.json(f"{ECOM}/delivered={day}")
    price = [f for f in events.schema["items"].dataType.elementType.fields if f.name == "unit_price"][0]
    first_event = events.agg(F.min("event_ts")).first()[0]
    app52 = events.filter(F.col("app_version") == "5.2").count()
    print(day, "events from", first_event[:10], "| app 5.2 events:", app52,
          "| items.unit_price is", price.dataType.simpleString())

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md ## 1. Till lines, read the way episode 07 taught us

# COMMAND ----------

lines = (spark.read
         .option("header", True)
         .schema(POS_SCHEMA)
         .csv(POS)
         .filter(F.col("txn_id") != "txn_id")                          # the stray header row
         .filter(~F.col("_metadata.file_name").contains("resend"))     # patch until episode 19
         .withColumn("trading_date", F.to_date("txn_ts", POS_TS_FORMAT))
         .filter(F.col("trading_date").between("2026-09-01", "2026-09-30")))
print(lines.count(), "till lines in September")

# COMMAND ----------

stores = (spark.read
          .option("header", True)
          .csv(f"{REFERENCE}/stores/stores_2026-09-23.csv")
          .select("store_id", "store_name", "format", "region_code"))
print(stores.count(), "stores")

# COMMAND ----------

# MAGIC %md ## 2. Join, then check

# COMMAND ----------

sales = lines.join(stores, on="store_id", how="left")
print("rows before:", lines.count(), " after:", sales.count())
print("lines with no store:", sales.filter(F.col("format").isNull()).count())

# COMMAND ----------

old_stores = (spark.read.option("header", True)
              .csv(f"{REFERENCE}/stores/stores_2026-08-31.csv")
              .select("store_id"))
orphans = lines.join(old_stores, on="store_id", how="left_anti")
print(orphans.count(), "lines have no store in the 31 August list")
display(orphans.groupBy("store_id").count())

# COMMAND ----------

# MAGIC %md ## 3. Daily sales by store: first attempt

# COMMAND ----------

daily_first = (sales
               .groupBy("trading_date", "store_id", "store_name", "format")
               .agg(F.countDistinct("txn_id").alias("baskets"),
                    F.sum("line_total").alias("sales")))
display(daily_first.filter((F.col("store_id") == "0001") & (F.col("trading_date") == "2026-09-01")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Reconcile
# MAGIC Z report, Kestrel Kensington Superstore (0001), 1 September 2026: **19,721.53**

# COMMAND ----------

display(sales
        .filter((F.col("store_id") == "0001") & (F.col("trading_date") == "2026-09-01"))
        .groupBy("is_void", "txn_type")
        .agg(F.count("*").alias("lines"), F.sum("line_total").alias("total"))
        .orderBy("is_void", "txn_type"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Net sales, written down
# MAGIC Sales and returns (as negatives) in. Voided lines out. Re-sent files and the stray header row out.

# COMMAND ----------

daily = (sales
         .filter(F.col("is_void") == "N")
         .groupBy("trading_date", "store_id", "store_name", "format")
         .agg(F.countDistinct("txn_id").alias("baskets"),
              F.sum("line_total").alias("net_sales")))
display(daily.filter((F.col("store_id") == "0001") & (F.col("trading_date") == "2026-09-01")))

# COMMAND ----------

print(daily.count(), "store-days")

# COMMAND ----------

by_format = (sales
             .filter(F.col("is_void") == "N")
             .groupBy("format")
             .agg(F.countDistinct("store_id").alias("stores"),
                  F.sum("line_total").alias("net_sales"))
             .orderBy(F.desc("net_sales")))
display(by_format)

# COMMAND ----------

display(sales.agg(
    F.sum("line_total").alias("all_lines"),
    F.sum(F.when(F.col("is_void") == "N", F.col("line_total"))).alias("net_sales")))

# COMMAND ----------

# MAGIC %md ## 6. The same result, from SQL

# COMMAND ----------

daily.createOrReplaceTempView("e08_daily_sales")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT trading_date, store_name, baskets, net_sales
# MAGIC FROM e08_daily_sales
# MAGIC ORDER BY net_sales DESC
# MAGIC LIMIT 5

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Grace
# MAGIC **Net sales, September 2026: 7,329,830.18** (Superstore 4,632,441.48; Local 2,443,123.02; Express 254,265.68).
# MAGIC 12,011 store-days, reconciled to the Z report for Kensington on 1 September (19,721.53).
# MAGIC **Definition:** sale and return lines; voided lines, re-sent files and the stray header row excluded.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Grace wants one more table for the board pack: **September's net sales by region**, using exactly the definition in section 5.
# MAGIC
# MAGIC **Which region had the highest net sales in September, and how much, to the penny?**
# MAGIC
# MAGIC Hint: `stores` already carries `region_code`.
# MAGIC
# MAGIC Put your answer in the comments. The answer is at the start of episode 09.

# COMMAND ----------

# Your answer here
