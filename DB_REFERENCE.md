# TouchPoint Database Reference - RockPointe
**Last Updated:** 2026-08-26

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
| 1119   | Adult Discipleship (AD) |
| 1124   | Reporting (RP) All Programs ONLY Sun AM |
| 1127   | Reporting (RP) All Programs OUTSIDE Sun AM |

`1124`/`1127` discovered 2026-08-30 via `OrganizationStructure` (see below). **Confirmed 2026-08-30: this is a hand-maintained, division-level classification, not a live schedule-derived rollup.** Only 37 of RPC's 82 divisions are tagged into either bucket at all (not "every division"). Proof it isn't schedule-computed: 9 divisions (`AD Classes/Meetings/Groups`, `CM Childcare`, `CM Elementary`, `CM Preschool`, `CM Special Needs`, `MEN Classes`, `MM Classes`, `WM Classes`, `WM Discipleship`) are tagged into **both** buckets simultaneously with the *identical* org roster and identical `OrgSchedule` breakdown in each — if this were per-org schedule filtering, the same division couldn't land its whole unchanged roster in both an "ONLY Sun AM" and an "OUTSIDE Sun AM" bucket. It's also directly contradicted by content: `WM Classes` (DivId 13, tagged "ONLY Sun AM") has 468 of 471 member orgs with **no `OrgSchedule` row at all** and only 1 actually scheduled Sunday AM — the label doesn't reliably describe when its orgs meet. `SM Sundays` (DivId 11) is the one division that does line up with its label (50 of 72 orgs genuinely Sunday-AM-scheduled).

**Do not use `1124`/`1127` as a "meets on Sunday morning" signal for attendance/schedule reporting** — treat it as a coarse ministry-scope tag (likely for facilities/capacity planning: who's on campus during the main service window vs. everything else), not a schedule fact. `OrgSchedule`/`Meetings` remain the only reliable source for actual meeting times, same as elsewhere in this doc. Not confirmed whether this is RPC-custom or a native TouchPoint feature — a quick look at TouchPoint's own Admin/Reports screens for something named "All Programs ONLY Sun AM" would settle that cheaply if it ever matters.

Divisions tagged only `1124` (Sun AM bucket): `CO Baptism`, `CO First Time Visitor`, `RP CC Worship`, `RP PS Worship`, `SM Sundays`, `WO Services`. Divisions tagged only `1127` (outside-Sun-AM bucket): `AD Events`, `CM Mission Trips`, `CM Weekday Preschool`, `CO Dinner with the Pastor`, `CO Membership Matters`, `MEN Coffee Groups`, `MEN Events`, `MM Events`, `MM Premarital`, `MM re|engage`, `MS (DNU) Mission Trips`, `MS Global/Mission Trips`, `MS Local Missions`, `OP DIV`, `SG Events`, `SG Groups`, `SM Classes`, `SM Events`, `SM Mission Trips`, `SM Wednesdays`, `WM Sub-ministries`, `WM Events`. Both buckets: the 9 divisions listed above.

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

**Embrace Ministry (Special Needs) involvement names — confirmed by email 2026-08-19.** Marlene (Embrace Ministry) sent the exact roster of Division 14 involvements the dashboard/email should be counting:
- Central: `CM: CC 9:00a Special Needs Kids`, `CM: CC 10:45 AM Special Needs Kids`, `CM: CC 9:00 a Volunteers Special Needs`, `CM: CC 10:45 AM Volunteers Special Needs`
- Parker Square: `CM: PS 9:45 Special Needs Kids`, `CM: PS 11:15 Special Needs Kids`, `CM: PS 9:45 Volunteers Special Needs`, `CM: PS 11:15 Volunteers Special Needs`

All eight already fall under the existing `"special needs" in lname` classification in both `cm-attendance-pyreport.py` and `CM_AttendanceDashboardEmail.py` (see their header notes for the 2026-08-17 validated scope) — no code change required. Filed here as written ministry confirmation of the names.

---

## Adult Discipleship (AD) / ReNew — confirmed 2026-08-26

Program `1119` = Adult Discipleship (AD). Division `126` = "AD ReNew"; the broader `31` = "AD Classes/Meetings/Groups" also carries most AD-program orgs (including ReNew ones), so filter on org name, not just division, when isolating ReNew specifically.

ReNew is a recovery/step-group ministry that runs a new `OrganizationId` each term (Fall/Spring), discovered live via `OrganizationName LIKE '%renew%'` — no prior script or reference to this ministry existed in this repo before 2026-08-26. Observed `OrganizationStatusId` values in the family: `30` = Active (current-term org), `40` appears consistently on every past-term org (F24, S25, F25, S26, etc.) — treat `40` as "past/completed term," distinct from the general "inactive" framing elsewhere in this doc; not yet confirmed against a `lookup.OrganizationStatus` label.

**ReNew Fall 2026 (current term):** `OrganizationId = 3906`, `OrganizationName = "ReNew Fall 2026"`, `OrganizationTypeId = 201`, `OrganizationStatusId = 30`, ~50 members. Linked in both Division 126 (AD ReNew) and Division 31 (AD Classes/Meetings/Groups). Meets weekly on **Mondays** — confirmed live: two meetings held so far (2026-08-17, 2026-08-24, `NumPresent` 35 and 34).

No separate Men/Women org exists for the current term (unlike some past terms, e.g. `Renew Men` id 3255 and `ReNew Women` id 3254, both status 40/past-term) — a gender split for Fall 2026 must be done via `People.GenderId` in the query, not by picking a different org.

Related current-term orgs, not folded into the roster report unless asked: `ReNew F26 Closed Groups` (4133, TypeId 201, Active) and `ReNew Fall 26 Leaders` (4039, TypeId 207 = volunteer/leader tracking, Active).

Deployed report: `renew-roster-report/AD_ReNewRosterReport.py` — a generic Leader/Member roster + attendance-grid report, not ReNew-specific. It picks its target involvement from a configured division list (`DIVISION_FILTERS`, currently Division 126 + 31 above) via an in-page picker rather than a hardcoded OrgId, so it already covers every active AD ReNew/Classes-Groups org, and is designed to extend to other ministries (e.g. Marriage Ministry classes) by adding their Division.Id once confirmed. See that folder's README for the extension recipe.

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

### OrganizationStructure (view) — confirmed 2026-08-30

A built-in view, not RPC-custom. Discovered while evaluating `bswaby/Touchpoint`'s `TPxi_RollSheet.py`, which joins it as a convenience wrapper instead of `DivOrg`. Columns confirmed live: `Program`, `Division`, `OrgStatus`, `Organization` (display names) and `ProgId`, `DivId`, `OrgId` (keys), plus aggregate columns `Members`, `Previous`, `Vistors` (TouchPoint's own spelling, not a typo introduced here), `Meetings`.

