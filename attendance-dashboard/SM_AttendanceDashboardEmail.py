# SM_AttendanceDashboardEmail.py - RockPointe Student Ministry Weekly Attendance Report
#
# PURPOSE:
# - Sends a mobile-friendly report each Monday for the immediately preceding Sunday.
# - Compares headline and campus totals with the Sunday before that.
# - Lists current-Sunday student attendance by campus and leader attendance from
#   the three confirmed 2026-2027 Sunday volunteer/leader organizations.
# - Flags active Sunday attendance organizations with no meeting row for the report date.
#
# DEPLOYMENT: Admin > Advanced > Special Content > Python Scripts
# File name should be: SM_AttendanceDashboardEmail
#
# LIVE RPC EVIDENCE REUSED FROM RPC-3:
# - Build the HTML body in this script and send with model.Email(...).
# - studentministry@rockpointechurch.org / RockPointe Student Ministry sent successfully.
# - No saved draft, email template, or HTML Special Content dependency is required.
#
# PRODUCTION BEHAVIOR:
# - Normal TPC execution and the Monday MorningBatch call send to all confirmed recipients.
# - There is no preview or single-recipient branch in this production artifact.
#
# SCHEDULING (only after a controlled live send succeeds):
#   if model.DayOfWeek == 1:  # Monday
#       model.CallScript("SM_AttendanceDashboardEmail")

from datetime import datetime, timedelta
import re


global model, q

# ============================================================
# CONFIGURATION
# ============================================================

FROM_EMAIL = "studentministry@rockpointechurch.org"
FROM_NAME = "RockPointe Student Ministry"
QUEUED_BY = 23164  # confirmed live sender PeopleId

# Confirmed from the 2026-08-13 RPC staff-directory export. PeopleIds are the
# durable TouchPoint recipient keys; staff emails remain in local gitignored evidence.
RECIPIENT_PEOPLE_IDS = [
    4702,
    284,
    23164,
    1675,
    6523,
    36696,
    659,
    11144,
    28000,
    46965,
    118,
    49921,
]

# Parameterized full dashboard deployed in TouchPoint.
DASHBOARD_SCRIPT_NAME = "sm-attendance-pyreport"

PROGRAM_ID = 1109
SUNDAY_DIVISION_ID = 11
STUDENT_TYPE_ID = 201
VOLUNTEER_TYPE_ID = 207
ORGANIZATION_STATUS_ACTIVE = 30
LEADER_ATTENDANCE_ORG_NAMES = [
    "SM: CC Sunday Morning Volunteers 2026-2027",
    "SM: PS Sunday Morning Volunteers 2026-2027",
    "SM: PS D Group Leaders 2026-2027",
]

# ============================================================
# DATE PARAMETERS
# ============================================================

# This remains correct for manual preview runs on any day: find the most recently
# completed Sunday, never a future scheduled Sunday.
today = datetime.now().date()
days_since_sunday = (today.weekday() + 1) % 7
if days_since_sunday == 0:
    days_since_sunday = 7
report_date = today - timedelta(days=days_since_sunday)
comparison_date = report_date - timedelta(days=7)

report_date_sql = report_date.strftime("%Y-%m-%d")
comparison_date_sql = comparison_date.strftime("%Y-%m-%d")
report_date_label = report_date.strftime("%A, %B %d, %Y").replace(" 0", " ")
subject_date_label = report_date.strftime("%b %d").replace(" 0", " ")

# ============================================================
# DATA QUERY
# ============================================================

