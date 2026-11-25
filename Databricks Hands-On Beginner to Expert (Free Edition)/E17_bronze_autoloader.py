# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze for the tills, with Auto Loader
# MAGIC **Asked by:** Meera Shah. Every till file loaded exactly once, every row labelled with its file and arrival time.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Episode 16's homework: dropDuplicates() on Scotland's 16 September

# COMMAND ----------

sco = (spark.read.option("header", True).schema(POS_SCHEMA)
       .csv(f"{POS}/delivered=2026-09-1*/pos_SCO_2026-09-16*.csv"))
row_cols = [c for c in sco.columns if c != "delivered"]
original = sco.filter(~F.col("_metadata.file_name").contains("resend"))
for name, df in [("both files", sco), ("original file", original),
                 ("after dropDuplicates()", sco.dropDuplicates(row_cols))]:
    r = df.agg(F.count("*").alias("lines"),
               F.sum(F.when(F.col("is_void") == "N", F.col("line_total"))).alias("net_sales")).first()
    print(f"{name:24s} {r.lines:>6,} lines  {r.net_sales:>10,.2f}")

# COMMAND ----------

from pyspark.sql import functions as F

TABLE = f"{BRONZE}.pos_transactions"
CHECKPOINT = f"{CHECKPOINTS}/bronze_pos_transactions"      # one checkpoint per table, named after it

# COMMAND ----------

# MAGIC %md ## 1. The load

# COMMAND ----------

def load_bronze_pos(checkpoint):
    query = (spark.readStream
             .format("cloudFiles")
             .option("cloudFiles.format", "csv")
             .option("header", True)
             .option("cloudFiles.schemaLocation", f"{checkpoint}/_schema")
             .load(POS)
             .select("*",
                     F.col("_metadata.file_path").alias("_source_file"),
                     F.current_timestamp().alias("_ingested_at"))
             .writeStream
             .option("checkpointLocation", checkpoint)
             .trigger(availableNow=True)
             .toTable(TABLE))
    query.awaitTermination()
    return query

# COMMAND ----------

load_bronze_pos(CHECKPOINT)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS rows_, COUNT(DISTINCT _source_file) AS files
# MAGIC FROM kestrel.bronze.pos_transactions

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE TABLE kestrel.bronze.pos_transactions

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Bronze keeps everything: the stray header row, and the re-sent file
# MAGIC SELECT _source_file, COUNT(*) AS rows_
# MAGIC FROM kestrel.bronze.pos_transactions
# MAGIC WHERE txn_id = 'txn_id' OR _source_file LIKE '%resend%'
# MAGIC GROUP BY _source_file

# COMMAND ----------

# MAGIC %md ## 2. Exactly once

# COMMAND ----------

load_bronze_pos(CHECKPOINT)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS rows_, COUNT(DISTINCT _source_file) AS files
# MAGIC FROM kestrel.bronze.pos_transactions

# COMMAND ----------

display(dbutils.fs.ls(CHECKPOINT))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. A new delivery
# MAGIC Run `kestrel_simulator` with mode `next_day` now, then continue.

# COMMAND ----------

load_bronze_pos(CHECKPOINT)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS rows_, COUNT(DISTINCT _source_file) AS files
# MAGIC FROM kestrel.bronze.pos_transactions

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT _source_file, _ingested_at, COUNT(*) AS rows_
# MAGIC FROM kestrel.bronze.pos_transactions
# MAGIC GROUP BY _source_file, _ingested_at
# MAGIC ORDER BY _ingested_at DESC, _source_file
# MAGIC LIMIT 9

# COMMAND ----------

# MAGIC %md ## 4. The tidy-up

# COMMAND ----------

load_bronze_pos(f"{CHECKPOINTS}/bronze_pos_transactions_v2")     # "renamed to match the new standard"

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS rows_, COUNT(DISTINCT _source_file) AS files
# MAGIC FROM kestrel.bronze.pos_transactions

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Every file should have exactly one load time
# MAGIC SELECT COUNT(*) AS files_loaded_more_than_once
# MAGIC FROM (SELECT _source_file
# MAGIC       FROM kestrel.bronze.pos_transactions
# MAGIC       GROUP BY _source_file
# MAGIC       HAVING COUNT(DISTINCT _ingested_at) > 1)

# COMMAND ----------

# MAGIC %md ## 5. Undo it: restore the table, remove the stray checkpoint

# COMMAND ----------

# The duplicate load can land as more than one write, so don't just step back one version.
# Every write from the v2 checkpoint carries the same queryId: restore to just before the first one.
writes = spark.sql(f"DESCRIBE HISTORY {TABLE}").filter("operation = 'STREAMING UPDATE'")
dup_query = writes.orderBy(F.desc("version")).first()["operationParameters"]["queryId"]
v_first_dup = (writes.filter(F.col("operationParameters")["queryId"] == dup_query)
               .agg(F.min("version")).first()[0])
spark.sql(f"RESTORE TABLE {TABLE} TO VERSION AS OF {v_first_dup - 1}")
dbutils.fs.rm(f"{CHECKPOINTS}/bronze_pos_transactions_v2", True)
print(f"Duplicate load began at version {v_first_dup}; restored to version {v_first_dup - 1}; stray checkpoint removed")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS rows_, COUNT(DISTINCT _source_file) AS files,
# MAGIC        (SELECT COUNT(*) FROM (SELECT _source_file FROM kestrel.bronze.pos_transactions
# MAGIC                               GROUP BY _source_file HAVING COUNT(DISTINCT _ingested_at) > 1)) AS files_loaded_more_than_once
# MAGIC FROM kestrel.bronze.pos_transactions

# COMMAND ----------

load_bronze_pos(CHECKPOINT)       # the real checkpoint still agrees with the table: nothing new to load

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS rows_ FROM kestrel.bronze.pos_transactions

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Meera
# MAGIC **`kestrel.bronze.pos_transactions`**: every till file loaded exactly once by Auto Loader, as strings, with
# MAGIC `_source_file` and `_ingested_at` on every row. Checkpoint: `/Volumes/kestrel/ops/checkpoints/bronze_pos_transactions`.
# MAGIC The table and its checkpoint are a pair: reset them together, or not at all.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Bronze keeps every till column as **text** (types are silver's decision).
# MAGIC Using only `kestrel.bronze.pos_transactions`, with deliveries up to 4 October (`WHERE delivered <= '2026-10-04'`):
# MAGIC **what is the latest till timestamp in bronze?**
# MAGIC
# MAGIC Try `SELECT MAX(txn_ts) ...` first, then decide whether you believe it. Episode 07's timestamp format, `dd/MM/yyyy HH:mm:ss`, will help.
# MAGIC
# MAGIC Put your answer in the comments. The answer opens the next episode.

# COMMAND ----------

# Your answer here
