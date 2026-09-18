#!/usr/bin/env python3
"""Reference solution for the Advanced SQL for Analytics capstone.

Read this AFTER verify.py passes, not before. Each deliverable names the
modules it draws on. Every query here is deterministic by construction:
every ORDER BY that feeds a LIMIT, a ROW_NUMBER or a frame ends in a
unique column, and every aggregate window states its frame explicitly.
"""
import duckdb
import sys
import time

SOL = {}

# -- 1 ----------------------------------------------------------- m06, m11
SOL["d01_store_day"] = """
CREATE OR REPLACE TABLE d01_store_day AS
WITH spine AS (                       -- every trading store x every day
  SELECT s.store_key, d.date_key, d.cal_date
    FROM dim_store s
   CROSS JOIN dim_date d
   WHERE s.is_trading
     AND d.cal_date BETWEEN DATE '2025-02-03' AND DATE '2026-08-31'
),
actual AS (
  SELECT store_key, date_key,
         SUM(net_amount)                    AS net_sales,
         COUNT(*)                           AS lines,
         COUNT(DISTINCT txn_id)             AS baskets
    FROM fact_sales_line
   GROUP BY store_key, date_key
)
SELECT sp.store_key, sp.date_key, sp.cal_date,
       COALESCE(a.net_sales, 0)             AS net_sales,
       COALESCE(a.lines, 0)                 AS lines,
       COALESCE(a.baskets, 0)               AS baskets,
       a.store_key IS NULL                  AS was_closed
  FROM spine sp
  LEFT JOIN actual a
    ON a.store_key = sp.store_key AND a.date_key = sp.date_key;
"""

# -- 2 ----------------------------------------------------- m11, m12
# Two walks, because the two directions fail differently. Downward from the
# roots SILENTLY OMITS the cycle and its subtree; it never loops. Upward
# from every node LOOPS FOREVER unless guarded. You need both.
SOL["d02_category_paths"] = """
CREATE OR REPLACE TABLE d02_category_paths AS
WITH RECURSIVE down AS (
  SELECT category_key, parent_key, category_name,
         1 AS depth, [category_key] AS path, category_key AS root_key
    FROM dim_category
   WHERE parent_key IS NULL
  UNION ALL
  SELECT c.category_key, c.parent_key, c.category_name,
         w.depth + 1, list_append(w.path, c.category_key), w.root_key
    FROM dim_category c
    JOIN down w ON c.parent_key = w.category_key
   WHERE NOT list_contains(w.path, c.category_key)
     AND w.depth < 20
)
SELECT * FROM down;
"""

SOL["d02_category_cycles"] = """
CREATE OR REPLACE TABLE d02_category_cycles AS
WITH RECURSIVE up AS (
  SELECT category_key AS start_key, category_key AS node,
         [category_key] AS path, false AS is_cycle
    FROM dim_category
  UNION ALL
  SELECT u.start_key, p.category_key,
         list_append(u.path, p.category_key),
         list_contains(u.path, p.category_key)
    FROM up u
    JOIN dim_category c ON c.category_key = u.node
    JOIN dim_category p ON p.category_key = c.parent_key
   WHERE NOT u.is_cycle
     AND len(u.path) < 25
)
SELECT DISTINCT start_key, path
  FROM up
 WHERE is_cycle;
"""

# -- 3 -------------------------------------------------------------- m13
# Gaps and islands, derived from the facts alone. stg_refurbishment is the
# answer key and must not be read here.
SOL["d03_trading_spells"] = """
CREATE OR REPLACE TABLE d03_trading_spells AS
WITH traded AS (
  SELECT store_key, cal_date,
         ROW_NUMBER() OVER (PARTITION BY store_key ORDER BY cal_date) AS rn
    FROM d01_store_day
   WHERE NOT was_closed
),
grouped AS (
  SELECT store_key, cal_date,
         cal_date - INTERVAL (rn) DAY AS grp   -- the row_number difference
    FROM traded
)
SELECT store_key,
       MIN(cal_date) AS spell_from,
       MAX(cal_date) AS spell_to,
       COUNT(*)      AS trading_days
  FROM grouped
 GROUP BY store_key, grp;
"""

