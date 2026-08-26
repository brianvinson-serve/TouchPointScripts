import json
import re
from datetime import datetime, timedelta

# ============================================================
# CM (Children's Ministry) Attendance Dashboard
#
# Modeled directly on sm-attendance-pyreport.py. Scope confirmed live
# 2026-08-17 via a read-only discovery query
# (data-dictionary-expander/sql/focused/RPC_ChildrenInvolvementDiscovery.sql)
# and an independently validated 4-week Sunday attendance pull
# (data-dictionary-expander/sql/focused/RPC_ChildrenFourWeekAttendanceValidation.sql),
# both exported from TouchPoint and reviewed on the Mac. See
# data-dictionary-expander/reports/2026-08-17/rpc-children-four-week-validation-summary.md
# for the full 93-involvement audited roster and findings.
#
# VALIDATED PRODUCTION FILTER (all conditions required):
#   1. OrganizationStatusId = 30 (active)
#   2. Name begins with "CM:"
#   3. OrganizationTypeId 201 (children/classroom) or 207 (volunteers)
#   4. Linked via DivOrg -> Division to reporting Program 1137 (Central,
#      Division 81 = RP CC Children) or 1138 (Parker Square, Division 82 =
#      RP PS Children)
#   5. Has a Sunday schedule (OrgSchedule.SchedDay = 0) OR an actual Sunday
#      meeting in the lookback window
#
# Condition 5 is the piece a naive Program-1111-linkage query misses: it is
# what correctly excludes ten stale/seasonal records that ARE linked to the
# reporting programs but have no real Sunday presence -- e.g. Christmas Eve
# 2025 classes, "CM: All Special Needs Volunteers" (confirmed dead rollup,
# zero attendance every week), "CM: CC Ignite Kids Fall 2026 Volunteers",
# "CM: CC Preschool Small Group/Student Leaders", a duplicate PS 8:30
# Volunteers Elementary org, and "CM: Volunteers Encompass". It also
# correctly excludes "CM: Embrace Families" (small group, no Sunday
# schedule, no Sunday meeting -- not a Sunday check-in involvement).
#
# Special Needs (Embrace) classroom + volunteer involvements ARE included:
# CC/PS Special Needs Kids and Volunteers Special Needs at both service
# times, both campuses -- they carry real Sunday schedules and weekly
# attendance.
#
# TWO EXPLICIT OVERRIDES:
#
# 1. (Confirmed by Angela 2026-08-19) org 3587 (CM: CC Welcome Team
#    Scheduler) bypasses conditions 4 and 5 above -- it's linked to Division
#    15 (CM Elementary) rather than the reporting divisions, and has no
#    standing OrgSchedule row -- because it's the org Angela actually wants
#    used for Central Welcome Team reporting. Orgs 4026/4027 (the newer
#    "...Volunteers Welcome Team 2026-2027" pair) are explicitly excluded so
#    Central Welcome Team doesn't double-count once those start logging
#    meetings. See @CentralWelcomeTeamOrgId in the SQL below.
#
# 2. (Per Angela's email 2026-08-25) org 3508 (CM: PS 8:30 Birth-5th
#    Volunteers Scheduler) is now the org PS 8:30 volunteers actually check
#    into, replacing the two previously-listed orgs 4020 (CM: PS 8:30
#    Volunteers Nursery/Kinder 2026-2027) and 4021 (CM: PS 8:30 Volunteers
#    Elementary 2026-2027), which Angela is making inactive. Same override
#    shape as 3587 -- bypasses conditions 4/5 and excludes 4020/4021 outright
#    -- applied by analogy to the "...Scheduler" naming pattern, since org
#    3508's own DivOrg linkage/OrgSchedule/OrganizationTypeId have NOT been
#    independently confirmed via a live query (no live TouchPoint access in
#    this session). Verify live before/soon after deploying -- see
#    BACKLOG.md. Because 3508 spans "Birth-5th" (both former buckets in one
#    org), it's classified into the "Nursery/Kinder" volunteer bucket by
#    explicit OrganizationId match rather than by name-keyword match --
#    see @PS830VolunteersSchedulerOrgId in the SQL below and
#    classify_volunteer_bucket() below.
#
# Parameters from URL (?StartDate=2026-01-01&EndDate=2026-07-08 etc.)
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

