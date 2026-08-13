# SM_StaffTaskDashboard.py - RockPointe Student Ministry Staff Task Dashboard
#
# TouchPoint deployment:
#   Admin > Advanced > Special Content > Python Scripts > +New
#   Name: SM_StaffTaskDashboard
#
# Purpose:
#   Shows outstanding Student Ministry staff/volunteer tasks by owner, assignee,
#   age, and due date using TaskNote as the source data.
#
# Backlog/project tracking note:
#   This dashboard intentionally runs inside TouchPoint. Linear can be used as the
#   project backlog for bugs/enhancements discovered during live testing, but it is
#   not the runtime display for TaskNote data.

global model, q, Data

# Confirmed hardcoded SM staff/volunteer PeopleIds.
# Keep this in sync with DB_REFERENCE.md and SM_TaskNote-ToDo.sql.
SM_STAFF = [
    (46965, "Isaac Jiles"),
    (659, "Price Peden"),
    (284, "Courtney Edmondson"),
    (23164, "Joseph McCalley"),
    (1675, "Libbie Risberg"),
    (40594, "Haven Burton"),
    (36696, "Joshua Watson"),
    (28000, "Abbie Vinson"),
    (19570, "Weston Watts"),
    (118, "Shawn Adams"),
]

HIGHLIGHT_DAYS_OLD = 7
CRITICAL_DAYS_OLD = 14
NEW_PERSON_DATA_ENTRY_PREFIX = "New Person Data Entry%"


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
    text = str(value)
    return html_escape(text[:10])


def people_options(selected):
    options = ['<option value="all">All SM staff</option>']
    for people_id, name in SM_STAFF:
        selected_attr = " selected" if str(people_id) == selected else ""
        options.append(
            '<option value="{0}"{2}>{1}</option>'.format(
                people_id, html_escape(name), selected_attr
            )
        )
    return "\n".join(options)


def get_param(name, default_value):
    try:
        value = getattr(Data, name)
        if value is None or value == "":
            return default_value
        return str(value).strip()
    except Exception:
        return default_value


def valid_staff_filter(raw_value):
    if raw_value == "all":
        return "all"
    valid_ids = [str(row[0]) for row in SM_STAFF]
    if raw_value in valid_ids:
        return raw_value
    return "all"


owner_filter = valid_staff_filter(get_param("owner", "all"))
assignee_filter = valid_staff_filter(get_param("assignee", "all"))
age_filter = get_param("age", "all")
due_filter = get_param("due", "all")
view_filter = get_param("view", "detail")

if age_filter not in ["all", "7", "14", "30"]:
    age_filter = "all"
if due_filter not in ["all", "overdue", "today", "7", "none"]:
    due_filter = "all"
if view_filter not in ["detail", "owner", "assignee"]:
    view_filter = "detail"

staff_ids_sql = ", ".join([str(row[0]) for row in SM_STAFF])
where_extra = []

if owner_filter != "all":
    where_extra.append("tn.OwnerId = {}".format(int(owner_filter)))
if assignee_filter != "all":
    where_extra.append("tn.AssigneeId = {}".format(int(assignee_filter)))
if age_filter != "all":
    where_extra.append("DATEDIFF(day, tn.CreatedDate, GETDATE()) >= {}".format(int(age_filter)))
if due_filter == "overdue":
    where_extra.append("tn.DueDate IS NOT NULL AND CAST(tn.DueDate AS DATE) < CAST(GETDATE() AS DATE)")
elif due_filter == "today":
    where_extra.append("tn.DueDate IS NOT NULL AND CAST(tn.DueDate AS DATE) = CAST(GETDATE() AS DATE)")
elif due_filter == "7":
    where_extra.append("tn.DueDate IS NOT NULL AND CAST(tn.DueDate AS DATE) <= DATEADD(day, 7, CAST(GETDATE() AS DATE))")
elif due_filter == "none":
    where_extra.append("tn.DueDate IS NULL")

where_extra_sql = ""
if where_extra:
    where_extra_sql = "AND " + "\nAND ".join(where_extra)

