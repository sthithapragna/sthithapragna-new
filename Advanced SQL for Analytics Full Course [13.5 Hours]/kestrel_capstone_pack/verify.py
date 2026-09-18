#!/usr/bin/env python3
"""Capstone verifier for Advanced SQL for Analytics.

    python3 verify.py                  # check everything in ./answers
    python3 verify.py --only d03       # check one deliverable
    python3 verify.py --dir my_answers

Put one .sql file per deliverable in ./answers, named for the table it
builds, and have each file end with:

    CREATE OR REPLACE TABLE d03_trading_spells AS ...

Every deliverable is run TWICE, into two separate schemas, and the two
results are compared. A deliverable that passes its content checks but
differs between runs FAILS on determinism, because a query with a set of
permitted answers does not have an answer.

The checks never print the expected value for anything you have to work
out. They tell you which property failed and where to look.
"""
import argparse
import pathlib
import sys
import duckdb

DB = "kestrel.duckdb"
ANCHOR = "DATE '2025-02-03'"
CLOSE = "DATE '2026-08-31'"

RESET = "\033[0m"; RED = "\033[31m"; GRN = "\033[32m"; YEL = "\033[33m"; DIM = "\033[2m"


class Check:
    def __init__(self, con):
        self.con = con
        self.results = []

    def one(self, sql):
        return self.con.execute(sql).fetchone()[0]

    def assert_(self, label, sql, hint=""):
        try:
            ok = bool(self.one(sql))
        except Exception as e:
            self.results.append((False, label, f"query failed: {str(e)[:90]}"))
            return False
        self.results.append((ok, label, "" if ok else hint))
        return ok


# --------------------------------------------------------------- deliverables
def d01(c):
    c.assert_("one row per store per day",
              "SELECT COUNT(*) = COUNT(DISTINCT (store_key, date_key)) FROM d01_store_day",
              "the grain is store and day; something has duplicated it")
    c.assert_("every trading store, every day in the window",
              f"""SELECT COUNT(*) = (SELECT COUNT(*) FROM dim_store WHERE is_trading)
                    * (SELECT COUNT(*) FROM dim_date
                        WHERE cal_date BETWEEN {ANCHOR} AND {CLOSE})
                  FROM d01_store_day""",
              "closed days must be present as rows, not absent")
    c.assert_("closed days carry zero, not null",
              "SELECT COUNT(*) FILTER (WHERE net_sales IS NULL) = 0 FROM d01_store_day",
              "coalesce the measures, or a later LAG will see a null instead of a zero")
    c.assert_("net sales tie back to the fact table",
              """SELECT ROUND((SELECT SUM(net_sales) FROM d01_store_day), 2)
                       = ROUND((SELECT SUM(net_amount) FROM fact_sales_line), 2)""",
              "the spine must not have dropped or duplicated any sales")


def d02(c):
    c.assert_("no category reached twice",
              """SELECT COUNT(*) = COUNT(DISTINCT category_key) FROM d02_category_paths""",
              "a node appearing twice means the walk went round something")
    c.assert_("the walk terminated below the cap",
              "SELECT MAX(depth) < 20 FROM d02_category_paths",
              "if you are at the cap, the walk was truncated rather than finished")
    c.assert_("fewer nodes reached than the table holds",
              """SELECT (SELECT COUNT(*) FROM d02_category_paths)
                       < (SELECT COUNT(*) FROM dim_category)""",
              "some categories are unreachable from any root; think about why")
    c.assert_("every path starts at a root",
              """SELECT COUNT(*) = 0 FROM d02_category_paths p
                  WHERE p.path[1] NOT IN (SELECT category_key FROM dim_category
                                           WHERE parent_key IS NULL)""",
              "the first element of each path should be the root it descends from")


def d02c(c):
    c.assert_("the cycle probe found something",
              "SELECT COUNT(*) > 0 FROM d02_category_cycles",
              "walking upward from every node is what finds a loop the roots cannot reach")
    c.assert_("it found the right loop",
              """SELECT COUNT(*) > 0 FROM d02_category_cycles
                  WHERE list_contains(path, 4471) AND list_contains(path, 4498)""",
              "the loop should be visible in the path you carried")


