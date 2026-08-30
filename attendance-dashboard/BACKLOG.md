# Attendance Dashboard Backlog

Active work and request status for the Student Ministry attendance dashboard.

## In Progress

### CM attendance email: expand recipient list to 14 confirmed names, schedule MorningBatch

**Status:** `RECIPIENT_PEOPLE_IDS` updated and `PREVIEW_MODE` flipped to `False` 2026-08-30 on Brian's go-ahead. Only remaining step is Brian pasting the MorningBatch block live (requires TouchPoint access this session doesn't have).
**Requestor:** Brian, 2026-08-30

**Request:** Brian supplied 14 names for the CM attendance email audience and asked to confirm email addresses are on file, then add the send to `MorningBatch`. Two names (Jen Schmitz, Angela Cheshire) match the two people `CM_AttendanceDashboardEmail.py`'s header note said the list was gated on pending sign-off from — treated as that sign-off per Brian's message.

**Resolved via `CM_AttendanceEmailRecipientLookup.sql`:** 13 of 14 names matched `dbo.People` directly with `RESOLVED` status. "Jen Schmitz" alone came back `NOT_FOUND` (her TouchPoint `FirstName` is "Jennifer", not "Jen", and no matching `NickName`) — resolved by matching her supplied email to the same PeopleId (`6523`) already in the script from the original Angela/Jennifer-only list, so no new lookup was needed for her. Final IDs are in `CM_AttendanceDashboardEmail.py`'s `RECIPIENT_PEOPLE_IDS` with name comments.

**Flag for Brian:** Sara Comer's TouchPoint record (`PeopleId` 25605) has a personal Gmail address on file, not an `@rpcstaff.org` address like the rest of the list. Name match confirms it's the right person; whether that's the address she wants used wasn't re-verified.

**2026-08-30 addendum:** the "View interactive attendance report" button's `DASHBOARD_SCRIPT_NAME` was still pointed at the old repo-filename-style script names (`cm-attendance-pyreport`). Brian confirmed the live TouchPoint deployment is now `CM_AttendanceDashboard` (URL: `https://rockpointe.tpsdb.com/PyScript/CM_AttendanceDashboard`) — updated in `CM_AttendanceDashboardEmail.py`. Same fix applied to `SM_AttendanceDashboardEmail.py`'s `DASHBOARD_SCRIPT_NAME`, now `SMAttendanceDashboard` (`https://rockpointe.tpsdb.com/PyScript/SMAttendanceDashboard`). Both keep the existing `?StartDate=&EndDate=&CampusFilter=ALL` deep-link params -- only the script-name portion changed.

**Done:**
- `CM_AttendanceDashboardEmail.py`: `RECIPIENT_PEOPLE_IDS` replaced with all 14 confirmed PeopleIds; header note rewritten to reflect the 2026-08-30 confirmation instead of the old "controlled first-test" framing; `PREVIEW_MODE` flipped to `False` on Brian's explicit go-ahead (skipping the extra preview pass suggested earlier -- his call).
- `DB_REFERENCE.md`'s MorningBatch section: moved the `CM_AttendanceDashboardEmail` block from pending to approved, alongside the SM one.
- `python3 -m py_compile` passes.

**Next steps (Brian, needs live TouchPoint access):**
1. Save the updated `CM_AttendanceDashboardEmail.py` in TouchPoint (Admin > Advanced > Special Content > Python Scripts).
2. Paste the approved block into TouchPoint's live `MorningBatch` script:
   ```python
   if model.DayOfWeek == 1:  # Monday
       model.CallScript("CM_AttendanceDashboardEmail")
   ```
3. `FROM_EMAIL`'s stale `TODO confirm` comment removed -- the 2026-08-19 live test run (Angela's 2026-08-25 reply references it) already proved `childrensministry@rockpointechurch.org` delivers, so tomorrow's Monday send is a repeat of an address already confirmed live, not a first use.

### `SM_AttendanceDashboardEmail.py` reworked into a dual-mode, dual-day report + live check-in view

**Status:** Code + local logic-harness validation done 2026-08-30; needs live TouchPoint validation before scheduling Thursday
**Requestor:** Brian

