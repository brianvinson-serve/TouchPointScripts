# Attendance Dashboard Backlog

Active work and request status for the Student Ministry attendance dashboard.

## In Progress

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
