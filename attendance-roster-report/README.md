# Ministry Attendance Roster Report

Printable Leader/Member roster + weekly attendance grid for one or more active involvements in **any RPC ministry** — a three-step live picker (Ministry → Division → Involvement(s)) replaces the original config list, so a new ministry, division, or involvement shows up automatically with no code change. Two roster columns and the grouping/page-break behavior are configurable per print run.

## History

Originally `AD_ReNewRosterReport.py`, built for Adult Discipleship's ReNew ministry with a hardcoded `DIVISION_FILTERS` list covering just the two AD divisions. Generalized 2026-08-30 into `RPC_AttendanceRoster.py` after evaluating [`bswaby/Touchpoint`](https://github.com/bswaby/Touchpoint)'s Roll Sheet tool (see `roll-sheet-report/`), which showed the value of a live-schema-driven picker over a hand-maintained config list. Same day: added configurable columns, gender/involvement/no grouping, multi-involvement selection, and row-level security.

## What it does

`RPC_AttendanceRoster.py` (TouchPoint Special Content Python Script, read-only) is a four-stage flow, all server-rendered by the same script depending on which of `?ProgId=`, `&DivId=`, `&OrgIds=` are present in the URL:

1. **No `ProgId`** — pick a ministry (`dbo.Program`).
2. **`ProgId` set, no `DivId`** — pick a division within that ministry (`dbo.Division`).
3. **`ProgId`+`DivId` set, no valid `OrgIds`** — check one or more active (`OrganizationStatusId = 30`) involvements in that division (with member counts), plus pick the two configurable columns and the grouping mode.
4. **A valid `OrgIds` present** — the combined roster for the checked involvement(s), with the chosen columns/grouping.

A stale or invalid id/option at any stage falls back to re-rendering that stage (e.g. a bookmarked URL for a division that no longer exists just reopens the division picker) rather than erroring. Each stage has a "Back" link to the previous one; the roster's back link intentionally omits `OrgIds` (so it lands on the checkbox picker, not a re-render of the same roster) but preserves the column/grouping choices.

**Combining multiple involvements** — only combine involvements that share the same meeting schedule/calendar (e.g. several Student Ministry grade+gender classes that all meet the same Sunday). The attendance grid is one shared set of date columns, built from the union of every selected involvement's meeting dates; if the selected involvements don't actually share a schedule, the grid gets sparse and "Total" stops meaning what you'd want. This isn't currently validated in code — pick sensibly.

**The roster** (stage 4), per person:
- Name, Gender, Member Type (**Leader or Member only** — Coach/InActive/Prospect/Volunteer and any unmapped/stray `MemberTypeId` are excluded entirely)
- One attendance column per meeting date any selected involvement actually held (checkmark if present; canceled/did-not-meet meetings are excluded from the grid)
- A **Total** column summing meetings attended
- **Two configurable columns** (see below)

Sort order: by Involvement (when multiple are selected), then Leaders-before-Members, then name.

## Configurable columns

The two rightmost columns (after Total) are chosen from a dropdown at stage 3, independently:

