"""
RPC_ChannelReport.py

TouchPoint Special Content (Python Script). Read-only.

Church-wide report of every involvement with a mobile-app Channel enabled,
built for Arianah Torres (Men's Ministry Assistant & Social Media Associate)
and Marlene Godinez, 2026-08-31 request. Ari's underlying problem: the
native Admin > Communications > Channels Excel export lists every
channel-enabled involvement, including inactive ones, with no column
telling her which is which -- she uses the report to find past-due/inactive
involvements that still have a channel enabled, for app cleanup.

Columns (per Ari's spec): Involvement ID, Name, Type, Campus, Photo,
Public/Closed, Leaders (count), Followers (count), Posts (count),
Active/Inactive. A Status dropdown (All / Active Only / Inactive Only)
reruns the query server-side -- "Inactive Only" is the cleanup worklist.

Schema, all confirmed live 2026-08-31 (see DB_REFERENCE.md, "Mobile App
Channels"):
  - Organizations.MobileChannelEnabled = 1  -- the "has a Channel" filter.
  - Organizations.MobileChannelPrivate      -- 0/NULL = public, 1 = closed.
    Confirmed by pattern: only 15 of 252 live rows are public, and every
    one is a broad standing channel (RockPointe Church, Marriage Ministry,
    etc.) -- exactly what "public" should mean here.
  - Organizations.ImageUrl                  -- the Photo field. Confirmed
    live: RockPointe Church (OrgId 3506) has ImageUrl set but NOT BadgeUrl,
    and its live app channel clearly shows a photo. BadgeUrl is NOT the
    channel photo -- do not use it here.
  - Organizations.OrganizationStatusId      -- 30 = Active, 40 = Inactive
    (already confirmed elsewhere in DB_REFERENCE.md).
  - OrganizationMembers, MemberTypeId = 140 (Leader), InactiveDate IS NULL
    -- Leaders count. No plural-leader table exists at RPC.
  - OrganizationMembers, all InactiveDate IS NULL rows -- Followers count.
    Confirmed live: RockPointe Church's app screen shows "889 Members",
    an exact match to this count for that org. (The app itself labels this
    "Members"; Ari's requested column name is "Followers" -- same number.)
  - dbo.UserPost, OrganizationId match, DeletedDate IS NULL -- Posts count.

This report intentionally has NO ministry/division picker and NO row-level
security scoping (unlike RPC_AttendanceRoster.py) -- it's a small,
named-audience admin/cleanup tool for Ari, Marlene, and Brian covering
every channel church-wide, not a self-service report for arbitrary staff.
Add row-level security only if a broader audience for this report is
requested later.

Deploy: Admin > Advanced > Special Content > Python Scripts > +New
Script name suggestion: RPC_ChannelReport
Access via /PyScript/RPC_ChannelReport so the Status dropdown's Apply
button (a GET form back to the same URL) works correctly.

Not yet live-tested end to end as a Python Script -- the underlying SQL
was run and its output validated live 2026-08-31 (data-dictionary-expander/
sql/focused/RPC_ChannelReportDiscovery.sql, 252 rows), but this specific
script (picker chrome, CSV export JS, checkmark rendering) has not been
deployed and run inside TouchPoint yet.
"""

# ============================================================
# Config
# ============================================================
ACTIVE_STATUS_ID = 30
INACTIVE_STATUS_ID = 40

STATUS_OPTIONS = [
    ("all", "All (Active + Inactive)"),
    ("active", "Active Only"),
    ("inactive", "Inactive Only -- cleanup worklist"),
]
STATUS_KEYS = [k for k, _ in STATUS_OPTIONS]
DEFAULT_STATUS = "all"


# ============================================================
# Helpers
# ============================================================
def esc(s):
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def valid_status(value):
    return value if value in STATUS_KEYS else DEFAULT_STATUS


def checkmark(is_true):
    # Faithful to Ari's spec: a check mark when true, nothing when false --
    # not a "Yes/No" label.
    return "&#10003;" if is_true else ""


# ============================================================
# Query
# ============================================================
requested_status = valid_status(str(getattr(model.Data, "Status", "") or ""))

status_filter_sql = ""
if requested_status == "active":
    status_filter_sql = "AND o.OrganizationStatusId = {0}".format(ACTIVE_STATUS_ID)
elif requested_status == "inactive":
    status_filter_sql = "AND o.OrganizationStatusId = {0}".format(INACTIVE_STATUS_ID)

