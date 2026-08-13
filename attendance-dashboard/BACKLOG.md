# Attendance Dashboard Backlog

Active work and request status for the Student Ministry attendance dashboard.

## In Progress

### Weekly SM attendance dashboard email

**Status:** In progress — waiting on requestor reply  
**Requestor:** Libbie Risberg / Student Ministry  
**Requested:** 2026-08-12  
**Default send day:** Monday  
**Default date range:** Fall 2026 semester start (`2026-08-16`) through current date  
**Candidate recipient alias:** `students@rpcstaff.org`

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

#### Recommended implementation

- Create a Python email wrapper script, tentatively `SM_AttendanceDashboardEmail`.
- Generate or call the existing attendance dashboard report with `StartDate=2026-08-16` and `EndDate=today`.
- Send Monday via `MorningBatch`:

```python
if model.DayOfWeek == 1:
    model.CallScript("SM_AttendanceDashboardEmail")
```

- Use a saved TouchPoint recipient query/tag/PeopleId list as the primary recipient list.
- Optionally test `students@rpcstaff.org` in `cclist` once the primary list is known.

#### Waiting on Libbie

Need reply with:

- desired recipient people/email addresses if not relying solely on the alias;
- confirmation that Monday is acceptable;
- optional confirmation that Fall 2026 should start on `2026-08-16`.

#### Linear note

Tracked in Linear as PRA-5: https://linear.app/praxen/issue/PRA-5/weekly-sm-attendance-dashboard-email

Caveat: this is RockPointe volunteer / TouchPoint work, but the only Linear team currently visible to this token is `PRA` / Praxen. If a RockPointe Linear team/project/label is created later, move this issue there.
