"""
WidgetTodaysCoveragePython.py

TouchPoint Special Content (Python Script). Read-only. Named per RPC's
existing Special Content "Widget" naming convention (WidgetXxxPython,
PascalCase, no underscores -- see the other WidgetXxxPython scripts
already deployed in TouchPoint), rather than this repo's usual RPC_ prefix,
since this one is meant to sit alongside those as an actual widget rather
than a standalone report page.

A compact, hardcoded "who's covering today" widget for RockPointe's two
Staff on Campus Scheduler involvements:

    AD: CC Staff on Campus 2026   OrgId 3951
    AD: PS Staff on Campus 2026   OrgId 3726

Companion to `RPC_SchedulerHistoryReport.py` (the full week-grid Coverage
Board) in this same folder -- this widget is the narrow, single-purpose
version of it: no OrgId picker, no date range, no tabs, just "here's both
campuses' MOC coverage for today," meant to be a quick glance rather than a
tool to browse history in. Each org's block links out to the full Board for
that org/day if more detail (a different date, past coverage, "my shifts")
is needed.

TouchPoint Special Content scripts don't share code across files (each is
pasted in as its own standalone script), so the query, the .NET-DateTime
parsing, and the shift-name normalization below are copied from
RPC_SchedulerHistoryReport.py rather than imported -- see that script's
docstring and README for the full background on why each of those exists
(community-sourced Scheduler table set, confirmed live 2026-09-24/27,
including the two naming-inconsistency bugs both hardcoded orgs already
hit). If either org's naming or table structure changes, check both files.

## Usage

Deploy as a TouchPoint Python Script (see Deployment below), then visit:

    /PyScript/WidgetTodaysCoveragePython

No parameters -- it always shows today's date for both hardcoded orgs.

## Deployment

Admin > Advanced > Special Content > Python Scripts > + New
  Name: WidgetTodaysCoveragePython
  Paste this file's contents, Save.

## Known limitation

The two OrgIds are hardcoded (`WIDGET_ORGS` below) per this request --
intentional, not an oversight. If a third Staff on Campus involvement (or
a different campus) is added later, add it to `WIDGET_ORGS` here; this
widget was not built to discover Scheduler orgs automatically the way the
full report's dropdown does.
"""

import re
from collections import Counter
from datetime import datetime, timedelta

# Name, OrgId -- confirmed live 2026-09-24 via sql_reference.sql query 2.
WIDGET_ORGS = [
    ("AD: CC Staff on Campus 2026", 3951),
    ("AD: PS Staff on Campus 2026", 3726),
]

# ============================================================
# RPC brand styling (main RockPointe Church palette)
# ============================================================
NAVY = "#0C2340"
YELLOW = "#FFD242"
LIGHT_GRAY = "#D1D3D4"
GAP_RED = "#C0392B"
GAP_RED_BG = "#FBEAE8"

TITLE_FONT = '"Bebas Neue", Impact, "Arial Narrow", Haettenschweiler, sans-serif'
SUBTITLE_FONT = 'Montserrat, "Segoe UI", Tahoma, sans-serif'
BODY_FONT = '-apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif'

ROOT_ID = "rpcTodaysCoverage"

CSS = """
  *, *::before, *::after { box-sizing: border-box; }
  body { font-family: %(body)s; margin: 20px; color: #222; background: #fff; }
  h1 { font-family: %(title)s; font-size: 26px; font-weight: normal; text-transform: uppercase;
       letter-spacing: 0.02em; color: %(navy)s; margin: 0 0 4px;
       border-bottom: 3px solid %(yellow)s; padding-bottom: 6px; }
  .tc-meta { color: #55606b; font-size: 13px; margin: 8px 0 20px; }
  .tc-orgs { display: flex; flex-wrap: wrap; gap: 18px; }
  .tc-org { flex: 1 1 320px; min-width: 280px; border: 1px solid %(gray)s; border-radius: 6px;
          overflow: hidden; }
  .tc-org h2 { font-family: %(subtitle)s; font-size: 14px; font-weight: 700; color: #fff;
          background: %(navy)s; margin: 0; padding: 10px 14px; text-transform: uppercase;
          letter-spacing: 0.03em; }
  .tc-org h2 a { color: #fff; text-decoration: none; border-bottom: 1px dotted rgba(255,255,255,0.5); }
  .tc-shift { display: flex; justify-content: space-between; align-items: center;
          padding: 12px 14px; border-top: 1px solid #edf0f3; font-size: 14px; }
  .tc-org .tc-shift:first-of-type { border-top: none; }
  .tc-shift-label { color: %(navy)s; font-weight: 600; }
  .tc-shift-name { color: #222; }
  .tc-shift.tc-gap { background: %(gapbg)s; }
  .tc-shift.tc-gap .tc-shift-name { color: %(gap)s; font-weight: 700; text-transform: uppercase;
          font-size: 12px; letter-spacing: 0.04em; }
  .tc-empty { padding: 14px; color: #6b7683; font-style: italic; font-size: 13px; }
  .tc-legend { margin-top: 14px; font-size: 12px; color: #55606b; }
  .tc-legend .tc-swatch { display: inline-block; width: 11px; height: 11px; border-radius: 2px;
          margin-right: 5px; vertical-align: middle; position: relative; top: -1px; }
""" % {
    "body": BODY_FONT, "title": TITLE_FONT, "subtitle": SUBTITLE_FONT,
    "navy": NAVY, "yellow": YELLOW, "gray": LIGHT_GRAY,
    "gap": GAP_RED, "gapbg": GAP_RED_BG,
}


