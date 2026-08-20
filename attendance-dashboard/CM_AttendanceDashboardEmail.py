# CM_AttendanceDashboardEmail.py - RockPointe Children's Ministry Weekly Attendance Report
#
# PURPOSE:
# - Sends a mobile-friendly report each Monday for the immediately preceding Sunday.
# - Compares headline and campus totals with the Sunday before that, and shows
#   a 6-week rolling average alongside every current-Sunday number.
# - Lists current-Sunday kid attendance by campus and bucket (Preschool,
#   Elementary, Special Needs), in the same age order confirmed for the
#   interactive dashboard, and volunteer attendance by campus.
# - Flags active Sunday reporting organizations with no meeting row for the
#   report date.
#
# MODELED ON: SM_AttendanceDashboardEmail.py (Student Ministry). Same shape,
# same email-safe HTML approach (model.Email, no saved draft / template
# dependency), same missing-meeting warning pattern.
#
# 2026-08-19: this script's query/classification logic is intentionally kept
# in sync BY HAND with attendance-dashboard/cm-attendance-pyreport.py (the
# interactive dashboard). A live spike confirmed model.CallScript(...) does
# not return that script's rendered output in a usable form here (came back
# empty), so calling the dashboard for data and parsing its output was not
# viable -- see attendance-dashboard/BACKLOG.md for the finding. Any future
# fix to the dashboard's filter, classification, ordering, or org overrides
# must be re-applied here too.
#
# SCOPE CONFIRMED LIVE 2026-08-17 (validated production filter -- see
# data-dictionary-expander/reports/2026-08-17/rpc-children-four-week-validation-summary.md
# for the full 93-involvement audited roster):
# - Program 1111 = Children's Ministry (CM)
# - Division 81 = RP CC Children (reporting, Program 1137, Central)
# - Division 82 = RP PS Children (reporting, Program 1138, Parker Square)
# - Type 201 = Kids classroom, Type 207 = Volunteers
# - Reporting-program linkage alone is too broad. Production also requires a
#   real Sunday presence: a standing Sunday schedule (OrgSchedule.SchedDay =
#   0) OR an actual Sunday meeting within the lookback window. This is what
#   correctly excludes ten stale/seasonal records still linked to the
#   reporting programs -- Christmas Eve 2025 classes, the dead
#   "CM: All Special Needs Volunteers" rollup (confirmed zero attendance
#   every week), "CM: CC Ignite Kids Fall 2026 Volunteers", "CM: CC
#   Preschool Small Group/Student Leaders", a duplicate PS 8:30 Volunteers
#   Elementary org, and "CM: Volunteers Encompass".
# - "CM: Embrace Families" is a small group with no Sunday schedule and no
#   Sunday meeting (confirmed NO MEETING every week) -- correctly excluded
#   by the same filter, not a Sunday check-in involvement.
# - Special Needs (Embrace) classroom + volunteer involvements ARE included:
#   CC/PS Special Needs Kids and Volunteers Special Needs at both service
#   times, both campuses -- real Sunday schedules, real weekly attendance.
# - Kindergarten is classified as Elementary, not Preschool (confirmed by
#   Brian 2026-08-19).
# - Central Welcome Team reporting org, confirmed by Angela 2026-08-19: org
#   3587 (CM: CC Welcome Team Scheduler) is used instead of the newer
#   4026/4027 ("...Volunteers Welcome Team 2026-2027") pair, which exist but
#   had no meeting logged as of 2026-08-16. 3587 bypasses the normal
#   reporting-division/Sunday-schedule checks via an explicit override; see
#   @CentralWelcomeTeamOrgId below.
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
# TESTING: set PREVIEW_MODE = True below, save, and run -- the report prints
# to the screen with a "PREVIEW MODE" banner and no model.Email call is made.
# Set PREVIEW_MODE = False (and save) before a real send or before scheduling
# to MorningBatch.
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

# Flip to True, save, and run to preview the report without sending any
# email. Flip back to False (and save) before a real send.
PREVIEW_MODE = True

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

# Central Welcome Team reporting org (see header note): included via an
# explicit override; 4026/4027 are excluded outright so Central Welcome Team
# never double-counts once those newer orgs start logging meetings.
CENTRAL_WELCOME_TEAM_ORG_ID = 3587
EXCLUDED_ORG_IDS = (4026, 4027)

