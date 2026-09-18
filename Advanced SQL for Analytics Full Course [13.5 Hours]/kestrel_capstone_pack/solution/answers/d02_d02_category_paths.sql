CREATE OR REPLACE TABLE d02_category_paths AS
WITH RECURSIVE down AS (
  SELECT category_key, parent_key, category_name,
         1 AS depth, [category_key] AS path, category_key AS root_key
    FROM dim_category
   WHERE parent_key IS NULL
  UNION ALL
  SELECT c.category_key, c.parent_key, c.category_name,
         w.depth + 1, list_append(w.path, c.category_key), w.root_key
    FROM dim_category c
    JOIN down w ON c.parent_key = w.category_key
   WHERE NOT list_contains(w.path, c.category_key)
     AND w.depth < 20
)
SELECT * FROM down;
