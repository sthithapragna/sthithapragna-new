-- Episode 05: first SQL with read_files
-- Run each query on its own in the SQL Editor. If you used the fallback catalog in
-- episode 02, replace /Volumes/kestrel/ with /Volumes/workspace/ everywhere.

-- Episode 04's homework: which stores_demo does UNDROP bring back?
DROP TABLE IF EXISTS workspace.default.stores_demo;
CREATE TABLE workspace.default.stores_demo AS
SELECT * FROM read_files('/Volumes/kestrel/landing/reference/stores/stores_2026-09-23.csv');
DROP TABLE workspace.default.stores_demo;                         -- version 1: 413 stores
CREATE TABLE workspace.default.stores_demo AS
SELECT * FROM read_files('/Volumes/kestrel/landing/reference/stores/stores_2026-09-23.csv')
WHERE region_code = 'LON';
DROP TABLE workspace.default.stores_demo;                         -- version 2: 55 stores
UNDROP TABLE workspace.default.stores_demo;
SELECT COUNT(*) AS stores FROM workspace.default.stores_demo;     -- 55
-- Version 1 is still listed by SHOW TABLES DROPPED IN workspace.default, with its table ID.
-- To get it back: ALTER TABLE workspace.default.stores_demo RENAME TO workspace.default.stores_london;
--                 UNDROP TABLE WITH ID '<table id of version 1>';

-- 1. One raw till file, straight from the volume
SELECT *
FROM read_files('/Volumes/kestrel/landing/pos/transactions/delivered=2026-09-02/pos_LON_2026-09-01.csv')
LIMIT 10;

-- 2. How many lines in that one file?
SELECT COUNT(*) AS lines
FROM read_files('/Volumes/kestrel/landing/pos/transactions/delivered=2026-09-02/pos_LON_2026-09-01.csv');

-- 3. Every till file at once, counted per delivery day
SELECT delivered, COUNT(*) AS lines
FROM read_files('/Volumes/kestrel/landing/pos/transactions/', format => 'csv')
GROUP BY delivered
ORDER BY delivered;

-- 4. Tom's question: how busy was each region on Wednesday 16 September?
SELECT split(_metadata.file_name, '_')[1]                 AS region,
       COUNT(DISTINCT txn_id)                            AS baskets,
       COUNT(*)                                          AS lines,
       ROUND(COUNT(*) / COUNT(DISTINCT txn_id), 2)       AS lines_per_basket
FROM read_files('/Volumes/kestrel/landing/pos/transactions/', format => 'csv')
WHERE txn_ts LIKE '16/09/2026%'
GROUP BY 1
ORDER BY baskets DESC;

-- 5. Where did Scotland's rows come from?
SELECT _metadata.file_name AS file_name, delivered, COUNT(*) AS lines
FROM read_files('/Volumes/kestrel/landing/pos/transactions/', format => 'csv')
WHERE txn_ts LIKE '16/09/2026%'
  AND split(_metadata.file_name, '_')[1] = 'SCO'
GROUP BY 1, 2
ORDER BY 2;

-- 6. Today's patch: leave out re-sent files (episode 19 does this properly)
SELECT split(_metadata.file_name, '_')[1]                 AS region,
       COUNT(DISTINCT txn_id)                            AS baskets,
       COUNT(*)                                          AS lines,
       ROUND(COUNT(*) / COUNT(DISTINCT txn_id), 2)       AS lines_per_basket
FROM read_files('/Volumes/kestrel/landing/pos/transactions/', format => 'csv')
WHERE txn_ts LIKE '16/09/2026%'
  AND _metadata.file_name NOT LIKE '%resend%'
GROUP BY 1
ORDER BY baskets DESC;

-- 7. read_files works out JSON by itself: web order events for the same day
SELECT event_type, COUNT(*) AS events
FROM read_files('/Volumes/kestrel/landing/ecom/order_events/delivered=2026-09-17/')
GROUP BY event_type
ORDER BY events DESC;

-- 8. The version Tom keeps: pick any day with the :day parameter, e.g. 16/09/2026
SELECT split(_metadata.file_name, '_')[1]                 AS region,
       COUNT(DISTINCT txn_id)                            AS baskets,
       COUNT(*)                                          AS lines,
       ROUND(COUNT(*) / COUNT(DISTINCT txn_id), 2)       AS lines_per_basket
FROM read_files('/Volumes/kestrel/landing/pos/transactions/', format => 'csv')
WHERE txn_ts LIKE concat(:day, '%')
  AND _metadata.file_name NOT LIKE '%resend%'
GROUP BY 1
ORDER BY baskets DESC;

-- Homework
-- Using read_files on the whole till folder, which was Kestrel's busiest trading day in September, by baskets, and how many baskets did it have?
-- 
-- Hint: left(txn_ts, 10) is the trading day, written day first, like 16/09/2026.
-- 
-- Put your answer in the comments. The answer is at the start of episode 06.
