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
# SQL  (config block resolved from Python; date preset logic removed)
# ============================================================
sql = """
SET DATEFIRST 7

DECLARE @ProgramId        INT          = 1109
DECLARE @SundayDivId      INT          = 11
DECLARE @WednesdayDivId   INT          = 42
DECLARE @StudentTypeId    INT          = 201
DECLARE @VolunteerTypeId  INT          = 207
DECLARE @WedGradeTypeId   INT          = 205
DECLARE @GuestTypeId      INT          = 310
DECLARE @StartDate        DATE         = '{start}'
DECLARE @EndDate          DATE         = '{end}'
DECLARE @IncludeSunday    BIT          = {sun}
DECLARE @IncludeWednesday BIT          = {wed}
DECLARE @CampusFilter     VARCHAR(20)  = '{campus}'
DECLARE @CCPrefix         VARCHAR(10)  = 'SM: CC '
DECLARE @PSPrefix         VARCHAR(10)  = 'SM: PS '

SELECT
    Campus = CASE
        WHEN o.OrganizationName LIKE @CCPrefix + '%' THEN 'Central'
        WHEN o.OrganizationName LIKE @PSPrefix + '%' THEN 'Parker Square'
        ELSE 'Other'
    END,
    PersonType = CASE o.OrganizationTypeId
        WHEN @StudentTypeId   THEN 'Students'
        WHEN @VolunteerTypeId THEN 'Volunteers'
        WHEN @WedGradeTypeId  THEN 'Students'
        ELSE 'Other'
    END,
    SchoolLevel = CASE
        WHEN o.OrganizationTypeId = @VolunteerTypeId             THEN ''
        WHEN pg.Grade IN ('6th','7th','8th')                     THEN 'Middle School'
        WHEN pg.Grade = 'Middle School Off Hour'                  THEN 'Middle School'
        WHEN pg.Grade IN ('9th','10th','11th','12th')            THEN 'High School'
        WHEN pg.Grade = 'High School Off Hour'                    THEN 'High School'
        ELSE 'Other'
    END,
    Grade = CASE
        WHEN o.OrganizationTypeId = @VolunteerTypeId THEN ''
        ELSE pg.Grade
    END,
    GradeOrder = CASE
        WHEN o.OrganizationTypeId = @VolunteerTypeId THEN 0
        ELSE CASE pg.Grade
            WHEN '6th'                    THEN 1
            WHEN '7th'                    THEN 2
            WHEN '8th'                    THEN 3
            WHEN '9th'                    THEN 4
            WHEN '10th'                   THEN 5
            WHEN '11th'                   THEN 6
            WHEN '12th'                   THEN 7
            WHEN 'Middle School Off Hour' THEN 8
            WHEN 'High School Off Hour'   THEN 9
            ELSE 99
        END
    END,
    Gender = pg.Gender,
    DayOfWeek = CASE DATEPART(dw, m.MeetingDate)
        WHEN 1 THEN 'Sunday'
        WHEN 4 THEN 'Wednesday'
        ELSE DATENAME(weekday, m.MeetingDate)
    END,
    MeetingDate      = CAST(m.MeetingDate AS DATE),
    OrganizationId   = o.OrganizationId,
    OrganizationName = o.OrganizationName,
    Category = CASE
        WHEN EXISTS (SELECT 1 FROM dbo.DivOrg dc WHERE dc.OrgId = o.OrganizationId AND dc.DivId = @SundayDivId)
            THEN 'Sunday'
        WHEN EXISTS (SELECT 1 FROM dbo.DivOrg dc WHERE dc.OrgId = o.OrganizationId AND dc.DivId = @WednesdayDivId)
            THEN 'D-Groups'
        ELSE 'Other'
    END,
    Attendance = ISNULL(m.NumPresent, 0),
    Guests = ISNULL((
        SELECT COUNT(*)
        FROM dbo.Attend att
        WHERE att.MeetingId = m.MeetingId
          AND ISNULL(att.AttendanceFlag, 0) = 1
          AND att.MemberTypeId = @GuestTypeId
    ), 0)

FROM dbo.Organizations o

CROSS APPLY (
    SELECT Remainder = LTRIM(SUBSTRING(o.OrganizationName, 8, 200))
) rm

CROSS APPLY (
    SELECT AfterWed = CASE
        WHEN rm.Remainder LIKE 'WED %' THEN SUBSTRING(rm.Remainder, 5, 200)
        ELSE rm.Remainder
    END
) wd

CROSS APPLY (
    SELECT
        Grade = CASE
            WHEN RIGHT(RTRIM(wd.AfterWed), 5) = ' Guys'  THEN RTRIM(LEFT(RTRIM(wd.AfterWed), LEN(RTRIM(wd.AfterWed)) - 5))
            WHEN RIGHT(RTRIM(wd.AfterWed), 6) = ' Girls' THEN RTRIM(LEFT(RTRIM(wd.AfterWed), LEN(RTRIM(wd.AfterWed)) - 6))
            WHEN RIGHT(RTRIM(wd.AfterWed), 5) = ' Boys'  THEN RTRIM(LEFT(RTRIM(wd.AfterWed), LEN(RTRIM(wd.AfterWed)) - 5))
            ELSE RTRIM(wd.AfterWed)
        END,
        Gender = CASE
            WHEN RIGHT(RTRIM(wd.AfterWed), 5) = ' Guys'  THEN 'Guys'
            WHEN RIGHT(RTRIM(wd.AfterWed), 6) = ' Girls' THEN 'Girls'
            WHEN RIGHT(RTRIM(wd.AfterWed), 5) = ' Boys'  THEN 'Guys'
            ELSE ''
        END
) pg

JOIN dbo.Meetings m
    ON  m.OrganizationId = o.OrganizationId
    AND CAST(m.MeetingDate AS DATE) BETWEEN @StartDate AND @EndDate

WHERE
    o.OrganizationStatusId = 30
    AND o.OrganizationName <> 'SM: SLT 26-27'
    AND (
        o.OrganizationName LIKE @CCPrefix + '%'
        OR o.OrganizationName LIKE @PSPrefix + '%'
        -- D-Group orgs don't all follow the 'SM: CC '/'SM: PS ' naming convention
        -- (e.g. "SM: Identity: Daughters of the King ...", "SM: Man Up ...") --
        -- include any Wednesday-division org regardless of name so these aren't
        -- silently dropped. Sunday-side inclusion is unaffected.
        OR EXISTS (
            SELECT 1 FROM dbo.DivOrg dwn
            WHERE dwn.OrgId = o.OrganizationId AND dwn.DivId = @WednesdayDivId
        )
    )
    AND (
           @CampusFilter = 'ALL'
        OR (@CampusFilter = 'CENTRAL'      AND o.OrganizationName LIKE @CCPrefix + '%')
        OR (@CampusFilter = 'PARKERSQUARE' AND o.OrganizationName LIKE @PSPrefix + '%')
    )
    AND o.OrganizationTypeId IN (@StudentTypeId, @VolunteerTypeId, @WedGradeTypeId)
    AND EXISTS (
        SELECT 1
        FROM dbo.DivOrg do2
        JOIN dbo.Division d ON d.Id = do2.DivId
        WHERE do2.OrgId = o.OrganizationId
          AND d.ProgId  = @ProgramId
    )
    AND (
        (
            @IncludeSunday = 1
            AND EXISTS (
                SELECT 1 FROM dbo.DivOrg ds
                WHERE ds.OrgId = o.OrganizationId AND ds.DivId = @SundayDivId
            )
        )
        OR (
            @IncludeWednesday = 1
            AND EXISTS (
                SELECT 1 FROM dbo.DivOrg dw
                WHERE dw.OrgId = o.OrganizationId AND dw.DivId = @WednesdayDivId
            )
        )
    )

ORDER BY Campus, PersonType, SchoolLevel, GradeOrder, Gender, MeetingDate
""".format(
    start=start_date,
    end=end_date,
    sun=inc_sunday,
    wed=inc_wednesday,
    campus=campus_filter,
)


