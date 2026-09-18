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
