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
4. Confirm the detail view shows columns for Owner, Assignee, About, Status, Age, Due, Task, and TaskNoteId.
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
- Task filtering uses `(IsNote = 0 OR IsNote IS NULL)` defensively, but the 2026-08-13 full RPC profile found current tasks at `IsNote = 0` and no `NULL` `IsNote` rows.

## Linear backlog recommendation

If Brian wants to use Linear for this project, create a small RockPointe/TouchPoint backlog after the first live test pass, with issues for:

- TouchPoint runtime errors
- Query/schema mismatches
- Filter/UI enhancements
- Staff-list updates
- Deployment polish

Do not sync `TaskNote` records into Linear unless we intentionally decide to build a separate integration.

---

# RPC Staff Task Dashboard

Church-wide sibling of the dashboard above. `RPC_StaffTaskDashboard.py` covers all ministries, not just SM.

## What it does

Two views in one screen, toggled by URL param (`?view=rollup` default, `?view=detail`):

- **Leadership Rollup** — department × age-bucket matrix, headline KPIs (open/overdue/"Forgotten" 90+ day count/staff with open tasks/unassigned-department count), a task-type breakdown, and a staff workload leaderboard.
- **Task Detail** — filterable, worst-first row list (overdue first, then oldest), with keyword chips and links out to each person's TouchPoint profile.

Filters: department, task type (Ministry / Care & Assimilation / System / Other / No Keyword), age bucket (New / Getting Stale / Needs a Nudge / Falling Behind / Backlogged / Forgotten — bucketed from `CreatedDate`), due date (Overdue / Today / This Week / Later / No Due Date), and staff member.

Read-only by design — no complete/reassign actions in this version. Every row links to the native TouchPoint person profile for follow-up instead.

## Where department and task-type come from

- **Department**: a hardcoded `PeopleId -> (Name, Department)` roster in the script, built from the 64 people holding an open task church-wide (2026-08-25) cross-referenced against the live staff directory at `rockpointechurch.org/staff/department/all-staff` (2026-08-26). No native TouchPoint field ties a task or a person to a department — `TaskNote.OrgId` is 0% populated at RPC, and no existing `MemberTags` usage is department-shaped (see `DB_REFERENCE.md`). 15 of the 64 aren't on the public directory and are bucketed `Unassigned`; update the `ROSTER` dict as that gets resolved or as staff change.
- **Task type**: RPC's native `Keyword`/`TaskNoteKeyword` tables, already in use (80% adoption on open tasks as of 2026-08-25). The 47 active keywords mix three different things — ministry tags, care/assimilation workflow tags, and automated system/HR tags — untangled into the `KEYWORD_GROUPS` dict. See `DB_REFERENCE.md`'s "TaskNote Keywords" section for the full reasoning and the complete code list.

## TouchPoint Deployment

- Type: Python Script
- TouchPoint path: `Admin > Advanced > Special Content > Python Scripts > +New`
- Script name: `RPC_StaffTaskDashboard`
- Source file: `outstanding-task-notifications/dashboard/RPC_StaffTaskDashboard.py`
- Source data: `TaskNote`, `TaskNoteKeyword`, `Keyword`, `People`
- Dependencies: TouchPoint runtime globals `model`, `q`, and `Data`

## Test steps

1. Create or update Python Script `RPC_StaffTaskDashboard` with the script contents.
2. Run it from TouchPoint Special Content — confirm the KPI cards and department matrix render on the default Leadership Rollup view.
3. Switch to Task Detail and confirm rows show keyword chips, age/due badges, and working profile links.
4. Test each filter individually (department, task type, age, due, staff member) and Reset.
5. Confirm the `STRING_AGG` keyword subquery doesn't error — **this needs live validation**; it requires SQL Server 2017+. If it errors, swap in a `FOR XML PATH` string-concatenation fallback.
6. Spot-check the department matrix and a few detail rows against the native TouchPoint task list.

## Expected caveats

