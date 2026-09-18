#!/usr/bin/env python3
"""Build kestrel.duckdb for the Advanced SQL for Analytics capstone.

Every quirk from the frozen landscape is generated into the data rather
than described, so the capstone's failure modes are real:

  1  sold_ts is second precision; ~31% of transactions tie inside a second
  2  txn_id is unique per store per day only, never globally
  3  fact_app_event has no session identifier; 30 minutes of inactivity
  4  dim_category contains a cycle: 4471 -> 4498 -> 4471
  5  promo_key is null on ~62% of sales lines
  6  63 refurbishment closures, median 19 days, so store-day series has gaps
  7  promotions overlap; a product can sit in several at once
  8  dim_customer is SCD2; as-was is the default join
  9  ledger postings back-dated up to 45 days: posted_ts <> effective_date
 10  three employees form a management loop after a TUPE load
 11  customer_key is null on ~38% of sales lines (guest transactions)
 12  discount_amount is null, not zero, on non-promotional lines
 13  dim_product_excluded holds 214 rows, one with a null product_key
 14  ~1,400 products have never recorded a sale

Scaled down from the landscape's 2.41bn sales lines so the file runs on a
laptop. Proportions are preserved, so every percentage quoted in the
course still holds.
"""
import argparse
import pathlib
import duckdb

DDL = []


def step(label, sql):
    DDL.append((label, sql))


# ------------------------------------------------------------------ calendar
step("dim_date", """
CREATE OR REPLACE TABLE dim_date AS
WITH d AS (
  SELECT (DATE '2019-01-01' + INTERVAL (n) DAY)::DATE AS cal_date
    FROM range(0, 4018) t(n)
),
anchored AS (
  -- retail year starts on the Sunday after the Saturday nearest 31 Jan
  SELECT cal_date,
         DATE_DIFF('day', DATE '2022-02-06', cal_date) AS days_from_epoch
    FROM d
)
SELECT
  CAST(STRFTIME(cal_date, '%Y%m%d') AS INTEGER)        AS date_key,
  cal_date,
  DAYOFWEEK(cal_date)                                  AS day_of_week,
  STRFTIME(cal_date, '%Y-%m')                          AS calendar_month,
  -- 4-4-5: 52-week years from the 2022-02-06 epoch
  CAST(FLOOR(days_from_epoch / 364.0) + 2022 AS INTEGER)            AS retail_year,
  CAST(FLOOR((days_from_epoch % 364) / 7.0) + 1 AS INTEGER)         AS retail_week,
  CAST(FLOOR(days_from_epoch / 364.0) * 100
       + FLOOR((days_from_epoch % 364) / 7.0) + 1 AS INTEGER)       AS retail_week_key,
  CAST(FLOOR(days_from_epoch / 364.0) * 100
       + FLOOR((days_from_epoch % 364) / 7.0) + 1 - 52 AS INTEGER)  AS comparable_week_ly
FROM anchored
WHERE days_from_epoch >= 0;
""")

# ------------------------------------------------------------------- stores
step("dim_store", """
CREATE OR REPLACE TABLE dim_store AS
SELECT
  n + 1                                              AS store_key,
  'Store ' || LPAD((n + 1)::VARCHAR, 4, '0')         AS store_name,
  CAST(((n * 7919) % 7) + 1 AS INTEGER)              AS region_key,
  CAST(((n * 104729) % 58) + 1 AS INTEGER)           AS area_key,
  CASE WHEN n < 412 THEN true ELSE false END         AS is_trading,
  CASE WHEN (n * 31) % 100 < 22 THEN 'Convenience'
       WHEN (n * 31) % 100 < 78 THEN 'Supermarket'
       ELSE 'Superstore' END                         AS store_format
FROM range(0, 449) t(n);
""")

# closures: 63 of them, median around 19 days
step("stg_refurbishment", """
CREATE OR REPLACE TABLE stg_refurbishment AS
SELECT
  ((n * 61) % 412) + 1                                                 AS store_key,
  (DATE '2025-03-01' + INTERVAL (((n * 137) % 520)) DAY)::DATE         AS closed_from,
  (DATE '2025-03-01' + INTERVAL (((n * 137) % 520)) DAY
     + INTERVAL (8 + ((n * 53) % 23)) DAY)::DATE                       AS closed_to
FROM range(0, 63) t(n);
""")

