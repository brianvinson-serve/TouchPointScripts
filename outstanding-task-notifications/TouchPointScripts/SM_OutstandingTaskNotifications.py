# SM_OutstandingTaskNotifications.py - RockPointe Student Ministry Task Notifications
# Sends personalized email reminders to SM staff about outstanding tasks.
#
# DEPLOYMENT: Admin > Advanced > Special Content > Python Scripts
# File name should be: SM_OutstandingTaskNotifications
#
# LIVE RPC EVIDENCE:
# - The proven implementation builds the HTML body in this script and uses model.Email(...).
# - No saved draft, email template, or HTML Special Content dependency is required.
# - studentministry@rockpointechurch.org / RockPointe Student Ministry previously sent successfully.
#
# TESTING:
# - TEST_MODE = True renders previews only and sends no email.
# - TEST_MODE = False sends to TEST_STAFF when it contains PeopleIds.
# - TEST_MODE = False with TEST_STAFF empty uses the full confirmed SM_STAFF list.
# - The controlled Abbie test succeeded live on 2026-08-13; do not manually run
#   the production configuration unless a full-audience send is explicitly intended.
#
# SCHEDULING: Production-ready but not scheduled; do not modify MorningBatch
# or another live scheduler without explicit approval.

global model, q

# ============================================================
# CONFIGURATION
# ============================================================

TEST_MODE = False  # True = render preview only; False = send email
TEST_STAFF = []  # Empty = use the full SM_STAFF list; add PeopleIds for controlled tests

FROM_EMAIL = "studentministry@rockpointechurch.org"
FROM_NAME = "RockPointe Student Ministry"
SUBJECT = "Student Ministry - Your Outstanding Tasks"
HIGHLIGHT_DAYS_OLD = 7
QUEUED_BY = 23164  # Max McCalley; confirmed live PeopleId

# Confirmed SM staff PeopleIds; keep synchronized with DB_REFERENCE.md and
# SM_TaskNote-ToDo.sql. Used only when TEST_STAFF is empty.
SM_STAFF = [46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118]

# ============================================================
# DATA QUERIES
# ============================================================

# Keep this filter aligned with SM_TaskNote-ToDo.sql:
# - StatusId 2 or 3 only
# - owner only when no assignee exists; otherwise assignee receives the task
# - exclude notes/history and New Person Data Entry tasks
TASK_SQL = """
SELECT
    tn.TaskNoteId,
    tn.Instructions,
    tn.CreatedDate,
    tn.DueDate,
    tn.OwnerId,
    tn.AssigneeId,
    COALESCE(abt.NickName, abt.FirstName) AS GoesBy,
    abt.LastName,
    abt.EmailAddress AS AboutEmail,
    abt.CellPhone,
    abt.PeopleId AS AboutPeopleId,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld
FROM TaskNote tn
JOIN People abt ON tn.AboutPersonId = abt.PeopleId
WHERE (
    (tn.OwnerId = {0} AND tn.AssigneeId IS NULL)
    OR tn.AssigneeId = {0}
)
AND tn.StatusId IN (2, 3)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE 'New Person Data Entry%')
ORDER BY tn.CreatedDate ASC
"""

STAFF_SQL = """
SELECT
    COALESCE(NickName, FirstName) AS GoesBy,
    LastName,
    EmailAddress
FROM People
WHERE PeopleId = {0}
"""

# ============================================================
# PREVIEW / SEND LOGIC
# ============================================================

staffList = TEST_STAFF if TEST_STAFF else SM_STAFF
emailsSent = 0
previewsRendered = 0

