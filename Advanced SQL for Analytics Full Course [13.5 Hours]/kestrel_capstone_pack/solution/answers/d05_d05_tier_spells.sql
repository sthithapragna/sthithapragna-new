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
