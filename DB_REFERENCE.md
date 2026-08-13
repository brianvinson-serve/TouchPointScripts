# TouchPoint Database Reference - RockPointe
**Last Updated:** 2026-07-08

This doc captures confirmed IDs, table structures, and join patterns discovered
by running queries against the live rockpointe.tpsdb.com instance.

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
- 2 = Pending
- 3 = Active (Accepted)
- 4 = Declined

Key columns: `OwnerId`, `AssigneeId`, `StatusId`, `Instructions`, `DueDate`, `IsNote`

Confirmed schema pitfall: RPC's `TaskNote` table does **not** expose an `Id` column in the TouchPoint SQL/Python `q.QuerySql` surface. Do not select `tn.Id AS TaskNoteId`; it causes `Invalid column name 'Id'` and can blank Python report output before rendering.

`IsNote`: 1 = note, 0 or NULL = task. Tasks store NULL (not 0) in practice, so always filter with `(IsNote = 0 OR IsNote IS NULL)` rather than `IsNote = 0` alone.

### OrganizationMembers
Links people to involvements.
Key columns: `PeopleId`, `OrganizationId`, `MemberTypeId`

MemberTypeId TBD - need to confirm which values represent leaders vs students.

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

## MemberTypeId Values (observed in SM involvements)

| MemberTypeId | Observed role |
|--------------|---------------|
| 220 | Leader/volunteer (primary role for SM staff in volunteer involvements) |
| 140 | Secondary volunteer or member role |
| 136 | Substitute (seen in CC Sunday Morning Subs) |

---

## Key SM Involvements for Staff Filtering

| OrgId | OrganizationName | TypeId | Notes |
|-------|-----------------|--------|-------|
| 176 | SM: Student Ministry Staff | 205 | Explicit staff list; only 3 of 6 confirmed staff present - not fully maintained |
| 3426 | SM: All Volunteers 2025-2026 | 207 | 5 of 6 confirmed staff; MemberTypeId 220 |
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

**Option B: All Volunteers + MemberTypeId 220 (self-updating year over year)**
```sql
AND tn.OwnerId IN (
    SELECT DISTINCT om.PeopleId
    FROM OrganizationMembers om
    JOIN Organizations o ON o.OrganizationId = om.OrganizationId
    JOIN DivOrg d2 ON d2.OrgId = o.OrganizationId
    JOIN Division dv ON dv.Id = d2.DivId
    WHERE dv.ProgId = 1109
    AND o.OrganizationName LIKE 'SM: All Volunteers%'
    AND om.MemberTypeId = 220
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
- `NumVisted` - visitors counted (separate from NumPresent)
- `Location` - optional string

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
- `SchedDay` - day of week (0 = Sunday in this table; differs from DATEPART convention)
- `SchedTime` - scheduled meeting time

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

---

### Organizations (attendance-relevant columns)
| Column | Notes |
|--------|-------|
| `OrganizationId` | Primary key |
| `OrganizationName` | Name string; SM attendance orgs follow 'SM: CC [grade] [gender]' pattern |
| `OrganizationTypeId` | See Organization Type IDs table above |
| `OrganizationStatusId` | 30 = Active; always filter on this for live orgs |
| `DivisionId` | Not reliably set at the org level; use `DivOrg` join instead |

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
