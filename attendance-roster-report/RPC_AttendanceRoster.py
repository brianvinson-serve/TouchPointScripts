"""
RPC_AttendanceRoster.py

TouchPoint Special Content (Python Script). Read-only.

Printable Leader/Member roster + weekly attendance grid for one or more
active involvements in ANY RPC ministry -- generalized from the original
AD/ReNew-only version (see attendance-roster-report/README.md for that
history).

Two of the roster's columns (after the attendance grid's Total column) are
configurable per-print via dropdowns: FIELD_OPTIONS below lists what can go
in each, including "Leave Blank" (an intentional empty write-in column, not
a hidden one -- the header stays but every cell is blank). A "Group roster
by" dropdown chooses Gender (Men/Women sections, the original default),
Involvement (one section per selected class/org -- e.g. one page per
Women's Ministry table), or no grouping at all (one flat list).

Multiple involvements can be selected at once (checkboxes), but only makes
sense for involvements that share the same meeting schedule/calendar --
e.g. several Student Ministry grade+gender classes that all meet the same
Sunday, not involvements with independent schedules. The attendance grid is
one shared set of columns (the union of meeting dates across every selected
involvement); if the selected involvements don't actually share a schedule,
the grid will be sparse and "Total" won't mean what you'd want.

An optional "Attendance since" date input (blank by default -- full
history) restricts both the meeting-date columns and the Total column to
meetings on/after that date -- e.g. a Student Ministry involvement with
several school years of history under one org, printed for just the
current school year. Same query-string round-trip as the column/grouping
choices (&SinceDate=YYYY-MM-DD), validated with a strict regex before it
ever reaches SQL.

A second optional checkbox, "Exclude members with zero attendance,"
(unchecked/off by default) drops anyone whose attendance count in the
range above is zero -- e.g. a printed roster of only students who actually
showed up this school year, versus everyone still carried as a member.
Applied after Total is computed but before grouping, so section counts,
headers, and the page's total-member-count all reflect the trimmed list.

Three-step picker driven live from dbo.Program / dbo.Division / DivOrg --
no ministry-specific config to maintain:
  1. No ?ProgId= yet: pick a ministry (Program).
  2. ?ProgId= set, no ?DivId=: pick a division within that ministry.
  3. ?ProgId=&DivId= set, no ?OrgIds=: pick one or more active involvements
     in that division (checkboxes), plus the two column choices and the
     grouping choice.
  4. All set: render the combined roster with the chosen columns/grouping.
Each stage reruns this same script via a GET form; a back link steps to
the previous stage (preserving column/grouping/involvement choices already
made). A stale/invalid id or option at any stage falls back to
re-rendering that stage instead of erroring.

Row-level security (same model.UserPeopleId pattern already proven in
outstanding-task-notifications/dashboard/RPC_MyTaskBoard.py and
SM_OutstandingTasksList.py, called out as "row-level security" in that
folder's own README): unless the logged-in user is in
ADMIN_BYPASS_PEOPLE_IDS, stages 1 and 2 only show a ministry/division if
the logged-in user has ANY OrganizationMembers row (any MemberTypeId --
deliberately not restricted to Leader yet, per Brian's direction 2026-08-30)
in an org under it. This is code-level filtering, not a TouchPoint
permission feature. Stage 3's org list itself is NOT further filtered --
once a division is unlocked, every active org in it is selectable, matching
"has an involvement in that ministry and division" rather than "personally
leads this specific org."

RPC's dbo.Program table includes a handful of internal reporting/admin
"programs" that aren't real ministries (see EXCLUDED_PROGRAM_IDS below,
confirmed via DB_REFERENCE.md's OrganizationStructure writeup, 2026-08-30)
-- those are filtered out of the ministry picker for everyone, admins
included. No other filtering is config-driven: a newly created division or
involvement under an existing, non-excluded Program appears automatically
with no code change.

Per person on the roster: Name, Gender, Member Type (Leader or Member only
-- other MemberTypeIds, e.g. Coach/InActive/Prospect/Volunteer/stray values
like "100", are excluded entirely), sorted by Involvement (when multiple are
selected) then Leaders-before-Members then name. One attendance column per
meeting date any selected involvement actually held (checkmark if present,
blank if absent; canceled/did-not-meet meetings excluded from the grid
entirely), a Total column summing meetings attended, then the two
configurable columns.

NOT YET RPC-CONFIRMED: the Grade/Marital Status columns assume standard
TouchPoint/BVCMS field names (People.GradeLevelId -> lookup.GradeLevel,
People.MaritalStatusId -> lookup.MaritalStatus) that haven't been
specifically verified live against RPC's instance the way
Program/Division/DivOrg/MemberType have been elsewhere in this repo. An
Address column was tried the same way and removed 2026-08-30 after a live
run threw "Invalid column name 'City'"/"'State'" -- People.City/State
don't exist on RPC's schema; likely on Families instead (per
DB_REFERENCE.md, People.FamilyId -> Families.FamilyId), not yet confirmed.
See attendance-roster-report/README.md for the discovery query to run
before re-adding it. Grade reuses the exact fallback pattern DB_REFERENCE.md
confirms for student-contact-export/SM_StudentContactExport.py. If any of
these throw an "Invalid column name" error live, that column's SQL/comment
here needs the fix folded back into DB_REFERENCE.md.

Deploy: Admin > Advanced > Special Content > Python Scripts > +New
Script name suggestion: RPC_AttendanceRoster
Access via /PyScript/RPC_AttendanceRoster (not the Special Content admin
"run" preview) so the picker's Apply buttons and query-string reruns work,
and so printing (Ctrl/Cmd+P) doesn't pick up TouchPoint's own admin chrome.
CSS forces landscape and a page break between sections (when grouped).

Saving a specific roster's settings: everything (Program, Division,
selected involvements, columns, grouping) lives in the URL query string, so
bookmarking the generated roster's URL "saves" that exact configuration to
rerun later -- no code-level saved-config feature has been built.
"""