| Value | Shows |
|---|---|
| Leave Blank | Nothing — an intentional empty write-in column (the header stays; every cell is blank), not a way to remove the column |
| Phone | `model.FmtPhone(CellPhone)` |
| Email | `EmailAddress`, falling back to `EmailAddress2` |
| Age | `People.Age` |
| Gender | `lookup.Gender.Description`/`Code`, falling back to "Unknown" |
| Grade | `lookup.GradeLevel.Code`/`Description`, falling back to the legacy `People.Grade` value |
| Marital Status | `lookup.MaritalStatus.Description`/`Code` |
| Last Name | `People.LastName` (an approximation for "who's in the same family" — there's no confirmed household/family-name field, see below) |
| Involvement (class/org name) | Which selected org/class this row belongs to — mainly useful when multiple involvements are combined |

Grade/Marital Status (Phone/Email/Involvement were already part of the original build) are **not yet RPC-confirmed** — they assume standard TouchPoint/BVCMS field names that haven't been specifically verified live the way Program/Division/DivOrg/MemberType have been elsewhere in this repo. If any throws `Invalid column name`, fix it here and fold the correction back into `DB_REFERENCE.md`.

**Address was tried and removed 2026-08-30** — a live run threw `Invalid column name 'City'`/`'State'`: `People.City`/`People.State` don't exist on RPC's schema. Likely on `Families` instead (per `DB_REFERENCE.md`, `People.FamilyId -> Families.FamilyId`), not yet confirmed. Before re-adding it, run this in `Admin > Advanced > Special Content > SQL Scripts` to find the real column names:

```sql
SELECT TABLE_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME IN ('People', 'Families')
  AND (COLUMN_NAME LIKE '%Address%' OR COLUMN_NAME LIKE '%City%' OR COLUMN_NAME LIKE '%State%' OR COLUMN_NAME LIKE '%Zip%')
ORDER BY TABLE_NAME, COLUMN_NAME
```

## Grouping / page breaks

A third stage-3 dropdown ("Group roster by") replaces the original gender-only toggle with three choices:
- **Gender** (default, matches the original behavior) — Men / Women / Unspecified Gender sections, page break between each.
- **Involvement** — one section per selected class/org (e.g. one printed page per Women's Ministry table), page break between each. Only meaningful with multiple involvements selected; with one, it's just a single section named after that org.
- **No grouping** — one flat list, no section headings, no page breaks.

## Row-level security

Unless the logged-in user (`model.UserPeopleId` — same pattern already proven in `outstanding-task-notifications/dashboard/RPC_MyTaskBoard.py` and `SM_OutstandingTasksList.py`, called "row-level security" in that folder's own README) is in `ADMIN_BYPASS_PEOPLE_IDS`, stages 1 and 2 only show a ministry/division if that person has **any** `OrganizationMembers` row (any `MemberTypeId` — deliberately not restricted to Leader yet, per Brian's direction 2026-08-30) in an org under it. This is code-level filtering, not a TouchPoint permission feature.

Confirmed 2026-08-30: Brian Vinson (PeopleId `47110`) and Marlene Godinez (PeopleId `7059`, per `DB_REFERENCE.md`'s staff roster) should see everything; everyone else is scoped to what they're actually in.

Stage 3's org list is **not** further filtered by RLS — once a division is unlocked, every active org in it is selectable, matching "has an involvement in that ministry and division" rather than "personally leads this specific org."

## What makes the picker church-wide

Instead of a hardcoded list of divisions, stage 1 queries `dbo.Program` directly, stage 2 queries `dbo.Division WHERE ProgId = <chosen>`, and stage 3 reuses the same `EXISTS`-against-`DivOrg` pattern the original script used (per `DB_REFERENCE.md`: `Organizations -> DivOrg` is one-to-many, so a plain `JOIN` would duplicate rows) — just parameterized by the single division chosen in stage 2 instead of a fixed list.

The only config left is `EXCLUDED_PROGRAM_IDS` at the top of the script — RPC's internal reporting/admin "programs" that aren't real ministries a staff member would pick a roster from (`1124`/`1127` "Reporting (RP) All Programs ONLY/OUTSIDE Sun AM", `1130` "CT Admin", `1137`/`1138` "Reporting (RP) CC/PS Children ONLY Sun AM", `1141` "RP PS Students" — all confirmed live 2026-08-30, see `DB_REFERENCE.md`'s `OrganizationStructure` section). Add to that list only if a *new* admin/reporting Program shows up — never add a real ministry there or anywhere else; ministries should need zero code changes to appear. This filter applies to everyone, admins included.

If a future ministry needs something structurally different (e.g. split by campus, a non-weekly meeting cadence, additional member types beyond Leader/Member), that's a real code change, not something the picker can route around — flag it rather than assuming this script covers it as-is.

## Saving a specific roster's settings

Everything (Program, Division, selected involvements, columns, grouping) lives in the URL query string, so bookmarking the generated roster's URL "saves" that exact configuration to rerun later — no extra feature needed. A true named/saved-config system (like Roll Sheet's, persisted via `model.WriteContentText`) hasn't been built; consider it only if bookmarking proves insufficient in practice.

## Confirmed for ReNew Fall 2026 (from the original AD-only build)

- `OrganizationId = 3906`, `OrganizationName = "ReNew Fall 2026"`, `OrganizationStatusId = 30` (Active), `OrganizationTypeId = 201`.
- Division 126 "AD ReNew" (also linked in Division 31 "AD Classes/Meetings/Groups"), Program 1119 "Adult Discipleship" (AD).
- Meets weekly on **Mondays**. Confirmed live 2026-08-26: two meetings held so far (8/17, 8/24).
- `lookup.Gender`: 1 = Male, 2 = Female, 0 = Unknown.
- `lookup.MemberType`: 140 = Leader, 220 = Member (the only two shown on the roster).

See `DB_REFERENCE.md` for the full write-up (Program 1119 addition, `Meetings.Canceled`/`Meetings.DidNotMeet` filter, ReNew org family discovered via name search, and the `OrganizationStructure`/`EXCLUDED_PROGRAM_IDS` discovery).

## Deploy

`Admin > Advanced > Special Content > Python Scripts > +New`, script name `RPC_AttendanceRoster`, paste in the file contents. **Access via `/PyScript/RPC_AttendanceRoster`**, not the Special Content admin "run" preview — the picker's Apply buttons submit a GET form back to the current URL, and the admin preview's own chrome would otherwise bleed into a print job. No email is sent.

## Status

Round 1–2 history (single hardcoded org, then the AD-only division-driven picker) is in git history under the old `renew-roster-report/AD_ReNewRosterReport.py` path.

Round 3 (2026-08-30): generalized to the three-stage live Program/Division/Involvement picker.

Round 4 (same day): configurable columns (incl. "Leave Blank"), a unified Gender/Involvement/None grouping dropdown, multi-involvement selection via checkboxes, and row-level security via `model.UserPeopleId`.

**First live run (2026-08-30) found a real bug**: the Address column threw `Invalid column name 'City'`/`'State'` — `People.City`/`People.State` don't exist on RPC's schema. Removed (see "Configurable columns" above for the discovery query to run before re-adding it). Everything else in that same run was not reported as broken.

Syntax-checked (`python3 -m py_compile`) and smoke-tested locally with mocked `q`/`model` objects across four rounds of tests, covering: the program/division/org pickers with exclusion filtering, invalid-id fallback at every stage, admin-bypass vs. scoped row-level security (including a zero-membership user seeing nothing), the checkbox picker, multi-involvement combined rosters grouped by involvement, custom column selection including "blank" and "Involvement", grouping-mode fallback on an invalid value, and (after the Address removal) that no query references `p.City`/`p.State` anymore. Still needs a full live pass to confirm:

- The three-stage picker and row-level-security `EXISTS` filters actually walk correctly through TouchPoint's live `Program`/`Division`/`DivOrg`/`OrganizationMembers` data end to end.
- `EXCLUDED_PROGRAM_IDS` fully hides RPC's admin/reporting Programs from the ministry picker (only spot-checked against `DB_REFERENCE.md`'s confirmed list, not re-queried live here).
- The Grade/Marital Status column SQL (see "Configurable columns" above) against RPC's actual schema — not flagged as broken by the first live run, but not independently re-verified either.
- Everything already flagged as unconfirmed in the original AD-only build: `Meetings.Canceled`/`Meetings.DidNotMeet` behavior generalized across whichever org(s) get picked, and whether `OrganizationMembers` for other ministries' orgs contains anyone who should be excluded beyond the Leader/Member filter.
