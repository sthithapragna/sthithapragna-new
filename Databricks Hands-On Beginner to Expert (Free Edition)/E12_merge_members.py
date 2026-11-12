# Databricks notebook source
# MAGIC %md
# MAGIC # A members table that is current every morning
# MAGIC **Asked by:** Callum Reid, Loyalty. New sign-ups in, changes applied, and anyone who asked to be erased, gone.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## Last episode's homework: EXCEPT looks one way

# COMMAND ----------

DSS = f"{CATALOG}.sandbox.daily_store_sales"
history = spark.sql(f"DESCRIBE HISTORY {DSS}")
v_delete = history.filter(F.col("operation") == "DELETE").agg(F.max("version")).first()[0]
v_update = history.filter(F.col("operation") == "UPDATE").agg(F.max("version")).first()[0]   # Thursday, after the rename
display(spark.sql(f"""
    SELECT * FROM {DSS} VERSION AS OF {v_update}
    EXCEPT
    SELECT * FROM {DSS} VERSION AS OF {v_delete - 1}""").orderBy("trading_date"))

# COMMAND ----------

from pyspark.sql import functions as F

MEMBERS = f"{CATALOG}.sandbox.members"

MEMBER_FIELDS = """
    member_id BIGINT, card_no STRING, first_name STRING, last_name STRING, email STRING,
    phone STRING, postcode STRING, home_store_id STRING, tier STRING, opt_in_marketing STRING,
    date_of_birth DATE, joined_date DATE
"""
MEMBER_COLS = [f.split()[0] for f in MEMBER_FIELDS.replace("\n", " ").split(",")]

CHANGES_SCHEMA = """
    op STRING, ts_ms BIGINT, member_id BIGINT,
    after STRUCT<member_id: BIGINT, card_no: STRING, first_name: STRING, last_name: STRING,
                 email: STRING, phone: STRING, postcode: STRING, home_store_id: STRING,
                 tier: STRING, opt_in_marketing: STRING, date_of_birth: DATE, joined_date: DATE,
                 updated_at: TIMESTAMP>,
    source STRUCT<db: STRING, table: STRING, lsn: BIGINT>
"""

# COMMAND ----------

# MAGIC %md ## 1. Start from the full export (31 August)

# COMMAND ----------

(spark.read.option("header", True).schema(MEMBER_FIELDS).csv(CRM_EXPORT)
      .withColumn("updated_at", F.lit("2026-08-31 23:59:59").cast("timestamp"))
      .write.mode("overwrite").saveAsTable(MEMBERS))
print(spark.table(MEMBERS).count(), "members")

# COMMAND ----------

# MAGIC %md ## 2. The first morning's changes

# COMMAND ----------

def read_changes(delivered):
    return (spark.read
            .schema(CHANGES_SCHEMA)
            .option("timestampFormat", "yyyy-MM-dd HH:mm:ss")
            .json(f"{CRM_CHANGES}/delivered={delivered}"))

day1 = read_changes("2026-09-02")
display(day1.groupBy("op").count().orderBy("op"))

# COMMAND ----------

display(day1.filter(F.col("op") == "d").select("op", "member_id", "after").limit(3))

# COMMAND ----------

# MAGIC %md ## 3. The usual template

# COMMAND ----------

day1.select("after.*").createOrReplaceTempView("e12_template_day1")

# COMMAND ----------

# MAGIC %sql
# MAGIC MERGE INTO kestrel.sandbox.members AS t
# MAGIC USING e12_template_day1 AS s
# MAGIC ON t.member_id = s.member_id
# MAGIC WHEN MATCHED THEN UPDATE SET *
# MAGIC WHEN NOT MATCHED THEN INSERT *

# COMMAND ----------

expected = 1_200_000 + day1.filter("op = 'c'").count() - day1.filter("op = 'd'").count()
members = spark.table(MEMBERS)
print("expected:", expected, "  got:", members.count())
print("rows with no member_id:", members.filter("member_id IS NULL").count())
print("erased member 10599802 still present:", members.filter("member_id = 10599802").count() == 1)

