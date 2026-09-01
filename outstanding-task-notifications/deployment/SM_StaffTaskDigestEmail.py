# SM_StaffTaskDigestEmail.py - RockPointe Student Ministry weekly staff task digest
#
# Built for Max McCalley (SM Leader): a Monday-morning email showing the
# status of every SM staff member's outstanding TouchPoint tasks (who has
# what, how old, overdue or not) in one place, instead of him having to
# visit an interactive dashboard.
#
# Replaces SM_StaffTaskDashboard.py (retired 2026-08-31 -- was an on-demand
# in-TouchPoint page, never scheduled or emailed, so it could never satisfy
# a "Max gets this automatically" request on its own). This script reuses
# that dashboard's query shape and RPC_StaffTaskDashboard.py's "accountable
# = assignee if set, else owner" convention, rendered as a single inline-
# styled email instead of a filterable page.
#
# DEPLOYMENT: Admin > Advanced > Special Content > Python Scripts
# File name should be: SM_StaffTaskDigestEmail
#
# SCHEDULING: add to MorningBatch, gated to Monday only:
#   if model.DayOfWeek == 1:
#       model.CallScript("SM_StaffTaskDigestEmail")
#
# TESTING:
# - TEST_MODE = True renders an HTML preview only (view via the Special
#   Content "run script" link) and sends no email.
# - TEST_MODE = False and TEST_RECIPIENT_PEOPLE_ID set sends one controlled
#   email to that PeopleId instead of Max, for a live send test.
# - TEST_MODE = False and TEST_RECIPIENT_PEOPLE_ID empty sends the real
#   digest to RECIPIENT_PEOPLE_ID (Max). Do not flip this live without a
#   controlled test send first.

global model, q

# ============================================================
# CONFIGURATION
# ============================================================

TEST_MODE = False  # True = render preview only; False = send email
TEST_RECIPIENT_PEOPLE_ID = None  # e.g. 47110 (Brian Vinson) for a controlled test send

RECIPIENT_PEOPLE_ID = 23164  # Max McCalley; confirmed live PeopleId
QUEUED_BY = 23164  # Max McCalley

FROM_EMAIL = "studentministry@rockpointechurch.org"
FROM_NAME = "RockPointe Student Ministry"
SUBJECT = "Student Ministry - Weekly Staff Task Digest"

HIGHLIGHT_DAYS_OLD = 7
CRITICAL_DAYS_OLD = 14

# Confirmed SM staff PeopleIds; keep synchronized with DB_REFERENCE.md's
# "SM Staff" table and SM_TaskNote-ToDo.sql's @SMStaff block.
# Weston Watts (19570) removed 2026-08-31 -- confirmed off staff 2026-08-26.
SM_STAFF = [
    (46965, "Isaac Jiles"),
    (659, "Price Peden"),
    (284, "Courtney Edmondson"),
    (23164, "Max McCalley"),
    (1675, "Libbie Risberg"),
    (40594, "Haven Burton"),
    (36696, "Joshua Watson"),
    (28000, "Abbie Vinson"),
    (118, "Shawn Adams"),
]

NEW_PERSON_DATA_ENTRY_PREFIX = "New Person Data Entry%"

# ============================================================
# DATA QUERY
# ============================================================

# Task definition matches SM_OutstandingTaskNotifications.py / SM_OutstandingTasksList.py:
# - StatusId 2 (Pending) or 3 (Active) only -- Declined/Complete are not outstanding.
# - Exclude notes/history and New Person Data Entry housekeeping tasks.
# - Exclude archived tasks (IsArchived is a separate flag from StatusId -- confirmed
#   2026-08-25 that some StatusId IN (2,3) rows are already archived; without this
#   filter they'd show as live work staff already closed out).
staff_ids_sql = ", ".join(str(pid) for pid, _ in SM_STAFF)

task_sql = """
SELECT
    tn.TaskNoteId,
    tn.OwnerId,
    COALESCE(ownerPerson.NickName, ownerPerson.FirstName) AS OwnerFirst,
    ownerPerson.LastName AS OwnerLast,
    tn.AssigneeId,
    COALESCE(assigneePerson.NickName, assigneePerson.FirstName) AS AssigneeFirst,
    assigneePerson.LastName AS AssigneeLast,
    tn.AboutPersonId,
    COALESCE(aboutPerson.NickName, aboutPerson.FirstName) AS AboutFirst,
    aboutPerson.LastName AS AboutLast,
    tn.CreatedDate,
    tn.DueDate,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld,
    CASE WHEN tn.DueDate IS NOT NULL AND CAST(tn.DueDate AS DATE) < CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END AS IsOverdue,
    tn.Instructions
FROM TaskNote tn
LEFT JOIN People ownerPerson ON ownerPerson.PeopleId = tn.OwnerId
LEFT JOIN People assigneePerson ON assigneePerson.PeopleId = tn.AssigneeId
LEFT JOIN People aboutPerson ON aboutPerson.PeopleId = tn.AboutPersonId
WHERE (
    tn.OwnerId IN ({staff_ids})
    OR tn.AssigneeId IN ({staff_ids})
)
AND tn.StatusId IN (2, 3)
AND (tn.IsArchived = 0 OR tn.IsArchived IS NULL)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE '{new_person_prefix}')
ORDER BY tn.CreatedDate ASC
""".format(staff_ids=staff_ids_sql, new_person_prefix=NEW_PERSON_DATA_ENTRY_PREFIX)