ATTENDANCE_SQL = """
SET DATEFIRST 7

DECLARE @ProgramId       INT  = {program_id}
DECLARE @SundayDivId     INT  = {sunday_division_id}
DECLARE @StudentTypeId   INT  = {student_type_id}
DECLARE @VolunteerTypeId INT  = {volunteer_type_id}
DECLARE @ActiveStatusId  INT  = {active_status_id}
DECLARE @ReportDate      DATE = '{report_date}'
DECLARE @ComparisonDate  DATE = '{comparison_date}'
DECLARE @CCPrefix        VARCHAR(10) = 'SM: CC '
DECLARE @PSPrefix        VARCHAR(10) = 'SM: PS '
DECLARE @CCLeaderOrgName VARCHAR(100) = '{cc_leader_org_name}'
DECLARE @PSLeaderOrgName VARCHAR(100) = '{ps_leader_org_name}'
DECLARE @PSDGroupOrgName VARCHAR(100) = '{ps_dgroup_org_name}'

SELECT
    Campus = CASE
        WHEN o.OrganizationName = @CCLeaderOrgName THEN 'Central'
        WHEN o.OrganizationName IN (@PSLeaderOrgName, @PSDGroupOrgName) THEN 'Parker Square'
        WHEN o.OrganizationName LIKE @CCPrefix + '%' THEN 'Central'
        WHEN o.OrganizationName LIKE @PSPrefix + '%' THEN 'Parker Square'
        ELSE 'Other'
    END,
    PersonType = CASE o.OrganizationTypeId
        WHEN @StudentTypeId THEN 'Students'
        WHEN @VolunteerTypeId THEN 'Leaders'
        ELSE 'Other'
    END,
    SchoolLevel = CASE
        WHEN o.OrganizationTypeId = @VolunteerTypeId THEN ''
        WHEN pg.Grade IN ('6th','7th','8th','Middle School Off Hour') THEN 'Middle School'
        WHEN pg.Grade IN ('9th','10th','11th','12th','High School Off Hour') THEN 'High School'
        ELSE 'Other'
    END,
    Grade = CASE WHEN o.OrganizationTypeId = @VolunteerTypeId THEN '' ELSE pg.Grade END,
    GradeOrder = CASE
        WHEN o.OrganizationTypeId = @VolunteerTypeId THEN 0
        ELSE CASE pg.Grade
            WHEN '6th' THEN 1 WHEN '7th' THEN 2 WHEN '8th' THEN 3
            WHEN '9th' THEN 4 WHEN '10th' THEN 5 WHEN '11th' THEN 6 WHEN '12th' THEN 7
            WHEN 'Middle School Off Hour' THEN 8 WHEN 'High School Off Hour' THEN 9
            ELSE 99
        END
    END,
    Gender = pg.Gender,
    MeetingDate = CAST(m.MeetingDate AS DATE),
    OrganizationId = o.OrganizationId,
    OrganizationName = o.OrganizationName,
    Attendance = m.NumPresent
FROM dbo.Organizations o
CROSS APPLY (
    SELECT Remainder = LTRIM(SUBSTRING(o.OrganizationName, 8, 200))
) rm
CROSS APPLY (
    SELECT AfterSunday = CASE
        WHEN rm.Remainder LIKE 'WED %' THEN SUBSTRING(rm.Remainder, 5, 200)
        ELSE rm.Remainder
    END
) sd
CROSS APPLY (
    SELECT
        Grade = CASE
            WHEN RIGHT(RTRIM(sd.AfterSunday), 5) = ' Guys' THEN RTRIM(LEFT(RTRIM(sd.AfterSunday), LEN(RTRIM(sd.AfterSunday)) - 5))
            WHEN RIGHT(RTRIM(sd.AfterSunday), 6) = ' Girls' THEN RTRIM(LEFT(RTRIM(sd.AfterSunday), LEN(RTRIM(sd.AfterSunday)) - 6))
            WHEN RIGHT(RTRIM(sd.AfterSunday), 5) = ' Boys' THEN RTRIM(LEFT(RTRIM(sd.AfterSunday), LEN(RTRIM(sd.AfterSunday)) - 5))
            ELSE RTRIM(sd.AfterSunday)
        END,
        Gender = CASE
            WHEN RIGHT(RTRIM(sd.AfterSunday), 5) = ' Guys' THEN 'Guys'
            WHEN RIGHT(RTRIM(sd.AfterSunday), 6) = ' Girls' THEN 'Girls'
            WHEN RIGHT(RTRIM(sd.AfterSunday), 5) = ' Boys' THEN 'Guys'
            ELSE ''
        END
) pg
LEFT JOIN dbo.Meetings m
    ON m.OrganizationId = o.OrganizationId
   AND CAST(m.MeetingDate AS DATE) IN (@ReportDate, @ComparisonDate)
WHERE o.OrganizationStatusId = @ActiveStatusId
  AND (
      (
          o.OrganizationTypeId = @StudentTypeId
          AND (o.OrganizationName LIKE @CCPrefix + '%' OR o.OrganizationName LIKE @PSPrefix + '%')
      )
      OR (
          o.OrganizationTypeId = @VolunteerTypeId
          AND o.OrganizationName IN (@CCLeaderOrgName, @PSLeaderOrgName, @PSDGroupOrgName)
      )
  )
  -- Intentionally excluded from weekly attendance totals and missing-report warnings:
  -- AND o.OrganizationName NOT LIKE '%Mentor Program%'
  -- AND o.OrganizationName <> 'SM: PS Health and Safety'
  AND o.OrganizationName NOT LIKE '%Mentor Program%'
  AND o.OrganizationName <> 'SM: PS Health and Safety'
  AND EXISTS (
      SELECT 1
      FROM dbo.DivOrg dp
      JOIN dbo.Division d ON d.Id = dp.DivId
      WHERE dp.OrgId = o.OrganizationId AND d.ProgId = @ProgramId
  )
  AND (
      o.OrganizationName IN (@CCLeaderOrgName, @PSLeaderOrgName, @PSDGroupOrgName)
      OR EXISTS (
          SELECT 1
          FROM dbo.DivOrg ds
          WHERE ds.OrgId = o.OrganizationId AND ds.DivId = @SundayDivId
      )
  )
ORDER BY Campus, PersonType, SchoolLevel, GradeOrder, Gender, OrganizationName, MeetingDate
""".format(
    program_id=PROGRAM_ID,
    sunday_division_id=SUNDAY_DIVISION_ID,
    student_type_id=STUDENT_TYPE_ID,
    volunteer_type_id=VOLUNTEER_TYPE_ID,
    active_status_id=ORGANIZATION_STATUS_ACTIVE,
    report_date=report_date_sql,
    comparison_date=comparison_date_sql,
    cc_leader_org_name=LEADER_ATTENDANCE_ORG_NAMES[0].replace("'", "''"),
    ps_leader_org_name=LEADER_ATTENDANCE_ORG_NAMES[1].replace("'", "''"),
    ps_dgroup_org_name=LEADER_ATTENDANCE_ORG_NAMES[2].replace("'", "''"),
)

