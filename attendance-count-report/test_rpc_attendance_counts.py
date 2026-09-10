# -*- coding: utf-8 -*-
"""Offline test suite for RPC_AttendanceCounts.py.

Runs the real script end-to-end against a mocked TouchPoint `q`/`model`
with fabricated (non-PII) data and captures the HTML it prints. No live
TouchPoint or database access -- run it from anywhere:

    python3 attendance-count-report/test_rpc_attendance_counts.py

What this CAN prove: the four picker stages route correctly, the counts
arithmetic (per-cell, per-row, per-column, grand total, and the
Member/Leader/Other split) reconciles, the three cell states stay
distinguishable, the options round-trip through the query string, hostile
input falls back safely, and the page survives being injected into a page
with a hostile stylesheet.

What it CANNOT prove: that the SQL is valid against RPC's live schema, or
that the numbers match what TouchPoint's own attendance screens show. See
README.md's "Not yet live-validated" section.

Fabricated fixture data only -- no real RPC member data lives here.
"""
import io
import os
import re
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "RPC_AttendanceCounts.py")


class Row(object):
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class Data(object):
    def __init__(self, **kw):
        self._d = dict(kw)

    def __getattr__(self, name):
        return self._d.get(name, "")


CMS_HOST = "https://example.invalid"  # fabricated -- never RPC's real host


class Model(object):
    def __init__(self, user_id, host=CMS_HOST, **data):
        self.UserPeopleId = user_id
        self.Data = Data(**data)
        self.CmsHost = host


# ---------------------------------------------------------------------
# Fixtures. Shaped to exercise every cell state and bucket at once:
#   5001  meets all 3 dates, has a Guest (member type 310 -> "Other")
#   5002  skips 8/31 entirely            -> a dim middot, NOT a zero
#   5003  meets 9/7 but nobody marked    -> a red 0, NOT a middot
#   5004  holds no meeting in range      -> the HideEmpty case
# ---------------------------------------------------------------------
PROGRAMS = [Row(Id=1109, Name="Student Ministry (SM)")]
DIVISIONS = [Row(Id=11, Name="SM Sundays")]
ORGS = [
    Row(OrganizationId=5001, OrganizationName="SM: CC 6th Guys", MemberCount=20),
    Row(OrganizationId=5002, OrganizationName="SM: CC 6th Girls", MemberCount=16),
    Row(OrganizationId=5003, OrganizationName="SM: PS 9th Guys", MemberCount=24),
    Row(OrganizationId=5004, OrganizationName="SM: CC Summer Groups 26", MemberCount=8),
    # A name containing a comma -- the one thing that forces CSV quoting.
    Row(OrganizationId=5005, OrganizationName="SM: PS Guys, Grades 7-8", MemberCount=12),
    # Meets twice in the SAME week (Mon 8/24 and Wed 8/26) -- the only
    # fixture that distinguishes date columns from week columns. Used only
    # by the week-grouping section, so it changes nothing above.
    Row(OrganizationId=5006, OrganizationName="SM: PS Welcome Team", MemberCount=10),
]
D_WED = "2026-08-26"          # Wednesday of D1's week
W1, W2, W3 = "2026-08-23", "2026-08-30", "2026-09-06"   # the Sundays
D1, D2, D3 = "2026-08-24", "2026-08-31", "2026-09-07"

MEETINGS = {
    5001: [D1, D2, D3],
    5002: [D1, D3],
    5003: [D1, D2, D3],
    5004: [],
    5005: [D1],
    5006: [D1, D_WED],
}

# (OrgId, date) -> how many meetings were held that day. Anything not listed
# held exactly one. 5002 on 9/7 is the multi-meeting case (DB_REFERENCE.md:
# the PS Welcome Team really did hold three on 2026-08-16).
MULTI = {(5002, D3): 2}


def meeting_id(oid, d, k=0):
    """Deterministic fake MeetingId, so link assertions can name one."""
    return oid * 100000 + int(d.replace("-", "")[4:]) * 10 + k

