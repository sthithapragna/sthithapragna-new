# Databricks notebook source
# MAGIC %md
# MAGIC # Auditing the handover notebook
# MAGIC Four checks from Season 1, applied to the contractor's board pack. Run `E15_contractor_pack` twice first.

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

# MAGIC %md ## What Grace's dashboard reads

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT format, net_sales, month FROM kestrel.sandbox.board_pack ORDER BY format

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT SUM(net_sales) AS dashboard_total FROM kestrel.sandbox.board_pack WHERE month = '2026-09'

# COMMAND ----------

# MAGIC %md ## Check 1 (episode 10): one row per format?

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT month, format, COUNT(*) AS rows_
# MAGIC FROM kestrel.sandbox.board_pack
# MAGIC GROUP BY month, format
# MAGIC HAVING COUNT(*) > 1

# COMMAND ----------

# MAGIC %md ## Check 2 (episodes 11 and 14): any missing days?

# COMMAND ----------

contractor = (spark.read.option("header", True).schema(POS_SCHEMA).csv(POS)
              .filter(F.col("delivered").between("2026-09-01", "2026-09-30")))

# COMMAND ----------

display(contractor
        .withColumn("trading_date", F.to_date("txn_ts", POS_TS_FORMAT))
        .agg(F.min("trading_date"), F.max("trading_date")))

# COMMAND ----------

display(contractor
        .filter(F.col("txn_id") != "txn_id")                                   # episode 07
        .withColumn("trading_date", F.to_date("txn_ts", POS_TS_FORMAT))
        .agg(F.min("trading_date").alias("first_day"),
             F.max("trading_date").alias("last_day"),
             F.countDistinct("trading_date").alias("days")))

# COMMAND ----------

# MAGIC %md ## Check 3 (episode 05): lines per basket

# COMMAND ----------

display(contractor
        .filter(F.col("txn_ts").startswith("16/09/2026"))
        .withColumn("region", F.split(F.col("_metadata.file_name"), "_")[1])
        .groupBy("region")
        .agg(F.countDistinct("txn_id").alias("baskets"), F.count("*").alias("lines"))
        .withColumn("lines_per_basket", F.round(F.col("lines") / F.col("baskets"), 2))
        .orderBy(F.desc("lines_per_basket")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 4 (episode 08): reconcile to a Z report
# MAGIC Z report, Kensington (0001), 1 September: **19,721.53**

# COMMAND ----------

display(contractor
        .filter((F.col("store_id") == "0001") & F.col("txn_ts").startswith("01/09/2026"))
        .agg(F.sum("line_total").alias("contractor_logic")))

# COMMAND ----------

# MAGIC %md ## From his number to the right one

# COMMAND ----------

base = spark.read.option("header", True).schema(POS_SCHEMA).csv(POS).filter(F.col("txn_id") != "txn_id")

def total(df):
    return df.agg(F.sum("line_total")).first()[0]

step0 = base.filter(F.col("delivered").between("2026-09-01", "2026-09-30"))
step1 = step0.filter(~F.col("_metadata.file_name").contains("resend"))
step2 = step1.filter(F.col("is_void") == "N")
step3 = (base.filter(~F.col("_metadata.file_name").contains("resend"))
             .filter(F.col("is_void") == "N")
             .withColumn("trading_date", F.to_date("txn_ts", POS_TS_FORMAT))
             .filter(F.col("trading_date").between("2026-09-01", "2026-09-30")))

display(spark.createDataFrame([
    ("1. The contractor's logic",                 total(step0)),
    ("2. Without the re-sent file",               total(step1)),
    ("3. Without voided lines",                   total(step2)),
    ("4. By trading date, 1 to 30 September",     total(step3)),
], "step STRING, september_net_sales DECIMAL(20,2)"))

# COMMAND ----------

# MAGIC %md ## The corrected pack, written safely

# COMMAND ----------

stores = spark.read.option("header", True).csv(f"{REFERENCE}/stores/stores_2026-09-23.csv")
corrected = (step3.join(stores, "store_id")
                  .groupBy("format")
                  .agg(F.sum("line_total").alias("net_sales"))
                  .withColumn("month", F.lit("2026-09")))

(corrected.write.mode("overwrite")
    .option("replaceWhere", "month = '2026-09'")
    .saveAsTable(f"{CATALOG}.sandbox.board_pack"))

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT format, net_sales FROM kestrel.sandbox.board_pack WHERE month = '2026-09' ORDER BY net_sales DESC

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS rows_, SUM(net_sales) AS september_net_sales FROM kestrel.sandbox.board_pack

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Meera and Grace
# MAGIC The handover notebook had four problems, none of which raised an error: it appended (and was run twice),
# MAGIC filtered on delivery date (losing 30 September), read the re-sent Scotland file, and included voided lines.
# MAGIC Corrected September net sales: **7,329,830.18**, matching the reconciled figure from episode 08.
# MAGIC
# MAGIC **Homework:** September's web sales, counting only delivered orders, as at the 1 October delivery. Orders and value, by channel.
