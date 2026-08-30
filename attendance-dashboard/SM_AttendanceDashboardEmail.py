# SM_AttendanceDashboardEmail.py - RockPointe Student Ministry Attendance Report
#
# PURPOSE (dual-mode, dual-day):
# - Sunday  -> live check-in VIEW of today's in-progress Sunday attendance
#              (students + the two Sunday morning volunteer orgs). Bookmark
#              this URL and open it on a phone during check-in; it never sends
#              mail.
# - Monday  -> SEND the recap EMAIL for the Sunday that just completed,
#              compared with the Sunday before it.
# - Wednesday -> live check-in VIEW of today's in-progress D-Group attendance
#              (D-Group classes + D-Group leaders). Same phone-during-check-in
#              use case as Sunday, never sends mail.
# - Thursday -> SEND the recap EMAIL for the D-Group night that just
#              completed, compared with the D-Group night before it.
# - Any other day (manual run) -> safe VIEW of the most recently completed
#              Sunday report. Never sends.
#
# SENDING IS STRUCTURALLY GATED BY DAY OF WEEK, NOT BY A URL PARAMETER:
# model.CallScript cannot pass parameters to the called script (confirmed
# dead end during the CM email rebuild -- see attendance-dashboard/BACKLOG.md),
# so MorningBatch cannot tell this script "send" vs "view" via an argument.
# Instead, model.Email(...) is only ever reachable when today is Monday or
# Thursday. Sunday/Wednesday can never send, no matter what URL params are
# present -- safe to open on a phone at any time during check-in.
#
# OPTIONAL URL PARAMETERS (manual testing only; MorningBatch passes none):
#   Mode=Sunday|Wednesday  - force which report to build, regardless of today
#   View=1                 - on a Monday/Thursday run, render the email body
#                             in-browser instead of sending it (mirrors the
#                             CM email script's Preview=1 pattern)
#   Date=YYYY-MM-DD         - force the report date instead of auto-detecting
#
# DEPLOYMENT: Admin > Advanced > Special Content > Python Scripts
# File name should be: SM_AttendanceDashboardEmail
#
# LIVE RPC EVIDENCE REUSED FROM RPC-3:
# - Build the HTML body in this script and send with model.Email(...).
# - studentministry@rockpointechurch.org / RockPointe Student Ministry sent successfully.
# - No saved draft, email template, or HTML Special Content dependency is required.
#
# SCHEDULING (only after a controlled live send succeeds on both days):
#   if model.DayOfWeek == 1:  # Monday
#       model.CallScript("SM_AttendanceDashboardEmail")
#   if model.DayOfWeek == 4:  # Thursday
#       model.CallScript("SM_AttendanceDashboardEmail")
#
# Mode/day selection inside this script is computed from Python's own
# datetime.weekday() (Monday=0 ... Sunday=6), not from model.DayOfWeek --
# TouchPoint's model.DayOfWeek numbering for Sunday is unconfirmed in this
# repo (only "1 = Monday" has been confirmed live), so relying on it here
# would risk misfiring the send gate. The MorningBatch wrapper above keeps
# using model.DayOfWeek == 1/4 for the Monday/Thursday call gate, unchanged
# from the existing confirmed pattern; only this script's *internal* mode
# logic uses Python's own clock.

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
# durable TouchPoint recipient keys; staff emails remain in local gitignored
# evidence. Reused as-is for both the Sunday and Thursday recap emails.
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
DASHBOARD_SCRIPT_NAME = "SMAttendanceDashboard"

PROGRAM_ID = 1109
ACTIVE_STATUS_ID = 30
STUDENT_TYPE_ID = 201
WED_GRADE_TYPE_ID = 205  # confirmed 2026-08-27: some active Wednesday PS WED grade orgs use this TypeId, not 201
VOLUNTEER_TYPE_ID = 207

# Excluded everywhere regardless of mode.
EXCLUDED_ORG_NAMES = [
    "SM: PS Health and Safety",  # sits in both Division 11 and 42; not a real attendance group
    "SM: SLT 26-27",             # student leadership team roster, not a D-Group meeting -- confirmed 2026-08-27
    "SM: CC Paint War response form F26",  # one-time summer event signup, not recurring attendance -- confirmed 2026-08-30
]

