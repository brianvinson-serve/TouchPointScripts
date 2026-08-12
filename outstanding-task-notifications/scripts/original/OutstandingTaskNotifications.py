# OutstandingTaskNotifications.py - Original from TenthPres
# Sends email to users with outstanding tasks
# Uses TaskNote-ToDo.sql for recipient list and OutstandingTasksReminder email template

global model

model.EmailContent("InSqlList( SqlScript='TaskNote-ToDo' ) = 1[True]", 22029, "dbhelp@tenth.org", "Tenth Church Automation", "OutstandingTasksReminder")
