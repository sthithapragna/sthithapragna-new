# Functional Specification — Work Order Parts Consumption and Backlog

**Program:** Field Service Analytics
**Source system:** Meridian FS
**Target:** Field Service Data Warehouse (`fs_dw`)

---

## Business Requirement

Parts consumption against field service work orders has grown faster than work order
volume over the last two years. Because parts are issued from three different stock
location schemes and reconciled in a separate finance system, it is difficult to give
planners a credible view of what is actually being consumed, or of which parts are
holding up released work. This limits the ability to set reorder points sensibly and
results in both stockouts on fast-moving parts and dead stock on slow ones.

This specification covers the warehouse assets required to support the Work Order
Parts and Backlog dashboard.

## Key Objectives

- Provide a comprehensive, credible view of parts consumption by part and site over
  rolling 12, 24 and 60 month windows.
- Enable planners to identify parts blocking released work orders.
- Support filtering by:
  - Planned vs unplanned parts
  - Corrective / Preventive / Project work order categories
  - Crew

## General Note on Reporting Impacts

This functional spec was used to build the assets supporting the Parts and Backlog
dashboard and continues to be modified for changes requested. However, the assets
created for this effort are used in several reports, and any change to these tables
can impact other dashboards. Reports currently reading these tables:

- Work Order Parts and Backlog (this effort)
- Crew Productivity
- Asset Reliability Summary
- Stock Location Health (in flight)

## Change Log

| Date | Change | Updated by |
|---|---|---|
| 03/14/24 | Approval | R. Nkomo |
| 04/02/24 | Confirmed that shortfall is not required below part / site for the legacy Talon source. We will roll up to part / site. | M. Feld |
| 09/19/24 | Added crew code to technician dimension to support crew-level dispatch reporting. | M. Feld |
| 11/08/24 | Corrected typo — the repairable part type should be ZRPS, not ZRPR. | M. Feld |
| 02/27/25 | EDL ingestion retired. All source reads move to the SRC ODS view layer. No functional change intended. | D. Achterberg |
| 06/11/25 | Shortfall calculation moved from part / site to part / site / stock location grain. | M. Feld |
| 01/22/26 | Aligned and signed. | RN |
| 04/30/26 | New section added for consumption movement type governance. | M. Feld |

---

## Data Sources Required

Meridian FS — see Source System Spreadsheet (Meridian FS)

- Work Order
  - WAUF — work order header
  - WOPR — work order operations
  - WRES — work order reservations
  - WSTT — object status records
  - T401 — work order type text
- Parts
  - PMAT — part master
  - PMATS — part at site
  - WMOV — parts movements against work orders
- Technician
  - TECH — technician master
  - TECHT — technician text
- Asset
  - ASSM — asset master
  - ASST — asset text

---

## Grain Decisions

- Meridian FS holds parts at part / site / stock location. Consumption and reservation
  are both maintained at that grain.
- Business has requested consumption be reported at **part / site** only. The stock
  location detail is not required on the consumption dashboard, though there are use
  cases in Stock Location Health where the lower grain adds value.
- Shortfall is calculated at **part / site / stock location**. Because the maximum
  stock level is only maintained at part / site, the quantity reserved in each stock
  location is compared against the part / site maximum. This carries a small risk of
  understatement, considered immaterial against the benefit of presenting shortfall
  at the lower grain.
- There are only four cases where a part carries reservations in more than one stock
  location and shortfall was previously calculated by summing at part / site. Moving to
  the new method reduced total shortfall by a quantity of 3.
- The legacy Talon source can only go to part / site. Its measures are held at that
  grain and are out of scope for this specification.

## Stock Location Scope

Only two stock locations are in scope:

- **1000** — main storeroom. Always in scope.
- **2000** — satellite crib. In scope only for repairable and consumable part types.

All other stock locations are excluded.

## Consumption Movement Type Governance

*Added 04/30/26.*

Parts consumption is a net figure. Movements that issue stock to a work order increase
consumption; movements that return stock from a work order decrease it. Transfers
between stock locations are not consumption and must be excluded on both sides.

The authoritative list of issue and return movement types is maintained by the
Materials Management team and is reviewed each quarter. The list in effect at the time
of a given load is what the calculation uses. Certain part types are also excluded from
consumption entirely — obsolete parts, and kit headers whose components are counted
separately.

Refer to the Movement Type Governance register maintained by Materials Management for
the current list.

---

## Open Items

- Slow mover indicator is defined but not yet populated. Deferred to a later phase.
- Unit cost currency conversion for the two Canadian sites is not yet implemented.
  All values are currently reported in the transaction currency.