def d03(c):
    c.assert_("spells cover every trading day, once",
              """SELECT (SELECT SUM(trading_days) FROM d03_trading_spells)
                       = (SELECT COUNT(*) FROM d01_store_day WHERE NOT was_closed)""",
              "a spell should span consecutive trading days and nothing else")
    c.assert_("no spell contains a closed day",
              """SELECT COUNT(*) = 0
                   FROM d03_trading_spells s
                   JOIN d01_store_day d
                     ON d.store_key = s.store_key
                    AND d.cal_date BETWEEN s.spell_from AND s.spell_to
                  WHERE d.was_closed""",
              "the islands must break at the gaps, not span them")
    c.assert_("spell count matches the closure pattern",
              """SELECT (SELECT COUNT(*) FROM d03_trading_spells)
                       = (SELECT COUNT(*) FROM dim_store WHERE is_trading)
                       + (SELECT COUNT(*) FROM stg_refurbishment)""",
              "each closure splits one store's history into one more spell")
    c.assert_("no two spells for a store overlap",
              """SELECT COUNT(*) = 0 FROM d03_trading_spells a JOIN d03_trading_spells b
                  ON a.store_key = b.store_key AND a.spell_from < b.spell_from
                 AND a.spell_to >= b.spell_from""",
              "overlapping islands mean the grouping key is not constant within a run")


def d04(c):
    c.assert_("every event belongs to exactly one session",
              """SELECT (SELECT SUM(events) FROM d04_sessions)
                       = (SELECT COUNT(*) FROM fact_app_event)""",
              "events must be partitioned by member, and none dropped")
    c.assert_("no session is longer than its events allow",
              """SELECT COUNT(*) = 0 FROM d04_sessions WHERE session_start > session_end""",
              "start and end are the min and max event time in the session")
    c.assert_("consecutive sessions are more than 30 minutes apart",
              """WITH s AS (
                   SELECT member_durable_key, session_start, session_end,
                          LAG(session_end) OVER (PARTITION BY member_durable_key
                                                 ORDER BY session_start) AS prev_end
                     FROM d04_sessions)
                 SELECT COUNT(*) = 0 FROM s
                  WHERE prev_end IS NOT NULL
                    AND session_start - prev_end <= INTERVAL 30 MINUTE""",
              "two sessions closer than the gap rule should have been one session")
    c.assert_("one row per member per session number",
              """SELECT COUNT(*) = COUNT(DISTINCT (member_durable_key, session_no))
                   FROM d04_sessions""",
              "the session number must be unique within a member")


def d05(c):
    c.assert_("spells cover every snapshot row",
              """SELECT (SELECT SUM(months) FROM d05_tier_spells)
                       = (SELECT COUNT(*) FROM snap_member_tier)""",
              "collapsing must not lose or duplicate a month")
    c.assert_("consecutive spells differ in tier",
              """WITH s AS (
                   SELECT member_durable_key, loyalty_tier, from_month,
                          LAG(loyalty_tier) OVER (PARTITION BY member_durable_key
                                                  ORDER BY from_month) AS prev
                     FROM d05_tier_spells)
                 SELECT COUNT(*) = 0 FROM s
                  WHERE prev IS NOT NULL AND prev IS NOT DISTINCT FROM loyalty_tier""",
              "two adjacent spells with the same tier should have been one spell")
    c.assert_("no member has overlapping spells",
              """SELECT COUNT(*) = 0 FROM d05_tier_spells a JOIN d05_tier_spells b
                  ON a.member_durable_key = b.member_durable_key
                 AND a.from_month < b.from_month AND a.to_month >= b.from_month""",
              "spells are disjoint by construction if the grouping key is right")


def d06(c):
    c.assert_("the sales grain survived",
              """SELECT (SELECT COUNT(*) FROM d06_price_as_at)
                       = (SELECT COUNT(*) FROM fact_sales_line)""",
              "an interval join that fans out has added rows; one price per line")
    c.assert_("every sale_key appears once",
              "SELECT COUNT(*) = COUNT(DISTINCT sale_key) FROM d06_price_as_at",
              "duplicated sale keys mean more than one price matched")
    c.assert_("no price is dated after its sale",
              """SELECT COUNT(*) = 0 FROM d06_price_as_at
                  WHERE effective_from IS NOT NULL AND effective_from > sold_date""",
              "as-at means the latest price at or before the sale, never after")
    c.assert_("no later price was available",
              """SELECT COUNT(*) = 0
                   FROM d06_price_as_at a
                   JOIN fact_price_change p
                     ON p.product_key = a.product_key AND p.store_key IS NULL
                    AND p.effective_from > a.effective_from
                    AND p.effective_from <= a.sold_date""",
              "you matched an earlier price when a nearer one existed")


