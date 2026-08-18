# TouchPoint Database Reference - RockPointe
**Last Updated:** 2026-08-17

This doc captures confirmed IDs, table structures, and join patterns discovered
by running queries against the live rockpointe.tpsdb.com instance.

Full structural inventory source: `data-dictionary-expander/exports/2026-08-13/rockpointe-touchpoint-data-dictionary-2026-08-13.csv` (collected 2026-08-13 through TouchPoint `q.QuerySql`; 505 tables/views, 4,539 columns, 457 primary-key columns, 456 foreign-key columns, 781 index-key columns, zero probe errors). Focused evidence: `data-dictionary-expander/exports/2026-08-13/rockpointe-touchpoint-focused-confirmation-2026-08-13.csv` (61 aggregate/lookup rows, zero probe errors). Human-readable summaries are under `data-dictionary-expander/reports/2026-08-13/`.

Structural metadata confirms object/column/key existence. Status/type meanings and value behavior below are documented only where the focused live export or prior RPC testing supplied evidence.

---

## Programs

| ProgId | Name |
|--------|------|
| 1109   | Student Ministry (SM) |
| 1111   | Children's Ministry (CM) |
| 1130   | CT Admin |
| 1137   | Reporting (RP) CC Children ONLY Sun AM |
| 1138   | Reporting (RP) PS Children ONLY Sun AM |
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

## Children's Ministry Sunday Reporting — confirmed 2026-08-17

The clean production boundary for Sunday Children's Ministry attendance is active `CM:` organizations of Type 201 or 207 linked through `DivOrg` to reporting program 1137 (Central) or 1138 (Parker Square), **and** having either a Sunday schedule (`OrgSchedule.SchedDay = 0`) or an actual Sunday meeting in the operational lookback window. Program linkage alone is too broad: the live validation found stale Christmas/event/leader records with no Sunday schedule or recent Sunday meeting. In this boundary, Type 201 is child/classroom attendance and Type 207 is volunteer attendance.

August 16, 2026 was Promotion Sunday and the start of the new school year. Children’s Ministry may have cleaned up or recreated involvements effective that date. Treat 2026-08-16 as the beginning of the Fall 2026 reporting roster: pre-8/16 history is useful for technical validation but is not an apples-to-apples attendance trend baseline. Do not exclude a correctly linked active involvement with a Sunday schedule simply because it has no pre-promotion meeting history.

| Division.Id | Division.Name | Program |
|-------------|---------------|---------|
| 14 | CM Special Needs | 1111 Children's Ministry (CM) |
| 15 | CM Elementary | 1111 Children's Ministry (CM) |
| 19 | CM Preschool | 1111 Children's Ministry (CM) |
| 66 | CM Childcare | 1111 Children's Ministry (CM) |
| 81 | RP CC Children | 1137 Reporting (RP) CC Children ONLY Sun AM |
| 82 | RP PS Children | 1138 Reporting (RP) PS Children ONLY Sun AM |

The dated discovery evidence is retained at `data-dictionary-expander/exports/2026-08-17/RunScript.xlsx`. Four-week validation evidence is `data-dictionary-expander/exports/2026-08-17/RPC_ChildrenFourWeekAttendanceValidation.xlsx`; the audited 93-involvement roster and findings are under `data-dictionary-expander/reports/2026-08-17/`.

Do not include rows solely because Angela Cheshire or Jennifer Schmitz is a member, or because an unrelated involvement name contains “kids” or “children.” Explicitly exclude the incorrectly linked `SM: PS Sunday Morning Volunteers 2026-2027` row. An organization can have multiple meetings on one Sunday (the PS Welcome Team had three on 2026-08-16), so weekly organization attendance must sum all non-canceled, non-`DidNotMeet` meetings for that organization/date rather than selecting `TOP 1` latest meeting.

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

### Campus lookup

The campus table is `lookup.Campus`, not `dbo.Campus`. Join organization campus metadata with `lookup.Campus.Id = Organizations.CampusId`. Using `dbo.Campus` causes `Invalid object name 'dbo.Campus'` in RPC TouchPoint.

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

## RPC Staff Directory

The canonical RPC staff identity key is `People.PeopleId`. Staff email addresses are useful discovery evidence but should not be used as durable application keys.

### Current source rule

Until RPC identifies a maintained employee roster inside TouchPoint, define the **staff-directory candidate set** as People records whose `EmailAddress` or `EmailAddress2` ends in `@rpcstaff.org` (case-insensitive, trimmed). This is a directory/reference rule, not proof of current employment.

The internal focused query and its live exports are retained only in local gitignored paths because this repository is public. They must not be committed or published.

### Review rules

- `UNIQUE_DOMAIN_EMAIL_RECORD` — one non-archived, non-deceased People record owns the normalized staff-domain email and the People record is not duplicate-flagged. The 2026-08-13 export used the older label `CURRENT_CANDIDATE` for this condition; it does **not** prove current employment.
- `REVIEW_ARCHIVED` — staff-domain email is attached to an archived People record.
- `REVIEW_DUPLICATE_EMAIL` — more than one People record owns the same normalized staff-domain email.
- `REVIEW_PERSON_DUPLICATE_FLAG` — TouchPoint marks the People record as having duplicates.
- `EXCLUDE_DECEASED` — record is deceased and must not be used as a recipient.