# Matched with SQL LIKE rather than an exact name, since the exact "SM: CC "/
# "SM: PS " prefix on some of these hasn't been confirmed -- and an exact-match
# miss silently reports 0 instead of erroring (see the "D Group" vs
# "D Groups Leaders" name-typo bug found 2026-08-30). The suffix pattern below
# still can't collide with "...D Groups Leaders 2026-2027" since "Leaders "
# sits between "Groups" and the year in that name.
EXCLUDED_NAME_LIKE_PATTERNS = [
    "%Mentor Program%",
    "%D Groups 2026-2027",  # confirmed 2026-08-30: a parent/tracking org, not a real attendance group
]

MODE_CONFIG = {
    "SUNDAY": {
        "division_id": 11,
        "student_type_ids": (STUDENT_TYPE_ID,),
        "require_cc_ps_prefix": True,
        # D-Group Leaders intentionally excluded here -- it's a Wednesday-division
        # org and gets its own line in the Wednesday report instead. (Its prior
        # inclusion here also had a name typo -- "D Group" vs the confirmed
        # "D Groups" -- so it was silently showing 0 either way.)
        "leader_org_names": [
            "SM: CC Sunday Morning Volunteers 2026-2027",
            "SM: PS Sunday Morning Volunteers 2026-2027",
        ],
        "group_by_campus": True,
        "title": "Student Ministry Attendance",
        "leader_section_label": "Leader Attendance",
        "group_word": "Sunday attendance",
        "subject_prefix": "SM Attendance",
        "send_weekday_name": "Monday",
        "dashboard_include_sunday": "1",
        "dashboard_include_wednesday": "0",
    },
    "WEDNESDAY": {
        "division_id": 42,
        "student_type_ids": (STUDENT_TYPE_ID, WED_GRADE_TYPE_ID),
        # D-Group orgs don't all follow the 'SM: CC '/'SM: PS ' naming convention
        # (e.g. "SM: Identity: Daughters of the King ...", "SM: Man Up ...") --
        # confirmed 2026-08-27 in sm-attendance-pyreport.py after two D-Group
        # orgs were found silently dropped by a name-prefix filter. Include any
        # active org in Division 42 regardless of name.
        "require_cc_ps_prefix": False,
        "leader_org_names": [
            "SM: PS D Groups Leaders 2026-2027",  # confirmed OrgId 4060, TypeId 207
        ],
        # Wednesday-only exclusions (not global -- these summer orgs are scoped
        # to this mode, confirmed 2026-08-30):
        "extra_excluded_org_names": [
            "SM: CC Summer Groups 26",
            "SM: CC Summer Groups Leaders 26",
        ],
        "group_by_campus": False,
        "title": "Student Ministry D-Group Attendance",
        "leader_section_label": "D-Group Leader Attendance",
        "group_word": "D-Group attendance",
        "subject_prefix": "SM D-Groups",
        "send_weekday_name": "Thursday",
        "dashboard_include_sunday": "0",
        "dashboard_include_wednesday": "1",
    },
}

# ============================================================
# MODE / ACTION / DATE RESOLUTION
# ============================================================

data = model.Data


def param(name):
    return str(getattr(data, name, "") or "").strip()


python_weekday = datetime.now().date().weekday()  # Monday=0 ... Sunday=6
SUNDAY_WD, WEDNESDAY_WD, MONDAY_WD, THURSDAY_WD = 6, 2, 0, 3

mode_override = param("Mode").upper()
if mode_override in MODE_CONFIG:
    mode = mode_override
elif python_weekday in (WEDNESDAY_WD, THURSDAY_WD):
    mode = "WEDNESDAY"
else:
    mode = "SUNDAY"  # Sunday, Monday, and any other manual-run day default here

target_weekday = SUNDAY_WD if mode == "SUNDAY" else WEDNESDAY_WD
is_live_checkin_day = python_weekday == target_weekday
is_send_day = python_weekday in (MONDAY_WD, THURSDAY_WD)
view_override = param("View") == "1"
action = "VIEW" if (view_override or not is_send_day) else "SEND"