**Same one-to-many shape as `DivOrg` — actually broader.** Tested against two orgs already confirmed multi-division elsewhere in this doc:

- `ReNew Fall 2026` (OrgId 3906, confirmed above in Division 126 + 31) returned **4 rows**: Division 31 under ProgId 1119 (its real program), Division 126 under ProgId 1119, and Division 31 again under both `1124` and `1127` (the "Reporting (RP) All Programs" ProgIds — see Programs table above).
- `SM: PS Health and Safety` (OrgId 1943, confirmed above in Division 11 + 42) returned **4 rows**: Division 11 under ProgId 1109 (real), Division 42 under ProgId 1109 (real), Division 11 under `1124`, Division 42 under `1127`.

So a plain `JOIN OrganizationStructure` fans out per (org, division, program) combination the org is linked into — worse than `DivOrg` alone, since it also picks up the church-wide `1124`/`1127` reporting buckets (confirmed hand-maintained division tags, not schedule-derived — see the Programs table above for the full breakdown). **The `EXISTS`-not-`JOIN` discipline documented for `DivOrg` applies here too.**

**The aggregate columns are per-org constants repeated on every fan-out row, not per-row values.** Both test orgs showed identical `Members`/`Previous`/`Vistors`/`Meetings` across all 4 of their rows (`52/1/1/2` for ReNew, `7/2/1/93` for Health and Safety). A naive `SUM()`/`COUNT()` over this view without first deduplicating by `OrgId` will over-count by however many rows that org fans into. Safe pattern (what `TPxi_RollSheet.py` actually does): filter to one specific `ProgId`/`DivId` in the `WHERE` clause, then `SELECT DISTINCT OrgId` — that naturally collapses to one row per org because only one division/program combination matches the filter.

**Possible shortcut, not yet trusted for reporting:** ReNew's `Meetings = 2` and `Members = 52` line up closely with this doc's independently-confirmed "two meetings held so far, ~50 members" — decent evidence `Members`/`Meetings` are legitimate live TouchPoint rollups. `Previous` and `Vistors` meanings are unconfirmed (guesses: prior-term/prior-meeting stat and visitor count, respectively). Do not build a report on these columns without confirming their exact definitions on a case where the expected number is independently known.

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
- 1 = Complete
- 2 = Pending
- 3 = Active (Accepted)
- 4 = Declined
- 5 = Note (always `IsNote = 1`, not "archived" — see `IsArchived` correction below)

