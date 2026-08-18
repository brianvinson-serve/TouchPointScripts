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
    AND EXISTS (
        SELECT 1
        FROM dbo.DivOrg dp
        JOIN dbo.Division d ON d.Id = dp.DivId
        WHERE dp.OrgId = o.OrganizationId
          AND d.ProgId  = @ProgramId
    )
    AND EXISTS (
        SELECT 1
        FROM dbo.DivOrg dr
        WHERE dr.OrgId = o.OrganizationId
          AND dr.DivId IN (@CCReportingDivId, @PSReportingDivId)
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
# matters: Special Needs is checked before Preschool/Elementary.
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


# ============================================================
# Run query and serialize rows
# ============================================================
rows = []
for r in q.QuerySql(sql):
    org_name = str(r.OrganizationName or "")
    person_type = str(r.PersonType or "")
    bucket = (
        classify_volunteer_bucket(org_name)
        if person_type == "Volunteers"
        else classify_age_group(org_name)
    )
    rows.append(
        {
            "Campus": str(r.Campus or ""),
            "PersonType": person_type,
            "Bucket": bucket,
            "MeetingDate": _norm_date(str(r.MeetingDate or "")),
            "OrganizationId": int(r.OrganizationId or 0),
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
        <button class="btn-toggle" onclick="setPreset(8,this)">8 wk</button>
        <button class="btn-toggle" onclick="setPreset(13,this)">13 wk</button>
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
  document.getElementById('thead').innerHTML='<tr><th class="col-label">Row</th>'+thDates+'<th class="col-total">Total</th><th class="col-avg">'+n+' Avg</th></tr>';
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
        var orgs=[...new Set(bd.map(function(r){return r.OrganizationName;}))].sort();
        for(var oi=0;oi<orgs.length;oi++){
          var org=orgs[oi];
          rows.push(mk('detail',shortName(org),bd.filter(function(r){return r.OrganizationName===org;}),dates,n));
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
        var vorgs=[...new Set(cvd.map(function(r){return r.OrganizationName;}))].sort();
        for(var voi=0;voi<vorgs.length;voi++){
          var vo=vorgs[voi];
          rows.push(mk('vol-detail',shortName(vo),cvd.filter(function(r){return r.OrganizationName===vo;}),dates,n));
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
