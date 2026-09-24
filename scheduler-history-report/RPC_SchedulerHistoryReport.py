"""
RPC_SchedulerHistoryReport.py

TouchPoint Special Content (Python Script). Read-only.

Answers Marlene's ask: TouchPoint's built-in Scheduler tab (the shift
sign-up grid inside a Scheduler-type Involvement, e.g. "AD: PS Staff on
Campus 2026") only shows names for shifts that have NOT yet passed, and
even for upcoming shifts it's a flat grid of small identical cards with no
visual hierarchy -- a gap (nobody signed up) looks exactly like a normal
day at a glance. TouchPoint support told her this needs a custom script --
this is that script.

## Design: "The Board" + "Mine"

Two views of the same underlying data, chosen with `?View=`:

- `Board` (default) -- a week grid, days as columns, shift slots as rows.
  A gap (a scheduled shift with nobody signed up) renders as a solid loud
  block, not a quiet blank cell -- absence is drawn, not implied, which is
  the actual fix for Marlene's coordinator job ("is everything covered,
  and who do I need to chase down"). Filled shifts are deliberately quiet:
  name only, no icon, no color -- so the one thing announcing itself on the
  page is the thing that needs attention.
- `Mine` -- a chronological list (not a grid) of one person's shifts, past
  and upcoming, for Debbie's job ("what am I signed up for, did I cover
  it"). Filtered from the same query and date range by a name search
  (`?View=Mine&PersonName=Debbie`), since staff don't carry PeopleIds
  around in their heads.

Two other concepts were sketched and deliberately NOT built here: a
phone-native "ticket stub" personal view, and an unattended shared-screen
"who's on now" kiosk view. Neither solves a problem anyone has actually
raised yet (Marlene's ask was specifically about seeing past coverage);
they're documented in this folder's README as candidates if requested.

## Why the built-in view hides past shifts (and why this script can show them)

TouchPoint support's answer implies the sign-up data itself isn't kept
anywhere queryable -- it is. The Scheduler feature is backed by its own
table set (TimeSlots / TimeSlotMeetings / TimeSlotMeetingTeams /
TimeSlotTeamSubGroups / TimeSlotMeetingTeamSubGroups /
TimeSlotMeetingTeamSubGroupVolunteers / TimeSlotMeetingVolunteers), separate
from Meetings/Attend. Sign-up rows are not deleted or archived once a
shift's date passes -- the built-in Scheduler tab (and every community
report modeled on it) simply adds a `WHERE ShiftDateTime > GETDATE()`
filter. Drop that filter and the same historical rows are right there.

Table names and the join shape below are adapted from Ben Swaby's (TPxi
Software) TPxi_SchedulerReport.py in the community repo
https://github.com/bswaby/Touchpoint (TPxi/Scheduler Report) -- credited
per this repo's own guidance to prefer adapting an existing community tool
over a from-scratch build. That script is a forward-looking, per-org
"who's signed up this year" email report with fill-percentage tracking,
family sign-up buttons, and Morning Batch delivery; none of that is needed
here. This script keeps only the join shape needed to answer "who was
assigned to which shift, in a given date range including the past."

## NOT YET RPC-CONFIRMED

The TimeSlot* table names/columns above come from the community script's
working query against a *different* TouchPoint instance, not from a live
RPC schema export -- none of RPC's own schema-discovery exports (see
DB_REFERENCE.md) captured this table set before now, because no report in
this repo had queried it. Every RPC-specific fact stated as confirmed
elsewhere in this repo does NOT apply here yet. Before trusting this
report's output:
  1. Deploy it (see below) against a Scheduler involvement RPC actually
     uses -- e.g. "AD: PS Staff on Campus 2026" from Marlene's screenshot.
  2. Compare its Board output for a date/time that still shows in the live
     Scheduler tab (a future shift) against what the tab currently shows.
  3. Then check a date that has already passed (e.g. today's earlier
     9am-noon MOC shift) and confirm the person shown matches who actually
     covered it.
If step 2 doesn't match, the join shape needs adjusting before step 3's
past-date output can be trusted. Once confirmed, add a short note back to
DB_REFERENCE.md under a new "Scheduler (shift sign-up)" section with the
confirmed table names/columns and this OrgId as a worked example.

## Usage

Deploy as a TouchPoint Python Script (see Deployment below), then visit:

    /PyScript/RPC_SchedulerHistoryReport?OrgId=1234

`OrgId` is the Scheduler involvement's OrganizationId (visible in that
involvement's admin URL -- the same OrganizationId used throughout this
repo's other reports). Optional `StartDate`/`EndDate` (YYYY-MM-DD) override
the default window, which is the current calendar week (Sunday-Saturday,
matching this repo's existing SchedDay=0-is-Sunday convention). The
"Coverage board" / "My shifts" tabs at the top switch `View` without
losing the OrgId or date range.

## Deployment

Admin > Advanced > Special Content > Python Scripts > + New
  Name: RPC_SchedulerHistoryReport
  Paste this file's contents, Save.
Then share the link above (with the correct OrgId) with Marlene, or add a
CustomReports entry for Blue Toolbar access if she'll use it often enough
to want a menu link (see other reports' READMEs in this repo for that XML
pattern) -- not done here since only one Scheduler involvement was named
in the request.
"""

