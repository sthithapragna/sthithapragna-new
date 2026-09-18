# The Kestrel Capstone

**Advanced SQL for Analytics — the project.**

Everything in this course has been a technique shown against a fictional
grocer. This is that grocer, as a real database on your laptop, with every
defect the course described actually present in the data. Ten deliverables.
Between them they need most of the twenty-six modules.

Nobody marks this but you, and the marking is the point: the harness checks
the same properties module 20 taught you to assert, and it runs every
deliverable twice to see whether it gives the same answer.

---

## Setup

```bash
pip install duckdb
python3 verify.py --only d01      # will report "skipped" until you write d01
```

`kestrel.duckdb` is 170 MB and needs nothing else. No warehouse, no account,
no cluster. If you would rather rebuild it, or build a smaller copy:

```bash
python3 build_kestrel.py kestrel.duckdb --scale small
```

DuckDB was chosen because it supports **every construct this course
teaches**: `QUALIFY`, `ROWS`/`RANGE`/`GROUPS` frames, `EXCLUDE`,
`WITH RECURSIVE`, `PERCENTILE_CONT`, `GROUPING SETS`, `PIVOT`, `ASOF JOIN`,
`IS DISTINCT FROM`, `FILTER`, and `IGNORE NULLS`. One note: DuckDB writes
`IGNORE NULLS` **inside** the parentheses — `LAG(x IGNORE NULLS) OVER (...)`
— which is a third syntax position, different from both Redshift and
Postgres 19.

---

## How to submit

Write one `.sql` file per deliverable into `answers/`, named for the table
it builds. Each file ends with a `CREATE OR REPLACE TABLE`:

```
answers/d03_trading_spells.sql   ->   CREATE OR REPLACE TABLE d03_trading_spells AS ...
```

Then:

```bash
python3 verify.py                 # everything
python3 verify.py --only d03      # one deliverable
```

Deliverables build on each other: `d03`, `d07` and `d08` read `d01`, so run
`d01` first. The harness does not tell you the expected values for anything
you have to work out. It names the property that failed and where to look.

---

## What the data actually contains

Not described — **generated**. You will meet all of this:

| | |
|---|---|
| `sold_ts` is second precision | **30.8%** of transactions have two or more lines in one second |
| `txn_id` | unique per store per day, **never globally** |
| `promo_key` | null on **62%** of sales lines |
| `member_durable_key` | null on **38%** of lines — guest shopping |
| `discount_amount` | **null, not zero**, when there is no promotion |
| `fact_app_event` | has **no session identifier**. A session is 30 minutes of inactivity |
| `dim_category` | contains a cycle: 4471 ↔ 4498, with 40 real categories beneath it |
| `dim_employee` | contains a three-node management loop, 88104 → 88251 → 88377 |
| refurbishment closures | 63 of them, median 20 days, so the store-day series **has gaps** |
| `dim_product_excluded` | 214 rows, **one with a null `product_key`** |
| ranged products | exactly **1,400 have never recorded a sale** |
| `fact_ledger` | postings back-dated up to 45 days: `posted_ts` ≠ `effective_date` |
| `dim_customer` | SCD2, four versions per member |
| `dim_promotion` | ~355 promotions live on any given day, so they overlap constantly |

`stg_refurbishment` is in the database and **is the answer key for d03**.
The harness reads it to check your work. You should not.

---

## The ten deliverables

### d01 — Complete the store-day series → `d01_store_day`
*Modules 6, 11.*

One row per trading store per day between 2025-02-03 and 2026-08-31, with
net sales, line count and basket count. **Days when a store was closed must
be present as rows carrying zero**, not absent.

This is the deliverable everything else stands on, and it is the fix module
6 kept pointing at: once the series is complete, "the previous row" and
"the previous day" are the same row again.

### d02 — Resolve the category hierarchy → `d02_category_paths`
*Modules 11, 12.*

Every category reachable from a root, with its depth, the path of keys from
the root, and which root it belongs to.

You will not reach all 4,912 categories, and that is correct. Work out why
before assuming your query is broken.

### d02c — Find the cycle → `d02_category_cycles`
*Module 12.*

The loop that d02 could not see, with the route it takes.

A node inside a cycle has its parent inside the cycle, so a downward walk
from the roots can never arrive at it — it finishes quickly and silently
omits the whole subtree. This deliverable needs the walk that **does** hang
if you write it without a guard.

### d03 — Trading spells → `d03_trading_spells`
*Module 13.*

One row per unbroken run of trading days per store: store, first day, last
day, number of days. A refurbishment closure ends one spell and starts the
next.

Derive it from d01. Do not read `stg_refurbishment`.

### d04 — Sessionise the app events → `d04_sessions`
*Modules 6, 13.*

One row per member per session: start, end, event count, and how many of
those events were checkouts. A session ends after **30 minutes of
inactivity**.

2 million events, no session column. This is the deliverable where the
first event of each member is the edge case.

### d05 — Collapse the tier snapshots → `d05_tier_spells`
*Module 13.*

`snap_member_tier` holds one row per member per retail month. Turn it into
spells: member, tier, from month, to month, number of months. Two adjacent
months on the same tier are one spell, not two.

### d06 — Price as at the sale → `d06_price_as_at`
*Modules 6, 15.*

Every sales line with the national price that applied on the day it sold.

**Exactly one row per sales line.** An interval join that fans out is the
failure mode here, and the harness checks both that the grain survived and
that you did not match an earlier price when a nearer one existed.

### d07 — The store scorecard → `d07_store_scorecard`
*Modules 4, 5, 7, 9.*

One row per trading store: net sales, baskets, mean basket, share of its
region, share of the nation, its region's share of the nation, an index
against the regional average (base 100), rank within region, and cumulative
distribution within region.

The harness checks that **share of region × region share of nation = share
of nation**. Module 7's scenario 1 is exactly the defect that breaks it, and
shares summing to 1.0 will not catch it.

### d08 — Regional summary with subtotals → `d08_regional_pivot`
*Modules 16, 19.*

Net sales by region and store format, with a subtotal per region and a
national total, in one pass. Carry explicit flags distinguishing a subtotal
row from a detail row — **a real null and a subtotal null must be
distinguishable**.

### d09 — Reconcile, both directions → `d09_reconciliation`
*Modules 18, 20.*

At least two measures — one money, one count — traced from the raw fact
through d01 and out to d07, proving all three agree.

A money measure and a count measure fail differently. That is why you need
both.

### d10 — Prove it → `d10_determinism`
*Modules 2, 5, 20.*

Your own assertions, at least six, as rows of `(assertion, holds)`. Every
one must hold. Cover grain, coverage, reconciliation, and anywhere you
believe an ordering is total.

This is the deliverable that grades the other nine. Writing assertions that
pass tells you nothing; writing the ones that would have caught your own
mistakes is the exercise.

---

## What the harness checks, and what it does not

It checks **properties**, not values: grain uniqueness, coverage, whether
shares sum and multiply out, whether spells tile without overlapping,
whether an as-at join found the nearest earlier row.

It runs each deliverable **twice** and compares. A deliverable that passes
its content checks and differs between runs fails, because a query with a
set of permitted answers does not have an answer.

**Be honest about that last check.** DuckDB on one machine is often stable
even for an under-specified query, so passing it is a backstop rather than a
proof. The guarantee comes from writing the total order, not from the test
agreeing with itself twice. Module 2 made this argument; the harness cannot
make it for you.

---

## When you are done

`solution/` holds a worked answer to all ten. **Read it after `verify.py`
passes, not before.** It is not the only correct answer to any deliverable,
and where your approach differs and still passes, yours is as good.
