"""
AD_ReNewRosterReport.py

TouchPoint Special Content (Python Script). Read-only.

Printable roster for the "ReNew Fall 2026" involvement (OrganizationId 3906,
Program 1119 "Adult Discipleship" / Division 126 "AD ReNew"). Splits members
onto separate print sections/pages by People.GenderId -- Men, then Women.
Anyone with unset/Unknown gender lands on a third "Unspecified Gender"
section instead of being silently dropped.

Per person: Name, Gender, Member Type, one attendance column per Monday
meeting this org has actually held (checkmark if present, blank if absent,
canceled/did-not-meet meetings excluded from the grid entirely), a Total
column summing weeks attended, then Phone and Email.

Deploy: Admin > Advanced > Special Content > Python Scripts > +New
Script name suggestion: AD_ReNewRosterReport
Run directly in TouchPoint; renders a print-styled HTML report, no email
sent. Use the browser's Print (Ctrl/Cmd+P) -- CSS forces landscape and a
page break between each gender section.

Config values to update if this is reused for a different ReNew term:
    ORG_ID    -- Organizations.OrganizationId for that term's ReNew roster org
    ORG_LABEL -- display title only
"""

import re

# ============================================================
# Config
# ============================================================
ORG_ID = 3906
ORG_LABEL = "ReNew Fall 2026"

# lookup.MemberType global labels (confirmed in DB_REFERENCE.md) -- mapped
# by hand rather than joined, since the lookup table's label column name is
# not confirmed at RPC.
MEMBER_TYPE_LABELS = {
    136: "Coach",
    140: "Leader",
    220: "Member",
    230: "InActive",
    311: "Prospect",
    710: "Volunteer",
}

# ============================================================
# SQL: meeting dates this org has actually held (excludes canceled/
# did-not-meet meetings), used to build one grid column per Monday.
# ============================================================
sql_meetings = """
SELECT DISTINCT CAST(m.MeetingDate AS DATE) AS MeetingDate
FROM dbo.Meetings m
WHERE m.OrganizationId = {org_id}
  AND ISNULL(m.Canceled, 0) = 0
  AND ISNULL(m.DidNotMeet, 0) = 0
ORDER BY MeetingDate
""".format(org_id=ORG_ID)

# ============================================================
# SQL: current roster (OrganizationMembers + People)
# ============================================================
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
ORDER BY p.LastName, Name
""".format(org_id=ORG_ID)

# ============================================================
# SQL: attendance -- who was present at which (non-canceled) meeting.
# Per DB_REFERENCE.md: require AttendanceFlag = 1, defensively exclude
# NoShow = 1.
# ============================================================
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
""".format(org_id=ORG_ID)

def normalize_date(value):
    # RPC's q.QuerySql returns dates as either 'YYYY-MM-DD[ HH:MM:SS]' or
    # 'M/D/YYYY' depending on context -- normalize both to 'YYYY-MM-DD' so
    # date-string comparisons/lookups are consistent. Same helper as
    # student-contact-export/SM_StudentContactExport.py.
    value = str(value or "").strip().replace(" ", " ")
    value = value.split("T")[0].split(" ")[0]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if match:
        return "{0}-{1}-{2}".format(
            match.group(3), match.group(1).zfill(2), match.group(2).zfill(2)
        )
    return value


meeting_rows = list(q.QuerySql(sql_meetings))
roster_rows = list(q.QuerySql(sql_roster))
attend_rows = list(q.QuerySql(sql_attend))

meeting_dates = [normalize_date(r.MeetingDate) for r in meeting_rows]

attended_by_person = {}
for r in attend_rows:
    attended_by_person.setdefault(r.PeopleId, set()).add(normalize_date(r.MeetingDate))


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
<h1>{org_label} -- Roster</h1>
<p class="meta">Organization {org_id} &middot; {meeting_count} meeting(s) through {last_date} &middot; {total_count} total member(s)</p>
{sections}
</body>
</html>""".format(
        org_label=esc(ORG_LABEL),
        org_id=ORG_ID,
        meeting_count=len(meeting_dates),
        last_date=esc(fmt_col_header(meeting_dates[-1])) if meeting_dates else "n/a",
        total_count=len(roster_rows),
        sections=sections_html,
    )
)
