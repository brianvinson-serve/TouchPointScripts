import json
import re
from datetime import datetime, timedelta

# ============================================================
# Parameters from URL  (?StartDate=2026-01-01&EndDate=2026-07-08 etc.)
# ============================================================
data = model.Data

today = datetime.now().date()
default_start = str(today - timedelta(days=90))
default_end = str(today)

def safe_date(s, fallback):
    s = (s or "").strip()
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else fallback

raw_campus = (getattr(data, "CampusFilter", "") or "").strip().upper()

start_date = safe_date(getattr(data, "StartDate", ""), default_start)
end_date = safe_date(getattr(data, "EndDate", ""), default_end)
campus_filter = (
    raw_campus if raw_campus in ("ALL", "CENTRAL", "PARKERSQUARE") else "ALL"
)
inc_sunday = 0 if str(getattr(data, "IncludeSunday", "1") or "1").strip() == "0" else 1
inc_wednesday = (
    0 if str(getattr(data, "IncludeWednesday", "1") or "1").strip() == "0" else 1
)

# ============================================================
# DATE PARAMETERS
# ============================================================

# This logic finds the most recently completed Sunday (for non-automated preview runs)
today = datetime.now().date()
days_since_sunday = (today.weekday() + 1) % 7
if days_since_sunday == 0:
    days_since_sunday = 7
report_date = today - timedelta(days=days_since_sunday)
comparison_date = report_date - timedelta(days=7)

report_date_sql = report_date.strftime("%Y-%m-%d")
comparison_date_sql = comparison_date.strftime("%Y-%m-%d")

# ============================================================
# SQL
# ============================================================

ATTENDANCE_SQL = """
SET DATEFIRST 7

DECLARE @ProgramId        INT          = 1109
DECLARE @SundayDivId      INT          = 11
DECLARE @WednesdayDivId   INT          = 42
DECLARE @StudentTypeId    INT          = 201
DECLARE @VolunteerTypeId  INT          = 207
DECLARE @WedGradeTypeId   INT          = 205
DECLARE @StartDate        DATE         = '{start}'
DECLARE @EndDate          DATE         = '{end}'
DECLARE @IncludeSunday    BIT          = {sun}
DECLARE @IncludeWednesday BIT          = {wed}
DECLARE @CampusFilter     VARCHAR(20)  = '{campus}'
DECLARE @CCPrefix         VARCHAR(10)  = 'SM: CC '
DECLARE @PSPrefix         VARCHAR(10)  = 'SM: PS '

-- Get all students attending Sunday school (and their leaders)
WITH StudentAttendance AS (
    SELECT 
        a.PersonId,
        p.NickName AS FirstName,
        p.LastName,
        p.Email,
        o.Name AS OrganizationName,
        o.Id AS OrganizationId,
        a.EventServiceDate
    FROM Attendance a
    JOIN Person p ON a.PersonId = p.Id
    JOIN OrganizationMember om ON om.PersonId = a.PersonId AND om.OrganizationId = o.Id
    JOIN Organization o ON a.OrganizationId = o.Id
    WHERE (
        -- Filter by the program that contains the student ministry (1109)
        o.ParentOrganizationId IN (
            SELECT Id FROM Organization 
            WHERE ParentOrganizationId IN (
                SELECT Id FROM Organization 
                WHERE Id = @ProgramId AND ISNULL(ChildrenCount, 0) > 0
            )
        )
        OR o.Id = @ProgramId
    )
    -- Only students in the student ministry organization  
    AND o.OrganizationTypeId = @StudentTypeId
    AND a.EventServiceDate BETWEEN @StartDate AND @EndDate
    AND (
        (@IncludeSunday = 1 AND DATEPART(WEEKDAY, a.EventServiceDate) = 1)
        OR (@IncludeWednesday = 1 AND DATEPART(WEEKDAY, a.EventServiceDate) = 4)
    )
    AND (ISNULL(@CampusFilter,'ALL') = 'ALL' OR o.CampusId IN (
        SELECT Id FROM Campus WHERE Name = @CampusFilter
    ))
),

-- Get volunteers for each Sunday school group 
VolunteerAttendance AS (
    SELECT 
        a.PersonId,
        p.NickName AS FirstName,
        p.LastName,
        p.Email,
        o.Name AS OrganizationName,
        o.Id AS OrganizationId,
        a.EventServiceDate,
        om.GroupMemberStatusId AS GroupStatusId
    FROM Attendance a
    JOIN Person p ON a.PersonId = p.Id
    JOIN OrganizationMember om ON om.PersonId = a.PersonId AND om.OrganizationId = o.Id
    JOIN Organization o ON a.OrganizationId = o.Id
    WHERE (
        -- Filter by the program that contains the student ministry (1109)
        o.ParentOrganizationId IN (
            SELECT Id FROM Organization 
            WHERE ParentOrganizationId IN (
                SELECT Id FROM Organization 
                WHERE Id = @ProgramId AND ISNULL(ChildrenCount, 0) > 0
            )
        )
        OR o.Id = @ProgramId
    )    
    -- Only volunteers in the student ministry organization  
    AND o.OrganizationTypeId = @VolunteerTypeId
    AND a.EventServiceDate BETWEEN @StartDate AND @EndDate
    AND (
        (@IncludeSunday = 1 AND DATEPART(WEEKDAY, a.EventServiceDate) = 1)
        OR (@IncludeWednesday = 1 AND DATEPART(WEEKDAY, a.EventServiceDate) = 4)
    )
    AND (ISNULL(@CampusFilter,'ALL') = 'ALL' OR o.CampusId IN (
        SELECT Id FROM Campus WHERE Name = @CampusFilter
    ))
)

-- Combine students and volunteers with their group names
SELECT 
    'Student' AS PersonType,
    sa.FirstName,
    sa.LastName,
    sa.Email,
    sa.OrganizationName,
    sa.EventServiceDate,
    sa.PersonId
FROM StudentAttendance sa

UNION ALL

SELECT 
    'Volunteer' AS PersonType,
    va.FirstName,
    va.LastName,
    va.Email,
    va.OrganizationName,
    va.EventServiceDate,
    va.PersonId
FROM VolunteerAttendance va

ORDER BY OrganizationName, LastName, FirstName
"""

