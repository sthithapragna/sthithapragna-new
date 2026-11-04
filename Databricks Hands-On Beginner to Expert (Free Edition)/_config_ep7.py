# Databricks notebook source
# MAGIC %md
# MAGIC # Kestrel course: shared settings
# MAGIC Every episode runs this with `%run ./_config`. Change the catalog here, once, and every notebook follows.

# COMMAND ----------

CATALOG = "kestrel"   # use "workspace" if setup in episode 02 needed the fallback

LANDING = f"/Volumes/{CATALOG}/landing"
POS = f"{LANDING}/pos/transactions"
ECOM = f"{LANDING}/ecom/order_events"
CRM_CHANGES = f"{LANDING}/crm/member_changes"
CRM_EXPORT = f"{LANDING}/crm/members_full/members_export_2026-08-31.csv"
WMS = f"{LANDING}/wms/stock_snapshots"
REFERENCE = f"{LANDING}/reference"

REGIONS = ["LON", "SE", "SW", "MID", "NW", "NE", "YH", "SCO", "WAL"]

# COMMAND ----------

# MAGIC %md ## Declared schemas (added in episode 07). Infer to explore, declare to build.

# COMMAND ----------

POS_SCHEMA = """
    txn_id STRING, store_id STRING, till_id INT, txn_ts STRING, txn_type STRING,
    loyalty_card_no STRING, sku STRING, qty INT,
    unit_price DECIMAL(10,2), discount_amt DECIMAL(10,2), line_total DECIMAL(10,2),
    payment_type STRING, is_void STRING, promo_code STRING
"""
POS_TS_FORMAT = "dd/MM/yyyy HH:mm:ss"   # day first, UK local time, no zone

print(f"Kestrel settings loaded. Catalog: {CATALOG}")
