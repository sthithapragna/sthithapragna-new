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