import re
from collections import OrderedDict

# ============================================================
# Config
# ============================================================
ACTIVE_STATUS_ID = 30

# PeopleIds who see every ministry/division regardless of their own
# OrganizationMembers rows -- confirmed 2026-08-30 per Brian: he (PeopleId
# 47110) and Marlene Godinez (PeopleId 7059, per DB_REFERENCE.md's staff
# roster) should see everything; everyone else is scoped to what they're
# actually in.
ADMIN_BYPASS_PEOPLE_IDS = [47110, 7059]  # Brian Vinson, Marlene Godinez

# dbo.Program rows that are internal reporting/admin buckets, not real
# ministries a staff member would pick a roster from. Confirmed live
# 2026-08-30 (see DB_REFERENCE.md, OrganizationStructure section) --
#   1124/1127  Reporting (RP) All Programs ONLY/OUTSIDE Sun AM
#   1130       CT Admin
#   1137/1138  Reporting (RP) CC/PS Children ONLY Sun AM
#   1141       RP PS Students
# Add a new Id here if another admin/reporting Program shows up. Do NOT add
# real ministries here or anywhere else -- they should need zero code
# changes to appear in the picker.
EXCLUDED_PROGRAM_IDS = [1124, 1127, 1130, 1137, 1138, 1141]

# Only these MemberTypeIds appear on the roster, sorted in this order
# (Leader first, then Member) -- everything else (Coach, InActive,
# Prospect, Volunteer, or an unmapped/stray value) is excluded entirely.
# Note: this is the ROSTER's own membership filter, unrelated to the
# row-level-security check above (which deliberately isn't tied to
# MemberTypeId).
MEMBER_TYPE_SORT_SQL = "CASE om.MemberTypeId WHEN 140 THEN 0 WHEN 220 THEN 1 ELSE 2 END"
MEMBER_TYPE_LABELS = {140: "Leader", 220: "Member"}

# Options for the two configurable roster columns (after Total). "blank" is
# an intentional empty write-in column, not a way to remove the column.
# Every value here must be handled in field_value() below.
FIELD_OPTIONS = [
    ("blank", "Leave Blank"),
    ("phone", "Phone"),
    ("email", "Email"),
    ("age", "Age"),
    ("gender", "Gender"),
    ("grade", "Grade"),
    ("maritalstatus", "Marital Status"),
    ("lastname", "Last Name"),
    ("involvement", "Involvement (class/org name)"),
]
FIELD_KEYS = [k for k, _ in FIELD_OPTIONS]
FIELD_LABELS = dict(FIELD_OPTIONS)
DEFAULT_COL1 = "phone"
DEFAULT_COL2 = "email"