def d07(c):
    c.assert_("one row per trading store",
              """SELECT (SELECT COUNT(*) FROM d07_store_scorecard)
                       = (SELECT COUNT(*) FROM dim_store WHERE is_trading)""",
              "the scorecard grain is the store")
    c.assert_("region shares sum to one, per region",
              """SELECT COUNT(*) = 0 FROM (
                   SELECT region_key, ROUND(SUM(share_of_region), 6) AS s
                     FROM d07_store_scorecard GROUP BY region_key)
                 WHERE ABS(s - 1) > 0.000001""",
              "a share's denominator must cover the whole region")
    c.assert_("nation shares sum to one",
              """SELECT ABS((SELECT SUM(share_of_nation) FROM d07_store_scorecard) - 1)
                       < 0.000001""",
              "if this sums to seven, the denominator is a region not the nation")
    c.assert_("region shares of the nation sum to one",
              """SELECT ABS((SELECT SUM(s) FROM (
                     SELECT DISTINCT region_key, region_share_of_nation AS s
                       FROM d07_store_scorecard)) - 1) < 0.000001""",
              "one value per region, and the seven of them must total one")
    c.assert_("the two levels multiply out",
              """SELECT COUNT(*) = 0 FROM d07_store_scorecard
                  WHERE ABS(share_of_region * region_share_of_nation
                            - share_of_nation) > 0.000001""",
              "share of region times region share of nation must equal share of nation")
    c.assert_("index averages to about 100 within a region",
              """SELECT COUNT(*) = 0 FROM (
                   SELECT region_key, AVG(index_vs_region) AS a
                     FROM d07_store_scorecard GROUP BY region_key)
                 WHERE ABS(a - 100) > 0.01""",
              "an index against the group mean averages to 100 by construction")
    c.assert_("ranks are dense from 1 within each region",
              """SELECT COUNT(*) = 0 FROM (
                   SELECT region_key, MIN(rank_in_region) mn,
                          COUNT(*) n, COUNT(DISTINCT rank_in_region) d
                     FROM d07_store_scorecard GROUP BY region_key)
                 WHERE mn <> 1 OR n <> d""",
              "with a unique tiebreaker no two stores share a rank")


def d08(c):
    c.assert_("region subtotals equal the sum of their formats",
              """SELECT COUNT(*) = 0 FROM (
                   SELECT r.region, ROUND(r.net_sales,2) AS sub,
                          ROUND(SUM(f.net_sales),2) AS parts
                     FROM d08_regional_pivot r
                     JOIN d08_regional_pivot f
                       ON f.region = r.region AND NOT f.is_region_subtotal
                                              AND NOT f.is_national_total
                    WHERE r.is_region_subtotal AND NOT r.is_national_total
                    GROUP BY r.region, r.net_sales)
                 WHERE ABS(sub - parts) > 0.01""",
              "a subtotal must equal the rows beneath it")
    c.assert_("the national total equals the sum of regions",
              """SELECT ABS(
                   (SELECT net_sales FROM d08_regional_pivot WHERE is_national_total)
                   - (SELECT SUM(net_sales) FROM d08_regional_pivot
                       WHERE is_region_subtotal AND NOT is_national_total)) < 0.01""",
              "the grand total is not the sum of every row; it is the sum of subtotals")
    c.assert_("subtotals are flagged, not inferred from nulls",
              """SELECT COUNT(*) > 0 FROM d08_regional_pivot WHERE is_region_subtotal""",
              "a real null and a subtotal null must be distinguishable")


def d09(c):
    c.assert_("every measure ties across all three sources",
              """SELECT COUNT(*) = 0 FROM d09_reconciliation
                  WHERE ABS(from_fact - from_model) > 0.01
                     OR ABS(from_fact - from_scorecard) > 0.01""",
              "a difference here means one layer dropped or duplicated rows")
    c.assert_("at least two measures were reconciled",
              "SELECT COUNT(*) >= 2 FROM d09_reconciliation",
              "reconcile a money measure and a count measure; they fail differently")