**Correction, confirmed 2026-08-25 (StatusId × IsNote × IsArchived cross-tab, all ~113,427 rows):** the old "5 = Archived/note history" label conflated two different things. `IsArchived` is a **separate, independent bit flag**, not a value folded into `StatusId`. No `StatusId = 6` rows exist at RPC (unlike some other TouchPoint instances that do use 6 for Archived) — don't assume it's a valid value here without new evidence. `IsArchived = True` shows up on a small number of rows at *every* `StatusId`, including nominally-open ones: of 426 tasks matching `StatusId IN (2,3)`, 10 (2 Pending + 8 Accepted) are already `IsArchived = True`. An "open task" filter that doesn't also exclude `IsArchived = True` will surface tasks staff already archived as if they're still live. Confirmed full distribution:

| StatusId | IsNote | IsArchived | RowCount |
|---|---|---|---:|
| 1 | False | False | 8,536 |
| 1 | False | True | 4 |
| 2 | False | False | 237 |
| 2 | False | True | 2 |
| 3 | False | False | 179 |
| 3 | False | True | 8 |
| 4 | False | False | 52 |
| 4 | False | True | 3 |
| 5 | True | False | 51,172 |
| 5 | True | True | 53,234 |

Key columns: `TaskNoteId`, `OwnerId`, `AssigneeId`, `AboutPersonId`, `StatusId`, `Instructions`, `DueDate`, `IsNote`, `OrgId`, `SourceTaskNoteId`

Confirmed 2026-08-13 full column inventory (not all previously documented): `TaskNoteId`, `CreatedBy`, `CreatedDate`, `ModifiedBy`, `ModifiedDate`, `CompletedBy`, `CompletedDate`, `DueDate`, `IsNote`, `IsArchived`, `StatusId`, `OwnerId`, `AssigneeId`, `AboutPersonId`, `RoleId`, `Instructions`, `Notes`, `OrgId`, `SourceTaskNoteId`, `DeclinedReason`, `ReminderSent`, `SortDate`. `IsArchived` is a separate bit flag from `StatusId` — do not assume `StatusId` alone tells you archived state; `CompletedDate`/`CompletedBy` are the fields to use for completion-rate/turnaround reporting (e.g. `DATEDIFF(day, CreatedDate, CompletedDate)`), not a derived value.

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

### TaskNote Keywords (task-type taxonomy) — confirmed 2026-08-25

TaskNote has a native task-type/tagging mechanism: `Keyword` (lookup table, 47 rows in the 2026-08-13 structural export) joined through `TaskNoteKeyword` (`TaskNoteId`, `KeywordId`, `TaskNoteKeywordId` PK; 27,725 rows). A task can carry more than one keyword. This is **already in active use at RPC**, not a greenfield feature — do not assume "task type" needs to be invented.

Confirmed live usage counts (2026-08-25, all `IsActive = 1`), highest-use first:

| Code | Description | Usage |
|---|---|---:|
| SG | Small Groups | 6,823 |
| CP | Care | 3,523 |
| CO | Connections | 3,352 |
| FTV | First Time Visitor | 3,005 |
| SM | Student Ministry | 2,111 |
| AD2 | Mid-Gen/Senior Adult | 1,322 |
| CM | Children's Ministry | 1,111 |
| Pray | Prayer Request | 1,105 |
| WM | Women's Ministry | 842 |
| Serve | Volunteering | 755 |
| MEN | Men's Ministry | 568 |
| PR5002 | Include in Prayer Feed | 429 |
| Mmbshp | Membership | 412 |
| Failed Gift | Failed Gift | 341 |
| DWP | Dinner with the Pastor | 334 |
| Grief | Grief | 271 |
| DX | Deacons | 267 |
| Bap | Baptism | 241 |
| MS | Missions | 230 |
| YA | Young Adult | 149 |
| AD | Adult Discipleship | 131 |
| PR5003 | Anonymous Prayer Request | 129 |
| PR5000 | Mobile Prayer Request | 90 |
| MM | Marriage Ministry | 90 |
| Beg w/God | Beginning a Relationship with God | 79 |
| WO | Worship Ministry | 60 |
| ERmvd | Staff email removed | 53 |
| RRmvd | Staff System Roles Removed | 50 |
| NLStaff | Note - no longer on staff | 45 |
| Hosp. | Hospital | 26 |
| Fix-It | Fix It Ministry (Facilities) | 21 |
| SN | Special Needs | 18 |
| SG1 | Prospect | 17 |
| FTGN | FTG Note | 16 |
| SNed | See Ned | 15 |
| TN0609 | Account Deletion Requested | 14 |
| PR5001 | Prayer Request Unauthenticated | 12 |
| CA | Caution/Concern | 9 |
| DE | Deceased | 9 |
| RFI | Removed From Involvements | 8 |
| OP | Operations | 7 |
| PM | Parenting | 2 |
| SA | See Alan | 2 |
| RFAI | Removed From Additional Involvements | 1 |
| FOUP | Follow Up Marlene | 1 |
| Cmpltd | Completed | 1 |
| RR | Remove Access Role | 0 |

