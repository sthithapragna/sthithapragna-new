# Databricks notebook source
# MAGIC %md
# MAGIC # Stores by format, for any region
# MAGIC **Asked by:** Grace Liu, Finance. **Question:** how many stores of each format are in a region?
# MAGIC
# MAGIC Pick a region in the widget at the top, then Run all.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

dbutils.widgets.dropdown("region", "MID", REGIONS, "Region")

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

# MAGIC %md
# MAGIC ## Checking the Genie Code answer
# MAGIC Read the whole folder, as the generated code did, and compare with the latest snapshot.

# COMMAND ----------

all_files = (spark.read
             .option("header", True)
             .csv(f"{REFERENCE}/stores/"))
print(all_files.count(), "rows from the whole folder, against", stores.count(), "stores")
display(all_files.select("_metadata.file_name").distinct())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick Fix
# MAGIC This cell has a typo on purpose. Run it, then use Genie Code's Quick Fix.

# COMMAND ----------

display(stores.groupBy("fromat").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Grace (Midlands)
# MAGIC | Format | Stores |
# MAGIC |---|---|
# MAGIC | Dark | 4 |
# MAGIC | Express | 15 |
# MAGIC | Local | 32 |
# MAGIC | Superstore | 15 |
# MAGIC | **Total** | **66** |
# MAGIC
# MAGIC Source: stores reference snapshot of 23 September 2026. Includes Solihull Local (0413), opened 20 September.