def scope_css(css, root="#" + ROOT_ID):
    """Prefix every selector in `css` with `root`; retarget `body` to it."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def block_end(text, start):
        depth = 0
        for k in range(start, len(text)):
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
                if depth == 0:
                    return k
        return len(text) - 1

    out, i = [], 0
    while i < len(css):
        brace = css.find("{", i)
        if brace == -1:
            out.append(css[i:])
            break
        selector = css[i:brace].strip()
        end = block_end(css, brace)
        if selector.startswith("@"):
            out.append("\n" + css[i:end + 1].strip())
        else:
            parts = []
            for sel in selector.split(","):
                sel = sel.strip()
                if not sel:
                    continue
                parts.append(root if sel == "body" else root + " " + sel)
            out.append("\n%s {%s}" % (", ".join(parts), css[brace + 1:end]))
        i = end + 1
    return "".join(out)


# Copied verbatim from RPC_SchedulerHistoryReport.py -- see that file for
# the full "why" (community-sourced Scheduler table set).
SCHEDULE_SQL = """
;WITH
LatestVolunteers AS (
    SELECT
        TimeSlotMeetingId,
        PeopleId,
        MAX(TimeSlotMeetingVolunteerId) AS TimeSlotMeetingVolunteerId
    FROM TimeSlotMeetingVolunteers
    GROUP BY TimeSlotMeetingId, PeopleId
)
SELECT
    tsm.MeetingDateTime AS ShiftStart,
    CASE WHEN mt.Name IS NULL THEN tsmt.TeamName ELSE mt.Name END AS TeamOrSlot,
    p.PeopleId AS PeopleId,
    p.Name AS PersonName,
    tsmv.VolunteerOption AS VolunteerOption
FROM TimeSlotMeetingTeams tsmt
JOIN TimeSlotMeetings tsm ON tsm.TimeSlotMeetingId = tsmt.TimeSlotMeetingId
JOIN Meetings m ON m.MeetingId = tsm.MeetingId
LEFT JOIN TimeSlotMeetingTeamSubGroups tssg
    ON tssg.TimeSlotMeetingTeamId = tsmt.TimeSlotMeetingTeamId
   AND (tssg.IsDeleted = 'False' OR tssg.IsDeleted IS NULL)
LEFT JOIN TimeSlotMeetingTeamSubGroupVolunteers tsGrpVol
    ON (tsGrpVol.IsActive <> 0
        AND tsGrpVol.TimeSlotMeetingTeamId = tsmt.TimeSlotMeetingTeamId
        AND tsGrpVol.TimeSlotMeetingTeamSubGroupId IS NULL)
    OR (tsGrpVol.IsActive <> 0
        AND tsGrpVol.TimeSlotMeetingTeamSubGroupId = tssg.TimeSlotMeetingTeamSubGroupId
        AND tsGrpVol.TimeSlotMeetingTeamSubGroupId IS NOT NULL)
LEFT JOIN LatestVolunteers lv
    ON lv.TimeSlotMeetingId = tsmt.TimeSlotMeetingId
   AND lv.PeopleId = tsGrpVol.PeopleId
LEFT JOIN TimeSlotMeetingVolunteers tsmv
    ON tsmv.TimeSlotMeetingVolunteerId = lv.TimeSlotMeetingVolunteerId