**Not a clean department taxonomy — it's three different kinds of tag mixed in one flat list:**
1. **Ministry/department tags** (16): SG, SM, AD2, CM, WM, MEN, MS, YA, AD, MM, WO, Fix-It, OP, PM, DX, SN — usable as a ministry-context filter. Cross-checked against the live RockPointe staff directory (`https://www.rockpointechurch.org/staff/department/all-staff`, 2026-08-26): all 16 correspond to a real named department (e.g. `SN` = Special Needs Ministry — corrected here 2026-08-26; an earlier pass omitted it from this list).
2. **Care/assimilation workflow tags** (22): CP, CO, FTV, Pray, PR5000, PR5001, PR5002, PR5003, Grief, Bap, Beg w/God, Hosp., CA, DE, SNed, SA, FOUP, Serve, Mmbshp, DWP, SG1, FTGN — pastoral-care/assimilation pipeline stages, not departments. These dominate total volume (SG/CP/CO/FTV alone are ~17,700 of the 27,725 tagged rows), so a naive "top keyword" chart will read as an assimilation-pipeline report, not a staff-task report.
3. **System/housekeeping tags** (9): Failed Gift, ERmvd, RRmvd, NLStaff, RFI, RFAI, RR, TN0609, Cmpltd — look auto-generated by TouchPoint account/role-maintenance processes, not staff-assigned. Worth excluding from a staff-facing task-type filter, or grouping under a single "System" bucket.

This 16/22/9 = 47 grouping is implemented as `KEYWORD_GROUPS` in `outstanding-task-notifications/dashboard/RPC_StaffTaskDashboard.py`. Keep that dict and this note in sync if new Keyword rows are added at RPC.

Do not treat Keyword as the sole department axis for a staff task dashboard — it tells you what a task is *about*, not reliably who owns it or what department that person sits in. Pair it with owner identity (see `MemberTags`/`OrgMemMemTags` below) for a "by department" staff rollup.

**`TaskNote.OrgId` is not usable as a ministry-context signal — confirmed 2026-08-25.** Live query against all 426 currently-open (`StatusId IN (2,3)`, non-note) tasks found `OrgId IS NOT NULL` on **0 of 426**. Nobody at RPC ties a task to an involvement in practice. Do not build a "task's ministry via `OrgId -> DivOrg -> Division -> Program`" join — it will return nothing. The ministry-tag subset of Keyword (above) is currently the only per-task ministry signal; owner identity (via `MemberTags`/`OrgMemMemTags`, pending confirmation) is the other, independent axis for a "by department" rollup.

### MemberTags / OrgMemMemTags (native SubGroups feature)

TouchPoint's involvement-level "SubGroups" tagging: `MemberTags` (`Id` PK, `Name`, `OrgId -> Organizations`, plus check-in/volunteer-scheduling columns `VolFrequency`, `VolStartDate`, `VolEndDate`, `CheckIn`, `CheckInCapacity`, `ScheduleId`) and `OrgMemMemTags` (composite PK `OrgId`+`PeopleId`+`MemberTagId`, plus `IsLeader` bit) linking a person's membership in a specific involvement to one or more tags on that involvement. Confirmed 2026-08-13 structural scale: `MemberTags` ~7,064 rows, `OrgMemMemTags` ~50,601 rows — heavily used at RPC already.

**Confirmed 2026-08-25: no department-style usage exists.** Queried every `%Staff%`/`%Team%`-named involvement's MemberTags live. Every result is event-RSVP options or volunteer-scheduling slots — e.g. `AP: Staff Social Styles` ("Will attend:"/"Unable to attend"), `Staff Women` (retreat attendance options), `CM:Childcare for Staff Kids Summer 26` (specific summer dates), `Health and Safety Team` / `SM: Servant Leadership Team` / `YA: Serve Team Interest Form` (serving positions like Floater, Welcome, Cashier 1). None of these are a church-wide staff department roster. Do not build a "department via MemberTags" join expecting existing data — there isn't any. A church-wide staff-by-department dashboard should use a hardcoded PeopleId → Department roster maintained in the script (extending the existing `SM Staff` / `SM_STAFF` pattern church-wide) rather than waiting on new TouchPoint admin setup for this.

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