date_override = param("Date")
if re.match(r"^\d{4}-\d{2}-\d{2}$", date_override):
    report_date = datetime.strptime(date_override, "%Y-%m-%d").date()
elif is_live_checkin_day:
    # Live check-in view: today's in-progress attendance, never last week's.
    report_date = datetime.now().date()
else:
    # Recap email (or a View=1 preview of it, or an off-day manual run):
    # most recently completed target weekday, never today.
    days_since = (python_weekday - target_weekday) % 7
    if days_since == 0:
        days_since = 7
    report_date = datetime.now().date() - timedelta(days=days_since)

comparison_date = report_date - timedelta(days=7)

report_date_sql = report_date.strftime("%Y-%m-%d")
comparison_date_sql = comparison_date.strftime("%Y-%m-%d")
report_date_label = report_date.strftime("%A, %B %d, %Y").replace(" 0", " ")
subject_date_label = report_date.strftime("%b %d").replace(" 0", " ")

cfg = MODE_CONFIG[mode]

# ============================================================
# DATA QUERY
# ============================================================


def sql_list(names):
    return ",".join("'{}'".format(n.replace("'", "''")) for n in names)


ATTENDANCE_SQL = """
SET DATEFIRST 7

DECLARE @ProgramId       INT  = {program_id}
DECLARE @DivisionId      INT  = {division_id}
DECLARE @ActiveStatusId  INT  = {active_status_id}
DECLARE @VolunteerTypeId INT  = {volunteer_type_id}
DECLARE @ReportDate      DATE = '{report_date}'
DECLARE @ComparisonDate  DATE = '{comparison_date}'

SELECT
    o.OrganizationId,
    o.OrganizationName,
    o.OrganizationTypeId,
    MeetingDate = CAST(m.MeetingDate AS DATE),
    Attendance  = m.NumPresent
FROM dbo.Organizations o
LEFT JOIN dbo.Meetings m
    ON m.OrganizationId = o.OrganizationId
   AND CAST(m.MeetingDate AS DATE) IN (@ReportDate, @ComparisonDate)
WHERE o.OrganizationStatusId = @ActiveStatusId
  AND o.OrganizationName NOT IN ({excluded_names})
  {excluded_like_clauses}
  AND EXISTS (
      SELECT 1
      FROM dbo.DivOrg dp
      JOIN dbo.Division d ON d.Id = dp.DivId
      WHERE dp.OrgId = o.OrganizationId AND d.ProgId = @ProgramId
  )
  AND (
      (
          o.OrganizationTypeId IN ({student_type_ids})
          AND {student_name_filter}
          AND EXISTS (
              SELECT 1 FROM dbo.DivOrg ds
              WHERE ds.OrgId = o.OrganizationId AND ds.DivId = @DivisionId
          )
      )
      OR (
          o.OrganizationTypeId = @VolunteerTypeId
          AND o.OrganizationName IN ({leader_names})
      )
  )
ORDER BY o.OrganizationName, MeetingDate
""".format(
    program_id=PROGRAM_ID,
    division_id=cfg["division_id"],
    active_status_id=ACTIVE_STATUS_ID,
    volunteer_type_id=VOLUNTEER_TYPE_ID,
    report_date=report_date_sql,
    comparison_date=comparison_date_sql,
    excluded_names=sql_list(EXCLUDED_ORG_NAMES + cfg.get("extra_excluded_org_names", [])),
    excluded_like_clauses="\n  ".join(
        "AND o.OrganizationName NOT LIKE '{}'".format(pattern.replace("'", "''"))
        for pattern in EXCLUDED_NAME_LIKE_PATTERNS
    ),
    student_type_ids=",".join(str(t) for t in cfg["student_type_ids"]),
    student_name_filter=(
        "(o.OrganizationName LIKE 'SM: CC %' OR o.OrganizationName LIKE 'SM: PS %')"
        if cfg["require_cc_ps_prefix"]
        else "1 = 1"
    ),
    leader_names=sql_list(cfg["leader_org_names"]),
)

raw_rows = list(q.QuerySql(ATTENDANCE_SQL))