for staffId in staffList:
    tasks = list(q.QuerySql(TASK_SQL.format(staffId)))
    if not tasks:
        if TEST_MODE:
            print("<p>No outstanding tasks found for test PeopleId {}.</p>".format(staffId))
        continue

    staffRow = q.QuerySqlTop1(STAFF_SQL.format(staffId))
    if not staffRow:
        if TEST_MODE:
            print("<p>No People record found for test PeopleId {}.</p>".format(staffId))
        continue

    taskBlocks = ""
    taskNum = 0

    for task in tasks:
        taskNum += 1
        daysOld = task.DaysOld if task.DaysOld is not None else 0
        instructions = model.Markdown(task.Instructions) if task.Instructions else "(no details)"
        dueDate = task.DueDate.ToString("M/d/yyyy") if task.DueDate else "No due date"

        if daysOld > HIGHLIGHT_DAYS_OLD:
            borderColor = "#e74c3c"
            urgencyBadge = (
                '<span style="background:#e74c3c;color:white;padding:2px 8px;'
                'border-radius:4px;font-size:12px;">OVERDUE - {} days</span>'
            ).format(daysOld)
        else:
            borderColor = "#3498db"
            urgencyBadge = (
                '<span style="background:#3498db;color:white;padding:2px 8px;'
                'border-radius:4px;font-size:12px;">{} days old</span>'
            ).format(daysOld)

        taskBlocks += """
        <div style="border:2px solid {border};margin:1.5em 0;padding:1.5em;border-radius:8px;background:#f9f9f9;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1em;">
                <strong style="font-size:1.1em;">Follow up with {about_name}</strong>
                {badge}
            </div>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:4px 8px;font-weight:bold;width:100px;">About:</td><td style="padding:4px 8px;">{about_name}</td></tr>
                <tr><td style="padding:4px 8px;font-weight:bold;">Email:</td><td style="padding:4px 8px;"><a href="mailto:{about_email}">{about_email}</a></td></tr>
                <tr><td style="padding:4px 8px;font-weight:bold;">Phone:</td><td style="padding:4px 8px;"><a href="tel:{about_phone}">{about_phone}</a></td></tr>
                <tr><td style="padding:4px 8px;font-weight:bold;">Created:</td><td style="padding:4px 8px;">{created}</td></tr>
                <tr><td style="padding:4px 8px;font-weight:bold;">Due:</td><td style="padding:4px 8px;">{due}</td></tr>
            </table>
            <div style="background:white;padding:1em;margin:1em 0;border-left:4px solid {border};">
                <strong>Task Details:</strong><br>{instructions}
            </div>
            <div style="margin-top:1em;">
                <a href="{host}/Person2/{about_id}#tab-touchpoints" style="background:#27ae60;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;margin-right:8px;">View Profile</a>
                <a href="{host}/Task/List" style="background:#3498db;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;">My Task List</a>
            </div>
        </div>
        """.format(
            border=borderColor,
            about_name=task.GoesBy + " " + task.LastName,
            badge=urgencyBadge,
            about_email=task.AboutEmail or "",
            about_phone=model.FmtPhone(task.CellPhone),
            created=task.CreatedDate,
            due=dueDate,
            instructions=instructions,
            host=model.CmsHost,
            about_id=task.AboutPeopleId,
        )

    body = """
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:760px;margin:0 auto;color:#222;">
        <p>Hi {name},</p>
        <p>You have <strong>{count}</strong> outstanding Student Ministry {task_word} in TouchPoint that {need_word} your attention.</p>
        <h2 style="color:#2c3e50;">Why this matters</h2>
        <p>Each task represents a student or family waiting for someone to follow up. Only one person is assigned to each task at a time, so please complete it or reassign it promptly.</p>
        <h2 style="color:#2c3e50;">Your outstanding tasks</h2>
        {tasks}
        <h2 style="color:#2c3e50;">What to do</h2>
        <ol>
            <li>Review the task details and person information.</li>
            <li>Take the appropriate follow-up action.</li>
            <li>Mark the task complete in TouchPoint when finished.</li>
            <li>Reassign it if someone else should handle it.</li>
        </ol>
        <p><a href="{host}/Task/List" style="display:inline-block;background:#3498db;color:white;padding:10px 18px;text-decoration:none;border-radius:4px;">Open My Task List</a></p>
        <hr style="border:0;border-top:1px solid #ddd;margin:24px 0;">
        <p>Questions? Reply to this email or contact the Student Ministry team.</p>
        <p><strong>RockPointe Student Ministry</strong><br>rockpointechurch.org</p>
    </div>
    """.format(
        name=staffRow.GoesBy,
        count=taskNum,
        task_word="task" if taskNum == 1 else "tasks",
        need_word="needs" if taskNum == 1 else "need",
        tasks=taskBlocks,
        host=model.CmsHost,
    )

    if TEST_MODE:
        print("<h3>PREVIEW ONLY — {} {} (PeopleId {})</h3>".format(
            staffRow.GoesBy,
            staffRow.LastName,
            staffId,
        ))
        print(body)
        previewsRendered += 1
    else:
        recipientQuery = staffId
        model.Email(
            recipientQuery,
            QUEUED_BY,
            FROM_EMAIL,
            FROM_NAME,
            SUBJECT,
            body,
        )
        emailsSent += 1

if TEST_MODE:
    print("<p><strong>TEST MODE:</strong> {} preview(s) rendered; no emails sent.</p>".format(previewsRendered))
else:
    print("<p>SM task reminder emails queued: {}.</p>".format(emailsSent))
