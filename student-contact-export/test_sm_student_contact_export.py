import contextlib
import io
import json
import re
import runpy
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).with_name("SM_StudentContactExport.py")


class Row(SimpleNamespace):
    pass


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.queries = []

    def QuerySql(self, sql):
        self.sql = sql
        self.queries.append(sql)
        return self.rows


def attendance_row(person_id, name, email, grade, gender, campus, category, org, meeting_date, **overrides):
    values = dict(
        StudentPeopleId=person_id,
        StudentName=name,
        StudentEmail=email,
        Grade=grade,
        Gender=gender,
        FamilyId=person_id + 1000,
        HouseholdName=name.split()[-1] + " Household",
        ParentGuardian1Name="Parent One",
        ParentGuardian1Email="parent1@example.org",
        ParentGuardian2Name="Parent Two",
        ParentGuardian2Email="parent2@example.org",
        Campus=campus,
        ActivityCategory=category,
        OrganizationName=org,
        MeetingDate=meeting_date,
    )
    values.update(overrides)
    return Row(**values)


def render(rows, data=None):
    fake_q = FakeQuery(rows)
    model = SimpleNamespace(Data=data or SimpleNamespace())
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        runpy.run_path(str(SCRIPT), init_globals={"model": model, "q": fake_q})
    return output.getvalue(), fake_q.queries[-1]


def extract_data(html):
    match = re.search(r"var attendance=(.*?);\nvar ids=", html, re.S)
    assert match, "Injected attendance JSON was not found"
    return json.loads(match.group(1))


def extract_javascript(html):
    match = re.search(r"<script>(.*?)</script>", html, re.S)
    assert match, "Inline report JavaScript was not found"
    return match.group(1)


def test_query_guardrails_and_default_dates():
    html, sql = render([])
    assert "DECLARE @ProgramId INT = 1109" in sql
    assert "DECLARE @VolunteerOrgTypeId INT = 207" in sql
    assert "DECLARE @VolunteerOrgNamePattern VARCHAR(100) = 'SM: All Volunteers%'" in sql
    assert "a.AttendanceFlag = 1" in sql
    assert "ISNULL(a.NoShow, 0) = 0" in sql
    assert "o.OrganizationTypeId <> @VolunteerOrgTypeId" in sql
    assert "FROM dbo.OrganizationMembers volunteerMember" in sql
    assert "volunteerMember.PeopleId = p.PeopleId" in sql
    assert "volunteerOrg.OrganizationName LIKE @VolunteerOrgNamePattern" in sql
    assert "NOT EXISTS (" in sql
    assert "fp.Child" not in sql
    assert "PositionInFamilyId" not in sql
    assert "activity.ActivityCategory IS NOT NULL" in sql
    end = date.today()
    assert 'value="{}"'.format(end.isoformat()) in html


def test_date_validation_and_range_cap():
    html, sql = render([], SimpleNamespace(StartDate="2020-01-01", EndDate="2026-08-13"))
    assert "DECLARE @EndDate DATE = '2026-08-13'" in sql
    assert "DECLARE @StartDate DATE = '2025-08-12'" in sql
    assert 'value="2025-08-12"' in html


def test_rows_are_serialized_and_dates_normalized():
    rows = [
        attendance_row(1, "Alex Smith", "alex@example.org", "9", "Male", "Central", "Sunday", "SM: CC 9th Guys", "8/9/2026 12:00:00 AM"),
        attendance_row(1, "Alex Smith", "alex@example.org", "9", "Male", "Parker Square", "Events", "SM: Paint War", "2026-08-11"),
    ]
    html, _ = render(rows)
    data = extract_data(html)
    assert len(data) == 2
    assert data[0]["MeetingDate"] == "2026-08-09"
    assert data[1]["MeetingDate"] == "2026-08-11"
    assert data[0]["StudentPeopleId"] == 1
    assert "function summarize()" in html
    assert "one row per student" not in html.lower() or "Student Ministry Contact Export" in html


def test_html_contains_filters_export_and_privacy_warning():
    html, _ = render([])
    for element_id in ["start", "end", "campus", "activity", "organization", "grade", "gender", "minimum", "search", "export"]:
        assert 'id="{}"'.format(element_id) in html
    assert "Export filtered CSV" in html
    assert "information about minors" in html
    assert "Activity Categories" in html
    assert "Parent/Guardian 2 Email" in html
    assert "SQL diagnostic" not in html
    assert "SMContactExportDiagnostic" not in html


def test_rendered_javascript_parses_and_executes_boot_path():
    html, _ = render([])
    javascript = extract_javascript(html)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js") as script_file:
        script_file.write(javascript)
        script_file.flush()
        syntax_result = subprocess.run(
            ["node", "--check", script_file.name],
            capture_output=True,
            text=True,
        )
        assert syntax_result.returncode == 0, syntax_result.stderr

        harness = r"""
const fs=require('fs'),vm=require('vm');
const elements={};
const defaults={start:'2026-05-15',end:'2026-08-13',minimum:'1',search:''};
function element(id){
  if(!elements[id]) elements[id]={
    value:defaults[id]||'',textContent:'',innerHTML:'',options:[],
    addEventListener:function(){},appendChild:function(){},removeChild:function(){}
  };
  return elements[id];
}
global.document={
  getElementById:element,
  createElement:function(){return element('__created')},
  body:element('__body')
};
global.window={location:{href:''}};
global.URL={createObjectURL:function(){return'blob:test'},revokeObjectURL:function(){}};
global.Blob=function(){};
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
console.log(JSON.stringify({
  campus:element('campus').innerHTML,
  results:element('results').innerHTML,
  range:element('rangeSummary').textContent
}));
"""
        execution_result = subprocess.run(
            ["node", "-e", harness, script_file.name],
            capture_output=True,
            text=True,
        )
    assert execution_result.returncode == 0, execution_result.stderr
    state = json.loads(execution_result.stdout)
    assert "All campuses" in state["campus"]
    assert "No students match the current filters." in state["results"]
    assert state["range"] == "2026-05-15 through 2026-08-13"
    assert "Server query complete" not in html
    assert "JS ACTIVE" not in html
    assert "JS INACTIVE" not in html
    assert "lines.join('\\r\\n')" in javascript


def test_date_reload_uses_touchpoint_pyscript_endpoint():
    html, _ = render([])
    assert "function reloadDateRange()" in html
    assert "'/PyScript/SM_StudentContactExport?StartDate='" in html
    assert "encodeURIComponent(byId('start').value)" in html
    assert "encodeURIComponent(byId('end').value)" in html
    assert "window.location.href.split" not in html
    assert "new URL(" not in html
    assert ".searchParams" not in html
    assert "addEventListener('click',reloadDateRange)" in html


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("{} tests passed".format(len(tests)))