import re
from collections import Counter
from datetime import date, datetime, timedelta

# ============================================================
# RPC brand styling (main RockPointe Church palette -- default per Comms
# Director Jessica Siri; this is a staff-wide admin tool, not ministry-
# branded, so no ministry sheet applies)
# ============================================================
NAVY = "#0C2340"
YELLOW = "#FFD242"
SPACE_BLUE = "#183D5F"
CURIOUS_BLUE = "#1D6A94"
LIGHT_GRAY = "#D1D3D4"
# Not a brand color -- reserved solely for an unfilled shift. A gap needs
# to be the loudest thing on the page (that's the whole point of this
# redesign), and none of RPC's own palette is alarm-toned enough to do
# that job without being mistaken for a normal accent.
GAP_RED = "#C0392B"
GAP_RED_BG = "#FBEAE8"

TITLE_FONT = '"Bebas Neue", Impact, "Arial Narrow", Haettenschweiler, sans-serif'
SUBTITLE_FONT = 'Montserrat, "Segoe UI", Tahoma, sans-serif'
BODY_FONT = '-apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif'

# Scoped the same way as RPC_AttendanceRoster: this page renders inside
# TouchPoint's own Bootstrap-derived layout, so generic class names are a
# collision risk. Every rule here is prefixed with this wrapper id.
ROOT_ID = "rpcSchedulerHistory"