# -- 4 -------------------------------------------------------- m06, m13
SOL["d04_sessions"] = """
CREATE OR REPLACE TABLE d04_sessions AS
WITH flagged AS (
  SELECT member_durable_key, event_key, event_ts, event_type,
         CASE WHEN event_ts - LAG(event_ts) OVER w > INTERVAL 30 MINUTE
                OR LAG(event_ts) OVER w IS NULL
              THEN 1 ELSE 0 END AS is_new_session
    FROM fact_app_event
  WINDOW w AS (PARTITION BY member_durable_key ORDER BY event_ts, event_key)
),
numbered AS (
  SELECT *,
         SUM(is_new_session) OVER (
           PARTITION BY member_durable_key
           ORDER BY event_ts, event_key
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS session_no
    FROM flagged
)
SELECT member_durable_key, session_no,
       MIN(event_ts)                                   AS session_start,
       MAX(event_ts)                                   AS session_end,
       COUNT(*)                                        AS events,
       COUNT(*) FILTER (WHERE event_type = 'checkout') AS checkouts
  FROM numbered
 GROUP BY member_durable_key, session_no;
"""

# -- 5 -------------------------------------------------------------- m13
SOL["d05_tier_spells"] = """
CREATE OR REPLACE TABLE d05_tier_spells AS
WITH marked AS (
  SELECT member_durable_key, retail_month_key, loyalty_tier,
         CASE WHEN loyalty_tier IS DISTINCT FROM
                   LAG(loyalty_tier) OVER (PARTITION BY member_durable_key
                                           ORDER BY retail_month_key)
              THEN 1 ELSE 0 END AS changed
    FROM snap_member_tier
),
grouped AS (
  SELECT *,
         SUM(changed) OVER (PARTITION BY member_durable_key
                            ORDER BY retail_month_key
                            ROWS BETWEEN UNBOUNDED PRECEDING
                                     AND CURRENT ROW) AS spell_no
    FROM marked
)
SELECT member_durable_key, spell_no, loyalty_tier,
       MIN(retail_month_key) AS from_month,
       MAX(retail_month_key) AS to_month,
       COUNT(*)              AS months
  FROM grouped
 GROUP BY member_durable_key, spell_no, loyalty_tier;
"""

# -- 6 -------------------------------------------------------- m06, m15
SOL["d06_price_as_at"] = """
CREATE OR REPLACE TABLE d06_price_as_at AS
WITH national AS (                    -- one price per product per date
  SELECT product_key, effective_from, price
    FROM fact_price_change
   WHERE store_key IS NULL
   QUALIFY ROW_NUMBER() OVER (PARTITION BY product_key, effective_from
                              ORDER BY price_change_key DESC) = 1
),
sale AS (
  SELECT sale_key, product_key, store_key, sold_ts::DATE AS sold_date, net_amount
    FROM fact_sales_line
)
SELECT s.sale_key, s.product_key, s.store_key, s.sold_date,
       s.net_amount, n.price AS price_as_at, n.effective_from
  FROM sale s
  ASOF LEFT JOIN national n
    ON s.product_key = n.product_key
   AND s.sold_date  >= n.effective_from;
"""

# -- 7 --------------------------------------------- m04, m05, m07, m09
SOL["d07_store_scorecard"] = """
CREATE OR REPLACE TABLE d07_store_scorecard AS
WITH base AS (
  SELECT d.store_key, s.region_key,
         SUM(d.net_sales)  AS net_sales,
         SUM(d.baskets)    AS baskets
    FROM d01_store_day d
    JOIN dim_store s ON s.store_key = d.store_key
   GROUP BY d.store_key, s.region_key
),
national AS (SELECT SUM(net_sales) AS total_net FROM base)
SELECT b.store_key, b.region_key, b.net_sales, b.baskets,
       b.net_sales / NULLIF(b.baskets, 0)                       AS mean_basket,
       b.net_sales / SUM(b.net_sales) OVER (PARTITION BY b.region_key)
                                                                AS share_of_region,
       b.net_sales / n.total_net                                AS share_of_nation,
       SUM(b.net_sales) OVER (PARTITION BY b.region_key) / n.total_net
                                                                AS region_share_of_nation,
       100.0 * b.net_sales
         / NULLIF(AVG(b.net_sales) OVER (PARTITION BY b.region_key), 0)
                                                                AS index_vs_region,
       RANK()      OVER (PARTITION BY b.region_key
                         ORDER BY b.net_sales DESC, b.store_key) AS rank_in_region,
       CUME_DIST() OVER (PARTITION BY b.region_key
                         ORDER BY b.net_sales)                   AS cume_dist_in_region,
       COUNT(*)    OVER (PARTITION BY b.region_key)              AS stores_in_region
  FROM base b CROSS JOIN national n;
"""

