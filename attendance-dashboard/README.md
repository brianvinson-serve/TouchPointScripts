# Student Ministry Attendance Reporting

## Files

- `sm-attendance-pyreport.py` — interactive TouchPoint attendance dashboard. Supports `StartDate`, `EndDate`, `IncludeSunday`, `IncludeWednesday`, and `CampusFilter` parameters.
- `SM_AttendanceDashboardEmail.py` — mobile-first Monday email for the immediately preceding Sunday. Includes prior-Sunday comparisons and missing-report warnings.
- `sm-attendance-flat.sql` — flat attendance export/query source.
- `sm-dashboard.html` — local CSV-driven dashboard helper.
- `BACKLOG.md` — request and rollout status.

## Weekly email deployment

- **Type:** Python Script
- **TouchPoint path:** `Admin > Advanced > Special Content > Python Scripts > +New`
- **Script name:** `SM_AttendanceDashboardEmail`
- **Dependency:** interactive Python report `sm-attendance-pyreport` for the detail link
- **Sender:** `studentministry@rockpointechurch.org` / `RockPointe Student Ministry`
- **Queued by:** confirmed live sender PeopleId configured in the script

The script calculates the most recently completed Sunday, even during a manual run on another day. It separately queries the previous Sunday for headline and campus comparisons. Student attendance uses active Student Ministry Sunday grade organizations. Leader attendance is the combined `Meetings.NumPresent` from exactly these three 2026-2027 organizations:

- `SM: CC Sunday Morning Volunteers 2026-2027`
- `SM: PS Sunday Morning Volunteers 2026-2027`
- `SM: PS D Group Leaders 2026-2027`

The email shows one combined leader headline plus detail for each source organization. Direct `DivOrg` joins are avoided at report grain.

TouchPoint may stringify a SQL `DATE` as `M/D/YYYY 12:00:00 AM`. The email script normalizes that format to ISO `YYYY-MM-DD` before comparing and aggregating rows. Do not replace `normalize_date()` with a simple whitespace split; that caused the first live preview to discard valid attendance while reporting every group as missing.

## Production behavior

The deployed artifact has no preview or single-recipient branch. Normal TPC execution queues the report to all 12 confirmed recipient PeopleIds. A manual run therefore sends immediately; use the Run button only when an intentional full-audience send is wanted.

## Production scheduling

Brian deployed the report and added the Monday `MorningBatch` call on 2026-08-13:

```python
if model.DayOfWeek == 1:  # Monday
    model.CallScript("SM_AttendanceDashboardEmail")
```

The Monday call sends to the full audience. On Monday, August 17, 2026, it will select the immediately preceding Sunday, August 16, 2026, and compare it with Sunday, August 9, 2026.

## Rollback

Remove or comment out the `MorningBatch` call. This report is read-only; it does not modify attendance or people records.
