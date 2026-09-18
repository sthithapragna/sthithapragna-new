CREATE OR REPLACE TABLE d04_sessions AS
WITH flagged AS (
  SELECT member_durable_key, event_key, event_ts, event_type,
         CASE WHEN event_ts - LAG(event_ts) OVER w > INTERVAL 30 MINUTE
                OR LAG(event_ts) OVER w IS NULL
              THEN 1 ELSE 0 END AS is_new_session
    FROM fact_app_event
  WINDOW w AS (PARTITION BY member_durable_key ORDER BY event_ts, event_key)
),
numbered AS (
  SELECT *,
         SUM(is_new_session) OVER (
           PARTITION BY member_durable_key
           ORDER BY event_ts, event_key
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS session_no
    FROM flagged
)
SELECT member_durable_key, session_no,
       MIN(event_ts)                                   AS session_start,
       MAX(event_ts)                                   AS session_end,
       COUNT(*)                                        AS events,
       COUNT(*) FILTER (WHERE event_type = 'checkout') AS checkouts
  FROM numbered
 GROUP BY member_durable_key, session_no;
