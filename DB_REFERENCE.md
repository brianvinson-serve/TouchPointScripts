# TouchPoint Database Reference - RockPointe
**Last Updated:** 2026-08-13

This doc captures confirmed IDs, table structures, and join patterns discovered
by running queries against the live rockpointe.tpsdb.com instance.

Full structural inventory source: `data-dictionary-expander/exports/2026-08-13/rockpointe-touchpoint-data-dictionary-2026-08-13.csv` (collected 2026-08-13 through TouchPoint `q.QuerySql`; 505 tables/views, 4,539 columns, 457 primary-key columns, 456 foreign-key columns, 781 index-key columns, zero probe errors). Focused evidence: `data-dictionary-expander/exports/2026-08-13/rockpointe-touchpoint-focused-confirmation-2026-08-13.csv` (61 aggregate/lookup rows, zero probe errors). Human-readable summaries are under `data-dictionary-expander/reports/2026-08-13/`.

Structural metadata confirms object/column/key existence. Status/type meanings and value behavior below are documented only where the focused live export or prior RPC testing supplied evidence.

---

## Programs

| ProgId | Name |
|--------|------|
| 1109   | Student Ministry (SM) |
| 1130   | CT Admin |
| 1138   | RP PS Children |
| 1141   | RP PS Students |

---

## SM Divisions (all ProgId = 1109)

| Division.Id | Division.Name |
|-------------|---------------|
| 11 | SM Sundays |
| 12 | SM Classes |
| 21 | SM Events |
| 42 | SM Wednesdays |
| 45 | SM Mission Trips |
| 108 | SM Admin |

---

## Organization Type IDs (updated 2026-07-08 from full org scan)

| OrganizationTypeId | Meaning |
|--------------------|---------|
| 106 | Students (RPC Students, student D groups) |
| 156 | **NOT in use for Sunday attendance orgs** -- original SQL assumption was wrong; no SM CC/PS orgs use this TypeId |
| 176 | **NOT in use for Sunday attendance orgs** -- original SQL assumption was wrong; no SM CC/PS orgs use this TypeId |
| 201 | Sunday grade orgs (SM: CC/PS 6th-12th Guys/Girls) AND Wednesday class orgs (D Groups, Apologetics, etc.) -- primary student attendance TypeId |
| 202 | Mission trips |
| 203 | Events (e.g. Paint War) |
| 205 | Older/historical orgs -- Sunday Volunteers pre-2024, Wednesday PS WED grade orgs, archived classes. StatusId filter keeps these out of live reports unless specifically included. |
| 207 | Active volunteer/leader tracking -- Sunday Morning Volunteers, All Volunteers, D Group Leaders, Lunch and Learn. Best filter for SM volunteer attendance. |

Key findings (from full DivOrg scan 2026-07-08):
- Use `IN (201, 207)` to capture students + volunteers in current Sunday attendance orgs.
- TypeIds 156 and 176 appear in the original attendance SQL but do not match any active CC/PS orgs.
- PS Sunday orgs (e.g., SM: PS 10th Girls) appear in BOTH Division 11 (SM Sundays, ProgId 1109) AND Division 85 (RP PS Students, ProgId 1141) -- use EXISTS subquery (not JOIN) to avoid duplicate rows.
- Wednesday PS grade orgs use naming 'SM: PS WED [grade] Boys/Girls' (TypeId 205, DivId 42). Note: suffix uses 'Boys/Girls' not 'Guys/Girls' -- the CC Sunday parser will not split gender correctly for these.

---

## Key Tables and Join Patterns

### DivOrg
Links organizations to divisions.
Columns: `DivId`, `OrgId`, `id`

Confirmed 2026-08-13: composite primary key is (`DivId`, `OrgId`). Declared foreign keys are `DivId -> Division.Id` and `OrgId -> Organizations.OrganizationId`. The lowercase `id` column exists but is not part of the declared primary key.

```sql
-- Orgs in SM program
SELECT o.*
FROM Organizations o
JOIN DivOrg d2 ON d2.OrgId = o.OrganizationId
JOIN Division dv ON dv.Id = d2.DivId
WHERE dv.ProgId = 1109
```

### TaskNote
Task and notes table. NOT exposed via OData API - Python scripts only.