# ============================================================
# SQL
# ============================================================
sql = """
SET DATEFIRST 7

DECLARE @ProgramId        INT          = 1111
DECLARE @CCReportingDivId INT          = 81
DECLARE @PSReportingDivId INT          = 82
DECLARE @KidsTypeId       INT          = 201
DECLARE @VolunteerTypeId  INT          = 207
DECLARE @StartDate        DATE         = '{start}'
DECLARE @EndDate          DATE         = '{end}'
DECLARE @CampusFilter     VARCHAR(20)  = '{campus}'
DECLARE @CCPrefix         VARCHAR(10)  = 'CM: CC '
DECLARE @PSPrefix         VARCHAR(10)  = 'CM: PS '
DECLARE @ScheduleLookbackDays INT      = 28

-- Central Welcome Team reporting org, confirmed by Angela 2026-08-19: org
-- 3587 (CM: CC Welcome Team Scheduler) is linked to Division 15 (CM
-- Elementary), not the reporting divisions below, so it needs an explicit
-- override -- and it carries real Sunday attendance (6 present 2026-08-16)
-- while the newer 4026/4027 "...Volunteers Welcome Team 2026-2027" orgs
-- exist but had no meeting logged that same Sunday. Excluding 4026/4027
-- keeps Central Welcome Team numbers matching what Angela actually wants
-- reported, and avoids silently doubling them if those orgs start getting
-- meetings logged later.
DECLARE @CentralWelcomeTeamOrgId INT  = 3587

-- PS 8:30 volunteer reporting org, per Angela's email 2026-08-25: org 3508
-- (CM: PS 8:30 Birth-5th Volunteers Scheduler) is what 8:30 PS volunteers
-- now check into, replacing 4020/4021 below, which Angela is making
-- inactive. Not yet independently confirmed live (division/schedule/type) --
-- treated the same as the 3587 override by analogy pending that check.
DECLARE @PS830VolunteersSchedulerOrgId INT = 3508

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
    OrganizationId   = o.OrganizationId,
    OrganizationName = o.OrganizationName,
    MeetingDate      = CAST(m.MeetingDate AS DATE),
    Attendance       = ISNULL(m.NumPresent, 0)

FROM dbo.Organizations o

JOIN dbo.Meetings m
    ON  m.OrganizationId = o.OrganizationId
    AND CAST(m.MeetingDate AS DATE) BETWEEN @StartDate AND @EndDate

WHERE
    o.OrganizationStatusId = 30
    AND o.OrganizationName LIKE 'CM:%'
    AND (
        o.OrganizationName LIKE @CCPrefix + '%'
        OR o.OrganizationName LIKE @PSPrefix + '%'
    )
    AND (
           @CampusFilter = 'ALL'
        OR (@CampusFilter = 'CENTRAL'      AND o.OrganizationName LIKE @CCPrefix + '%')
        OR (@CampusFilter = 'PARKERSQUARE' AND o.OrganizationName LIKE @PSPrefix + '%')
    )
    AND o.OrganizationTypeId IN (@KidsTypeId, @VolunteerTypeId)
    AND o.OrganizationId NOT IN (4026, 4027, 4020, 4021)
    AND EXISTS (
        SELECT 1
        FROM dbo.DivOrg dp
        JOIN dbo.Division d ON d.Id = dp.DivId
        WHERE dp.OrgId = o.OrganizationId
          AND d.ProgId  = @ProgramId
    )
    AND (
        EXISTS (
            SELECT 1
            FROM dbo.DivOrg dr
            WHERE dr.OrgId = o.OrganizationId
              AND dr.DivId IN (@CCReportingDivId, @PSReportingDivId)
        )
        OR o.OrganizationId IN (@CentralWelcomeTeamOrgId, @PS830VolunteersSchedulerOrgId)
    )
    -- Validated 2026-08-17: reporting-program linkage alone is too broad.
    -- Require a real Sunday presence -- either a standing Sunday schedule
    -- or an actual Sunday meeting in the lookback window -- to exclude
    -- stale/seasonal records (Christmas Eve classes, dead rollup orgs,
    -- one-off event volunteer lists) that are still linked to the
    -- reporting program but no longer represent live Sunday attendance.
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
        -- 3587 and 3508 are "Scheduler" orgs, not classroom/attendance orgs
        -- with a fixed recurring slot, so they can't rely on the two checks
        -- above staying true every week. Bypass them for these two
        -- confirmed-by-name orgs rather than let them silently drop out.
        OR o.OrganizationId IN (@CentralWelcomeTeamOrgId, @PS830VolunteersSchedulerOrgId)
    )

ORDER BY Campus, PersonType, OrganizationName, MeetingDate
""".format(
    start=start_date,
    end=end_date,
    campus=campus_filter,
)


