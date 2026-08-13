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

The script calculates the most recently completed Sunday, even during a manual preview on another day. It separately queries the previous Sunday for headline and campus comparisons. It uses active Student Ministry Sunday organizations and `Meetings.NumPresent`; direct `DivOrg` joins are avoided at report grain.

TouchPoint may stringify a SQL `DATE` as `M/D/YYYY 12:00:00 AM`. The email script normalizes that format to ISO `YYYY-MM-DD` before comparing and aggregating rows. Do not replace `normalize_date()` with a simple whitespace split; that caused the first live preview to discard valid attendance while reporting every group as missing.

## Safe rollout

Completed live preview validation on 2026-08-13:

- report date correctly resolved to Sunday, August 9, 2026;
- totals rendered as 235 students, 46 volunteers, 281 total;
- all 12 confirmed TouchPoint PeopleIds were loaded;
- mobile-first layout rendered correctly;
- all Mentor Program variants and `SM: PS Health and Safety` are intentionally excluded from totals and missing-attendance warnings.

Production artifact has `TEST_MODE = False` after Brian's approval. Brian deployed it and added the Monday `MorningBatch` call on 2026-08-13. A manual run sends immediately, while `MorningBatch` sends only on Monday.

Live configuration:

```python
if model.DayOfWeek == 1:  # Monday
    model.CallScript("SM_AttendanceDashboardEmail")
```

Do not manually run the production script unless an immediate 12-recipient send is intended. Verify the first scheduled Monday delivery in Outlook desktop and on a phone.

Historical preview checklist:

1. Deploy with `TEST_MODE = True`.
2. Run the script manually and confirm:
   - the subject references the intended Sunday;
   - all 12 requested email addresses resolve to unique PeopleIds;
   - student, volunteer, campus, and grade totals look correct;
   - missing attendance warnings identify genuinely unreported groups rather than inactive or Wednesday organizations;
   - the interactive report button opens the same Sunday with Sunday-only parameters.
3. Temporarily reduce `RECIPIENT_PEOPLE_IDS` to one approved test recipient, set `TEST_MODE = False`, and run one controlled send.
4. Verify the email in Outlook desktop and on a phone. Check stacking, font size, table width, subject, preview text, and button behavior.
5. Restore all 12 requested PeopleIds and run one intentional full-audience send.
6. Only after that succeeds, add to `MorningBatch`:

```python
if model.DayOfWeek == 1:  # Monday
    model.CallScript("SM_AttendanceDashboardEmail")
```

## Rollback

Remove or comment out the `MorningBatch` call. This report is read-only; it does not modify attendance or people records.