**Correction, confirmed 2026-08-26:** Weston Watts (19570) is no longer on staff. This list (and `SM_TaskNote-ToDo.sql`'s `@SMStaff` table, and `SM_StaffTaskDashboard.py`'s `SM_STAFF` list) still has him as active — needs updating next time either script is touched. He's already handled correctly in the newer church-wide roster below (bucketed `Unassigned` rather than removed, so any orphaned tasks of his stay visible).

---

## RPC Staff Departments (hardcoded roster — update when staff change)

Church-wide `PeopleId -> Department` mapping, for the department axis of the `RPC_StaffTaskDashboard` dashboard (task type comes from `Keyword`/`TaskNoteKeyword` instead — see above). No native TouchPoint field ties a person or a task to a department at RPC (`TaskNote.OrgId` is unused; no department-shaped `MemberTags` usage exists — see notes above), so this is maintained by hand, same pattern as `SM Staff` above.

**Source:** the 64 people holding an open TaskNote task church-wide (query confirmed 2026-08-25), cross-referenced against the live staff directory `https://www.rockpointechurch.org/staff/department/all-staff` (fetched 2026-08-26), plus two corrections Brian confirmed by hand (Isaac Jiles and Abbie Vinson are Student Ministry despite the directory listing them under "Ministry Leaders"). This is the same data as the `ROSTER` dict in `outstanding-task-notifications/dashboard/RPC_StaffTaskDashboard.py` — **keep both in sync**; the code comment there points back here.

| PeopleId | Name | Department |
|---|---|---|
| 18460 | Abrie Champion | Worship and Production |
| 29093 | Aimee Whaley | Special Needs Ministry |
| 1673 | Alan Michael | Executive/Admin |
| 6674 | Amy Kraus | Special Needs Ministry |
| 2879 | Angela Cheshire | Children's Ministry |
| 17314 | Arianah Torres | Men's Ministry |
| 21230 | Ashley Reynolds | Special Needs Ministry |
| 22732 | Austin Powell | Worship and Production |
| 23670 | Brenda Bommarito | Connections Team |
| 26216 | Bridget Church | Communications |
| 13982 | Cam Champion | Worship and Production |
| 3262 | Christi Victor | Children's Ministry |
| 19792 | Colleen Dobbs | Care Team |
| 284 | Courtney Edmondson | Student Ministry |
| 23538 | Courtney Rehbehn | Children's Ministry |
| 10430 | Debbie Avinger | Marriage Ministry |
| 23748 | Greg Methvin | Marriage Ministry |
| 46965 | Isaac Jiles | Student Ministry *(per Brian; directory lists "Ministry Leaders")* |
| 21285 | Jason Trottie | Ministry Leaders |
| 4666 | Jen Armstrong | Small Groups |
| 24371 | Kelli Leird | Marriage Ministry |
| 5285 | Kellie Lampe | Operations |
| 15580 | Kimberley Cramer | Small Groups |
| 9393 | Kristin Baker | Connections Team |
| 7039 | Lauren Etter | Women's Ministry |
| 28926 | Leah McBain | Children's Ministry |
| 11144 | Linda Morrison | NextGen Ministry |
| 28745 | Maddy McCalley | Young Adults |
| 37195 | Makayla Tucker | Student Ministry |
| 2990 | Marcie Rumsey | Operations |
| 35320 | Margaret Bartlebaugh | Mid-Gen/Senior Adults |
| 106 | Margo Baisley | Children's Ministry |
| 8962 | Maria Jerke | Missions & Church Planting |
| 7059 | Marlene Godinez | Operations |
| 23164 | Max McCalley | Student Ministry |
| 34921 | Megan DeFilippo | Care Team |
| 665 | Melissa Pierce | Operations |
| 35319 | Ned Bartlebaugh | Care Team |
| 25605 | Sara Comer | Special Needs Ministry |
| 34835 | Steven Christopher | Men's Ministry |
| 17100 | Tino Smith | Young Adults |
| 32745 | Trace Summers | Worship and Production |
| 300 | Traci Erb | Weekday Preschool |
| 29228 | Treeka Andries | Weekday Preschool |
| 2351 | Virginia Smith | Connections Team |
| 28000 | Abbie Vinson | Student Ministry *(per Brian; directory lists "Ministry Leaders")* |
| 44574 | Alex Erkelens | Unassigned — not on public directory |
| 45948 | Anthony Aguilar | Unassigned — not on public directory |
| 46101 | Ayeli Padron | Unassigned — not on public directory |
| 45732 | Brandi Protonentis | Unassigned — not on public directory |
| 27392 | Chris Victor | Unassigned — not on public directory |
| 49649 | David Johnston | Unassigned — not on public directory |
| 4353 | Gary Tyner | Unassigned — not on public directory |
| 44564 | Jillian Diveley | Unassigned — not on public directory |
| 3222 | Matthew Webb | Unassigned — not on public directory |
| 45230 | Nancy Tassy | Unassigned — not on public directory |
| 5673 | Natalie Hite | Unassigned — not on public directory |
| 45265 | Patricia Barela | Unassigned — not on public directory |
| 46456 | Patti Flynn | Unassigned — not on public directory |
| 47918 | Stacie Tran | Unassigned — not on public directory |
| 28183 | Stephanie Hiester | Unassigned — not on public directory |
| 19570 | Weston Watts | Unassigned — confirmed off staff 2026-08-26, kept visible rather than removed |
| 33283 | TP System | System Account — non-human integration account, not a staff member |