# (OrgId, date) -> {MemberTypeId: count}. 220 Member, 140 Leader,
# 710 Volunteer (also a "leader"), 310 Guest (an "other").
ATTEND = {
    (5001, D1): {220: 11, 140: 2},
    (5001, D2): {220: 14, 140: 2},
    (5001, D3): {220: 12, 140: 2, 310: 1},
    (5002, D1): {220: 10, 140: 1},
    (5002, D3): {220: 9, 140: 1},
    (5003, D1): {220: 16, 710: 3},
    (5003, D2): {220: 13, 710: 3},
    # (5003, D3) deliberately absent: the meeting happened, nobody marked.
    (5005, D1): {220: 7},
    (5006, D1): {220: 5},
    (5006, D_WED): {220: 7},
}


def _ids(s):
    m = re.search(r"IN \(([0-9,\s]+)\)", s)
    return [int(x) for x in m.group(1).split(",")] if m else []


def _range(s):
    m = re.search(r"BETWEEN '(\d{4}-\d{2}-\d{2})' AND '(\d{4}-\d{2}-\d{2})'", s)
    return (m.group(1), m.group(2)) if m else ("0001-01-01", "9999-12-31")


class Q(object):
    def __init__(self):
        self.seen = []

    def QuerySql(self, sql):
        s = " ".join(sql.split())
        self.seen.append(s)
        if "FROM dbo.Program p" in s:
            return list(PROGRAMS)
        if "FROM dbo.Division d" in s:
            return list(DIVISIONS)
        if "FROM dbo.Organizations o WHERE o.OrganizationStatusId" in s:
            return list(ORGS)
        if "FROM dbo.Meetings m WHERE" in s:
            oids, (lo, hi) = _ids(s), _range(s)
            out = []
            for oid in oids:
                for d in MEETINGS.get(oid, []):
                    if lo <= d <= hi:
                        for k in range(MULTI.get((oid, d), 1)):
                            out.append(Row(OrganizationId=oid,
                                           MeetingId=meeting_id(oid, d, k),
                                           MeetingDate=d))
            out.sort(key=lambda r: r.MeetingDate)
            return out
        if "FROM dbo.Attend a JOIN dbo.Meetings m" in s:
            oids, (lo, hi) = _ids(s), _range(s)
            out = []
            for (oid, d), types in sorted(ATTEND.items()):
                if oid in oids and lo <= d <= hi:
                    for mt, n in sorted(types.items()):
                        out.append(Row(OrganizationId=oid, MeetingDate=d,
                                       MemberTypeId=mt, Cnt=n))
            return out
        raise AssertionError("unmatched SQL:\n" + s[:400])


def run(user_id=47110, host=CMS_HOST, **data):
    src = io.open(SCRIPT, encoding="utf-8").read()
    qobj = Q()
    g = {"__name__": "__main__", "model": Model(user_id, host, **data), "q": qobj}
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        exec(compile(src, SCRIPT, "exec"), g)
    finally:
        sys.stdout = old
    return buf.getvalue(), qobj


BASE = dict(ProgId="1109", DivId="11", StartDate=D1, EndDate=D3)


def report(**over):
    kw = dict(BASE)
    kw.update(over)
    return run(**kw)[0]


def row_cells(html, name):
    """The <td> text of the row whose first cell is `name`, entities and
    tags stripped, so assertions read as the numbers a person would see.

    Cells are wrapped in deep links now, so the tag-stripping here is what
    keeps every arithmetic assertion above about numbers rather than markup.
    The superscript on a multi-meeting cell survives stripping and is
    asserted for separately."""
    m = re.search(
        r'<tr[^>]*><td class="ac-name">(?:<a[^>]*>)?' + re.escape(name) +
        r'(?:</a>)?</td>(.*?)</tr>',
        html, re.S)
    if not m:
        return None
    cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)
    return [re.sub(r"<[^>]+>", "", c).replace("&middot;", ".").replace("&mdash;", "-").strip()
            for c in cells]


