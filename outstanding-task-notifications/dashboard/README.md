# SM Staff Task Dashboard

Standalone TouchPoint dashboard for RockPointe Student Ministry outstanding tasks.

## What it does

`SM_StaffTaskDashboard.py` renders an in-TouchPoint dashboard from `TaskNote` data showing:

- Outstanding tasks by owner
- Outstanding tasks by assignee
- Task age
- Due-date status
- Task detail with links back to the about-person TouchPoint profile

It filters to the confirmed Student Ministry staff/volunteer PeopleId list currently documented in `../../DB_REFERENCE.md`.

## Why this is not a Linear dashboard

The dashboard needs to live in TouchPoint because `TaskNote` is TouchPoint-native data and Brian will copy/paste the Special Content Python script into TouchPoint for live testing.

Linear is still useful as a project/backlog tracker for enhancement requests and bugs discovered while testing this dashboard. It should not be the runtime display unless we later build a deliberate TouchPoint-to-Linear sync, and that would be a separate project with its own failure modes. Dude, making a sync layer before the basic dashboard works would be backwards.

## TouchPoint Deployment

- Type: Python Script
- TouchPoint path: `Admin > Advanced > Special Content > Python Scripts > +New`
- Script name: `SM_StaffTaskDashboard`
- Source file: `outstanding-task-notifications/dashboard/SM_StaffTaskDashboard.py`
- Source data: `TaskNote`
- Dependencies: TouchPoint runtime globals `model`, `q`, and `Data`

## Test steps

1. In TouchPoint, create or update Python Script `SM_StaffTaskDashboard` with the contents of `SM_StaffTaskDashboard.py`.
2. Run the script from TouchPoint Special Content.
3. Confirm the top metrics render.
4. Confirm the detail view shows columns for Owner, Assignee, About, Status, Age, Due, and Task.
5. Test filters:
   - Owner = one SM staff member
   - Assignee = one SM staff member
   - Age = 7+ days
   - Due date = Overdue
   - View = Summary by owner
   - View = Summary by assignee
6. Spot-check a few rows against the native TouchPoint task list.

## Expected caveats

- Local validation can only check Python syntax. The query and rendered dashboard still need live TouchPoint execution.
- The SM staff list is hardcoded. Update `SM_STAFF` and `DB_REFERENCE.md` when staff changes.
- The dashboard intentionally excludes `New Person Data Entry%` tasks to match the existing SM reminder behavior.
- Task filtering uses `(IsNote = 0 OR IsNote IS NULL)` because live tasks store `NULL` in practice.

## Linear backlog recommendation

If Brian wants to use Linear for this project, create a small RockPointe/TouchPoint backlog after the first live test pass, with issues for:

- TouchPoint runtime errors
- Query/schema mismatches
- Filter/UI enhancements
- Staff-list updates
- Deployment polish

Do not sync `TaskNote` records into Linear unless we intentionally decide to build a separate integration.
