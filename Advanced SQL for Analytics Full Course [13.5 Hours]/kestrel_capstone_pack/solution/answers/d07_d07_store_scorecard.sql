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
