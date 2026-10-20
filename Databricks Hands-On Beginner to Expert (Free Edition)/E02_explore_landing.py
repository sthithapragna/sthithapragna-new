# Databricks notebook source
# MAGIC %md
# MAGIC # Episode 02: a first look at what landed
# MAGIC
# MAGIC Run `kestrel_simulator` in `setup` mode, then `backfill`, before this notebook.
# MAGIC We look at the raw files exactly as the source systems sent them. Nothing is fixed yet.

# COMMAND ----------

dbutils.widgets.text("catalog", "kestrel", "Catalog")
CATALOG = dbutils.widgets.get("catalog")
LANDING = f"/Volumes/{CATALOG}/landing"
print(LANDING)

# COMMAND ----------

# MAGIC %md ## 1. The five landing volumes

# COMMAND ----------

# A schema isn't a folder: ask Unity Catalog for its volumes (dbutils.fs.ls works from a volume down)
display(spark.sql(f"SHOW VOLUMES IN {CATALOG}.landing"))

# COMMAND ----------

# MAGIC %md ## 2. One folder per delivery day

# COMMAND ----------

display(dbutils.fs.ls(f"{LANDING}/pos/transactions/"))

# COMMAND ----------

# MAGIC %sql
# MAGIC -- The same listing from SQL. Change the catalog name if you are not using kestrel.
# MAGIC LIST '/Volumes/kestrel/landing/pos/transactions/delivered=2026-09-02/'

# COMMAND ----------

# MAGIC %md ## 3. Raw till data: look before you load

# COMMAND ----------

print(dbutils.fs.head(f"{LANDING}/pos/transactions/delivered=2026-09-02/pos_LON_2026-09-01.csv", 700))

# COMMAND ----------

# MAGIC %md
# MAGIC Two things to notice, both of which bite in episode 07:
# MAGIC - `store_id` is `0001`, text with leading zeros.
# MAGIC - `txn_ts` is `01/09/2026 07:18:45`, day first, in UK local time, with no time zone.

# COMMAND ----------

# MAGIC %md ## 4. Web orders: nested JSON events

# COMMAND ----------

print(dbutils.fs.head(f"{LANDING}/ecom/order_events/delivered=2026-09-02/events_2026-09-01_08.jsonl", 1500))

# COMMAND ----------

# MAGIC %md ## 5. Loyalty CRM: a change feed, not a table

# COMMAND ----------

print(dbutils.fs.head(f"{LANDING}/crm/member_changes/delivered=2026-09-02/changes_2026-09-01.jsonl", 900))

# COMMAND ----------

# MAGIC %md ## 6. Warehouse stock: Parquet carries its own schema

# COMMAND ----------

# Needs simulator 1.1.1 or later: older versions wrote last_counted_at in nanoseconds, which serverless can't read
wms = spark.read.parquet(f"{LANDING}/wms/stock_snapshots/delivered=2026-09-07/")
wms.printSchema()
display(wms.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC Here `store_id` is an **integer**: store `0001` in the tills is `1` in the warehouse.
# MAGIC Two systems, one store, two different keys. Remember this in episode 22.

# COMMAND ----------

# MAGIC %md ## 7. Homework
# MAGIC The 13 September delivery should contain one till file per region for 12 September.
# MAGIC One region is missing. Which one, and in which delivery folder does it turn up?

# COMMAND ----------

display(dbutils.fs.ls(f"{LANDING}/pos/transactions/delivered=2026-09-13/"))