15 people (Alex Erkelens through Stephanie Hiester above) are not resolved to a real department — they weren't on the public staff directory as of 2026-08-26 and may not be current payroll staff. Don't guess their department; confirm with Brian/Marlene and update both this table and the `ROSTER` dict together.

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

**`lookup.MemberType` schema confirmed live 2026-08-27** (`SELECT * FROM lookup.MemberType ORDER BY Id`): columns are `Id`, `Code`, `Description`, `AttendanceTypeId`, `Hardwired`, `Pending`, `Inactive`. Full table as returned (not all rows appear in `Attend`/`OrganizationMembers` usage above -- this is the complete lookup, not just observed usage):

| Id | Code | Description | AttendanceTypeId | Hardwired | Pending | Inactive |
|----|------|--------------|------------------:|-----------|---------|----------|
| 103 | DR | Director | 10 | | False | False |
| 104 | ED | Elder/Deacon Team | 30 | | False | False |
| 130 | CH | Chairman | 30 | | False | False |
| 136 | CC | Coach | 10 | | False | False |
| 140 | L | Leader | 10 | | False | False |
| 160 | T | Teacher | 10 | True | False | False |
| 161 | AT | Assistant Teacher | 10 | | False | False |
| 162 | SC | Secretary | 10 | | False | False |
| 170 | IR | In Reach Leader | 10 | | False | False |
| 172 | OR | Outreach Leader | 10 | | False | False |
| 220 | M | Member | 30 | True | False | False |
| 230 | IA | InActive | 40 | True | False | True |
| 300 | VM | Visiting Member | 30 | True | False | False |
| 310 | G | Guest | 60 | True | False | False |
| 311 | PR | Prospect | 190 | True | True | False |
| 415 | HB | Homebound | 100 | | False | False |
| 500 | IM | In-Service Member | 70 | True | False | False |
| 700 | VI | VIP | 20 | True | False | False |
| 710 | VL | Volunteer | 20 | | False | False |

`MemberTypeId = 310` (Guest) is the key one for weekly attendance reporting -- see the SM Wednesdays / D-Groups section below.

---

## SM Wednesdays / D-Groups — confirmed 2026-08-27

Live weekly snapshot (Sunday 2026-08-23 through Saturday 2026-08-29, `Attend.AttendanceFlag = 1`, meetings not `Canceled`/`DidNotMeet`), gathered while reworking `sm-attendance-pyreport.py` to handle D-Groups differently from Sunday.

**TypeId 106 is not a live D-Group signal.** Every active Wednesday D-Group org this week (Division 42 = SM Wednesdays) is `OrganizationTypeId` `201` (grade/topic classes, e.g. "SM: PS 10th Grade Apologetics F26-S27") or `207` (`SM: PS D Groups Leaders 2026-2027`) -- the same TypeIds already used for Sunday. The one org observed with TypeId `106` ("SM: CC Basics for Students") sits in Division 12 (SM Classes), not Division 42, and had zero attendance. Do not use TypeId 106 as a D-Group filter; `201`/`207` on Division 42 is confirmed correct.