Key StatusId values (from docs):
- 1 = Complete (confirmed by existing task scripts; 8,240 current rows)
- 2 = Pending
- 3 = Active (Accepted)
- 4 = Declined
- 5 = Archived/note history (confirmed by existing task scripts; 103,938 current rows, all `IsNote = 1`)

Key columns: `TaskNoteId`, `OwnerId`, `AssigneeId`, `AboutPersonId`, `StatusId`, `Instructions`, `DueDate`, `IsNote`, `OrgId`, `SourceTaskNoteId`

Confirmed schema pitfall: RPC's `TaskNote` table does **not** expose a column literally named `Id`. Its declared primary key is `TaskNoteId`. Do not select `tn.Id AS TaskNoteId`; it causes `Invalid column name 'Id'` and can blank Python report output before rendering. Select `tn.TaskNoteId` when the task/note key is needed.

Confirmed 2026-08-13 declared relationships:
- `OwnerId -> People.PeopleId`
- `AssigneeId -> People.PeopleId`
- `AboutPersonId -> People.PeopleId`
- `OrgId -> Organizations.OrganizationId`
- `RoleId -> Roles.RoleId`
- `SourceTaskNoteId -> TaskNote.TaskNoteId` (self-reference)

`StatusId` has no declared foreign key in the exported schema. `lookup.TaskStatus` is **not** the lookup behind `TaskNote.StatusId`: its IDs are 10, 20, 30, 40, 50, 60, and 70, and all joined to zero `TaskNote` rows on 2026-08-13. Live `TaskNote.StatusId` values are 1–5. Do not join these tables or copy `lookup.TaskStatus` labels onto `TaskNote` values.

Observed structural scale on 2026-08-13: approximately 112,877 `TaskNote` rows. The separate legacy-looking `Task` table exists but had an approximate row count of 0; do not substitute it for `TaskNote` in current RPC reports without new evidence.

`IsNote`: 1 = note/history, 0 = task in the 2026-08-13 full aggregate. No NULL `IsNote` rows were observed. Existing task filters may retain `(IsNote = 0 OR IsNote IS NULL)` defensively for compatibility, but the previous claim that tasks currently store NULL was disproven by the full-table profile.

### OrganizationMembers
Links people to involvements.
Key columns: `PeopleId`, `OrganizationId`, `MemberTypeId`

Confirmed 2026-08-13: composite primary key is (`OrganizationId`, `PeopleId`). Declared joins are `OrganizationId -> Organizations.OrganizationId`, `PeopleId -> People.PeopleId`, and `MemberTypeId -> MemberType.Id`. Approximate row count: 82,428.

Global lookup labels are confirmed through `lookup.MemberType`; ministry-specific usage still depends on the involvement being queried.

---

## SM Staff (hardcoded PeopleId list - update when staff changes)

| PeopleId | Name |
|----------|------|
| 46965 | Isaac Jiles |
| 659 | Price Peden |
| 284 | Courtney Edmondson |
| 23164 | Joseph McCalley |
| 1675 | Libbie Risberg |
| 40594 | Haven Burton |
| 36696 | Joshua Watson |
| 28000 | Abbie Vinson |
| 19570 | Weston Watts |
| 118 | Shawn Adams |

Update the DECLARE @SMStaff block in SM_TaskNote-ToDo.sql when staff changes.

---

## MemberTypeId Values

| MemberTypeId | Global lookup meaning | Current OrganizationMembers rows |
|--------------|-----------------------|---------------------------------:|
| 136 | Coach | 33 |
| 140 | Leader | 1,344 |
| 220 | Member | 80,404 |
| 230 | InActive | 454 |
| 311 | Prospect | 108 |
| 710 | Volunteer | 36 |

Correction from the 2026-08-13 focused export: the old note describing 220 as Leader/volunteer and 136 as Substitute was wrong. Use 140 for the global Leader member type. Do not infer a person's ministry role from `MemberTypeId` without considering the organization context.

---

## Key SM Involvements for Staff Filtering

| OrgId | OrganizationName | TypeId | Notes |
|-------|-----------------|--------|-------|
| 176 | SM: Student Ministry Staff | 205 | Explicit staff list; only 3 of 6 confirmed staff present - not fully maintained |
| 3426 | SM: All Volunteers 2025-2026 | 207 | 5 of 6 confirmed staff; previously observed with MemberTypeId 220, whose global lookup meaning is Member—not Leader |
| 4011 | SM: All Volunteers 2026-2027 | 207 | 4 of 6 confirmed staff; active rollover in progress |