# How to split the roster into print sections/page breaks.
GROUP_BY_OPTIONS = [
    ("gender", "Gender (Men / Women sections)"),
    ("involvement", "Involvement (one section per selected class/org)"),
    ("none", "No grouping -- one combined list"),
]
GROUP_BY_KEYS = [k for k, _ in GROUP_BY_OPTIONS]
DEFAULT_GROUP_BY = "gender"

# Optional attendance-grid start date (stage 3's "Attendance since" date
# input, YYYY-MM-DD -- the format an HTML5 <input type="date"> submits).
# When set, the meeting-date columns and Total only cover meetings on/after
# this date -- e.g. an involvement with several years of history (a
# graduating senior's single Student Ministry class) printed for just this
# school year. Empty string means no filter, the original all-time
# behavior. Validated with a strict regex before ever reaching SQL, since
# unlike every other query input here it isn't an int or a value drawn from
# a fixed option list.
DEFAULT_SINCE_DATE = ""

# ============================================================
# Helpers
# ============================================================
def to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def normalize_date(value):
    # RPC's q.QuerySql returns dates as either 'YYYY-MM-DD[ HH:MM:SS]' or
    # 'M/D/YYYY' depending on context -- normalize both to 'YYYY-MM-DD' so
    # date-string comparisons/lookups are consistent. Same helper as
    # student-contact-export/SM_StudentContactExport.py.
    value = str(value or "").strip().replace(" ", " ")
    value = value.split("T")[0].split(" ")[0]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if match:
        return "{0}-{1}-{2}".format(
            match.group(3), match.group(1).zfill(2), match.group(2).zfill(2)
        )
    return value


def fmt_col_header(date_str):
    # date_str is 'YYYY-MM-DD' -- render as 'M/D'
    y, m, d = date_str.split("-")
    return "{0}/{1}".format(int(m), int(d))


def esc(s):
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def member_type_label(member_type_id):
    return MEMBER_TYPE_LABELS.get(member_type_id, str(member_type_id))


def valid_field_key(value, default):
    return value if value in FIELD_KEYS else default


def valid_group_by(value):
    return value if value in GROUP_BY_KEYS else DEFAULT_GROUP_BY


def valid_since_date(value):
    # Strict YYYY-MM-DD only (what an HTML5 date input submits) -- anything
    # else (blank, malformed, a paste gone wrong) falls back to "no filter"
    # rather than being trusted into SQL.
    value = str(value or "").strip()
    return value if re.match(r"^\d{4}-\d{2}-\d{2}$", value) else DEFAULT_SINCE_DATE


def field_value(key, p):
    """Display string for configurable-column field `key` on roster row p."""
    if key == "phone":
        return model.FmtPhone(p.CellPhone) if p.CellPhone else ""
    if key == "email":
        return p.Email or ""
    if key == "age":
        age = getattr(p, "Age", None)
        return str(age) if age not in (None, "") else ""
    if key == "gender":
        return p.Gender or ""
    if key == "grade":
        return p.Grade or ""
    if key == "maritalstatus":
        return p.MaritalStatus or ""
    if key == "lastname":
        return p.LastName or ""
    if key == "involvement":
        return getattr(p, "Involvement", "") or ""
    return ""  # "blank", or an unrecognized key -- render as an empty cell


