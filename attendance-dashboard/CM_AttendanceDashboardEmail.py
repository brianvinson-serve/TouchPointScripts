# CM_AttendanceDashboardEmail.py - RockPointe Children's Ministry Weekly Attendance Report
#
# PURPOSE:
# - Sends a mobile-friendly report each Monday for the immediately preceding Sunday.
# - Compares headline and campus totals with the Sunday before that.
# - Lists current-Sunday kid attendance by campus and bucket (Preschool,
#   Elementary, Special Needs) and volunteer attendance by campus.
# - Flags active Sunday reporting organizations with no meeting row for the
#   report date.
#
# MODELED ON: SM_AttendanceDashboardEmail.py (Student Ministry). Same shape,
# same email-safe HTML approach (model.Email, no saved draft / template
# dependency), same missing-meeting warning pattern.
#
# SCOPE CONFIRMED LIVE 2026-08-17:
# - Program 1111 = Children's Ministry (CM)
# - Division 81 = RP CC Children (reporting, Program 1137, Central)
# - Division 82 = RP PS Children (reporting, Program 1138, Parker Square)
# - Type 201 = Kids classroom, Type 207 = Volunteers
# - "CM: All Special Needs Volunteers" is a stale rollup org (zero attendance
#   every week in a 4-week live pull) and is explicitly excluded by name.
# - "CM: Embrace Families" is a small group with NO Sunday-AM reporting
#   division link (confirmed NO MEETING every week) and is correctly excluded
#   by the reporting-division EXISTS filter -- do not add it back without a
#   real Sunday meeting schedule behind it.
#
# RECIPIENTS -- STATUS AS OF 2026-08-17:
# Marlene's request came in copying Angela Cheshire (Children's Ministry
# Administrator, PeopleId 2879) and Jennifer Schmitz (NextGen Administrator,
# PeopleId 6523). Marlene asked THEM to confirm the full involvement list
# before this goes into regular production rotation. Until that confirmation
# comes back, RECIPIENT_PEOPLE_IDS below intentionally contains only Angela,
# Jennifer, and Brian's own PeopleId for a controlled first live test --
# do NOT expand this list or schedule MorningBatch calls until Angela and
# Jennifer have signed off on the involvement scope above.
#
# DEPLOYMENT: Admin > Advanced > Special Content > Python Scripts
# File name should be: CM_AttendanceDashboardEmail
#
# SCHEDULING (only after a controlled live send succeeds AND Angela/Jennifer
# have confirmed scope):
#   if model.DayOfWeek == 1:  # Monday
#       model.CallScript("CM_AttendanceDashboardEmail")

from datetime import datetime, timedelta
import re


global model, q

# ============================================================
# CONFIGURATION
# ============================================================

FROM_EMAIL = "childrensministry@rockpointechurch.org"  # TODO confirm exact CM send-as address before first live send
FROM_NAME = "RockPointe Children's Ministry"
QUEUED_BY = 23164  # confirmed live sender PeopleId (reused from SM scripts)

# TODO: replace with the confirmed full list once Angela and Jennifer sign
# off on involvement scope (see header note above). Until then this is a
# controlled first-test list only.
RECIPIENT_PEOPLE_IDS = [
    2879,  # Angela Cheshire -- Children's Ministry Administrator
    6523,  # Jennifer Schmitz -- NextGen Administrator
]

PROGRAM_ID = 1111
CC_REPORTING_DIVISION_ID = 81
PS_REPORTING_DIVISION_ID = 82
KIDS_TYPE_ID = 201
VOLUNTEER_TYPE_ID = 207
ORGANIZATION_STATUS_ACTIVE = 30
EXCLUDED_ORG_NAME = "CM: All Special Needs Volunteers"

# Parameterized full dashboard deployed in TouchPoint.
DASHBOARD_SCRIPT_NAME = "cm-attendance-pyreport"

# ============================================================
# DATE PARAMETERS
# ============================================================

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

DECLARE @ProgramId        INT  = {program_id}
DECLARE @CCReportingDivId INT  = {cc_reporting_division_id}
DECLARE @PSReportingDivId INT  = {ps_reporting_division_id}
DECLARE @KidsTypeId       INT  = {kids_type_id}
DECLARE @VolunteerTypeId  INT  = {volunteer_type_id}
DECLARE @ActiveStatusId   INT  = {active_status_id}
DECLARE @ReportDate       DATE = '{report_date}'
DECLARE @ComparisonDate   DATE = '{comparison_date}'
DECLARE @CCPrefix         VARCHAR(10)  = 'CM: CC '
DECLARE @PSPrefix         VARCHAR(10)  = 'CM: PS '
DECLARE @ExcludedOrgName  VARCHAR(100) = '{excluded_org_name}'

