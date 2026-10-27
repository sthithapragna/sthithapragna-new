# Databricks notebook source
# MAGIC %md
# MAGIC # Where Kestrel's data lives
# MAGIC **Asked by:** Dan Mercer, Information Security, through Meera.
# MAGIC **Question:** where exactly does the loyalty data live, and who can see it?

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Episode 03's homework: North West Superstores, with a second widget

# COMMAND ----------

hw_latest = spark.read.option("header", True).csv(f"{REFERENCE}/stores/stores_2026-09-23.csv")
hw_folder = spark.read.option("header", True).csv(f"{REFERENCE}/stores/")
nw_superstores = "region_code = 'NW' AND format = 'Superstore'"
print("latest snapshot:", hw_latest.filter(nw_superstores).count())
print("whole folder:   ", hw_folder.filter(nw_superstores).count())

# COMMAND ----------

# MAGIC %md ## 1. Where am I?

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT current_catalog() AS catalog, current_schema() AS schema

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW CATALOGS

# COMMAND ----------

# MAGIC %md ## 2. Walk down Kestrel's levels

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW SCHEMAS IN kestrel

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW VOLUMES IN kestrel.landing

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE VOLUME kestrel.landing.crm

# COMMAND ----------

display(dbutils.fs.ls(f"{LANDING}/crm/members_full/"))

# COMMAND ----------

# MAGIC %md ## 3. The catalog describes itself

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT volume_schema, volume_name, volume_type, volume_owner
# MAGIC FROM kestrel.information_schema.volumes
# MAGIC ORDER BY volume_schema, volume_name

# COMMAND ----------

# MAGIC %md ## 4. Two-part names depend on where you are

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG workspace;
# MAGIC SHOW VOLUMES IN landing

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW VOLUMES IN kestrel.landing

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. A managed table, dropped by mistake
# MAGIC A scratch table in the `workspace` catalog, so Kestrel's catalog stays clean.

# COMMAND ----------

stores = spark.read.option("header", True).csv(f"{REFERENCE}/stores/stores_2026-09-23.csv")
stores.write.mode("overwrite").saveAsTable("workspace.default.stores_demo")

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE TABLE EXTENDED workspace.default.stores_demo

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS stores FROM workspace.default.stores_demo

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP TABLE workspace.default.stores_demo

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS stores FROM workspace.default.stores_demo

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW TABLES DROPPED IN workspace.default

# COMMAND ----------

# MAGIC %sql
# MAGIC UNDROP TABLE workspace.default.stores_demo

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS stores FROM workspace.default.stores_demo

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Dan
# MAGIC - **Where:** the managed volume `kestrel.landing.crm`, in storage managed by Unity Catalog.
# MAGIC - **Owner:** the person who ran setup in episode 02.
# MAGIC - **Who can see it:** the owner, and anyone granted access. Nothing has been granted yet.
# MAGIC - **Risk to fix:** `members_export_2026-08-31.csv` holds names, emails, phone numbers and dates of birth in plain text.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Undrop, twice over. Using the `stores` DataFrame and the scratch table from section 5:
# MAGIC
# MAGIC 1. `DROP TABLE workspace.default.stores_demo` (the 413-store table).
# MAGIC 2. Save London's stores under the same name: `stores.filter(stores.region_code == "LON").write.saveAsTable("workspace.default.stores_demo")`
# MAGIC 3. `DROP TABLE workspace.default.stores_demo` again.
# MAGIC 4. `UNDROP TABLE workspace.default.stores_demo`, then count its rows.
# MAGIC
# MAGIC **What count do you get, and why?**
# MAGIC
# MAGIC Put your answer in the comments. The answer is at the start of episode 05.

# COMMAND ----------

# Your answer here