# How many trailing Sundays (including the report Sunday) feed the 6-week
# average shown next to every current-Sunday number.
AVERAGE_WINDOW_WEEKS = 6

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
# 6 Sundays inclusive of report_date (report_date and the 5 before it). This
# window already covers comparison_date, so one query serves both the
# week-over-week delta and the 6-week average.
window_start = report_date - timedelta(weeks=AVERAGE_WINDOW_WEEKS - 1)

report_date_sql = report_date.strftime("%Y-%m-%d")
comparison_date_sql = comparison_date.strftime("%Y-%m-%d")
window_start_sql = window_start.strftime("%Y-%m-%d")
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
DECLARE @WindowStart      DATE = '{window_start}'
DECLARE @CCPrefix         VARCHAR(10)  = 'CM: CC '
DECLARE @PSPrefix         VARCHAR(10)  = 'CM: PS '
DECLARE @ScheduleLookbackDays INT      = 28
DECLARE @CentralWelcomeTeamOrgId INT   = {central_welcome_team_org_id}

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
   AND CAST(m.MeetingDate AS DATE) BETWEEN @WindowStart AND @ReportDate
WHERE o.OrganizationStatusId = @ActiveStatusId
  AND o.OrganizationName LIKE 'CM:%'
  AND (o.OrganizationName LIKE @CCPrefix + '%' OR o.OrganizationName LIKE @PSPrefix + '%')
  AND o.OrganizationTypeId IN (@KidsTypeId, @VolunteerTypeId)
  AND o.OrganizationId NOT IN ({excluded_org_ids})
  AND EXISTS (
      SELECT 1
      FROM dbo.DivOrg dp
      JOIN dbo.Division d ON d.Id = dp.DivId
      WHERE dp.OrgId = o.OrganizationId AND d.ProgId = @ProgramId
  )
  AND (
      EXISTS (
          SELECT 1
          FROM dbo.DivOrg dr
          WHERE dr.OrgId = o.OrganizationId
            AND dr.DivId IN (@CCReportingDivId, @PSReportingDivId)
      )
      OR o.OrganizationId = @CentralWelcomeTeamOrgId
  )
  -- Validated 2026-08-17: reporting-program linkage alone is too broad.
  -- Require a real Sunday presence -- a standing Sunday schedule or an
  -- actual Sunday meeting in the lookback window -- to exclude
  -- stale/seasonal records (Christmas Eve classes, dead rollup orgs,
  -- one-off event volunteer lists) still linked to the reporting program.
  AND (
      EXISTS (
          SELECT 1 FROM dbo.OrgSchedule os
          WHERE os.OrganizationId = o.OrganizationId AND os.SchedDay = 0
      )
      OR EXISTS (
          SELECT 1 FROM dbo.Meetings sm
          WHERE sm.OrganizationId = o.OrganizationId
            AND CAST(sm.MeetingDate AS DATE) >= DATEADD(DAY, -@ScheduleLookbackDays, CAST(GETDATE() AS DATE))
            AND DATEPART(dw, sm.MeetingDate) = 1
      )
      -- 3587 has no standing OrgSchedule row (it's a "Scheduler" org, not a
      -- classroom/attendance org with a fixed recurring slot); bypass the
      -- two checks above for this one confirmed org rather than let it
      -- silently drop out.
      OR o.OrganizationId = @CentralWelcomeTeamOrgId
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
    window_start=window_start_sql,
    central_welcome_team_org_id=CENTRAL_WELCOME_TEAM_ORG_ID,
    excluded_org_ids=",".join(str(org_id) for org_id in EXCLUDED_ORG_IDS),
)

rows = list(q.QuerySql(ATTENDANCE_SQL))

recipient_people_ids = list(RECIPIENT_PEOPLE_IDS)
if len(set(recipient_people_ids)) != len(recipient_people_ids):
    raise ValueError("RECIPIENT_PEOPLE_IDS contains a duplicate PeopleId")

# ============================================================
# AGE-GROUP / BUCKET CLASSIFICATION
# Mirrored from cm-attendance-pyreport.py (see header note). Confirmed
# against the full live 2026-08-17 involvement export (125 active CM orgs in
# reporting scope). Match order matters: Special Needs, then
# Kindergarten/Grade (Elementary), then Preschool.
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
    "nursery",
)


def classify_age_group(name):
    lname = name.lower()
    if "special needs" in lname:
        return "Special Needs"
    if "kindergarten" in lname or "grade" in lname:
        return "Elementary"
    if any(k in lname for k in _PRESCHOOL_KEYWORDS):
        return "Preschool"
    return "Other"