def render_picker(step_title, heading, meta_text, select_name, options_html, hidden_fields=None, back_href=None):
    hidden_html = "".join(
        '<input type="hidden" name="{0}" value="{1}">'.format(k, v)
        for k, v in (hidden_fields or {}).items()
    )
    back_html = (
        '<p class="back"><a href="{0}">&larr; Back</a></p>'.format(back_href)
        if back_href else ""
    )
    print(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{step_title}</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 20px; color: #222; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .meta {{ color: #555; font-size: 13px; margin-bottom: 16px; }}
  .back {{ margin-bottom: 12px; font-size: 13px; }}
  select {{ font-size: 14px; padding: 6px; min-width: 420px; }}
  button {{ font-size: 14px; padding: 6px 16px; margin-left: 8px; }}
</style>
</head>
<body>
{back_html}
<h1>{heading}</h1>
<p class="meta">{meta_text}</p>
<form method="get">
  {hidden_html}
  <select name="{select_name}" required>
    <option value="">-- Select --</option>
    {options_html}
  </select>
  <button type="submit">Apply</button>
</form>
</body>
</html>""".format(
            step_title=step_title,
            heading=heading,
            meta_text=meta_text,
            hidden_html=hidden_html,
            select_name=select_name,
            options_html=options_html,
            back_html=back_html,
        )
    )


def render_org_and_options_picker(org_rows, selected_program, selected_division, col1, col2, group_by, since_date, exclude_zero):
    # No pre-checking: this stage is only ever reached with zero validly-
    # selected orgs (any valid OrgIds jump straight to stage 4), so there's
    # never a prior selection worth restoring here.
    checkbox_html = "".join(
        '<label class="orgcb"><input type="checkbox" class="orgcheck" value="{oid}"> {name} ({count} member{plural})</label>'.format(
            oid=r.OrganizationId,
            name=esc(r.OrganizationName),
            count=r.MemberCount,
            plural="" if r.MemberCount == 1 else "s",
        )
        for r in org_rows
    )

    def field_options_html(selected_key):
        return "".join(
            '<option value="{0}"{1}>{2}</option>'.format(
                key, ' selected' if key == selected_key else '', esc(label)
            )
            for key, label in FIELD_OPTIONS
        )

    group_options_html = "".join(
        '<option value="{0}"{1}>{2}</option>'.format(key, ' selected' if key == group_by else '', esc(label))
        for key, label in GROUP_BY_OPTIONS
    )

    print(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Choose Involvement(s) -- Roster Report</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 20px; color: #222; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .meta {{ color: #555; font-size: 13px; margin-bottom: 16px; }}
  .back {{ margin-bottom: 12px; font-size: 13px; }}
  .field {{ margin-bottom: 16px; }}
  label {{ display: block; font-size: 13px; color: #444; margin-bottom: 4px; }}
  .orglist {{ border: 1px solid #ddd; border-radius: 4px; padding: 8px 12px; max-height: 320px; overflow-y: auto; min-width: 420px; }}
  .orgcb {{ display: block; font-size: 14px; color: #222; padding: 3px 0; font-weight: normal; }}
  select {{ font-size: 14px; padding: 6px; min-width: 420px; }}
  button {{ font-size: 14px; padding: 8px 20px; margin-top: 8px; }}
</style>
</head>
<body>
<p class="back"><a href="?ProgId={prog_id}">&larr; Back</a></p>
<h1>Choose Involvement(s)</h1>
<p class="meta">{count} active involvement(s) in {div_name}. Check one or more -- only combine involvements that share the same meeting schedule.</p>
<form method="get" id="pickerForm">
  <input type="hidden" name="ProgId" value="{prog_id}">
  <input type="hidden" name="DivId" value="{div_id}">
  <input type="hidden" name="OrgIds" id="OrgIdsField" value="">
  <div class="field">
    <div class="orglist">{checkbox_html}</div>
  </div>
  <div class="field">
    <label for="Col1">Column 1 (after Total)</label>
    <select name="Col1" id="Col1">{col1_options}</select>
  </div>
  <div class="field">
    <label for="Col2">Column 2 (after Total)</label>
    <select name="Col2" id="Col2">{col2_options}</select>
  </div>
  <div class="field">
    <label for="GroupBy">Group roster by</label>
    <select name="GroupBy" id="GroupBy">{group_options}</select>
  </div>
  <div class="field">
    <label for="SinceDate">Attendance since (optional -- leave blank for full history)</label>
    <input type="date" name="SinceDate" id="SinceDate" value="{since_date}">
  </div>
  <div class="field">
    <label class="checklabel"><input type="checkbox" name="ExcludeZero" value="1"{exclude_zero_checked}> Exclude members with zero attendance (within the date range above, if set)</label>
  </div>
  <button type="submit">Apply</button>
</form>
<script>
document.getElementById('pickerForm').addEventListener('submit', function(e) {{
  var checked = [];
  var boxes = document.querySelectorAll('.orgcheck:checked');
  for (var i = 0; i < boxes.length; i++) {{ checked.push(boxes[i].value); }}
  if (checked.length === 0) {{
    alert('Pick at least one involvement.');
    e.preventDefault();
    return;
  }}
  document.getElementById('OrgIdsField').value = checked.join(',');
}});
</script>
</body>
</html>""".format(
            prog_id=selected_program.Id,
            div_id=selected_division.Id,
            div_name=esc(selected_division.Name),
            count=len(org_rows),
            checkbox_html=checkbox_html,
            col1_options=field_options_html(col1),
            col2_options=field_options_html(col2),
            group_options=group_options_html,
            since_date=esc(since_date),
            exclude_zero_checked=' checked' if exclude_zero else '',
        )
    )