# -- 8 -------------------------------------------------------- m16, m19
SOL["d08_regional_pivot"] = """
CREATE OR REPLACE TABLE d08_regional_pivot AS
WITH m AS (
  SELECT s.region_key, d.store_format,
         SUM(f.net_sales) AS net_sales
    FROM d01_store_day f
    JOIN dim_store s ON s.store_key = f.store_key
    JOIN dim_store d ON d.store_key = f.store_key
   GROUP BY GROUPING SETS ((s.region_key, d.store_format),
                           (s.region_key), ())
)
SELECT COALESCE(region_key::VARCHAR, 'ALL')      AS region,
       COALESCE(store_format, 'ALL FORMATS')     AS store_format,
       region_key IS NULL                        AS is_national_total,
       store_format IS NULL                      AS is_region_subtotal,
       net_sales
  FROM m;
"""

# -- 9 -------------------------------------------------------- m18, m20
SOL["d09_reconciliation"] = """
CREATE OR REPLACE TABLE d09_reconciliation AS
SELECT 'net_sales'  AS measure,
       (SELECT ROUND(SUM(net_amount), 2) FROM fact_sales_line)   AS from_fact,
       (SELECT ROUND(SUM(net_sales),  2) FROM d01_store_day)     AS from_model,
       (SELECT ROUND(SUM(net_sales),  2) FROM d07_store_scorecard) AS from_scorecard
UNION ALL
SELECT 'baskets',
       (SELECT COUNT(*) FROM (SELECT DISTINCT store_key, date_key, txn_id
                                FROM fact_sales_line)),
       (SELECT SUM(baskets) FROM d01_store_day),
       (SELECT SUM(baskets) FROM d07_store_scorecard);
"""

# -- 10 ------------------------------------------------------- m02, m05
SOL["d10_determinism"] = """
CREATE OR REPLACE TABLE d10_determinism AS
SELECT 'd03 spells cover all trading days' AS assertion,
       (SELECT SUM(trading_days) FROM d03_trading_spells)
         = (SELECT COUNT(*) FROM d01_store_day WHERE NOT was_closed) AS holds
UNION ALL
SELECT 'd02 downward walk omits the poisoned subtree',
       (SELECT COUNT(*) FROM d02_category_paths)
         < (SELECT COUNT(*) FROM dim_category)
UNION ALL
SELECT 'd02 upward probe found the planted cycle',
       (SELECT COUNT(*) FROM d02_category_cycles) > 0
UNION ALL
SELECT 'd02 no node reached twice downward',
       (SELECT COUNT(*) FROM d02_category_paths)
         = (SELECT COUNT(DISTINCT category_key) FROM d02_category_paths)
UNION ALL
SELECT 'd05 spells cover every snapshot row',
       (SELECT SUM(months) FROM d05_tier_spells)
         = (SELECT COUNT(*) FROM snap_member_tier)
UNION ALL
SELECT 'd06 kept the sales grain',
       (SELECT COUNT(*) FROM d06_price_as_at)
         = (SELECT COUNT(*) FROM fact_sales_line)
UNION ALL
SELECT 'd07 region shares sum to one',
       (SELECT ROUND(SUM(share_of_region), 4) FROM d07_store_scorecard)
         = (SELECT COUNT(DISTINCT region_key) FROM d07_store_scorecard);
"""


def main(db="kestrel.duckdb"):
    con = duckdb.connect(db)
    for name, sql in SOL.items():
        t0 = time.time()
        try:
            con.execute(sql)
            n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            print(f"  {name:<24} {n:>12,} rows   {time.time()-t0:5.1f}s")
        except Exception as e:
            print(f"  {name:<24} FAILED: {str(e)[:120]}")
            sys.exit(1)
    print("\n  d10 assertions:")
    for a, h in con.execute("SELECT assertion, holds FROM d10_determinism").fetchall():
        print(f"    {'PASS' if h else 'FAIL'}  {a}")
    print("\n  d09 reconciliation:")
    for r in con.execute("SELECT * FROM d09_reconciliation").fetchall():
        print(f"    {r}")
    con.close()


if __name__ == "__main__":
    main(*sys.argv[1:])