def person_name(first, last, fallback):
    name = ((first or "") + " " + (last or "")).strip()
    return name if name else fallback


raw_tasks = list(q.QuerySql(task_sql))

# Accountable staff member = assignee if set, otherwise owner -- matches
# RPC_StaffTaskDashboard.py's convention (the person actually on the hook).
tasks_by_staff = {pid: [] for pid, _ in SM_STAFF}
for row in raw_tasks:
    accountable_id = row.AssigneeId or row.OwnerId
    if accountable_id not in tasks_by_staff:
        # Owner/assignee is in the WHERE clause but the other side of the
        # pair isn't SM staff (e.g. owner is SM, assignee is another dept).
        # Still attribute it to whichever side is on the SM list.
        if row.OwnerId in tasks_by_staff:
            accountable_id = row.OwnerId
        elif row.AssigneeId in tasks_by_staff:
            accountable_id = row.AssigneeId
        else:
            continue
    tasks_by_staff[accountable_id].append(row)

# ============================================================
# RENDER (inline styles -- email clients strip <style> blocks)
# ============================================================

total_count = len(raw_tasks)
overdue_count = sum(1 for t in raw_tasks if t.IsOverdue)
old_count = sum(1 for t in raw_tasks if (t.DaysOld or 0) >= HIGHLIGHT_DAYS_OLD)

summary_rows = ""
for pid, name in SM_STAFF:
    staff_tasks = tasks_by_staff[pid]
    count = len(staff_tasks)
    overdue = sum(1 for t in staff_tasks if t.IsOverdue)
    day_olds = [t.DaysOld or 0 for t in staff_tasks]
    oldest = max(day_olds) if day_olds else 0

    if count == 0:
        status_cell = '<span style="color:#27ae60;font-weight:bold;">All clear</span>'
    elif overdue:
        status_cell = '<span style="color:#e74c3c;font-weight:bold;">{} overdue</span>'.format(overdue)
    elif oldest >= HIGHLIGHT_DAYS_OLD:
        status_cell = '<span style="color:#d68910;font-weight:bold;">Getting old</span>'
    else:
        status_cell = '<span style="color:#3498db;">On track</span>'

    summary_rows += """
    <tr>
        <td style="padding:8px 10px;border-bottom:1px solid #e1e8ed;">{name}</td>
        <td style="padding:8px 10px;border-bottom:1px solid #e1e8ed;text-align:center;">{count}</td>
        <td style="padding:8px 10px;border-bottom:1px solid #e1e8ed;text-align:center;">{oldest}</td>
        <td style="padding:8px 10px;border-bottom:1px solid #e1e8ed;">{status}</td>
    </tr>
    """.format(name=name, count=count, oldest=(oldest if count else "—"), status=status_cell)

