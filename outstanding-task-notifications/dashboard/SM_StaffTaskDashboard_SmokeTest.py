# SM_StaffTaskDashboard_SmokeTest.py
# Deploy as a temporary TouchPoint Python Script to isolate blank-screen failures.
# Name: SM_StaffTaskDashboard_SmokeTest
#
# If this script blanks, the issue is not the dashboard SQL. It is the Python
# script deployment/runtime surface.
# If Section 2 prints but Section 3 blanks/errors, the issue is q.QuerySql or SQL.

global model, q, Data

print("<h1>SM Staff Task Dashboard Smoke Test</h1>")
print("<p>Section 1: Python print works.</p>")

try:
    print("<p>Section 2: model.CmsHost = {}</p>".format(model.CmsHost))
except Exception as e:
    print("<p>Section 2 error reading model.CmsHost: {}</p>".format(e))

try:
    rows = list(q.QuerySql("SELECT TOP 1 GETDATE() AS CurrentDate"))
    print("<p>Section 3: q.QuerySql works. Rows returned: {}</p>".format(len(rows)))
    if rows:
        print("<p>CurrentDate: {}</p>".format(rows[0].CurrentDate))
except Exception as e:
    print("<p>Section 3 error running q.QuerySql: {}</p>".format(e))

try:
    rows = list(q.QuerySql("SELECT TOP 1 OwnerId, AssigneeId, StatusId, CreatedDate FROM TaskNote ORDER BY CreatedDate DESC"))
    print("<p>Section 4: TaskNote query works. Rows returned: {}</p>".format(len(rows)))
    if rows:
        row = rows[0]
        print("<ul>")
        print("<li>OwnerId: {}</li>".format(row.OwnerId))
        print("<li>AssigneeId: {}</li>".format(row.AssigneeId))
        print("<li>StatusId: {}</li>".format(row.StatusId))
        print("<li>CreatedDate: {}</li>".format(row.CreatedDate))
        print("</ul>")
except Exception as e:
    print("<p>Section 4 error querying TaskNote: {}</p>".format(e))

print("<p>Smoke test complete.</p>")
