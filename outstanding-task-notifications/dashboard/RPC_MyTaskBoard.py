# RPC_MyTaskBoard.py - RockPointe personal "my tasks" Kanban-style board
#
# TouchPoint deployment:
#   Admin > Advanced > Special Content > Python Scripts > +New
#   Name: RPC_MyTaskBoard
#
# Purpose:
#   Trello-look-alike single-staff-member view of open TaskNote tasks, in
#   columns by native TaskNote.StatusId ("stage") and color-coded by task
#   age. Sibling of RPC_StaffTaskDashboard.py (the church-wide leadership
#   rollup) -- this one is scoped to one person's own queue instead.
#
# Row-level security:
#   Scoped to the logged-in TouchPoint user via model.UserPeopleId, same
#   pattern already proven in
#   ../TouchPointScripts/SM_OutstandingTasksList.py. This is code-level
#   filtering, not a TouchPoint permission/role feature -- see the "Known
#   gap" note below before this is added as a nav link for general staff.
#
# Columns ("stages"):
#   TaskNote has no native multi-stage/Kanban field -- StatusId is the only
#   status-like column, and it has exactly 4 non-note values (confirmed
#   2026-08-25, see DB_REFERENCE.md "TaskNote" section):
#     2 = Pending   -> "To Do"
#     3 = Active    -> "In Progress"
#     1 = Complete  -> "Done" (shown for a short recent lookback only, so
#                      the board doesn't accumulate a person's entire
#                      completion history)
#     4 = Declined  -> "Declined" (shown for the same recent lookback,
#                      and only rendered at all if non-empty -- rare)
#   No fake/invented stage field. lookup.TaskStatus does NOT map to this
#   StatusId -- do not join it (confirmed wrong in DB_REFERENCE.md).
#
# v1 is READ-ONLY by design (repo rule: no mutation scripts without
# explicit sign-off + rollback plan). Every card links out to the native
# TouchPoint person profile; there is no drag-and-drop and no status write-
# back in this version. A v2 that lets a card's column change actually move
# StatusId is a deliberate follow-up requiring Brian's explicit approval.
#
# Known gap (close before this is a staff-facing nav link, not just a
# Special Content "run script" link):
#   The optional pid= override below exists for Brian/admin testing only
#   (mirrors the Data.Person/Data.pid pattern in SM_OutstandingTasksList.py).
#   It is NOT role-gated. Anyone who can reach this script's URL and knows
#   another person's PeopleId can currently view that person's board. Fine
#   while this is only reachable via Admin > Special Content "run script";
#   remove the override or add a real role check before adding it as a
#   general staff-facing page.

global model, q, Data

NEW_PERSON_DATA_ENTRY_PREFIX = "New Person Data Entry%"
RECENT_LOOKBACK_DAYS = 14  # how far back Done/Declined columns reach

# StatusId -> (Column label, sort order)
STATUS_COLUMNS = [
    (2, "To Do"),
    (3, "In Progress"),
    (1, "Done"),
    (4, "Declined"),
]

# (min_days, max_days_exclusive_or_None, label) -- same buckets/order as
# RPC_StaffTaskDashboard.py, kept identical so staff see the same age
# language in both tools.
AGE_BUCKETS = [
    (0, 7, "New"),
    (7, 14, "Getting Stale"),
    (14, 21, "Needs a Nudge"),
    (21, 30, "Falling Behind"),
    (30, 90, "Backlogged"),
    (90, None, "Forgotten"),
]

# Age bucket -> (pill class, card left-border hex). Same 3-tier grouping
# RPC_StaffTaskDashboard.py uses for its detail-view pills, so color meaning
# stays consistent across both tools.
AGE_COLOR = {
    "New": ("blue", "#1d4ed8"),
    "Getting Stale": ("blue", "#1d4ed8"),
    "Needs a Nudge": ("orange", "#9a3412"),
    "Falling Behind": ("orange", "#9a3412"),
    "Backlogged": ("yellow", "#7c5e10"),
    "Forgotten": ("red", "#b42318"),
}