rows = list(q.QuerySql(ATTENDANCE_SQL))

recipient_people_ids = list(RECIPIENT_PEOPLE_IDS)
if len(set(recipient_people_ids)) != len(recipient_people_ids):
    raise ValueError("RECIPIENT_PEOPLE_IDS contains a duplicate PeopleId")

# ============================================================
# AGGREGATION
# ============================================================


def normalize_date(value):
    if value is None:
        return ""
    value = str(value).split(" ")[0].split("T")[0].strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if match:
        return "{}-{}-{}".format(
            match.group(3),
            match.group(1).zfill(2),
            match.group(2).zfill(2),
        )
    return value


def escape_html(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def as_int(value):
    return int(value or 0)


def row_date(row):
    return normalize_date(row.MeetingDate)


def rows_for(date_string, campus=None, person_type=None, school_level=None):
    selected = []
    for row in rows:
        if row_date(row) != date_string:
            continue
        if campus and str(row.Campus or "") != campus:
            continue
        if person_type and str(row.PersonType or "") != person_type:
            continue
        if school_level and str(row.SchoolLevel or "") != school_level:
            continue
        selected.append(row)
    return selected


def total(selected):
    return sum(as_int(row.Attendance) for row in selected)


def total_for(date_string, campus=None, person_type=None, school_level=None):
    return total(rows_for(date_string, campus, person_type, school_level))


def delta_text(current, previous):
    delta = current - previous
    if delta > 0:
        return "&#9650; {} from last Sunday".format(delta)
    if delta < 0:
        return "&#9660; {} from last Sunday".format(abs(delta))
    return "No change from last Sunday"


def short_org_name(name):
    name = str(name or "")
    if name.startswith("SM: CC ") or name.startswith("SM: PS "):
        return name[7:]
    return name


campuses = ["Central", "Parker Square"]
student_total = total_for(report_date_sql, person_type="Students")
leader_total = total_for(report_date_sql, person_type="Leaders")
grand_total = student_total + leader_total
previous_student_total = total_for(comparison_date_sql, person_type="Students")
previous_leader_total = total_for(comparison_date_sql, person_type="Leaders")

# LEFT JOIN produces one row with MeetingDate NULL for an active Sunday org that has
# neither current nor comparison attendance. An org with comparison attendance but no
# report-date attendance is found by set subtraction below.
expected_orgs = {}
reported_org_ids = set()
for row in rows:
    org_id = as_int(row.OrganizationId)
    expected_orgs[org_id] = (str(row.Campus or ""), str(row.OrganizationName or ""))
    if row_date(row) == report_date_sql:
        reported_org_ids.add(org_id)
missing_orgs = [expected_orgs[org_id] for org_id in expected_orgs if org_id not in reported_org_ids]
missing_orgs.sort(key=lambda item: (item[0], item[1]))

# ============================================================
# EMAIL-SAFE HTML (TABLES + INLINE CSS; NO JAVASCRIPT)
# ============================================================


def summary_card(label, value, comparison):
    return """
    <tr><td valign="top" style="padding:6px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#f1f5f9;border-radius:8px;">
        <tr>
          <td style="padding:14px 12px;font-family:Arial,sans-serif;font-size:16px;line-height:22px;font-weight:bold;color:#334155;">{label}<div style="padding-top:2px;font-size:12px;line-height:18px;font-weight:normal;color:#64748b;">{comparison}</div></td>
          <td align="right" width="90" style="padding:14px 12px;font-family:Arial,sans-serif;font-size:30px;line-height:34px;font-weight:bold;color:#12355b;">{value}</td>
        </tr>
      </table>
    </td></tr>
    """.format(label=label, value=value, comparison=comparison)


def detail_rows(campus, school_level):
    selected = rows_for(report_date_sql, campus, "Students", school_level)
    grouped = {}
    for row in selected:
        grade = str(row.Grade or "Other")
        gender = str(row.Gender or "")
        label = (grade + " " + gender).strip()
        order = as_int(row.GradeOrder)
        key = (order, label)
        grouped[key] = grouped.get(key, 0) + as_int(row.Attendance)

    html_rows = ""
    for key in sorted(grouped):
        html_rows += """
        <tr>
          <td style="padding:9px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;color:#334155;">{label}</td>
          <td align="right" style="padding:9px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#0f172a;">{value}</td>
        </tr>
        """.format(label=escape_html(key[1]), value=grouped[key])

    school_total = total(selected)
    html_rows += """
    <tr>
      <td style="padding:10px 12px;background:#e8f1fb;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#12355b;">{label} total</td>
      <td align="right" style="padding:10px 12px;background:#e8f1fb;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#12355b;">{value}</td>
    </tr>
    """.format(label=school_level, value=school_total)
    return html_rows


def campus_section(campus):
    students = total_for(report_date_sql, campus, "Students")
    previous_total = total_for(comparison_date_sql, campus, "Students")
    return """
    <tr><td style="padding:24px 18px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
        <tr>
          <td style="font-family:Arial,sans-serif;font-size:22px;line-height:28px;font-weight:bold;color:#12355b;">{campus}</td>
          <td align="right" style="font-family:Arial,sans-serif;font-size:22px;line-height:28px;font-weight:bold;color:#12355b;">{students}</td>
        </tr>
        <tr><td colspan="2" style="padding-top:3px;font-family:Arial,sans-serif;font-size:14px;line-height:21px;color:#475569;">{students} students &middot; {delta}</td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:0 18px 8px;">
      <div style="padding:8px 12px;background:#dbeafe;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#12355b;">Middle School</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{middle_rows}</table>
    </td></tr>
    <tr><td style="padding:8px 18px;">
      <div style="padding:8px 12px;background:#dbeafe;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#12355b;">High School</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{high_rows}</table>
    </td></tr>
    """.format(
        campus=campus,
        students=students,
        delta=delta_text(students, previous_total),
        middle_rows=detail_rows(campus, "Middle School"),
        high_rows=detail_rows(campus, "High School"),
    )


def leader_rows():
    grouped = {}
    for row in rows_for(report_date_sql, person_type="Leaders"):
        name = str(row.OrganizationName or "")
        grouped[name] = grouped.get(name, 0) + as_int(row.Attendance)

    html_rows = ""
    for name in LEADER_ATTENDANCE_ORG_NAMES:
        html_rows += """
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;color:#334155;">{name}</td>
          <td align="right" style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#0f172a;">{value}</td>
        </tr>
        """.format(name=escape_html(name), value=grouped.get(name, 0))
    return html_rows


dashboard_url = (
    model.CmsHost
    + "/PyScript/"
    + DASHBOARD_SCRIPT_NAME
    + "?StartDate="
    + report_date_sql
    + "&EndDate="
    + report_date_sql
    + "&IncludeSunday=1&IncludeWednesday=0&CampusFilter=ALL"
)

missing_warning = ""
if missing_orgs:
    missing_items = "".join(
        "<li style=\"margin:5px 0;\">{}</li>".format(escape_html(name))
        for campus, name in missing_orgs
    )
    missing_warning = """
    <tr><td style="padding:18px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#fff7ed;border:1px solid #fdba74;border-radius:8px;">
        <tr><td style="padding:14px 16px;font-family:Arial,sans-serif;font-size:15px;line-height:22px;color:#7c2d12;">
          <strong>Attendance may be incomplete.</strong><br>
          No meeting was reported for {count} active Sunday attendance {group_word}:
          <ul style="margin:8px 0 0;padding-left:20px;">{items}</ul>
        </td></tr>
      </table>
    </td></tr>
    """.format(count=len(missing_orgs), group_word="group" if len(missing_orgs) == 1 else "groups", items=missing_items)

body = """
<div style="margin:0;padding:0;background:#eef2f7;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{students} students &middot; {leaders} leaders &middot; Sunday attendance summary</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#eef2f7;">
    <tr><td align="center" style="padding:16px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;max-width:640px;background:#ffffff;border-radius:10px;overflow:hidden;">
        <tr><td style="padding:22px 18px;background:#12355b;font-family:Arial,sans-serif;color:#ffffff;">
          <div style="font-size:24px;line-height:30px;font-weight:bold;">Student Ministry Attendance</div>
          <div style="padding-top:4px;font-size:15px;line-height:22px;color:#dbeafe;">{date_label}</div>
        </td></tr>
        <tr><td style="padding:12px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            {student_card}
            {leader_card}
            {total_card}
          </table>
        </td></tr>
        {missing_warning}
        {campus_sections}
        <tr><td style="padding:8px 18px 18px;">
          <div style="padding:8px 12px;background:#fef3c7;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#78350f;">Leader Attendance</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            {leader_rows}
          </table>
        </td></tr>
        <tr><td align="center" style="padding:20px 18px 26px;">
          <a href="{dashboard_url}" style="display:inline-block;padding:13px 20px;background:#2563eb;border-radius:6px;font-family:Arial,sans-serif;font-size:16px;line-height:20px;font-weight:bold;color:#ffffff;text-decoration:none;">View interactive attendance report</a>
          <div style="padding-top:16px;font-family:Arial,sans-serif;font-size:12px;line-height:18px;color:#64748b;">Automated Monday report from RockPointe TouchPoint</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</div>
""".format(
    students=student_total,
    leaders=leader_total,
    date_label=report_date_label,
    student_card=summary_card("Students", student_total, delta_text(student_total, previous_student_total)),
    leader_card=summary_card("Leaders", leader_total, delta_text(leader_total, previous_leader_total)),
    total_card=summary_card("Total", grand_total, "Students + leaders"),
    missing_warning=missing_warning,
    campus_sections="".join(campus_section(campus) for campus in campuses),
    leader_rows=leader_rows(),
    dashboard_url=dashboard_url,
)

subject = "SM Attendance - {}: {} students, {} leaders".format(
    subject_date_label,
    student_total,
    leader_total,
)

# ============================================================
# SEND
# ============================================================

recipient_query = "peopleids='{}'".format(
    ",".join(str(people_id) for people_id in recipient_people_ids)
)
model.Email(
    recipient_query,
    QUEUED_BY,
    FROM_EMAIL,
    FROM_NAME,
    subject,
    body,
)
print("<p>Weekly SM attendance report queued for {} recipient(s).</p>".format(len(recipient_people_ids)))