SELECT
    Campus = CASE
        WHEN o.OrganizationName LIKE @CCPrefix + '%' THEN 'Central'
        WHEN o.OrganizationName LIKE @PSPrefix + '%' THEN 'Parker Square'
        ELSE 'Other'
    END,
    PersonType = CASE o.OrganizationTypeId
        WHEN @KidsTypeId      THEN 'Kids'
        WHEN @VolunteerTypeId THEN 'Volunteers'
        ELSE 'Other'
    END,
    MeetingDate = CAST(m.MeetingDate AS DATE),
    OrganizationId = o.OrganizationId,
    OrganizationName = o.OrganizationName,
    Attendance = m.NumPresent
FROM dbo.Organizations o
LEFT JOIN dbo.Meetings m
    ON m.OrganizationId = o.OrganizationId
   AND CAST(m.MeetingDate AS DATE) IN (@ReportDate, @ComparisonDate)
WHERE o.OrganizationStatusId = @ActiveStatusId
  AND o.OrganizationName <> @ExcludedOrgName
  AND (o.OrganizationName LIKE @CCPrefix + '%' OR o.OrganizationName LIKE @PSPrefix + '%')
  AND o.OrganizationTypeId IN (@KidsTypeId, @VolunteerTypeId)
  AND EXISTS (
      SELECT 1
      FROM dbo.DivOrg dp
      JOIN dbo.Division d ON d.Id = dp.DivId
      WHERE dp.OrgId = o.OrganizationId AND d.ProgId = @ProgramId
  )
  AND EXISTS (
      SELECT 1
      FROM dbo.DivOrg dr
      WHERE dr.OrgId = o.OrganizationId
        AND dr.DivId IN (@CCReportingDivId, @PSReportingDivId)
  )