# Outstanding task definition mirrors the SM notification work:
# - Owner owns declined tasks and unassigned pending/active tasks.
# - Assignee owns assigned pending/active tasks.
# - Include IsNote NULL because live tasks store NULL in practice.
# - Exclude TouchPoint's noisy New Person Data Entry tasks.
task_sql = """
SELECT
    tn.OwnerId,
    COALESCE(ownerPerson.NickName, ownerPerson.FirstName) AS OwnerFirst,
    ownerPerson.LastName AS OwnerLast,
    tn.AssigneeId,
    COALESCE(assigneePerson.NickName, assigneePerson.FirstName) AS AssigneeFirst,
    assigneePerson.LastName AS AssigneeLast,
    tn.AboutPersonId,
    COALESCE(aboutPerson.NickName, aboutPerson.FirstName) AS AboutFirst,
    aboutPerson.LastName AS AboutLast,
    tn.StatusId,
    CASE tn.StatusId
        WHEN 2 THEN 'Pending'
        WHEN 3 THEN 'Active'
        WHEN 4 THEN 'Declined'
        ELSE CAST(tn.StatusId AS VARCHAR(20))
    END AS StatusName,
    tn.CreatedDate,
    tn.DueDate,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld,
    CASE
        WHEN tn.DueDate IS NULL THEN 0
        WHEN CAST(tn.DueDate AS DATE) < CAST(GETDATE() AS DATE) THEN 1
        ELSE 0
    END AS IsOverdue,
    DATEDIFF(day, CAST(GETDATE() AS DATE), CAST(tn.DueDate AS DATE)) AS DaysUntilDue,
    tn.Instructions
FROM TaskNote tn
LEFT JOIN People ownerPerson ON ownerPerson.PeopleId = tn.OwnerId
LEFT JOIN People assigneePerson ON assigneePerson.PeopleId = tn.AssigneeId
LEFT JOIN People aboutPerson ON aboutPerson.PeopleId = tn.AboutPersonId
WHERE (
    tn.OwnerId IN ({staff_ids})
    OR tn.AssigneeId IN ({staff_ids})
)
AND (
    tn.StatusId = 4
    OR tn.StatusId IN (2, 3)
)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE '{new_person_prefix}')
{where_extra}
ORDER BY
    CASE WHEN tn.DueDate IS NULL THEN 1 ELSE 0 END,
    tn.DueDate ASC,
    tn.CreatedDate ASC
""".format(
    staff_ids=staff_ids_sql,
    new_person_prefix=NEW_PERSON_DATA_ENTRY_PREFIX,
    where_extra=where_extra_sql,
)

tasks = list(q.QuerySql(task_sql))

def person_name(first, last, fallback):
    name = ((first or "") + " " + (last or "")).strip()
    return name if name else fallback


def task_role_bucket(task):
    if task.AssigneeId:
        return task.AssigneeId
    return task.OwnerId


owner_counts = {}
assignee_counts = {}
overdue_count = 0
old_count = 0
no_due_count = 0

for task in tasks:
    owner_id = task.OwnerId or 0
    assignee_id = task.AssigneeId or 0
    owner_counts[owner_id] = owner_counts.get(owner_id, 0) + 1
    if assignee_id:
        assignee_counts[assignee_id] = assignee_counts.get(assignee_id, 0) + 1
    else:
        assignee_counts[0] = assignee_counts.get(0, 0) + 1
    if task.IsOverdue:
        overdue_count += 1
    if (task.DaysOld or 0) >= HIGHLIGHT_DAYS_OLD:
        old_count += 1
    if not task.DueDate:
        no_due_count += 1

