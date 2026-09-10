"""
RPC_AttendanceCounts.py

TouchPoint Special Content (Python Script). Read-only.

Attendance COUNT report for one or more active involvements in ANY RPC
ministry. Same live three-step picker as
attendance-roster-report/RPC_AttendanceRoster.py (Ministry -> Division ->
Involvement(s) + options), but the output is the SM/CM attendance
dashboard's shape rather than a printable person-level roster:

    Involvement                 9/7  8/31  8/24 | Mtgs Total  Avg | Members Leaders
    ----------------------------------------------------------------------------
    SM: CC 6th Guys              12    14    11 |    3    37 12.3 |      35       2
    SM: CC 6th Girls              9     8    10 |    3    27  9.0 |      25       2
    SM: PS 9th Guys              15    13    16 |    3    44 14.7 |      41       3
    ----------------------------------------------------------------------------
    TOTAL                        36    35    37 |    3   108 36.0 |     101       7

One row per selected involvement, one column per meeting date any selected
involvement actually held, a bold TOTAL row, and a stat bar (dates, total
visits, average per date, peak date) above the grid.

Counts come from dbo.Attend rows (AttendanceFlag = 1, NoShow excluded),
NOT dbo.Meetings.NumPresent -- that is the deliberate difference from
attendance-dashboard/sm-attendance-pyreport.py, and it is what makes the
Members/Leaders split possible: Attend carries its own MemberTypeId per
attendance record (the same column sm-attendance-pyreport.py already uses
to count guests). NumPresent is a single blended headcount with no way to
separate students from the adults serving them.

WHY THE TWO SOURCES CAN DISAGREE: NumPresent is whatever headcount was
recorded on the meeting; Attend rows are the individually-marked people. A
class that records "18 present" but only marks 15 people will read 15
here and 18 on the SM/CM dashboard. That is a real data-entry gap, not a
bug in either report -- see README.md.

Because a person is counted once per (meeting, person), an organization
holding several meetings on one date (per DB_REFERENCE.md, the PS Welcome
Team had three on 2026-08-16) sums all of them into that date's cell,
rather than picking one -- which is the documented-correct behavior.

Stage-3 options, all round-tripped through the query string so a generated
report's URL can be bookmarked to "save" that configuration:
  - Involvement checkboxes, with a search box and Select all / Clear all
    (a counts report usually wants a whole division, unlike a roster).
  - Start / End date, with 4 / 8 / 13-week presets. Defaults to the last
    DEFAULT_RANGE_WEEKS weeks -- unlike the roster's one-sided "attendance
    since", a counts grid needs both ends or the column count runs away.
  - Count who: Everyone / Members only / Leaders & volunteers only. When
    this is anything but Everyone, the Members/Leaders breakdown columns
    are suppressed (they would just restate the filter) and the grid says
    what it is filtered to.
  - Sort involvements by name, or by total attendance high-to-low.
  - Optionally hide involvements that held no meeting in the range.

A cell distinguishes three states, which is the whole point of reading
this grid: a number (a meeting was held, that many were marked present),
"0" (a meeting was held and NOBODY was marked present -- the thing worth
chasing), and a dim middot (that involvement held no meeting that day, so
there is nothing to chase).

Row-level security is the same model.UserPeopleId pattern as the roster
report: unless the logged-in user is in ADMIN_BYPASS_PEOPLE_IDS, stages 1
and 2 only offer a ministry/division the user has some OrganizationMembers
row under. Code-level filtering, not a TouchPoint permission feature.

Deploy: Admin > Advanced > Special Content > Python Scripts > +New
Script name: RPC_AttendanceCounts
Access via /PyScript/RPC_AttendanceCounts (not the Special Content admin
"run" preview) so the picker's buttons and query-string reruns work.

NOT YET LIVE-VALIDATED against RPC's TouchPoint -- see README.md.
"""

import re
from datetime import datetime, timedelta

# ============================================================
# Config
# ============================================================
ACTIVE_STATUS_ID = 30

# PeopleIds who see every ministry/division regardless of their own
# OrganizationMembers rows. Same list as RPC_AttendanceRoster.py --
# confirmed 2026-08-30 per Brian.
ADMIN_BYPASS_PEOPLE_IDS = [47110, 7059]  # Brian Vinson, Marlene Godinez

# dbo.Program rows that are internal reporting/admin buckets, not real
# ministries. Kept in sync with RPC_AttendanceRoster.py (confirmed live
# 2026-08-30, see DB_REFERENCE.md OrganizationStructure).
EXCLUDED_PROGRAM_IDS = [1124, 1127, 1130, 1137, 1138, 1141]

# Which bucket each Attend.MemberTypeId counts into. Ids per
# DB_REFERENCE.md (136 Coach / 140 Leader / 220 Member / 710 Volunteer);
# 310 Guest is carried over from attendance-dashboard/sm-attendance-
# pyreport.py's @GuestTypeId and is the one id here NOT independently
# confirmed in DB_REFERENCE.md.
#
# Anything not listed falls into "other" so the arithmetic always
# reconciles -- Total = Members + Leaders + Other, with the Other column
# rendered only when it is nonzero (and footnoted with which types landed
# there). An unmapped id therefore shows up visibly instead of silently
# inflating or deflating one of the two named columns.
MEMBER_TYPE_BUCKETS = {
    220: "member",
    140: "leader",
    136: "leader",
    710: "leader",
}
BUCKET_OTHER = "other"
MEMBER_TYPE_LABELS = {
    136: "Coach",
    140: "Leader",
    220: "Member",
    310: "Guest",
    710: "Volunteer",
}

# Stage-3 "Count who" filter. Values are bucket names (or "all").
COUNT_WHO_OPTIONS = [
    ("all", "Everyone marked present"),
    ("member", "Members only (excludes leaders/volunteers)"),
    ("leader", "Leaders & volunteers only"),
]
COUNT_WHO_KEYS = [k for k, _ in COUNT_WHO_OPTIONS]
COUNT_WHO_LABELS = dict(COUNT_WHO_OPTIONS)
DEFAULT_COUNT_WHO = "all"

# How the date columns are bucketed. "date" is one column per meeting date
# (the original behavior); "week" collapses each week into one column, which
# is what makes a school-year-length range readable -- ~40 columns instead of
# ~40 dates plus every midweek and special meeting.
#
# Weeks start SUNDAY, matching how the church reads a week and how
# OrgSchedule stores it (SchedDay = 0 is Sunday, per DB_REFERENCE.md).
# Deliberately computed in Python rather than with T-SQL's DATEPART(dw),
# whose answer depends on the session's DATEFIRST setting -- the exact trap
# DB_REFERENCE.md calls out.
GROUP_DATES_OPTIONS = [
    ("date", "Each meeting date (one column per date)"),
    ("week", "By week (Sunday-Saturday, one column per week)"),
]
GROUP_DATES_KEYS = [k for k, _ in GROUP_DATES_OPTIONS]
DEFAULT_GROUP_DATES = "date"

SORT_BY_OPTIONS = [
    ("name", "Involvement name (A-Z)"),
    ("total", "Total attendance (highest first)"),
]
SORT_BY_KEYS = [k for k, _ in SORT_BY_OPTIONS]
DEFAULT_SORT_BY = "name"

# Default date range when none is in the query string. Both ends are
# required (unlike the roster's open-ended "attendance since") because
# every meeting date becomes a column -- an unbounded range on an org with
# years of history produces a grid nobody can read.
DEFAULT_RANGE_WEEKS = 8
RANGE_PRESET_WEEKS = [4, 8, 13]

