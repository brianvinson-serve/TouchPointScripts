"""
WidgetTodaysCoveragePython.py

TouchPoint Special Content (Python Script). Read-only. Named per RPC's
existing Special Content "Widget" naming convention (WidgetXxxPython,
PascalCase, no underscores -- see the other WidgetXxxPython scripts
already deployed in TouchPoint), rather than this repo's usual RPC_ prefix,
since this one is meant to sit alongside those as an actual widget rather
than a standalone report page.

A compact, hardcoded "who's covering today" widget for RockPointe's MOC /
welcome desk Scheduler involvement:

    MOC + welcome desk sign-ups   OrgId 4176   (since 2026-11-02)

Previously pointed at the two per-campus Staff on Campus orgs
(AD: CC Staff on Campus 2026 = 3951, AD: PS Staff on Campus 2026 = 3726),
which Dawn retired in favor of 4176 starting November 2026.

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

The OrgIds are hardcoded (`WIDGET_ORG_IDS` below) per this request --
intentional, not an oversight. If another Scheduler involvement is added
later, add it to `WIDGET_ORG_IDS` here; this
widget was not built to discover Scheduler orgs automatically the way the
full report's dropdown does.
"""

import re
from collections import Counter
from datetime import datetime, timedelta

# OrgIds shown, in order. Display name is read live via
# model.GetOrganization() so it tracks renames.
# 2026-11-02: swapped from the two per-campus orgs (CC 3951, PS 3726) to
# Dawn's new combined MOC + welcome desk sign-up involvement, per her note
# that November sign-ups now live there.
WIDGET_ORG_IDS = [4176]

# Copied from RPC_SchedulerHistoryReport.py -- see CAMPUSES there for why.
# Each campus gets its own box; order here is display order.
CAMPUSES = [
    ("Central", ("central", "cc")),
    ("Parker Square", ("parker square", "ps")),
]
OTHER_CAMPUS = "Other"

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
  .tc-orgname { font-family: %(subtitle)s; font-size: 12px; font-weight: 700; color: %(navy)s;
          text-transform: uppercase; letter-spacing: 0.03em; margin: 0 0 8px; }
  .tc-orgname a { color: %(navy)s; text-decoration: none; border-bottom: 1px dotted %(navy)s; }
  .tc-orgs { margin-bottom: 18px; display: flex; flex-wrap: wrap; gap: 18px; }
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
    """See RPC_SchedulerHistoryReport.py -- grouping key blind to case,
    whitespace, dash-vs-space, and "9am" vs "9a"."""
    key = normalize_team_label(name).lower().replace("-", " ")
    key = re.sub(r"(\d)\s*([ap])m\b", r"\1\2", key)
    return re.sub(r"\s+", " ", key).strip()


def campus_of(name):
    """See RPC_SchedulerHistoryReport.py -- (sort index, campus name) from
    the team name's prefix."""
    label = canonical_team_key(name)
    for idx, (campus, prefixes) in enumerate(CAMPUSES):
        for prefix in prefixes:
            if label == prefix or label.startswith(prefix + " ") or label.startswith(prefix + "-"):
                return idx, campus
    return len(CAMPUSES), OTHER_CAMPUS


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
    # Absolute path: the widget renders on pages outside /PyScript/ (e.g. the
    # home page), where a relative link resolved to /RPC_... and 404'd.
    board_link = "/PyScript/RPC_SchedulerHistoryReport?OrgId={0}&StartDate={1}&EndDate={1}&View=Board".format(
        org_id, today_str
    )
    print('<div class="tc-orgname"><a href="{0}">{1}</a></div>'.format(board_link, org_name))
    print('<div class="tc-orgs">')
    if not shifts:
        print('<div class="tc-org"><div class="tc-empty">No shifts scheduled today.</div></div>')
        print("</div>")
        return

    # One box per campus. Explicit (time, label) sort inside each box --
    # IronPython 2.7's dict order is arbitrary, so sorting on time alone
    # left same-time shifts in a random order.
    for key in shifts:
        shifts[key]["label"] = shifts[key]["label_votes"].most_common(1)[0][0]
    by_campus = {}
    for key, entry in shifts.items():
        by_campus.setdefault(campus_of(entry["label"]), []).append(entry)

    for campus_idx, campus in sorted(by_campus):
        print('<div class="tc-org">')
        print("<h2>{0}</h2>".format(campus))
        for entry in sorted(by_campus[(campus_idx, campus)],
                            key=lambda e: (e["first_start"], e["label"])):
            time_str = format_shift_time(entry["first_start"])
            if entry["names"]:
                print(
                    '<div class="tc-shift"><span class="tc-shift-label">{0} &middot; {1}</span>'
                    '<span class="tc-shift-name">{2}</span></div>'.format(
                        time_str, entry["label"], "; ".join(entry["names"])
                    )
                )
            else:
                print(
                    '<div class="tc-shift tc-gap"><span class="tc-shift-label">{0} &middot; {1}</span>'
                    '<span class="tc-shift-name">Unfilled</span></div>'.format(time_str, entry["label"])
                )
        print("</div>")
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

    for org_id in WIDGET_ORG_IDS:
        org = model.GetOrganization(org_id)
        org_name = org.name if org else "Involvement {0}".format(org_id)
        render_org_block(org_name, org_id, today_str, tomorrow_str)

    print(
        '<div class="tc-legend">'
        '<span class="tc-swatch" style="background:{0}"></span>Unfilled shift'
        "</div>".format(GAP_RED)
    )
    print("</div>")


main()