detail_sections = ""
for pid, name in SM_STAFF:
    staff_tasks = tasks_by_staff[pid]
    if not staff_tasks:
        continue

    # Worst first: overdue before not, oldest first within each.
    staff_tasks = sorted(staff_tasks, key=lambda t: (0 if t.IsOverdue else 1, -(t.DaysOld or 0)))

    task_rows = ""
    for task in staff_tasks:
        days_old = task.DaysOld or 0
        instructions = model.Markdown(task.Instructions) if task.Instructions else "(no details)"
        due_date = task.DueDate.ToString("M/d/yyyy") if task.DueDate else "No due date"
        about_name = person_name(task.AboutFirst, task.AboutLast, "—")

        if task.IsOverdue:
            border = "#e74c3c"
            badge = '<span style="background:#e74c3c;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">OVERDUE - due {}</span>'.format(due_date)
        elif days_old >= CRITICAL_DAYS_OLD:
            border = "#e74c3c"
            badge = '<span style="background:#e74c3c;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{} days old</span>'.format(days_old)
        elif days_old >= HIGHLIGHT_DAYS_OLD:
            border = "#d68910"
            badge = '<span style="background:#d68910;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{} days old</span>'.format(days_old)
        else:
            border = "#3498db"
            badge = '<span style="background:#3498db;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{} days old</span>'.format(days_old)

        task_rows += """
        <div style="border:1px solid {border};margin:0.75em 0;padding:1em;border-radius:6px;background:#f9f9f9;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5em;">
                <strong>About: {about}</strong>
                {badge}
            </div>
            <div style="font-size:13px;color:#555;margin-bottom:0.5em;">
                Created {created} &middot; Due {due}
            </div>
            <div style="background:white;padding:0.75em;border-left:3px solid {border};">
                {instructions}
            </div>
            <div style="margin-top:0.5em;">
                <a href="{host}/Person2/{about_id}#tab-touchpoints" style="color:#27ae60;text-decoration:none;font-size:13px;">View Profile &rarr;</a>
            </div>
        </div>
        """.format(
            border=border,
            about=about_name,
            badge=badge,
            created=task.CreatedDate.ToString("M/d/yyyy") if task.CreatedDate else "—",
            due=due_date,
            instructions=instructions,
            host=model.CmsHost,
            about_id=task.AboutPersonId,
        )

    detail_sections += """
    <h3 style="color:#2c3e50;border-bottom:2px solid #d9e2ec;padding-bottom:4px;margin-top:1.75em;">{name} ({count})</h3>
    {rows}
    """.format(name=name, count=len(staff_tasks), rows=task_rows)

body = """
<div style="font-family:Arial,Helvetica,sans-serif;max-width:760px;margin:0 auto;color:#222;">
    <p>Hi Max,</p>
    <p>Here's the Student Ministry team's outstanding TouchPoint task status for the week.</p>

    <div style="display:flex;gap:10px;margin:1.25em 0;">
        <div style="flex:1;background:#f7fafc;border:1px solid #d9e2ec;border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:24px;font-weight:800;">{total}</div>
            <div style="font-size:12px;color:#52606d;">Open tasks</div>
        </div>
        <div style="flex:1;background:#fff5f5;border:1px solid #fca5a5;border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:#e74c3c;">{overdue}</div>
            <div style="font-size:12px;color:#52606d;">Overdue</div>
        </div>
        <div style="flex:1;background:#fffbeb;border:1px solid #fbbf24;border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:#d68910;">{old}</div>
            <div style="font-size:12px;color:#52606d;">{highlight_days}+ days old</div>
        </div>
    </div>

    <h2 style="color:#2c3e50;">By staff member</h2>
    <table style="width:100%;border-collapse:collapse;">
        <thead>
            <tr style="background:#243b53;color:white;">
                <th style="padding:8px 10px;text-align:left;">Staff</th>
                <th style="padding:8px 10px;">Open</th>
                <th style="padding:8px 10px;">Oldest (days)</th>
                <th style="padding:8px 10px;text-align:left;">Status</th>
            </tr>
        </thead>
        <tbody>
            {summary_rows}
        </tbody>
    </table>

    {detail_header}
    {detail_sections}

    <hr style="border:0;border-top:1px solid #ddd;margin:24px 0;">
    <p style="font-size:12px;color:#888;">
        Source: TaskNote. Open = Pending/Active, not archived, not a note, excluding New Person Data Entry
        housekeeping tasks. A staff member is "accountable" for a task as its assignee, or as owner when
        no assignee is set. Staff roster is hardcoded and maintained in DB_REFERENCE.md -- update it when
        SM staff change.
    </p>
    <p><strong>RockPointe Student Ministry</strong><br>rockpointechurch.org</p>
</div>
""".format(
    total=total_count,
    overdue=overdue_count,
    old=old_count,
    highlight_days=HIGHLIGHT_DAYS_OLD,
    summary_rows=summary_rows,
    detail_header='<h2 style="color:#2c3e50;">Task detail</h2>' if detail_sections else "",
    detail_sections=detail_sections or '<p style="color:#27ae60;font-weight:bold;">No outstanding tasks for the team. Nice work!</p>',
)

# ============================================================
# PREVIEW / SEND
# ============================================================

if TEST_MODE:
    print("<h3>PREVIEW ONLY -- SM_StaffTaskDigestEmail</h3>")
    print(body)
    print("<p><strong>TEST MODE:</strong> preview rendered; no email sent.</p>")
else:
    recipient = TEST_RECIPIENT_PEOPLE_ID or RECIPIENT_PEOPLE_ID
    model.Email(
        recipient,
        QUEUED_BY,
        FROM_EMAIL,
        FROM_NAME,
        SUBJECT,
        body,
    )
    print("<p>SM staff task digest queued to PeopleId {}.</p>".format(recipient))