print("""
<style>
.sm-task-dashboard { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2933; }
.sm-task-dashboard .hero { background: #12355b; color: white; border-radius: 12px; padding: 22px 26px; margin-bottom: 18px; }
.sm-task-dashboard .hero h1 { margin: 0 0 6px 0; font-size: 28px; }
.sm-task-dashboard .hero p { margin: 0; opacity: .9; }
.sm-task-dashboard .cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 18px; }
.sm-task-dashboard .card { flex: 1; min-width: 155px; background: #f7fafc; border: 1px solid #d9e2ec; border-radius: 10px; padding: 14px; }
.sm-task-dashboard .metric { font-size: 30px; font-weight: 800; line-height: 1; }
.sm-task-dashboard .label { color: #52606d; font-size: 13px; margin-top: 5px; }
.sm-task-dashboard .filters { background: #f0f4f8; border: 1px solid #d9e2ec; border-radius: 10px; padding: 14px; margin-bottom: 18px; }
.sm-task-dashboard .filters form { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; margin: 0; }
.sm-task-dashboard .field label { display: block; font-size: 12px; color: #52606d; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .04em; }
.sm-task-dashboard select { padding: 7px 10px; border: 1px solid #bcccdc; border-radius: 6px; background: white; }
.sm-task-dashboard button, .sm-task-dashboard .button { background: #0b6bcb; color: white; border: 0; border-radius: 6px; padding: 8px 13px; text-decoration: none; cursor: pointer; display: inline-block; }
.sm-task-dashboard .button.secondary { background: #627d98; }
.sm-task-dashboard table { width: 100%; border-collapse: collapse; margin-bottom: 18px; }
.sm-task-dashboard th { background: #243b53; color: white; text-align: left; padding: 10px; font-size: 13px; }
.sm-task-dashboard td { border-bottom: 1px solid #d9e2ec; padding: 10px; vertical-align: top; }
.sm-task-dashboard tr.overdue td { background: #fff5f5; }
.sm-task-dashboard tr.old td { background: #fffbeb; }
.sm-task-dashboard .pill { display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; }
.sm-task-dashboard .pill.red { background: #fde2e2; color: #b42318; }
.sm-task-dashboard .pill.yellow { background: #fff3bf; color: #7c5e10; }
.sm-task-dashboard .pill.blue { background: #dbeafe; color: #1d4ed8; }
.sm-task-dashboard .pill.gray { background: #e5e7eb; color: #374151; }
.sm-task-dashboard .instructions { max-width: 520px; }
.sm-task-dashboard .muted { color: #627d98; }
.sm-task-dashboard .empty { text-align: center; padding: 32px; background: #f0fff4; border: 1px solid #c6f6d5; border-radius: 10px; color: #276749; font-weight: 700; }
</style>
<div class="sm-task-dashboard">
  <div class="hero">
    <h1>SM Staff Task Dashboard</h1>
    <p>Outstanding TouchPoint TaskNote tasks for confirmed Student Ministry staff and volunteers.</p>
  </div>
""")

print("""
  <div class="cards">
    <div class="card"><div class="metric">{total}</div><div class="label">Outstanding tasks</div></div>
    <div class="card"><div class="metric">{overdue}</div><div class="label">Overdue</div></div>
    <div class="card"><div class="metric">{old}</div><div class="label">{old_days}+ days old</div></div>
    <div class="card"><div class="metric">{no_due}</div><div class="label">No due date</div></div>
  </div>
""".format(total=len(tasks), overdue=overdue_count, old=old_count, old_days=HIGHLIGHT_DAYS_OLD, no_due=no_due_count))

print("""
  <div class="filters">
    <form method="get">
      <div class="field">
        <label for="owner">Owner</label>
        <select id="owner" name="owner">{owner_options}</select>
      </div>
      <div class="field">
        <label for="assignee">Assignee</label>
        <select id="assignee" name="assignee">{assignee_options}</select>
      </div>
      <div class="field">
        <label for="age">Age</label>
        <select id="age" name="age">
          <option value="all"{age_all}>All ages</option>
          <option value="7"{age_7}>7+ days</option>
          <option value="14"{age_14}>14+ days</option>
          <option value="30"{age_30}>30+ days</option>
        </select>
      </div>
      <div class="field">
        <label for="due">Due date</label>
        <select id="due" name="due">
          <option value="all"{due_all}>All due dates</option>
          <option value="overdue"{due_overdue}>Overdue</option>
          <option value="today"{due_today}>Due today</option>
          <option value="7"{due_7}>Due in next 7 days</option>
          <option value="none"{due_none}>No due date</option>
        </select>
      </div>
      <div class="field">
        <label for="view">View</label>
        <select id="view" name="view">
          <option value="detail"{view_detail}>Task detail</option>
          <option value="owner"{view_owner}>Summary by owner</option>
          <option value="assignee"{view_assignee}>Summary by assignee</option>
        </select>
      </div>
      <button type="submit">Apply</button>
      <a class="button secondary" href="?">Reset</a>
    </form>
  </div>
""".format(
    owner_options=people_options(owner_filter),
    assignee_options=people_options(assignee_filter),
    age_all=" selected" if age_filter == "all" else "",
    age_7=" selected" if age_filter == "7" else "",
    age_14=" selected" if age_filter == "14" else "",
    age_30=" selected" if age_filter == "30" else "",
    due_all=" selected" if due_filter == "all" else "",
    due_overdue=" selected" if due_filter == "overdue" else "",
    due_today=" selected" if due_filter == "today" else "",
    due_7=" selected" if due_filter == "7" else "",
    due_none=" selected" if due_filter == "none" else "",
    view_detail=" selected" if view_filter == "detail" else "",
    view_owner=" selected" if view_filter == "owner" else "",
    view_assignee=" selected" if view_filter == "assignee" else "",
))