# Display order within each campus/bucket, confirmed by Brian 2026-08-19 and
# mirrored verbatim from cm-attendance-pyreport.py's _AGE_ORDER tables. Keys
# are org names with the "CM: CC "/"CM: PS " campus prefix stripped. Any org
# not found here falls back to alphabetical -- see age_rank() below.
_CENTRAL_PRESCHOOL_ORDER = [
    "9:00a Infants", "10:45 AM Infants",
    "9:00a Crawlers", "10:45 AM Crawlers",
    "9:00a Walking-18 Months", "10:45 AM Walking-18 Months",
    "9:00a 18-24 Months", "10:45 AM 18-24 Months",
    "9:00a 2 Years", "10:45 AM 2 Years",
    "9:00a 3 Years", "10:45 AM 3 Years",
    "9:00a PreK (4-5 Years)", "10:45 AM PreK (4-5 Years)",
]

_CENTRAL_ELEMENTARY_ORDER = [
    "9:00a Kindergarten", "10:45 AM Kindergarten",
    "9:00a 1st Grade", "10:45 AM 1st Grade",
    "9:00a 2nd Grade", "10:45 AM 2nd Grade",
    "9:00a 3rd Grade Boys", "10:45 AM 3rd Grade Boys",
    "9:00a 3rd Grade Girls", "10:45 AM 3rd Grade Girls",
    "9:00a 4th Grade Boys", "10:45 AM 4th Grade Boys",
    "9:00a 4th Grade Girls", "10:45 AM 4th Grade Girls",
    "9:00a 5th Grade Boys", "10:45 AM 5th Grade Boys",
    "9:00a 5th Grade Girls", "10:45 AM 5th Grade Girls",
]

_PS_PRESCHOOL_ORDER = [
    "8:30 Infants (Birth-Crawling)", "9:45 Infants (Birth-Crawling)", "11:15 Infants (Birth-Crawling)",
    "8:30 Toddlers (Walking-24 mo)", "9:45 Toddlers (Walking-24 mo)", "11:15 Toddlers (Walking-24 mo)",
    "8:30 2 Years", "9:45 2 Years", "11:15 2 Years",
    "8:30 3 Years", "9:45 3 Years", "11:15 3 Years",
    "8:30 PreK", "9:45 PreK", "11:15 PreK",
]

_PS_ELEMENTARY_ORDER = [
    "8:30 Kindergarten", "9:45 Kindergarten", "11:15 Kindergarten",
    "8:30 1st Grade", "9:45 1st Grade", "11:15 1st Grade",
    "8:30 2nd Grade", "9:45 2nd Grade", "11:15 2nd Grade",
    "8:30 3rd Grade Boys", "9:45 3rd Grade Boys", "11:15 3rd Grade Boys",
    "8:30 3rd Grade Girls", "9:45 3rd Grade Girls", "11:15 3rd Grade Girls",
    "8:30 4th Grade Boys", "9:45 4th Grade Boys", "11:15 4th Grade Boys",
    "8:30 4th Grade Girls", "9:45 4th Grade Girls", "11:15 4th Grade Girls",
    "8:30 5th Grade Boys", "9:45 5th Grade Boys", "11:15 5th Grade Boys",
    "8:30 5th Grade Girls", "9:45 5th Grade Girls", "11:15 5th Grade Girls",
]

_AGE_ORDER = {
    ("Central", "Preschool"): _CENTRAL_PRESCHOOL_ORDER,
    ("Central", "Elementary"): _CENTRAL_ELEMENTARY_ORDER,
    ("Parker Square", "Preschool"): _PS_PRESCHOOL_ORDER,
    ("Parker Square", "Elementary"): _PS_ELEMENTARY_ORDER,
}

_CAMPUS_PREFIX_RE = re.compile(r"^CM: (CC|PS) ")


def age_rank(campus, bucket, org_name):
    order = _AGE_ORDER.get((campus, bucket))
    if not order:
        return None
    short = _CAMPUS_PREFIX_RE.sub("", org_name)
    try:
        return order.index(short)
    except ValueError:
        return None


# Mirrored from cm-attendance-pyreport.py's classify_volunteer_bucket/sort:
# groups volunteer rows by type (Nursery/Kinder -> Elementary -> Special
# Needs -> Welcome Team) then by service time, instead of plain alphabetical.
def classify_volunteer_bucket(name):
    lname = name.lower()
    if "special needs" in lname:
        return "Special Needs"
    if "nursery" in lname or "kinder" in lname:
        return "Nursery/Kinder"
    if "elementary" in lname:
        return "Elementary"
    if "welcome team" in lname:
        return "Welcome Team"
    return "Other"


