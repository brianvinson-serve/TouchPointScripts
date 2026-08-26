"""
AD_ReNewRosterReport.py

TouchPoint Special Content (Python Script). Read-only.

Printable Leader/Member roster + weekly attendance grid for any active
involvement under a configured set of ministry divisions (currently the two
Adult Discipleship (AD) divisions that carry ReNew: "AD ReNew" and "AD
Classes/Meetings/Groups"). Splits members onto separate print sections/pages
by People.GenderId -- Men, then Women. Anyone with unset/Unknown gender
lands on a third "Unspecified Gender" section instead of being silently
dropped.

No involvement chosen yet (no ?OrgId= in the URL): renders a picker --
every active involvement in the configured divisions, grouped by division,
with a dropdown + Apply button. Choosing one reruns this same script with
?OrgId=<id> and renders that involvement's roster.

Per person on the roster: Name, Gender, Member Type (Leader or Member only
-- other MemberTypeIds, e.g. Coach/InActive/Prospect/Volunteer/stray values
like "100", are excluded entirely), sorted Leaders first then Members within
each gender section. One attendance column per meeting this org has
actually held (checkmark if present, blank if absent; canceled/did-not-meet
meetings excluded from the grid entirely), a Total column summing meetings
attended, then Phone and Email.

Deploy: Admin > Advanced > Special Content > Python Scripts > +New
Script name suggestion: AD_ReNewRosterReport
Access via /PyScript/AD_ReNewRosterReport (not the Special Content admin
"run" preview) so the picker's Apply button and query-string reruns work,
and so printing (Ctrl/Cmd+P) doesn't pick up TouchPoint's own admin chrome.
CSS forces landscape and a page break between each gender section.

To make another ministry's classes/groups selectable in the picker, add a
row to DIVISION_FILTERS below once you have that ministry's Division.Id:
    SELECT Id, Name, ProgId FROM dbo.Division WHERE Name LIKE '%something%'
"""

import re

# ============================================================
# Config
# ============================================================
ACTIVE_STATUS_ID = 30

# Which ministry divisions populate the involvement picker. Add a
# (DivisionId, "Program (Code): Division Name") row here to extend this
# report to another ministry -- e.g. once Marriage Ministry's classes
# division ID is confirmed:
#     (999, "Marriage Ministry (MM): MM Classes"),
DIVISION_FILTERS = [
    (126, "Adult Discipleship (AD): AD ReNew"),
    (31, "Adult Discipleship (AD): AD Classes/Meetings/Groups"),
]

# Only these MemberTypeIds appear on the roster, sorted in this order
# (Leader first, then Member) -- everything else (Coach, InActive,
# Prospect, Volunteer, or an unmapped/stray value) is excluded entirely.
MEMBER_TYPE_SORT_SQL = "CASE om.MemberTypeId WHEN 140 THEN 0 WHEN 220 THEN 1 ELSE 2 END"
MEMBER_TYPE_LABELS = {140: "Leader", 220: "Member"}

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


# ============================================================
# SQL: active involvements in the configured divisions (the picker list).
# Organizations -> DivOrg is one-to-many, so use EXISTS rather than a plain
# JOIN to avoid duplicate-row fan-out (per DB_REFERENCE.md).
# ============================================================
division_ids_sql = ", ".join(str(div_id) for div_id, _ in DIVISION_FILTERS)
group_label_case_sql = " ".join(
    "WHEN EXISTS (SELECT 1 FROM dbo.DivOrg dChk WHERE dChk.OrgId = o.OrganizationId AND dChk.DivId = {0}) THEN '{1}'".format(
        div_id, label.replace("'", "''")
    )
    for div_id, label in DIVISION_FILTERS
)

sql_orgs = """
SELECT
    o.OrganizationId,
    o.OrganizationName,
    ISNULL(o.MemberCount, 0) AS MemberCount,
    GroupLabel = CASE {group_label_case_sql} ELSE 'Other' END
FROM dbo.Organizations o
WHERE o.OrganizationStatusId = {active_status_id}
  AND EXISTS (
      SELECT 1 FROM dbo.DivOrg d2 WHERE d2.OrgId = o.OrganizationId AND d2.DivId IN ({division_ids_sql})
  )
ORDER BY o.OrganizationName
""".format(
    group_label_case_sql=group_label_case_sql,
    division_ids_sql=division_ids_sql,
    active_status_id=ACTIVE_STATUS_ID,
)