**The real Sunday-vs-Wednesday difference is Guest attendance, not volunteers.** A per-meeting `Attend.MemberTypeId` breakdown for this week's D-Group orgs (query joined `Attend` -> `Meetings` -> `Organizations`, grouped by org + `MemberTypeId`) showed nearly all non-`220` attendance is `MemberTypeId = 310` (Guest), not `140`/`710` (Leader/Volunteer):

| OrganizationId | OrganizationName | 220 (Member) | 310 (Guest) |
|---|---|---:|---:|
| 4058 | SM: Identity: Daughters of the King 9th Grade Girls 2026-2027 | 31 | 3 |
| 4052 | SM: Man Up 9th Grade Guys 2026-2027 | 23 | 0 |
| 4047 | SM: PS 10th Grade Apologetics F26-S27 | 17 | 14 |
| 4050 | SM: PS 11th Grade Systematic Theology F26-S27 | 16 | 9 |
| 4051 | SM: PS 12th Grade Biblical Worldview F26-S27 | 23 | 18 |
| 4044 | SM: PS 6th Grade Alpha F26-S27 | 30 | 2 |
| 4046 | SM: PS 7th Grade New Testament F26-S27 | 30 | 13 |
| 4048 | SM: PS 8th Grade Inductive Bible Study F26-S27 | 22 (+2 as `140`) | 12 |
| 4060 | SM: PS D Groups Leaders 2026-2027 | 47 | 6 |
| 1943 | SM: PS Health and Safety | 2 | 0 |

`MemberTypeId = 310` attendance ran roughly 30-45% of total attendance on several D-Group classes this week (e.g. 18 of 41 on "PS 12th Grade Biblical Worldview," 14 of 31 on "PS 10th Grade Apologetics"). Sunday grade orgs the same week were almost entirely `MemberTypeId = 220`, with only single-digit stray `140`s.