recipient_people_ids = list(RECIPIENT_PEOPLE_IDS)
if len(set(recipient_people_ids)) != len(recipient_people_ids):
    raise ValueError("RECIPIENT_PEOPLE_IDS contains a duplicate PeopleId")

# ============================================================
# PARSING / AGGREGATION HELPERS
# ============================================================

GENDER_SUFFIXES = [(" Guys", "Guys"), (" Girls", "Girls"), (" Boys", "Guys")]
GRADE_ORDER_BASE = {
    "6th": 1, "7th": 2, "8th": 3,
    "9th": 4, "10th": 5, "11th": 6, "12th": 7,
}
OFF_HOUR_SCHOOL_LEVEL = {
    "Middle School Off Hour": ("Middle School", 8),
    "High School Off Hour": ("High School", 9),
}
GRADE_WORD_RE = re.compile(r"\b(6th|7th|8th|9th|10th|11th|12th)\b")


def normalize_date(value):
    if value is None:
        return ""
    value = str(value).split(" ")[0].split("T")[0].strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if match:
        return "{}-{}-{}".format(
            match.group(3), match.group(1).zfill(2), match.group(2).zfill(2)
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


def short_org_name(name):
    name = str(name or "")
    for prefix in ("SM: CC ", "SM: PS ", "SM: "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def classify_campus(name):
    if name.startswith("SM: CC "):
        return "Central"
    if name.startswith("SM: PS "):
        return "Parker Square"
    return "Other"


def strip_known_prefix(name):
    for prefix in ("SM: CC ", "SM: PS "):
        if name.startswith(prefix):
            remainder = name[len(prefix):]
            if remainder.startswith("WED "):
                remainder = remainder[4:]
            return remainder
    return None


def parse_grade_gender(org_name):
    """`grade` drives Middle/High School bucketing and is searched anywhere in
    the full org name, so a D-Group topic org with the grade buried mid-name
    (e.g. "SM: Identity: Daughters of the King 9th Grade Girls 2026-2027")
    still sorts into the right school level. `gender` is only set when the
    name follows Sunday's strict "<grade> Guys/Girls/Boys" *suffix* convention
    (after stripping the SM: CC/PS prefix) -- that's what tells detail_label()
    to use the bare "6th Guys"-style label instead of the org's own name; a
    D-Group topic org keeps its full name as the label even when a grade was
    found for bucketing purposes."""
    remainder = strip_known_prefix(org_name)
    if remainder is None:
        remainder = org_name
    remainder = remainder.strip()

    if remainder in OFF_HOUR_SCHOOL_LEVEL:
        return remainder, ""

    gender = ""
    for suffix, gender_label in GENDER_SUFFIXES:
        if remainder.endswith(suffix):
            gender = gender_label
            break

    grade_match = GRADE_WORD_RE.search(org_name)
    grade = grade_match.group(1) if grade_match else ""
    return grade, gender


def school_level_for(grade):
    if grade in OFF_HOUR_SCHOOL_LEVEL:
        return OFF_HOUR_SCHOOL_LEVEL[grade][0]
    if grade in ("6th", "7th", "8th"):
        return "Middle School"
    if grade in ("9th", "10th", "11th", "12th"):
        return "High School"
    return "Other"


def grade_order_for(grade):
    if grade in OFF_HOUR_SCHOOL_LEVEL:
        return OFF_HOUR_SCHOOL_LEVEL[grade][1]
    return GRADE_ORDER_BASE.get(grade, 99)


def detail_label(row):
    if row["Gender"] or row["Grade"] in OFF_HOUR_SCHOOL_LEVEL:
        return (row["Grade"] + " " + row["Gender"]).strip()
    return short_org_name(row["OrganizationName"])


rows = []
for r in raw_rows:
    org_name = str(r.OrganizationName or "")
    type_id = as_int(r.OrganizationTypeId)
    person_type = "Leaders" if type_id == VOLUNTEER_TYPE_ID else "Students"
    grade, gender = parse_grade_gender(org_name) if person_type == "Students" else ("", "")
    rows.append(
        {
            "OrganizationId": as_int(r.OrganizationId),
            "OrganizationName": org_name,
            "PersonType": person_type,
            "Campus": classify_campus(org_name),
            "Grade": grade,
            "Gender": gender,
            "SchoolLevel": school_level_for(grade) if person_type == "Students" else "",
            "GradeOrder": grade_order_for(grade) if person_type == "Students" else 0,
            "MeetingDate": normalize_date(r.MeetingDate),
            "Attendance": as_int(r.Attendance),
        }
    )


def rows_for(date_string, campus=None, person_type=None, school_level=None):
    selected = []
    for row in rows:
        if row["MeetingDate"] != date_string:
            continue
        if campus and row["Campus"] != campus:
            continue
        if person_type and row["PersonType"] != person_type:
            continue
        if school_level and row["SchoolLevel"] != school_level:
            continue
        selected.append(row)
    return selected


def total(selected):
    return sum(row["Attendance"] for row in selected)


def total_for(date_string, campus=None, person_type=None, school_level=None):
    return total(rows_for(date_string, campus, person_type, school_level))


def delta_text(current, previous):
    delta = current - previous
    if delta > 0:
        return "&#9650; {} from last week".format(delta)
    if delta < 0:
        return "&#9660; {} from last week".format(abs(delta))
    return "No change from last week"


campuses = ["Central", "Parker Square"] if cfg["group_by_campus"] else [None]
student_total = total_for(report_date_sql, person_type="Students")
leader_total = total_for(report_date_sql, person_type="Leaders")
grand_total = student_total + leader_total
previous_student_total = total_for(comparison_date_sql, person_type="Students")
previous_leader_total = total_for(comparison_date_sql, person_type="Leaders")

# LEFT JOIN produces one row with MeetingDate '' for an active org that has
# neither current nor comparison attendance. An org with comparison
# attendance but no report-date attendance is found by set subtraction below.
expected_orgs = {}
reported_org_ids = set()
for row in rows:
    org_id = row["OrganizationId"]
    expected_orgs[org_id] = (row["Campus"], row["OrganizationName"])
    if row["MeetingDate"] == report_date_sql:
        reported_org_ids.add(org_id)
missing_orgs = [expected_orgs[org_id] for org_id in expected_orgs if org_id not in reported_org_ids]
missing_orgs.sort(key=lambda item: (item[0], item[1]))

# ============================================================
# EMAIL/VIEW-SAFE HTML (TABLES + INLINE CSS; NO JAVASCRIPT)
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
        key = (row["GradeOrder"], detail_label(row))
        grouped[key] = grouped.get(key, 0) + row["Attendance"]

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


def school_level_block(title, campus, school_level):
    selected = rows_for(report_date_sql, campus, "Students", school_level)
    if not selected:
        return ""
    return """
    <tr><td style="padding:8px 18px;">
      <div style="padding:8px 12px;background:#dbeafe;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#12355b;">{title}</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{rows}</table>
    </td></tr>
    """.format(title=title, rows=detail_rows(campus, school_level))


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
    {middle_block}
    {high_block}
    """.format(
        campus=campus,
        students=students,
        delta=delta_text(students, previous_total),
        middle_block=school_level_block("Middle School", campus, "Middle School"),
        high_block=school_level_block("High School", campus, "High School"),
    )


def flat_students_section():
    """Wednesday D-Groups: no campus split (org names don't reliably carry
    campus), just Middle School / High School / Other topic groups."""
    students = total_for(report_date_sql, None, "Students")
    previous_total = total_for(comparison_date_sql, None, "Students")
    return """
    <tr><td style="padding:24px 18px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
        <tr>
          <td style="font-family:Arial,sans-serif;font-size:22px;line-height:28px;font-weight:bold;color:#12355b;">D-Groups</td>
          <td align="right" style="font-family:Arial,sans-serif;font-size:22px;line-height:28px;font-weight:bold;color:#12355b;">{students}</td>
        </tr>
        <tr><td colspan="2" style="padding-top:3px;font-family:Arial,sans-serif;font-size:14px;line-height:21px;color:#475569;">{students} students &middot; {delta}</td></tr>
      </table>
    </td></tr>
    {middle_block}
    {high_block}
    {other_block}
    """.format(
        students=students,
        delta=delta_text(students, previous_total),
        middle_block=school_level_block("Middle School", None, "Middle School"),
        high_block=school_level_block("High School", None, "High School"),
        other_block=school_level_block("Other D-Groups", None, "Other"),
    )


def leader_rows():
    grouped = {}
    for row in rows_for(report_date_sql, person_type="Leaders"):
        name = row["OrganizationName"]
        grouped[name] = grouped.get(name, 0) + row["Attendance"]

    html_rows = ""
    for name in cfg["leader_org_names"]:
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
    + "&IncludeSunday="
    + cfg["dashboard_include_sunday"]
    + "&IncludeWednesday="
    + cfg["dashboard_include_wednesday"]
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
          No meeting was reported for {count} active {group_word_label} {group_word}:
          <ul style="margin:8px 0 0;padding-left:20px;">{items}</ul>
        </td></tr>
      </table>
    </td></tr>
    """.format(
        count=len(missing_orgs),
        group_word_label=cfg["group_word"],
        group_word="group" if len(missing_orgs) == 1 else "groups",
        items=missing_items,
    )

if cfg["group_by_campus"]:
    campus_sections_html = "".join(campus_section(campus) for campus in campuses)
else:
    campus_sections_html = flat_students_section()

body = """
<div style="margin:0;padding:0;background:#eef2f7;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{students} students &middot; {leaders} leaders &middot; {title}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#eef2f7;">
    <tr><td align="center" style="padding:16px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;max-width:640px;background:#ffffff;border-radius:10px;overflow:hidden;">
        <tr><td style="padding:22px 18px;background:#12355b;font-family:Arial,sans-serif;color:#ffffff;">
          <div style="font-size:24px;line-height:30px;font-weight:bold;">{title}</div>
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
          <div style="padding:8px 12px;background:#fef3c7;font-family:Arial,sans-serif;font-size:14px;line-height:20px;font-weight:bold;color:#78350f;">{leader_section_label}</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            {leader_rows}
          </table>
        </td></tr>
        <tr><td align="center" style="padding:20px 18px 26px;">
          <a href="{dashboard_url}" style="display:inline-block;padding:13px 20px;background:#2563eb;border-radius:6px;font-family:Arial,sans-serif;font-size:16px;line-height:20px;font-weight:bold;color:#ffffff;text-decoration:none;">View interactive attendance report</a>
          <div style="padding-top:16px;font-family:Arial,sans-serif;font-size:12px;line-height:18px;color:#64748b;">{footer_text}</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</div>
""".format(
    students=student_total,
    leaders=leader_total,
    title=cfg["title"],
    date_label=report_date_label,
    student_card=summary_card("Students", student_total, delta_text(student_total, previous_student_total)),
    leader_card=summary_card("Leaders", leader_total, delta_text(leader_total, previous_leader_total)),
    total_card=summary_card("Total", grand_total, "Students + leaders"),
    missing_warning=missing_warning,
    campus_sections=campus_sections_html,
    leader_section_label=cfg["leader_section_label"],
    leader_rows=leader_rows(),
    dashboard_url=dashboard_url,
    footer_text=(
        "Live check-in view -- reopen this page for updated counts. No email is sent from this view."
        if is_live_checkin_day
        else "Automated {} report from RockPointe TouchPoint".format(cfg["send_weekday_name"])
    ),
)

subject = "{} - {}: {} students, {} leaders".format(
    cfg["subject_prefix"],
    subject_date_label,
    student_total,
    leader_total,
)

# ============================================================
# SEND OR VIEW
# ============================================================

if action == "SEND":
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
    print("<p>{} report queued for {} recipient(s).</p>".format(cfg["subject_prefix"], len(recipient_people_ids)))
else:
    if is_live_checkin_day:
        banner = "<p style=\"font-family:Arial,sans-serif;color:#0f766e;\"><strong>LIVE VIEW</strong> -- {}. No email is sent from this page.</p>".format(escape_html(report_date_label))
    else:
        banner = "<p style=\"font-family:Arial,sans-serif;color:#b45309;\"><strong>PREVIEW MODE</strong> -- no email sent (View=1). Would send to {} recipient(s) as: {}</p>".format(
            len(recipient_people_ids), escape_html(subject)
        )
    print(banner + body)