_VOLUNTEER_BUCKET_ORDER = {"Nursery/Kinder": 0, "Elementary": 1, "Special Needs": 2, "Welcome Team": 3}
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")


def volunteer_time_minutes(name):
    match = _TIME_RE.search(name)
    if not match:
        return 9999
    return int(match.group(1)) * 60 + int(match.group(2))


# Mirrored from cm-attendance-pyreport.py's prettyLabel(): CM staff's
# TouchPoint org-naming conventions are inconsistent ("9:00a" vs "10:45 AM"
# vs "9:00 a", "Volunteer" vs "Volunteers", a trailing school-year suffix).
# This only cleans up the display label -- age_rank/bucket/sort logic and
# the raw OrganizationName elsewhere are untouched.
def pretty_label(name):
    name = re.sub(
        r"^(\d{1,2}):(\d{2})\s*a\.?m?\.?\s*",
        lambda m: "{}:{} AM ".format(m.group(1), m.group(2)),
        name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r"\bVolunteers?\b\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\d{4}-\d{4}\s*$", "", name)
    return re.sub(r"\s{2,}", " ", name).strip()


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


def weekly_totals(campus=None, person_type=None, bucket=None, org_id=None):
    """{date_string: summed_attendance} across the fetched window, for every
    Sunday that actually has a logged meeting matching the filters. Weeks
    with no meeting are omitted entirely rather than counted as zero, so a
    newly created org isn't penalized for weeks before it existed."""
    by_date = {}
    for row in rows:
        date_string = row_date(row)
        if not date_string:
            continue
        if campus and str(row.Campus or "") != campus:
            continue
        if person_type and str(row.PersonType or "") != person_type:
            continue
        if bucket and classify_age_group(str(row.OrganizationName or "")) != bucket:
            continue
        if org_id is not None and as_int(row.OrganizationId) != org_id:
            continue
        by_date[date_string] = by_date.get(date_string, 0) + as_int(row.Attendance)
    return by_date


def avg_6wk(campus=None, person_type=None, bucket=None, org_id=None):
    totals = weekly_totals(campus, person_type, bucket, org_id)
    if not totals:
        return 0
    return round(sum(totals.values()) / len(totals))


def delta_text(current, previous):
    delta = current - previous
    if delta > 0:
        return "&#9650; {} from last Sunday".format(delta)
    if delta < 0:
        return "&#9660; {} from last Sunday".format(abs(delta))
    return "No change from last Sunday"


def with_avg_caption(delta, avg):
    return "{} &middot; 6-wk avg: {}".format(delta, avg)


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
kids_avg = avg_6wk(person_type="Kids")
leader_avg = avg_6wk(person_type="Volunteers")
grand_avg = avg_6wk()

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


def column_header_row():
    return """
    <tr>
      <td style="padding:0 12px;"></td>
      <td align="right" style="padding:0 12px;font-family:Arial,sans-serif;font-size:10px;line-height:16px;font-weight:bold;color:#94a3b8;text-transform:uppercase;letter-spacing:.3px;">This Sun</td>
      <td align="right" width="66" style="padding:0 12px;font-family:Arial,sans-serif;font-size:10px;line-height:16px;font-weight:bold;color:#94a3b8;text-transform:uppercase;letter-spacing:.3px;">6-wk avg</td>
    </tr>
    """


def detail_row_html_raw(label_html, value, avg):
    """label_html must already be HTML-safe (pre-escaped) -- used when a row's
    label is built from more than one escaped field, e.g. campus + org name."""
    return """
    <tr>
      <td style="padding:9px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;color:#334155;">{label}</td>
      <td align="right" style="padding:9px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#0f172a;">{value}</td>
      <td align="right" width="66" style="padding:9px 12px;border-bottom:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:13px;line-height:20px;color:#94a3b8;">{avg}</td>
    </tr>
    """.format(label=label_html, value=value, avg=avg)


def detail_row_html(label, value, avg):
    return detail_row_html_raw(escape_html(label), value, avg)