# COMMAND ----------

# MAGIC %md ## 4. Undo it (episode 11), then merge properly

# COMMAND ----------

history = spark.sql(f"DESCRIBE HISTORY {MEMBERS}")
v_merge = history.filter(F.col("operation") == "MERGE").agg(F.max("version")).first()[0]
spark.sql(f"RESTORE TABLE {MEMBERS} TO VERSION AS OF {v_merge - 1}")
print(spark.table(MEMBERS).count(), "members after restore")

# COMMAND ----------

def apply_changes(delivered):
    changes = read_changes(delivered)
    view = "e12_changes_" + delivered.replace("-", "_")          # a unique name per day (episode 06)
    (changes.select("op", "member_id",
                    F.timestamp_millis("ts_ms").alias("change_ts"),
                    *[F.col(f"after.{c}").alias(c) for c in MEMBER_COLS if c != "member_id"])
            .createOrReplaceTempView(view))
    return spark.sql(f"""
        MERGE INTO {MEMBERS} AS t
        USING {view} AS s
        ON t.member_id = s.member_id
        WHEN MATCHED AND s.op = 'd' THEN DELETE
        WHEN MATCHED AND s.change_ts > t.updated_at THEN UPDATE SET
            card_no = s.card_no, first_name = s.first_name, last_name = s.last_name,
            email = s.email, phone = s.phone, postcode = s.postcode,
            home_store_id = s.home_store_id, tier = s.tier, opt_in_marketing = s.opt_in_marketing,
            date_of_birth = s.date_of_birth, joined_date = s.joined_date,
            updated_at = s.change_ts
        WHEN NOT MATCHED AND s.op <> 'd' THEN INSERT
            (member_id, card_no, first_name, last_name, email, phone, postcode,
             home_store_id, tier, opt_in_marketing, date_of_birth, joined_date, updated_at)
            VALUES (s.member_id, s.card_no, s.first_name, s.last_name, s.email, s.phone, s.postcode,
             s.home_store_id, s.tier, s.opt_in_marketing, s.date_of_birth, s.joined_date, s.change_ts)
    """)

# COMMAND ----------

display(apply_changes("2026-09-02"))

# COMMAND ----------

members = spark.table(MEMBERS)
print("expected:", expected, "  got:", members.count())
print("rows with no member_id:", members.filter("member_id IS NULL").count())
print("erased member 10599802 still present:", members.filter("member_id = 10599802").count() == 1)
display(members.filter("member_id = 10930888").select("member_id", "email", "tier", "updated_at"))

# COMMAND ----------

# MAGIC %md ## 5. Safe to rerun?

# COMMAND ----------

display(apply_changes("2026-09-02"))

# COMMAND ----------

# MAGIC %md ## 6. The next morning

# COMMAND ----------

display(apply_changes("2026-09-03"))

# COMMAND ----------

print(spark.table(MEMBERS).count(), "members")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer for Callum
# MAGIC **`kestrel.sandbox.members`**: 1,200,901 members after the changes delivered on 2 and 3 September.
# MAGIC Sign-ups are inserted, changes applied only if newer than what we hold, and erasures deleted (16 and 17).
# MAGIC The merge is safe to rerun. Season 3 automates this with AUTO CDC.


# COMMAND ----------

# MAGIC %md
# MAGIC ## Homework
# MAGIC Apply the third morning, straight after this episode (the table holds the changes delivered on 2 and 3 September):
# MAGIC
# MAGIC ```python
# MAGIC display(apply_changes("2026-09-04"))
# MAGIC ```
# MAGIC
# MAGIC 1. **How many members does Callum have afterwards?** Check it against a sum you can do yourself.
# MAGIC 2. **How many of that morning's update records (`op = 'u'`) were skipped as older than what the table already held?**
# MAGIC
# MAGIC Put your answer in the comments. I'll show mine at the start of episode 13.

# COMMAND ----------

# Your answer here