org_rows = list(q.QuerySql(sql_orgs))

requested_org_id = to_int(getattr(model.Data, "OrgId", ""))
selected_org = None
for r in org_rows:
    if r.OrganizationId == requested_org_id:
        selected_org = r
        break

if selected_org is None:
    # ============================================================
    # No (valid) involvement selected -- render the picker.
    # ============================================================
    group_order = [label for _, label in DIVISION_FILTERS] + ["Other"]
    grouped = {}
    for r in org_rows:
        grouped.setdefault(r.GroupLabel, []).append(r)

    optgroups_html = ""
    for label in group_order:
        rows_in_group = grouped.get(label)
        if not rows_in_group:
            continue
        options = "".join(
            '<option value="{oid}">{name} ({count} member{plural})</option>'.format(
                oid=r.OrganizationId,
                name=esc(r.OrganizationName),
                count=r.MemberCount,
                plural="" if r.MemberCount == 1 else "s",
            )
            for r in rows_in_group
        )
        optgroups_html += '<optgroup label="{0}">{1}</optgroup>'.format(esc(label), options)

    print(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Choose an Involvement -- Roster Report</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 20px; color: #222; }}
  h1 {{ font-size: 20px; }}
  .meta {{ color: #555; font-size: 13px; margin-bottom: 16px; }}
  select {{ font-size: 14px; padding: 6px; min-width: 420px; }}
  button {{ font-size: 14px; padding: 6px 16px; margin-left: 8px; }}
</style>
</head>
<body>
<h1>Choose an Involvement</h1>
<p class="meta">{count} active involvement(s) found in the configured ministry divisions. Pick one and click Apply to generate its printable roster.</p>
<form method="get">
  <select name="OrgId" required>
    <option value="">-- Select an involvement --</option>
    {optgroups}
  </select>
  <button type="submit">Apply</button>
</form>
</body>
</html>""".format(count=len(org_rows), optgroups=optgroups_html)
    )

else:
    # ============================================================
    # Involvement selected -- build its roster.
    # ============================================================
    org_id = selected_org.OrganizationId
    org_label = selected_org.OrganizationName

    sql_meetings = """
    SELECT DISTINCT CAST(m.MeetingDate AS DATE) AS MeetingDate
    FROM dbo.Meetings m
    WHERE m.OrganizationId = {org_id}
      AND ISNULL(m.Canceled, 0) = 0
      AND ISNULL(m.DidNotMeet, 0) = 0
    ORDER BY MeetingDate
    """.format(org_id=org_id)

    # Only Leader/Member MemberTypeIds; Leaders sorted before Members within
    # each gender section (list order below is preserved through the later
    # per-gender split).
    sql_roster = """
    SELECT
        p.PeopleId,
        Name = LTRIM(RTRIM(COALESCE(NULLIF(p.PreferredName, ''), NULLIF(p.NickName, ''), p.FirstName, '') + ' ' + COALESCE(p.LastName, ''))),
        LastName = COALESCE(p.LastName, ''),
        GenderId = ISNULL(p.GenderId, 0),
        Gender = COALESCE(NULLIF(g.Description, ''), NULLIF(g.Code, ''), 'Unknown'),
        MemberTypeId = om.MemberTypeId,
        CellPhone = p.CellPhone,
        Email = COALESCE(NULLIF(LTRIM(RTRIM(p.EmailAddress)), ''), NULLIF(LTRIM(RTRIM(p.EmailAddress2)), ''), '')
    FROM dbo.OrganizationMembers om
    JOIN dbo.People p ON p.PeopleId = om.PeopleId
    LEFT JOIN lookup.Gender g ON g.Id = p.GenderId
    WHERE om.OrganizationId = {org_id}
      AND om.MemberTypeId IN (140, 220)
    ORDER BY {member_type_sort_sql}, p.LastName, Name
    """.format(org_id=org_id, member_type_sort_sql=MEMBER_TYPE_SORT_SQL)

    # Per DB_REFERENCE.md: require AttendanceFlag = 1, defensively exclude
    # NoShow = 1.
    sql_attend = """
    SELECT
        a.PeopleId,
        CAST(a.MeetingDate AS DATE) AS MeetingDate
    FROM dbo.Attend a
    JOIN dbo.Meetings m ON m.MeetingId = a.MeetingId
    WHERE a.OrganizationId = {org_id}
      AND a.AttendanceFlag = 1
      AND ISNULL(a.NoShow, 0) = 0
      AND ISNULL(m.Canceled, 0) = 0
      AND ISNULL(m.DidNotMeet, 0) = 0
    """.format(org_id=org_id)

    meeting_rows = list(q.QuerySql(sql_meetings))
    roster_rows = list(q.QuerySql(sql_roster))
    attend_rows = list(q.QuerySql(sql_attend))

    meeting_dates = [normalize_date(r.MeetingDate) for r in meeting_rows]

    attended_by_person = {}
    for r in attend_rows:
        attended_by_person.setdefault(r.PeopleId, set()).add(normalize_date(r.MeetingDate))

    def build_rows_html(people):
        rows = []
        for p in people:
            dates_attended = attended_by_person.get(p.PeopleId, set())
            cells = []
            for d in meeting_dates:
                mark = "&#10003;" if d in dates_attended else ""
                cells.append('<td class="mark">{0}</td>'.format(mark))
            total = len(dates_attended)
            phone = model.FmtPhone(p.CellPhone) if p.CellPhone else ""
            rows.append(
                "<tr><td>{name}</td><td>{gender}</td><td>{mtype}</td>{cells}"
                '<td class="total">{total}</td><td>{phone}</td><td class="email">{email}</td></tr>'.format(
                    name=esc(p.Name),
                    gender=esc(p.Gender),
                    mtype=esc(member_type_label(p.MemberTypeId)),
                    cells="".join(cells),
                    total=total,
                    phone=esc(phone),
                    email=esc(p.Email),
                )
            )
        return "".join(rows)

    men = [p for p in roster_rows if p.GenderId == 1]
    women = [p for p in roster_rows if p.GenderId == 2]
    other = [p for p in roster_rows if p.GenderId not in (1, 2)]

    col_headers = "".join(
        '<th class="mark">{0}</th>'.format(esc(fmt_col_header(d))) for d in meeting_dates
    )

    def build_section_html(title, people, page_break):
        break_class = " page-break" if page_break else ""
        return """
<div class="section{break_class}">
  <h2>{title} <span class="count">({count})</span></h2>
  <table>
    <thead>
      <tr>
        <th>Name</th><th>Gender</th><th>Member Type</th>{col_headers}<th class="total">Total</th><th>Phone</th><th>Email</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</div>
""".format(
            break_class=break_class,
            title=esc(title),
            count=len(people),
            col_headers=col_headers,
            rows=build_rows_html(people),
        )

    sections_data = [
        (name, people)
        for name, people in (("Men", men), ("Women", women), ("Unspecified Gender", other))
        if people
    ]

    sections_html = "".join(
        build_section_html(title, people, page_break=(i > 0))
        for i, (title, people) in enumerate(sections_data)
    )

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
  td.email {{ white-space: normal; }}
</style>
</head>
<body>
<p class="no-print"><a href="?">&larr; Choose a different involvement</a></p>
<h1>{org_label} -- Roster</h1>
<p class="meta">Organization {org_id} &middot; {meeting_count} meeting(s) through {last_date} &middot; {total_count} total member(s)</p>
{sections}
</body>
</html>""".format(
            org_label=esc(org_label),
            org_id=org_id,
            meeting_count=len(meeting_dates),
            last_date=esc(fmt_col_header(meeting_dates[-1])) if meeting_dates else "n/a",
            total_count=len(roster_rows),
            sections=sections_html,
        )
    )