# ============================================================
# Helpers
# ============================================================
def _norm_date(s):
    """Normalize any date string to YYYY-MM-DD for JS consumption."""
    s = s.split(" ")[0].split("T")[0].strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return "{}-{}-{}".format(m.group(3), m.group(1).zfill(2), m.group(2).zfill(2))
    return s


# Age-group / bucket classification confirmed against the full live 2026-08-17
# involvement export (125 active CM orgs in reporting scope). Match order
# matters: Special Needs, then Kindergarten/Grade (Elementary), then Preschool.
# Kindergarten confirmed by Brian 2026-08-19 as belonging in the Elementary
# section, not Preschool -- it was previously misclassified via the
# "kindergarten" keyword below matching before the "grade" check ran.
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


# Display order within each campus/bucket, confirmed by Brian 2026-08-19 as
# the desired "age order" (youngest to oldest, service times interleaved in
# the sequence he provided). Keys are org names with the "CM: CC "/"CM: PS "
# campus prefix stripped, matching shortName() in the JS below. Any org not
# found here (new/renamed orgs, Special Needs, "Other") falls back to
# alphabetical -- see AgeRank handling in buildRows().
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


def classify_volunteer_bucket(name, org_id=None):
    # Org 3508 (CM: PS 8:30 Birth-5th Volunteers Scheduler) spans both the
    # Nursery/Kinder and Elementary buckets in one org, so its name alone
    # won't match either keyword rule below -- match by ID instead of text.
    if org_id == 3508:
        return "Nursery/Kinder"
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


# ============================================================
# Run query and serialize rows
# ============================================================
rows = []
for r in q.QuerySql(sql):
    campus = str(r.Campus or "")
    org_name = str(r.OrganizationName or "")
    org_id = int(r.OrganizationId or 0)
    person_type = str(r.PersonType or "")
    bucket = (
        classify_volunteer_bucket(org_name, org_id)
        if person_type == "Volunteers"
        else classify_age_group(org_name)
    )
    rows.append(
        {
            "Campus": campus,
            "PersonType": person_type,
            "Bucket": bucket,
            "AgeRank": age_rank(campus, bucket, org_name) if person_type == "Kids" else None,
            "MeetingDate": _norm_date(str(r.MeetingDate or "")),
            "OrganizationId": org_id,
            "OrganizationName": org_name,
            "Attendance": int(r.Attendance or 0),
        }
    )

json_data = json.dumps(rows)

subtitle = "{} to {} | {} rows".format(start_date, end_date, len(rows))

