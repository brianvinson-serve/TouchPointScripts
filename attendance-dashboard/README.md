# Student Ministry Attendance Reporting

## Files

- `sm-attendance-pyreport.py` — interactive TouchPoint attendance dashboard. Supports `StartDate`, `EndDate`, `IncludeSunday`, `IncludeWednesday`, and `CampusFilter` parameters.
- `SM_AttendanceDashboardEmail.py` — dual-mode, dual-day report (see below): a live check-in view on Sunday/Wednesday, and a recap email on Monday/Thursday.
- `sm-attendance-flat.sql` — flat attendance export/query source.
- `sm-dashboard.html` — local CSV-driven dashboard helper.
- `sm-attendance-3yr-gender-history.sql` — 3-year Sunday attendance-by-gender pull for Central/Parker Square, gender from `People.GenderId` rather than org-name parsing (so it survives involvement/naming changes across years). Ad hoc research query, not a deployed report.
- `sm-flash-attendance-report.py` — untracked draft found in the repo 2026-08-30, broken and wrong-ministry (queries non-existent tables, CM subject/recipients despite the SM filename). Needs triage before any fix; not related to the script below. See `BACKLOG.md`.
- `BACKLOG.md` — request and rollout status.

## `SM_AttendanceDashboardEmail.py` — one script, two attendance types, two purposes per type

The script determines its own **mode** (which attendance to report) and **action** (view vs. send) from the day of the week, using Python's own clock (`datetime.now().date().weekday()`), not `model.DayOfWeek` — see the file's header comment for why.

| Day | Mode | Action | What it shows |
|-----|------|--------|----------------|
| Sunday | Sunday | **View** (never sends) | Today's in-progress Sunday attendance — students + the two Sunday Morning Volunteers orgs. Open this URL on a phone during check-in. |
| Monday | Sunday | **Send** | Recap email for the Sunday that just completed, vs. the Sunday before it. |
| Wednesday | D-Groups | **View** (never sends) | Today's in-progress D-Group attendance — D-Group classes + D-Group leaders. Same phone-during-check-in use case as Sunday. |
| Thursday | D-Groups | **Send** | Recap email for the D-Group night that just completed, vs. the D-Group night before it. |
| Any other day (manual run) | Sunday | View | Safe fallback — most recently completed Sunday, never sends. |

**Sending is only reachable on Monday or Thursday, full stop.** `model.CallScript` cannot pass parameters to the called script (confirmed dead end during the CM email rebuild — see `BACKLOG.md`), so the Monday/Thursday `MorningBatch` calls can't tell this script "send" vs. "view" via an argument. Instead the day-of-week gate lives inside the script itself: Sunday and Wednesday structurally cannot reach `model.Email(...)`, regardless of URL params. That makes it safe to bookmark and open on a phone at any time during check-in without risk of triggering a real send.

### Optional URL parameters (manual testing only — MorningBatch passes none)

