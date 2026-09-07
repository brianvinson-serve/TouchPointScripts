# Ministry Attendance Roster Report

Printable Leader/Member roster + weekly attendance grid for one or more active involvements in **any RPC ministry** — a three-step live picker (Ministry → Division → Involvement(s)) replaces the original config list, so a new ministry, division, or involvement shows up automatically with no code change. Two roster columns, the sort order, the grouping/page-break behavior, and an optional attendance start date are configurable per print run.

Involvement **sub-groups** (TouchPoint's SubGroups feature) can be used as a column, a sort order, or a page break — offered only when the involvement(s) you picked actually have any. See "Sub-groups" below.

## History

Originally `AD_ReNewRosterReport.py`, built for Adult Discipleship's ReNew ministry with a hardcoded `DIVISION_FILTERS` list covering just the two AD divisions. Generalized 2026-08-30 into `RPC_AttendanceRoster.py` after evaluating [`bswaby/Touchpoint`](https://github.com/bswaby/Touchpoint)'s Roll Sheet tool (see `roll-sheet-report/`), which showed the value of a live-schema-driven picker over a hand-maintained config list. Same day: added configurable columns, gender/involvement/no grouping, multi-involvement selection, and row-level security.

## What it does

`RPC_AttendanceRoster.py` (TouchPoint Special Content Python Script, read-only) is a four-stage flow, all server-rendered by the same script depending on which of `?ProgId=`, `&DivId=`, `&OrgIds=` are present in the URL:

1. **No `ProgId`** — pick a ministry (`dbo.Program`).
2. **`ProgId` set, no `DivId`** — pick a division within that ministry (`dbo.Division`).
3. **`ProgId`+`DivId` set, no valid `OrgIds`** — check one or more active (`OrganizationStatusId = 30`) involvements in that division (with member and sub-group counts, and a search box to narrow a long list), plus pick the two configurable columns, the sort order, the grouping mode, and an optional attendance start date.
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
| Sub-Group | The member's sub-group(s) on that involvement, comma-joined if they're in more than one. Only selectable when the picked involvement(s) have sub-groups — see below |

Grade/Marital Status (Phone/Email/Involvement were already part of the original build) are **not yet RPC-confirmed** — they assume standard TouchPoint/BVCMS field names that haven't been specifically verified live the way Program/Division/DivOrg/MemberType have been elsewhere in this repo. If any throws `Invalid column name`, fix it here and fold the correction back into `DB_REFERENCE.md`.

**Address was tried and removed 2026-08-30** — a live run threw `Invalid column name 'City'`/`'State'`: `People.City`/`People.State` don't exist on RPC's schema. Likely on `Families` instead (per `DB_REFERENCE.md`, `People.FamilyId -> Families.FamilyId`), not yet confirmed. Before re-adding it, run this in `Admin > Advanced > Special Content > SQL Scripts` to find the real column names:

```sql
SELECT TABLE_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME IN ('People', 'Families')
  AND (COLUMN_NAME LIKE '%Address%' OR COLUMN_NAME LIKE '%City%' OR COLUMN_NAME LIKE '%State%' OR COLUMN_NAME LIKE '%Zip%')
ORDER BY TABLE_NAME, COLUMN_NAME
```

## Attendance since (optional date filter)

A fourth stage-3 field, "Attendance since," is a plain HTML5 date input, blank by default. When set, both the meeting-date grid columns and the Total column only cover meetings on/after that date — e.g. Student Ministry involvements where a senior's single class has meeting/attendance history going back several school years, printed for just the current school year (`8/16/2026` forward). Leaving it blank keeps the original all-time behavior.

Round-trips through the URL the same way as the column/grouping choices (`&SinceDate=YYYY-MM-DD`), and is preserved across the roster's "Back" link. Validated with a strict `^\d{4}-\d{2}-\d{2}$` regex before it's ever interpolated into SQL — anything else (blank, malformed, a bad paste) silently falls back to no filter rather than erroring or reaching the query.

## Exclude zero-attendance members (optional)

A checkbox next to the date field, unchecked by default, drops anyone whose attendance count (within the "Attendance since" range, if set) is zero — e.g. a printed roster of only students who actually showed up this school year, rather than the full class list including no-shows. Round-trips as `&ExcludeZero=1`. Applied after Total is computed but before grouping, so section counts/headers and the page's total-member count all reflect the trimmed list.

## Living inside TouchPoint's page (CSS isolation)

This script's HTML is injected into a TouchPoint page that brings its own Bootstrap-derived stylesheet, so **generic class names are a live collision risk.** Confirmed on the first live run (2026-09-07): the branded header rendered short with its "RockPointe Church" eyebrow missing entirely, because TouchPoint's CSS defines rules on names this page also used.

Two defenses, both required — neither is sufficient alone:

1. **Every class is prefixed `rr-`** (`rr-bar`, `rr-card`, `rr-status`, …). Prefixing is what actually prevents collisions. Specificity does *not* help when the host declares a property this page never declares (a host `.church { display: none }` wins by default, because there's nothing to override), nor when the host uses `!important`.
2. **Every rule is scoped under `#rpcAttendanceRoster`** at render time by `scope_css()`, and the page content is wrapped in that element. This protects the bare *element* selectors that can't be prefixed — `h1`, `button`, `select`, `legend`, `th`, `td` — which TouchPoint definitely styles. `body` rules are retargeted at the wrapper, so this page no longer tries to restyle TouchPoint's own `<body>`. `@page` is passed through unprefixed, since it takes no selector.

`scope_css()` lets the CSS constants stay readable (write `.rr-card { … }`, not `#rpcAttendanceRoster .rr-card { … }`) with the scoping applied at print time. The test suite renders every screen against a deliberately hostile stylesheet — `.church{display:none}`, `.bar{padding:0 !important}`, `.orglist{max-height:none !important}` — and asserts the page still comes out right. **If you add a class, prefix it; if you add a rule, let `scope_css()` handle it.**

## Searching a long involvement list

Divisions like `AD Classes/Meetings/Groups` carry dozens of active involvements — **156 of them, confirmed live 2026-09-07** — so the checkbox list has a **search box** that filters it by name as you type (case-insensitive substring, with a clear button and a "No involvements match that search" state).

**A search only hides rows — it never unchecks one.** Anything already checked stays selected, still counts toward sub-group availability, and still ends up on the roster. The line under the list keeps that honest: `Showing 4 of 34 · 2 selected · 1 of them hidden by the search (still included)`. It stays empty until there's something to report.

Two implementation notes worth keeping if this gets touched:
- Filtering toggles a `.hide { display: none !important; }` class rather than the `hidden` attribute, because `.orgcb { display: block }` would otherwise win over the browser's default `[hidden]` rule and the "hidden" rows would stay visible.
- Enter inside the search box is suppressed, so typing a search and hitting Enter doesn't submit the form with whatever happens to be checked.

## Sub-groups

TouchPoint's involvement-level **SubGroups** feature (`dbo.MemberTags` = the sub-groups defined on an involvement, `dbo.OrgMemMemTags` = who's in them) is surfaced in three independent places, all on stage 3:

- **As a column** — "Sub-Group" in either configurable column dropdown.
- **As a sort** — "Sort members by → Sub-Group" (see below).
- **As a page break** — "Group roster by → Sub-Group", one printed page per sub-group.

**Only offered when the checked involvement(s) actually have sub-groups.** Stage 3 loads a per-involvement sub-group count for every active org in the division and hands it to the browser as a small JS map; as boxes are ticked, the three Sub-Group choices enable or disable live and a status line says why ("2 sub-groups found in your selection…" / "The involvement(s) you checked have no sub-groups…"). Options are **disabled and relabelled, never hidden**, so nothing appears and vanishes as the selection changes; if a Sub-Group choice was already made and then becomes unavailable, it resets to the default and the status line says so.

That's a convenience layer only — `valid_group_by()`/`valid_sort_by()` plus a server-side stage-4 fallback still backstop it, so a hand-edited URL, a stale bookmark, or a browser with JS off gets a sane roster (falling back to the default grouping/sort, with a note in the roster's meta line) instead of an error.