# ============================================================
# Output: full dashboard HTML with rawData injected.
# ============================================================
print(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CM Attendance Dashboard</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#f0f4f8;color:#1a202c;font-size:13px;line-height:1.5}
.topbar{background:#1a365d;color:white;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.topbar h1{font-size:15px;font-weight:700;letter-spacing:.3px}
.topbar-right{display:flex;gap:8px;align-items:center}
.topbar small{color:rgba(255,255,255,.55);font-size:11px;margin-left:12px}
.btn{padding:5px 13px;border-radius:5px;border:none;cursor:pointer;font-size:12px;font-weight:600;transition:background .15s}
.btn-ghost{background:rgba(255,255,255,.12);color:white}
.btn-ghost:hover{background:rgba(255,255,255,.22)}
.btn-ghost:disabled{opacity:.35;cursor:default}
.filters{background:white;border-bottom:1px solid #e2e8f0;padding:10px 24px;display:flex;flex-wrap:wrap;gap:14px;align-items:center;position:sticky;top:45px;z-index:90;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.filter-group{display:flex;align-items:center;gap:6px}
.filter-label{font-size:10px;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:.6px;white-space:nowrap}
.btn-group{display:flex;border-radius:5px;overflow:hidden;border:1px solid #e2e8f0}
.btn-toggle{padding:4px 10px;border:none;background:white;color:#4a5568;font-size:11px;font-weight:500;cursor:pointer;border-right:1px solid #e2e8f0;transition:background .12s,color .12s;white-space:nowrap}
.btn-toggle:last-child{border-right:none}
.btn-toggle.active{background:#2b6cb0;color:white;font-weight:700}
.btn-toggle:hover:not(.active):not(:disabled){background:#ebf8ff}
.btn-toggle:disabled{color:#cbd5e0;cursor:default}
.date-row{display:flex;gap:6px;align-items:center}
.date-row input[type="date"]{padding:3px 7px;border:1px solid #e2e8f0;border-radius:4px;font-size:11px;color:#2d3748}
.date-sep{color:#a0aec0;font-size:11px}
.stats-bar{display:flex;gap:24px;padding:9px 24px;background:#ebf8ff;border-bottom:1px solid #bee3f8;flex-wrap:wrap;align-items:center}
.stat{display:flex;flex-direction:column}
.stat-val{font-size:19px;font-weight:800;color:#2b6cb0;line-height:1.1}
.stat-lbl{font-size:10px;color:#4a5568;text-transform:uppercase;letter-spacing:.4px;margin-top:1px}
.stat-range{font-size:12px;font-weight:600;color:#2b6cb0}
.table-section{padding:16px 24px}
.table-wrapper{overflow-x:auto;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
table{border-collapse:collapse;width:100%;background:white}
thead th{background:#1a365d;color:white;padding:7px 10px;font-size:11px;font-weight:600;text-align:right;white-space:nowrap}
thead th.col-label{text-align:left;min-width:210px;background:#12263f}
thead th.col-total{background:#163155}
thead th.col-avg{background:#163155;color:rgba(255,255,255,.75)}
td{padding:4px 10px;border-bottom:1px solid #edf2f7;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
td.col-label{text-align:left}
td.col-total{font-weight:600}
td.col-avg{color:#718096}
.zero{color:#e2e8f0}
tr.r-campus td{background:#dbeafe;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.5px;padding:7px 10px;border-bottom:1px solid #bfdbfe}
tr.r-campus td.col-label{padding-left:12px}
tr.r-bucket td{background:#f0fdf4;font-weight:600;border-bottom:1px solid #dcfce7}
tr.r-bucket td.col-label{padding-left:20px}
tr.r-detail td{background:white}
tr.r-detail td.col-label{padding-left:36px;color:#2d3748}
tr.r-subtotal td{background:#dbeafe;font-weight:600;border-top:1px solid #bfdbfe;border-bottom:1px solid #bfdbfe}
tr.r-subtotal td.col-label{padding-left:20px}
tr.r-campus-total td{background:#bfdbfe;font-weight:700;border-top:2px solid #93c5fd;border-bottom:2px solid #93c5fd}
tr.r-campus-total td.col-label{padding-left:12px}
tr.r-vol-header td{background:#fffbeb;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.5px;padding:7px 10px;border-top:4px solid #e2e8f0;border-bottom:1px solid #fde68a}
tr.r-vol-campus td{background:#fefce8;font-weight:600}
tr.r-vol-campus td.col-label{padding-left:20px}
tr.r-vol-detail td{background:white}
tr.r-vol-detail td.col-label{padding-left:36px}
tr.r-vol-subtotal td{background:#fef9c3;font-weight:600}
tr.r-vol-subtotal td.col-label{padding-left:20px}
tr.r-grand td{background:#1a365d;color:white;font-weight:700;font-size:13px;padding:8px 10px;border-top:2px solid #2b6cb0}
tr.r-grand td.col-avg{color:rgba(255,255,255,.65)}
tr.r-spacer td{height:6px;background:#f0f4f8;border:none}
.empty-state{padding:60px;text-align:center;color:#a0aec0;background:white}
.empty-state p{margin-top:8px;font-size:12px}
</style>
</head>
<body>

<div class="topbar">
  <div>
    <h1>Children's Ministry Attendance</h1>
    <small id="topbarSub">"""
    + subtitle
    + """</small>
  </div>
  <div class="topbar-right">
    <button class="btn btn-ghost" id="exportBtn" onclick="exportCSV()">Export CSV</button>
  </div>
</div>

<div id="dashboard">
  <div class="filters">
    <div class="filter-group">
      <span class="filter-label">Campus</span>
      <div class="btn-group">
        <button class="btn-toggle active" onclick="setFilter('campus','all',this)">All</button>
        <button class="btn-toggle" onclick="setFilter('campus','Central',this)">Central</button>
        <button class="btn-toggle" onclick="setFilter('campus','Parker Square',this)">Parker Square</button>
      </div>
    </div>
    <div class="filter-group">
      <span class="filter-label">Type</span>
      <div class="btn-group">
        <button class="btn-toggle active" onclick="setFilter('personType','Kids',this)">Kids</button>
        <button class="btn-toggle" onclick="setFilter('personType','Volunteers',this)">Volunteers</button>
        <button class="btn-toggle" onclick="setFilter('personType','all',this)">Both</button>
      </div>
    </div>
    <div class="filter-group" id="bucketGroup">
      <span class="filter-label">Group</span>
      <div class="btn-group" id="bucketBtns">
        <button class="btn-toggle active" onclick="setFilter('bucket','all',this)">All</button>
        <button class="btn-toggle" onclick="setFilter('bucket','Preschool',this)">Preschool</button>
        <button class="btn-toggle" onclick="setFilter('bucket','Elementary',this)">Elementary</button>
        <button class="btn-toggle" onclick="setFilter('bucket','Special Needs',this)">Special Needs</button>
      </div>
    </div>
    <div class="filter-group">
      <span class="filter-label">Range</span>
      <div class="btn-group" id="presetBtns">
        <button class="btn-toggle" onclick="setPreset(4,this)">4 wk</button>
        <button class="btn-toggle" onclick="setPreset(6,this)">6 wk</button>
        <button class="btn-toggle" onclick="setPreset(8,this)">8 wk</button>
        <button class="btn-toggle active" onclick="setPreset('all',this)">All</button>
      </div>
      <div class="date-row">
        <input type="date" id="startDate" onchange="onCustomDate()">
        <span class="date-sep">to</span>
        <input type="date" id="endDate" onchange="onCustomDate()">
      </div>
    </div>
  </div>

  <div class="stats-bar" id="statsBar"></div>

  <div class="table-section">
    <div class="table-wrapper">
      <table>
        <thead id="thead"></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<script>
// ============================================================
// Injected data
// ============================================================
var rawData = """
    + json_data
    + """;

// ============================================================
// State
// ============================================================
var S = {
  campus: 'all',
  personType: 'Kids',
  bucket: 'all',
  startDate: null,
  endDate: null,
};

// ============================================================
// Filters
// ============================================================
function setFilter(key, val, btn) {
  S[key]=val;
  btn.closest('.btn-group').querySelectorAll('.btn-toggle').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  if (key==='personType') {
    var btns = document.querySelectorAll('#bucketBtns .btn-toggle');
    if (val==='Volunteers'){
      btns.forEach(function(b){b.disabled=true;b.classList.remove('active');});
      btns[0].classList.add('active');
      S.bucket='all';
    } else {
      btns.forEach(function(b){b.disabled=false;});
    }
  }
  render();
}

function setPreset(weeks, btn) {
  btn.closest('.btn-group').querySelectorAll('.btn-toggle').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  var dates=allDates(rawData);
  if(!dates.length)return;
  var end=dates[dates.length-1];
  var start=weeks==='all'?dates[0]:dates[Math.max(0,dates.length-weeks)];
  document.getElementById('startDate').value=start;
  document.getElementById('endDate').value=end;
  render();
}

function onCustomDate() {
  document.querySelectorAll('#presetBtns .btn-toggle').forEach(function(b){b.classList.remove('active');});
  render();
}

function filtered() {
  var s=document.getElementById('startDate').value;
  var e=document.getElementById('endDate').value;
  return rawData.filter(function(r){
    if(S.campus!=='all'&&r.Campus!==S.campus)return false;
    if(S.personType!=='all'&&r.PersonType!==S.personType)return false;
    if(S.bucket!=='all'&&r.PersonType==='Kids'&&r.Bucket!==S.bucket)return false;
    if(s&&r.MeetingDate<s)return false;
    if(e&&r.MeetingDate>e)return false;
    return true;
  });
}

// ============================================================
// Render
// ============================================================
function render() {
  var data=filtered();
  var dates=allDates(data);
  renderStats(data,dates);
  renderTable(data,dates);
}

function avgByDate(rows) {
  var byDate={};
  rows.forEach(function(r){byDate[r.MeetingDate]=(byDate[r.MeetingDate]||0)+r.Attendance;});
  var totals=Object.values(byDate);
  return {avg:totals.length?Math.round(totals.reduce(function(s,v){return s+v;},0)/totals.length):0,
          peak:totals.length?Math.max.apply(null,totals):0};
}

function renderStats(data,dates) {
  var s=dates[0],e=dates[dates.length-1];
  var kids=data.filter(function(r){return r.PersonType==='Kids';});
  var kidsAvg=avgByDate(kids);
  var totalVisits=kids.reduce(function(s,r){return s+r.Attendance;},0);
  var html='<div class="stat"><span class="stat-val">'+dates.length+'</span><span class="stat-lbl">dates loaded</span></div>'
         +'<div class="stat"><span class="stat-range">'+fmt(s)+' - '+fmt(e)+'</span><span class="stat-lbl">date range</span></div>';
  if(kids.length)
    html+='<div class="stat"><span class="stat-val">'+kidsAvg.avg+'</span><span class="stat-lbl">Sunday avg</span></div>'
        +'<div class="stat"><span class="stat-val">'+kidsAvg.peak+'</span><span class="stat-lbl">Sunday peak</span></div>';
  html+='<div class="stat"><span class="stat-val">'+totalVisits.toLocaleString()+'</span><span class="stat-lbl">total kid visits</span></div>';
  document.getElementById('statsBar').innerHTML=html;
}

function renderTable(data,dates) {
  if(!dates.length){
    document.getElementById('thead').innerHTML='';
    document.getElementById('tbody').innerHTML='<tr><td colspan="5" class="empty-state">No data matches the current filters.</td></tr>';
    return;
  }
  var n=dates.length;
  var thDates=dates.map(function(d){return '<th>'+fmt(d)+'</th>';}).join('');
  document.getElementById('thead').innerHTML='<tr><th class="col-label"></th>'+thDates+'<th class="col-total">Total</th><th class="col-avg">'+n+' Avg</th></tr>';
  var rows=buildRows(data,dates,n);
  document.getElementById('tbody').innerHTML=rows.map(function(r){
    if(r.type==='spacer')return '<tr class="r-spacer"><td colspan="'+(dates.length+3)+'"></td></tr>';
    var cells=dates.map(function(d){var v=r.byDate[d]||0;return '<td>'+(v===0?'<span class="zero">-</span>':v)+'</td>';}).join('');
    return '<tr class="r-'+r.type+'"><td class="col-label">'+r.label+'</td>'+cells+'<td class="col-total">'+(r.total||0)+'</td><td class="col-avg">'+(r.avg||0)+'</td></tr>';
  }).join('');
}

function buildRows(data,dates,n) {
  var rows=[];
  var showK=S.personType==='Kids'||S.personType==='all';
  var showV=S.personType==='Volunteers'||S.personType==='all';

  if(showK){
    var kd=data.filter(function(r){return r.PersonType==='Kids';});
    var kidCampuses=[...new Set(kd.map(function(r){return r.Campus;}))].filter(Boolean).sort();
    for(var ci=0;ci<kidCampuses.length;ci++){
      var campus=kidCampuses[ci];
      var cd=kd.filter(function(r){return r.Campus===campus;});
      if(!cd.length)continue;
      rows.push(mk('campus',campus,cd,dates,n));
      var buckets=['Preschool','Elementary','Special Needs'];
      for(var bi=0;bi<buckets.length;bi++){
        var bucket=buckets[bi];
        if(S.bucket!=='all'&&S.bucket!==bucket)continue;
        var bd=cd.filter(function(r){return r.Bucket===bucket;});
        if(!bd.length)continue;
        rows.push(mk('bucket',bucket,bd,dates,n));
        var orgs=sortByAgeRank(bd);
        for(var oi=0;oi<orgs.length;oi++){
          var org=orgs[oi];
          rows.push(mk('detail',prettyLabel(shortName(org)),bd.filter(function(r){return r.OrganizationName===org;}),dates,n));
        }
        rows.push(mk('subtotal',bucket+' Total',bd,dates,n));
      }
      rows.push(mk('campus-total',campus+' Kids',cd,dates,n));
    }
    if(kidCampuses.length>1&&S.campus==='all'){
      rows.push(mk('grand','Grand Total (Kids)',kd,dates,n));
    }
  }

  if(showV){
    var vd=data.filter(function(r){return r.PersonType==='Volunteers';});
    if(vd.length){
      rows.push({type:'spacer'});
      rows.push(mk('vol-header','Volunteers',vd,dates,n));
      var volCampuses=[...new Set(vd.map(function(r){return r.Campus;}))].filter(Boolean).sort();
      for(var vc=0;vc<volCampuses.length;vc++){
        var vcampus=volCampuses[vc];
        var cvd=vd.filter(function(r){return r.Campus===vcampus;});
        if(!cvd.length)continue;
        rows.push(mk('vol-campus',vcampus,cvd,dates,n));
        var vorgs=sortVolunteerOrgs(cvd);
        for(var voi=0;voi<vorgs.length;voi++){
          var vo=vorgs[voi];
          rows.push(mk('vol-detail',prettyLabel(shortName(vo)),cvd.filter(function(r){return r.OrganizationName===vo;}),dates,n));
        }
        rows.push(mk('vol-subtotal',vcampus+' Total',cvd,dates,n));
      }
      if(volCampuses.length>1&&S.campus==='all'){
        rows.push(mk('grand','Volunteer Total',vd,dates,n));
      }
    }
  }
  return rows;
}

function mk(type,label,data,dates,n){
  var byDate={};
  dates.forEach(function(d){byDate[d]=data.filter(function(r){return r.MeetingDate===d;}).reduce(function(s,r){return s+r.Attendance;},0);});
  var total=Object.values(byDate).reduce(function(s,v){return s+v;},0);
  var avg=n>0?Math.round(total/n):0;
  return{type:type,label:label,byDate:byDate,total:total,avg:avg};
}

function sortByAgeRank(rows){
  var rankOf={};
  rows.forEach(function(r){rankOf[r.OrganizationName]=r.AgeRank;});
  return [...new Set(rows.map(function(r){return r.OrganizationName;}))].sort(function(a,b){
    var ra=rankOf[a], rb=rankOf[b];
    // _AGE_ORDER has no Special Needs table (no age progression to rank), so
    // AgeRank is null there -- fall back to service time instead of
    // alphabetical, which would sort "10:45 ..." before "9:00 ..." since "1"
    // < "9" as text.
    if(ra!=null && rb!=null) return ra-rb;
    if(ra!=null) return -1;
    if(rb!=null) return 1;
    var ta=volunteerTimeMinutes(a), tb=volunteerTimeMinutes(b);
    if(ta!==tb) return ta-tb;
    return a<b?-1:a>b?1:0;
  });
}

// CM staff's TouchPoint org-naming conventions are inconsistent ("9:00a" vs
// "10:45 AM" vs "9:00 a", "Volunteer" vs "Volunteers", a trailing school-year
// suffix) -- this only cleans up the on-screen label; grouping/sorting and
// CSV export still use the raw OrganizationName untouched.
function prettyLabel(name){
  name = name.replace(/^(\\d{1,2}):(\\d{2})\\s*a\\.?m?\\.?\\s*/i, function(_, h, m){ return h+':'+m+' AM '; });
  name = name.replace(/\\bVolunteers?\\b\\s*/i, '');
  name = name.replace(/\\s*\\d{4}-\\d{4}\\s*$/, '');
  return name.replace(/\\s{2,}/g, ' ').trim();
}

var VOLUNTEER_BUCKET_ORDER = {'Nursery/Kinder':0, 'Elementary':1, 'Special Needs':2, 'Welcome Team':3, 'Other':4};

function volunteerTimeMinutes(name){
  var m = name.match(/(\\d{1,2}):(\\d{2})/);
  return m ? (parseInt(m[1],10)*60 + parseInt(m[2],10)) : 9999;
}

function sortVolunteerOrgs(rows){
  var infoOf={};
  rows.forEach(function(r){
    if(!infoOf[r.OrganizationName]){
      infoOf[r.OrganizationName]={
        bucket: VOLUNTEER_BUCKET_ORDER.hasOwnProperty(r.Bucket) ? VOLUNTEER_BUCKET_ORDER[r.Bucket] : 5,
        time: volunteerTimeMinutes(r.OrganizationName),
      };
    }
  });
  return [...new Set(rows.map(function(r){return r.OrganizationName;}))].sort(function(a,b){
    var ia=infoOf[a], ib=infoOf[b];
    if(ia.bucket!==ib.bucket)return ia.bucket-ib.bucket;
    if(ia.time!==ib.time)return ia.time-ib.time;
    return a<b?-1:a>b?1:0;
  });
}

function allDates(data){
  return[...new Set(data.map(function(r){return r.MeetingDate;}))].filter(Boolean).sort();
}

function fmt(dateStr){
  if(!dateStr)return'';
  var parts=dateStr.split('-').map(Number);
  var months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return months[parts[1]-1]+' '+parts[2];
}

function shortName(org){
  return org.replace(/^CM: (CC|PS) /,'');
}

function exportCSV(){
  var data=filtered();
  var cols=['Campus','PersonType','Bucket','MeetingDate','OrganizationName','Attendance'];
  var csv=[cols.join(',')].concat(data.map(function(r){return cols.map(function(c){return JSON.stringify(r[c]!=null?r[c]:'');}).join(',');})).join('\\n');
  var a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
  a.download='cm-attendance-'+new Date().toISOString().slice(0,10)+'.csv';
  a.click();
}

// ============================================================
// Boot
// ============================================================
(function(){
  var dates=allDates(rawData);
  document.getElementById('startDate').value=dates[0]||'';
  document.getElementById('endDate').value=dates[dates.length-1]||'';
  render();
})();
</script>
</body>
</html>"""
)