DUE_COLORS = {"Overdue": "red", "Today": "orange", "This Week": "yellow", "Later": "blue", "No Due Date": "gray"}


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


def safe_markdown(value):
    if not value:
        return "<em>No task instructions entered.</em>"
    return model.Markdown(value)


def format_date(value):
    if not value:
        return "—"
    return html_escape(str(value)[:10])


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


def due_bucket_for(is_overdue, due_date, days_until_due):
    if not due_date:
        return "No Due Date"
    if is_overdue:
        return "Overdue"
    if days_until_due is not None and days_until_due <= 0:
        return "Today"
    if days_until_due is not None and days_until_due <= 7:
        return "This Week"
    return "Later"


# ---------------------------------------------------------------------------
# Who is this board for
# ---------------------------------------------------------------------------

viewing_other_person = False
try:
    override_pid = Data.pid
except Exception:
    override_pid = None

if override_pid:
    try:
        people_id = int(str(override_pid).strip())
        viewing_other_person = True
    except (TypeError, ValueError):
        people_id = model.UserPeopleId
else:
    people_id = model.UserPeopleId

viewer_row = list(q.QuerySql(
    "SELECT COALESCE(NickName, FirstName) AS GoesBy, LastName FROM People WHERE PeopleId = {}".format(int(people_id))
))
viewer_name = person_name(viewer_row[0].GoesBy, viewer_row[0].LastName, "Unknown") if viewer_row else "Unknown"

# ---------------------------------------------------------------------------
# Data pull -- one person's accountable tasks (assignee if set, else owner),
# open (Pending/Active) plus a short recent window of Complete/Declined so
# the board shows what just moved, not the person's entire task history.
# ---------------------------------------------------------------------------

task_sql = """
SELECT
    tn.TaskNoteId,
    tn.StatusId,
    tn.OwnerId,
    tn.AssigneeId,
    tn.AboutPersonId,
    COALESCE(abt.NickName, abt.FirstName) AS AboutFirst,
    abt.LastName AS AboutLast,
    tn.CreatedDate,
    tn.DueDate,
    tn.CompletedDate,
    tn.ModifiedDate,
    tn.Instructions,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld,
    CASE WHEN tn.DueDate IS NOT NULL AND CAST(tn.DueDate AS DATE) < CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END AS IsOverdue,
    DATEDIFF(day, CAST(GETDATE() AS DATE), CAST(tn.DueDate AS DATE)) AS DaysUntilDue,
    (
        SELECT STRING_AGG(k.Code, ',')
        FROM TaskNoteKeyword tnk
        JOIN Keyword k ON k.KeywordId = tnk.KeywordId
        WHERE tnk.TaskNoteId = tn.TaskNoteId
    ) AS KeywordCodes
FROM TaskNote tn
LEFT JOIN People abt ON abt.PeopleId = tn.AboutPersonId
WHERE
    ((tn.OwnerId = {pid} AND tn.AssigneeId IS NULL) OR tn.AssigneeId = {pid})
    AND (tn.IsArchived = 0 OR tn.IsArchived IS NULL)
    AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
    AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE '{new_person_prefix}')
    AND (
        tn.StatusId IN (2, 3)
        OR (tn.StatusId = 1 AND tn.CompletedDate >= DATEADD(day, -{lookback}, GETDATE()))
        OR (tn.StatusId = 4 AND tn.ModifiedDate >= DATEADD(day, -{lookback}, GETDATE()))
    )
""".format(pid=int(people_id), new_person_prefix=NEW_PERSON_DATA_ENTRY_PREFIX, lookback=RECENT_LOOKBACK_DAYS)
# NOTE: STRING_AGG requires SQL Server 2017+ -- same unconfirmed-on-live-RPC
# caveat as RPC_StaffTaskDashboard.py. If it errors, swap in FOR XML PATH.

raw_tasks = list(q.QuerySql(task_sql))