fails = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name +
          (("\n         " + str(detail)) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


# =====================================================================
print("=== 1. PICKER WALKTHROUGH (the roster report's flow, kept) ===")
h1, _ = run()
check("no ProgId -> stage 1 asks for a ministry", "Choose a Ministry" in h1)
check("stage 1 lists ministries from dbo.Program", "Student Ministry (SM)" in h1)
check("stage 1 marks itself current in the breadcrumb",
      '<span class="ac-on">1. Ministry</span>' in h1)

h2, _ = run(ProgId="1109")
check("ProgId only -> stage 2 asks for a division", "Choose a Division" in h2)
check("stage 2 lists divisions under that ministry", "SM Sundays" in h2)
check("stage 2 can go back to stage 1", '<a href="?">' in h2)

h3, _ = run(ProgId="1109", DivId="11")
check("ProgId+DivId -> stage 3 lists involvements as checkboxes",
      h3.count('class="ac-orgcheck"') == len(ORGS))
check("an involvement name with a comma survives into the checkbox list",
      "SM: PS Guys, Grades 7-8" in h3)
check("stage 3 offers Select all shown / Clear all",
      'id="selectAll"' in h3 and 'id="clearAll"' in h3)
check("stage 3 offers the 4/8/13-week presets",
      all(('data-weeks="%d"' % w) in h3 for w in (4, 8, 13)))
check("stage 3 defaults to an 8-week range ending today", (
    lambda: __import__("datetime").datetime.now().date().strftime("%Y-%m-%d") in h3)())
check("stage 3 has both date inputs, both required",
      h3.count('type="date"') == 2 and h3.count("required") >= 2)
check("stage 3 can go back to stage 2", 'href="?ProgId=1109"' in h3)

check("a stale ProgId falls back to stage 1, it does not error",
      "Choose a Ministry" in run(ProgId="999999")[0])
check("a stale DivId falls back to stage 2, it does not error",
      "Choose a Division" in run(ProgId="1109", DivId="999999")[0])
check("stale OrgIds fall back to stage 3, they do not error",
      'class="ac-orgcheck"' in report(OrgIds="999999,888888"))

# =====================================================================
print("\n=== 2. THE COUNTS GRID (the dashboard's output shape) ===")
h = report(OrgIds="5001,5002,5003")
# 5001: 11+2=13 | 14+2=16 | 12+2+1=15  -> 3 mtgs, 44 total, 14.7 avg
check("a normal row's per-date cells, meetings, total and average",
      row_cells(h, "SM: CC 6th Guys") == ["13", "16", "15", "3", "44", "14.7", "37", "6", "1"],
      row_cells(h, "SM: CC 6th Guys"))
# 5002 skipped 8/31 -> a dim middot, and Avg is over the 2 meetings it held
check("an involvement that did not meet that day shows a dim middot, not a 0",
      row_cells(h, "SM: CC 6th Girls") == ["11", ".", "102", "2", "21", "10.5", "19", "2", "0"],
      row_cells(h, "SM: CC 6th Girls"))  # "102" = the 10 plus its <sup>2</sup>
# 5003 met on 9/7 with nobody marked -> a real 0
check("an involvement that met with nobody marked shows a 0",
      row_cells(h, "SM: PS 9th Guys") == ["19", "16", "0", "3", "35", "11.7", "29", "6", "0"],
      row_cells(h, "SM: PS 9th Guys"))
check("the two cell states are visually distinct, not just textually",
      'class="ac-zero"' in h and 'class="ac-none"' in h)
check("the zero cell explains itself on hover",
      'title="Meeting held, nobody marked present. Open this meeting' in h)
check("the TOTAL row sums each date column and the roll-ups",
      row_cells(h, "TOTAL") == ["43", "32", "25", "3", "100", "33.3", "85", "14", "1"],
      row_cells(h, "TOTAL"))
check("Members + Leaders + Other reconciles to Total (85+14+1=100)",
      85 + 14 + 1 == 100)
check("date columns are headed M/D per the RPC Style Guide (no ordinals)",
      ">8/24</th>" in h and ">9/7</th>" in h and "24th" not in h)
check("a date column header carries the full date on hover",
      'title="August 24"' in h)

check("the stat bar reports dates, total, average and the peak date",
      all(x in h for x in ("meeting dates", "total attendance", "avg per date", "peak")))
check("the peak stat names the right date (8/24, 43)",
      re.search(r'ac-statval">43</span><span class="ac-statlbl">peak &mdash; 8/24', h) is not None)

# =====================================================================
print("\n=== 3. THE MEMBER-TYPE SPLIT ===")
check("Other appears only because a Guest (310) attended",
      ">Other</th>" in h)
check("the Other column names which member types landed in it",
      "Guest" in h and "neither Member nor Leader" in h)
no_guest = ATTEND.pop((5001, D3))
ATTEND[(5001, D3)] = {220: 12, 140: 2}
h_noguest = report(OrgIds="5001,5002,5003")
check("with no unmapped member types, the Other column is not rendered at all",
      ">Other</th>" not in h_noguest)
ATTEND[(5001, D3)] = no_guest
check("Volunteers (710) count as Leaders, not as Other",
      row_cells(h, "SM: PS 9th Guys")[-2] == "6")

h_mem = report(OrgIds="5001,5002,5003", CountWho="member")
check("CountWho=member filters every number (5001 total 37, not 44)",
      row_cells(h_mem, "SM: CC 6th Guys")[:6] == ["11", "14", "12", "3", "37", "12.3"],
      row_cells(h_mem, "SM: CC 6th Guys"))
check("a filtered report drops the breakdown columns rather than restating itself",
      ">Members</th>" not in h_mem and ">Leaders</th>" not in h_mem)
check("a filtered report says what it is filtered to",
      "Members only" in h_mem and "excludes everyone else" in h_mem)

h_ldr = report(OrgIds="5001,5002,5003", CountWho="leader")
check("CountWho=leader keeps only leaders/coaches/volunteers (5003 -> 3|3|0)",
      row_cells(h_ldr, "SM: PS 9th Guys")[:5] == ["3", "3", "0", "3", "6"],
      row_cells(h_ldr, "SM: PS 9th Guys"))
check("a bogus CountWho falls back to Everyone",
      ">Members</th>" in report(OrgIds="5001", CountWho="'; DROP TABLE"))

# =====================================================================
print("\n=== 4. OPTIONS ROUND-TRIP AND SORTING ===")
h_sorted = report(OrgIds="5001,5002,5003", SortBy="total")
order = re.findall(r'<td class="ac-name"><a[^>]*>(SM: [^<]+)</a></td>', h_sorted)
check("SortBy=total orders rows by total attendance, highest first",
      order == ["SM: CC 6th Guys", "SM: PS 9th Guys", "SM: CC 6th Girls"], order)
order_name = re.findall(r'<td class="ac-name"><a[^>]*>(SM: [^<]+)</a></td>', h)
check("the default sort is by involvement name",
      order_name == ["SM: CC 6th Girls", "SM: CC 6th Guys", "SM: PS 9th Guys"], order_name)
check("a bogus SortBy falls back to name, it does not error",
      re.findall(r'<td class="ac-name"><a[^>]*>(SM: [^<]+)</a></td>',
                 report(OrgIds="5001,5002,5003", SortBy="nonsense")) == order_name)

h_empty = report(OrgIds="5001,5004")
check("an involvement with no meetings is shown by default, all middots",
      row_cells(h_empty, "SM: CC Summer Groups 26") == [".", ".", ".", "0", "0", "-", "0", "0", "0"],
      row_cells(h_empty, "SM: CC Summer Groups 26"))
h_hide = report(OrgIds="5001,5004", HideEmpty="1")
check("HideEmpty=1 drops it", row_cells(h_hide, "SM: CC Summer Groups 26") is None)
check("HideEmpty says how many it dropped", "1 selected involvement(s) held no meeting" in h_hide)
# HideEmpty can never empty the table: `dates` is the union of the selected
# involvements' meeting dates, so an all-empty selection has already hit the
# "no meetings in that date range" page before hiding is considered.
check("a selection where nothing met lands on the no-meetings page, not an empty grid",
      "No meetings in that date range" in report(OrgIds="5004", HideEmpty="1"))
check("...with or without HideEmpty",
      "No meetings in that date range" in report(OrgIds="5004"))

back = re.search(r'ac-back ac-no-print"><a href="([^"]+)"', h_hide)
check("the back link preserves every option except the involvements",
      back is not None
      and "OrgIds" not in back.group(1)
      and "HideEmpty=1" in back.group(1)
      and "StartDate=" + D1 in back.group(1),
      back.group(1) if back else None)

# =====================================================================
print("\n=== 5. HOSTILE INPUT (the query string is the only untrusted path) ===")
_, qbad = run(ProgId="1109", DivId="11", OrgIds="5001",
              StartDate="2026-08-24'; DROP TABLE dbo.Attend --", EndDate=D3)
meeting_sql = [s for s in qbad.seen if "FROM dbo.Meetings m WHERE" in s]
check("a malformed StartDate never reaches SQL",
      meeting_sql and "DROP TABLE" not in meeting_sql[0], meeting_sql[:1])
check("...and falls back to the 8-week default instead of erroring",
      "Attendance Counts" in report(OrgIds="5001", StartDate="not-a-date"))
check("an impossible-but-well-formed date (2026-02-31) also falls back",
      "Attendance Counts" in report(OrgIds="5001", StartDate="2026-02-31"))

_, qswap = run(ProgId="1109", DivId="11", OrgIds="5001", StartDate=D3, EndDate=D1)
swapped = [s for s in qswap.seen if "FROM dbo.Meetings m WHERE" in s][0]
check("a backwards date range is swapped, not queried as an empty range",
      "BETWEEN '%s' AND '%s'" % (D1, D3) in swapped)

h_dupe = report(OrgIds="5001,5001,5001")
check("a repeated OrgId is deduped, so the TOTAL is not multiplied",
      row_cells(h_dupe, "TOTAL")[4] == "44", row_cells(h_dupe, "TOTAL"))
check("an OrgId outside the chosen division is ignored",
      row_cells(report(OrgIds="5001,999999"), "TOTAL")[4] == "44")

check("a range with no meetings in it explains itself and offers a way back",
      "No meetings in that date range" in
      report(OrgIds="5001", StartDate="2020-01-01", EndDate="2020-01-31"))

# A 61-date range: the column cap keeps the most recent MAX_DATE_COLUMNS.
saved_meetings = MEETINGS[5001]
MEETINGS[5001] = ["2026-06-%02d" % d for d in range(1, 31)] + \
                 ["2026-07-%02d" % d for d in range(1, 32)]
h_wide = report(OrgIds="5001", StartDate="2026-06-01", EndDate="2026-07-31")
check("more than 60 meeting dates is capped and reported, not silently cut",
      "Showing the most recent 60" in h_wide and h_wide.count("<th title=") == 61)
check("the cap keeps the MOST RECENT dates", ">7/31</th>" in h_wide and ">6/1</th>" not in h_wide)
MEETINGS[5001] = saved_meetings

# =====================================================================
print("\n=== 6. DEEP LINKS BACK INTO TOUCHPOINT ===")
check("the involvement name links to the involvement",
      '<a href="%s/Org/5001" target="_blank" rel="noopener"' % CMS_HOST in h)
check("a cell links to that meeting's own attendance list",
      '<a href="%s/Meeting/%d"' % (CMS_HOST, meeting_id(5001, D1)) in h,
      re.findall(r'href="[^"]*/Meeting/[^"]*"', h)[:3])
check("every date column links to its OWN meeting, not one shared link",
      len(set(re.findall(r'/Meeting/(\d+)', h))) == 7)  # 3 + 1 + 3 single-meeting cells
check("the red 0 is linked too -- it is the cell most worth opening",
      re.search(r'<td class="ac-zero"><a href="[^"]*/Meeting/%d"' % meeting_id(5003, D3), h)
      is not None)
check("...and its link says why it is worth opening",
      "Meeting held, nobody marked present. Open this meeting" in h)
check("a did-not-meet cell is NOT a link",
      '<td class="ac-none" title="No meeting held">&middot;</td>' in h
      and re.search(r'<td class="ac-none"[^>]*><a', h) is None)
check("a date with several meetings does not pretend to link to one of them",
      re.search(r'<td class="ac-multi"><a href="[^"]*/Org/5002#tab-Meetings-tab"', h) is not None)
check("...and marks itself with the meeting count",
      "10<sup>2</sup>" in h and "2 meetings on this date, summed here" in h)
check("the TOTAL row is not linked (it spans involvements)",
      re.search(r'<tr class="ac-grand">.*?<a ', h, re.S) is None)
table_only = re.search(r"<table id=\"countsTable\">.*?</table>", h, re.S).group(0)
check("every link in the grid opens a new tab, so the built report is not lost",
      table_only.count('target="_blank"') == table_only.count("<a href=")
      and table_only.count('rel="noopener"') == table_only.count("<a href="))
check("the page's own Back link stays in the same tab",
      re.search(r'ac-back ac-no-print"><a href="[^"]+">', h) is not None
      and 'target="_blank"' not in re.search(r'<p class="ac-back.*?</p>', h, re.S).group(0))
check("the notes explain what clicking does",
      "opens that meeting" in h and "Meetings tab instead" in h)
check("links print as plain numbers, not as underlined blue text",
      "#rpcAttendanceCounts td a, #rpcAttendanceCounts td.ac-name a { color: inherit !important;"
      in h, re.findall(r"[^{}]*color: inherit[^{}]*\{[^}]*\}", h)[:2])

check("links are built from model.CmsHost", CMS_HOST + "/Org/5001" in h)
hostless, _ = run(host="", ProgId="1109", DivId="11", OrgIds="5001",
                  StartDate=D1, EndDate=D3)
check("a missing CmsHost degrades to host-relative links, it does not crash",
      '<a href="/Org/5001"' in hostless and "//Org/" not in hostless)
trailing, _ = run(host=CMS_HOST + "/", ProgId="1109", DivId="11", OrgIds="5001",
                  StartDate=D1, EndDate=D3)
check("a CmsHost with a trailing slash does not produce a doubled slash",
      CMS_HOST + "//Org/" not in trailing and CMS_HOST + "/Org/5001" in trailing)

print("\n=== 7. GROUPING THE COLUMNS BY WEEK ===")
h_day = report(OrgIds="5006")
check("by date, the two meetings in one week are two columns",
      row_cells(h_day, "SM: PS Welcome Team") == ["5", "7", "2", "12", "6.0", "12", "0"],
      row_cells(h_day, "SM: PS Welcome Team"))

h_wk = report(OrgIds="5006", GroupDates="week")
check("by week, they collapse into one column that sums them",
      row_cells(h_wk, "SM: PS Welcome Team") == ["122", "1", "12", "12.0", "12", "0"],
      row_cells(h_wk, "SM: PS Welcome Team"))  # "122" = 12 plus its <sup>2</sup>
check("the total is unchanged by regrouping -- only the columns move",
      row_cells(h_day, "SM: PS Welcome Team")[-4] == row_cells(h_wk, "SM: PS Welcome Team")[-4]
      == "12")
check("Avg follows the column unit (6.0 over 2 dates, 12.0 over 1 week)",
      "6.0" in row_cells(h_day, "SM: PS Welcome Team")
      and "12.0" in row_cells(h_wk, "SM: PS Welcome Team"))
check("the roll-up column is relabelled Weeks, not Mtgs",
      ">Weeks</th>" in h_wk and ">Mtgs</th>" not in h_wk and ">Mtgs</th>" in h_day)

check("week columns are labelled by their Sunday and marked as weeks",
      ">Wk 8/23</th>" in h_wk and ">8/24</th>" not in h_wk)
check("a same-month week spells out its span per the style guide (no ordinals)",
      'title="August 23-29"' in h_wk, re.findall(r'<th title="[^"]+"', h_wk)[:4])

h_wk_all = report(OrgIds="5001,5002,5003,5006", GroupDates="week")
check("a cross-month week is spaced per the style guide",
      'title="August 30 \u2013 September 5"' in h_wk_all,
      re.findall(r'<th title="[^"]+"', h_wk_all)[:4])
check("three Mondays in three different weeks stay three columns",
      h_wk_all.count(">Wk ") == 3, re.findall(r">Wk [0-9/]+", h_wk_all))
check("a week cell with several meetings links to the Meetings tab, not one meeting",
      re.search(r'<td class="ac-multi"><a href="[^"]*/Org/5006#tab-Meetings-tab"[^>]*'
                r'title="2 meetings that week', h_wk_all) is not None)
check("a week cell with exactly one meeting still deep-links to that meeting",
      '<a href="%s/Meeting/%d"' % (CMS_HOST, meeting_id(5001, D2)) in h_wk_all)

check("the stat bar counts weeks and averages per week",
      "weeks with meetings" in h_wk and "avg per week" in h_wk
      and "meeting dates" in h_day and "avg per date" in h_day)
check("the peak stat says peak week", "peak week &mdash;" in h_wk_all)
check("the notes explain what a week column is",
      "Sunday&ndash;Saturday, labelled by" in h_wk and "held no meeting that week" in h_wk)
check("the notes say 'that day' when grouped by date", "held no meeting that day" in h_day)

check("the back link carries the grouping choice",
      "GroupDates=week" in re.search(r'ac-back ac-no-print"><a href="([^"]+)"', h_wk).group(1))
check("a bogus GroupDates falls back to date columns, it does not error",
      ">8/24</th>" in report(OrgIds="5006", GroupDates="fortnight"))
check("stage 3 offers the choice",
      'name="GroupDates"' in h3 and "one column per week" in h3)

# The cap is applied AFTER grouping -- that is what makes week mode a real
# answer to a long range rather than a differently-shaped truncation.
saved = MEETINGS[5001]
MEETINGS[5001] = ["2026-06-%02d" % d for d in range(1, 31)] + \
                 ["2026-07-%02d" % d for d in range(1, 32)]
wide_day = report(OrgIds="5001", StartDate="2026-06-01", EndDate="2026-07-31")
wide_wk = report(OrgIds="5001", StartDate="2026-06-01", EndDate="2026-07-31",
                 GroupDates="week")
check("61 daily meetings overflow the 60-column cap by date",
      "Showing the most recent 60" in wide_day)
check("...and the warning suggests grouping by week", "group the columns by week" in wide_day)
check("...but fit in 9 week columns with nothing truncated",
      "Showing the most recent" not in wide_wk and wide_wk.count(">Wk ") == 9,
      re.findall(r">Wk [0-9/]+", wide_wk))
# The roll-up column is [-5]: Mtgs/Weeks, Total, Avg, Members, Leaders.
check("by date the cap drops a meeting date (60 of 61 kept)",
      row_cells(wide_day, "SM: CC 6th Guys")[-5] == "60",
      row_cells(wide_day, "SM: CC 6th Guys")[-6:])
check("by week every one of those 61 dates is still represented, in 9 columns",
      row_cells(wide_wk, "SM: CC 6th Guys")[-5] == "9",
      row_cells(wide_wk, "SM: CC 6th Guys")[-6:])
MEETINGS[5001] = saved

print("\n=== 8. CSV EXPORT ===")
csv = re.search(r"var csv = '(.*?)';", h, re.S)
check("the report embeds a CSV built server-side, not scraped from the DOM",
      csv is not None)
if csv:
    lines = csv.group(1).split("\\n")
    check("the CSV header carries ISO dates and the summary columns",
          lines[0] == "Involvement,2026-08-24,2026-08-31,2026-09-07,Meetings,Total,Avg,Members,Leaders,Other",
          lines[0])
    check("a CSV row matches its rendered row",
          "SM: CC 6th Guys,13,16,15,3,44,14.7,37,6,1" in csv.group(1))
    check("a did-not-meet cell exports as blank, not as a 0",
          "SM: CC 6th Girls,11,,10,2,21,10.5,19,2,0" in csv.group(1))
    check("the CSV includes the TOTAL row", "TOTAL,43,32,25,3,100,33.3,85,14,1" in csv.group(1))
csv_comma = re.search(r"var csv = '(.*?)';", report(OrgIds="5001,5005"), re.S)
check("an involvement name containing a comma is quoted in the CSV",
      csv_comma is not None and '"SM: PS Guys, Grades 7-8",7,' in csv_comma.group(1),
      csv_comma.group(1)[:200] if csv_comma else None)
check("the CSV carries no HTML and no URLs -- it is built from the raw values",
      csv is not None
      and not re.search(r'<a |href=|</a>|<sup>|/Meeting/|/Org/|target=|' + re.escape(CMS_HOST),
                        csv.group(1)),
      re.findall(r'<[^>]+>|https?://\S+', csv.group(1))[:5] if csv else None)
check("a multi-meeting cell exports as its number alone, without the superscript",
      csv is not None and "SM: CC 6th Girls,11,,10,2,21,10.5,19,2,0" in csv.group(1))
csv_wk = re.search(r"var csv = '(.*?)';", report(OrgIds="5006", GroupDates="week"), re.S)
check("the CSV heads week columns with an ISO week-start date",
      csv_wk is not None
      and csv_wk.group(1).split("\\n")[0] == "Involvement,Week of 2026-08-23,Weeks,Total,Avg,Members,Leaders",
      csv_wk.group(1).split("\\n")[0] if csv_wk else None)
check("a collapsed week exports as its plain summed number",
      csv_wk is not None and "SM: PS Welcome Team,12,1,12,12.0,12,0" in csv_wk.group(1))
check("the CSV filename carries the date range",
      "attendance-counts-2026-08-24-2026-09-07.csv" in h)

# =====================================================================
print("\n=== 9. EMBEDDING IN TOUCHPOINT'S PAGE ===")
# Same lesson RPC_AttendanceRoster.py learned live on 2026-09-07: this HTML
# is injected into a TouchPoint page carrying its own Bootstrap-derived
# stylesheet, where a host `.church { display:none }` blanked the header's
# eyebrow. Every class is prefixed AND every rule is scoped under a wrapper
# id -- prefixing stops the collisions, scoping protects the bare element
# selectors (table/th/td/button/select) that cannot be prefixed.
for label, page in (("stage 1", h1), ("stage 2", h2), ("stage 3", h3), ("report", h)):
    check("%s wraps its content in the scoping element" % label,
          'id="rpcAttendanceCounts"' in page)
    check("%s scopes every CSS rule under that id" % label, "#rpcAttendanceCounts" in page)
    check("%s styles the wrapper, never TouchPoint's own <body>" % label,
          not re.search(r"(?m)^\s*body\s*\{", page))
    check("%s uses only ac- prefixed class names" % label,
          not re.search(r'class="(?!ac-)', page))
check("@page survives scoping unprefixed (it takes no selector)",
      "@page { size: landscape" in h)
check("the report's interactive chrome is print-suppressed",
      "ac-no-print" in h and ".ac-no-print { display: none !important; }" in h)

# =====================================================================
print("\n=== 10. ROW-LEVEL SECURITY ===")
_, qadmin = run(user_id=47110)
check("an admin's ministry query carries no RLS filter",
      "om_rls" not in [s for s in qadmin.seen if "FROM dbo.Program p" in s][0])
_, quser = run(user_id=99999)
prog_sql = [s for s in quser.seen if "FROM dbo.Program p" in s][0]
check("a non-admin's ministry query is filtered to their own memberships",
      "om_rls.PeopleId = 99999" in prog_sql)
_, qdiv = run(user_id=99999, ProgId="1109")
check("...and so is their division query",
      "om_rls.PeopleId = 99999" in [s for s in qdiv.seen if "FROM dbo.Division d" in s][0])
check("stage 3's involvement list is not RLS-filtered (matches the roster report)",
      "om_rls" not in [s for s in run(user_id=99999, ProgId="1109", DivId="11")[1].seen
                       if "FROM dbo.Organizations o" in s][0])

# =====================================================================
print("\n=== 11. THE KNOWN SCHEMA TRAPS (DB_REFERENCE.md) ===")
_, qtrap = run(ProgId="1109", DivId="11", OrgIds="5001", StartDate=D1, EndDate=D3)
org_sql = [s for s in qtrap.seen if "FROM dbo.Organizations o" in s][0]
check("DivOrg is reached through EXISTS, never a JOIN that fans rows out",
      "EXISTS ( SELECT 1 FROM dbo.DivOrg" in org_sql and "JOIN dbo.DivOrg" not in org_sql)
mtg_sql = [s for s in qtrap.seen if "FROM dbo.Meetings m WHERE" in s][0]
check("canceled and did-not-meet meetings are excluded from the grid",
      "ISNULL(m.Canceled, 0) = 0" in mtg_sql and "ISNULL(m.DidNotMeet, 0) = 0" in mtg_sql)
check("MeetingDate is compared as a DATE, never as a datetime",
      "CAST(m.MeetingDate AS DATE)" in mtg_sql)
att_sql = [s for s in qtrap.seen if "FROM dbo.Attend a" in s][0]
check("attendance requires AttendanceFlag = 1 and excludes NoShow",
      "a.AttendanceFlag = 1" in att_sql and "ISNULL(a.NoShow, 0) = 0" in att_sql)
check("counts group by date, so an org's several meetings on one day all sum",
      "GROUP BY a.OrganizationId, CAST(a.MeetingDate AS DATE)" in att_sql)
check("the report says it counts visits rather than distinct people",
      "visits" in h and "counts twice" in h)
check("it says out loud that it is not NumPresent", "NumPresent" in h)

print("\n" + "=" * 62)
print("FAILURES: %d" % len(fails))
for f in fails:
    print("  - " + f)
sys.exit(1 if fails else 0)