# ---------------------------------------------------------------- categories
# 4,912 nodes over six levels. Keys 4471 and 4498 are made to point at each
# other, which is the merchandising correction of 2024-03-11.
step("dim_category", """
CREATE OR REPLACE TABLE dim_category AS
WITH base AS (
  SELECT n + 1 AS category_key,
         CASE WHEN n + 1 <=   12 THEN 1
              WHEN n + 1 <=   72 THEN 2
              WHEN n + 1 <=  312 THEN 3
              WHEN n + 1 <= 1212 THEN 4
              WHEN n + 1 <= 3412 THEN 5
              ELSE 6 END AS lvl
    FROM range(0, 4912) t(n)
),
parented AS (
  SELECT category_key, lvl,
         CASE lvl
           WHEN 1 THEN NULL
           WHEN 2 THEN ((category_key * 13) %   12) + 1
           WHEN 3 THEN ((category_key * 13) %   60) + 13
           WHEN 4 THEN ((category_key * 13) %  240) + 73
           WHEN 5 THEN ((category_key * 13) %  900) + 313
           ELSE       ((category_key * 13) % 2200) + 1213
         END AS parent_key
    FROM base
)
SELECT category_key,
       CASE WHEN category_key = 4471 THEN 4498
            WHEN category_key = 4498 THEN 4471
            -- 40 real categories hang beneath the cycle, so a downward walk
            -- from the roots silently omits 42 nodes rather than looping
            WHEN category_key BETWEEN 4800 AND 4839 THEN 4471
            ELSE parent_key END AS parent_key,
       CASE WHEN category_key = 4471 THEN 'Chilled Desserts'
            WHEN category_key = 4498 THEN 'Ambient Desserts'
            -- names deliberately repeat across branches
            ELSE ['Seasonal','Everyday','Core Range','Premium','Value',
                  'Local','Own Label','Branded','Bakery','Chilled',
                  'Frozen','Ambient'][(category_key % 12) + 1]
                 || ' ' || ((category_key % 37) + 1)::VARCHAR END AS category_name,
       lvl AS declared_level
  FROM parented;
""")

# ------------------------------------------------------------------ products
step("dim_product", """
CREATE OR REPLACE TABLE dim_product AS
SELECT
  n + 1000                                                   AS product_key,
  'SKU ' || LPAD((n + 1000)::VARCHAR, 6, '0')                AS product_name,
  ((n * 1543) % 1500) + 3413                                 AS category_key,
  ROUND(0.45 + ((n * 7919) % 2400) / 100.0, 2)               AS list_price,
  CASE WHEN n < 61400 THEN true ELSE false END               AS is_ranged
FROM range(0, 84000) t(n);
""")

# 214 excluded products, one of which has a null key
step("dim_product_excluded", """
CREATE OR REPLACE TABLE dim_product_excluded AS
SELECT CASE WHEN n = 99 THEN NULL ELSE ((n * 389) % 84000) + 1000 END AS product_key,
       CASE WHEN n % 3 = 0 THEN 'staff purchase' ELSE 'test product' END AS reason
  FROM range(0, 214) t(n);
""")

# ----------------------------------------------------------------- employees
# 61,200 employees, max depth 9, plus 88104 -> 88251 -> 88377 -> 88104
step("dim_employee", """
CREATE OR REPLACE TABLE dim_employee AS
WITH base AS (
  SELECT n + 80000 AS employee_key,
         CASE WHEN n < 4 THEN NULL
              ELSE 80000 + CAST(FLOOR((n - 1) / 6) AS INTEGER) END AS mgr
    FROM range(0, 61200) t(n)
)
SELECT employee_key,
       CASE WHEN employee_key = 88104 THEN 88251
            WHEN employee_key = 88251 THEN 88377
            WHEN employee_key = 88377 THEN 88104
            ELSE mgr END AS manager_key,
       'Employee ' || employee_key::VARCHAR AS employee_name,
       CASE WHEN employee_key IN (88104, 88251, 88377)
            THEN 'TUPE transfer 2025' ELSE 'core' END AS loaded_from
  FROM base;
""")

# ---------------------------------------------------------------- promotions
step("dim_promotion", """
CREATE OR REPLACE TABLE dim_promotion AS
SELECT
  n + 1                                                                AS promo_key,
  'Promotion ' || (n + 1)::VARCHAR                                     AS promo_name,
  (DATE '2025-02-03' + INTERVAL (((n * 97) % 560)) DAY)::DATE          AS effective_from,
  (DATE '2025-02-03' + INTERVAL (((n * 97) % 560)) DAY
     + INTERVAL (13 + ((n * 29) % 30)) DAY)::DATE                      AS effective_to
FROM range(0, 6840) t(n);
""")

