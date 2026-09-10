# Ministry Attendance Count Report

Attendance **counts** for one or more active involvements in **any RPC ministry** — the roster report's live three-step picker (Ministry → Division → Involvement(s)) in front, the SM/CM attendance dashboard's grid behind it.

```
Involvement                 9/7  8/31  8/24 | Mtgs Total  Avg | Members Leaders
------------------------------------------------------------------------------
SM: CC 6th Guys              15    16    13 |    3    44 14.7 |      37       6
SM: CC 6th Girls             10     ·    11 |    2    21 10.5 |      19       2
SM: PS 9th Guys               0    16    19 |    3    35 11.7 |      29       6
------------------------------------------------------------------------------
TOTAL                        25    32    43 |    3   100 33.3 |      85      14
```

## Why this exists

Built 2026-09-09 from a request by a staff member already using `attendance-roster-report/` who wanted counts, not names.

The two existing tools each had half of it:

| | Picker | Output |
|---|---|---|
| `attendance-roster-report/RPC_AttendanceRoster.py` | Church-wide, live from `Program`/`Division`/`DivOrg` | Person-level printable roster |
| `attendance-dashboard/sm-attendance-pyreport.py` | None — hardcoded to SM (Program 1109, Div 11/42) | Counts grid + stat bar |

This is the missing diagonal: any ministry, counts output. It does **not** replace either one. The roster is still the tool when you need names on a page a leader can carry; the SM/CM dashboards are still the tool for the weekly SM/CM cadence with their ministry-specific campus/grade/gender grouping and their scheduled recap emails.

## What it does

`RPC_AttendanceCounts.py` (TouchPoint Special Content Python Script, read-only) is a four-stage flow, all server-rendered by the same script depending on which of `?ProgId=`, `&DivId=`, `&OrgIds=` are present:

1. **No `ProgId`** — pick a ministry (`dbo.Program`).
2. **`ProgId`, no `DivId`** — pick a division within it (`dbo.Division`).
3. **`ProgId`+`DivId`, no valid `OrgIds`** — check involvements, set the date range, pick the options.
4. **Valid `OrgIds`** — the counts grid.

A stale or invalid id at any stage falls back to re-rendering that stage rather than erroring, so a bookmarked URL for a division that no longer exists just reopens the division picker. Each stage has a Back link; the report's back link omits `OrgIds` (landing on the checkbox picker) but preserves the date range and every option.

## The three cell states

This is the whole reason to read the grid, and it's the one thing `NumPresent`-based reports can't show you:

| Cell | Means | Do something? |
|---|---|---|
| `14` | A meeting was held; 14 people were marked present. | No |
| **`0`** (red) | A meeting was held and **nobody was marked present.** | **Yes** — almost always a leader who didn't take attendance, not an empty room |
| `·` (dim) | That involvement held no meeting that day. | No — nothing to chase |

Collapsing the last two into a shared "0" is what makes most attendance exports useless for finding missing attendance, so they're kept apart here.

## Clicking through to TouchPoint

Every number on the grid is a link back to what it summarizes, so the report is a starting point rather than a dead end.

| Click | Goes to |
|---|---|
| An **involvement name** | `/Org/{OrganizationId}` — that involvement in TouchPoint |
| A **count** in a date cell | `/Meeting/{MeetingId}` — that meeting's own attendance list: names, present/absent, member type, headcount |
| A **red `0`** | Same — deliberately linked, since a meeting nobody took attendance for is the cell most worth opening |
| A count with a small **superscript** (`10²`) | `/Org/{OrganizationId}#tab-Meetings-tab` — the involvement held that many meetings that day and they're summed into one cell, so there's no single meeting to open |
| A dim **·** | Nothing — not a link, because no meeting exists to open |

The TOTAL row isn't linked: it spans involvements, so there's nothing single to point at. Grid links open in a new tab (the report you just built stays put); the page's own Back link deliberately doesn't.

