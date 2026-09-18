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