**Correction, confirmed 2026-08-27 (name-level spot-check by Brian, then verified against `OrganizationMembers` for all 77 `MemberTypeId = 310` attendance rows across this week's D-Group meetings):** the "not formally rostered on this org" theory is wrong. **71 of 77 (92%) of the `310`-flagged people ARE already enrolled (`OrganizationMembers`) on the exact org they attended.** This is not a visitor signal and not a drop-in-from-another-org signal — it's enrolled students and leaders whose `Attend` row is getting the wrong `MemberTypeId` at check-in. Age breakdown: 63 students (ages 11-18), 12 adults (ages 40-59), 2 unresolved. 11 of the 12 adults are properly enrolled on the org they attended, including 6 on `SM: PS D Groups Leaders 2026-2027` itself (ages 40/45/45/54/55/59) — i.e. actual known leaders, correctly rostered, still tagged "Guest" on their attendance record. Heaviest-affected orgs this week: PS 12th Grade Biblical Worldview (18 rows), PS 10th Grade Apologetics (14), PS 7th New Testament (13), PS 8th Inductive Bible Study (12).

**Conclusion: this is a Wednesday D-Group check-in data-quality issue at RPC, not a query/reporting problem.** Do not build report logic that treats D-Group `MemberTypeId = 310` as meaningful (visitor, drop-in, or otherwise) until RPC's admin team (Libbie Risberg, PeopleId 1675) has looked at whatever check-in method is used for D-Groups and confirmed why it isn't pulling the person's actual enrolled role. `sm-attendance-pyreport.py`'s D-Group Guest/`NotRostered` column (added 2026-08-27, see attendance-dashboard section) should be treated as provisional/likely-noise pending that cleanup.

Also reconfirmed: `SM: PS D Groups Leaders 2026-2027` (OrgId 4060, TypeId 207) attendance is overwhelmingly `MemberTypeId = 220`, not 140/710 — same pattern already documented for `SM: All Volunteers` orgs above (don't infer role from `MemberTypeId`, use the org's `OrganizationTypeId`/name instead). And `SM: PS Health and Safety` (OrgId 1943, TypeId 207) sits in **both** Division 11 (SM Sundays) and Division 42 (SM Wednesdays) — another live multi-division `DivOrg` example (`EXISTS`, not `JOIN`).

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

`Meetings.Canceled` and `Meetings.DidNotMeet` are separate bit-flag columns used elsewhere in this repo (`data-dictionary-expander/sql/focused/RPC_Children*.sql`) to exclude non-meetings from attendance rollups — pattern is `ISNULL(m.Canceled, 0) = 0 AND ISNULL(m.DidNotMeet, 0) = 0`. Not yet in the confirmed-column list above; carried forward here since `renew-roster-report/AD_ReNewRosterReport.py` also depends on it and hasn't had a live TouchPoint run yet to verify.

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

## Native Duplicate/Merge Tables — confirmed 2026-08-26

Discovered via the 2026-08-13 structural export while researching a fuzzy-duplicate-finder tool (roundtable topic at the 2026-08-26 TouchPoint summit). TouchPoint has its own native duplicate-detection and merge pipeline at RPC — do not assume this is greenfield before building duplicate-related tooling.

| Table | Role | Approx. rows (2026-08-13) |
|---|---|---:|
| `dbo.Duplicate` | Candidate duplicate pairs. Composite PK (`id1`, `id2`), both `int` -> presumably `People.PeopleId`, not yet confirmed live. | ~21 |
| `dbo.DuplicatesRun` | History of the native duplicate-finder job runs. Columns: `id`, `started`, `count`, `processed`, `found`, `completed`, `error`, `running`. | ~32 |
| `dbo.MergeHistory` | Log of actual merges performed. Columns: `FromId`, `ToId`, `FromName`, `ToName`, `Dt`, `WhoName`, `WhoId`, `Action`. PK `FromId`. | ~3,839 |
| `People.HasDuplicates` | `bit` flag TouchPoint sets on a People record. Already used as a review signal in the RPC staff-directory export (`REVIEW_PERSON_DUPLICATE_FLAG`). | n/a |

Only ~21 open candidate pairs is low relative to the roundtable's "a ton of duplicates coming through registrations" complaint. Per Brian, the native finder does not catch nickname variants (e.g. "Jonathan" vs "Johnny" vs "Jon") — it appears to key on close/exact name matches, not a nickname-aware or general fuzzy match. Not yet confirmed: whether `DuplicatesRun` is scheduled/run regularly at RPC, or what its exact matching criteria are.

**Deployed gap-filler report:** `duplicate-finder/TP_DuplicatePersonFinder.py` (renamed 2026-08-27 from `RPC_DuplicatePersonFinder` — no RPC-specific IDs/names in it, portable to any TouchPoint church, so it got a generic `TP_` name instead of this repo's RPC-specific-script prefix) — read-only, nickname-aware + fuzzy-string audit report scoped to recently-created People records, explicitly excluding pairs already in `dbo.Duplicate`. Never merges; links out to TouchPoint's own profile/merge UI. See that folder's README for full design and pending live-validation items (notably `lookup.Origin` mapping to scope the "recent" set to registration-created records specifically, and SOUNDEX-blocking performance at RPC's live table size).

---

## Special Content - Deployed Scripts

| Tab | Name | Status |
|-----|------|--------|
| SQL Scripts | SM_TaskNote-ToDo | Deployed, filter still being tuned |
| Python Scripts | SM_OutstandingTasksList | Not yet deployed |
| Python Scripts | SM_OutstandingTaskNotifications | Deployed, tested 2026-07-03 |
| Python Scripts | SM_StaffTaskDashboard | Built, needs live TouchPoint test pass |
| Python Scripts | RPC_StaffTaskDashboard | Live-tested by Brian 2026-08-26; Alan reviewing. Reachable only via Special Content "run script" link -- not yet added as a page for other staff. |
| Python Scripts | RPC_MyTaskBoard | Built 2026-08-26, needs live TouchPoint test pass (STRING_AGG support unconfirmed). Personal Kanban-style "my tasks" view, read-only v1 -- see `outstanding-task-notifications/dashboard/README.md`. |
| Python Scripts | AD_ReNewRosterReport | Built 2026-08-26, needs live TouchPoint test pass. Generalized past ReNew-only: picks any active involvement from a configured division list (currently the two AD divisions; extensible to other ministries), Leader/Member-only roster (sorted Leaders first) + weekly attendance grid -- see `renew-roster-report/README.md`. |
| Python Scripts | TP_DuplicatePersonFinder (was RPC_DuplicatePersonFinder, renamed 2026-08-27 -- generic-portable, no RPC-specific IDs) | Live-tested by Brian 2026-08-26/27 (2026 summit roundtable follow-up), judged a clear improvement after performance and household-false-positive fixes. Read-only nickname-aware + fuzzy duplicate-person audit report, scoped to recently-created People, excludes pairs already in native `dbo.Duplicate` -- see `duplicate-finder/README.md`. |

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

Approved addition for the weekly CM attendance report -- recipient list
confirmed and PREVIEW_MODE flipped to False 2026-08-30 (14 names, see
attendance-dashboard/BACKLOG.md and CM_AttendanceDashboardEmail.py's header):
```python
if model.DayOfWeek == 1:
    model.CallScript("CM_AttendanceDashboardEmail")
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
