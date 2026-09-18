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
