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
