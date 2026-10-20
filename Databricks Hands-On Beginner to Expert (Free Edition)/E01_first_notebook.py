# Databricks notebook source
# MAGIC %md
# MAGIC # Episode 01: your first notebook
# MAGIC Attach to **Serverless** (top right), then run each cell with Shift+Enter.

# COMMAND ----------

# MAGIC %md ## 1. Read a table with Python

# COMMAND ----------

trips = spark.read.table("samples.nyctaxi.trips")
display(trips.limit(10))

# COMMAND ----------

# MAGIC %md ## 2. The same data with SQL, in the same notebook

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT pickup_zip,
# MAGIC        COUNT(*)                   AS trips,
# MAGIC        ROUND(AVG(fare_amount), 2) AS avg_fare
# MAGIC FROM samples.nyctaxi.trips
# MAGIC GROUP BY pickup_zip
# MAGIC ORDER BY trips DESC
# MAGIC LIMIT 10

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Code from an older tutorial
# MAGIC Both of the next two cells fail on Free Edition. That is the point: read the errors.

# COMMAND ----------

sc = spark.sparkContext
sc.parallelize(range(10)).count()

# COMMAND ----------

dbutils.fs.ls("/FileStore/tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. The same work, written for today
# MAGIC DataFrames instead of RDDs, and a Unity Catalog volume instead of `/FileStore`.

# COMMAND ----------

spark.range(10).count()

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE VOLUME IF NOT EXISTS workspace.default.scratch
# MAGIC COMMENT 'A place for files, instead of /FileStore'

# COMMAND ----------

dbutils.fs.put("/Volumes/workspace/default/scratch/hello.txt", "Hello from a volume", overwrite=True)
display(dbutils.fs.ls("/Volumes/workspace/default/scratch"))
