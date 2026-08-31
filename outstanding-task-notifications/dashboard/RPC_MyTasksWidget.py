# RPC_MyTasksWidget.py - RockPointe "My Tasks" TouchPoint Homepage Widget
#
# TouchPoint deployment:
#   1. Admin > Advanced > Special Content > Python Scripts > +New
#      Name: RPC_MyTasksWidget
#      Content Keywords: Widget   (required -- this is how TouchPoint knows
#      it's eligible to attach to a Homepage Widget, confirmed from
#      TPxi's Volunteer Widget install instructions)
#   2. Admin > Advanced > Homepage Widgets > + Add Widget
#      Name/Description: your choice
#      Code (Python): RPC_MyTasksWidget
#      View (HTML): none needed -- this script prints its own HTML directly,
#      same as RPC_MyTaskBoard.py and TPxi's Volunteer Widget (confirmed a
#      widget can be registered with only a Python file selected).
#      Roles: leave blank for all logged-in staff, or restrict as desired.
#      Caching: recommend "Once a day" / "Per user" -- task lists don't need
#      real-time widget refresh, and this is a per-user query.
#
# Purpose:
#   Compact homepage-widget sibling of RPC_MyTaskBoard.py. That page is a
#   full multi-column Kanban board (too wide for a homepage widget slot);
#   this widget is a short worst-first list of open tasks plus headline
#   counts, with a link out to the full board for the Kanban view.
#
# Why not TouchPoint's stock "My Tasks" widget:
#   TouchPoint ships a built-in My Tasks widget, but per TouchPoint's own
#   docs it queries the legacy `Task` table, not `TaskNote`. DB_REFERENCE.md
#   confirms RPC's `Task` table has an approximate row count of 0 -- all of
#   RPC's live task data is in `TaskNote`. The stock widget would render
#   empty here, so this custom widget queries TaskNote instead, same as
#   RPC_MyTaskBoard.py and RPC_StaffTaskDashboard.py.
#
# Row-level security:
#   Scoped to the logged-in TouchPoint user via model.UserPeopleId only --
#   no admin/testing override for another PeopleId (that pattern was removed
#   from RPC_MyTaskBoard.py on 2026-08-31 as a known security gap; this
#   widget was written without it in the first place). Admins who need to
#   check another person's tasks should use RPC_StaffTaskDashboard.py's
#   Task Detail view (filterable by staff member) instead.
#
# v1 is READ-ONLY by design (repo rule: no mutation scripts without explicit
# sign-off + rollback plan). Each row links out to the native TouchPoint
# person profile; there is no drag-and-drop or status write-back here.

global model, q, Data

NEW_PERSON_DATA_ENTRY_PREFIX = "New Person Data Entry%"
MAX_ROWS = 5  # worst-first tasks shown before "view full board"
FULL_BOARD_SCRIPT_NAME = "RPC_MyTaskBoard"

# Same age buckets/colors as RPC_MyTaskBoard.py and RPC_StaffTaskDashboard.py
# so the language and color meaning stay consistent across all three tools.
AGE_BUCKETS = [
    (0, 7, "New"),
    (7, 14, "Getting Stale"),
    (14, 21, "Needs a Nudge"),
    (21, 30, "Falling Behind"),
    (30, 90, "Backlogged"),
    (90, None, "Forgotten"),
]

AGE_COLOR = {
    "New": "#1d4ed8",
    "Getting Stale": "#1d4ed8",
    "Needs a Nudge": "#9a3412",
    "Falling Behind": "#9a3412",
    "Backlogged": "#7c5e10",
    "Forgotten": "#b42318",
}


def html_escape(value):
    if value is None:
        return ""
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def person_name(first, last, fallback):
    name = ((first or "") + " " + (last or "")).strip()
    return name if name else fallback


def age_bucket_for(days_old):
    days_old = days_old or 0
    for lo, hi, label in AGE_BUCKETS:
        if hi is None:
            if days_old >= lo:
                return label
        elif lo <= days_old < hi:
            return label
    return AGE_BUCKETS[-1][2]


def truncate(text, max_len):
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


people_id = model.UserPeopleId

# ---------------------------------------------------------------------------
# Data pull -- one person's accountable open tasks only (assignee if set,
# else owner). No Done/Declined lookback here; this is a "what's outstanding
# right now" widget, not a recent-activity view like the full board.
# ---------------------------------------------------------------------------

