# SM_OutstandingTaskNotifications.py - RockPointe Student Ministry Task Notifications
# Sends weekly email reminders to SM staff about outstanding tasks
#
# DEPLOYMENT: Admin > Advanced > Special Content > Python Scripts
# File name should be: SM_OutstandingTaskNotifications
#
# PREREQUISITES:
# 1. SM_OutstandingTasksList.py must be deployed and confirmed working
#
# SCHEDULING: Add to MorningBatch after confirming this script works:
#   if model.DayOfWeek == 2:  # Tuesday mornings
#       model.CallScript('SM_OutstandingTaskNotifications')

global model, q

TEST_MODE = False  # True = print to screen only; False = send emails
TEST_STAFF = [
    28000
]  # Abbie - swap in your own PeopleId if you want to receive the test

FROM_EMAIL = "studentministry@rockpointechurch.org"
FROM_NAME = "RockPointe Student Ministry"
SUBJECT = "Student Ministry - Your Outstanding Tasks"
HIGHLIGHT_DAYS_OLD = 7
# QueuedBy: PeopleId whose record the email is queued under - use Max McCalley or SM admin account
QUEUED_BY = 23164  # Joseph McCalley

# Hardcoded SM staff PeopleIds - update when staff changes (see ../../DB_REFERENCE.md)
SM_STAFF = [46965, 659, 284, 23164, 1675, 40594, 36696, 28000, 19570, 118]

taskSql = """
SELECT
    tn.Instructions,
    tn.CreatedDate,
    tn.OwnerId,
    COALESCE(abt.NickName, abt.FirstName) AS GoesBy,
    abt.LastName,
    abt.EmailAddress AS AboutEmail,
    abt.CellPhone,
    abt.PeopleId AS AboutPeopleId,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld
FROM TaskNote tn
JOIN People abt ON tn.AboutPersonId = abt.PeopleId
WHERE (
    (tn.OwnerId = {0} AND tn.AssigneeId IS NULL) OR
    (tn.AssigneeId = {0})
)
AND tn.StatusId IN (2, 3)
AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
ORDER BY tn.CreatedDate ASC
"""

staffSql = """
SELECT
    COALESCE(NickName, FirstName) AS GoesBy,
    LastName,
    EmailAddress
FROM People
WHERE PeopleId = {0}
"""

emailsSent = 0

staffList = TEST_STAFF if TEST_MODE else SM_STAFF

for staffId in staffList:
    tasks = list(q.QuerySql(taskSql.format(staffId)))
    if not tasks:
        continue

    staffRow = q.QuerySqlTop1(staffSql.format(staffId))
    if not staffRow:
        continue

    recipientQuery = "PeopleId = {}".format(staffId)

    taskBlocks = ""
    taskNum = 0
    for task in tasks:
        taskNum += 1
        daysOld = task.DaysOld if task.DaysOld else 0
        instr = (
            model.Markdown(task.Instructions) if task.Instructions else "(no details)"
        )

        if daysOld > HIGHLIGHT_DAYS_OLD:
            borderColor = "#e74c3c"
            badge = '<span style="background:#e74c3c;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">OVERDUE - {} days</span>'.format(
                daysOld
            )
        else:
            borderColor = "#3498db"
            badge = '<span style="background:#3498db;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{} days old</span>'.format(
                daysOld
            )

        taskBlocks += """
        <div style="border:2px solid {7};margin:1.5em 0;padding:1.5em;border-radius:8px;background:#f9f9f9;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1em;">
                <strong style="font-size:1.1em;">Task #{8}</strong>
                {9}
            </div>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:4px 8px;font-weight:bold;width:100px;">About:</td><td style="padding:4px 8px;">{0}</td></tr>
                <tr><td style="padding:4px 8px;font-weight:bold;">Email:</td><td style="padding:4px 8px;"><a href="mailto:{1}">{1}</a></td></tr>
                <tr><td style="padding:4px 8px;font-weight:bold;">Phone:</td><td style="padding:4px 8px;"><a href="tel:{2}">{2}</a></td></tr>
                <tr><td style="padding:4px 8px;font-weight:bold;">Created:</td><td style="padding:4px 8px;">{5}</td></tr>
            </table>
            <div style="background:white;padding:1em;margin:1em 0;border-left:4px solid {7};">
                <strong>Task Details:</strong><br/>{6}
            </div>
            <div style="margin-top:1em;">
                <a href="{3}/Person2/{4}#tab-touchpoints" style="background:#27ae60;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;margin-right:8px;">View Profile</a>
                <a href="{3}/Task/List" style="background:#3498db;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;">My Task List</a>
            </div>
        </div>""".format(
            task.GoesBy + " " + task.LastName,
            task.AboutEmail,
            model.FmtPhone(task.CellPhone),
            model.CmsHost,
            task.AboutPeopleId,
            task.CreatedDate,
            instr,
            borderColor,
            taskNum,
            badge,
        )

    body = """
    <div style="font-family:sans-serif;max-width:700px;margin:0 auto;">
        <h2 style="color:#2c3e50;">Hi {name} - you have {count} outstanding {word} in Student Ministry</h2>
        {tasks}
        <p style="color:#7f8c8d;font-size:12px;margin-top:2em;">
            This is an automated reminder sent every Tuesday morning.
            Go to <a href="{host}/Task/List">My Task List</a> to manage all your tasks.
        </p>
    </div>""".format(
        name=staffRow.GoesBy,
        count=taskNum,
        word="task" if taskNum == 1 else "tasks",
        tasks=taskBlocks,
        host=model.CmsHost,
    )

    if TEST_MODE:
        print(
            "<h3>--- PREVIEW for {} {} (PeopleId {}) ---</h3>".format(
                staffRow.GoesBy, staffRow.LastName, staffId
            )
        )
        print(body)
    else:
        model.Email(recipientQuery, QUEUED_BY, FROM_EMAIL, FROM_NAME, SUBJECT, body)
        emailsSent += 1

if TEST_MODE:
    print("<p><em>TEST MODE - no emails sent. Set TEST_MODE = False to send.</em></p>")
else:
    print("SM task reminder emails sent: {}".format(emailsSent))