- Local validation only checked Python syntax (`py_compile`). The query, `STRING_AGG` usage, and rendered dashboard all still need live TouchPoint execution.
- The staff roster is hardcoded and only ~77% resolved to a real department (49 of 64 as of 2026-08-26, after adding two names Brian confirmed by hand). Update `ROSTER` in the script and this note as more get confirmed.
- The Ministry / Care & Assimilation / System keyword grouping is a judgment call, not a TouchPoint-native categorization — reasoning is in `DB_REFERENCE.md`.
- `TP System` (PeopleId 33283) is a non-human integration account that owns open tasks; it's bucketed under a distinct "System Account" department rather than mixed into real staff numbers, and the dashboard banners it when present. Worth a look at what those tasks actually are.
- Weston Watts (confirmed off staff) is bucketed `Unassigned` rather than removed, so any orphaned open tasks stay visible instead of disappearing.

## Live status (2026-08-26)

Live-tested by Brian; Alan is now reviewing it. Currently reachable only through Admin > Advanced > Special Content's "run script" link -- **not yet added as a page/nav link for other staff.** Revisit the caveats below once it is.

---

# RPC My Task Board

Personal Kanban-style sibling of the two dashboards above. `RPC_MyTaskBoard.py` answers a different question than the church-wide/SM dashboards: "what does *my* queue look like right now," Trello-style, instead of a leadership rollup.

## What it does

Columns = `TaskNote.StatusId` (the only status-like field TaskNote has -- there is no native multi-stage/Kanban field, confirmed in `DB_REFERENCE.md`):

- **To Do** (StatusId 2 / Pending)
- **In Progress** (StatusId 3 / Active)
- **Done** (StatusId 1 / Complete) -- last 14 days only, so the board doesn't fill up with completion history
- **Declined** (StatusId 4) -- last 14 days, column hidden entirely when empty

Cards are color-coded by task age using the same bucket labels/thresholds as `RPC_StaffTaskDashboard.py`'s detail view (New / Getting Stale / Needs a Nudge / Falling Behind / Backlogged / Forgotten), shown as both a left-border stripe and an age pill, plus a due-date pill and keyword-code chips. Every card links out to the about-person's TouchPoint profile.

**Row-level security:** scoped to the logged-in user via `model.UserPeopleId`, the same pattern proven in `../TouchPointScripts/SM_OutstandingTasksList.py`. This is code-level filtering, not a TouchPoint permission feature.

**v1 is read-only.** No drag-and-drop, no status write-back -- cards link to the native TouchPoint profile/task list for any action. A v2 that writes `StatusId` back on a column move is a deliberate follow-up requiring Brian's explicit sign-off and a rollback plan (per this repo's read-only-by-default rule).

## Known gap before wider rollout

The script accepts an optional `?pid=` query param (mirrors `SM_OutstandingTasksList.py`'s `Data.pid`) so Brian/admin can view another person's board for testing. **It is not role-gated** -- anyone who can reach the script URL and knows another PeopleId can currently view that person's board. That's an acceptable gap while this is only reachable via the admin "run script" link; it needs to be removed or replaced with a real role check before this is added as a general staff-facing nav page.

## TouchPoint Deployment

- Type: Python Script
- TouchPoint path: `Admin > Advanced > Special Content > Python Scripts > +New`
- Script name: `RPC_MyTaskBoard`
- Source file: `outstanding-task-notifications/dashboard/RPC_MyTaskBoard.py`
- Source data: `TaskNote`, `TaskNoteKeyword`, `Keyword`, `People`
- Dependencies: TouchPoint runtime globals `model`, `q`, and `Data`

## Test steps

1. Create or update Python Script `RPC_MyTaskBoard` with the script contents.
2. Run it while logged in as a staff member with open tasks -- confirm the board shows only that person's tasks (assignee if set, else owner).
3. Confirm columns render as To Do / In Progress / Done, with Declined appearing only if that person has a recent declined task.
4. Confirm card color/border matches age (spot-check one old task and one new task).
5. Confirm the `STRING_AGG` keyword subquery doesn't error -- **needs live validation**, same caveat as `RPC_StaffTaskDashboard.py`.
6. Test the `?pid=` admin override with a different PeopleId and confirm the "viewing via override" banner appears.
7. Confirm card links open the right person's TouchPoint profile.

## Expected caveats

- Local validation only checked Python syntax (`py_compile`). The query, `STRING_AGG` usage, and rendered board still need live TouchPoint execution.
- Not yet added as a page for staff -- reachable only via Special Content "run script" today. Close the `?pid=` gap above first.
- Keyword chips show raw codes (e.g. `SG`, `CP`), not the fuller description/group labels `RPC_StaffTaskDashboard.py` uses -- kept intentionally lightweight since this view isn't filtering by task type.