**Request:** (1) confirm the Monday recap email already scopes to Sunday-only student/volunteer attendance, (2) reuse the same script for a Thursday recap of Wednesday-night D-Group attendance, and — raised mid-session — (3) also let Brian pull up the same report live on his phone during Sunday/Wednesday check-in, before the recap email would fire.

**Findings before implementation:**
- The one open bug near this script (`sm-attendance-flat.sql`/`sm-attendance-pyreport.py`'s same-day "phantom meeting" issue, below) does **not** affect this script — confirmed unaffected in the original 2026-08-13 implementation notes, since it already targets the most-recently-completed Sunday explicitly.
- Found a real, previously-uncaught bug while checking Brian's memory of "a bug we found for the email report": the prior script's `LEADER_ATTENDANCE_ORG_NAMES` had `"SM: PS D Group Leaders 2026-2027"` (singular "Group"), but `DB_REFERENCE.md`'s live-confirmed name (OrgId 4060) is `"SM: PS D Groups Leaders 2026-2027"` (plural). Exact-name-match SQL meant that leader line had silently shown 0 every week. Moot for Sunday now (see below), fixed with the correct plural name for the new Wednesday report.
- Confirmed via `git log -p` that `sm-attendance-pyreport.py` (commit `a62c89b`, 2026-08-27) already hit and fixed the exact bug this rework would otherwise reintroduce: D-Group orgs don't all follow the `SM: CC */SM: PS *` naming convention (e.g. `SM: Identity: Daughters of the King`, `SM: Man Up`), and a name-prefix filter had silently dropped two of them. The new Wednesday-mode query includes any active org in Division 42 regardless of name, same as the dashboard's fix.

**Decisions confirmed with Brian:**
- Remove `SM: PS D Groups Leaders 2026-2027` from the Sunday report's leader section entirely — it's a Wednesday-division org and gets its own line in the new Wednesday report instead.
- Same 12 recipient PeopleIds for both the Sunday and Wednesday/D-Group recap emails.
- D-Group detail rows grouped by grade only (Middle School / High School / Other), no gender split — D-Group org names are topic-based (e.g. "10th Grade Apologetics"), not Guys/Girls like Sunday.
- Sending is gated purely by day-of-week, hardcoded in the script (Monday/Thursday only) — not a URL flag — so the phone-check-in link is safe to open on Sunday/Wednesday with zero risk of triggering a send. `model.CallScript` cannot pass parameters to a called script (confirmed dead end, see the CM email rebuild's `model.CallScript` finding below), so this gate has to live inside the script itself rather than being passed in from the `MorningBatch` caller.
- The live Sunday/Wednesday view uses the same layout as the email, including the week-over-week delta, just dated today instead of last week.

**Implementation:** `SM_AttendanceDashboardEmail.py` now resolves its own `mode` (Sunday vs. Wednesday/D-Groups) and `action` (View vs. Send) from Python's own `datetime.now().date().weekday()` — not `model.DayOfWeek`, whose exact Sunday/Thursday numeric values are unconfirmed in this repo (only "1 = Monday" has been confirmed live). Sunday/Wednesday always render a live view of today's in-progress attendance and can never reach `model.Email(...)`; Monday/Thursday send the prior day's recap. Optional `Mode=`, `View=1`, and `Date=` URL params exist for manual testing only and cannot force a send outside Monday/Thursday. Grade/gender parsing moved from T-SQL `CROSS APPLY` into a shared Python parser so it can handle both Sunday's `Guys`/`Girls` suffix convention and D-Group's mixed graded/topic-only names. See `README.md` for the full mode table and the not-yet-live-validated checklist.

**Validation done without live TouchPoint access:** `python3 -m py_compile`, plus a logic harness (mocked `model`/`q`, `datetime` patched via `unittest.mock`) exercising 7 scenarios: Sunday view, Monday send, Wednesday view, Thursday send, Monday `View=1` preview, an off-day manual run, and a `Mode=`/`Date=` override — mode/action/date routing, the send gate, missing-meeting detection, and D-Group label rendering (including ungraded topic orgs like "Identity: Daughters of the King" and the "Middle School Off Hour" case) all resolved correctly against synthetic rows. This does **not** validate the actual SQL against RPC's live schema. Before scheduling the Thursday `MorningBatch` call, Brian should: confirm `Mode=Sunday` still renders identically to the known-good prior output; confirm `Mode=Wednesday` actually surfaces the non-CC/PS-prefixed D-Group orgs and excludes `SM: SLT 26-27`; confirm the plural `SM: PS D Groups Leaders 2026-2027` name matches OrgId 4060 live; and follow the same preview-then-controlled-recipient-then-full-audience rollout used for the original Sunday email before trusting a live Thursday send.

### SM dashboard: same-day "phantom" meeting silently dilutes every average

**Status:** Found 2026-08-30, fix pending — Brian plans to resolve later today
**Requestor:** Brian (found during a routine dashboard review)

**Finding:** A CSV export pulled at 1:30am on Sunday 2026-08-30 (`sm-attendance-2026-08-30.csv`), before any check-in had happened, contained one stray row: `SM: CC 6th Guys`, `2026-08-30`, Attendance `0`, Guests `0`. No other SM Sunday group had a row for that date, which is correct — but that one row was enough to add 2026-08-30 into `sm-dashboard.html`'s shared date axis (`allDates()`), and every group's average divides by that shared date count. Verified impact against the file: the "Sunday avg" stat read 210 instead of the true 245 (6 completed Sundays), and every detail/campus average was understated ~14% (dividing by n=7 instead of n=6). Not cosmetic — reads as a real attendance drop that didn't happen.

**Root cause:** `sm-attendance-flat.sql` (and the identical pattern in `sm-attendance-pyreport.py`) joins `Meetings` with only a date-truncated range filter (`CAST(m.MeetingDate AS DATE) BETWEEN @StartDate AND @EndDate`) and `ISNULL(m.NumPresent, 0)`, with no guard excluding a meeting that hasn't happened yet or is flagged `DidNotMeet`/`Canceled`. TouchPoint creates the `Meetings` row from `OrgSchedule` ahead of the actual service time, so a same-day row can exist with `NumPresent` defaulting to 0 hours before check-in starts. `DB_REFERENCE.md` already documents excluding `Canceled`/`DidNotMeet` meetings for D-Group weekly snapshots — that exclusion was never carried into this flat query or the interactive dashboard.

**Not affected:** `SM_AttendanceDashboardEmail.py` — it already targets the most recently completed Sunday explicitly, never today.

**Proposed fix:** in `sm-attendance-flat.sql` and `sm-attendance-pyreport.py`, exclude meetings that haven't occurred yet and any `DidNotMeet`/`Canceled` meetings (e.g. `m.MeetingDate <= GETDATE() AND` a not-yet-confirmed `DidNotMeet`/cancel-flag check — confirm the exact column against `DB_REFERENCE.md`/live schema before wiring in).

### `sm-flash-attendance-report.py`: broken, wrong-ministry draft sitting untracked

**Status:** Found 2026-08-30, untracked in the repo — needs triage before it's committed or run
**Requestor:** Brian (found during a routine dashboard review)

An untracked file, `attendance-dashboard/sm-flash-attendance-report.py`, is sitting in the repo (not committed, present at session start — possibly Kenny/Hermes WIP, unconfirmed). It appears broken and mis-scoped:

- Invalid T-SQL: `JOIN OrganizationMember om ON ... om.OrganizationId = o.Id` references alias `o` before the `JOIN Organization o` line that defines it — will throw a binding error if run.
- Table/column names don't match RPC's confirmed schema per `DB_REFERENCE.md` (`Attendance`/`Organization`/`Campus` instead of the confirmed `Attend`/`Organizations`/`lookup.Campus`).
- Despite the `sm-` filename, the email subject and body both say "Children's Ministry Attendance Report," and the recipient list includes Angela Cheshire (the CM contact from the CM email rebuild item above), not SM's confirmed 12 recipients from `DB_REFERENCE.md`.

Needs confirmation of origin/intent before any fix — do not deploy as-is.

### CM email rebuild: mirrored dashboard fixes + 6-week average

**Status:** Waiting on client — live TouchPoint test run came back clean 2026-08-19, sent on to the RPC team for feedback
**Requestor:** Brian (on Angela's behalf — Angela likes the full interactive dashboard but it isn't email-safe)

#### 2026-08-26 update: Angela's reply — PS 8:30 volunteer org swap, range presets, confirmed report shape

Angela Cheshire replied 2026-08-25 (cc Jennifer Schmitz, Ashley, Marlene) after reviewing the 2026-08-23 live dashboard and the email report still in testing:

1. **PS 8:30 volunteers moved to a scheduler org.** The two orgs previously listed for PS 8:30 volunteers — `4020` (CM: PS 8:30 Volunteers Nursery/Kinder 2026-2027) and `4021` (CM: PS 8:30 Volunteers Elementary 2026-2027) — are no longer where people check in. Angela said the real org is `3508` (CM: PS 8:30 Birth-5th Volunteers Scheduler) and that she'll make 4020/4021 inactive. Implemented in both `cm-attendance-pyreport.py` and `CM_AttendanceDashboardEmail.py`: org 3508 added as a second explicit override (`@PS830VolunteersSchedulerOrgId`, same bypass-conditions-4/5 shape as the existing `@CentralWelcomeTeamOrgId` = 3587 override), and 4020/4021 added to the excluded-org-IDs list alongside 4026/4027. Because 3508 covers "Birth-5th" in one org (both former buckets combined), `classify_volunteer_bucket()` in both scripts now takes an `org_id` and special-cases 3508 into the "Nursery/Kinder" bucket by ID rather than by name-keyword match, since its name doesn't contain "nursery," "kinder," or "elementary."
   - **Not independently confirmed live** — no live TouchPoint SQL access in this session. Org 3508's `OrganizationTypeId` (should be 207), `OrganizationStatusId` (should be 30/active), and DivOrg/OrgSchedule linkage (assumed to need the override, by analogy to 3587's "Scheduler" org pattern) are all unverified. Brian should confirm via a live run or query before treating this as production-correct, and update this note / `DB_REFERENCE.md` once confirmed.
   - Angela did not say whether 4020/4021 should be deactivated before or after this deploys. Excluding them outright now means no double-counting risk regardless of timing.
2. **General preschool volunteer involvements will change again "in the next couple of weeks."** Angela asked whether she should just email the new involvement when that happens. Answered: yes — no code change needed now, this is a placeholder for a future request in the same shape as the 3508 swap above.
3. **Dashboard range presets: 4wk/8wk/13wk → 4wk/6wk/8wk.** Done in `cm-attendance-pyreport.py` — the three preset buttons now call `setPreset(4|6|8, this)`. No other logic change needed: the average column header already reads `{n} Avg` off however many weeks are in the selected range, so selecting "6 wk" now shows a live 6-week average automatically.
4. **Supply-ladies' ask (most recent Sunday, past 6 weeks, 6-wk average) and Angela's ask for the email (past Sunday vs. week before, plus 6-wk avg) are already satisfied by existing work**, not new asks: the dashboard's per-row/per-bucket average already reflects the active range (see #3), and `CM_AttendanceDashboardEmail.py`'s existing `AVERAGE_WINDOW_WEEKS = 6` and week-over-week delta (shipped in the 2026-08-19 rebuild) already show exactly "last Sunday vs. 6-wk avg." No code change made for this item — confirm it reads correctly once 3508 has real data in the next live test.

Still gated on the existing recipient-list sign-off note above (`RECIPIENT_PEOPLE_IDS` remains Angela/Jennifer/Brian only) — this round of fixes doesn't change that, and Jennifer's confirmation is still needed before scheduling `MorningBatch`.

#### 2026-08-26 fix: Special Needs rows sorted alphabetically instead of by service time

Brian flagged (from the 2026-08-23 email preview) that Special Needs rows showed 10:45 AM before 9:00 AM (Central) and 11:15 before 9:45 (Parker Square). Root cause: `_AGE_ORDER` only has Preschool/Elementary tables — there's no age progression to rank within Special Needs — so `age_rank()` returns `None` for that bucket and the sort fell back to alphabetical on the org name, where `"1"` sorts before `"9"` as text.

Fixed in `CM_AttendanceDashboardEmail.py`'s `detail_rows()`: when `age_rank()` is `None`, the sort key now falls back to `volunteer_time_minutes()` (the same H:MM regex parser already used for volunteer sorting) instead of alphabetical. Ranked rows are unaffected (still sorted 0..N ahead of any unranked rows).

The same root cause exists in the interactive dashboard (`cm-attendance-pyreport.py`'s `sortByAgeRank()` JS, confirmed from the 2026-08-23 screenshot Brian originally sent), so it was fixed there too by the same shape: fall back to `volunteerTimeMinutes()` instead of alphabetical when `AgeRank` is null on either side. Verified both the Python (`detail_rows`) and JS (`sortByAgeRank`) fallback logic in isolation with sample Central/Parker Square Special Needs org name pairs — both now sort 9:00 before 10:45 and 9:45 before 11:15.
**Requested:** 2026-08-19

#### `model.CallScript` finding

Investigated whether `CM_AttendanceDashboardEmail.py` could source its data by calling `cm-attendance-pyreport` (the interactive dashboard) via `model.CallScript(...)` and parsing the embedded `var rawData = [...]` JSON out of the returned HTML, instead of maintaining a second copy of the query/classification logic. A live spike test came back with 3 blank/empty rows — `model.CallScript` did not return the called script's rendered output in a usable form here. **Conclusion: `model.CallScript` is fire-and-forget in this TouchPoint instance** (consistent with every other use in this repo — `MorningBatch`, `SM_AttendanceDashboardEmail` scheduling — none of which use a return value or pass parameters). Don't retry this approach without new evidence it works differently.

#### Implementation

Given the above, `CM_AttendanceDashboardEmail.py` keeps its own copy of the query/classification logic (same pattern as `SM_AttendanceDashboardEmail.py`), now re-synced with the corrected `cm-attendance-pyreport.py`:

- Kindergarten classified as Elementary, not Preschool.
- Kids detail rows (Preschool/Elementary) sorted in age order via the same `_AGE_ORDER` tables as the dashboard, instead of alphabetically.
- Central Welcome Team uses org `3587` (bypasses the reporting-division/Sunday-schedule checks via an explicit override) instead of the newer, currently-unused `4026`/`4027`, which are excluded outright.
- The query window widened from 2 exact dates to a 6-Sunday `BETWEEN` range, and every row (detail lines, bucket/campus totals, the 3 summary cards) now shows a 6-week average next to the current Sunday's count. The average is computed only over Sundays that actually have a logged meeting for that scope (skips missing weeks rather than diluting new orgs).

#### 2026-08-19 update: mirrored naming cleanup + volunteer sort, added Preview mode

After the interactive dashboard got a naming-convention cleanup (`prettyLabel`) and a corrected volunteer sort (grouped by type -- Nursery/Kinder, Elementary, Special Needs, Welcome Team -- then by service time, instead of plain alphabetical), the same two fixes were ported into `CM_AttendanceDashboardEmail.py` (`pretty_label()`, `classify_volunteer_bucket()`, `volunteer_time_minutes()` -- same regexes/logic, Python instead of JS).

Also added a `Preview` URL parameter for testing: `/PyScript/CM_AttendanceDashboardEmail?Preview=1` renders the full report body in the browser and prints a "PREVIEW MODE -- no email sent" banner instead of calling `model.Email(...)`. Any falsy/omitted value (`0`, `false`, blank) sends for real, unchanged. Verified both branches with a synthetic `model.Email` stub that raises if called while `Preview=1` -- confirmed it's never invoked in preview mode, and is invoked normally otherwise.

#### Central Preschool/Nursery volunteers: confirmed no data yet, not a bug

2026-08-19: Central's Volunteers section shows Elementary, Special Needs, and Welcome Team but no Preschool/Nursery bucket, even over the full "All" date range. Brian confirmed live via SQL: orgs `4018` (CM: CC 9:00 Volunteers Nursery/Preschool 2026-2027) and `4019` (CM: CC 10:45 Volunteers Nursery/Preschool 2026-2027) both exist, `OrganizationStatusId = 30` (active), and each has 1 `OrgSchedule` row — but `TotalMeetingsEver = 0` for both. Nobody has taken attendance on them yet. The dashboard's `INNER JOIN` to `Meetings` correctly hides orgs with zero attendance history regardless of date range, so this is expected behavior, not a filter bug. Will resolve itself the first Sunday CM records attendance on these two orgs — no code change needed.

Any future fix to the dashboard's filter/classification/ordering/overrides must be re-applied here by hand — this is the accepted tradeoff of the `model.CallScript` finding above.

### Weekly SM attendance dashboard email

**Status:** Wrapped — deployed live and scheduled in MorningBatch on 2026-08-13
**Requestor:** Libbie Risberg / Student Ministry  
**Requested:** 2026-08-12  
**Confirmed send day:** Monday morning
**Confirmed date range:** immediately preceding Sunday

#### Request

Libbie asked whether the Student Ministry attendance dashboard at `attendance-dashboard/sm-attendance-pyreport.py` can be sent as a weekly email to `students@rpcstaff.org`, or whether she needs to export and send it manually each week.

Brian replied asking:

- whether the default range should be beginning of current semester or 90 days;
- whether TouchPoint can send to the `students@rpcstaff.org` alias;
- for the actual recipient email addresses if the alias is not viable;
- whether Monday is the desired send day.

#### Research findings

TouchPoint can automate this through Python Special Content and `MorningBatch`.

Key findings:

- `MorningBatch` is the right recurring mechanism for weekly generated reports. It runs every morning; guard weekly execution with `model.DayOfWeek`.
- TouchPoint Python email functions (`model.Email`, `model.EmailContent`, `model.EmailReport`) take a recipient `query` parameter. That query can be a saved search name, a single PeopleId, or TouchPoint query code such as `peopleids='1,2'`.
- The Python email API supports an optional `cclist` parameter as a comma-separated list of raw email addresses.
- Therefore, the safest primary recipient list is actual TouchPoint people via a saved query/tag/PeopleIds. The `students@rpcstaff.org` alias may be usable as CC, but must be tested because delivery also depends on the Google Workspace group accepting TouchPoint-sent mail.
- TouchPoint's normal UI can send to single email addresses, but that does not make raw aliases the best primary recipient model for recurring Python automation.

#### Confirmed response from Libbie

Libbie confirmed that the email should cover only the previous Sunday, that Monday morning is the correct schedule, and that the requested audience contains 12 staff recipients. The confirmed production PeopleIds are documented in `DB_REFERENCE.md`; staff email addresses remain only in local gitignored evidence because this repository is public.

#### Implementation

- Deploy `SM_AttendanceDashboardEmail.py` as Python Special Content `SM_AttendanceDashboardEmail`.
- The report calculates the most recently completed Sunday and the Sunday before it.
- It renders email-safe, mobile-first HTML rather than embedding the JavaScript dashboard.
- It includes headline student/volunteer totals, week-over-week comparison, campus summaries, grade/gender detail, volunteer detail, and a missing-attendance warning.
- It links to the full dashboard parameterized to the report Sunday.
- It sends to 12 confirmed TouchPoint PeopleIds from the 2026-08-13 live staff-directory export.
- Weekly totals and missing-attendance warnings intentionally exclude all `Mentor Program` organization variants and `SM: PS Health and Safety`.
- Send Monday via `MorningBatch`:

```python
if model.DayOfWeek == 1:
    model.CallScript("SM_AttendanceDashboardEmail")
```

- Follow the RPC-3 rollout pattern: preview first, then one controlled live recipient, then production audience, then scheduling.

#### Completed live validation

- All 12 requested recipients were resolved to confirmed TouchPoint PeopleIds.
- The previous-Sunday report rendered 235 students, 46 volunteers, and 281 total for 2026-08-09.
- Mobile-first rendering and the parameterized report link were validated in TouchPoint preview.
- All Mentor Program variants and `SM: PS Health and Safety` were removed from totals and missing-attendance warnings.
- `TEST_MODE = False` was deployed and the Monday `MorningBatch` call was added by Brian on 2026-08-13.

#### 2026-08-13 preview defect and root cause

The first live preview displayed zero attendance for 2026-08-09 even though a confirmed student check-in existed with a populated `NumPresent` value.

The meeting passed every original SQL filter: active status 30, type 201, `SM: CC` name, Program 1109, and Division 11. The involvement did not change. The defect was Python date normalization: TouchPoint returned the SQL date as `8/9/2026 12:00:00 AM`, but the email aggregator compared that unnormalized value with ISO string `2026-08-09`. The email script now normalizes both ISO and M/D/YYYY TouchPoint date strings before aggregation.

#### Linear note

Tracked under the RPC DEV team in the Touchpoint Backlog project as RPC-1: https://linear.app/praxen/issue/RPC-1/weekly-sm-attendance-dashboard-email