def total_row_html(label, value, avg):
    return """
    <tr>
      <td style="padding:10px 12px;background:#e8f1fb;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#12355b;">{label} total</td>
      <td align="right" style="padding:10px 12px;background:#e8f1fb;font-family:Arial,sans-serif;font-size:15px;line-height:20px;font-weight:bold;color:#12355b;">{value}</td>
      <td align="right" width="66" style="padding:10px 12px;background:#e8f1fb;font-family:Arial,sans-serif;font-size:13px;line-height:20px;color:#4a6b8a;">{avg}</td>
    </tr>
    """.format(label=escape_html(label), value=value, avg=avg)


def detail_rows(campus, bucket):
    selected = rows_for(report_date_sql, campus, "Kids", bucket)
    orgs = {}
    for row in selected:
        org_id = as_int(row.OrganizationId)
        full_name = str(row.OrganizationName or "")
        entry = orgs.setdefault(
            org_id,
            {"full_name": full_name, "short_name": short_org_name(full_name), "count": 0},
        )
        entry["count"] += as_int(row.Attendance)

    def sort_key(org_id):
        entry = orgs[org_id]
        rank = age_rank(campus, bucket, entry["full_name"])
        return (rank if rank is not None else 9999, entry["short_name"])

    html_rows = column_header_row()
    for org_id in sorted(orgs, key=sort_key):
        entry = orgs[org_id]
        html_rows += detail_row_html(pretty_label(entry["short_name"]), entry["count"], avg_6wk(org_id=org_id))

    bucket_total = total(selected)
    bucket_avg = avg_6wk(campus=campus, person_type="Kids", bucket=bucket)
    html_rows += total_row_html(bucket, bucket_total, bucket_avg)
    return html_rows


def campus_section(campus):
    kids = total_for(report_date_sql, campus, "Kids")
    previous_total = total_for(comparison_date_sql, campus, "Kids")
    campus_avg = avg_6wk(campus=campus, person_type="Kids")
    return """
    <tr><td style="padding:24px 18px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
        <tr>
          <td style="font-family:Arial,sans-serif;font-size:22px;line-height:28px;font-weight:bold;color:#12355b;">{campus}</td>
          <td align="right" style="font-family:Arial,sans-serif;font-size:22px;line-height:28px;font-weight:bold;color:#12355b;">{kids}</td>
        </tr>
        <tr><td colspan="2" style="padding-top:3px;font-family:Arial,sans-serif;font-size:14px;line-height:21px;color:#475569;">{kids} kids &middot; {delta_and_avg}</td></tr>
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
        delta_and_avg=with_avg_caption(delta_text(kids, previous_total), campus_avg),
        preschool_rows=detail_rows(campus, "Preschool"),
        elementary_rows=detail_rows(campus, "Elementary"),
        special_needs_rows=detail_rows(campus, "Special Needs"),
    )


def leader_rows():
    orgs = {}
    for row in rows_for(report_date_sql, person_type="Volunteers"):
        org_id = as_int(row.OrganizationId)
        campus = str(row.Campus or "")
        full_name = str(row.OrganizationName or "")
        entry = orgs.setdefault(
            org_id,
            {"campus": campus, "full_name": full_name, "short_name": short_org_name(full_name), "count": 0},
        )
        entry["count"] += as_int(row.Attendance)

    def sort_key(org_id):
        entry = orgs[org_id]
        bucket_rank = _VOLUNTEER_BUCKET_ORDER.get(classify_volunteer_bucket(entry["full_name"]), 4)
        return (entry["campus"], bucket_rank, volunteer_time_minutes(entry["full_name"]), entry["short_name"])

    html_rows = column_header_row()
    for org_id in sorted(orgs, key=sort_key):
        entry = orgs[org_id]
        # Escape campus/name individually so the literal &middot; entity
        # between them doesn't get double-escaped into visible text.
        label = "{} &middot; {}".format(escape_html(entry["campus"]), escape_html(pretty_label(entry["short_name"])))
        html_rows += detail_row_html_raw(label, entry["count"], avg_6wk(org_id=org_id))
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
    kids_card=summary_card("Kids", kids_total, with_avg_caption(delta_text(kids_total, previous_kids_total), kids_avg)),
    leader_card=summary_card("Volunteers", leader_total, with_avg_caption(delta_text(leader_total, previous_leader_total), leader_avg)),
    total_card=summary_card("Total", grand_total, with_avg_caption("Kids + volunteers", grand_avg)),
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

if PREVIEW_MODE:
    print(
        "<p><strong>PREVIEW MODE</strong> -- no email sent. Would have gone to "
        "{} recipient(s). Subject: {}</p>".format(len(recipient_people_ids), escape_html(subject))
    )
    print(body)
else:
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