# ------------------------------------------------------------------ members
# SCD2 customer dimension: 50,000 durable members, ~4 versions each
step("dim_customer", """
CREATE OR REPLACE TABLE dim_customer AS
WITH v AS (
  SELECT (n % 50000) + 1                    AS member_durable_key,
         CAST(n / 50000 AS INTEGER)         AS version_no
    FROM range(0, 200000) t(n)
)
SELECT ROW_NUMBER() OVER (ORDER BY member_durable_key, version_no) AS customer_key,
       member_durable_key,
       (DATE '2025-02-03' + INTERVAL (version_no * 140) DAY)::DATE  AS valid_from,
       CASE WHEN version_no = 3 THEN DATE '9999-12-31'
            ELSE (DATE '2025-02-03' + INTERVAL ((version_no+1) * 140) DAY
                  - INTERVAL 1 DAY)::DATE END                       AS valid_to,
       version_no = 3                                               AS is_current,
       'Postcode ' || LPAD(((member_durable_key * 37) % 9000)::VARCHAR, 4, '0')
                                                                    AS postcode
  FROM v;
""")

# monthly tier snapshot: the thing the learner must collapse into spells
step("snap_member_tier", """
CREATE OR REPLACE TABLE snap_member_tier AS
SELECT m.member_durable_key,
       d.retail_year * 100 + CAST(CEIL(d.retail_week / 4.0) AS INTEGER) AS retail_month_key,
       ['Bronze','Silver','Gold','Platinum'][
         (CAST(FLOOR((m.member_durable_key * 7 + d.retail_week) / 11.0) AS INTEGER) % 4) + 1
       ] AS loyalty_tier
  FROM (SELECT DISTINCT member_durable_key FROM dim_customer) m
 CROSS JOIN (SELECT DISTINCT retail_year, retail_week FROM dim_date
              WHERE cal_date BETWEEN DATE '2025-02-03' AND DATE '2026-08-31'
                AND retail_week % 4 = 1) d;
""")

# ------------------------------------------------------------------- prices
step("fact_price_change", """
CREATE OR REPLACE TABLE fact_price_change AS
SELECT
  ROW_NUMBER() OVER ()                                                 AS price_change_key,
  p.product_key,
  CASE WHEN (p.product_key * n) % 9 = 0
       THEN ((p.product_key * 3) % 412) + 1 ELSE NULL END              AS store_key,
  (DATE '2025-02-03' + INTERVAL ((n * 90 + (p.product_key % 60))) DAY)::DATE
                                                                       AS effective_from,
  ROUND(p.list_price * (0.82 + ((p.product_key * (n+1)) % 40) / 100.0), 2)
                                                                       AS price
FROM dim_product p, range(0, 6) t(n)
WHERE p.is_ranged;
""")

# ------------------------------------------------------------------- ledger
step("fact_ledger", """
CREATE OR REPLACE TABLE fact_ledger AS
SELECT
  ROW_NUMBER() OVER ()                                                 AS ledger_key,
  ((n * 17) % 412) + 1                                                 AS store_key,
  ((n * 29) %  40) + 1                                                 AS account_key,
  (TIMESTAMP '2025-02-03 00:00:00' + INTERVAL ((n * 13) % 13000) HOUR) AS posted_ts,
  -- back-dated by up to 45 days: effective_date <> posted_ts::DATE
  ((TIMESTAMP '2025-02-03 00:00:00' + INTERVAL ((n * 13) % 13000) HOUR)
     - INTERVAL (CASE WHEN n % 7 = 0 THEN (n % 45) ELSE 0 END) DAY)::DATE
                                                                       AS effective_date,
  ROUND((((n * 7919) % 200000) - 100000) / 100.0, 2)                   AS amount
FROM range(0, 400000) t(n);
""")

SALES = """
CREATE OR REPLACE TABLE fact_sales_line AS
WITH days AS (
  SELECT cal_date, date_key
    FROM dim_date
   WHERE cal_date BETWEEN DATE '2025-02-03' AND DATE '2026-08-31'
),
open_days AS (
  SELECT s.store_key, d.cal_date, d.date_key
    FROM dim_store s
   CROSS JOIN days d
   WHERE s.is_trading
     AND NOT EXISTS (SELECT 1 FROM stg_refurbishment r
                      WHERE r.store_key = s.store_key
                        AND d.cal_date BETWEEN r.closed_from AND r.closed_to)
),
txns AS (
  -- txn_id restarts at 1 for every store every day: unique per store per day
  SELECT o.store_key, o.cal_date, o.date_key,
         t.n + 1 AS txn_id,
         hash(o.store_key, o.date_key, t.n)     AS ht,   -- transaction-level
         hash(t.n, o.date_key, o.store_key, 97) AS hs    -- independent draw
    FROM open_days o,
         range(0, {TXN_PER_DAY}) t(n)
),
lines AS (
  SELECT x.*, l.n + 1 AS line_no,
         hash(x.store_key, x.date_key, x.txn_id, l.n, 7919) AS hl  -- line-level
    FROM txns x,
         range(0, 4) l(n)
   WHERE l.n < 1 + (x.ht % 4)
)
SELECT
  ROW_NUMBER() OVER ()                                          AS sale_key,
  txn_id,
  line_no,
  store_key,
  date_key,
  -- second precision. 41% of multi-line transactions land in one second,
  -- which is ~31% of all transactions once single-line ones are counted.
  (cal_date::TIMESTAMP
     + INTERVAL (7 + (ht % 15)) HOUR
     + INTERVAL ((ht // 7) % 60) MINUTE
     + INTERVAL (CASE WHEN hs % 100 < 41 THEN (ht // 11) % 60
                      ELSE ((ht // 11) + line_no * 7) % 60 END) SECOND)
                                                                AS sold_ts,
  -- guest shopping is a property of the transaction, not of the line
  CASE WHEN hs % 100 < 38 THEN NULL
       ELSE (ht % 50000) + 1 END                                AS member_durable_key,
  -- ranged keys run 1000..62399; only 1000..60999 ever sell,
  -- so exactly 1,400 ranged products have never recorded a sale
  (hl % 60000) + 1000                                           AS product_key,
  1 + (hl % 3)                                                  AS qty,
  ROUND(0.60 + ((hl // 3) % 3800) / 100.0, 2)                   AS net_amount,
  -- promo_key null on ~62% of lines
  CASE WHEN (hl // 7) % 100 < 62 THEN NULL
       ELSE ((hl // 13) % 6840) + 1 END                         AS promo_key,
  -- discount_amount is NULL, not zero, when there is no promotion
  CASE WHEN (hl // 7) % 100 < 62 THEN NULL
       ELSE ROUND(((hl // 17) % 400) / 100.0, 2) END            AS discount_amount,
  1 + ((hl // 19) % 4)                                          AS tender_key
FROM lines;
"""

