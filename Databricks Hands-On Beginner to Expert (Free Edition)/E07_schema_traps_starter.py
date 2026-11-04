# Databricks notebook source
# MAGIC %md
# MAGIC # Why does my chart say 9 January?
# MAGIC **Asked by:** Grace Liu, Finance. Baskets per day for the first week of September came out as
# MAGIC 9 January to 9 July, and there is a store "1" that is not in the store list.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Episode 06's homework: London's week 3 (trading 15 to 21 September)

# COMMAND ----------

hw_lon = (spark.read
          .option("header", True)
          .option("basePath", POS)
          .csv(f"{POS}/delivered=*/pos_LON_*.csv")
          .filter(F.col("is_void") == "N")
          .withColumn("qty", F.col("qty").cast("int")))
week3 = (hw_lon.filter(F.col("delivered").between("2026-09-16", "2026-09-22"))   # trading 15 to 21 September
               .groupBy("sku").agg(F.sum("qty").alias("units"))
               .orderBy(F.desc("units"), "sku")
               .limit(10))
display(week3)

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md ## 1. What Spark guesses from one file

# COMMAND ----------

one = (spark.read
       .option("header", True)
       .option("inferSchema", True)
       .csv(f"{POS}/delivered=2026-09-02/pos_LON_2026-09-01.csv"))
one.printSchema()
display(one.limit(5))

# COMMAND ----------

# MAGIC %md ## 2. Grace's chart: baskets per day, first week

# COMMAND ----------

week1 = (spark.read
         .option("header", True)
         .option("inferSchema", True)
         .csv([f"{POS}/delivered=2026-09-0{d}" for d in range(2, 9)]))

# COMMAND ----------

display(week1
        .withColumn("trading_date", F.to_date("txn_ts", "MM/dd/yyyy HH:mm:ss"))
        .groupBy("trading_date")
        .agg(F.countDistinct("txn_id").alias("baskets"))
        .orderBy("trading_date"))

# COMMAND ----------

display(week1
        .withColumn("trading_date", F.to_date("txn_ts", "dd/MM/yyyy HH:mm:ss"))
        .groupBy("trading_date")
        .agg(F.countDistinct("txn_id").alias("baskets"))
        .orderBy("trading_date"))

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT to_date('16/09/2026 10:00:00', 'MM/dd/yyyy HH:mm:ss')

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT try_to_timestamp('16/09/2026 10:00:00', 'MM/dd/yyyy HH:mm:ss') AS parsed

# COMMAND ----------

# MAGIC %md ## 3. The whole folder

# COMMAND ----------

all_pos = (spark.read
           .option("header", True)
           .option("inferSchema", True)
           .csv(POS))
all_pos.printSchema()

# COMMAND ----------

display(all_pos.agg(F.sum("line_total")))

# COMMAND ----------

display(all_pos
        .filter(F.col("store_id") == "store_id")
        .select("_metadata.file_name", "txn_id", "store_id", "qty", "line_total"))

# COMMAND ----------

# MAGIC %md ## 4. Declare the schema instead
# MAGIC `POS_SCHEMA` now lives in `_config`, so every later episode uses the same types.

# COMMAND ----------

print(POS_SCHEMA)

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

display(pos.filter(F.col("txn_id") == "txn_id")
           .select("_metadata.file_name", "txn_id", "store_id", "till_id", "qty", "line_total"))

# COMMAND ----------

# Type this cell along with the video

# COMMAND ----------

# MAGIC %md ## 5. JSON guesses too: the same field, two days

# COMMAND ----------

for day in ["2026-09-06", "2026-09-12"]:
    events = spark.read.json(f"{ECOM}/delivered={day}")
    price = [f for f in events.schema["items"].dataType.elementType.fields if f.name == "unit_price"][0]
    print(day, "items.unit_price is", price.dataType.simpleString())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Grace
# MAGIC Kestrel's tills write dates **day first** (`dd/MM/yyyy`). Parsed that way, the first week is 1 to 7 September,
# MAGIC busiest on Saturday 5 September (19,958 baskets). Store "1" is store `0001`: the leading zeros were lost when
# MAGIC Spark guessed the column was a number. From now on we read the tills with a declared schema, `POS_SCHEMA`.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC App version 5.2 started sending `unit_price` as text on **10 September**.
# MAGIC
# MAGIC Change the JSON loop in section 5 to check the web event deliveries from `2026-09-08` to `2026-09-12`.
# MAGIC **Which is the first delivery folder where Spark infers `items.unit_price` as a string, and why that day?**
# MAGIC
# MAGIC Put your answer in the comments. The answer is at the start of episode 08.

# COMMAND ----------

# Your answer here