Do not infer active employment solely from `@rpcstaff.org`; former staff may retain an address or an archived TouchPoint record. For production recipient lists, resolve and review the current live export, then use PeopleIds with `model.Email`.

### Confirmed directory snapshot

Confirmed 2026-08-13 from `data-dictionary-expander/exports/2026-08-13/rpc-staff-directory-2026-08-13.csv` (a privacy-minimized extract of the original local `RunScript.xlsx`; SHA-256 hashes are recorded in the dated report notes):

- 140 People records have a normalized `@rpcstaff.org` address in `EmailAddress` or `EmailAddress2`.
- 110 records had a unique domain email and were labeled `CURRENT_CANDIDATE` by the first query version. This label means **unique staff-domain record**, not current employee.
- 30 records require duplicate-email review.
- The candidate set includes real people, shared ministry mailboxes, system/test records, and children or household members carrying another person's staff address. The email domain cannot serve as an authoritative whole-staff employment roster.
- The complete directory and review rows are retained locally in the dated export/report paths, which are gitignored because this repository is public. Do not commit or duplicate the 140-row PII-bearing table here.

### Confirmed SM attendance-report recipients — 2026-08-13

The 12-recipient production PeopleId list was resolved from the live whole-domain export and is embedded in `SM_AttendanceDashboardEmail.py`. Staff email corrections and the complete directory evidence are retained only in local gitignored files because this repository is public. Use PeopleIds—not runtime email-string matching—for the weekly report.

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

### Attend
Individual attendance table. One row per person/meeting attendance record; use this rather than `Meetings.NumPresent` when the report needs student names or contact information.

Confirmed structurally from the 2026-08-13 export:
- Primary key: `AttendId`.
- Declared joins: `PeopleId -> People.PeopleId`, `MeetingId -> Meetings.MeetingId`, `OrganizationId -> Organizations.OrganizationId`, `AttendanceTypeId -> lookup.AttendType.Id`, and `MemberTypeId -> lookup.MemberType.Id`.
- Relevant fields include `PeopleId`, `MeetingId`, `OrganizationId`, `MeetingDate`, `AttendanceFlag`, `NoShow`, and `EffAttendFlag`.
- For the SM student contact report, require `AttendanceFlag = 1` and defensively exclude `NoShow = 1`. This is the implemented rule and still requires live RPC validation against known attendance records.

### Student and household contact joins

Confirmed structurally from the 2026-08-13 export:
- `People.FamilyId -> Families.FamilyId`.
- `People.GenderId -> lookup.Gender.Id` and `People.GradeLevelId -> lookup.GradeLevel.Id`.
- `People.PositionInFamilyId -> lookup.FamilyPosition.Id`; the lookup structurally exposes `Child`, `PrimaryAdult`, and `SecondaryAdult` fields, but their live RPC values and maintenance quality have not been validated. Do not require `FamilyPosition.Child = 1` in operational student reports until focused live evidence confirms it; that gate is a leading suspected cause of the first SM contact-export query returning zero rows.
- `Families` exposes `HeadOfHouseholdId` and `HeadOfHouseholdSpouseId`. The confirmed family table has no household-level email field; email addresses live on People records.
- Contact exports should label the two family heads neutrally as Parent/Guardian 1 and Parent/Guardian 2 rather than inferring mother/father roles.
- `SM_StudentContactExport` current grade is profile data, not an organization-name calculation: it resolves `People.GradeLevelId -> lookup.GradeLevel` and displays `Code`, then `Description`, then the legacy `People.Grade` value as fallback. Live validation on 2026-08-13 showed adult volunteer Jason McMahon with `G9`, so grade is not reliable evidence that a person is a student.
- For person-level volunteer exclusion in this report, use membership in any annual involvement named `SM: All Volunteers%`, not only the current-year name. Live validation showed the exact `SM: All Volunteers 2026-2027` roster excluded Brian Vinson but missed volunteer Jason McMahon during rollover.

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

## Registrations (Online Registration / RegQuestion / RegAnswer) — confirmed 2026-08-17

Registration data lives in its own table set, separate from `Meetings`/`Attendance`. Confirmed live against the "SM: Man Up Meal Sign Up 2026-2027" registration (OrganizationId 4053).

### Table roles

| Table | Role |
|---|---|
| `Organizations` | The event/org itself. `RegistrationTypeId`, `RegistrationTitle`, `RegistrationClosed` flag whether/how registration is configured on that org. |
| `Registration` | One row per registration transaction. `RegistrationId` is a `uniqueidentifier` (GUID) — **not** a small int. Tied to `OrganizationId` and the registering `PeopleId`. |
| `RegPeople` | The person/people attached to a given `Registration` (covers group signups where one registration includes multiple people). FK: `RegPeople.RegistrationId -> Registration.RegistrationId`. |
| `RegQuestion` | The custom questions configured on that org's registration form. FK: `RegQuestion.OrganizationId -> Organizations.OrganizationId`. Has `Label`, `QuestionTypeId`, `IsRequired`, and `Options` (see below). |
| `RegAnswer` | The actual answers people gave. FK: `RegAnswer.RegQuestionId -> RegQuestion.RegQuestionId`, `RegAnswer.RegPeopleId -> RegPeople.RegPeopleId`. `AnswerValue` holds the answer (see JSON gotcha below). |