- `Mode=Sunday` or `Mode=Wednesday` — force which report to build, regardless of today's actual weekday.
- `View=1` — on a Monday/Thursday run, render the email body in the browser instead of sending it (same pattern as `CM_AttendanceDashboardEmail.py`'s `Preview=1`).
- `Date=YYYY-MM-DD` — force the report date instead of auto-detecting it. Comparison date is always 7 days earlier.

None of these can force a send outside Monday/Thursday.

### Sunday mode

- Students: active `SM: CC */SM: PS *` Type 201 orgs in Division 11 (Sunday).
- Leaders: exactly `SM: CC Sunday Morning Volunteers 2026-2027` and `SM: PS Sunday Morning Volunteers 2026-2027` (Type 207), matched by explicit name, not "any Type-207 org in the division" — that avoids accidentally pulling in a global roster involvement like `SM: All Volunteers 2026-2027`, which isn't a per-Sunday meeting org.
- Grouped by Campus (Central / Parker Square), then Middle School / High School, then grade + gender.

### Wednesday (D-Group) mode

- Students: active Type 201 **and** Type 205 orgs in Division 42 (SM Wednesdays), **regardless of name** — D-Group orgs don't all follow the `SM: CC */SM: PS *` naming convention (e.g. `SM: Identity: Daughters of the King`, `SM: Man Up`). Confirmed live 2026-08-27 in `sm-attendance-pyreport.py` after a name-prefix filter silently dropped two D-Group orgs; this script carries the same fix in from day one instead of reintroducing that bug.
- Leaders: exactly `SM: PS D Groups Leaders 2026-2027` (OrgId 4060, Type 207).
- Not grouped by campus (D-Group org names don't reliably carry campus). Grouped by Middle School / High School / Other, where "Other" is any D-Group org whose name doesn't parse to a grade (most small-group/topic D-Groups) — those are listed by their own (shortened) org name rather than collapsed into a bucket.
- `SM: SLT 26-27` (student leadership team roster, not a meeting) is excluded, same as `SM: PS Health and Safety` (excluded in both modes — it sits in both Division 11 and 42 and isn't a real attendance group) and `SM: CC Paint War response form F26` (a one-time summer event signup, not recurring attendance — confirmed 2026-08-30).
- `SM: CC Summer Groups 26` and `SM: CC Summer Groups Leaders 26` are also excluded, Wednesday-only (confirmed 2026-08-30) — summer programming, not part of the regular D-Group school-year lineup.

### 2026-08-30 fixes made during this rework

- **Name typo, confirmed by DB_REFERENCE.md:** the prior single-purpose Sunday script's leader-org allowlist had `"SM: PS D Group Leaders 2026-2027"` (singular "Group"). The live-confirmed name is `"SM: PS D Groups Leaders 2026-2027"` (plural). Since the SQL matched by exact name equality, that line had been silently showing 0 every week. Moot for Sunday now (that org moved to Wednesday's report, per Brian's decision — D-Group leaders belong in the D-Group report, not the Sunday one), but the correct plural name is what's used in `WEDNESDAY_LEADER_ORG_NAMES` now.
- Grade/gender parsing moved from a T-SQL `CROSS APPLY` chain into Python (`parse_grade_gender`), so the same parser can handle both Sunday's `SM: CC 6th Guys`-style names and D-Group's mixed `SM: PS 10th Grade Apologetics F26-S27` / no-grade-at-all topic names in one place, without forcing D-Groups into Sunday's campus/gender shape.

### Not yet live-validated

No live TouchPoint SQL access in this session. Validated locally instead: `python3 -m py_compile`, plus a logic harness that mocks `model`/`q` and runs the script's actual code through 7 scenarios (Sunday view, Monday send, Wednesday view, Thursday send, Monday `View=1` preview, an off-day manual run, and a `Mode=`/`Date=` override) — mode/action/date routing, the send gate, and D-Group name parsing (including ungraded topic orgs and the off-hour grade case) all resolved correctly with synthetic rows. What that harness **cannot** validate: the actual SQL against RPC's live schema (table/column names, the Division 42 `EXISTS` fix actually returning the two previously-dropped D-Group orgs, real attendance counts). Before scheduling the Thursday `MorningBatch` call:

1. Run with `?Mode=Sunday` on a non-Sunday to confirm the Sunday recap still renders identically to the prior single-purpose script's known-good output.
2. Run with `?Mode=Wednesday` (or naturally on a Wednesday) and confirm against a live SQL spot-check that `SM: Identity: Daughters of the King` / `SM: Man Up`-style D-Group orgs actually appear, and that `SM: SLT 26-27` does not.
3. Confirm the plural `"SM: PS D Groups Leaders 2026-2027"` matches OrgId 4060 live and reports a nonzero leader count on an actual D-Group Wednesday.
4. Follow the same preview-then-controlled-recipient-then-full-audience rollout pattern used for the original RPC-3 rollout before trusting Thursday's send.

## Weekly email deployment

- **Type:** Python Script
- **TouchPoint path:** `Admin > Advanced > Special Content > Python Scripts > +New`
- **Script name:** `SM_AttendanceDashboardEmail`
- **Dependency:** interactive Python report `sm-attendance-pyreport` for the detail link
- **Sender:** `studentministry@rockpointechurch.org` / `RockPointe Student Ministry`
- **Queued by:** confirmed live sender PeopleId configured in the script
- **Recipients:** same 12 confirmed TouchPoint PeopleIds for both the Sunday and Thursday recap emails.

TouchPoint may stringify a SQL `DATE` as `M/D/YYYY 12:00:00 AM`. The script normalizes that format to ISO `YYYY-MM-DD` before comparing and aggregating rows. Do not replace `normalize_date()` with a simple whitespace split; that caused the first live preview (back when this was Sunday-only) to discard valid attendance while reporting every group as missing.

## Production behavior

Manual runs on Monday or Thursday send immediately to the full 12-recipient audience unless `View=1` is passed — use the Run button only when an intentional full-audience send is wanted, or add `View=1` to preview safely. Manual runs on Sunday or Wednesday (or any other day) never send, by construction.

## Production scheduling

Existing Monday call (deployed 2026-08-13, unaffected by this rework):

```python
if model.DayOfWeek == 1:  # Monday
    model.CallScript("SM_AttendanceDashboardEmail")
```

Add, once Thursday is live-validated per the checklist above:

```python
if model.DayOfWeek == 4:  # Thursday
    model.CallScript("SM_AttendanceDashboardEmail")
```

(`model.DayOfWeek`'s exact Thursday value is inferred from the existing confirmed "1 = Monday" — verify it live before relying on it; this is the `MorningBatch` wrapper's own gate, separate from the script's internal Python-clock-based mode logic described above.)

## Live check-in view

No scheduling needed — just open the script's URL directly (e.g. `/PyScript/SM_AttendanceDashboardEmail`) on a phone or browser on a Sunday or Wednesday. It renders the same report layout as the recap email, dated today, and is safe to reopen repeatedly as check-in numbers update. It never sends mail.

## Rollback

Remove or comment out the `MorningBatch` call(s). This report is read-only; it does not modify attendance or people records.
