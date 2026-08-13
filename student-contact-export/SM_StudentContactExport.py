# TouchPoint Python Script: SM_StudentContactExport
#
# Read-only Student Ministry attendance/contact report for RockPointe Church.
# Defaults to the last 90 days, excludes volunteer involvements, filters attendance
# in the browser, and exports one CSV row per student.
#
# TouchPoint runtime: uses model.Data and q.QuerySql; no third-party packages.

import json
import re
from datetime import datetime, timedelta


PROGRAM_ID = 1109
VOLUNTEER_ORG_TYPE_ID = 207
VOLUNTEER_ORG_NAME_PATTERN = "SM: All Volunteers%"
DEFAULT_DAYS = 90
MAX_RANGE_DAYS = 366


def safe_date(value, fallback):
    value = (value or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return fallback


def normalize_date(value):
    value = str(value or "").strip().replace("\u202f", " ")
    value = value.split("T")[0].split(" ")[0]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if match:
        return "{}-{}-{}".format(
            match.group(3), match.group(1).zfill(2), match.group(2).zfill(2)
        )
    return value


def text(value):
    return str(value or "").strip()


def number(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


today = datetime.now().date()
def_start = (today - timedelta(days=DEFAULT_DAYS)).isoformat()
def_end = today.isoformat()
data = model.Data
start_date = safe_date(getattr(data, "StartDate", ""), def_start)
end_date = safe_date(getattr(data, "EndDate", ""), def_end)

start_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
end_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
if end_obj < start_obj:
    start_date, end_date = end_date, start_date
    start_obj, end_obj = end_obj, start_obj
if (end_obj - start_obj).days > MAX_RANGE_DAYS:
    start_obj = end_obj - timedelta(days=MAX_RANGE_DAYS)
    start_date = start_obj.isoformat()

sql = """
SET DATEFIRST 7

DECLARE @ProgramId INT = {program_id}
DECLARE @VolunteerOrgTypeId INT = {volunteer_type_id}
DECLARE @VolunteerOrgNamePattern VARCHAR(100) = '{volunteer_org_name_pattern}'
DECLARE @StartDate DATE = '{start_date}'
DECLARE @EndDate DATE = '{end_date}'

SELECT
    StudentPeopleId = p.PeopleId,
    StudentName = LTRIM(RTRIM(COALESCE(NULLIF(p.PreferredName, ''), NULLIF(p.NickName, ''), p.FirstName, '') + ' ' + COALESCE(p.LastName, ''))),
    StudentEmail = COALESCE(NULLIF(LTRIM(RTRIM(p.EmailAddress)), ''), NULLIF(LTRIM(RTRIM(p.EmailAddress2)), ''), ''),
    Grade = COALESCE(NULLIF(gl.Code, ''), NULLIF(gl.Description, ''), NULLIF(CONVERT(VARCHAR(20), p.Grade), ''), ''),
    Gender = COALESCE(NULLIF(g.Description, ''), NULLIF(g.Code, ''), ''),
    FamilyId = ISNULL(p.FamilyId, 0),
    HouseholdName = CASE
        WHEN hoh.PeopleId IS NULL AND spouse.PeopleId IS NULL THEN ''
        WHEN hoh.PeopleId IS NOT NULL AND spouse.PeopleId IS NOT NULL
             AND ISNULL(hoh.LastName, '') = ISNULL(spouse.LastName, '')
            THEN LTRIM(RTRIM(ISNULL(hoh.LastName, ''))) + ' Household'
        WHEN hoh.PeopleId IS NOT NULL AND spouse.PeopleId IS NOT NULL
            THEN LTRIM(RTRIM(ISNULL(hoh.LastName, '') + ' / ' + ISNULL(spouse.LastName, ''))) + ' Household'
        ELSE LTRIM(RTRIM(COALESCE(hoh.LastName, spouse.LastName, ''))) + ' Household'
    END,
    ParentGuardian1Name = CASE WHEN hoh.PeopleId IS NULL THEN '' ELSE LTRIM(RTRIM(COALESCE(NULLIF(hoh.PreferredName, ''), NULLIF(hoh.NickName, ''), hoh.FirstName, '') + ' ' + COALESCE(hoh.LastName, ''))) END,
    ParentGuardian1Email = CASE WHEN hoh.PeopleId IS NULL THEN '' ELSE COALESCE(NULLIF(LTRIM(RTRIM(hoh.EmailAddress)), ''), NULLIF(LTRIM(RTRIM(hoh.EmailAddress2)), ''), '') END,
    ParentGuardian2Name = CASE WHEN spouse.PeopleId IS NULL THEN '' ELSE LTRIM(RTRIM(COALESCE(NULLIF(spouse.PreferredName, ''), NULLIF(spouse.NickName, ''), spouse.FirstName, '') + ' ' + COALESCE(spouse.LastName, ''))) END,
    ParentGuardian2Email = CASE WHEN spouse.PeopleId IS NULL THEN '' ELSE COALESCE(NULLIF(LTRIM(RTRIM(spouse.EmailAddress)), ''), NULLIF(LTRIM(RTRIM(spouse.EmailAddress2)), ''), '') END,
    Campus = COALESCE(
        NULLIF(orgCampus.Description, ''),
        NULLIF(orgCampus.Code, ''),
        CASE
            WHEN o.OrganizationName LIKE 'SM: CC %' THEN 'Central'
            WHEN o.OrganizationName LIKE 'SM: PS %' THEN 'Parker Square'
            ELSE 'Other / Unassigned'
        END
    ),
    ActivityCategory = COALESCE(activity.ActivityCategory, 'Other SM'),
    OrganizationName = o.OrganizationName,
    MeetingDate = CAST(a.MeetingDate AS DATE)
FROM dbo.Attend a
JOIN dbo.People p ON p.PeopleId = a.PeopleId
JOIN dbo.Organizations o ON o.OrganizationId = a.OrganizationId
LEFT JOIN dbo.Families f ON f.FamilyId = p.FamilyId
LEFT JOIN dbo.People hoh ON hoh.PeopleId = f.HeadOfHouseholdId
LEFT JOIN dbo.People spouse ON spouse.PeopleId = f.HeadOfHouseholdSpouseId
LEFT JOIN lookup.GradeLevel gl ON gl.Id = p.GradeLevelId
LEFT JOIN lookup.Gender g ON g.Id = p.GenderId
LEFT JOIN lookup.Campus orgCampus ON orgCampus.Id = o.CampusId
OUTER APPLY (
    SELECT TOP 1
        ActivityCategory = CASE d.Id
            WHEN 11 THEN 'Sunday'
            WHEN 42 THEN 'Wednesday / D-Groups'
            WHEN 21 THEN 'Events'
            WHEN 45 THEN 'Mission Trips'
            WHEN 12 THEN 'Classes'
            WHEN 108 THEN 'SM Admin'
            ELSE d.Name
        END,
        SortOrder = CASE d.Id
            WHEN 11 THEN 1 WHEN 42 THEN 2 WHEN 21 THEN 3
            WHEN 45 THEN 4 WHEN 12 THEN 5 WHEN 108 THEN 9 ELSE 8
        END
    FROM dbo.DivOrg divisionLink
    JOIN dbo.Division d ON d.Id = divisionLink.DivId
    WHERE divisionLink.OrgId = o.OrganizationId
      AND d.ProgId = @ProgramId
    ORDER BY
        CASE d.Id
            WHEN 11 THEN 1 WHEN 42 THEN 2 WHEN 21 THEN 3
            WHEN 45 THEN 4 WHEN 12 THEN 5 WHEN 108 THEN 9 ELSE 8
        END,
        d.Id
) activity
WHERE
    a.AttendanceFlag = 1
    AND ISNULL(a.NoShow, 0) = 0
    AND CAST(a.MeetingDate AS DATE) BETWEEN @StartDate AND @EndDate
    AND o.OrganizationTypeId <> @VolunteerOrgTypeId
    AND activity.ActivityCategory IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM dbo.OrganizationMembers volunteerMember
        JOIN dbo.Organizations volunteerOrg
          ON volunteerOrg.OrganizationId = volunteerMember.OrganizationId
        WHERE volunteerMember.PeopleId = p.PeopleId
          AND volunteerOrg.OrganizationName LIKE @VolunteerOrgNamePattern
          AND volunteerOrg.OrganizationTypeId = @VolunteerOrgTypeId
    )
    AND ISNULL(p.ArchivedFlag, 0) = 0
    AND ISNULL(p.IsDeceased, 0) = 0
ORDER BY p.LastName, p.FirstName, a.MeetingDate, o.OrganizationName
""".format(
    program_id=PROGRAM_ID,
    volunteer_type_id=VOLUNTEER_ORG_TYPE_ID,
    volunteer_org_name_pattern=VOLUNTEER_ORG_NAME_PATTERN.replace("'", "''"),
    start_date=start_date,
    end_date=end_date,
)

rows = []
for row in q.QuerySql(sql):
    rows.append(
        {
            "StudentPeopleId": number(row.StudentPeopleId),
            "StudentName": text(row.StudentName),
            "StudentEmail": text(row.StudentEmail),
            "Grade": text(row.Grade),
            "Gender": text(row.Gender),
            "FamilyId": number(row.FamilyId),
            "HouseholdName": text(row.HouseholdName),
            "ParentGuardian1Name": text(row.ParentGuardian1Name),
            "ParentGuardian1Email": text(row.ParentGuardian1Email),
            "ParentGuardian2Name": text(row.ParentGuardian2Name),
            "ParentGuardian2Email": text(row.ParentGuardian2Email),
            "Campus": text(row.Campus),
            "ActivityCategory": text(row.ActivityCategory),
            "OrganizationName": text(row.OrganizationName),
            "MeetingDate": normalize_date(row.MeetingDate),
        }
    )

json_data = json.dumps(rows).replace("</", "<\\/")

print("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SM Student Contact Export</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#172033;font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.top{background:#193b64;color:#fff;padding:18px 24px}.top h1{margin:0;font-size:21px}.top p{margin:5px 0 0;color:#d7e4f3}.wrap{padding:18px 24px}.panel{background:#fff;border:1px solid #dfe7f1;border-radius:10px;box-shadow:0 2px 8px rgba(23,32,51,.06);margin-bottom:16px}.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;padding:16px}.field label{display:block;color:#65748b;font-size:11px;font-weight:700;letter-spacing:.05em;margin-bottom:5px;text-transform:uppercase}.field input,.field select{background:#fff;border:1px solid #cdd8e6;border-radius:6px;color:#172033;padding:8px;width:100%}.actions{align-items:end;display:flex;gap:8px;flex-wrap:wrap}.btn{border:0;border-radius:6px;cursor:pointer;font-weight:700;padding:9px 14px}.primary{background:#1e67a8;color:#fff}.secondary{background:#e9f0f8;color:#24496f}.summary{align-items:center;display:flex;gap:24px;justify-content:space-between;padding:14px 16px}.count{font-size:22px;font-weight:800;color:#1e67a8}.subtle{color:#65748b;font-size:12px}.table-wrap{overflow:auto;max-height:62vh}table{border-collapse:collapse;width:100%;min-width:1260px}th{background:#193b64;color:#fff;font-size:11px;letter-spacing:.03em;padding:9px;text-align:left;position:sticky;top:0}td{border-bottom:1px solid #e7edf4;padding:8px 9px;vertical-align:top}tr:nth-child(even) td{background:#f9fbfd}.email{word-break:break-word}.empty{text-align:center;color:#65748b;padding:40px}.privacy{background:#fff7df;border:1px solid #f0d58d;border-radius:8px;color:#694f0e;margin-top:12px;padding:10px 12px;font-size:12px}@media(max-width:700px){.wrap{padding:12px}.top{padding:15px}.summary{align-items:flex-start;flex-direction:column;gap:8px}}
</style>
</head>
<body>
<div class="top"><h1>Student Ministry Contact Export</h1><p>Students who attended an SM activity; volunteer involvements are excluded.</p></div>
<div class="wrap">
  <div class="panel filters">
    <div class="field"><label for="start">Attendance from</label><input type="date" id="start" value="__START__"></div>
    <div class="field"><label for="end">Attendance through</label><input type="date" id="end" value="__END__"></div>
    <div class="field"><label for="campus">Campus attended</label><select id="campus"></select></div>
    <div class="field"><label for="activity">Activity category</label><select id="activity"></select></div>
    <div class="field"><label for="organization">Specific activity</label><select id="organization"></select></div>
    <div class="field"><label for="grade">Current grade</label><select id="grade"></select></div>
    <div class="field"><label for="gender">Gender</label><select id="gender"></select></div>
    <div class="field"><label for="minimum">Minimum attendances</label><input id="minimum" type="number" value="1" min="1" step="1"></div>
    <div class="field"><label for="search">Student search</label><input id="search" type="search" placeholder="Name or email"></div>
    <div class="actions"><button class="btn secondary" type="button" id="reload">Load date range</button><button class="btn secondary" type="button" id="reset">Reset filters</button><button class="btn primary" type="button" id="export">Export filtered CSV</button></div>
  </div>
  <div class="panel summary"><div><span class="count" id="studentCount">0</span> students <span class="subtle" id="visitCount"></span></div><div class="subtle" id="rangeSummary"></div></div>
  <div class="panel table-wrap"><table><thead><tr><th>Student</th><th>Student email</th><th>Grade</th><th>Gender</th><th>Attendance</th><th>Last attended</th><th>Campuses</th><th>Activities</th><th>Household</th><th>Parent/Guardian 1</th><th>Parent/Guardian 1 email</th><th>Parent/Guardian 2</th><th>Parent/Guardian 2 email</th></tr></thead><tbody id="results"></tbody></table></div>
  <div class="privacy">This report contains information about minors and family contact details. Export only what you need and store/share the CSV appropriately.</div>
</div>
<script>
var attendance=__DATA__;
var ids=['campus','activity','organization','grade','gender'];
function byId(id){return document.getElementById(id)}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function uniq(values){return Array.from(new Set(values.filter(Boolean))).sort(function(a,b){return a.localeCompare(b,undefined,{numeric:true})})}
function fill(id,values,label){var el=byId(id),old=el.value;el.innerHTML='<option value="">All '+esc(label)+'</option>'+uniq(values).map(function(v){return'<option>'+esc(v)+'</option>'}).join('');if(Array.from(el.options).some(function(o){return o.value===old}))el.value=old}
function populate(){fill('campus',attendance.map(function(r){return r.Campus}),'campuses');fill('activity',attendance.map(function(r){return r.ActivityCategory}),'categories');fill('organization',attendance.map(function(r){return r.OrganizationName}),'activities');fill('grade',attendance.map(function(r){return r.Grade}),'grades');fill('gender',attendance.map(function(r){return r.Gender}),'genders')}
function matchingEvents(){var start=byId('start').value,end=byId('end').value,needle=byId('search').value.trim().toLowerCase();return attendance.filter(function(r){if(start&&r.MeetingDate<start)return false;if(end&&r.MeetingDate>end)return false;if(byId('campus').value&&r.Campus!==byId('campus').value)return false;if(byId('activity').value&&r.ActivityCategory!==byId('activity').value)return false;if(byId('organization').value&&r.OrganizationName!==byId('organization').value)return false;if(byId('grade').value&&r.Grade!==byId('grade').value)return false;if(byId('gender').value&&r.Gender!==byId('gender').value)return false;if(needle&&(r.StudentName+' '+r.StudentEmail).toLowerCase().indexOf(needle)<0)return false;return true})}
function summarize(){var people={},events=matchingEvents();events.forEach(function(r){var p=people[r.StudentPeopleId];if(!p){p=people[r.StudentPeopleId]={StudentPeopleId:r.StudentPeopleId,StudentName:r.StudentName,StudentEmail:r.StudentEmail,Grade:r.Grade,Gender:r.Gender,HouseholdName:r.HouseholdName,ParentGuardian1Name:r.ParentGuardian1Name,ParentGuardian1Email:r.ParentGuardian1Email,ParentGuardian2Name:r.ParentGuardian2Name,ParentGuardian2Email:r.ParentGuardian2Email,AttendanceCount:0,LastAttendanceDate:'',Campuses:[],ActivityCategories:[],Organizations:[]}}p.AttendanceCount++;if(r.MeetingDate>p.LastAttendanceDate)p.LastAttendanceDate=r.MeetingDate;if(p.Campuses.indexOf(r.Campus)<0)p.Campuses.push(r.Campus);if(p.ActivityCategories.indexOf(r.ActivityCategory)<0)p.ActivityCategories.push(r.ActivityCategory);if(p.Organizations.indexOf(r.OrganizationName)<0)p.Organizations.push(r.OrganizationName)});var minimum=Math.max(1,parseInt(byId('minimum').value||'1',10));return Object.keys(people).map(function(k){var p=people[k];p.Campuses.sort();p.ActivityCategories.sort();p.Organizations.sort();return p}).filter(function(p){return p.AttendanceCount>=minimum}).sort(function(a,b){return a.StudentName.localeCompare(b.StudentName)})}
function render(){var rows=summarize(),visits=rows.reduce(function(n,r){return n+r.AttendanceCount},0);byId('studentCount').textContent=rows.length.toLocaleString();byId('visitCount').textContent='('+visits.toLocaleString()+' matching attendance records)';byId('rangeSummary').textContent=byId('start').value+' through '+byId('end').value;if(!rows.length){byId('results').innerHTML='<tr><td class="empty" colspan="13">No students match the current filters.</td></tr>';return}byId('results').innerHTML=rows.map(function(r){return'<tr><td>'+esc(r.StudentName)+'</td><td class="email">'+esc(r.StudentEmail)+'</td><td>'+esc(r.Grade)+'</td><td>'+esc(r.Gender)+'</td><td>'+r.AttendanceCount+'</td><td>'+esc(r.LastAttendanceDate)+'</td><td>'+esc(r.Campuses.join('; '))+'</td><td>'+esc(r.Organizations.join('; '))+'</td><td>'+esc(r.HouseholdName)+'</td><td>'+esc(r.ParentGuardian1Name)+'</td><td class="email">'+esc(r.ParentGuardian1Email)+'</td><td>'+esc(r.ParentGuardian2Name)+'</td><td class="email">'+esc(r.ParentGuardian2Email)+'</td></tr>'}).join('')}
function csvCell(value){var s=String(value==null?'':value);return'"'+s.replace(/"/g,'""')+'"'}
function exportCsv(){var rows=summarize(),cols=[['Student Name','StudentName'],['Student Email','StudentEmail'],['Current Grade','Grade'],['Gender','Gender'],['Attendance Count','AttendanceCount'],['Most Recent Attendance','LastAttendanceDate'],['Campuses Attended','Campuses'],['Activity Categories','ActivityCategories'],['Activities Attended','Organizations'],['Household Name','HouseholdName'],['Parent/Guardian 1 Name','ParentGuardian1Name'],['Parent/Guardian 1 Email','ParentGuardian1Email'],['Parent/Guardian 2 Name','ParentGuardian2Name'],['Parent/Guardian 2 Email','ParentGuardian2Email']];var lines=[cols.map(function(c){return csvCell(c[0])}).join(',')];rows.forEach(function(r){lines.push(cols.map(function(c){var v=r[c[1]];return csvCell(Array.isArray(v)?v.join('; '):v)}).join(','))});var blob=new Blob(['\ufeff'+lines.join('\\r\\n')],{type:'text/csv;charset=utf-8'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='sm-student-contacts-'+new Date().toISOString().slice(0,10)+'.csv';document.body.appendChild(a);a.click();document.body.removeChild(a);setTimeout(function(){URL.revokeObjectURL(a.href)},1000)}
function reloadDateRange(){var start=encodeURIComponent(byId('start').value),end=encodeURIComponent(byId('end').value);window.location.href='/PyScript/SM_StudentContactExport?StartDate='+start+'&EndDate='+end}
ids.concat(['minimum','search']).forEach(function(id){byId(id).addEventListener(id==='search'?'input':'change',render)});byId('start').addEventListener('change',render);byId('end').addEventListener('change',render);byId('export').addEventListener('click',exportCsv);byId('reload').addEventListener('click',reloadDateRange);byId('reset').addEventListener('click',function(){ids.forEach(function(id){byId(id).value=''});byId('minimum').value='1';byId('search').value='';render()});populate();render();
</script>
</body>
</html>""".replace("__START__", start_date).replace("__END__", end_date).replace("__DATA__", json_data))