# ============================================================
# Helpers
# ============================================================
def _norm_date(s):
    """Normalize any date string to YYYY-MM-DD for JS consumption."""
    s = s.split(" ")[0].split("T")[0].strip()  # strip time component
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # M/D/YYYY or MM/DD/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return "{}-{}-{}".format(m.group(3), m.group(1).zfill(2), m.group(2).zfill(2))
    return s


# ============================================================
# Run query and serialize rows
# ============================================================
rows = []
for r in q.QuerySql(sql):
    rows.append(
        {
            "Campus": str(r.Campus or ""),
            "PersonType": str(r.PersonType or ""),
            "SchoolLevel": str(r.SchoolLevel or ""),
            "Grade": str(r.Grade or ""),
            "GradeOrder": int(r.GradeOrder or 0),
            "Gender": str(r.Gender or ""),
            "DayOfWeek": str(r.DayOfWeek or ""),
            "MeetingDate": _norm_date(str(r.MeetingDate or "")),
            "OrganizationId": int(r.OrganizationId or 0),
            "OrganizationName": str(r.OrganizationName or ""),
            "Category": str(r.Category or "Sunday"),
            "Attendance": int(r.Attendance or 0),
            "Guests": int(r.Guests or 0),
        }
    )

json_data = json.dumps(rows)