# ============================================================
# QUERY RESULT
# ============================================================

sql = ATTENDANCE_SQL.format(
    start=report_date_sql,
    end=end_date,
    sun=inc_sunday,
    wed=inc_wednesday,
    campus=campus_filter,
)

rows = list(q.QuerySql(sql))

# ============================================================
# RECIPIENTS
# ============================================================

# These are the recipients from the issue description 
RECIPIENT_PEOPLE_IDS = [
    157029, # Christy McCallum  
    234682, # Jen Schmitz
    204652, # Angela Cheshire
    201766, # Leah McBain
    203119, # Christi Victor
    167522, # Courtney Rehbehn
    173895, # Margo Baisley
    189248, # Treeka Andries
    154122, # Darlene Everest
    141786, # Kellie Lampe
]

# ============================================================
# AGGREGATION
# ============================================================

def normalize_date(value):
    if value is None:
        return ""
    value = str(value).split(" ")[0].split("T")[0].strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    match = re.match(r"(^(\d{1,2})/(\d{1,2})/(\d{4}))", value)
    if match:
        return f"{match.group(4)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return value

def aggregate_attendance(rows, report_date):
    # Get attendance by Organization
    org_totals = {}
    person_records = {}  # To track unique people per organization
    
    for row in rows:
        org_name = str(row.OrganizationName or "")
        person_id = getattr(row, "PersonId", None)
        person_type = str(getattr(row, "PersonType", "") or "").lower() 
        
        if org_name not in org_totals:
            org_totals[org_name] = {"Students": 0, "Volunteers": 0, "Total": 0}
            
        # Count only unique people (prevent double counting)  
        if person_id not in person_records.get(org_name, []):
            person_records.setdefault(org_name, []).append(person_id)
            org_totals[org_name]["Total"] += 1
            
            # Add to proper type
            if person_type == "student":
                org_totals[org_name]["Students"] += 1
            elif person_type == "volunteer":
                org_totals[org_name]["Volunteers"] += 1
    
    return org_totals

def escape_html(text):
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# Aggregate the data
org_totals = aggregate_attendance(rows, report_date_sql)

# ============================================================
# EMAIL CONTENT
# ============================================================

email_body_html = """<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
    th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
    th { background-color: #f2f2f2; }
    .date-header { font-size: 18px; font-weight: bold; margin-top: 20px; color: #333; }
    .summary-row { font-weight: bold; background-color: #f9f9f9; }
  </style>
</head>

<body>
  <h2>Children's Ministry Attendance Report - """ + report_date_sql + """</h2>

  <p>Weekly attendance summary for Children's Ministry volunteer staff.</p>

  <div class="date-header">Report Period: """ + report_date_sql + """ to """ + comparison_date_sql + """</div>

  <table>
    <thead>
      <tr>
        <th>Group</th>
        <th>Students</th>
        <th>Volunteers</th>
        <th>Total</th>
      </tr>
    </thead>
    <tbody>"""

# Add rows for each organization
for org_name in sorted(org_totals.keys()):
    total = org_totals[org_name]["Total"]
    students = org_totals[org_name]["Students"] 
    volunteers = org_totals[org_name]["Volunteers"]
    email_body_html += """
      <tr>
        <td>""" + escape_html(org_name) + """</td>
        <td>""" + str(students) + """</td>
        <td>""" + str(volunteers) + """</td>
        <td>""" + str(total) + """</td>
      </tr>"""

email_body_html += """
    </tbody>
  </table>

  <p>Thank you for your service!</p>
</body>
</html>"""

# ============================================================
# SEND EMAIL
# ============================================================

# Send email to the specified recipients with the attendance report data
for person_id in RECIPIENT_PEOPLE_IDS:
    # We're using a simple mailer script that emails based on person ID
    e = model.Email
    e.ToPersonId = person_id
    e.Subject = "Children's Ministry Attendance Report - " + report_date_sql
    e.Body = email_body_html
    if model.SendEmail(e):
        print("Email sent to recipient #" + str(person_id))
    else:
        print("Failed to send email to recipient #" + str(person_id))