tasks = []
for row in raw_tasks:
    about_name = person_name(row.AboutFirst, row.AboutLast, "—")
    keyword_codes = [c.strip() for c in (row.KeywordCodes or "").split(",") if c.strip()]
    days_old = row.DaysOld or 0
    tasks.append({
        "task_note_id": row.TaskNoteId,
        "status_id": row.StatusId,
        "about_id": row.AboutPersonId,
        "about_name": about_name,
        "created_date": row.CreatedDate,
        "due_date": row.DueDate,
        "completed_date": row.CompletedDate,
        "days_old": days_old,
        "age_bucket": age_bucket_for(days_old),
        "is_overdue": bool(row.IsOverdue),
        "due_bucket": due_bucket_for(row.IsOverdue, row.DueDate, row.DaysUntilDue),
        "instructions": row.Instructions,
        "keyword_codes": keyword_codes,
    })

columns = {}
for status_id, label in STATUS_COLUMNS:
    columns[status_id] = [t for t in tasks if t["status_id"] == status_id]

total_open = len(columns.get(2, [])) + len(columns.get(3, []))
overdue_open = sum(1 for t in tasks if t["status_id"] in (2, 3) and t["is_overdue"])
forgotten_open = sum(1 for t in tasks if t["status_id"] in (2, 3) and t["age_bucket"] == "Forgotten")

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

print("""
<style>
.rpc-my-board { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2933; }
.rpc-my-board .hero { background: #12355b; color: white; border-radius: 12px; padding: 20px 26px; margin-bottom: 16px; }
.rpc-my-board .hero h1 { margin: 0 0 6px 0; font-size: 26px; }
.rpc-my-board .hero p { margin: 0; opacity: .9; }
.rpc-my-board .cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.rpc-my-board .card { flex: 1; min-width: 150px; background: #f7fafc; border: 1px solid #d9e2ec; border-radius: 10px; padding: 12px 14px; }
.rpc-my-board .card.warn { background: #fff5f5; border-color: #fca5a5; }
.rpc-my-board .metric { font-size: 26px; font-weight: 800; line-height: 1; }
.rpc-my-board .label { color: #52606d; font-size: 12px; margin-top: 4px; }
.rpc-my-board .banner { background: #fffbeb; border: 1px solid #fbbf24; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: 14px; }
.rpc-my-board .banner.info { background: #eff6ff; border-color: #93c5fd; }
.rpc-my-board .board { display: flex; gap: 14px; overflow-x: auto; padding-bottom: 8px; align-items: flex-start; }
.rpc-my-board .column { flex: 0 0 280px; background: #eef2f6; border-radius: 10px; padding: 10px; }
.rpc-my-board .column-header { display: flex; justify-content: space-between; align-items: center; padding: 4px 6px 10px 6px; font-weight: 700; font-size: 14px; color: #243b53; }
.rpc-my-board .column-count { background: #d9e2ec; color: #243b53; border-radius: 999px; padding: 1px 9px; font-size: 12px; }
.rpc-my-board .task-card { background: white; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.08); border-left: 5px solid #cbd5e1; }
.rpc-my-board .task-card .badges { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.rpc-my-board .task-card .about { font-weight: 700; font-size: 13px; margin-bottom: 4px; }
.rpc-my-board .task-card .about a { color: #12355b; text-decoration: none; }
.rpc-my-board .task-card .body { font-size: 13px; color: #334155; margin-bottom: 6px; max-height: 4.5em; overflow: hidden; }
.rpc-my-board .task-card .keyword-chip { display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 6px; padding: 2px 7px; font-size: 11px; margin: 1px 3px 1px 0; }
.rpc-my-board .task-card .open-link { font-size: 12px; font-weight: 700; color: #0b6bcb; text-decoration: none; }
.rpc-my-board .pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.rpc-my-board .pill.red { background: #fde2e2; color: #b42318; }
.rpc-my-board .pill.orange { background: #ffedd5; color: #9a3412; }
.rpc-my-board .pill.yellow { background: #fff3bf; color: #7c5e10; }
.rpc-my-board .pill.blue { background: #dbeafe; color: #1d4ed8; }
.rpc-my-board .pill.gray { background: #e5e7eb; color: #374151; }
.rpc-my-board .empty-column { color: #94a3b8; font-size: 12px; text-align: center; padding: 18px 6px; }
.rpc-my-board .muted { color: #627d98; }
</style>
<div class="rpc-my-board">
  <div class="hero">
    <h1>My Task Board</h1>
    <p>{viewer}'s open TouchPoint tasks -- by stage, color-coded by age.</p>
  </div>
""".format(viewer=html_escape(viewer_name)))