sql_channels = """
SELECT
    o.OrganizationId,
    o.OrganizationName,
    ISNULL(NULLIF(ot.Description, ''), CAST(o.OrganizationTypeId AS VARCHAR(10))) AS OrganizationType,
    ISNULL(NULLIF(c.Description, ''), '') AS CampusName,
    CASE WHEN o.OrganizationStatusId = {active_status} THEN 'Active'
         WHEN o.OrganizationStatusId = {inactive_status} THEN 'Inactive'
         ELSE 'Other'
    END AS StatusLabel,
    CASE WHEN ISNULL(o.ImageUrl, '') <> '' THEN 1 ELSE 0 END AS HasPhoto,
    CASE WHEN ISNULL(o.MobileChannelPrivate, 0) = 0 THEN 1 ELSE 0 END AS IsPublic,
    ISNULL(leaderStats.LeaderCount, 0) AS LeaderCount,
    ISNULL(followerStats.FollowerCount, 0) AS FollowerCount,
    ISNULL(postStats.PostCount, 0) AS PostCount
FROM dbo.Organizations o
LEFT JOIN lookup.OrganizationType ot ON ot.Id = o.OrganizationTypeId
LEFT JOIN lookup.Campus c ON c.Id = o.CampusId
OUTER APPLY (
    SELECT COUNT(*) AS LeaderCount
    FROM dbo.OrganizationMembers om
    WHERE om.OrganizationId = o.OrganizationId
      AND om.MemberTypeId = 140
      AND om.InactiveDate IS NULL
) leaderStats
OUTER APPLY (
    SELECT COUNT(*) AS FollowerCount
    FROM dbo.OrganizationMembers om
    WHERE om.OrganizationId = o.OrganizationId
      AND om.InactiveDate IS NULL
) followerStats
OUTER APPLY (
    SELECT COUNT(*) AS PostCount
    FROM dbo.UserPost up
    WHERE up.OrganizationId = o.OrganizationId
      AND up.DeletedDate IS NULL
) postStats
WHERE o.MobileChannelEnabled = 1
{status_filter}
ORDER BY StatusLabel, CampusName, o.OrganizationName
""".format(
    active_status=ACTIVE_STATUS_ID,
    inactive_status=INACTIVE_STATUS_ID,
    status_filter=status_filter_sql,
)

channel_rows = list(q.QuerySql(sql_channels))

active_count = sum(1 for r in channel_rows if r.StatusLabel == "Active")
inactive_count = sum(1 for r in channel_rows if r.StatusLabel == "Inactive")


# ============================================================
# Render
# ============================================================
status_options_html = "".join(
    '<option value="{0}"{1}>{2}</option>'.format(
        key, ' selected' if key == requested_status else '', esc(label)
    )
    for key, label in STATUS_OPTIONS
)

table_rows_html = "".join(
    """<tr>
  <td>{oid}</td>
  <td>{name}</td>
  <td>{otype}</td>
  <td>{campus}</td>
  <td class="mark" data-csv="{photo_csv}">{photo}</td>
  <td class="mark" data-csv="{public_csv}">{public}</td>
  <td class="num">{leaders}</td>
  <td class="num">{followers}</td>
  <td class="num">{posts}</td>
  <td class="status status-{status_class}">{status}</td>
</tr>""".format(
        oid=r.OrganizationId,
        name=esc(r.OrganizationName),
        otype=esc(r.OrganizationType),
        campus=esc(r.CampusName),
        photo=checkmark(r.HasPhoto == 1),
        photo_csv="Yes" if r.HasPhoto == 1 else "No",
        public=checkmark(r.IsPublic == 1),
        public_csv="Public" if r.IsPublic == 1 else "Closed",
        leaders=r.LeaderCount,
        followers=r.FollowerCount,
        posts=r.PostCount,
        status=esc(r.StatusLabel),
        status_class=r.StatusLabel.lower(),
    )
    for r in channel_rows
)