# Deep links back into TouchPoint. Both paths are confirmed: /Org/{id} is
# documented (docs.touchpointsoftware.com/Organizations/Organization.html --
# "This ID can be found at the end of the URL when you are viewing the
# Involvement"), and /Meeting/{MeetingId} is used by two independent
# bswaby/Touchpoint tools (TPxi_AttendanceMarkings, TPxi_SQLQueryExplorer),
# as is the #tab-Meetings-tab anchor. The meeting page is TouchPoint's own
# attendance list for that meeting -- names, present/absent, member type,
# headcount -- which is exactly what a count on this grid is a summary of.
#
# model.CmsHost is the repo's proven pattern (the task dashboards deep-link
# to /Person2/{id} with it). When it is missing these degrade to
# host-relative URLs, which still resolve because this report is served from
# the same TouchPoint host.
ORG_URL = "{host}/Org/{org_id}"
ORG_MEETINGS_URL = "{host}/Org/{org_id}#tab-Meetings-tab"
MEETING_URL = "{host}/Meeting/{meeting_id}"

# Hard ceiling on date columns, so a wide hand-edited date range can't
# render a grid with hundreds of columns. The report still renders -- it
# reports the truncation and keeps the most recent MAX_DATE_COLUMNS dates.
MAX_DATE_COLUMNS = 60

# ============================================================
# RPC brand styling
# ============================================================
# Main RockPointe Church palette (the default per Comms Director Jessica
# Siri -- ministry sheets are only for artifacts branded to that ministry's
# audience, which a church-wide staff tool is not).
NAVY = "#0C2340"
YELLOW = "#FFD242"
SPACE_BLUE = "#183D5F"
CURIOUS_BLUE = "#1D6A94"
STEEL_BLUE = "#4580B9"
LIGHT_GRAY = "#D1D3D4"

TITLE_FONT = '"Bebas Neue", Impact, "Arial Narrow", Haettenschweiler, sans-serif'
SUBTITLE_FONT = 'Montserrat, "Segoe UI", Tahoma, sans-serif'
BODY_FONT = '-apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif'

BUILDER_CSS = """
  *, *::before, *::after { box-sizing: border-box; }
  body { font-family: %(body)s; margin: 0; padding: 0 0 40px; color: #222;
         background: #f7f9fb; -webkit-font-smoothing: antialiased; }
  .ac-bar { background: %(navy)s; border-bottom: 4px solid %(yellow)s;
         padding: 26px 24px 22px; margin: 12px 0 0; overflow: visible; }
  .ac-bar .ac-church { font-family: %(subtitle)s; font-size: 11px; letter-spacing: 0.14em;
                 text-transform: uppercase; color: %(yellow)s; margin: 0 0 6px; font-weight: 600;
                 line-height: 1; }
  .ac-bar h1 { font-family: %(title)s; font-size: 30px; line-height: 1.15; letter-spacing: 0.03em;
            color: #fff; margin: 0; padding: 0; font-weight: normal; text-transform: uppercase; }
  .ac-wrap { max-width: 720px; margin: 0 auto; padding: 22px 24px 0; }
  .ac-steps { font-family: %(subtitle)s; font-size: 11px; letter-spacing: 0.10em;
           text-transform: uppercase; color: %(curious)s; font-weight: 600; margin: 0 0 14px; }
  .ac-steps .ac-on { color: %(navy)s; }
  .ac-steps .ac-sep { color: %(gray)s; padding: 0 6px; }
  .ac-meta { color: #55606b; font-size: 13px; margin: 0 0 18px; line-height: 1.5; }
  .ac-back { margin: 0 0 14px; font-size: 13px; }
  a { color: %(curious)s; }
  a:hover { color: %(navy)s; }
  .ac-card { background: #fff; border: 1px solid #e3e8ee; border-radius: 6px;
          padding: 22px 24px 14px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(12,35,64,0.05); }
  fieldset { border: 0; border-top: 1px solid #e3e8ee; padding: 22px 0 0; margin: 24px 0 4px; }
  fieldset.ac-first { border-top: 0; padding-top: 0; margin-top: 0; }
  legend { font-family: %(subtitle)s; font-size: 11px; font-weight: 700; color: %(navy)s;
           padding: 0; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.09em; }
  .ac-field { margin-bottom: 16px; }
  label { display: block; font-size: 13px; color: #3d4753; margin-bottom: 5px; font-weight: 600; }
  label.ac-checklabel { font-weight: normal; color: #222; }
  .ac-orglist { border: 1px solid %(gray)s; border-radius: 4px; padding: 6px 12px;
             max-height: 320px; overflow-y: auto; background: #fff; }
  .ac-orgcb { display: block; font-size: 14px; color: #222; padding: 5px 0;
           font-weight: normal; border-bottom: 1px solid #f0f3f6; }
  .ac-orgcb:last-child { border-bottom: 0; }
  .ac-cnt { color: #6b7683; font-size: 12px; }
  select, input[type=date] { font-family: %(body)s; font-size: 14px; padding: 7px 8px;
          width: 100%%; max-width: 460px; border: 1px solid %(gray)s; border-radius: 4px;
          background: #fff; color: #222; }
  select:focus, input:focus { outline: 2px solid %(steel)s; outline-offset: 1px;
          border-color: %(curious)s; }
  button { font-family: %(subtitle)s; font-size: 14px; font-weight: 700; letter-spacing: 0.04em;
           padding: 11px 30px; margin-top: 4px; color: #fff; background: %(navy)s;
           border: 0; border-radius: 4px; cursor: pointer; text-transform: uppercase; }
  button:hover { background: %(space)s; }
  button:active { background: %(curious)s; }
  .ac-hint { font-size: 12px; color: #6b7683; margin: 8px 0 0; line-height: 1.5; }
  .ac-searchrow { position: relative; margin-bottom: 8px; }
  .ac-searchrow input { width: 100%%; max-width: none; padding: 8px 34px 8px 10px; }
  .ac-searchrow .ac-clear { position: absolute; right: 8px; top: 50%%; transform: translateY(-50%%);
            border: 0; background: none; color: #8a949e; font-size: 18px; line-height: 1;
            padding: 2px 4px; cursor: pointer; margin: 0; border-radius: 3px;
            text-transform: none; letter-spacing: 0; font-weight: normal; }
  .ac-searchrow .ac-clear:hover { color: %(navy)s; background: #eef2f6; }
  .ac-listmeta { font-size: 12px; color: #6b7683; margin: 7px 0 0; }
  .ac-listmeta strong { color: %(navy)s; }
  .ac-noresults { font-size: 13px; color: #6b7683; padding: 14px 2px; font-style: italic; }
  /* Secondary "chip" buttons: Select all / Clear all, and the week presets.
     Deliberately not the navy primary button -- these change the form, they
     don't submit it. */
  .ac-chiprow { margin: 8px 0 0; }
  .ac-chip { font-family: %(subtitle)s; font-size: 12px; font-weight: 600; letter-spacing: 0.03em;
          text-transform: none; padding: 6px 13px; margin: 0 6px 0 0; color: %(navy)s;
          background: #eef2f6; border: 1px solid %(gray)s; border-radius: 20px; }
  .ac-chip:hover { background: %(steel)s; color: #fff; border-color: %(steel)s; }
  .ac-chip.ac-chipon { background: %(navy)s; color: #fff; border-color: %(navy)s; }
  .ac-daterow { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
  .ac-daterow input[type=date] { max-width: 190px; }
  .ac-datesep { color: #6b7683; font-size: 13px; }
  .ac-hide { display: none !important; }
""" % {
    "body": BODY_FONT, "title": TITLE_FONT, "subtitle": SUBTITLE_FONT,
    "navy": NAVY, "yellow": YELLOW, "space": SPACE_BLUE, "curious": CURIOUS_BLUE,
    "steel": STEEL_BLUE, "gray": LIGHT_GRAY,
}