if viewing_other_person:
    print(
        '<div class="banner">Viewing <strong>{}</strong>\'s board via admin override '
        '(<code>?pid=</code>) -- not your own login. This override is for testing only; '
        'see the script header\'s "Known gap" note before this page is linked for general '
        'staff use.</div>'.format(html_escape(viewer_name))
    )

print("""
  <div class="cards">
    <div class="card"><div class="metric">{total}</div><div class="label">Open (To Do + In Progress)</div></div>
    <div class="card warn"><div class="metric">{overdue}</div><div class="label">Overdue</div></div>
    <div class="card warn"><div class="metric">{forgotten}</div><div class="label">Forgotten (90+ days)</div></div>
  </div>
  <div class="banner info">Read-only preview. Click a card to open the related TouchPoint profile;
  use the native task list there to change status, reassign, or complete a task. Drag-and-drop
  stage changes are planned for a future version.</div>
""".format(total=total_open, overdue=overdue_open, forgotten=forgotten_open))

print('<div class="board">')
for status_id, label in STATUS_COLUMNS:
    items = columns.get(status_id, [])
    if status_id == 4 and not items:
        continue  # Declined column only shown when non-empty

    # Worst-first within a column: overdue before not, oldest first.
    items_sorted = sorted(items, key=lambda t: (0 if t["is_overdue"] else 1, -t["days_old"]))

    print('<div class="column"><div class="column-header"><span>{}</span><span class="column-count">{}</span></div>'.format(
        html_escape(label), len(items_sorted)
    ))

    if not items_sorted:
        print('<div class="empty-column">Nothing here</div>')

    for t in items_sorted:
        age_pill_class, border_hex = AGE_COLOR.get(t["age_bucket"], ("gray", "#94a3b8"))
        age_badge = '<span class="pill {}">{} &middot; {}d</span>'.format(age_pill_class, t["age_bucket"], t["days_old"])

        due_label = t["due_bucket"]
        if t["due_date"] and due_label != "No Due Date":
            due_label = "{} ({})".format(due_label, format_date(t["due_date"]))
        due_badge = '<span class="pill {}">{}</span>'.format(DUE_COLORS.get(t["due_bucket"], "gray"), due_label)

        about_html = html_escape(t["about_name"])
        if t["about_id"]:
            about_html = '<a href="{}/Person2/{}#tab-touchpoints">{}</a>'.format(model.CmsHost, t["about_id"], about_html)

        keyword_html = "".join('<span class="keyword-chip">{}</span>'.format(html_escape(k)) for k in t["keyword_codes"])

        print("""
        <div class="task-card" style="border-left-color: {border}">
          <div class="badges">{age}{due}</div>
          <div class="about">{about}</div>
          <div class="body">{instructions}</div>
          {keywords}
          {open_link}
        </div>
        """.format(
            border=border_hex,
            age=age_badge,
            due=due_badge,
            about=about_html,
            instructions=safe_markdown(t["instructions"]),
            keywords='<div>{}</div>'.format(keyword_html) if keyword_html else "",
            open_link='<a class="open-link" href="{}/Person2/{}#tab-touchpoints">Open in TouchPoint &rarr;</a>'.format(
                model.CmsHost, t["about_id"]
            ) if t["about_id"] else "",
        ))

    print('</div>')
print('</div>')

print("""
  <p class="muted">
    Source: TaskNote, scoped to this person as assignee (or owner when no assignee is set).
    Open = Pending/Active; Done/Declined show only the last {lookback} days so the board
    doesn't fill up with old history. Excludes archived tasks, notes, and New Person Data
    Entry housekeeping tasks. Column = TaskNote.StatusId; there is no other stage/workflow
    field in TouchPoint for tasks.
  </p>
</div>
""".format(lookback=RECENT_LOOKBACK_DAYS))