---

## SM SQL Filter Options

**Option A: Explicit staff involvement (cleanest, requires Max to maintain)**
```sql
AND tn.OwnerId IN (
    SELECT om.PeopleId
    FROM OrganizationMembers om
    JOIN Organizations o ON o.OrganizationId = om.OrganizationId
    WHERE o.OrganizationName = 'SM: Student Ministry Staff'
)
```

**Option B: All Volunteers involvement membership (self-updating year over year)**
```sql
AND tn.OwnerId IN (
    SELECT DISTINCT om.PeopleId
    FROM OrganizationMembers om
    JOIN Organizations o ON o.OrganizationId = om.OrganizationId
    JOIN DivOrg d2 ON d2.OrgId = o.OrganizationId
    JOIN Division dv ON dv.Id = d2.DivId
    WHERE dv.ProgId = 1109
    AND o.OrganizationName LIKE 'SM: All Volunteers%'
    -- Do not filter to 220 as a "leader" role; lookup.MemberType says 220 = Member.
    -- If role filtering is required, validate whether 140 = Leader is maintained
    -- consistently in these specific SM volunteer involvements first.
)
```

Pending: confirm with Max which approach to use and whether SM: Student Ministry Staff
should be the maintained source of truth going forward.

---

---

## Attendance Tables

### Meetings
Core attendance table. One row per meeting instance (org + date + time).

Key columns:
- `MeetingId` - primary key
- `OrganizationId` - links to Organizations
- `MeetingDate` - datetime; contains both date and time of the meeting
- `NumPresent` - aggregate headcount recorded for the meeting (what the dashboard uses)
- `NumVstMembers`, `NumRepeatVst`, `NumNewVisit` - visitor-related aggregate columns exposed by the live schema. The previously documented `NumVisted` spelling does not exist.
- `Location` - optional string

Confirmed 2026-08-13: `MeetingId` is the declared primary key; `OrganizationId -> Organizations.OrganizationId`. Approximate row count: 78,125. A unique index named `MeetingDateOrgId` uses (`MeetingDate`, `OrganizationId`), so that pair is database-enforced as unique in the exported schema.

The `MeetingDate` column stores the scheduled meeting time, so a Sunday 9am service will show a timestamp like `2026-05-04 09:00:00`. Filter by `CAST(MeetingDate AS DATE)` for date-only comparison.

```sql
-- Explore: recent SM Sunday meetings and their counts
SELECT TOP 50
    o.OrganizationName,
    CAST(m.MeetingDate AS DATE) AS MeetingDate,
    CONVERT(TIME, m.MeetingDate) AS MeetingTime,
    m.NumPresent
FROM dbo.Meetings m
JOIN dbo.Organizations o ON o.OrganizationId = m.OrganizationId
WHERE o.OrganizationName LIKE 'SM: CC %' OR o.OrganizationName LIKE 'SM: PS %'
ORDER BY MeetingDate DESC
```

```sql
-- Explore: confirm DATEPART(dw) values for Sunday and Wednesday meetings
SELECT DISTINCT
    DATEPART(dw, MeetingDate) AS DW_Value,
    DATENAME(weekday, MeetingDate) AS DayName
FROM dbo.Meetings m
JOIN dbo.Organizations o ON o.OrganizationId = m.OrganizationId
WHERE o.OrganizationName LIKE 'SM: CC %'
  AND CAST(MeetingDate AS DATE) > DATEADD(month, -6, GETDATE())
ORDER BY DW_Value
-- Expected: 1 = Sunday, 4 = Wednesday (with SET DATEFIRST 7)
```

---

### OrgSchedule
Stores the recurring schedule for an organization (not individual meeting instances).
Used to determine which day of week an org is scheduled to meet.

Key columns:
- `OrganizationId`
- `Id`
- `SchedDay` - day of week (0 = Sunday in this table; differs from DATEPART convention)
- `SchedTime` - scheduled meeting time

Confirmed 2026-08-13: composite primary key is (`OrganizationId`, `Id`); declared join is `OrganizationId -> Organizations.OrganizationId`. Approximate row count: 431.

