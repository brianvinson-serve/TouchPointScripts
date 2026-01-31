# SM_OutstandingTasksList.py - RockPointe Student Ministry Adaptation
# Generates a list of outstanding tasks for Student Ministry staff
# Designed for Max McCalley's request for SM incomplete task notifications
#
# DEPLOYMENT: Admin > Advanced > Special Content > Python Scripts
# File name should be: SM_OutstandingTasksList
#
# MODIFICATIONS FROM ORIGINAL:
# 1. Added ministry-specific filtering capability
# 2. Enhanced styling for RockPointe branding
# 3. Added task age/urgency indicators

global model, Data, q

# Configuration - adjust these for different ministries
MINISTRY_NAME = "Student Ministry"
HIGHLIGHT_DAYS_OLD = 7  # Tasks older than this get highlighted

if Data.Person:
    peopleId = Data.Person.PeopleId
elif Data.pid:
    peopleId = Data.pid
else:
    peopleId = model.UserPeopleId

# SQL to fetch outstanding tasks
# StatusId values: 1=Complete, 2=Pending, 3=Active, 4=Declined, 5=Archived, 6=Cancelled
taskSql = """
SELECT
    tn.*,
    COALESCE(abt.NickName, abt.FirstName) AS GoesBy,
    abt.LastName,
    abt.EmailAddress,
    abt.CellPhone,
    abt.PeopleId AS AboutPeopleId,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld
FROM TaskNote tn
JOIN People abt ON tn.AboutPersonId = abt.PeopleId
WHERE (
    (tn.OwnerId = {0} AND tn.AssigneeId IS NULL) OR
    (tn.AssigneeId = {0})
)
AND tn.StatusID NOT IN (1, 5, 6)  -- Not Complete, Archived, or Cancelled
ORDER BY tn.CreatedDate ASC
""".format(peopleId)

taskCount = 0
for task in q.QuerySql(taskSql, peopleId, None):
    taskCount += 1
    instr = model.Markdown(task.Instructions)
    daysOld = task.DaysOld if hasattr(task, 'DaysOld') else 0

    # Determine urgency styling
    if daysOld > HIGHLIGHT_DAYS_OLD:
        borderColor = "#e74c3c"  # Red for overdue
        urgencyBadge = '<span style="background:#e74c3c;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">OVERDUE - {} days</span>'.format(daysOld)
    else:
        borderColor = "#3498db"  # Blue for normal
        urgencyBadge = '<span style="background:#3498db;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{} days old</span>'.format(daysOld)

    print("""
    <div style="border: 2px solid {7}; margin: 1.5em 0; padding: 1.5em; border-radius: 8px; background: #f9f9f9;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1em;">
            <strong style="font-size: 1.1em;">Task #{8}</strong>
            {9}
        </div>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 4px 8px; font-weight: bold; width: 100px;">About:</td><td style="padding: 4px 8px;">{0}</td></tr>
            <tr><td style="padding: 4px 8px; font-weight: bold;">Email:</td><td style="padding: 4px 8px;"><a href="mailto:{1}">{1}</a></td></tr>
            <tr><td style="padding: 4px 8px; font-weight: bold;">Phone:</td><td style="padding: 4px 8px;"><a href="tel:{2}">{2}</a></td></tr>
            <tr><td style="padding: 4px 8px; font-weight: bold;">Created:</td><td style="padding: 4px 8px;">{5}</td></tr>
        </table>

        <div style="background: white; padding: 1em; margin: 1em 0; border-left: 4px solid {7};">
            <strong>Task Details:</strong><br/>
            {6}
        </div>

        <div style="margin-top: 1em;">
            <a href="{3}/Person2/{4}#tab-touchpoints" style="background: #27ae60; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-right: 8px;">View Profile</a>
            <a href="{3}/Task/List" style="background: #3498db; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;">My Task List</a>
        </div>
    </div>
    """.format(
        task.GoesBy + " " + task.LastName,  # 0 - Full name
        task.EmailAddress,                    # 1 - Email
        model.FmtPhone(task.CellPhone),       # 2 - Phone
        model.CmsHost,                        # 3 - TouchPoint URL
        task.AboutPeopleId,                   # 4 - PeopleId for profile link
        task.CreatedDate,                     # 5 - Created date
        instr,                                # 6 - Task instructions
        borderColor,                          # 7 - Border color based on urgency
        taskCount,                            # 8 - Task number
        urgencyBadge                          # 9 - Urgency badge HTML
    ))

if taskCount == 0:
    print('<div style="text-align: center; padding: 2em; color: #27ae60;"><strong>No outstanding tasks found. Great job!</strong></div>')
