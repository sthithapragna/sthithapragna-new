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