# Stage 4. Unlike the roster (a print-first artifact that stays white), this
# is a screen-first dashboard -- so the stat bar and header row carry filled
# brand color, and print rules strip the interactive chrome.
REPORT_CSS = """
  @media print {
    @page { size: landscape; margin: 0.4in; }
    .ac-no-print { display: none !important; }
    body { background: #fff; }
    .ac-tablewrap { overflow: visible; }
    .ac-stats { break-inside: avoid; }
  }
  *, *::before, *::after { box-sizing: border-box; }
  body { font-family: %(body)s; margin: 0; padding: 0 0 40px; color: #222; background: #f7f9fb; }
  .ac-bar { background: %(navy)s; border-bottom: 4px solid %(yellow)s;
         padding: 22px 24px 18px; margin: 12px 0 0; display: flex; flex-wrap: wrap;
         align-items: flex-end; justify-content: space-between; gap: 12px; }
  .ac-bar .ac-church { font-family: %(subtitle)s; font-size: 11px; letter-spacing: 0.14em;
                 text-transform: uppercase; color: %(yellow)s; margin: 0 0 6px; font-weight: 600;
                 line-height: 1; }
  .ac-bar h1 { font-family: %(title)s; font-size: 28px; line-height: 1.15; letter-spacing: 0.03em;
            color: #fff; margin: 0; font-weight: normal; text-transform: uppercase; }
  .ac-bar .ac-sub { font-family: %(subtitle)s; font-size: 12px; color: #cdd8e4; margin: 6px 0 0; }
  .ac-btnrow { display: flex; gap: 8px; }
  .ac-btnrow button { font-family: %(subtitle)s; font-size: 12px; font-weight: 700;
          letter-spacing: 0.04em; text-transform: uppercase; padding: 8px 16px;
          color: %(navy)s; background: %(yellow)s; border: 0; border-radius: 4px; cursor: pointer; }
  .ac-btnrow button:hover { background: #fff; }
  .ac-wrap { max-width: 1500px; margin: 0 auto; padding: 18px 24px 0; }
  .ac-back { margin: 0 0 14px; font-size: 13px; }
  a { color: %(curious)s; }
  a:hover { color: %(navy)s; }
  .ac-stats { display: flex; flex-wrap: wrap; gap: 1px; background: #e3e8ee;
           border: 1px solid #e3e8ee; border-radius: 6px; overflow: hidden; margin: 0 0 16px; }
  .ac-stat { background: #fff; padding: 13px 20px; flex: 1 1 130px; }
  .ac-statval { display: block; font-family: %(subtitle)s; font-size: 22px; font-weight: 700;
             color: %(navy)s; line-height: 1.15; }
  .ac-statlbl { display: block; font-size: 11px; color: #6b7683; margin-top: 3px;
             text-transform: uppercase; letter-spacing: 0.06em; }
  .ac-note { font-size: 12px; color: #55606b; margin: 0 0 14px; line-height: 1.55; }
  .ac-note strong { color: %(navy)s; }
  .ac-warn { font-size: 13px; margin: 0 0 14px; padding: 9px 12px; border-radius: 4px;
          background: #fff8e1; border-left: 4px solid %(yellow)s; color: #6b5600; line-height: 1.5; }
  .ac-tablewrap { background: #fff; border: 1px solid #e3e8ee; border-radius: 6px;
               overflow-x: auto; margin-bottom: 18px; }
  table { border-collapse: collapse; width: 100%%; }
  thead { display: table-header-group; }
  th, td { border-bottom: 1px solid #eef2f6; padding: 7px 9px; font-size: 13px;
           text-align: right; white-space: nowrap; }
  th { background: %(navy)s; color: #fff; font-family: %(subtitle)s; font-size: 11px;
       text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;
       border-bottom: 0; position: sticky; top: 0; }
  th.ac-name, td.ac-name { text-align: left; white-space: normal; min-width: 210px;
       position: sticky; left: 0; background: #fff; }
  th.ac-name { background: %(navy)s; z-index: 2; }
  tbody tr:nth-child(even) td { background: #fbfcfd; }
  tbody tr:nth-child(even) td.ac-name { background: #fbfcfd; }
  tbody tr:hover td { background: #eef4f9; }
  tbody tr:hover td.ac-name { background: #eef4f9; }
  /* The divider before the summary columns, so the eye knows where the
     per-date grid stops and the roll-ups start. */
  th.ac-sep, td.ac-sep { border-left: 2px solid %(gray)s; }
  /* Cells are links, but the grid has to stay scannable as numbers --
     so no underline or link color until hover. */
  td a, th.ac-name a { color: inherit; text-decoration: none; }
  td a:hover, th.ac-name a:hover { color: %(curious)s; text-decoration: underline; }
  td.ac-name a { color: %(navy)s; font-weight: 600; }
  td.ac-multi sup { font-size: 9px; color: %(curious)s; padding-left: 1px; }
  @media print {
    td a, td.ac-name a { color: inherit !important; text-decoration: none !important; }
  }
  td.ac-tot { font-weight: 700; color: %(navy)s; }
  td.ac-none { color: %(gray)s; }
  td.ac-zero { color: #b3261e; font-weight: 700; }
  tr.ac-grand td { background: #eef2f6 !important; font-weight: 700; color: %(navy)s;
       border-top: 2px solid %(navy)s; border-bottom: 0; font-size: 13px; }
""" % {
    "body": BODY_FONT, "title": TITLE_FONT, "subtitle": SUBTITLE_FONT,
    "navy": NAVY, "yellow": YELLOW, "curious": CURIOUS_BLUE, "gray": LIGHT_GRAY,
}

# This script's HTML is injected INTO a TouchPoint page that brings its own
# (Bootstrap-derived) stylesheet, so generic class names are a live
# collision risk -- confirmed on RPC_AttendanceRoster.py's first live run,
# where the branded header's eyebrow line vanished entirely. Two defenses,
# both required: every class is prefixed `ac-`, AND every rule is scoped
# under this wrapper id at render time (which is what protects the bare
# element selectors -- table/th/td/button/select -- that can't be prefixed).
ROOT_ID = "rpcAttendanceCounts"


def scope_css(css, root="#" + ROOT_ID):
    """Prefix every selector in `css` with `root`; retarget `body` to it.

    Same implementation as RPC_AttendanceRoster.py's -- deliberately
    duplicated rather than shared, since TouchPoint Special Content scripts
    are each deployed as one standalone blob with no import path between
    them.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)  # comments confuse the scanner

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
            # @media/@supports wrap real selectors; @page and friends don't.
            if selector.startswith("@media") or selector.startswith("@supports"):
                out.append("\n%s {%s}" % (selector, scope_css(css[brace + 1:end], root)))
            else:
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


def steps_html(current):
    labels = ["1. Ministry", "2. Division", "3. Involvements + range"]
    parts = []
    for i, label in enumerate(labels, start=1):
        cls = ' class="ac-on"' if i == current else ""
        parts.append("<span{0}>{1}</span>".format(cls, label))
    return '<span class="ac-sep">&rsaquo;</span>'.join(parts)


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
    # 'M/D/YYYY' depending on context -- normalize both so date-string
    # lookups are consistent. Same helper as RPC_AttendanceRoster.py.
    value = str(value or "").strip()
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
    """'YYYY-MM-DD' -> 'M/D' (AP style: Arabic figures, no ordinals)."""
    y, m, d = date_str.split("-")
    return "{0}/{1}".format(int(m), int(d))


def fmt_long_date(date_str):
    """'YYYY-MM-DD' -> 'February 17' / 'February 17, 2025' per the RPC Style
    Guide: no ordinals, and the year omitted only within the current
    calendar year."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return date_str
    if dt.year == datetime.now().year:
        return dt.strftime("%B ") + str(dt.day)
    return dt.strftime("%B ") + str(dt.day) + ", " + str(dt.year)


def esc(s):
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def js_string(s):
    """Escape a Python string for embedding inside a JS single-quoted
    literal. '</' is broken up so a value can never close the <script>."""
    return (
        str(s if s is not None else "")
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace("</", "<\\/")
    )


