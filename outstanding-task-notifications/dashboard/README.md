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

## Bug fixed (2026-08-31): KeyError on first live run

Brian's first live test threw `KeyError: The given key was not present in the dictionary.` The `<style>` block's CSS is built inside a Python string that's piped through `.format(viewer=...)` -- `.format()` treats every single `{`/`}` as a placeholder, and raw CSS rules like `.rpc-my-board { ... }` have dozens of them. Fixed by escaping the CSS body's braces to `{{ }}` so only the intended `{viewer}` placeholder resolves. Verified locally by executing the fixed block with a mock `model`/`q`, and by rendering the full script end-to-end -- both come back clean. Checked the two sibling scripts (`RPC_StaffTaskDashboard.py`, `SM_StaffTaskDashboard.py`) for the same pattern: both keep their CSS `print()` separate from any `.format()` call, so they don't have this bug.

## Security gap closed (2026-08-31)

v1 originally had an optional `?pid=` query param (mirroring `SM_OutstandingTasksList.py`'s `Data.pid`) so Brian/admin could view another person's board for testing. It was **not role-gated** -- anyone who could reach the script URL and knew another PeopleId could view that person's board. Removed entirely ahead of the widget rollout below, since a homepage widget is visible to a much wider staff audience than the admin "run script" link. Admins who need to check another person's tasks should use `RPC_StaffTaskDashboard.py`'s Task Detail view (filterable by staff member) instead -- no functionality was actually lost.

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
6. Confirm card links open the right person's TouchPoint profile.

## Expected caveats

- Local validation only checked Python syntax (`py_compile`). The query, `STRING_AGG` usage, and rendered board still need live TouchPoint execution.
- Not yet added as a page for staff -- reachable only via Special Content "run script" today (the compact `RPC_MyTasksWidget.py` below is the homepage-facing entry point; this full board is reached from its "View full board" link).
- Keyword chips show raw codes (e.g. `SG`, `CP`), not the fuller description/group labels `RPC_StaffTaskDashboard.py` uses -- kept intentionally lightweight since this view isn't filtering by task type.

---

# RPC My Tasks Widget

Compact TouchPoint Homepage Widget sibling of `RPC_MyTaskBoard.py`. The full board is a wide, multi-column Kanban layout -- too big for a homepage widget slot -- so this widget shows a short worst-first list of open tasks plus headline counts, with a link out to the full board.

## What it does

- Header shows a red "N overdue" badge when applicable.
- Up to 5 worst-first open tasks (`StatusId` 2/3 only -- no Done/Declined lookback, since this is a "what's outstanding now" view, not a recent-activity view).
- Each row: about-person name (linked to their TouchPoint profile), a truncated instructions snippet, and an age-bucket label using the same color/bucket language as `RPC_MyTaskBoard.py` and `RPC_StaffTaskDashboard.py`.
- "+N more open tasks" line when there are more than 5.
- Footer link to the full Kanban board (`RPC_MyTaskBoard`) via `/PyScript/RPC_MyTaskBoard`.

**Row-level security:** `model.UserPeopleId` only -- this widget was written without the `?pid=` admin-override pattern in the first place, since a homepage widget has a much wider audience than an admin-only "run script" link.

**Why not TouchPoint's stock My Tasks widget:** TouchPoint ships a built-in My Tasks widget, but per TouchPoint's docs it queries the legacy `Task` table, not `TaskNote`. `DB_REFERENCE.md` confirms RPC's `Task` table has an approximate row count of 0 -- all live RPC task data is in `TaskNote`. The stock widget would render empty here.

**Styling:** reuses TouchPoint's own `box` / `box-title` / `list-group` CSS classes (confirmed from the stock Vital Stats widget's markup) so it visually matches other homepage widgets instead of introducing a new look.

**v1 is read-only**, same rule as the full board -- rows link out to the person's TouchPoint profile for any action.

## TouchPoint Deployment

1. `Admin > Advanced > Special Content > Python Scripts > +New`, name `RPC_MyTasksWidget`, paste in the script contents, and set **Content Keywords** to `Widget` (required for it to be selectable as a widget's Code file).
2. `Admin > Advanced > Homepage Widgets > + Add Widget`:
   - **Code (Python):** `RPC_MyTasksWidget`
   - **View (HTML):** none needed -- this script prints its own HTML directly (confirmed possible from a community widget's install instructions: a widget can be registered with only a Python file selected).
   - **Roles:** blank for all logged-in staff, or restrict as desired.
   - **Caching:** recommend "Once a day" / "per user" -- task lists don't need real-time refresh and this is a per-user query.
3. Enable the widget.

## Test steps

1. Create the Python script and register the widget per the steps above.
2. Load the TouchPoint homepage as a staff member with open tasks -- confirm the widget shows only that person's tasks, worst-first, capped at 5.
3. Confirm the overdue badge appears only when the person has an overdue task, and the count matches.
4. Confirm each row's name link opens the right TouchPoint profile.
5. Confirm "View full board" links to the working `RPC_MyTaskBoard` page.
6. Load as a staff member with zero open tasks -- confirm the "Nothing outstanding right now" empty state.

## Expected caveats

- Local validation only checked Python syntax (`py_compile`). The query and rendered widget still need live TouchPoint execution, including whether the Homepage Widgets admin form actually allows leaving View (HTML) blank -- if it doesn't, a trivial placeholder Text file tagged `Widget` will need to be created and selected instead.
- Widget caching means the list can lag behind real-time task changes by up to the configured cache interval -- acceptable tradeoff for a homepage glance view, not appropriate if Brian wants live-refresh behavior.