### URL → ID mapping

TouchPoint's public registration page URL pattern is `https://{site}.tpsdb.com/OnlineReg/{OrganizationId}` — the number in that URL is the **OrganizationId**, not a `Registration.RegistrationId` (which is a GUID and would never render as a short decimal in a URL). Confirmed: `/OnlineReg/4053` → `Organizations.OrganizationId = 4053`, `OrganizationName = "SM: Man Up Meal Sign Up 2026-2027"`, `RegistrationTypeId = 26`.

### JSON-encoded answer/option data (multi-select questions)

For a multi-select `RegQuestion` (e.g. "choose a night" checkboxes), both of the following are stored as **JSON strings**, not plain delimited text — do not assume newline/semicolon splitting without checking first:

- `RegAnswer.AnswerValue` — JSON array of the option strings the person picked, e.g. `["9/16 Nacho Bar","4/14 Hot Dogs"]`. A person can select more than one option; don't assume one answer per person per question.
- `RegQuestion.Options` — JSON array of option objects describing the full picklist offered on the form, e.g. `[{"Name":null,"Value":"8/26","Text":"8/26 Hot Dogs (Hot dogs, buns, condiments, chips)","Lookup":null,"Fee":null,"MeetingId":null,"Limit":1,"InvId":null,"Other":false,"SkipToId":null,"Status":null,"Count":null}, ...]`. Use each object's `Text` (or `Value`) field to get the option's display string — do not treat the raw field as one-option-per-line text.

Both fields need `json.loads` (or equivalent) before parsing; a plain-line-split fallback is reasonable defensive coding but should not be the primary path.

### Man Up Meal Sign-Up — confirmed IDs

| Item | Value |
|---|---|
| OrganizationId | 4053 |
| OrganizationName | SM: Man Up Meal Sign Up 2026-2027 |
| RegistrationTypeId | 26 |
| RegistrationTitle | Man Up Meal Sign-Up 2026-2027 |
| RegQuestionId — "Enter your information" | c2cd7305-669e-478f-a03e-990f4ccf7cfd |
| RegQuestionId — "Please choose a night to lead a meal." | fd1504b9-4cfd-4252-a0f3-f1a34c517c4d |

All confirmed claimed nights for this registration land on a Wednesday, consistent with SM Wednesdays (Division 42) — this event tracks "bring food" as a Wednesday-night meal slot claim, not a free-text food item.

### Reusable SQL

```sql
-- Confirm an OrganizationId belongs to a registration and show its title
SELECT OrganizationId, OrganizationName, RegistrationTypeId, RegistrationTitle
FROM dbo.Organizations
WHERE OrganizationId = @OrgId

-- List the registration questions configured for an org (find RegQuestionId + Options)
SELECT RegQuestionId, [Order], Label, QuestionTypeId, IsRequired, Options
FROM dbo.RegQuestion
WHERE OrganizationId = @OrgId
ORDER BY [Order]

-- Pull registrants + their raw (possibly JSON) answer for a given question
SELECT
    p.Name, p.CellPhone, p.EmailAddress,
    r.CreatedDate AS RegisteredOn,
    ra.AnswerValue AS RawAnswer
FROM dbo.Registration r
JOIN dbo.RegPeople rp ON rp.RegistrationId = r.RegistrationId
JOIN dbo.RegAnswer ra ON ra.RegPeopleId = rp.RegPeopleId
                     AND ra.RegQuestionId = @RegQuestionId
JOIN dbo.People p ON p.PeopleId = r.PeopleId
WHERE r.OrganizationId = @OrgId
ORDER BY p.Name
```

### Pitfall: GUID literal quoting

Pasting a `uniqueidentifier` literal into TouchPoint's SQL Script editor can trigger `Conversion failed when converting from a character string to uniqueidentifier` if the editor's rich-text box auto-converts straight quotes (`'`) into curly/smart quotes (`'`/`'`) on paste — SQL Server can't parse a string literal wrapped in curly quotes. If a GUID-literal query fails this way, retype the quote marks manually instead of pasting from a source with autocorrect (Word, Notes, some browsers).

### Deployed report script

`meal-signup-report/SM_ManUpMealSignUpReport.py` (this repo) — read-only TouchPoint Python Script that reports signed-up nights (one row per claimed night, duplicate nights per person flagged) and diffs claimed nights against `RegQuestion.Options` to list unclaimed nights. See that folder's README for deployment steps and confirmed IDs.

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
Approved addition for the weekly SM attendance report:
```python
if model.DayOfWeek == 1:
    model.CallScript("SM_AttendanceDashboardEmail")
```

Still pending for outstanding-task notifications:
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