APP = """
CREATE OR REPLACE TABLE fact_app_event AS
WITH members AS (
  SELECT (n % 50000) + 1 AS member_durable_key,
         CAST(n / 50000 AS INTEGER) AS session_no,
         hash(n, 4099) AS hs
    FROM range(0, {SESSIONS}) t(n)          -- sessions per member
),
sessions AS (
  SELECT member_durable_key, session_no, hs,
         -- sessions land days apart, at plausible hours
         TIMESTAMP '2026-02-02 00:00:00'
           + INTERVAL ((hs % 200)) DAY
           + INTERVAL (7 + (hs // 7) % 15) HOUR
           + INTERVAL ((hs // 11) % 60) MINUTE AS session_start,
         1 + (hs % 12) AS n_events            -- 1 to 12 events per session
    FROM members
),
ev AS (
  SELECT s.member_durable_key, s.session_no, s.session_start, s.hs,
         e.n AS event_no,
         hash(s.member_durable_key, s.session_no, e.n, 7919) AS he
    FROM sessions s, range(0, 12) e(n)
   WHERE e.n < s.n_events
)
SELECT
  ROW_NUMBER() OVER ()                                          AS event_key,
  member_durable_key,
  -- events inside a session are 0 to 4 minutes apart, so a 30-minute
  -- rule keeps them together, and the next session is days away
  (session_start
     + INTERVAL (event_no * (he % 5)) MINUTE
     + INTERVAL ((he // 3) % 60) SECOND)                        AS event_ts,
  ['view','search','add_to_basket','checkout','login','browse',
   'wishlist','review','share','scan','offer_view','store_locator',
   'receipt','reorder','support','settings','notification','logout'
  ][CAST(he % 18 AS INTEGER) + 1]                               AS event_type,
  ['ios','android','web'][CAST(ev.hs % 3 AS INTEGER) + 1]       AS device_type,
  'screen_' || ((he // 17) % 40)::VARCHAR                       AS screen
FROM ev;
"""


def build(path, scale):
    txn_per_day = {"small": 4, "full": 12}[scale]
    sessions  = {"small": 100_000, "full": 400_000}[scale]  # member-sessions

    p = pathlib.Path(path)
    if p.exists():
        p.unlink()
    con = duckdb.connect(str(p))
    con.execute("SET preserve_insertion_order = false;")

    for label, sql in DDL:
        con.execute(sql)
        n = con.execute(f"SELECT COUNT(*) FROM {label}").fetchone()[0]
        print(f"  {label:<24} {n:>12,}")

    con.execute(SALES.replace("{TXN_PER_DAY}", str(txn_per_day)))
    n = con.execute("SELECT COUNT(*) FROM fact_sales_line").fetchone()[0]
    print(f"  {'fact_sales_line':<24} {n:>12,}")

    con.execute(APP.replace("{SESSIONS}", str(sessions)))
    n = con.execute("SELECT COUNT(*) FROM fact_app_event").fetchone()[0]
    print(f"  {'fact_app_event':<24} {n:>12,}")

    con.close()
    print(f"\n  written -> {p}  ({p.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="kestrel.duckdb")
    ap.add_argument("--scale", choices=["small", "full"], default="full")
    a = ap.parse_args()
    build(a.out, a.scale)
