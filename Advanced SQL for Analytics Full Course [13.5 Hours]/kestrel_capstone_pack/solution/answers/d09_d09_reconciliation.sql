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