# ============================================================
# Row-level security: who is looking at this?
# ============================================================
CURRENT_USER_ID = to_int(getattr(model, "UserPeopleId", None))
IS_ADMIN = CURRENT_USER_ID in ADMIN_BYPASS_PEOPLE_IDS

# ============================================================
# Stage 1: pick a ministry (Program)
# ============================================================
excluded_ids_sql = ", ".join(str(x) for x in EXCLUDED_PROGRAM_IDS)

rls_program_clause = "" if IS_ADMIN else """
  AND EXISTS (
      SELECT 1
      FROM dbo.OrganizationMembers om_rls
      JOIN dbo.DivOrg do_rls ON do_rls.OrgId = om_rls.OrganizationId
      JOIN dbo.Division dv_rls ON dv_rls.Id = do_rls.DivId
      WHERE dv_rls.ProgId = p.Id
        AND om_rls.PeopleId = {user_id}
  )
""".format(user_id=CURRENT_USER_ID)

sql_programs = """
SELECT p.Id, p.Name
FROM dbo.Program p
WHERE p.Id NOT IN ({excluded})
{rls_clause}
ORDER BY p.Name
""".format(excluded=excluded_ids_sql, rls_clause=rls_program_clause)

program_rows = list(q.QuerySql(sql_programs))

requested_prog_id = to_int(getattr(model.Data, "ProgId", ""))
selected_program = None
for r in program_rows:
    if r.Id == requested_prog_id:
        selected_program = r
        break

if selected_program is None:
    options_html = "".join(
        '<option value="{id}">{name}</option>'.format(id=r.Id, name=esc(r.Name))
        for r in program_rows
    )
    render_picker(
        step_title="Choose a Ministry -- Roster Report",
        heading="Choose a Ministry",
        meta_text="{0} ministry program(s) available. Pick one to see its divisions.".format(len(program_rows)),
        select_name="ProgId",
        options_html=options_html,
    )