```sql
-- Explore: scheduled days for SM CC attendance orgs
SELECT
    o.OrganizationId,
    o.OrganizationName,
    os.SchedDay,
    CONVERT(TIME, os.SchedTime) AS SchedTime
FROM dbo.OrgSchedule os
JOIN dbo.Organizations o ON o.OrganizationId = os.OrganizationId
WHERE o.OrganizationName LIKE 'SM: CC %' OR o.OrganizationName LIKE 'SM: PS %'
ORDER BY o.OrganizationName
```

Note: `OrgSchedule.SchedDay = 0` = Sunday (confirmed in original attendance query).
This differs from `DATEPART(dw, ...)` where Sunday = 1 under `SET DATEFIRST 7`.
The 2026-08-13 full profile observed values 0–6 plus special value 10. The meaning of 10 remains unconfirmed. Returned `SchedTime` values include a date component; compare or render only the time portion.

---

### Organizations (attendance-relevant columns)
| Column | Notes |
|--------|-------|
| `OrganizationId` | Primary key |
| `OrganizationName` | Name string; SM attendance orgs follow 'SM: CC [grade] [gender]' pattern |
| `OrganizationTypeId` | See Organization Type IDs table above |
| `OrganizationStatusId` | 30 = Active; always filter on this for live orgs |
| `DivisionId` | Not reliably set at the org level; use `DivOrg` join instead |

Confirmed 2026-08-13: `OrganizationId` is the declared primary key. Declared lookup joins include `OrganizationTypeId -> OrganizationType.Id`, `OrganizationStatusId -> OrganizationStatus.Id`, `DivisionId -> Division.Id`, `CampusId -> Campus.Id`, and self-references through `ParentOrgId` and `RegJoinOtherOrgId`. Approximate row count: 3,646.

```sql
-- Explore: all active SM attendance orgs with their TypeId and divisions
SELECT
    o.OrganizationId,
    o.OrganizationName,
    o.OrganizationTypeId,
    d.Id   AS DivisionId,
    d.Name AS DivisionName
FROM dbo.Organizations o
JOIN dbo.DivOrg do2 ON do2.OrgId = o.OrganizationId
JOIN dbo.Division d  ON d.Id     = do2.DivId
WHERE d.ProgId = 1109
  AND o.OrganizationStatusId = 30
  AND (o.OrganizationName LIKE 'SM: CC %' OR o.OrganizationName LIKE 'SM: PS %')
ORDER BY d.Name, o.OrganizationName
-- Run this to confirm TypeIds for Wednesday orgs (Division 42)
```

```sql
-- Explore: verify org name parsing assumption (7-char prefix, grade + gender suffix)
SELECT
    o.OrganizationName,
    LTRIM(SUBSTRING(o.OrganizationName, 8, 200)) AS ParsedRemainder,
    CASE UPPER(SUBSTRING(o.OrganizationName, 5, 2))
        WHEN 'CC' THEN 'Central'
        WHEN 'PS' THEN 'Parker Square'
    END AS Campus
FROM dbo.Organizations o
WHERE (o.OrganizationName LIKE 'SM: CC %' OR o.OrganizationName LIKE 'SM: PS %')
  AND o.OrganizationStatusId = 30
ORDER BY o.OrganizationName
-- Check ParsedRemainder column for unexpected formats before running the dashboard query
```

---

## Special Content - Deployed Scripts

| Tab | Name | Status |
|-----|------|--------|
| SQL Scripts | SM_TaskNote-ToDo | Deployed, filter still being tuned |
| Python Scripts | SM_OutstandingTasksList | Not yet deployed |
| Python Scripts | SM_OutstandingTaskNotifications | Deployed, tested 2026-07-03 |

---

## MorningBatch (Python Script)
Current contents:
```python
model.CallScript("RegistrationsWithoutAccountCodes")
```
Will add after SM scripts are confirmed working:
```python
if model.DayOfWeek == 2:
    model.CallScript("SM_OutstandingTaskNotifications")
```

---

## ScheduledTasks (Python Script)
Runs every 15 min. Not the right place for weekly email triggers.
Current contents:
```python
# TPxi Go - User Sync (runs every 15 min)
Data.run_batch = "true"
model.CallScript("TPGoBatch")
```