ORDER BY Campus, PersonType, OrganizationName, MeetingDate
""".format(
    program_id=PROGRAM_ID,
    cc_reporting_division_id=CC_REPORTING_DIVISION_ID,
    ps_reporting_division_id=PS_REPORTING_DIVISION_ID,
    kids_type_id=KIDS_TYPE_ID,
    volunteer_type_id=VOLUNTEER_TYPE_ID,
    active_status_id=ORGANIZATION_STATUS_ACTIVE,
    report_date=report_date_sql,
    comparison_date=comparison_date_sql,
    excluded_org_name=EXCLUDED_ORG_NAME.replace("'", "''"),
)

rows = list(q.QuerySql(ATTENDANCE_SQL))

recipient_people_ids = list(RECIPIENT_PEOPLE_IDS)
if len(set(recipient_people_ids)) != len(recipient_people_ids):
    raise ValueError("RECIPIENT_PEOPLE_IDS contains a duplicate PeopleId")

# ============================================================
# AGE-GROUP / BUCKET CLASSIFICATION
# Confirmed against the full live 2026-08-17 involvement export (125 active
# CM orgs in reporting scope). Match order matters: Special Needs is checked
# before Preschool/Elementary.
# ============================================================

_PRESCHOOL_KEYWORDS = (
    "infant",
    "crawler",
    "walking",
    "months",
    "year",
    "toddler",
    "prek",
    "pre-k",
    "kindergarten",
    "nursery",
)


def classify_age_group(name):
    lname = name.lower()
    if "special needs" in lname:
        return "Special Needs"
    if any(k in lname for k in _PRESCHOOL_KEYWORDS):
        return "Preschool"
    if "grade" in lname:
        return "Elementary"
    return "Other"


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


def rows_for(date_string, campus=None, person_type=None, bucket=None):
    selected = []
    for row in rows:
        if row_date(row) != date_string:
            continue
        if campus and str(row.Campus or "") != campus:
            continue
        if person_type and str(row.PersonType or "") != person_type:
            continue
        if bucket and classify_age_group(str(row.OrganizationName or "")) != bucket:
            continue
        selected.append(row)
    return selected


def total(selected):
    return sum(as_int(row.Attendance) for row in selected)


def total_for(date_string, campus=None, person_type=None, bucket=None):
    return total(rows_for(date_string, campus, person_type, bucket))


def delta_text(current, previous):
    delta = current - previous
    if delta > 0:
        return "&#9650; {} from last Sunday".format(delta)
    if delta < 0:
        return "&#9660; {} from last Sunday".format(abs(delta))
    return "No change from last Sunday"


def short_org_name(name):
    name = str(name or "")
    if name.startswith("CM: CC ") or name.startswith("CM: PS "):
        return name[7:]
    return name


campuses = ["Central", "Parker Square"]
kids_total = total_for(report_date_sql, person_type="Kids")
leader_total = total_for(report_date_sql, person_type="Volunteers")
grand_total = kids_total + leader_total
previous_kids_total = total_for(comparison_date_sql, person_type="Kids")
previous_leader_total = total_for(comparison_date_sql, person_type="Volunteers")

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


def detail_rows(campus, bucket):
    selected = rows_for(report_date_sql, campus, "Kids", bucket)
    grouped = {}
    for row in selected:
        name = short_org_name(str(row.OrganizationName or ""))
        grouped[name] = grouped.get(name, 0) + as_int(row.Attendance)

    html_rows = ""
    for name in sorted(grouped):
        html_rows += """
        <tr>
          <td style="padding:9px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;color:#334155;">{label}</td>
          <td align="right" style="padding:9px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#0f172a;">{value}</td>
        </tr>
        """.format(label=escape_html(name), value=grouped[name])

    bucket_total = total(selected)
    html_rows += """
    <tr>
      <td style="padding:10px 12px;background:#e8f1fb;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#12355b;">{label} total</td>
      <td align="right" style="padding:10px 12px;background:#e8f1fb;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#12355b;">{value}</td>
    </tr>
    """.format(label=bucket, value=bucket_total)
    return html_rows


def campus_section(campus):
    kids = total_for(report_date_sql, campus, "Kids")
    previous_total = total_for(comparison_date_sql, campus, "Kids")
    return """
    <tr><td style="padding:24px 18px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
        <tr>
          <td style="font-family:Arial,sans-serif;font-size:22px;line-height:28px;font-weight:bold;color:#12355b;">{campus}</td>
          <td align="right" style="font-family:Arial,sans-serif;font-size:22px;line-height:28px;font-weight:bold;color:#12355b;">{kids}</td>
        </tr>
        <tr><td colspan="2" style="padding-top:3px;font-family:Arial,sans-serif;font-size:14px;line-height:21px;color:#475569;">{kids} kids &middot; {delta}</td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:0 18px 8px;">
      <div style="padding:8px 12px;background:#dbeafe;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#12355b;">Preschool</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{preschool_rows}</table>
    </td></tr>
    <tr><td style="padding:8px 18px;">
      <div style="padding:8px 12px;background:#dbeafe;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#12355b;">Elementary</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{elementary_rows}</table>
    </td></tr>
    <tr><td style="padding:8px 18px;">
      <div style="padding:8px 12px;background:#dbeafe;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#12355b;">Special Needs</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{special_needs_rows}</table>
    </td></tr>
    """.format(
        campus=campus,
        kids=kids,
        delta=delta_text(kids, previous_total),
        preschool_rows=detail_rows(campus, "Preschool"),
        elementary_rows=detail_rows(campus, "Elementary"),
        special_needs_rows=detail_rows(campus, "Special Needs"),
    )


def leader_rows():
    grouped = {}
    for row in rows_for(report_date_sql, person_type="Volunteers"):
        campus = str(row.Campus or "")
        name = short_org_name(str(row.OrganizationName or ""))
        key = (campus, name)
        grouped[key] = grouped.get(key, 0) + as_int(row.Attendance)

    html_rows = ""
    for key in sorted(grouped):
        campus, name = key
        html_rows += """
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;color:#334155;">{campus} &middot; {name}</td>
          <td align="right" style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#0f172a;">{value}</td>
        </tr>
        """.format(campus=escape_html(campus), name=escape_html(name), value=grouped[key])
    return html_rows


dashboard_url = (
    model.CmsHost
    + "/PyScript/"
    + DASHBOARD_SCRIPT_NAME
    + "?StartDate="
    + report_date_sql
    + "&EndDate="
    + report_date_sql
    + "&CampusFilter=ALL"
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
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{kids} kids &middot; {leaders} volunteers &middot; Sunday attendance summary</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#eef2f7;">
    <tr><td align="center" style="padding:16px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;max-width:640px;background:#ffffff;border-radius:10px;overflow:hidden;">
        <tr><td style="padding:22px 18px;background:#12355b;font-family:Arial,sans-serif;color:#ffffff;">
          <div style="font-size:24px;line-height:30px;font-weight:bold;">Children's Ministry Attendance</div>
          <div style="padding-top:4px;font-size:15px;line-height:22px;color:#dbeafe;">{date_label}</div>
        </td></tr>
        <tr><td style="padding:12px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            {kids_card}
            {leader_card}
            {total_card}
          </table>
        </td></tr>
        {missing_warning}
        {campus_sections}
        <tr><td style="padding:8px 18px 18px;">
          <div style="padding:8px 12px;background:#fef3c7;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#78350f;">Volunteer Attendance</div>
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
    kids=kids_total,
    leaders=leader_total,
    date_label=report_date_label,
    kids_card=summary_card("Kids", kids_total, delta_text(kids_total, previous_kids_total)),
    leader_card=summary_card("Volunteers", leader_total, delta_text(leader_total, previous_leader_total)),
    total_card=summary_card("Total", grand_total, "Kids + volunteers"),
    missing_warning=missing_warning,
    campus_sections="".join(campus_section(campus) for campus in campuses),
    leader_rows=leader_rows(),
    dashboard_url=dashboard_url,
)

subject = "CM Attendance - {}: {} kids, {} volunteers".format(
    subject_date_label,
    kids_total,
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
print("<p>Weekly CM attendance report queued for {} recipient(s).</p>".format(len(recipient_people_ids)))
