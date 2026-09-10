# Course Materials - AI for Data Engineers

The worked example used throughout the course. A field service warehouse
built on a fictional ERP called Meridian FS.

## The three artifacts

| File | What it is |
|---|---|
| `MERIDIAN_FS_Mapping_Document_v1.0.xlsx` | The mapping document, written at go-live and never updated since |
| `FS_Functional_Spec_WO_Parts_and_Backlog.md` | The functional spec, maintained through 2026. Read the change log |
| `fs_wo_procedures.sql` | The eight stored procedures that actually run |

All three describe the same system. They disagree with each other in eight
places, and the code contains fourteen defects on top of that.

## How to use them

Work through them in the order the course does.

1. **Module 2.** Run the three reconciliation prompts against the mapping
   document and the SQL. Try to find the disagreements before the module
   shows you where they are.
2. **Module 3.** Build the consumption query from the mapping document alone.
   Then compare it to what the code does. The gap is the lesson.
3. **Module 4.** Run the structure map against `usp_load_dim_work_order_fs`.
   It is a three-branch union and one of its columns is polymorphic.
4. **Modules 5 to 9.** The defects for debugging, performance, migration and
   review are all in the same file.

You do not need a database. Everything in the course is done by reading these
three files against each other.

## A note on the material

This is not a real company's project. Names, schemas, table names, column
names and business details are all invented. The failure modes are not.
Every drift point and every defect is a pattern taken from real warehouse
work, reconstructed here so it can be taught without exposing anyone's data.