def valid_date(value, fallback):
    """Strict YYYY-MM-DD only -- what an HTML5 date input submits. Anything
    else (blank, malformed, a paste gone wrong) falls back rather than
    being trusted into SQL. Both date inputs are string-interpolated into
    the query, so this is the only thing standing between the query string
    and the database; keep it strict."""
    value = str(value or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return fallback
    try:
        datetime.strptime(value, "%Y-%m-%d")  # rejects 2026-02-31 etc.
    except ValueError:
        return fallback
    return value


def valid_count_who(value):
    return value if value in COUNT_WHO_KEYS else DEFAULT_COUNT_WHO


def valid_sort_by(value):
    return value if value in SORT_BY_KEYS else DEFAULT_SORT_BY


def valid_group_dates(value):
    return value if value in GROUP_DATES_KEYS else DEFAULT_GROUP_DATES


def week_start(date_str):
    """The Sunday on or before `date_str`, as 'YYYY-MM-DD'."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    # Python's weekday() is Mon=0..Sun=6, so this is days since Sunday.
    return (dt - timedelta(days=(dt.weekday() + 1) % 7)).strftime("%Y-%m-%d")


def period_key(date_str, group_dates):
    """Which column a meeting date belongs to. The single place the two
    grouping modes differ -- everything downstream just handles opaque,
    chronologically-sortable column keys."""
    return week_start(date_str) if group_dates == "week" else date_str


def fmt_week_span(start_str):
    """'2026-08-24' -> 'August 24-30'. Per the RPC Style Guide: Arabic
    figures, no ordinals, same-month ranges hyphenated with no spaces
    ('March 9-12'), cross-month ranges spaced ('May 30 - June 2')."""
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    if start.month == end.month:
        label = "{0} {1}-{2}".format(start.strftime("%B"), start.day, end.day)
        if start.year != datetime.now().year:
            label += ", " + str(start.year)
        return label
    return "{0} \u2013 {1}".format(fmt_long_date(start_str),
                                   fmt_long_date(end.strftime("%Y-%m-%d")))


def col_header(key, group_dates):
    """Short column heading. Week columns are prefixed so a printed grid
    can't be misread as a single date."""
    return ("Wk " if group_dates == "week" else "") + fmt_col_header(key)


def col_title(key, group_dates):
    """Hover text spelling the column out in full."""
    return fmt_week_span(key) if group_dates == "week" else fmt_long_date(key)


def bucket_for(member_type_id):
    return MEMBER_TYPE_BUCKETS.get(member_type_id, BUCKET_OTHER)


def member_type_label(member_type_id):
    return MEMBER_TYPE_LABELS.get(member_type_id, "Type {0}".format(member_type_id))


def fmt_avg(total, divisor):
    if not divisor:
        return "&mdash;"
    return "{0:.1f}".format(float(total) / float(divisor))


def default_range():
    end = datetime.now().date()
    start = end - timedelta(weeks=DEFAULT_RANGE_WEEKS)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def render_picker(step_title, heading, meta_text, select_name, options_html,
                  hidden_fields=None, back_href=None, step_num=1):
    hidden_html = "".join(
        '<input type="hidden" name="{0}" value="{1}">'.format(k, v)
        for k, v in (hidden_fields or {}).items()
    )
    back_html = (
        '<p class="ac-back"><a href="{0}">&larr; Back</a></p>'.format(back_href)
        if back_href else ""
    )
    print(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{step_title}</title>
<style>{css}</style>
</head>
<body>
<div id="{root_id}">
<div class="ac-bar">
  <div>
    <p class="ac-church">RockPointe Church</p>
    <h1>Attendance Counts</h1>
  </div>
</div>
<div class="ac-wrap">
{back_html}
<p class="ac-steps">{steps}</p>
<div class="ac-card">
  <p class="ac-meta">{meta_text}</p>
  <form method="get">
    {hidden_html}
    <div class="ac-field">
      <label for="{select_name}">{heading}</label>
      <select name="{select_name}" id="{select_name}" required>
        <option value="">-- Select --</option>
        {options_html}
      </select>
    </div>
    <button type="submit">Continue</button>
  </form>
</div>
</div>
</div>
</body>
</html>""".format(
            step_title=step_title,
            css=scope_css(BUILDER_CSS),
            root_id=ROOT_ID,
            steps=steps_html(step_num),
            heading=heading,
            meta_text=meta_text,
            hidden_html=hidden_html,
            select_name=select_name,
            options_html=options_html,
            back_html=back_html,
        )
    )


def render_message(title, heading, body_html, back_href="?"):
    """Small standalone page for the dead ends (no divisions, no meetings in
    range). Uses the builder chrome so it doesn't look like an error page."""
    print(
        """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title>
<style>{css}</style></head>
<body>
<div id="{root_id}">
<div class="ac-bar">
  <div>
    <p class="ac-church">RockPointe Church</p>
    <h1>Attendance Counts</h1>
  </div>
</div>
<div class="ac-wrap">
<p class="ac-back"><a href="{back_href}">&larr; Back</a></p>
<div class="ac-card">
  <p class="ac-meta"><strong>{heading}</strong></p>
  {body_html}
</div>
</div>
</div>
</body>
</html>""".format(
            title=esc(title),
            css=scope_css(BUILDER_CSS),
            root_id=ROOT_ID,
            back_href=back_href,
            heading=esc(heading),
            body_html=body_html,
        )
    )


def render_org_and_options_picker(org_rows, selected_program, selected_division,
                                  start_date, end_date, count_who, sort_by, hide_empty,
                                  group_dates):
    """Stage 3: check involvement(s), pick a date range and the options."""

    def org_checkbox(r):
        return (
            '<label class="ac-orgcb" data-name="{search_name}">'
            '<input type="checkbox" class="ac-orgcheck" value="{oid}"> {name} '
            '<span class="ac-cnt">({count} member{plural})</span></label>'
        ).format(
            oid=r.OrganizationId,
            search_name=esc(str(r.OrganizationName or "").lower()).replace('"', "&quot;"),
            name=esc(r.OrganizationName),
            count=r.MemberCount,
            plural="" if r.MemberCount == 1 else "s",
        )

    checkbox_html = "".join(org_checkbox(r) for r in org_rows)

    def options_html(pairs, selected_key):
        return "".join(
            '<option value="{0}"{1}>{2}</option>'.format(
                key, ' selected' if key == selected_key else '', esc(label)
            )
            for key, label in pairs
        )

    preset_html = "".join(
        '<button type="button" class="ac-chip ac-preset" data-weeks="{0}">{0} wk</button>'.format(w)
        for w in RANGE_PRESET_WEEKS
    )

    print(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Choose Involvements -- Attendance Counts</title>
<style>{css}</style>
</head>
<body>
<div id="{root_id}">
<div class="ac-bar">
  <div>
    <p class="ac-church">RockPointe Church</p>
    <h1>Attendance Counts</h1>
  </div>
</div>
<div class="ac-wrap">
<p class="ac-back"><a href="?ProgId={prog_id}">&larr; Back</a></p>
<p class="ac-steps">{steps}</p>
<div class="ac-card">
<p class="ac-meta">{count} active involvement(s) in {div_name}. Each one you check becomes a row in the counts grid.</p>
<form method="get" id="pickerForm">
  <input type="hidden" name="ProgId" value="{prog_id}">
  <input type="hidden" name="DivId" value="{div_id}">
  <input type="hidden" name="OrgIds" id="OrgIdsField" value="">
  <fieldset class="ac-first">
    <legend>Involvements</legend>
    <div class="ac-searchrow">
      <input type="search" id="orgSearch" autocomplete="off"
             placeholder="Search involvements by name...">
      <button type="button" class="ac-clear" id="orgSearchClear" title="Clear search" hidden>&times;</button>
    </div>
    <div class="ac-orglist" id="orgList">{checkbox_html}<p class="ac-noresults" id="noResults" hidden>No involvements match that search.</p></div>
    <div class="ac-chiprow ac-no-print">
      <button type="button" class="ac-chip" id="selectAll">Select all shown</button>
      <button type="button" class="ac-chip" id="clearAll">Clear all</button>
    </div>
    <p class="ac-listmeta" id="listMeta"></p>
    <p class="ac-hint">Unlike the roster report, involvements here do <em>not</em> need to share a meeting schedule &mdash; each gets its own row, and a day it didn't meet shows a dim &middot; rather than a zero.</p>
  </fieldset>
  <fieldset>
    <legend>Date range</legend>
    <div class="ac-field">
      <label for="StartDate">Meetings from / to</label>
      <div class="ac-daterow">
        <input type="date" name="StartDate" id="StartDate" value="{start_date}" required>
        <span class="ac-datesep">to</span>
        <input type="date" name="EndDate" id="EndDate" value="{end_date}" required>
      </div>
      <div class="ac-chiprow ac-no-print">{preset_html}</div>
      <p class="ac-hint">Every meeting date in the range becomes a column, so keep the range to something printable. More than {max_cols} dates and only the most recent {max_cols} are shown.</p>
    </div>
  </fieldset>
  <fieldset>
    <legend>Report options</legend>
    <div class="ac-field">
      <label for="GroupDates">Group columns by</label>
      <select name="GroupDates" id="GroupDates">{group_dates_options}</select>
      <p class="ac-hint">Grouping by week keeps a long range readable &mdash; a full school year is about 40 week columns instead of every individual meeting date.</p>
    </div>
    <div class="ac-field">
      <label for="CountWho">Count who</label>
      <select name="CountWho" id="CountWho">{count_who_options}</select>
      <p class="ac-hint">Anything but "Everyone" filters every number on the report, and the Members/Leaders breakdown columns are dropped.</p>
    </div>
    <div class="ac-field">
      <label for="SortBy">Sort involvements by</label>
      <select name="SortBy" id="SortBy">{sort_options}</select>
    </div>
    <div class="ac-field">
      <label class="ac-checklabel"><input type="checkbox" name="HideEmpty" value="1"{hide_empty_checked}> Hide involvements that held no meeting in this range</label>
    </div>
  </fieldset>
  <button type="submit">Build report</button>
</form>
</div>
</div>
</div>""".format(
            css=scope_css(BUILDER_CSS),
            root_id=ROOT_ID,
            steps=steps_html(3),
            prog_id=selected_program.Id,
            div_id=selected_division.Id,
            div_name=esc(selected_division.Name),
            count=len(org_rows),
            checkbox_html=checkbox_html,
            start_date=esc(start_date),
            end_date=esc(end_date),
            preset_html=preset_html,
            max_cols=MAX_DATE_COLUMNS,
            group_dates_options=options_html(GROUP_DATES_OPTIONS, group_dates),
            count_who_options=options_html(COUNT_WHO_OPTIONS, count_who),
            sort_options=options_html(SORT_BY_OPTIONS, sort_by),
            hide_empty_checked=' checked' if hide_empty else '',
        )
    )

    # Plain (unformatted) JS -- kept out of the .format() above so its braces
    # don't have to be doubled and mis-escaped.
    print("""<script>
(function () {
  var form = document.getElementById('pickerForm');
  var search = document.getElementById('orgSearch');
  var searchClear = document.getElementById('orgSearchClear');
  var noResults = document.getElementById('noResults');
  var listMeta = document.getElementById('listMeta');
  var labels = document.querySelectorAll('.ac-orgcb');

  function applySearch() {
    var term = (search.value || '').trim().toLowerCase();
    var shown = 0;
    for (var i = 0; i < labels.length; i++) {
      var match = !term || labels[i].getAttribute('data-name').indexOf(term) !== -1;
      if (match) { labels[i].classList.remove('ac-hide'); shown++; }
      else { labels[i].classList.add('ac-hide'); }
    }
    noResults.classList.toggle('ac-hide', shown !== 0);
    searchClear.hidden = !term;
    updateMeta(shown, term);
  }

  // A search only hides rows -- it never unchecks one. Anything already
  // checked stays selected and still lands on the report, so the count line
  // calls out hidden selections rather than letting them disappear quietly.
  function updateMeta(shown, term) {
    var checked = document.querySelectorAll('.ac-orgcheck:checked');
    var hiddenChecked = 0;
    for (var i = 0; i < checked.length; i++) {
      if (checked[i].parentNode.classList.contains('ac-hide')) { hiddenChecked++; }
    }
    var parts = [];
    if (term) { parts.push('Showing <strong>' + shown + '</strong> of ' + labels.length); }
    if (checked.length) { parts.push('<strong>' + checked.length + '</strong> selected'); }
    if (hiddenChecked > 0) {
      parts.push(hiddenChecked + ' of them hidden by the search (still included)');
    }
    listMeta.innerHTML = parts.join(' &middot; ');
  }

  search.addEventListener('input', applySearch);
  search.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.keyCode === 13) { e.preventDefault(); }  // don't submit mid-search
  });
  searchClear.addEventListener('click', function () {
    search.value = '';
    applySearch();
    search.focus();
  });

  // "Select all SHOWN" is scoped to the current search on purpose: it is how
  // you grab "every 6th grade class" without hand-ticking twelve boxes.
  // "Clear all" is deliberately NOT scoped -- it clears hidden selections
  // too, so it always means what it says.
  document.getElementById('selectAll').addEventListener('click', function () {
    for (var i = 0; i < labels.length; i++) {
      if (!labels[i].classList.contains('ac-hide')) {
        labels[i].querySelector('.ac-orgcheck').checked = true;
      }
    }
    applySearch();
  });
  document.getElementById('clearAll').addEventListener('click', function () {
    var all = document.querySelectorAll('.ac-orgcheck');
    for (var i = 0; i < all.length; i++) { all[i].checked = false; }
    applySearch();
  });

  var boxes = document.querySelectorAll('.ac-orgcheck');
  for (var i = 0; i < boxes.length; i++) {
    boxes[i].addEventListener('change', applySearch);
  }

  // ---- Date range presets --------------------------------------------
  var startInput = document.getElementById('StartDate');
  var endInput = document.getElementById('EndDate');
  var presets = document.querySelectorAll('.ac-preset');

  function iso(d) {
    return d.getFullYear() + '-' +
           ('0' + (d.getMonth() + 1)).slice(-2) + '-' +
           ('0' + d.getDate()).slice(-2);
  }
  function markActivePreset() {
    for (var i = 0; i < presets.length; i++) {
      var weeks = parseInt(presets[i].getAttribute('data-weeks'), 10);
      var end = new Date(); end.setHours(12, 0, 0, 0);
      var start = new Date(end.getTime() - weeks * 7 * 86400000);
      var on = (startInput.value === iso(start) && endInput.value === iso(end));
      presets[i].classList.toggle('ac-chipon', on);
    }
  }
  for (var p = 0; p < presets.length; p++) {
    presets[p].addEventListener('click', function () {
      var weeks = parseInt(this.getAttribute('data-weeks'), 10);
      var end = new Date(); end.setHours(12, 0, 0, 0);
      var start = new Date(end.getTime() - weeks * 7 * 86400000);
      startInput.value = iso(start);
      endInput.value = iso(end);
      markActivePreset();
    });
  }
  startInput.addEventListener('change', markActivePreset);
  endInput.addEventListener('change', markActivePreset);
  markActivePreset();

  applySearch();

  form.addEventListener('submit', function (e) {
    var checked = [];
    var sel = document.querySelectorAll('.ac-orgcheck:checked');
    for (var i = 0; i < sel.length; i++) { checked.push(sel[i].value); }
    if (checked.length === 0) {
      alert('Pick at least one involvement.');
      e.preventDefault();
      return;
    }
    if (startInput.value && endInput.value && startInput.value > endInput.value) {
      alert('The start date is after the end date.');
      e.preventDefault();
      return;
    }
    document.getElementById('OrgIdsField').value = checked.join(',');
  });
})();
</script>
</body>
</html>""")


# ============================================================
# Row-level security: who is looking at this?
# ============================================================
CURRENT_USER_ID = to_int(getattr(model, "UserPeopleId", None))
IS_ADMIN = CURRENT_USER_ID in ADMIN_BYPASS_PEOPLE_IDS

# Trailing slash stripped so "{host}/Org/1" never becomes "//Org/1"; an
# absent CmsHost leaves "" and the deep links fall back to host-relative.
TP_HOST = str(getattr(model, "CmsHost", "") or "").rstrip("/")

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
        step_title="Choose a Ministry -- Attendance Counts",
        heading="Choose a Ministry",
        meta_text="{0} ministry program(s) available. Pick one to see its divisions.".format(
            len(program_rows)
        ),
        select_name="ProgId",
        options_html=options_html,
        step_num=1,
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
        render_message(
            title="No Divisions -- Attendance Counts",
            heading="No divisions found",
            body_html="<p class=\"ac-hint\">{0} has no divisions you have access to.</p>".format(
                esc(selected_program.Name)
            ),
        )

    elif selected_division is None:
        options_html = "".join(
            '<option value="{id}">{name}</option>'.format(id=r.Id, name=esc(r.Name))
            for r in division_rows
        )
        render_picker(
            step_title="Choose a Division -- Attendance Counts",
            heading="Choose a Division",
            meta_text="{0} division(s) under {1}.".format(
                len(division_rows), esc(selected_program.Name)
            ),
            select_name="DivId",
            options_html=options_html,
            hidden_fields={"ProgId": selected_program.Id},
            back_href="?",
            step_num=2,
        )

    else:
        # ============================================================
        # Stage 3: pick involvements + the date range and options.
        # Organizations -> DivOrg is one-to-many, so EXISTS rather than a
        # plain JOIN, or an org sitting in several divisions duplicates its
        # row and its attendance would be double-counted (DB_REFERENCE.md).
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
        org_names = dict((r.OrganizationId, r.OrganizationName) for r in org_rows)

        requested_org_ids_raw = str(getattr(model.Data, "OrgIds", "") or "")
        requested_org_ids = [to_int(x) for x in requested_org_ids_raw.split(",") if x.strip()]
        # Dedupe while preserving order -- a hand-edited URL repeating an id
        # would otherwise produce two identical rows and double the TOTAL.
        selected_org_ids = []
        for oid in requested_org_ids:
            if oid in org_names and oid not in selected_org_ids:
                selected_org_ids.append(oid)

        default_start, default_end = default_range()
        start_date = valid_date(getattr(model.Data, "StartDate", ""), default_start)
        end_date = valid_date(getattr(model.Data, "EndDate", ""), default_end)
        if start_date > end_date:  # ISO strings sort chronologically
            start_date, end_date = end_date, start_date
        count_who = valid_count_who(str(getattr(model.Data, "CountWho", "") or ""))
        sort_by = valid_sort_by(str(getattr(model.Data, "SortBy", "") or ""))
        group_dates = valid_group_dates(str(getattr(model.Data, "GroupDates", "") or ""))
        hide_empty = str(getattr(model.Data, "HideEmpty", "") or "") == "1"

        if not selected_org_ids:
            render_org_and_options_picker(
                org_rows, selected_program, selected_division,
                start_date, end_date, count_who, sort_by, hide_empty, group_dates,
            )

        else:
            # ============================================================
            # Stage 4: build the counts grid.
            # ============================================================
            org_ids_str = ",".join(str(oid) for oid in selected_org_ids)

            # Which dates each selected org actually HELD a meeting on.
            # Needed per-org, not just as a union, so a cell can tell "met,
            # nobody marked present" (a 0 worth chasing) apart from "didn't
            # meet that day" (nothing to chase). Canceled/DidNotMeet
            # meetings are excluded per DB_REFERENCE.md's rollup pattern.
            # MeetingId comes back too, so each cell can deep-link to the
            # meeting it summarizes. An org can hold SEVERAL meetings on one
            # date (per DB_REFERENCE.md, the PS Welcome Team had three on
            # 2026-08-16) -- those all sum into one cell, so the cell keeps
            # the whole list and only links to a specific meeting when there
            # is exactly one to link to.
            sql_meetings = """
            SELECT DISTINCT
                m.OrganizationId,
                m.MeetingId,
                CAST(m.MeetingDate AS DATE) AS MeetingDate
            FROM dbo.Meetings m
            WHERE m.OrganizationId IN ({org_ids})
              AND ISNULL(m.Canceled, 0) = 0
              AND ISNULL(m.DidNotMeet, 0) = 0
              AND CAST(m.MeetingDate AS DATE) BETWEEN '{start}' AND '{end}'
            ORDER BY MeetingDate
            """.format(org_ids=org_ids_str, start=start_date, end=end_date)

            # A "column" is a meeting date, or a week -- period_key() is the
            # only place that differs, so everything below works on opaque
            # keys that still sort chronologically (both are ISO dates).
            held = {}          # OrgId -> set of column keys it met in
            meeting_ids = {}   # (OrgId, column key) -> [MeetingId, ...]
            all_cols = set()
            for r in q.QuerySql(sql_meetings):
                pk = period_key(normalize_date(r.MeetingDate), group_dates)
                held.setdefault(r.OrganizationId, set()).add(pk)
                meeting_ids.setdefault((r.OrganizationId, pk), []).append(r.MeetingId)
                all_cols.add(pk)

            # The cap is applied AFTER grouping, so switching to weeks
            # genuinely buys columns back rather than trimming to 60 dates
            # and then collapsing those into a handful of weeks.
            columns = sorted(all_cols)
            truncated_from = 0
            if len(columns) > MAX_DATE_COLUMNS:
                truncated_from = len(columns)
                columns = columns[-MAX_DATE_COLUMNS:]  # keep the most recent
                keep = set(columns)
                for oid in list(held.keys()):
                    held[oid] = held[oid] & keep

            col_index = dict((c, i) for i, c in enumerate(columns))

            if not columns:
                render_message(
                    title="No Meetings -- Attendance Counts",
                    heading="No meetings in that date range",
                    body_html=(
                        '<p class="ac-hint">None of the {n} selected involvement(s) held a '
                        'meeting between {start} and {end} (canceled and did-not-meet '
                        'meetings are excluded). Go back and widen the range.</p>'
                    ).format(
                        n=len(selected_org_ids),
                        start=esc(fmt_long_date(start_date)),
                        end=esc(fmt_long_date(end_date)),
                    ),
                    back_href=("?ProgId={0}&DivId={1}&StartDate={2}&EndDate={3}"
                               "&CountWho={4}&SortBy={5}&GroupDates={6}{7}").format(
                        selected_program.Id, selected_division.Id, start_date, end_date,
                        count_who, sort_by, group_dates,
                        "&HideEmpty=1" if hide_empty else "",
                    ),
                )

            else:
                # Per DB_REFERENCE.md: require AttendanceFlag = 1 and
                # defensively exclude NoShow = 1 -- the same rule
                # student-contact-export/SM_StudentContactExport.py uses.
                #
                # Grouped by (org, date, member type) rather than fetching
                # one row per attendance record: a whole division over a
                # quarter is tens of thousands of Attend rows, and nothing
                # here needs a person's identity. Grouping by date also
                # means an org that held several meetings on one date sums
                # them into that date's cell, which is the behavior
                # DB_REFERENCE.md calls for.
                #
                # A person attending twice on the same date (two meetings of
                # the same org) is therefore counted twice -- these are
                # attendance VISITS, not distinct people. The report says so.
                sql_counts = """
                SELECT
                    a.OrganizationId,
                    MeetingDate = CAST(a.MeetingDate AS DATE),
                    MemberTypeId = ISNULL(a.MemberTypeId, 0),
                    Cnt = COUNT(*)
                FROM dbo.Attend a
                JOIN dbo.Meetings m ON m.MeetingId = a.MeetingId
                WHERE a.OrganizationId IN ({org_ids})
                  AND a.AttendanceFlag = 1
                  AND ISNULL(a.NoShow, 0) = 0
                  AND ISNULL(m.Canceled, 0) = 0
                  AND ISNULL(m.DidNotMeet, 0) = 0
                  AND CAST(a.MeetingDate AS DATE) BETWEEN '{start}' AND '{end}'
                GROUP BY a.OrganizationId, CAST(a.MeetingDate AS DATE), ISNULL(a.MemberTypeId, 0)
                """.format(org_ids=org_ids_str, start=start_date, end=end_date)

                # counts[oid][date] -> {'member': n, 'leader': n, 'other': n}
                counts = {}
                other_type_ids = set()
                for r in q.QuerySql(sql_counts):
                    d = period_key(normalize_date(r.MeetingDate), group_dates)
                    if d not in col_index:
                        continue  # outside the (possibly truncated) columns
                    bucket = bucket_for(r.MemberTypeId)
                    if bucket == BUCKET_OTHER:
                        other_type_ids.add(r.MemberTypeId)
                    if count_who != "all" and bucket != count_who:
                        continue
                    cell = counts.setdefault(r.OrganizationId, {}).setdefault(
                        d, {"member": 0, "leader": 0, BUCKET_OTHER: 0}
                    )
                    cell[bucket] = cell[bucket] + r.Cnt

                show_breakdown = (count_who == "all")
                # Only surface the Other column when it actually holds
                # something -- otherwise every report grows a column of
                # zeros to explain a case that didn't happen.
                other_total = 0
                for oid in counts:
                    for d in counts[oid]:
                        other_total += counts[oid][d][BUCKET_OTHER]
                show_other = show_breakdown and other_total > 0

                # ---- Assemble one row per selected involvement ----------
                rows = []
                for oid in selected_org_ids:
                    org_cols = held.get(oid, set())
                    per_date = counts.get(oid, {})
                    cells, total, members, leaders, others = [], 0, 0, 0, 0
                    for d in columns:
                        if d not in org_cols:
                            cells.append(None)  # didn't meet -- not a zero
                            continue
                        c = per_date.get(d, {"member": 0, "leader": 0, BUCKET_OTHER: 0})
                        n = c["member"] + c["leader"] + c[BUCKET_OTHER]
                        cells.append(n)
                        total += n
                        members += c["member"]
                        leaders += c["leader"]
                        others += c[BUCKET_OTHER]
                    rows.append({
                        "oid": oid,
                        "name": org_names.get(oid, "Organization {0}".format(oid)),
                        "cells": cells,
                        # In date mode this is meeting dates; in week mode,
                        # weeks met. Either way it is "columns this
                        # involvement is present in", which is what Avg
                        # divides by -- so Avg always means "average per
                        # column you are looking at".
                        "mtgs": len(org_cols),
                        "total": total,
                        "members": members,
                        "leaders": leaders,
                        "others": others,
                    })

                hidden_empty_count = 0
                if hide_empty:
                    before = len(rows)
                    rows = [r for r in rows if r["mtgs"] > 0]
                    hidden_empty_count = before - len(rows)

                if sort_by == "total":
                    # Name is the tiebreak so two involvements with equal
                    # totals don't swap order run to run.
                    rows.sort(key=lambda r: (-r["total"], r["name"].lower()))
                else:
                    rows.sort(key=lambda r: r["name"].lower())

                # ---- Column totals (the TOTAL row) ----------------------
                col_totals = []
                for i in range(len(columns)):
                    col = 0
                    any_met = False
                    for r in rows:
                        v = r["cells"][i]
                        if v is not None:
                            col += v
                            any_met = True
                    col_totals.append(col if any_met else None)

                grand_total = sum(r["total"] for r in rows)
                grand_members = sum(r["members"] for r in rows)
                grand_leaders = sum(r["leaders"] for r in rows)
                grand_others = sum(r["others"] for r in rows)
                # Dates where at least one still-shown involvement met --
                # after hide_empty, a date could belong only to a hidden row.
                active_cols = [i for i, v in enumerate(col_totals) if v is not None]

                peak_value, peak_col = 0, None
                for i in active_cols:
                    if col_totals[i] > peak_value:
                        peak_value, peak_col = col_totals[i], columns[i]

                # ---- Render --------------------------------------------
                by_week = (group_dates == "week")
                head_cells = "".join(
                    '<th title="{full}">{label}</th>'.format(
                        full=esc(col_title(c, group_dates)),
                        label=esc(col_header(c, group_dates)),
                    )
                    for c in columns
                )
                unit_head = "Weeks" if by_week else "Mtgs"
                unit_title = ("Weeks in which this involvement met"
                              if by_week else
                              "Meeting dates this involvement held in range")
                summary_heads = (
                    '<th class="ac-sep" title="{unit_title}">{unit_head}</th>'
                    '<th>Total</th>'
                    '<th title="Total divided by the {unit_word} it actually met">Avg</th>'
                ).format(unit_title=esc(unit_title), unit_head=unit_head,
                         unit_word="weeks" if by_week else "dates")
                if show_breakdown:
                    summary_heads += '<th class="ac-sep">Members</th><th>Leaders</th>'
                    if show_other:
                        summary_heads += '<th>Other</th>'

                def cell_html(oid, date_str, value):
                    """One date cell, deep-linked to what it summarizes.

                    The red 0 is linked too -- deliberately, since that is
                    the cell someone most needs to open: a meeting nobody
                    took attendance for."""
                    if value is None:
                        return '<td class="ac-none" title="No meeting held">&middot;</td>'
                    cls = ' class="ac-zero"' if value == 0 else ''
                    note = "Meeting held, nobody marked present. " if value == 0 else ""
                    when = "that week" if by_week else "on this date"
                    mids = meeting_ids.get((oid, date_str), [])
                    if len(mids) == 1:
                        return (
                            '<td{cls}><a href="{url}" target="_blank" rel="noopener" '
                            'title="{note}Open this meeting\'s attendance list in TouchPoint">{v}</a></td>'
                        ).format(
                            cls=cls, v=value, note=esc(note),
                            url=MEETING_URL.format(host=TP_HOST, meeting_id=mids[0]),
                        )
                    if len(mids) > 1:
                        # No single meeting to open, so say so and go to the
                        # involvement's Meetings tab rather than silently
                        # linking to whichever one sorted first.
                        return (
                            '<td class="ac-multi{extra}"><a href="{url}" target="_blank" rel="noopener" '
                            'title="{note}{n} meetings {when}, summed here. '
                            'Opens the involvement\'s Meetings tab.">{v}<sup>{n}</sup></a></td>'
                        ).format(
                            extra=" ac-zero" if value == 0 else "",
                            n=len(mids), v=value, note=esc(note), when=when,
                            url=ORG_MEETINGS_URL.format(host=TP_HOST, org_id=oid),
                        )
                    return '<td{cls}>{v}</td>'.format(cls=cls, v=value)  # meeting vanished mid-run

                body_rows = []
                for r in rows:
                    tds = []
                    for i, v in enumerate(r["cells"]):
                        tds.append(cell_html(r["oid"], columns[i], v))
                    tds.append('<td class="ac-sep">{0}</td>'.format(r["mtgs"]))
                    tds.append('<td class="ac-tot">{0}</td>'.format(r["total"]))
                    tds.append("<td>{0}</td>".format(fmt_avg(r["total"], r["mtgs"])))
                    if show_breakdown:
                        tds.append('<td class="ac-sep">{0}</td>'.format(r["members"]))
                        tds.append("<td>{0}</td>".format(r["leaders"]))
                        if show_other:
                            tds.append("<td>{0}</td>".format(r["others"]))
                    body_rows.append(
                        '<tr><td class="ac-name"><a href="{url}" target="_blank" rel="noopener" '
                        'title="Open this involvement in TouchPoint">{name}</a></td>{tds}</tr>'.format(
                            url=ORG_URL.format(host=TP_HOST, org_id=r["oid"]),
                            name=esc(r["name"]), tds="".join(tds)
                        )
                    )

                total_tds = []
                for v in col_totals:
                    total_tds.append("<td>{0}</td>".format("&middot;" if v is None else v))
                total_tds.append('<td class="ac-sep">{0}</td>'.format(len(active_cols)))
                total_tds.append("<td>{0}</td>".format(grand_total))
                total_tds.append("<td>{0}</td>".format(fmt_avg(grand_total, len(active_cols))))
                if show_breakdown:
                    total_tds.append('<td class="ac-sep">{0}</td>'.format(grand_members))
                    total_tds.append("<td>{0}</td>".format(grand_leaders))
                    if show_other:
                        total_tds.append("<td>{0}</td>".format(grand_others))
                total_row = '<tr class="ac-grand"><td class="ac-name">TOTAL</td>{0}</tr>'.format(
                    "".join(total_tds)
                )

                # No "every row was hidden" case to handle: `dates` is the
                # union of the selected involvements' meeting dates, so if
                # HideEmpty could empty the table, every selected
                # involvement held no meeting -- and that already rendered
                # the "no meetings in that date range" page above.
                table_html = (
                    '<div class="ac-tablewrap"><table id="countsTable"><thead><tr>'
                    '<th class="ac-name">Involvement</th>{head}{summary}</tr></thead>'
                    '<tbody>{body}{total}</tbody></table></div>'
                ).format(
                    head=head_cells,
                    summary=summary_heads,
                    body="".join(body_rows),
                    total=total_row,
                )

                stats = [
                    (str(len(rows)), "involvements"),
                    (str(len(active_cols)), "weeks with meetings" if by_week else "meeting dates"),
                    ("{0:,}".format(grand_total), "total attendance"),
                    (fmt_avg(grand_total, len(active_cols)),
                     "avg per week" if by_week else "avg per date"),
                ]
                if peak_col:
                    stats.append((
                        str(peak_value),
                        ("peak week &mdash; " if by_week else "peak &mdash; ")
                        + esc(fmt_col_header(peak_col)),
                    ))
                stats_html = "".join(
                    '<div class="ac-stat"><span class="ac-statval">{v}</span>'
                    '<span class="ac-statlbl">{l}</span></div>'.format(v=v, l=l)
                    for v, l in stats
                )

                notes = []
                if count_who != "all":
                    notes.append(
                        "Filtered to <strong>{0}</strong> &mdash; every number on this "
                        "report excludes everyone else.".format(
                            esc(COUNT_WHO_LABELS[count_who])
                        )
                    )
                notes.append(
                    "Counts are attendance <strong>visits</strong> from individually-marked "
                    "attendance records (<code>Attend</code>, present and not a no-show), not "
                    "the recorded <code>NumPresent</code> headcount the SM/CM dashboards use. "
                    "Someone attending two meetings of the same involvement on one date counts twice."
                )
                if by_week:
                    notes.append(
                        "Columns are <strong>weeks</strong> (Sunday&ndash;Saturday, labelled by "
                        "the Sunday). Every meeting an involvement held that week is summed "
                        "into one cell."
                    )
                notes.append(
                    "An involvement name opens it in TouchPoint; a number opens that "
                    "meeting's own attendance list. A number with a small superscript "
                    "means the involvement held that many meetings in that column and they "
                    "are summed here &mdash; there is no single meeting to open, so it goes "
                    "to the involvement's Meetings tab instead."
                )
                notes.append(
                    "A dim &middot; means that involvement held no meeting {0}. "
                    "A red <strong>0</strong> means it met and nobody was marked present."
                    .format("that week" if by_week else "that day")
                )
                if show_other:
                    labels_seen = ", ".join(
                        esc(member_type_label(t)) for t in sorted(other_type_ids)
                    )
                    notes.append(
                        "<strong>Other</strong> holds attendance by member types that are "
                        "neither Member nor Leader/Coach/Volunteer: {0}.".format(labels_seen)
                    )
                if hidden_empty_count:
                    notes.append(
                        "{0} selected involvement(s) held no meeting in this range and were "
                        "hidden.".format(hidden_empty_count)
                    )

                warn_html = ""
                if truncated_from:
                    warn_html = (
                        '<p class="ac-warn">That range covers <strong>{n}</strong> {unit}. '
                        'Showing the most recent {m} &mdash; narrow the range{alt} for the rest.</p>'
                    ).format(n=truncated_from, m=MAX_DATE_COLUMNS,
                             unit="weeks" if by_week else "meeting dates",
                             alt="" if by_week else " (or group the columns by week)")

                # CSV is built server-side rather than scraped out of the
                # DOM, so the export can't drift from the table or inherit
                # its HTML entities.
                csv_head = (["Involvement"]
                            + [("Week of " + c) if by_week else c for c in columns]
                            + [("Weeks" if by_week else "Meetings"), "Total", "Avg"])
                if show_breakdown:
                    csv_head += ["Members", "Leaders"]
                    if show_other:
                        csv_head += ["Other"]
                csv_lines = [csv_head]
                for r in rows:
                    line = [r["name"]]
                    line += ["" if v is None else str(v) for v in r["cells"]]
                    line += [str(r["mtgs"]), str(r["total"]),
                             fmt_avg(r["total"], r["mtgs"]).replace("&mdash;", "")]
                    if show_breakdown:
                        line += [str(r["members"]), str(r["leaders"])]
                        if show_other:
                            line += [str(r["others"])]
                    csv_lines.append(line)
                total_line = ["TOTAL"] + ["" if v is None else str(v) for v in col_totals]
                total_line += [str(len(active_cols)), str(grand_total),
                               fmt_avg(grand_total, len(active_cols)).replace("&mdash;", "")]
                if show_breakdown:
                    total_line += [str(grand_members), str(grand_leaders)]
                    if show_other:
                        total_line += [str(grand_others)]
                csv_lines.append(total_line)

                def csv_cell(v):
                    v = str(v)
                    if '"' in v or "," in v or "\n" in v:
                        return '"' + v.replace('"', '""') + '"'
                    return v

                csv_text = "\n".join(
                    ",".join(csv_cell(c) for c in line) for line in csv_lines
                )
                csv_name = "attendance-counts-{0}-{1}.csv".format(start_date, end_date)

                back_href = (
                    "?ProgId={prog}&DivId={div}&StartDate={start}&EndDate={end}"
                    "&CountWho={who}&SortBy={sort}&GroupDates={gd}{hide}"
                ).format(
                    prog=selected_program.Id, div=selected_division.Id,
                    start=start_date, end=end_date, who=count_who, sort=sort_by,
                    gd=group_dates, hide="&HideEmpty=1" if hide_empty else "",
                )

                print(
                    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Attendance Counts -- {div_name}</title>
<style>{css}</style>
</head>
<body>
<div id="{root_id}">
<div class="ac-bar">
  <div>
    <p class="ac-church">RockPointe Church</p>
    <h1>Attendance Counts</h1>
    <p class="ac-sub">{prog_name} &rsaquo; {div_name} &middot; {start_long} &ndash; {end_long}</p>
  </div>
  <div class="ac-btnrow ac-no-print">
    <button type="button" id="csvBtn">Export CSV</button>
    <button type="button" onclick="window.print()">Print</button>
  </div>
</div>
<div class="ac-wrap">
<p class="ac-back ac-no-print"><a href="{back_href}">&larr; Change involvements or dates</a></p>
<div class="ac-stats">{stats_html}</div>
{warn_html}
{table_html}
<p class="ac-note">{notes}</p>
</div>
</div>
<script>
(function () {{
  var csv = '{csv_js}';
  var btn = document.getElementById('csvBtn');
  if (!btn) {{ return; }}
  btn.addEventListener('click', function () {{
    var blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = '{csv_name}';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  }});
}})();
</script>
</body>
</html>""".format(
                        css=scope_css(REPORT_CSS),
                        root_id=ROOT_ID,
                        prog_name=esc(selected_program.Name),
                        div_name=esc(selected_division.Name),
                        start_long=esc(fmt_long_date(start_date)),
                        end_long=esc(fmt_long_date(end_date)),
                        back_href=back_href,
                        stats_html=stats_html,
                        warn_html=warn_html,
                        table_html=table_html,
                        notes=" ".join(notes),
                        csv_js=js_string(csv_text),
                        csv_name=csv_name,
                    )
                )