# Label shown in the top bar
subtitle = "{} to {} | {} rows".format(start_date, end_date, len(rows))

# ============================================================
# Output: full dashboard HTML with rawData injected.
# The upload screen is hidden; the dashboard renders immediately.
# ============================================================
print(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SM Attendance Dashboard</title>
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
/* One neutral hierarchy for every section (Sunday/D-Groups x Students/Volunteers):
   r-top = section header, r-node = a grouping level (e.g. Campus, School),
   r-total = that group's subtotal, r-leaf = a detail row, r-grand = the section's
   final rollup. Depth (d1/d2/d3) controls indentation only, independent of kind,
   so every section shares the same visual language regardless of its shape. */
tr.r-top td{background:#1e293b;color:white;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.5px;padding:7px 10px;border-top:4px solid #e2e8f0}
tr.r-top td.col-label{padding-left:10px}
tr.r-node td{font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.4px;padding:6px 10px}
tr.d1.r-node td{background:#e2e8f0}
tr.d2.r-node td{background:#eef2f6}
tr.r-total td{background:#dbeafe;font-weight:700;border-top:1px solid #bfdbfe;border-bottom:1px solid #bfdbfe}
tr.r-leaf td{background:white;color:#2d3748}
tr.r-leaf-alt td{background:#fafafa;color:#718096;font-style:italic}
tr.d1 td.col-label{padding-left:14px}
tr.d2 td.col-label{padding-left:22px}
tr.d3 td.col-label{padding-left:36px}
tr.r-grand td{background:#1a365d;color:white;font-weight:700;font-size:13px;padding:8px 10px;border-top:2px solid #2b6cb0}
tr.r-grand td.col-label{padding-left:10px}
tr.r-grand td.col-avg{color:rgba(255,255,255,.65)}
tr.r-spacer td{height:6px;background:#f0f4f8;border:none}
.empty-state{padding:60px;text-align:center;color:#a0aec0;background:white}
.empty-state p{margin-top:8px;font-size:12px}
</style>
</head>
<body>

<div class="topbar">
  <div>
    <h1>Student Ministry Attendance</h1>
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
        <button class="btn-toggle active" onclick="setFilter('personType','Students',this)">Students</button>
        <button class="btn-toggle" onclick="setFilter('personType','Volunteers',this)">Volunteers</button>
        <button class="btn-toggle" onclick="setFilter('personType','all',this)">Both</button>
      </div>
    </div>
    <div class="filter-group" id="schoolGroup">
      <span class="filter-label">School</span>
      <div class="btn-group" id="schoolBtns">
        <button class="btn-toggle active" onclick="setFilter('schoolLevel','all',this)">All</button>
        <button class="btn-toggle" onclick="setFilter('schoolLevel','Middle School',this)">Middle</button>
        <button class="btn-toggle" onclick="setFilter('schoolLevel','High School',this)">High School</button>
      </div>
    </div>
    <div class="filter-group">
      <span class="filter-label">Day</span>
      <div class="btn-group">
        <button class="btn-toggle active" onclick="setFilter('dayOfWeek','all',this)">All</button>
        <button class="btn-toggle" onclick="setFilter('dayOfWeek','Sunday',this)">Sunday</button>
        <button class="btn-toggle" onclick="setFilter('dayOfWeek','Wednesday',this)">Wednesday</button>
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
  personType: 'Students',
  schoolLevel: 'all',
  dayOfWeek: 'all',
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
    var btns = document.querySelectorAll('#schoolBtns .btn-toggle');
    if (val==='Volunteers'){
      btns.forEach(function(b){b.disabled=true;b.classList.remove('active');});
      btns[0].classList.add('active');
      S.schoolLevel='all';
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
    if(S.schoolLevel!=='all'&&r.PersonType==='Students'&&r.SchoolLevel!==S.schoolLevel)return false;
    if(S.dayOfWeek!=='all'&&r.DayOfWeek!==S.dayOfWeek)return false;
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
  var showSun=S.dayOfWeek==='all'||S.dayOfWeek==='Sunday';
  var showWed=S.dayOfWeek==='all'||S.dayOfWeek==='Wednesday';
  var sunStudents=data.filter(function(r){return r.PersonType==='Students'&&r.Category==='Sunday';});
  var dgStudents =data.filter(function(r){return r.PersonType==='Students'&&r.Category==='D-Groups';});
  var sun=avgByDate(sunStudents);
  var dg =avgByDate(dgStudents);
  var totalVisits=data.filter(function(r){return r.PersonType==='Students';}).reduce(function(s,r){return s+r.Attendance;},0);
  var html='<div class="stat"><span class="stat-val">'+dates.length+'</span><span class="stat-lbl">dates loaded</span></div>'
         +'<div class="stat"><span class="stat-range">'+fmt(s)+' - '+fmt(e)+'</span><span class="stat-lbl">date range</span></div>';
  if(showSun&&sunStudents.length)
    html+='<div class="stat"><span class="stat-val">'+sun.avg+'</span><span class="stat-lbl">Sunday avg</span></div>'
        +'<div class="stat"><span class="stat-val">'+sun.peak+'</span><span class="stat-lbl">Sunday peak</span></div>';
  if(showWed&&dgStudents.length)
    html+='<div class="stat"><span class="stat-val">'+dg.avg+'</span><span class="stat-lbl">D-Group avg</span></div>'
        +'<div class="stat"><span class="stat-val">'+dg.peak+'</span><span class="stat-lbl">D-Group peak</span></div>';
  html+='<div class="stat"><span class="stat-val">'+totalVisits.toLocaleString()+'</span><span class="stat-lbl">total student visits</span></div>';
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

// One config entry per section. `levels` declares which grouping tiers apply --
// 'campus' then optionally 'school' -- so the SAME render loop below produces
// every section's shape instead of a hand-built block per section.
var SECTIONS=[
  {category:'Sunday',   personType:'Students',   label:'Sunday Students',    levels:['campus','school']},
  {category:'D-Groups', personType:'Students',   label:'D-Groups',           levels:[]},
  {category:'Sunday',   personType:'Volunteers', label:'Sunday Volunteers',  levels:['campus']},
  {category:'D-Groups', personType:'Volunteers', label:'D-Group Volunteers', levels:[]},
];

function buildRows(data,dates,n) {
  var rows=[];
  var showS=S.personType==='Students'||S.personType==='all';
  var showV=S.personType==='Volunteers'||S.personType==='all';
  var showSun=S.dayOfWeek==='all'||S.dayOfWeek==='Sunday';
  var showWed=S.dayOfWeek==='all'||S.dayOfWeek==='Wednesday';

  SECTIONS.forEach(function(cfg){
    if(cfg.category==='Sunday'   && !showSun) return;
    if(cfg.category==='D-Groups' && !showWed) return;
    if(cfg.personType==='Students'   && !showS) return;
    if(cfg.personType==='Volunteers' && !showV) return;

    var subset=data.filter(function(r){return r.PersonType===cfg.personType && r.Category===cfg.category;});
    if(!subset.length) return;

    if(rows.length) rows.push({type:'spacer'});
    rows.push(mk('top',cfg.label,subset,dates,n));

    var hasCampus=cfg.levels.indexOf('campus')>=0;
    var hasSchool=cfg.levels.indexOf('school')>=0;
    var topGroups=hasCampus
      ? [...new Set(subset.map(function(r){return r.Campus;}))].filter(Boolean).sort()
      : [null];

    for(var gi=0;gi<topGroups.length;gi++){
      var groupKey=topGroups[gi];
      var gd=hasCampus ? subset.filter(function(r){return r.Campus===groupKey;}) : subset;
      if(!gd.length) continue;
      if(hasCampus) rows.push(mk('node d1',groupKey,gd,dates,n));

      if(hasSchool){
        var sls=['Middle School','High School'];
        for(var si=0;si<sls.length;si++){
          var sl=sls[si];
          if(S.schoolLevel!=='all'&&S.schoolLevel!==sl)continue;
          var sld=gd.filter(function(r){return r.SchoolLevel===sl;});
          if(!sld.length)continue;
          rows.push(mk('node d2',sl,sld,dates,n));
          var combos=gradeCombos(sld);
          for(var ci=0;ci<combos.length;ci++){
            var grade=combos[ci][0],gender=combos[ci][1];
            var dd=sld.filter(function(r){return r.Grade===grade&&r.Gender===gender;});
            if(!dd.length)continue;
            rows.push(mk('leaf d3',gender?grade+' '+gender:grade,dd,dates,n));
          }
          rows.push(mk('total d2',sl+' Total',sld,dates,n));
        }
        if(S.schoolLevel==='all'){
          var od=gd.filter(function(r){return r.SchoolLevel==='Other'||!r.SchoolLevel;});
          if(od.length){
            var oorgs=[...new Set(od.map(function(r){return r.OrganizationName;}))].sort();
            for(var ooi=0;ooi<oorgs.length;ooi++){
              var oorg=oorgs[ooi];
              rows.push(mk('leaf-alt d2',shortName(oorg),od.filter(function(r){return r.OrganizationName===oorg;}),dates,n));
            }
          }
        }
      } else {
        var orgs=[...new Set(gd.map(function(r){return r.OrganizationName;}))].sort();
        var leafDepth=hasCampus?'d2':'d1';
        for(var oi=0;oi<orgs.length;oi++){
          var org=orgs[oi];
          rows.push(mk('leaf '+leafDepth,shortName(org),gd.filter(function(r){return r.OrganizationName===org;}),dates,n));
        }
      }

      if(hasCampus) rows.push(mk('total d1',groupKey+' Total',gd,dates,n));
    }

    var showGrand=hasCampus
      ? topGroups.length>1
      : (new Set(subset.map(function(r){return r.OrganizationName;}))).size>1;
    if(showGrand){
      rows.push(mk('grand',cfg.label+' Total',subset,dates,n));
    }
  });

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

function gradeCombos(data){
  var seen=new Map();
  data.forEach(function(r){
    var k=r.GradeOrder+'|'+r.Grade+'|'+r.Gender;
    if(!seen.has(k))seen.set(k,[r.GradeOrder,r.Grade,r.Gender]);
  });
  return[...seen.values()]
    .sort(function(a,b){return a[0]-b[0]||a[2].localeCompare(b[2]);})
    .map(function(v){return[v[1],v[2]];});
}

function fmt(dateStr){
  if(!dateStr)return'';
  var parts=dateStr.split('-').map(Number);
  var months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return months[parts[1]-1]+' '+parts[2];
}

function shortName(org){
  return org.replace(/^SM: (CC|PS) /,'');
}

function exportCSV(){
  var data=filtered();
  var cols=['Campus','PersonType','SchoolLevel','Grade','Gender','DayOfWeek','MeetingDate','OrganizationName','Category','Attendance','Guests'];
  var csv=[cols.join(',')].concat(data.map(function(r){return cols.map(function(c){return JSON.stringify(r[c]!=null?r[c]:'');}).join(',');})).join('\\n');
  var a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
  a.download='sm-attendance-'+new Date().toISOString().slice(0,10)+'.csv';
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