if not tasks:
    print('<div class="empty">No outstanding SM staff tasks match these filters.</div>')
elif view_filter == "owner":
    print('<table><thead><tr><th>Owner</th><th>Tasks</th></tr></thead><tbody>')
    for people_id, name in SM_STAFF:
        count = owner_counts.get(people_id, 0)
        if count:
            print('<tr><td>{}</td><td>{}</td></tr>'.format(html_escape(name), count))
    print('</tbody></table>')
elif view_filter == "assignee":
    print('<table><thead><tr><th>Assignee</th><th>Tasks</th></tr></thead><tbody>')
    unassigned = assignee_counts.get(0, 0)
    if unassigned:
        print('<tr><td><em>Unassigned — owner is accountable</em></td><td>{}</td></tr>'.format(unassigned))
    for people_id, name in SM_STAFF:
        count = assignee_counts.get(people_id, 0)
        if count:
            print('<tr><td>{}</td><td>{}</td></tr>'.format(html_escape(name), count))
    print('</tbody></table>')
else:
    print("""
  <table>
    <thead>
      <tr>
        <th>Owner</th>
        <th>Assignee</th>
        <th>About</th>
        <th>Status</th>
        <th>Age</th>
        <th>Due</th>
        <th>Task</th>
      </tr>
    </thead>
    <tbody>
    """)
    for task in tasks:
        owner_name = person_name(task.OwnerFirst, task.OwnerLast, "Unknown owner")
        assignee_name = person_name(task.AssigneeFirst, task.AssigneeLast, "Unassigned") if task.AssigneeId else "Unassigned"
        about_name = person_name(task.AboutFirst, task.AboutLast, "—")
        days_old = task.DaysOld or 0
        row_class = ""
        if task.IsOverdue:
            row_class = "overdue"
        elif days_old >= HIGHLIGHT_DAYS_OLD:
            row_class = "old"

        if task.IsOverdue:
            due_badge = '<span class="pill red">Overdue {}</span>'.format(format_date(task.DueDate))
        elif not task.DueDate:
            due_badge = '<span class="pill gray">No due date</span>'
        elif task.DaysUntilDue is not None and task.DaysUntilDue <= 7:
            due_badge = '<span class="pill yellow">Due {}</span>'.format(format_date(task.DueDate))
        else:
            due_badge = '<span class="pill blue">Due {}</span>'.format(format_date(task.DueDate))

        if days_old >= CRITICAL_DAYS_OLD:
            age_badge = '<span class="pill red">{} days</span>'.format(days_old)
        elif days_old >= HIGHLIGHT_DAYS_OLD:
            age_badge = '<span class="pill yellow">{} days</span>'.format(days_old)
        else:
            age_badge = '<span class="pill blue">{} days</span>'.format(days_old)

        about_link = "—"
        if task.AboutPersonId:
            about_link = '<a href="{}/Person2/{}#tab-touchpoints">{}</a>'.format(
                model.CmsHost, task.AboutPersonId, html_escape(about_name)
            )

        print("""
      <tr class="{row_class}">
        <td>{owner}</td>
        <td>{assignee}</td>
        <td>{about}</td>
        <td>{status}</td>
        <td>{age}</td>
        <td>{due}</td>
        <td class="instructions">{instructions}</td>
      </tr>
        """.format(
            row_class=row_class,
            owner=html_escape(owner_name),
            assignee=html_escape(assignee_name),
            about=about_link,
            status=html_escape(task.StatusName),
            age=age_badge,
            due=due_badge,
            instructions=safe_markdown(task.Instructions),
        ))
    print("""
    </tbody>
  </table>
    """)

print("""
  <p class="muted">
    Source: TaskNote. Outstanding = Pending/Active/Declined task records where owner or assignee is in the confirmed SM staff list.
    Notes are excluded with <code>(IsNote = 0 OR IsNote IS NULL)</code>; New Person Data Entry tasks are excluded.
  </p>
</div>
""")