**A member can be in more than one sub-group of the same involvement.** That shapes each use differently:
- *Column* — their sub-groups are comma-joined into one cell ("Table 1, Table 2").
- *Page break* — they are printed **once under each** of their sub-groups, so a page handed to a sub-group's leader is complete. Section counts can therefore sum to more than the roster's total member count; the meta line says so.
- *Sort* — they sort by their comma-joined label.

Members with no sub-group collect into a final **"(No sub-group)"** section, always printed last.

**Sub-group names are only unique within an involvement** (`MemberTags.OrgId`), so when several involvements are combined, sub-group section headings are prefixed with the involvement name — otherwise two unrelated groups both called "Table 1" would merge onto one page. With a single involvement selected the labels stay unprefixed.

**Implementation note:** this deliberately does *not* use the `STUFF(... FOR XML PATH(''))` string-concat that `roll-sheet-report/TPxi_RollSheet.py` uses for the same data. `FOR XML PATH` XML-escapes the tag name, so a sub-group called `Men & Women` comes back as `Men &amp; Women` and gets double-escaped by `esc()` on render. The names are fetched as rows and joined in Python instead — which grouping needs anyway.

## Sort order

A stage-3 "Sort members by" dropdown:
- **Default** — the original behavior, unchanged: Involvement, then Leaders before Members, then name (applied by `sql_roster`'s `ORDER BY`).
- **Sub-Group** — re-sorts in Python by the sub-group label, with the default order kept as the tiebreak (Python's sort is stable), so members inside one sub-group still read Leaders-first and alphabetically. Members with no sub-group sort last.

Sorting is independent of grouping: with gender grouping still on, a sub-group sort applies *within* the Men and Women sections rather than replacing them.

## Grouping / page breaks

A stage-3 dropdown ("Group roster by") replaces the original gender-only toggle with four choices:
- **Gender** (default, matches the original behavior) — Men / Women / Unspecified Gender sections, page break between each.
- **Involvement** — one section per selected class/org (e.g. one printed page per Women's Ministry table), page break between each. Only meaningful with multiple involvements selected; with one, it's just a single section named after that org.
- **Sub-Group** — one section per sub-group, page break between each; see "Sub-groups" above for the multi-sub-group and name-collision behavior.
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

Everything (Program, Division, selected involvements, columns, sort, grouping) lives in the URL query string, so bookmarking the generated roster's URL "saves" that exact configuration to rerun later — no extra feature needed. A true named/saved-config system (like Roll Sheet's, persisted via `model.WriteContentText`) hasn't been built; consider it only if bookmarking proves insufficient in practice.

**Bookmarked URLs from earlier versions keep working, and this is enforced by tests.** Staff have bookmarked URLs against several iterations of this report, so backward compatibility is a hard requirement, not a nice-to-have. Two properties protect it:

- New option values are **appended** to `FIELD_OPTIONS`/`GROUP_BY_OPTIONS` and matched **by name, not position**, so adding `subgroup` can't shift the meaning of an existing `Col1=age` or `GroupBy=involvement`.
- The new `SortBy` parameter is **optional** — absent from every pre-existing bookmark, and `valid_sort_by("")` returns the original default order.

`test_rpc_attendance_roster.py` replays every query-string shape an existing bookmark could hold against both the pre-sub-group baseline (git `d15f4ae`) and the current script, and asserts the rendered roster rows and section headings are identical. Keep those tests passing when changing option lists or parameter names.

## Confirmed for ReNew Fall 2026 (from the original AD-only build)

- `OrganizationId = 3906`, `OrganizationName = "ReNew Fall 2026"`, `OrganizationStatusId = 30` (Active), `OrganizationTypeId = 201`.
- Division 126 "AD ReNew" (also linked in Division 31 "AD Classes/Meetings/Groups"), Program 1119 "Adult Discipleship" (AD).
- Meets weekly on **Mondays**. Confirmed live 2026-08-26: two meetings held so far (8/17, 8/24).
- `lookup.Gender`: 1 = Male, 2 = Female, 0 = Unknown.
- `lookup.MemberType`: 140 = Leader, 220 = Member (the only two shown on the roster).

See `DB_REFERENCE.md` for the full write-up (Program 1119 addition, `Meetings.Canceled`/`Meetings.DidNotMeet` filter, ReNew org family discovered via name search, and the `OrganizationStructure`/`EXCLUDED_PROGRAM_IDS` discovery).

## Styling

The three builder screens (Ministry → Division → Involvement + options) use the **main RockPointe Church brand** — Navy `#0C2340` header with a Sunshine Yellow `#FFD242` rule, Curious Blue `#1D6A94` links, Space Blue `#183D5F` on hover, Light Gray `#D1D3D4` borders — plus a "1. Ministry › 2. Division › 3. Involvement + options" step indicator so it's clear where you are in the flow. Main brand rather than an Adult Discipleship or ministry sheet, per Comms: this is a church-wide staff tool, not a ministry-audience artifact.

The stage-3 card's two groups are labelled **"Involvements"** and **"Print options"** — deliberately *not* "Step 1/Step 2", which collided with the "3. Involvement + options" breadcrumb above and made the page look like it had two different step counters. If those legends get renamed again, check the sub-group status-line copy, which refers to "Print options below" by name.

Brand fonts (Bebas / Montserrat / HelveticaNeue) are declared as closest-safe stacks with no webfont `<link>` — TouchPoint-hosted pages can't load webfonts reliably, so the hex values carry the brand. `BUILDER_CSS`/`ROSTER_CSS` are module-level constants passed into the page templates as `.format()` arguments rather than living inside them, so their CSS braces don't have to be doubled.

The **roster itself (stage 4) stays deliberately print-first**: white background, brand color used for the heading, the yellow rule under it, and table-header text, but no filled backgrounds — it's a landscape sheet printed one page per section, and flooding it with navy would burn toner for no benefit.

Each grouped section renders as its own `<table>`, which browsers size independently — so the first three columns carry explicit `width` suggestions to keep sections lined up page-to-page. They're suggestions, not caps: a long name still widens its column.

## Tests

`test_rpc_attendance_roster.py` — offline, no live TouchPoint or DB access, fabricated (non-PII) fixture data:

```
python3 attendance-roster-report/test_rpc_attendance_roster.py
```

It mocks `q`/`model`, `exec`s the real script end-to-end, and captures the printed HTML. Coverage: bookmark compatibility against the `d15f4ae` baseline (see above), sub-group column/sort/grouping behavior, multi-sub-group members appearing under each section, cross-involvement sub-group name collisions, the no-sub-groups fallbacks, all three builder screens, and the row-level-security paths. Exits non-zero on failure.

## Deploy

`Admin > Advanced > Special Content > Python Scripts > +New`, script name `RPC_AttendanceRoster`, paste in the file contents. **Access via `/PyScript/RPC_AttendanceRoster`**, not the Special Content admin "run" preview — the picker's Apply buttons submit a GET form back to the current URL, and the admin preview's own chrome would otherwise bleed into a print job. No email is sent.

## Status

Round 1–2 history (single hardcoded org, then the AD-only division-driven picker) is in git history under the old `renew-roster-report/AD_ReNewRosterReport.py` path.

Round 3 (2026-08-30): generalized to the three-stage live Program/Division/Involvement picker.

Round 4 (same day): configurable columns (incl. "Leave Blank"), a unified Gender/Involvement/None grouping dropdown, multi-involvement selection via checkboxes, and row-level security via `model.UserPeopleId`.

Round 5 (2026-08-31): optional "Attendance since" date filter and "Exclude zero-attendance members" checkbox (see above), requested for Student Ministry involvements with several school years of history under one class/org.

Round 6a (2026-09-07, after a live pass): Debbie confirmed the sub-group work reads correctly against real data. Reviewing the deployed page in a browser then surfaced four things:

- **CSS collisions with TouchPoint's own stylesheet** — the branded header rendered short with its eyebrow line missing. Fixed by prefixing every class and scoping every rule (see "Living inside TouchPoint's page" above). This was invisible in local rendering, which has no host stylesheet.
- **156 active involvements** in Division 31, not the couple of dozen assumed — so a **search box** on the involvement list (see above) is essential rather than a nicety.
- The **"Step 1 / Step 2"** legends collided with the "3. Involvement + options" breadcrumb, making the page look like it had two step counters; renamed to "Involvements" / "Print options".
- Grouped roster sections each render as their own table and so didn't line up column-for-column; the leading columns now carry width hints.

Round 6 (2026-09-07): **sub-group support** — as a column, a sort order, and a page-break grouping, offered only when the selected involvement(s) have sub-groups (see "Sub-groups" above). Requested by Debbie Avinger (Adult Discipleship) after discovering she could create sub-groups inside her involvement. Same round: the builder screens restyled to the main RPC brand with a step indicator, and `test_rpc_attendance_roster.py` added — including the bookmark-compatibility suite, since staff have bookmarked URLs from several earlier iterations.

**Still needs a live pass for the sub-group work specifically:**

- That `dbo.MemberTags` / `dbo.OrgMemMemTags` return what TouchPoint's involvement UI shows as "SubGroups" for a real RPC involvement — the tables and their scale are confirmed in `DB_REFERENCE.md`, but this report's specific joins have not been run live.
- Whether RPC involvements carry `MemberTags` rows created for **other** purposes (`DB_REFERENCE.md` notes RPC's existing usage skews toward event-RSVP options and volunteer-scheduling slots, which share this table). If those show up as noise in the picker's sub-group counts, this may need a filter — currently every `MemberTags` row on an involvement counts as a sub-group.
- The sub-group count query joins `dbo.Organizations` and `dbo.DivOrg` for every active org in a division; fine at RPC's scale by inspection, not timed live.

**First live run (2026-08-30) found a real bug**: the Address column threw `Invalid column name 'City'`/`'State'` — `People.City`/`People.State` don't exist on RPC's schema. Removed (see "Configurable columns" above for the discovery query to run before re-adding it). Everything else in that same run was not reported as broken.

Syntax-checked (`python3 -m py_compile`) and smoke-tested locally with mocked `q`/`model` objects across four rounds of tests, covering: the program/division/org pickers with exclusion filtering, invalid-id fallback at every stage, admin-bypass vs. scoped row-level security (including a zero-membership user seeing nothing), the checkbox picker, multi-involvement combined rosters grouped by involvement, custom column selection including "blank" and "Involvement", grouping-mode fallback on an invalid value, and (after the Address removal) that no query references `p.City`/`p.State` anymore. Still needs a full live pass to confirm:

- The three-stage picker and row-level-security `EXISTS` filters actually walk correctly through TouchPoint's live `Program`/`Division`/`DivOrg`/`OrganizationMembers` data end to end.
- `EXCLUDED_PROGRAM_IDS` fully hides RPC's admin/reporting Programs from the ministry picker (only spot-checked against `DB_REFERENCE.md`'s confirmed list, not re-queried live here).
- The Grade/Marital Status column SQL (see "Configurable columns" above) against RPC's actual schema — not flagged as broken by the first live run, but not independently re-verified either.
- Everything already flagged as unconfirmed in the original AD-only build: `Meetings.Canceled`/`Meetings.DidNotMeet` behavior generalized across whichever org(s) get picked, and whether `OrganizationMembers` for other ministries' orgs contains anyone who should be excluded beyond the Leader/Member filter.