else:
    # ============================================================
    # Stage 2: pick a division within that ministry
    # ============================================================
    rls_division_clause = "" if IS_ADMIN else """
      AND EXISTS (
          SELECT 1
          FROM dbo.OrganizationMembers om_rls
          JOIN dbo.DivOrg do_rls ON do_rls.OrgId = om_rls.OrganizationId
          WHERE do_rls.DivId = d.Id
            AND om_rls.PeopleId = {user_id}
      )
    """.format(user_id=CURRENT_USER_ID)

    sql_divisions = """
    SELECT d.Id, d.Name
    FROM dbo.Division d
    WHERE d.ProgId = {prog_id}
    {rls_clause}
    ORDER BY d.Name
    """.format(prog_id=selected_program.Id, rls_clause=rls_division_clause)

    division_rows = list(q.QuerySql(sql_divisions))

    requested_div_id = to_int(getattr(model.Data, "DivId", ""))
    selected_division = None
    for r in division_rows:
        if r.Id == requested_div_id:
            selected_division = r
            break

    if not division_rows:
        print(
            """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>No Divisions -- Roster Report</title>
<style>body {{ font-family: Arial, Helvetica, sans-serif; margin: 20px; color: #222; }}</style>
</head>
<body>
<p><a href="?">&larr; Back</a></p>
<h1>No divisions found</h1>
<p>{prog_name} has no divisions you have access to.</p>
</body>
</html>""".format(prog_name=esc(selected_program.Name))
        )

    elif selected_division is None:
        options_html = "".join(
            '<option value="{id}">{name}</option>'.format(id=r.Id, name=esc(r.Name))
            for r in division_rows
        )
        render_picker(
            step_title="Choose a Division -- Roster Report",
            heading="Choose a Division",
            meta_text="{0} division(s) under {1}.".format(len(division_rows), esc(selected_program.Name)),
            select_name="DivId",
            options_html=options_html,
            hidden_fields={"ProgId": selected_program.Id},
            back_href="?",
        )

    else:
        # ============================================================
        # Stage 3: pick one or more active involvements in that division,
        # plus the two configurable columns and the grouping choice.
        # Organizations -> DivOrg is one-to-many, so use EXISTS rather than
        # a plain JOIN to avoid duplicate-row fan-out (per DB_REFERENCE.md).
        # No further row-level-security filtering here -- once a division
        # is unlocked (stage 2), every active org in it is selectable.
        # ============================================================
        sql_orgs = """
        SELECT
            o.OrganizationId,
            o.OrganizationName,
            ISNULL(o.MemberCount, 0) AS MemberCount
        FROM dbo.Organizations o
        WHERE o.OrganizationStatusId = {active_status_id}
          AND EXISTS (
              SELECT 1 FROM dbo.DivOrg d2 WHERE d2.OrgId = o.OrganizationId AND d2.DivId = {div_id}
          )
        ORDER BY o.OrganizationName
        """.format(active_status_id=ACTIVE_STATUS_ID, div_id=selected_division.Id)

        org_rows = list(q.QuerySql(sql_orgs))
        valid_org_ids_set = set(r.OrganizationId for r in org_rows)

        requested_org_ids_raw = str(getattr(model.Data, "OrgIds", "") or "")
        requested_org_ids = [to_int(x) for x in requested_org_ids_raw.split(",") if x.strip()]
        selected_org_ids = [oid for oid in requested_org_ids if oid in valid_org_ids_set]

        # Column/grouping choices: read from the query string with safe
        # defaults, so this works whether we're re-rendering stage 3 (first
        # visit, or no valid OrgIds yet) or arriving at stage 4.
        col1 = valid_field_key(str(getattr(model.Data, "Col1", "") or ""), DEFAULT_COL1)
        col2 = valid_field_key(str(getattr(model.Data, "Col2", "") or ""), DEFAULT_COL2)
        group_by = valid_group_by(str(getattr(model.Data, "GroupBy", "") or ""))
        since_date = valid_since_date(str(getattr(model.Data, "SinceDate", "") or ""))
        exclude_zero = str(getattr(model.Data, "ExcludeZero", "") or "") == "1"

        if not selected_org_ids:
            render_org_and_options_picker(org_rows, selected_program, selected_division, col1, col2, group_by, since_date, exclude_zero)

        else:
            # ============================================================
            # Stage 4: involvement(s) selected -- build the combined roster.
            # ============================================================
            org_ids_str = ",".join(str(oid) for oid in selected_org_ids)
            selected_org_names = [r.OrganizationName for r in org_rows if r.OrganizationId in selected_org_ids]
            org_label = " + ".join(selected_org_names) if len(selected_org_names) > 1 else selected_org_names[0]

            # since_date is already validated as strict YYYY-MM-DD (or "") by
            # valid_since_date() before it ever reaches here.
            since_date_clause = (
                "AND CAST(m.MeetingDate AS DATE) >= '{0}'".format(since_date)
                if since_date else ""
            )

            sql_meetings = """
            SELECT DISTINCT CAST(m.MeetingDate AS DATE) AS MeetingDate
            FROM dbo.Meetings m
            WHERE m.OrganizationId IN ({org_ids})
              AND ISNULL(m.Canceled, 0) = 0
              AND ISNULL(m.DidNotMeet, 0) = 0
              {since_date_clause}
            ORDER BY MeetingDate
            """.format(org_ids=org_ids_str, since_date_clause=since_date_clause)

            # Only Leader/Member MemberTypeIds; sorted by Involvement (so a
            # multi-org combined roster naturally groups by org even before
            # any Python-side grouping), then Leader-before-Member, then
            # name. Age/Grade/Marital Status are always fetched
            # (cheap one-to-one lookups keyed on People's own foreign keys,
            # no fan-out risk) regardless of which two are actually chosen
            # for display -- simpler than building the SELECT/JOINs
            # dynamically per selection.
            sql_roster = """
            SELECT
                p.PeopleId,
                Name = LTRIM(RTRIM(COALESCE(NULLIF(p.PreferredName, ''), NULLIF(p.NickName, ''), p.FirstName, '') + ' ' + COALESCE(p.LastName, ''))),
                LastName = COALESCE(p.LastName, ''),
                GenderId = ISNULL(p.GenderId, 0),
                Gender = COALESCE(NULLIF(g.Description, ''), NULLIF(g.Code, ''), 'Unknown'),
                MemberTypeId = om.MemberTypeId,
                CellPhone = p.CellPhone,
                Email = COALESCE(NULLIF(LTRIM(RTRIM(p.EmailAddress)), ''), NULLIF(LTRIM(RTRIM(p.EmailAddress2)), ''), ''),
                Age = p.Age,
                Grade = COALESCE(NULLIF(gl.Code, ''), NULLIF(gl.Description, ''), NULLIF(CAST(p.Grade AS VARCHAR(20)), ''), ''),
                MaritalStatus = COALESCE(NULLIF(ms.Description, ''), NULLIF(ms.Code, ''), ''),
                Involvement = o2.OrganizationName
            FROM dbo.OrganizationMembers om
            JOIN dbo.People p ON p.PeopleId = om.PeopleId
            JOIN dbo.Organizations o2 ON o2.OrganizationId = om.OrganizationId
            LEFT JOIN lookup.Gender g ON g.Id = p.GenderId
            LEFT JOIN lookup.GradeLevel gl ON gl.Id = p.GradeLevelId
            LEFT JOIN lookup.MaritalStatus ms ON ms.Id = p.MaritalStatusId
            WHERE om.OrganizationId IN ({org_ids})
              AND om.MemberTypeId IN (140, 220)
            ORDER BY o2.OrganizationName, {member_type_sort_sql}, p.LastName, Name
            """.format(org_ids=org_ids_str, member_type_sort_sql=MEMBER_TYPE_SORT_SQL)

            # Per DB_REFERENCE.md: require AttendanceFlag = 1, defensively
            # exclude NoShow = 1. Attendance is looked up by PeopleId across
            # ALL selected orgs, so someone in two selected involvements is
            # credited for attending via either.
            sql_attend = """
            SELECT
                a.PeopleId,
                CAST(a.MeetingDate AS DATE) AS MeetingDate
            FROM dbo.Attend a
            JOIN dbo.Meetings m ON m.MeetingId = a.MeetingId
            WHERE a.OrganizationId IN ({org_ids})
              AND a.AttendanceFlag = 1
              AND ISNULL(a.NoShow, 0) = 0
              AND ISNULL(m.Canceled, 0) = 0
              AND ISNULL(m.DidNotMeet, 0) = 0
              {since_date_clause}
            """.format(org_ids=org_ids_str, since_date_clause=since_date_clause)

            meeting_rows = list(q.QuerySql(sql_meetings))
            roster_rows = list(q.QuerySql(sql_roster))
            attend_rows = list(q.QuerySql(sql_attend))

            meeting_dates = [normalize_date(r.MeetingDate) for r in meeting_rows]

            attended_by_person = {}
            for r in attend_rows:
                attended_by_person.setdefault(r.PeopleId, set()).add(normalize_date(r.MeetingDate))

            # Optional: drop anyone with zero attended meetings in the
            # (possibly since_date-filtered) range above -- e.g. printing
            # only students who've actually shown up this school year.
            # Filtered before grouping so section counts/headers and the
            # page meta line's total_count reflect the trimmed list, not
            # the full membership.
            if exclude_zero:
                roster_rows = [p for p in roster_rows if attended_by_person.get(p.PeopleId)]

            def build_rows_html(people):
                rows = []
                for p in people:
                    dates_attended = attended_by_person.get(p.PeopleId, set())
                    cells = []
                    for d in meeting_dates:
                        mark = "&#10003;" if d in dates_attended else ""
                        cells.append('<td class="mark">{0}</td>'.format(mark))
                    total = len(dates_attended)
                    col1_val = field_value(col1, p)
                    col2_val = field_value(col2, p)
                    rows.append(
                        "<tr><td>{name}</td><td>{gender}</td><td>{mtype}</td>{cells}"
                        '<td class="total">{total}</td><td>{col1}</td><td>{col2}</td></tr>'.format(
                            name=esc(p.Name),
                            gender=esc(p.Gender),
                            mtype=esc(member_type_label(p.MemberTypeId)),
                            cells="".join(cells),
                            total=total,
                            col1=esc(col1_val),
                            col2=esc(col2_val),
                        )
                    )
                return "".join(rows)

            col_headers = "".join(
                '<th class="mark">{0}</th>'.format(esc(fmt_col_header(d))) for d in meeting_dates
            )
            col1_header = esc(FIELD_LABELS.get(col1, ""))
            col2_header = esc(FIELD_LABELS.get(col2, ""))

            def build_section_html(title, people, page_break):
                break_class = " page-break" if page_break else ""
                heading_html = (
                    '<h2>{0} <span class="count">({1})</span></h2>'.format(esc(title), len(people))
                    if title else ""
                )
                return """
<div class="section{break_class}">
  {heading}
  <table>
    <thead>
      <tr>
        <th>Name</th><th>Gender</th><th>Member Type</th>{col_headers}<th class="total">Total</th><th>{col1_header}</th><th>{col2_header}</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</div>
""".format(
                    break_class=break_class,
                    heading=heading_html,
                    col_headers=col_headers,
                    col1_header=col1_header,
                    col2_header=col2_header,
                    rows=build_rows_html(people),
                )

            if group_by == "gender":
                men = [p for p in roster_rows if p.GenderId == 1]
                women = [p for p in roster_rows if p.GenderId == 2]
                other = [p for p in roster_rows if p.GenderId not in (1, 2)]
                sections_data = [
                    (name, people)
                    for name, people in (("Men", men), ("Women", women), ("Unspecified Gender", other))
                    if people
                ]
            elif group_by == "involvement":
                # sql_roster is already ORDER BY o2.OrganizationName first,
                # so accumulating in an OrderedDict preserves alphabetical
                # involvement order with no extra sort needed.
                groups = OrderedDict()
                for p in roster_rows:
                    groups.setdefault(p.Involvement, []).append(p)
                sections_data = [(name, people) for name, people in groups.items() if people]
            else:
                # No grouping: one flat list, already sorted via sql_roster's
                # ORDER BY. No section heading -- the meta line above already
                # gives the total count.
                sections_data = [(None, roster_rows)] if roster_rows else []

            sections_html = "".join(
                build_section_html(title, people, page_break=(i > 0))
                for i, (title, people) in enumerate(sections_data)
            )

            # Deliberately omits OrgIds: any valid OrgIds would jump straight
            # back to this same roster instead of showing the picker (see
            # render_org_and_options_picker's note on why it doesn't
            # pre-check anything). Same behavior as the original single-
            # select version's back link.
            back_href = "?ProgId={0}&amp;DivId={1}&amp;Col1={2}&amp;Col2={3}&amp;GroupBy={4}&amp;SinceDate={5}&amp;ExcludeZero={6}".format(
                selected_program.Id, selected_division.Id, col1, col2, group_by, since_date, "1" if exclude_zero else ""
            )

            since_date_meta = " since {0}".format(esc(since_date)) if since_date else ""
            exclude_zero_meta = " &middot; excluding zero-attendance members" if exclude_zero else ""

            print(
                """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{org_label} -- Roster</title>
<style>
  @media print {{
    @page {{ size: landscape; margin: 0.4in; }}
    .page-break {{ page-break-before: always; }}
    .no-print {{ display: none; }}
  }}
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 20px; color: #222; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .meta {{ color: #555; font-size: 13px; margin-bottom: 16px; }}
  h2 {{ font-size: 16px; margin-top: 24px; }}
  .count {{ font-weight: normal; color: #666; font-size: 13px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
  thead {{ display: table-header-group; }}
  tr {{ page-break-inside: avoid; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; font-size: 12px; text-align: left; white-space: nowrap; }}
  th {{ background: #f2f2f2; }}
  th.mark, td.mark {{ text-align: center; width: 32px; }}
  th.total, td.total {{ text-align: center; font-weight: bold; background: #fafafa; }}
</style>
</head>
<body>
<p class="no-print"><a href="{back_href}">&larr; Choose different involvement(s)</a></p>
<h1>{org_label} -- Roster</h1>
<p class="meta">{org_count} involvement(s) &middot; {meeting_count} meeting(s){since_date_meta} through {last_date} &middot; {total_count} total member(s){exclude_zero_meta}</p>
{sections}
</body>
</html>""".format(
                    org_label=esc(org_label),
                    back_href=back_href,
                    org_count=len(selected_org_ids),
                    meeting_count=len(meeting_dates),
                    since_date_meta=since_date_meta,
                    exclude_zero_meta=exclude_zero_meta,
                    last_date=esc(fmt_col_header(meeting_dates[-1])) if meeting_dates else "n/a",
                    total_count=len(roster_rows),
                    sections=sections_html,
                )
            )