print(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mobile App Channels Report</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 20px; color: #222; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .meta {{ color: #555; font-size: 13px; margin-bottom: 16px; }}
  .controls {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
  .controls label {{ font-size: 13px; color: #444; }}
  select {{ font-size: 14px; padding: 6px; }}
  button {{ font-size: 14px; padding: 6px 16px; cursor: pointer; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 5px 8px; font-size: 13px; text-align: left; }}
  th {{ background: #f2f2f2; position: sticky; top: 0; }}
  td.mark {{ text-align: center; width: 60px; }}
  td.num {{ text-align: center; width: 70px; }}
  td.status {{ font-weight: bold; }}
  .status-active {{ color: #1a7a1a; }}
  .status-inactive {{ color: #a33; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  th.sortable {{ cursor: pointer; user-select: none; white-space: nowrap; }}
  th.sortable:hover {{ background: #e6e6e6; }}
  th.sortable::after {{ content: '\\2195'; color: #999; margin-left: 4px; font-size: 11px; }}
  th.sortable.sort-asc::after {{ content: '\\2191'; color: #222; }}
  th.sortable.sort-desc::after {{ content: '\\2193'; color: #222; }}
</style>
</head>
<body>
<h1>Mobile App Channels Report</h1>
<p class="meta">{total} channel(s) enabled &middot; {active_count} Active &middot; {inactive_count} Inactive</p>
<form method="get" class="controls">
  <label for="Status">Show:</label>
  <select name="Status" id="Status">{status_options}</select>
  <button type="submit">Apply</button>
  <button type="button" onclick="exportCsv()">Download CSV</button>
</form>
<table id="channelTable">
  <thead>
    <tr>
      <th class="sortable" data-type="num">Involvement ID</th>
      <th class="sortable" data-type="text">Name</th>
      <th class="sortable" data-type="text">Type</th>
      <th class="sortable" data-type="text">Campus</th>
      <th class="sortable" data-type="text">Photo</th>
      <th class="sortable" data-type="text">Public</th>
      <th class="sortable" data-type="num">Leaders</th>
      <th class="sortable" data-type="num">Followers</th>
      <th class="sortable" data-type="num">Posts</th>
      <th class="sortable" data-type="text">Status</th>
    </tr>
  </thead>
  <tbody>
    {table_rows}
  </tbody>
</table>
<script>
function csvCell(v) {{
  v = String(v == null ? '' : v);
  if (v.indexOf(',') >= 0 || v.indexOf('"') >= 0 || v.indexOf('\\n') >= 0) {{
    v = '"' + v.replace(/"/g, '""') + '"';
  }}
  return v;
}}
function exportCsv() {{
  var table = document.getElementById('channelTable');
  var lines = [];
  var headerCells = table.querySelectorAll('thead th');
  lines.push(Array.prototype.map.call(headerCells, function(th) {{
    return csvCell(th.textContent);
  }}).join(','));
  var rows = table.querySelectorAll('tbody tr');
  rows.forEach(function(tr) {{
    var cells = tr.querySelectorAll('td');
    lines.push(Array.prototype.map.call(cells, function(td) {{
      var v = td.hasAttribute('data-csv') ? td.getAttribute('data-csv') : td.textContent;
      return csvCell(v);
    }}).join(','));
  }});
  var blob = new Blob(['\\ufeff' + lines.join('\\r\\n')], {{type: 'text/csv;charset=utf-8'}});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'rpc-channel-report-' + new Date().toISOString().slice(0, 10) + '.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function() {{ URL.revokeObjectURL(a.href); }}, 1000);
}}

(function() {{
  // Click-to-sort table headers. Client-side only -- this table tops out
  // around a few hundred rows, so re-sorting the DOM in the browser is
  // instant and needs no round trip back through TouchPoint. Sorting
  // physically reorders the <tr> elements, so exportCsv() above (which
  // reads tbody rows in their current DOM order) exports in whatever
  // sort is currently showing, with no extra code.
  var table = document.getElementById('channelTable');
  var tbody = table.querySelector('tbody');
  var headers = Array.prototype.slice.call(table.querySelectorAll('th.sortable'));
  var sortState = {{col: -1, dir: 1}};

  function cellValue(tr, colIndex) {{
    var td = tr.children[colIndex];
    return td.hasAttribute('data-csv') ? td.getAttribute('data-csv') : td.textContent.trim();
  }}

  function compareRows(a, b, colIndex, isNumeric) {{
    var va = cellValue(a, colIndex);
    var vb = cellValue(b, colIndex);
    if (isNumeric) {{
      return (parseFloat(va) || 0) - (parseFloat(vb) || 0);
    }}
    return va.localeCompare(vb, undefined, {{numeric: true, sensitivity: 'base'}});
  }}

  headers.forEach(function(th, colIndex) {{
    th.addEventListener('click', function() {{
      var isNumeric = th.getAttribute('data-type') === 'num';
      var dir = (sortState.col === colIndex) ? -sortState.dir : 1;
      sortState = {{col: colIndex, dir: dir}};

      var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
      rows.sort(function(a, b) {{ return dir * compareRows(a, b, colIndex, isNumeric); }});
      rows.forEach(function(tr) {{ tbody.appendChild(tr); }});

      headers.forEach(function(h) {{ h.classList.remove('sort-asc', 'sort-desc'); }});
      th.classList.add(dir === 1 ? 'sort-asc' : 'sort-desc');
    }});
  }});
}})();
</script>
</body>
</html>""".format(
        total=len(channel_rows),
        active_count=active_count,
        inactive_count=inactive_count,
        status_options=status_options_html,
        table_rows=table_rows_html,
    )
)
