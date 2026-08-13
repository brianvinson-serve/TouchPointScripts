# SM Student Contact Export

TouchPoint-hosted Python report for finding students who attended RockPointe Student Ministry activities and exporting contact information for the filtered students.

## Behavior

- Defaults to the last 90 days.
- Accepts a custom date range, capped at 366 days.
- Includes attendance in Student Ministry program `1109` across Sundays, Wednesdays/D-Groups, classes, events, mission trips, and other SM divisions.
- Requires `Attend.AttendanceFlag = 1` and excludes no-shows.
- Excludes attendance recorded against organization type `207` (active volunteer/leader tracking).
- Also excludes anyone enrolled in an annual involvement matching `SM: All Volunteers%`, even if that volunteer was accidentally checked into a student activity. Checking all annual rosters prevents an incomplete school-year rollover from leaking volunteers into the report. This is a person-level exclusion and does not rely on family position or grade.
- Treats positive attendance in non-volunteer SM involvements as the student boundary. RPC's actual family-position values have not been validated well enough to use them as a required gate; grade and gender remain filterable from the People record.
- Excludes archived and deceased People records.
- Produces one displayed/exported record per student after filters are applied.
- Uses current grade and gender from the student's People record.
- Uses `Families.HeadOfHouseholdId` and `HeadOfHouseholdSpouseId` as Parent/Guardian 1 and 2. TouchPoint does not store a household-level email address in the confirmed RPC schema.
- Leaves missing contact values blank rather than dropping the student.

## Filters

- Attendance date range
- Campus attended
- Activity category
- Specific activity/involvement
- Current grade
- Gender
- Minimum attendance count
- Student name or email search

Changing dates within the loaded range filters immediately. To query dates outside the loaded range, choose the dates and click **Load date range**. That button navigates to TouchPoint's direct Python execution route, `/PyScript/SM_StudentContactExport?StartDate=...&EndDate=...`, which starts a new server-side script run; browser JavaScript cannot call `q.QuerySql` after the initial page has rendered.

## CSV output

The CSV contains one row per filtered student:

- Student Name
- Student Email
- Current Grade
- Gender
- Attendance Count
- Most Recent Attendance
- Campuses Attended
- Activity Categories
- Activities Attended
- Household Name
- Parent/Guardian 1 Name and Email
- Parent/Guardian 2 Name and Email

Multiple campuses or activities are semicolon-separated within one cell.

## TouchPoint deployment

- **Type:** Python Script
- **TouchPoint path:** `Admin > Advanced > Special Content > Python Scripts > +New`
- **Script name:** `SM_StudentContactExport`
- **Source:** `SM_StudentContactExport.py`
- **Dependencies:** Maintained annual TouchPoint involvements matching `SM: All Volunteers%`, plus built-in `model`, `q.QuerySql`, and browser JavaScript.
- **Data access:** Read-only SQL.

The temporary SQL diagnostic panel and the `Server query complete` / `JS ACTIVE` execution sentinels used during live validation have been removed from the production report. The regression suite retains automated coverage of the JavaScript parse and boot path.

The report stays on the proven `/PyScript/SM_StudentContactExport` pattern used by the working attendance dashboard. TouchPoint's `/PyScriptForm` plus `model.Form`/`model.Script` is supported for AJAX form workflows, but is not required for this read-only report because custom date retrieval is a direct server-side `/PyScript` rerun.

## Live test checklist

1. Deploy the script as `SM_StudentContactExport`.
2. Run it without parameters. Verify the displayed range is the last 90 days and the filters/results render without any diagnostic or execution-sentinel panel.
3. Verify each dropdown contains an `All ...` option and the result table contains either students or the JavaScript-generated empty-state row.
4. Find Jack Larson (PeopleId 3156), whose known positive attendance is MeetingId 87790 on 2026-08-09 in OrgId 55, and compare the displayed count/date to TouchPoint.
5. Change both dates and click **Load date range**. Verify the page reruns at `/PyScript/SM_StudentContactExport?StartDate=...&EndDate=...`, displays the requested range, and renders the filters/results.
6. Filter to Wednesday/D-Groups, 9th grade, and female; confirm the resulting students against a known D-Group roster.
7. Filter to 9th grade and male with campus and activity set to All.
8. Export each result and verify the CSV has exactly one row per displayed student.
9. Spot-check student and parent/guardian emails against the People and family records.
10. Confirm a known volunteer-only attendee does not appear.
11. Confirm Brian Vinson does not appear even though mistaken student-activity check-ins exist for him.
12. Confirm Jason McMahon does not appear; his profile grade is not used as proof that he is a student.

## Local tests

From `student-contact-export/` run:

```bash
python3 test_sm_student_contact_export.py
```

The regression suite extracts the final browser JavaScript, runs `node --check`, and executes the boot path against a minimal DOM harness. This specifically prevents Python string escaping from emitting literal CR/LF characters inside JavaScript string literals—the root cause of the 2026-08-13 live page rendering static HTML while all JavaScript-owned fields remained blank.

## Rollback

Delete or disable the `SM_StudentContactExport` Python Script in TouchPoint. The script makes no database changes, so no data rollback is required.

## Privacy

This report exposes contact information for minors and household adults. Grant access only to appropriate Student Ministry leaders and avoid leaving exported CSVs in broadly shared locations.