**URL patterns.** `/Org/{id}` is documented ([Involvement — Defined and Dissected](https://docs.touchpointsoftware.com/Organizations/Organization.html): "This ID can be found at the end of the URL when you are viewing the Involvement"). `/Meeting/{MeetingId}` and the `#tab-Meetings-tab` anchor are not in the public docs, but are used by two independent `bswaby/Touchpoint` tools (`TPxi_AttendanceMarkings`, `TPxi_SQLQueryExplorer`) — good evidence, still worth a click on the first live run. The [Meeting Page docs](https://docs.touchpointsoftware.com/Organizations/Meeting_Index.html) confirm that page is the attendance list.

Links are built from `model.CmsHost`, the pattern the deployed task dashboards already use for `/Person2/{id}`. A missing or trailing-slashed `CmsHost` degrades to host-relative URLs rather than breaking, since this report is served from the same TouchPoint host.

**The CSV export contains none of this** — no URLs, no markup, no superscripts, just the values. It's assembled server-side from the raw numbers rather than scraped out of the rendered table, which is exactly why link markup can't leak into it. A multi-meeting cell exports as its plain number.

## Counts come from `Attend`, not `Meetings.NumPresent`

**This is the deliberate difference from the SM/CM dashboards, and the two reports can legitimately disagree.**

- `Meetings.NumPresent` is a single recorded headcount for the meeting. Fast, but blended: no way to separate students from the adults serving them.
- `dbo.Attend` rows are the individually-marked people (`AttendanceFlag = 1`, `NoShow` excluded, per `DB_REFERENCE.md`). Each row carries its own `MemberTypeId`, which is what makes the Members/Leaders split possible.

A class that records "18 present" but only marks 15 individuals reads **15** here and **18** on `sm-attendance-pyreport.py`. That gap is a real data-entry finding, not a bug in either report — but don't file it as a discrepancy without checking which source each report used first.

### Member-type buckets

| Bucket | `MemberTypeId` |
|---|---|
| Members | 220 |
| Leaders | 140 Leader, 136 Coach, 710 Volunteer |
| Other | everything else — 310 Guest, and any unmapped/stray value |

Total always equals Members + Leaders + Other, so the arithmetic reconciles on the page. The **Other** column is rendered only when it's nonzero, and when it appears the notes name which member types landed in it — so an unmapped id shows up visibly instead of silently inflating one of the two named columns. Add a new id to `MEMBER_TYPE_BUCKETS` if one turns out to belong with Members or Leaders.

Every id here is live-confirmed in `DB_REFERENCE.md`, including **310 = Guest**: its `Attend` section records a per-meeting `Attend.MemberTypeId` breakdown across eight D-Group orgs (2026-08-23 – 2026-08-29) showing 220 Member and 310 Guest as the dominant values, with one org also carrying `140`. If some other id shows up anyway, it lands in Other and the notes name it as "Type NNN" — visible, not silent.

### Visits, not people

A cell counts attendance **visits**. An organization holding several meetings on one date (per `DB_REFERENCE.md`, the PS Welcome Team had three on 2026-08-16) sums all of them into that date's cell — which is the documented-correct rollup — so someone attending two of those counts twice. The report says so in its own notes; don't read a cell as "distinct people."

## Stage-3 options

Everything round-trips through the query string, so bookmarking a generated report's URL "saves" that configuration.

- **Involvements** — checkboxes with a search box, plus **Select all shown** / **Clear all**. Unlike the roster, involvements here do *not* need to share a meeting schedule: each gets its own row, and a day one didn't meet is a `·` rather than a misleading zero. *Select all shown* is scoped to the current search (that's how you grab "every 6th grade class" without ticking twelve boxes); *Clear all* deliberately is not, so it always means what it says. A search only hides rows — it never unchecks one, and the line under the list says how many selected rows the search is hiding.
- **Date range** (`&StartDate=` / `&EndDate=`, both `YYYY-MM-DD`) — with 4 / 8 / 13-week presets, defaulting to the last 8 weeks. Both ends are required, unlike the roster's open-ended "attendance since". A backwards range is swapped rather than queried as empty. Past 60 columns the report keeps the most recent 60 and says so — grouping by week is usually the better answer than narrowing the range.
- **Group columns by** (`&GroupDates=`) — `date` (default, one column per meeting date) or `week` (one column per week). See below.
- **Count who** (`&CountWho=`) — Everyone / Members only / Leaders & volunteers only. Anything but Everyone filters *every* number on the page, and the Members/Leaders breakdown columns are dropped (they'd just restate the filter) with a note saying what the grid is filtered to.
- **Sort involvements by** (`&SortBy=`) — name (default), or total attendance high-to-low. Name is the tiebreak on totals, so equal rows don't swap order between runs.
- **Hide involvements that held no meeting in this range** (`&HideEmpty=1`) — off by default. When it hides something, the notes say how many.

## Grouping the columns by week

`&GroupDates=week` collapses each week into a single column instead of one column per meeting date. Weeks run **Sunday–Saturday** and are labelled by their Sunday (`Wk 8/23`, hovering for `August 23-29`).

This is the answer to a long "since" range. Sixty-one daily meetings overflow the 60-column cap by date; the same range is nine week columns with nothing dropped — and because the cap is applied *after* grouping, switching to weeks genuinely buys columns back rather than truncating to 60 dates and then collapsing those into a handful of weeks.

What changes, and what doesn't:

| | By date | By week |
|---|---|---|
| Column | One meeting date | All meetings that week, summed |
| Roll-up column | **Mtgs** — meeting dates held | **Weeks** — weeks in which it met |
| **Avg** | Total ÷ dates it met | Total ÷ weeks it met |
| Stat bar | "meeting dates", "avg per date" | "weeks with meetings", "avg per week" |
| **Total** | Identical — regrouping moves columns, it never changes the arithmetic |

The cell states carry over unchanged: a `·` now means "held no meeting *that week*", and a red `0` means it met that week with nobody marked. A week cell covering several meetings gets the same superscript treatment as a date with several meetings (`12²` → the involvement's Meetings tab), since there's no single meeting to open. A week containing exactly one meeting still deep-links straight to it.

Week bucketing is computed in Python, deliberately **not** with T-SQL's `DATEPART(dw, ...)`, whose answer depends on the session's `DATEFIRST` — the exact trap `DB_REFERENCE.md` flags (`OrgSchedule.SchedDay = 0` is Sunday, while `DATEPART(dw)` calls Sunday 1 under `SET DATEFIRST 7`).

CSV headers become `Week of 2026-08-23` — ISO, like the date-mode headers.

## Output

- **Stat bar** — involvements, meeting dates, total attendance, average per date, peak date and its count.
- **Grid** — sticky header row and sticky involvement column, so scrolling a wide grid keeps both labels in view.
- **Export CSV** — built server-side and embedded, not scraped out of the DOM, so it can't drift from the table or inherit its HTML entities. Dates export as ISO `YYYY-MM-DD`; a did-not-meet cell exports blank, not `0`. Filename carries the range.
- **Print** — landscape, with the buttons and back link suppressed.

## Living inside TouchPoint's page (CSS isolation)

Same two-defense pattern `RPC_AttendanceRoster.py` learned the hard way on its first live run (2026-09-07), when TouchPoint's own Bootstrap-derived stylesheet blanked the branded header's eyebrow line. Both are required; neither is sufficient alone:

1. **Every class is prefixed `ac-`.** Prefixing is what actually prevents collisions — specificity doesn't help when the host declares a property this page never declares (a host `.church { display: none }` wins by default), nor when the host uses `!important`.
2. **Every rule is scoped under `#rpcAttendanceCounts`** by `scope_css()` at render time, with the page wrapped in that element. This protects the bare *element* selectors that can't be prefixed — `table`, `th`, `td`, `button`, `select` — which TouchPoint definitely styles. `body` rules are retargeted at the wrapper so this page never restyles TouchPoint's own `<body>`. `@page` passes through unprefixed, since it takes no selector.

`scope_css()` is copied from `RPC_AttendanceRoster.py` rather than shared: TouchPoint Special Content scripts are each deployed as one standalone blob with no import path between them. **If you add a class, prefix it; if you add a rule, let `scope_css()` handle it.**

## Row-level security

Same `model.UserPeopleId` pattern as the roster report and `outstanding-task-notifications/`. Unless the logged-in user is in `ADMIN_BYPASS_PEOPLE_IDS` (Brian Vinson `47110`, Marlene Godinez `7059`), stages 1 and 2 only offer a ministry/division that person has *any* `OrganizationMembers` row under — any `MemberTypeId`, deliberately not restricted to Leader. Stage 3's involvement list is not further filtered: once a division is unlocked, every active org in it is selectable. This is code-level filtering, not a TouchPoint permission feature.

`EXCLUDED_PROGRAM_IDS` (internal reporting/admin "programs" — 1124, 1127, 1130, 1137, 1138, 1141) are hidden from the ministry picker for everyone, admins included. Keep it in sync with `RPC_AttendanceRoster.py`; both lists come from `DB_REFERENCE.md`'s OrganizationStructure writeup.

## Tests

```bash
python3 attendance-count-report/test_rpc_attendance_counts.py
```

133 assertions, no live TouchPoint or database access — the real script runs end-to-end against a mocked `q`/`model` with fabricated (non-PII) fixtures, and the printed HTML is asserted. Covers the four picker stages and their stale-id fallbacks, the counts arithmetic (per-cell, per-row, per-column, grand total, and that Members + Leaders + Other reconciles to Total), the three cell states, the `CountWho` filter, sorting, `HideEmpty`, the back link's option round-trip, CSV shape and quoting, the CSS-isolation invariants, row-level security, and the `DB_REFERENCE.md` schema traps (`DivOrg` via `EXISTS`, canceled/did-not-meet exclusion, `CAST(... AS DATE)`, `AttendanceFlag`/`NoShow`, same-day meeting summing).

Hostile input gets its own section: the query string is the only untrusted path into this script, and both date inputs are string-interpolated into SQL. `valid_date()` is the only thing standing between them and the database — strict `^\d{4}-\d{2}-\d{2}$` plus a real `strptime` (so `2026-02-31` is rejected too), falling back to the default rather than erroring. The suite asserts a `'; DROP TABLE` payload never reaches the generated SQL. Every other query input is an int or a value drawn from a fixed option list.

## Deploy

- **Type:** Python Script
- **TouchPoint path:** `Admin > Advanced > Special Content > Python Scripts > +New`
- **Script name:** `RPC_AttendanceCounts`
- **Access via:** `/PyScript/RPC_AttendanceCounts` — *not* the Special Content admin "run" preview, or the picker's buttons and query-string reruns won't work and printing picks up TouchPoint's admin chrome.
- **Schedule:** none. This is an on-demand report; it sends no email and writes nothing.

## Status

**Not yet live-validated against RPC's TouchPoint.** Validated locally only: `python3 -m py_compile`, plus the 133-assertion suite above against mocked data.

What that cannot prove, and what to check on the first live run:

1. **The deep links resolve.** `/Meeting/{MeetingId}` and `#tab-Meetings-tab` come from community tools, not TouchPoint's own docs. Click one count and one superscripted count on the first run. If `/Meeting/` is wrong, the grid still reads correctly — only the click-through breaks — and the fix is one constant (`MEETING_URL`).
2. **The Members/Leaders split reads sensibly** on a division with known leaders. `Attend.MemberTypeId` itself is live-confirmed (`DB_REFERENCE.md`'s `Attend` section, both the declared `MemberTypeId -> lookup.MemberType.Id` join and a real per-meeting breakdown), so this is about whether RPC's *values* bucket the way `MEMBER_TYPE_BUCKETS` assumes — not about whether the column exists.
3. **Spot-check one involvement's total** against TouchPoint's own attendance screen for the same date range, and against `sm-attendance-pyreport.py` for an SM involvement — expect the `NumPresent` gap described above, and confirm the direction of any difference before treating it as a bug.
4. **A red `0` is real.** Pick one and click it — the linked meeting page should exist and show no marked attendance.
5. **Performance on a wide selection.** The AD Classes/Meetings/Groups division carries 156 active involvements (confirmed live 2026-09-07). Select-all across it over 13 weeks is the worst realistic case; the counts query is a single `GROUP BY` rather than one row per attendance record, but it hasn't been timed live.

Add anything confirmed to `DB_REFERENCE.md` — that file, not this README, is the durable source of truth for RPC schema facts.
