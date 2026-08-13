# SM_OutstandingTaskNotifications.py - RockPointe Student Ministry Task Notifications
# Sends weekly email reminders to SM staff about outstanding tasks
#
# DEPLOYMENT: Admin > Advanced > Special Content > Python Scripts
# File name should be: SM_OutstandingTaskNotifications
#
# PREREQUISITES:
# 1. SM_TaskNote-ToDo.sql must be deployed
# 2. SM_OutstandingTasksList.py must be deployed
# 3. Email template SM_OutstandingTasksReminder must exist (Admin > Emails > Saved Drafts)
#
# CONFIGURATION REQUIRED:
# - Update the sender email address (FROM_EMAIL)
# - Update the sender name (FROM_NAME)
# - Confirm the PeopleId used to queue the email (QUEUED_BY)
#
# SCHEDULING: Add to MorningBatch or ScheduledTasks script:
#   if model.DayOfWeek == 2:  # Tuesday mornings
#       model.CallScript('SM_OutstandingTaskNotifications')

global model

# ============================================================
# CONFIGURATION - UPDATE THESE VALUES FOR ROCKPOINTE
# ============================================================

FROM_EMAIL = "studentministry@rockpointechurch.org"  # Update with actual SM email
FROM_NAME = "RockPointe Student Ministry"
EMAIL_TEMPLATE_NAME = "SM_OutstandingTasksReminder"  # Name of saved email template
SQL_SCRIPT_NAME = "SM_TaskNote-ToDo"  # SQL script for recipient list

# PeopleId whose record queues the email. Confirm before deployment.
QUEUED_BY = 23164  # Joseph McCalley

# ============================================================
# EMAIL SENDING LOGIC
# ============================================================

# Build the search query using the SQL script for recipients
recipientSearch = "InSqlList( SqlScript='{}' ) = 1[True]".format(SQL_SCRIPT_NAME)

# Send the email
# Parameters: (search_query, queued_by_people_id, from_email, from_name, template_name)
model.EmailContent(
    recipientSearch,
    QUEUED_BY,
    FROM_EMAIL,
    FROM_NAME,
    EMAIL_TEMPLATE_NAME
)

print("Student Ministry task reminder emails sent successfully!")