CSS = """
  *, *::before, *::after { box-sizing: border-box; }
  body { font-family: %(body)s; margin: 20px; color: #222; background: #fff; }
  .sh-church { font-family: %(subtitle)s; font-size: 10px; letter-spacing: 0.14em;
            text-transform: uppercase; color: %(curious)s; margin: 0 0 2px; font-weight: 600; }
  h1 { font-family: %(title)s; font-size: 26px; font-weight: normal; text-transform: uppercase;
       letter-spacing: 0.02em; color: %(navy)s; margin: 0 0 4px;
       border-bottom: 3px solid %(yellow)s; padding-bottom: 6px; }
  .sh-meta { color: #55606b; font-size: 13px; margin: 8px 0 18px; line-height: 1.5; }

  .sh-tabs { display: flex; gap: 2px; margin: 0 0 18px; border-bottom: 2px solid %(gray)s; }
  .sh-tabs a { display: inline-block; padding: 9px 18px; font-family: %(subtitle)s;
          font-size: 13px; font-weight: 700; letter-spacing: 0.03em; text-decoration: none;
          color: #6b7683; background: #f2f4f6; border: 1px solid %(gray)s; border-bottom: none;
          border-radius: 5px 5px 0 0; position: relative; top: 2px; }
  .sh-tabs a.sh-tab-on { color: %(navy)s; background: #fff; border-bottom: 2px solid #fff; }

  .sh-form { background: #f7f9fb; border: 1px solid #e3e8ee; border-radius: 6px;
          padding: 16px 18px; margin: 0 0 18px; }
  .sh-form label { display: block; font-size: 12px; font-weight: 600; color: #3d4753;
          text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
  .sh-form .sh-row { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
  .sh-form .sh-field { min-width: 150px; }
  .sh-form .sh-field-wide { min-width: 260px; flex: 1 1 260px; }
  .sh-form input, .sh-form select { font-family: %(body)s; font-size: 14px; padding: 7px 8px;
          border: 1px solid %(gray)s; border-radius: 4px; width: 100%%; background: #fff; }
  .sh-form button { font-family: %(subtitle)s; font-size: 13px; font-weight: 700;
          letter-spacing: 0.04em; padding: 9px 22px; color: #fff; background: %(navy)s;
          border: 0; border-radius: 4px; cursor: pointer; text-transform: uppercase; }
  .sh-form button:hover { background: %(space)s; }
  .sh-error { background: #fdecea; border-left: 4px solid #d9534f; color: #7a2b25;
          padding: 10px 14px; border-radius: 4px; margin: 0 0 18px; font-size: 13px; }
  h2 { font-family: %(subtitle)s; font-size: 15px; font-weight: 700; color: %(navy)s;
       margin: 4px 0 0; text-transform: uppercase; letter-spacing: 0.05em; }
  .sh-nav { font-size: 13px; margin: 4px 0 20px; }
  .sh-nav a { color: %(curious)s; text-decoration: none; margin-right: 16px; }
  .sh-nav a:hover { text-decoration: underline; }
  .sh-empty { color: #6b7683; font-style: italic; margin: 14px 0; }

  /* ---- Board (coverage grid) ---- */
  .sh-boardwrap { overflow-x: auto; margin-top: 10px; }
  table.sh-board { border-collapse: collapse; width: 100%%; min-width: 640px; table-layout: fixed; }
  table.sh-board th, table.sh-board td { border: 1px solid %(gray)s; padding: 0; vertical-align: top; }
  table.sh-board th.sh-rowhead { width: 150px; text-align: left; padding: 8px 10px;
          background: #eef2f6; color: %(navy)s; font-family: %(subtitle)s;
          font-size: 12px; font-weight: 700; }
  table.sh-board th.sh-colhead { text-align: center; padding: 8px 4px; background: %(navy)s;
          color: #fff; font-family: %(subtitle)s; font-size: 12px; }
  table.sh-board th.sh-colhead .sh-daynum { font-family: %(title)s; font-size: 18px;
          letter-spacing: 0.02em; display: block; }
  table.sh-board th.sh-colhead.sh-today { background: %(space)s; box-shadow: inset 0 -3px 0 %(yellow)s; }
  table.sh-board td.sh-cell { padding: 10px 8px; font-size: 13px; text-align: center; }
  table.sh-board td.sh-na { background: #fafbfc; color: %(gray)s; }
  table.sh-board td.sh-filled { background: #fff; color: #222; }
  table.sh-board td.sh-filled .sh-past-tag { display: block; font-size: 10px; color: #9aa4ad;
          text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
  table.sh-board td.sh-gap { background: %(gapbg)s; color: %(gap)s; font-weight: 700; }
  table.sh-board td.sh-gap .sh-gap-label { display: block; font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
  .sh-legend { margin-top: 12px; font-size: 12px; color: #55606b; }
  .sh-legend .sh-swatch { display: inline-block; width: 11px; height: 11px; border-radius: 2px;
          margin-right: 5px; vertical-align: middle; position: relative; top: -1px; }

  /* ---- Mine (personal list) ---- */
  .sh-searchresult { font-size: 13px; color: #55606b; margin: 0 0 14px; }
  ul.sh-mine { list-style: none; margin: 0; padding: 0; max-width: 520px; }
  ul.sh-mine li { display: flex; justify-content: space-between; align-items: baseline;
          padding: 11px 4px; border-bottom: 1px solid #edf0f3; }
  ul.sh-mine li.sh-mine-past { opacity: 0.55; }
  ul.sh-mine .sh-mine-when { font-weight: 600; color: %(navy)s; }
  ul.sh-mine .sh-mine-team { color: #55606b; font-size: 13px; }
  ul.sh-mine li.sh-mine-past .sh-mine-when { color: #55606b; font-weight: normal; }
  .sh-matchlist { list-style: none; margin: 0; padding: 0; }
  .sh-matchlist li { padding: 6px 0; }
""" % {
    "body": BODY_FONT, "title": TITLE_FONT, "subtitle": SUBTITLE_FONT,
    "navy": NAVY, "yellow": YELLOW, "space": SPACE_BLUE, "curious": CURIOUS_BLUE,
    "gray": LIGHT_GRAY, "gap": GAP_RED, "gapbg": GAP_RED_BG,
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


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def valid_date(value):
    value = str(value or "").strip()
    return value if DATE_RE.match(value) else None


def week_bounds(today):
    # Sunday-Saturday, matching this repo's existing SchedDay=0-is-Sunday
    # convention (DB_REFERENCE.md) rather than an ISO Monday-start week.
    start = today - timedelta(days=(today.weekday() + 1) % 7)
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def shift_neighbor(start_str, end_str, direction):
    """Shift the current window by one window-length in `direction` (+1/-1)."""
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    span = (end - start).days + 1
    new_start = start + timedelta(days=direction * span)
    new_end = end + timedelta(days=direction * span)
    return new_start.strftime("%Y-%m-%d"), new_end.strftime("%Y-%m-%d")


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

# Powers the OrgId dropdown: any active involvement that has at least one
# TimeSlotMeeting is, by definition, a real Scheduler involvement (this is
# the same live signal used to confirm 3726/3951 -- OrganizationTypeId 207
# alone isn't distinctive enough, since it's shared with plain volunteer-
# tracking orgs that were never built as a Scheduler). OrganizationStatusId
# 30 = Active, confirmed in DB_REFERENCE.md.
SCHEDULER_ORGS_SQL = """
SELECT DISTINCT o.OrganizationId, o.OrganizationName
FROM Organizations o
JOIN Meetings m ON m.OrganizationId = o.OrganizationId
JOIN TimeSlotMeetings tsm ON tsm.MeetingId = m.MeetingId
WHERE o.OrganizationStatusId = 30
ORDER BY o.OrganizationName
"""


def fetch_scheduler_orgs():
    try:
        return list(q.QuerySql(SCHEDULER_ORGS_SQL))
    except Exception:
        return []


def format_shift_time(dt):
    # Avoid %-I/%#I (non-portable strftime flags) -- same convention as
    # RPC_AttendanceCounts.py elsewhere in this repo.
    if not hasattr(dt, "strftime"):
        return str(dt)
    return dt.strftime("%I:%M %p").lstrip("0")


def format_shift_date(dt):
    return dt.strftime("%a, %B ") + str(dt.day) + dt.strftime(", %Y")


def normalize_team_label(name):
    """Tidy whitespace/dash-spacing in a shift's team name for display --
    confirmed live 2026-09-27 on "AD: PS Staff on Campus 2026", where the
    same 9am-noon shift alternates between "PS MOC 9a - noon" and
    "PS MOC 9a-noon" week to week."""
    name = (name or "(unnamed)").strip()
    name = re.sub(r"\s*-\s*", "-", name)
    name = re.sub(r"\s+", " ", name)
    return name


def canonical_team_key(name):
    """Case-insensitive key used to GROUP a shift's rows on the board.

    normalize_team_label() alone isn't enough: confirmed live 2026-09-27 on
    "AD: CC Staff on Campus 2026", the same noon-3pm shift alternates
    between "CC MOC noon-3p" and "CC MOC noon-3P" (capitalization, not
    whitespace) week to week. Without folding case here too, that split one
    real shift into two board rows and showed a false GAP/NOT COVERED on
    whichever variant didn't match that week -- exactly the kind of false
    negative the board's whole design depends on NOT showing. Display text
    still comes from normalize_team_label() (via the most-common raw
    spelling, see render_board) so a display label is never invented --
    only which rows count as "the same shift" is case-blind."""
    return normalize_team_label(name).lower()


def escape_html(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_org_field(org_id, org_list):
    if not org_list:
        # Live query came back empty (or errored) -- fall back to the
        # original plain text entry rather than showing a useless dropdown.
        return '''
    <div class="sh-field">
      <label for="OrgId">Involvement (OrganizationId)</label>
      <input type="text" id="OrgId" name="OrgId" value="{0}" placeholder="e.g. 1234" required>
    </div>
'''.format(escape_html(org_id or ""))

    known_ids = set(str(row.OrganizationId) for row in org_list)
    options = ['<option value="">Select an involvement&hellip;</option>']
    for row in org_list:
        selected = " selected" if str(row.OrganizationId) == str(org_id or "") else ""
        options.append(
            '<option value="{0}"{1}>{2}</option>'.format(
                row.OrganizationId, selected, escape_html(row.OrganizationName)
            )
        )
    select_html = '''
    <div class="sh-field sh-field-wide">
      <label for="OrgId">Involvement</label>
      <select id="OrgId" name="OrgId">{0}</select>
    </div>
'''.format("".join(options))

    # If the current OrgId (e.g. from a hand-edited URL, or an org whose
    # only shifts are all in the past/future outside any window) isn't in
    # the active-Scheduler-with-shifts list, still let it be entered
    # directly rather than silently losing it.
    manual_html = ""
    if org_id and str(org_id) not in known_ids:
        manual_html = '''
    <div class="sh-field">
      <label for="OrgIdManual">Or enter an OrganizationId</label>
      <input type="text" id="OrgIdManual" name="OrgIdManual" value="{0}" placeholder="e.g. 1234">
    </div>
'''.format(escape_html(org_id))
    else:
        manual_html = '''
    <div class="sh-field">
      <label for="OrgIdManual">Or enter an OrganizationId</label>
      <input type="text" id="OrgIdManual" name="OrgIdManual" placeholder="not listed above?">
    </div>
'''
    return select_html + manual_html


def render_form(org_id, start_date, end_date, view, org_list, person_name="", error=None):
    parts = []
    if error:
        parts.append('<div class="sh-error">{0}</div>'.format(error))
    name_field = ""
    if view == "Mine":
        name_field = '''
    <div class="sh-field">
      <label for="PersonName">Name</label>
      <input type="text" id="PersonName" name="PersonName" value="{0}" placeholder="e.g. Debbie">
    </div>
'''.format(escape_html(person_name or ""))
    parts.append('''
<form class="sh-form" method="get" action="">
  <input type="hidden" name="View" value="{3}">
  <div class="sh-row">
    {5}
    <div class="sh-field">
      <label for="StartDate">Start date</label>
      <input type="date" id="StartDate" name="StartDate" value="{1}">
    </div>
    <div class="sh-field">
      <label for="EndDate">End date</label>
      <input type="date" id="EndDate" name="EndDate" value="{2}">
    </div>
    {4}
    <div class="sh-field">
      <button type="submit">View</button>
    </div>
  </div>
</form>
'''.format(
        escape_html(org_id or ""), start_date or "", end_date or "", view, name_field,
        render_org_field(org_id, org_list),
    ))
    return "".join(parts)


def tabs_html(org_id, start_date, end_date, view, person_name):
    def link(v, label):
        cls = "sh-tab-on" if v == view else ""
        pn = "&PersonName={0}".format(person_name) if (v == "Mine" and person_name) else ""
        return '<a class="{0}" href="?OrgId={1}&StartDate={2}&EndDate={3}&View={4}{5}">{6}</a>'.format(
            cls, org_id, start_date, end_date, v, pn, label
        )
    return '<div class="sh-tabs">{0}{1}</div>'.format(
        link("Board", "Coverage board"), link("Mine", "My shifts")
    )


def to_python_datetime(value):
    """TouchPoint's q.QuerySql hands back DateTime columns as .NET DateTime
    objects (no .strftime, confirmed live 2026-09-24 -- AttributeError on
    ShiftStart.strftime), not Python datetimes. Stringify and reparse, same
    convention as normalize_date() elsewhere in this repo (e.g.
    RPC_AttendanceRoster.py), extended to keep the time-of-day component
    since a shift's time is the point here, not just its date."""
    if hasattr(value, "strftime"):
        return value
    text = str(value).strip()
    text = re.sub(r"\.\d+$", "", text)  # strip .NET fractional-tick suffix, if present
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


def fetch_shifts(org_id, start_date, end_date):
    """Returns (shift_dict, ordered_keys). Key = (ShiftStart, TeamOrSlot)."""
    end_date_exclusive = (
        datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")
    rows = q.QuerySql(
        SCHEDULE_SQL,
        {"OrgId": org_id, "StartDate": start_date, "EndDateExclusive": end_date_exclusive},
    )
    shifts = {}
    order = []
    for row in rows:
        key = (to_python_datetime(row.ShiftStart), row.TeamOrSlot)
        if key not in shifts:
            shifts[key] = []
            order.append(key)
        if row.PeopleId:
            display = row.PersonName
            if row.VolunteerOption and row.VolunteerOption != "This Time Slot":
                display = "{0} ({1})".format(display, row.VolunteerOption)
            shifts[key].append((row.PeopleId, display))
    return shifts, order


def render_board(shifts, order, today):
    """Days as columns, TeamOrSlot as rows. Gaps are loud; N/A cells are quiet."""
    if not order:
        print('<div class="sh-empty">No shifts found for this involvement in this date range.</div>')
        return

    dates = sorted(set(k[0].date() if hasattr(k[0], "date") else k[0] for k in order))

    # A shift's own name isn't always spelled/cased the same way week to
    # week (confirmed live -- see canonical_team_key's docstring), so rows
    # are grouped by a case-and-whitespace-blind key, and the row's header
    # is whichever raw spelling actually appeared most often -- a real
    # spelling that was used, never an invented one.
    label_votes = {}
    for _, team in order:
        team_key = canonical_team_key(team)
        label_votes.setdefault(team_key, Counter())[normalize_team_label(team)] += 1
    display_label = {k: v.most_common(1)[0][0] for k, v in label_votes.items()}
    team_keys = sorted(display_label, key=lambda k: display_label[k])

    # cell[(team_key, date)] = list of display names, or None if not scheduled that day
    cell = {}
    for shift_start, team in order:
        d = shift_start.date() if hasattr(shift_start, "date") else shift_start
        key = (canonical_team_key(team), d)
        cell.setdefault(key, []).extend(name for _, name in shifts[(shift_start, team)])

    today_date = today.date() if hasattr(today, "date") else today

    print('<div class="sh-boardwrap"><table class="sh-board">')
    print("<tr><th class=\"sh-rowhead\">Shift</th>")
    for d in dates:
        is_today = " sh-today" if d == today_date else ""
        print(
            '<th class="sh-colhead{0}">{1}<span class="sh-daynum">{2}</span></th>'.format(
                is_today, d.strftime("%a"), d.day
            )
        )
    print("</tr>")

    for team_key in team_keys:
        print('<tr><th class="sh-rowhead">{0}</th>'.format(display_label[team_key]))
        for d in dates:
            key = (team_key, d)
            if key not in cell:
                print('<td class="sh-cell sh-na">&mdash;</td>')
                continue
            names = cell[key]
            is_past = d < today_date
            if names:
                past_tag = '<span class="sh-past-tag">covered</span>' if is_past else ""
                print(
                    '<td class="sh-cell sh-filled">{0}{1}</td>'.format(
                        "; ".join(names), past_tag
                    )
                )
            else:
                label = "GAP" if not is_past else "NOT COVERED"
                print(
                    '<td class="sh-cell sh-gap">&#9679;<span class="sh-gap-label">{0}</span></td>'.format(
                        label
                    )
                )
        print("</tr>")
    print("</table></div>")

    print(
        '<div class="sh-legend">'
        '<span class="sh-swatch" style="background:{0}"></span>Unfilled shift &nbsp; '
        '<span class="sh-swatch" style="background:#fafbfc;border:1px solid {1}"></span>'
        "No shift scheduled that day</div>".format(GAP_RED, LIGHT_GRAY)
    )


def render_mine(shifts, order, today, person_name, org_id, start_date, end_date):
    if not person_name:
        print(
            '<div class="sh-empty">Enter a name above and press View to see one '
            "person's shifts (past and upcoming) in this date range.</div>"
        )
        return

    needle = person_name.strip().lower()
    matches = {}  # PeopleId -> display name
    for key in order:
        for people_id, name in shifts[key]:
            base_name = name.split(" (")[0]
            if needle in base_name.lower():
                matches[people_id] = base_name

    if not matches:
        print(
            '<div class="sh-empty">No one matching &ldquo;{0}&rdquo; is signed up for '
            "any shift in this date range.</div>".format(person_name)
        )
        return

    if len(matches) > 1:
        print('<div class="sh-searchresult">More than one match for &ldquo;{0}&rdquo; -- pick one:</div>'.format(person_name))
        print('<ul class="sh-matchlist">')
        for _, name in sorted(matches.items(), key=lambda kv: kv[1]):
            print(
                '<li><a href="?OrgId={0}&StartDate={1}&EndDate={2}&View=Mine&PersonName={3}">{3}</a></li>'.format(
                    org_id, start_date, end_date, name
                )
            )
        print("</ul>")
        return

    target_name = list(matches.values())[0]
    print('<div class="sh-searchresult">Shifts for <strong>{0}</strong>:</div>'.format(target_name))

    today_val = today
    entries = []
    for shift_start, team in order:
        for people_id, name in shifts[(shift_start, team)]:
            if name.split(" (")[0] == target_name:
                entries.append((shift_start, team, name))

    if not entries:
        print('<div class="sh-empty">No shifts found for {0} in this date range.</div>'.format(target_name))
        return

    print('<ul class="sh-mine">')
    for shift_start, team, name in entries:
        is_past = shift_start < today_val
        li_class = "sh-mine-past" if is_past else ""
        print(
            '<li class="{0}"><span class="sh-mine-when">{1} &middot; {2}</span>'
            '<span class="sh-mine-team">{3}</span></li>'.format(
                li_class, format_shift_date(shift_start), format_shift_time(shift_start),
                normalize_team_label(team),
            )
        )
    print("</ul>")


def main():
    org_id_raw = model.Data.OrgId if hasattr(model.Data, "OrgId") else ""
    manual_org_id = str(model.Data.OrgIdManual).strip() if hasattr(model.Data, "OrgIdManual") and model.Data.OrgIdManual else ""
    if manual_org_id:
        org_id_raw = manual_org_id
    start_raw = model.Data.StartDate if hasattr(model.Data, "StartDate") else ""
    end_raw = model.Data.EndDate if hasattr(model.Data, "EndDate") else ""
    view = str(model.Data.View).strip() if hasattr(model.Data, "View") and model.Data.View else "Board"
    if view not in ("Board", "Mine"):
        view = "Board"
    person_name = str(model.Data.PersonName).strip() if hasattr(model.Data, "PersonName") and model.Data.PersonName else ""

    default_start, default_end = week_bounds(date.today())
    start_date = valid_date(start_raw) or default_start
    end_date = valid_date(end_raw) or default_end

    model.Header = "Scheduler Coverage Board"

    print('<div id="{0}">'.format(ROOT_ID))
    print("<style>{0}</style>".format(scope_css(CSS)))
    print('<div class="sh-church">ROCKPOINTE CHURCH</div>')
    print("<h1>Scheduler Coverage</h1>")
    print(
        '<div class="sh-meta">The built-in Scheduler tab hides a shift once its date '
        "passes. This shows every shift -- past and upcoming -- so gaps and "
        "past coverage are both visible.</div>"
    )

    org_list = fetch_scheduler_orgs()

    org_id = to_int(org_id_raw)
    if not org_id:
        print(render_form(org_id_raw, start_date, end_date, view, org_list))
        print(
            '<div class="sh-empty">Choose a Scheduler involvement above to view its '
            "shifts.</div>"
        )
        print("</div>")
        return

    try:
        org = model.GetOrganization(org_id)
    except Exception:
        org = None

    if not org:
        print(render_form(org_id_raw, start_date, end_date, view, org_list,
                           error="No involvement found for OrganizationId {0}.".format(org_id)))
        print("</div>")
        return

    if start_date > end_date:
        print(render_form(org_id, start_date, end_date, view, org_list,
                           error="Start date must be on or before end date."))
        print("</div>")
        return

    print(render_form(org_id, start_date, end_date, view, org_list, person_name))
    print(tabs_html(org_id, start_date, end_date, view, person_name))

    prev_start, prev_end = shift_neighbor(start_date, end_date, -1)
    next_start, next_end = shift_neighbor(start_date, end_date, 1)
    print('<div class="sh-nav">'
          '<a href="?OrgId={0}&StartDate={1}&EndDate={2}&View={5}">&laquo; Previous period</a>'
          '<a href="?OrgId={0}&StartDate={3}&EndDate={4}&View={5}">Next period &raquo;</a>'
          "</div>".format(org_id, prev_start, prev_end, next_start, next_end, view))

    print("<h2>{0}</h2>".format(org.name))
    print('<div class="sh-meta">{0} through {1}</div>'.format(start_date, end_date))

    shifts, order = fetch_shifts(org_id, start_date, end_date)
    today = datetime.now()

    if view == "Mine":
        render_mine(shifts, order, today, person_name, org_id, start_date, end_date)
    else:
        render_board(shifts, order, today)

    print("</div>")


main()