def d10(c):
    c.assert_("every assertion you wrote holds",
              "SELECT COUNT(*) FILTER (WHERE NOT holds) = 0 FROM d10_determinism",
              "your own assertions are failing; read the assertion column")
    c.assert_("you wrote at least six assertions",
              "SELECT COUNT(*) >= 6 FROM d10_determinism",
              "six is the minimum: grain, coverage, reconciliation, and determinism")


DELIVERABLES = [
    ("d01", "d01_store_day", "Complete the store-day series", d01),
    ("d02", "d02_category_paths", "Resolve the category hierarchy", d02),
    ("d02c", "d02_category_cycles", "Find the cycle the roots cannot reach", d02c),
    ("d03", "d03_trading_spells", "Trading spells across the gaps", d03),
    ("d04", "d04_sessions", "Sessionise the app events", d04),
    ("d05", "d05_tier_spells", "Collapse the tier snapshots", d05),
    ("d06", "d06_price_as_at", "Price as at the sale", d06),
    ("d07", "d07_store_scorecard", "The store scorecard", d07),
    ("d08", "d08_regional_pivot", "Regional summary with subtotals", d08),
    ("d09", "d09_reconciliation", "Reconcile, both directions", d09),
    ("d10", "d10_determinism", "Prove it", d10),
]


def determinism(con, table, sql):
    """Run the deliverable a second time and compare. Order must not matter."""
    try:
        con.execute(f"CREATE OR REPLACE TABLE __run1 AS SELECT * FROM {table}")
        con.execute(sql)
        con.execute(f"CREATE OR REPLACE TABLE __run2 AS SELECT * FROM {table}")
        diff = con.execute(f"""
            SELECT (SELECT COUNT(*) FROM (SELECT * FROM __run1 EXCEPT SELECT * FROM __run2))
                 + (SELECT COUNT(*) FROM (SELECT * FROM __run2 EXCEPT SELECT * FROM __run1))
        """).fetchone()[0]
        return diff == 0, diff
    except Exception as e:
        return False, str(e)[:80]
    finally:
        con.execute("DROP TABLE IF EXISTS __run1")
        con.execute("DROP TABLE IF EXISTS __run2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="answers")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()

    d = pathlib.Path(a.dir)
    if not d.exists():
        print(f"{RED}No answers directory at {d}{RESET}")
        sys.exit(2)

    con = duckdb.connect(a.db)
    total = passed = skipped = 0

    for tag, table, title, checker in DELIVERABLES:
        if a.only and not tag.startswith(a.only):
            continue
        f = next(iter(sorted(d.glob(f"{tag}_*.sql"))), None)
        print(f"\n{tag.upper():<5} {title}")
        if f is None:
            print(f"      {YEL}skipped{RESET} {DIM}(no {tag}_*.sql in {d}){RESET}")
            skipped += 1
            continue
        sql = f.read_text()
        try:
            con.execute(sql)
        except Exception as e:
            print(f"      {RED}FAIL{RESET}  the file did not run: {str(e)[:100]}")
            total += 1
            continue

        c = Check(con)
        checker(c)
        for ok, label, hint in c.results:
            total += 1
            if ok:
                passed += 1
                print(f"      {GRN}pass{RESET}  {label}")
            else:
                print(f"      {RED}FAIL{RESET}  {label}")
                if hint:
                    print(f"            {DIM}{hint}{RESET}")

        ok, info = determinism(con, table, sql)
        total += 1
        if ok:
            passed += 1
            print(f"      {GRN}pass{RESET}  identical on a second run")
        else:
            print(f"      {RED}FAIL{RESET}  the second run differed ({info} rows)")
            print(f"            {DIM}an ORDER BY somewhere does not uniquely identify a row{RESET}")

    print(f"\n{'-'*58}")
    print(f"  {passed}/{total} checks passed" + (f", {skipped} deliverables skipped" if skipped else ""))
    if skipped == 0 and passed == total:
        print(f"  {GRN}All deliverables pass. Read solution/ now, not before.{RESET}")
    con.close()
    sys.exit(0 if passed == total and skipped == 0 else 1)


if __name__ == "__main__":
    main()
