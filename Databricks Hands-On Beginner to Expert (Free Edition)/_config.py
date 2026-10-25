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

print(f"Kestrel settings loaded. Catalog: {CATALOG}")