LEFT JOIN MemberTags mt ON mt.Id = tssg.MemberTagId AND mt.OrgId = @OrgId
LEFT JOIN People p ON p.PeopleId = tsGrpVol.PeopleId
WHERE m.OrganizationId = @OrgId
  AND tsm.MeetingDateTime >= @StartDate
  AND tsm.MeetingDateTime < @EndDateExclusive
ORDER BY tsm.MeetingDateTime, TeamOrSlot, p.Name
"""


def to_python_datetime(value):
    """See RPC_SchedulerHistoryReport.py's to_python_datetime() docstring --
    q.QuerySql hands back DateTime columns as .NET DateTime objects (no
    .strftime), confirmed live 2026-09-24."""
    if hasattr(value, "strftime"):
        return value
    text = str(value).strip()
    text = re.sub(r"\.\d+$", "", text)
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M %p",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("Unrecognized TouchPoint datetime value: {0!r}".format(value))


def normalize_team_label(name):
    """See RPC_SchedulerHistoryReport.py -- tidies whitespace/dash-spacing."""
    name = (name or "(unnamed)").strip()
    name = re.sub(r"\s*-\s*", "-", name)
    name = re.sub(r"\s+", " ", name)
    return name


def canonical_team_key(name):
    """See RPC_SchedulerHistoryReport.py -- case-and-whitespace-blind
    grouping key, confirmed necessary live on both hardcoded orgs here
    (PS: whitespace variants, CC: case variants of the same shift name)."""
    return normalize_team_label(name).lower()


def format_shift_time(dt):
    if not hasattr(dt, "strftime"):
        return str(dt)
    return dt.strftime("%I:%M %p").lstrip("0")


def fetch_today_shifts(org_id, today_str, tomorrow_str):
    rows = q.QuerySql(
        SCHEDULE_SQL,
        {"OrgId": org_id, "StartDate": today_str, "EndDateExclusive": tomorrow_str},
    )
    shifts = {}  # canonical_key -> {"names": [...], "first_start": dt, "label_votes": Counter}
    for row in rows:
        start = to_python_datetime(row.ShiftStart)
        key = canonical_team_key(row.TeamOrSlot)
        entry = shifts.setdefault(
            key, {"names": [], "first_start": start, "label_votes": Counter()}
        )
        entry["label_votes"][normalize_team_label(row.TeamOrSlot)] += 1
        entry["first_start"] = min(entry["first_start"], start)
        if row.PeopleId:
            display = row.PersonName
            if row.VolunteerOption and row.VolunteerOption != "This Time Slot":
                display = "{0} ({1})".format(display, row.VolunteerOption)
            entry["names"].append(display)
    return shifts


def render_org_block(org_name, org_id, today_str, tomorrow_str):
    shifts = fetch_today_shifts(org_id, today_str, tomorrow_str)
    board_link = "RPC_SchedulerHistoryReport?OrgId={0}&StartDate={1}&EndDate={1}&View=Board".format(
        org_id, today_str
    )
    print('<div class="tc-org">')
    print('<h2><a href="{0}">{1}</a></h2>'.format(board_link, org_name))
    if not shifts:
        print('<div class="tc-empty">No shifts scheduled today.</div>')
        print("</div>")
        return
    for key in sorted(shifts, key=lambda k: shifts[k]["first_start"]):
        entry = shifts[key]
        label = entry["label_votes"].most_common(1)[0][0]
        time_str = format_shift_time(entry["first_start"])
        if entry["names"]:
            print(
                '<div class="tc-shift"><span class="tc-shift-label">{0} &middot; {1}</span>'
                '<span class="tc-shift-name">{2}</span></div>'.format(
                    time_str, label, "; ".join(entry["names"])
                )
            )
        else:
            print(
                '<div class="tc-shift tc-gap"><span class="tc-shift-label">{0} &middot; {1}</span>'
                '<span class="tc-shift-name">Unfilled</span></div>'.format(time_str, label)
            )
    print("</div>")


def main():
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    model.Header = "Today's Coverage"

    print('<div id="{0}">'.format(ROOT_ID))
    print("<style>{0}</style>".format(scope_css(CSS)))
    print("<h1>Today's Coverage</h1>")
    print('<div class="tc-meta">{0}</div>'.format(today.strftime("%A, %B ") + str(today.day)))

    print('<div class="tc-orgs">')
    for org_name, org_id in WIDGET_ORGS:
        render_org_block(org_name, org_id, today_str, tomorrow_str)
    print("</div>")

    print(
        '<div class="tc-legend">'
        '<span class="tc-swatch" style="background:{0}"></span>Unfilled shift'
        "</div>".format(GAP_RED)
    )
    print("</div>")


main()