task_sql = """
SELECT
    tn.TaskNoteId,
    tn.AboutPersonId,
    COALESCE(abt.NickName, abt.FirstName) AS AboutFirst,
    abt.LastName AS AboutLast,
    tn.DueDate,
    tn.Instructions,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld,
    CASE WHEN tn.DueDate IS NOT NULL AND CAST(tn.DueDate AS DATE) < CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END AS IsOverdue
FROM TaskNote tn
LEFT JOIN People abt ON abt.PeopleId = tn.AboutPersonId
WHERE
    ((tn.OwnerId = {pid} AND tn.AssigneeId IS NULL) OR tn.AssigneeId = {pid})
    AND (tn.IsArchived = 0 OR tn.IsArchived IS NULL)
    AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
    AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE '{new_person_prefix}')
    AND tn.StatusId IN (2, 3)
""".format(pid=int(people_id), new_person_prefix=NEW_PERSON_DATA_ENTRY_PREFIX)

raw_tasks = list(q.QuerySql(task_sql))

tasks = []
for row in raw_tasks:
    days_old = row.DaysOld or 0
    tasks.append({
        "about_id": row.AboutPersonId,
        "about_name": person_name(row.AboutFirst, row.AboutLast, "—"),
        "due_date": row.DueDate,
        "instructions": row.Instructions,
        "days_old": days_old,
        "age_bucket": age_bucket_for(days_old),
        "is_overdue": bool(row.IsOverdue),
    })

total_open = len(tasks)
overdue_open = sum(1 for t in tasks if t["is_overdue"])

# Worst-first: overdue before not, oldest first.
tasks_sorted = sorted(tasks, key=lambda t: (0 if t["is_overdue"] else 1, -t["days_old"]))
top_tasks = tasks_sorted[:MAX_ROWS]
remaining_count = total_open - len(top_tasks)

full_board_url = "{}/PyScript/{}".format(model.CmsHost, FULL_BOARD_SCRIPT_NAME)

# ---------------------------------------------------------------------------
# Rendering -- reuses TouchPoint's own "box" / "list-group" widget styling
# (confirmed from the stock Vital Stats widget) so this fits visually
# alongside other homepage widgets instead of introducing a new look.
# ---------------------------------------------------------------------------

print("""
<div class="box">
    <div class="box-title hidden-xs" style="border:0;">
        <h5>My Tasks{overdue_suffix}</h5>
    </div>
    <a class="visible-xs-block" id="rpc-mytasks-collapse" data-toggle="collapse" href="#rpc-mytasks-section" aria-expanded="true" aria-controls="rpc-mytasks-section">
        <div class="box-title">
            <h5><i class="fa fa-chevron-circle-right"></i>&nbsp;&nbsp;My Tasks</h5>
        </div>
    </a>
    <div class="collapse in" id="rpc-mytasks-section">
""".format(
    overdue_suffix=(
        ' <span class="badge" style="background:#b42318;">{} overdue</span>'.format(overdue_open)
        if overdue_open else ""
    )
))

if total_open == 0:
    print('<div class="box-content" style="padding:10px 14px;color:#94a3b8;">Nothing outstanding right now.</div>')
else:
    print('<ul class="list-group bordered">')
    for t in top_tasks:
        border_hex = AGE_COLOR.get(t["age_bucket"], "#94a3b8")
        about_html = html_escape(t["about_name"])
        if t["about_id"]:
            about_html = '<a href="{}/Person2/{}#tab-touchpoints">{}</a>'.format(
                model.CmsHost, t["about_id"], about_html
            )
        age_label = "{} · {}d".format(t["age_bucket"], t["days_old"])
        snippet = html_escape(truncate(t["instructions"], 70))

        print("""
        <li class="list-group-item" style="border-left:4px solid {border}; padding-left:10px;">
            <div style="font-weight:700; font-size:13px;">{about}</div>
            <div style="font-size:12px; color:#334155;">{snippet}</div>
            <div style="font-size:11px; color:{border}; font-weight:700;">{age}</div>
        </li>
        """.format(border=border_hex, about=about_html, snippet=snippet, age=html_escape(age_label)))
    print("</ul>")

    if remaining_count > 0:
        print('<div style="padding:6px 14px; font-size:12px; color:#627d98;">+ {} more open task{}</div>'.format(
            remaining_count, "" if remaining_count == 1 else "s"
        ))

print("""
    <div style="padding:8px 14px; border-top:1px solid #e5e7eb;">
        <a href="{url}" style="font-size:12px; font-weight:700;">View my full task board &rarr;</a>
    </div>
    </div>
</div>
""".format(url=full_board_url))
