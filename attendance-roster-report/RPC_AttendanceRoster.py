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
    ("subgroup", "Sub-Group"),
]
FIELD_KEYS = [k for k, _ in FIELD_OPTIONS]
FIELD_LABELS = dict(FIELD_OPTIONS)
DEFAULT_COL1 = "phone"
DEFAULT_COL2 = "email"

# How to split the roster into print sections/page breaks.
GROUP_BY_OPTIONS = [
    ("gender", "Gender (Men / Women sections)"),
    ("involvement", "Involvement (one section per selected class/org)"),
    ("subgroup", "Sub-Group (one section per sub-group)"),
    ("none", "No grouping -- one combined list"),
]
GROUP_BY_KEYS = [k for k, _ in GROUP_BY_OPTIONS]
DEFAULT_GROUP_BY = "gender"

# Roster sort order. "default" is the original behavior (already applied by
# sql_roster's ORDER BY: Involvement, then Leader-before-Member, then name).
# "subgroup" re-sorts in Python by sub-group label, keeping that original
# ordering as the tiebreak (Python's sort is stable), so a sub-group's
# members still read Leaders-first and alphabetically within the group.
SORT_BY_OPTIONS = [
    ("default", "Default (Leaders first, then name)"),
    ("subgroup", "Sub-Group, then the default order"),
]
SORT_BY_KEYS = [k for k, _ in SORT_BY_OPTIONS]
DEFAULT_SORT_BY = "default"

# TouchPoint's involvement-level "SubGroups" feature is dbo.MemberTags
# (one row per sub-group defined on an involvement) + dbo.OrgMemMemTags
# (composite PK OrgId+PeopleId+MemberTagId, linking a member to one or more
# of them) -- confirmed at RPC in DB_REFERENCE.md, ~7,064 / ~50,601 rows,
# so this is a well-used feature here, not a speculative join.
#
# A person can hold MORE THAN ONE sub-group in the same involvement. That
# shapes three behaviors below:
#   - as a column, their sub-groups are comma-joined into one cell;
#   - as a page-break grouping, they are printed once under EACH of their
#     sub-groups (so a per-sub-group printout handed to a table leader is
#     complete), which means section counts can sum to more than the
#     roster's total member count;
#   - as a sort, they sort by their comma-joined label.
# Members with no sub-group collect into a final section, always last.
NO_SUBGROUP_LABEL = "(No sub-group)"

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
# RPC brand styling
# ============================================================
# Main RockPointe Church palette (the default per Comms -- ministry-specific
# sheets are only for artifacts branded to that ministry's audience, which a
# church-wide staff tool is not):
#   Navy #0C2340 (primary)   Sunshine Yellow #FFD242 (accent)
#   Space Blue #183D5F       Curious Blue #1D6A94
#   Steel Blue #4580B9       Baby Blue #76C2E3       Light Gray #D1D3D4
# Brand fonts are Bebas (titles) / Montserrat (subtitles) / HelveticaNeue
# (body). TouchPoint-hosted pages can't load webfonts reliably, so these are
# closest-safe stacks and the hex values carry the brand.
NAVY = "#0C2340"
YELLOW = "#FFD242"
SPACE_BLUE = "#183D5F"
CURIOUS_BLUE = "#1D6A94"
LIGHT_GRAY = "#D1D3D4"

TITLE_FONT = '"Bebas Neue", Impact, "Arial Narrow", Haettenschweiler, sans-serif'
SUBTITLE_FONT = 'Montserrat, "Segoe UI", Tahoma, sans-serif'
BODY_FONT = '-apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif'

# Used by the interactive builder screens (stages 1-3). Passed into the page
# templates as a .format() argument rather than living inside them, so its
# braces don't need doubling.
BUILDER_CSS = """
  *, *::before, *::after { box-sizing: border-box; }
  body { font-family: %(body)s; margin: 0; padding: 0 0 40px; color: #222;
         background: #f7f9fb; -webkit-font-smoothing: antialiased; }
  .rr-bar { background: %(navy)s; border-bottom: 4px solid %(yellow)s;
         padding: 26px 24px 22px; margin: 12px 0 0; overflow: visible; }
  .rr-bar .rr-church { font-family: %(subtitle)s; font-size: 11px; letter-spacing: 0.14em;
                 text-transform: uppercase; color: %(yellow)s; margin: 0 0 6px; font-weight: 600;
                 line-height: 1; }
  .rr-bar h1 { font-family: %(title)s; font-size: 30px; line-height: 1.15; letter-spacing: 0.03em;
            color: #fff; margin: 0; padding: 0; font-weight: normal; text-transform: uppercase; }
  .rr-wrap { max-width: 720px; margin: 0 auto; padding: 22px 24px 0; }
  .rr-steps { font-family: %(subtitle)s; font-size: 11px; letter-spacing: 0.10em;
           text-transform: uppercase; color: %(curious)s; font-weight: 600; margin: 0 0 14px; }
  .rr-steps .rr-on { color: %(navy)s; }
  .rr-steps .rr-sep { color: %(gray)s; padding: 0 6px; }
  .rr-meta { color: #55606b; font-size: 13px; margin: 0 0 18px; line-height: 1.5; }
  .rr-back { margin: 0 0 14px; font-size: 13px; }
  a { color: %(curious)s; }
  a:hover { color: %(navy)s; }
  .rr-card { background: #fff; border: 1px solid #e3e8ee; border-radius: 6px;
          padding: 22px 24px 14px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(12,35,64,0.05); }
  fieldset { border: 0; border-top: 1px solid #e3e8ee; padding: 22px 0 0; margin: 24px 0 4px; }
  fieldset.rr-first { border-top: 0; padding-top: 0; margin-top: 0; }
  legend { font-family: %(subtitle)s; font-size: 11px; font-weight: 700; color: %(navy)s;
           padding: 0; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.09em; }
  .rr-field { margin-bottom: 16px; }
  label { display: block; font-size: 13px; color: #3d4753; margin-bottom: 5px; font-weight: 600; }
  label.rr-checklabel { font-weight: normal; color: #222; }
  .rr-orglist { border: 1px solid %(gray)s; border-radius: 4px; padding: 6px 12px;
             max-height: 320px; overflow-y: auto; background: #fff; }
  .rr-orgcb { display: block; font-size: 14px; color: #222; padding: 5px 0;
           font-weight: normal; border-bottom: 1px solid #f0f3f6; }
  .rr-orgcb:last-child { border-bottom: 0; }
  .rr-cnt { color: #6b7683; font-size: 12px; }
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
  .rr-hint { font-size: 12px; color: #6b7683; margin: 8px 0 0; line-height: 1.5; }
  .rr-searchrow { position: relative; margin-bottom: 8px; }
  .rr-searchrow input { width: 100%%; max-width: none; padding: 8px 34px 8px 10px; }
  .rr-searchrow .rr-clear { position: absolute; right: 8px; top: 50%%; transform: translateY(-50%%);
            border: 0; background: none; color: #8a949e; font-size: 18px; line-height: 1;
            padding: 2px 4px; cursor: pointer; margin: 0; border-radius: 3px; }
  .rr-searchrow .rr-clear:hover { color: %(navy)s; background: #eef2f6; }
  .rr-listmeta { font-size: 12px; color: #6b7683; margin: 7px 0 0; }
  .rr-listmeta strong { color: %(navy)s; }
  .rr-noresults { font-size: 13px; color: #6b7683; padding: 14px 2px; font-style: italic; }
  .rr-status { font-size: 13px; margin: 14px 0 4px; padding: 9px 12px; border-radius: 4px;
            background: #eef4f9; border-left: 4px solid %(steel)s; color: %(space)s; line-height: 1.5; }
  .rr-status.rr-off { background: #f4f5f6; border-left-color: %(gray)s; color: #63707d; }
  select option:disabled { color: #a6adb5; }
  .rr-hide { display: none !important; }
""" % {
    "body": BODY_FONT, "title": TITLE_FONT, "subtitle": SUBTITLE_FONT,
    "navy": NAVY, "yellow": YELLOW, "space": SPACE_BLUE, "curious": CURIOUS_BLUE,
    "steel": "#4580B9", "gray": LIGHT_GRAY,
}

# Stage 4 is a print artifact, so it stays mostly white -- brand colors are
# used for rules/headings rather than filled backgrounds, to avoid burning
# toner on a landscape roster that gets printed per section.
ROSTER_CSS = """
  @media print {
    @page { size: landscape; margin: 0.4in; }
    .rr-page-break { page-break-before: always; }
    .rr-no-print { display: none; }
    body { background: #fff; }
  }
  body { font-family: %(body)s; margin: 20px; color: #222; background: #fff; }
  h1 { font-family: %(title)s; font-size: 26px; font-weight: normal; text-transform: uppercase;
       letter-spacing: 0.02em; color: %(navy)s; margin: 0 0 4px;
       border-bottom: 3px solid %(yellow)s; padding-bottom: 6px; }
  .rr-church { font-family: %(subtitle)s; font-size: 10px; letter-spacing: 0.14em;
            text-transform: uppercase; color: %(curious)s; margin: 0 0 2px; font-weight: 600; }
  .rr-meta { color: #55606b; font-size: 13px; margin: 8px 0 16px; }
  h2 { font-family: %(subtitle)s; font-size: 15px; font-weight: 700; color: %(navy)s;
       margin-top: 24px; margin-bottom: 0; text-transform: uppercase; letter-spacing: 0.05em; }
  .rr-count { font-weight: normal; color: #6b7683; font-size: 13px; letter-spacing: 0; text-transform: none; }
  table { border-collapse: collapse; width: 100%%; margin-top: 8px; }
  thead { display: table-header-group; }
  tr { page-break-inside: avoid; }
  th, td { border: 1px solid %(gray)s; padding: 5px 6px; font-size: 12px;
           text-align: left; white-space: nowrap; }
  th { background: #eef2f6; color: %(navy)s; font-family: %(subtitle)s;
       font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }
  th.rr-mark, td.rr-mark { text-align: center; width: 32px; }
  th.rr-total, td.rr-total { text-align: center; font-weight: bold; background: #fafbfc; }
  /* Each grouped section is its own <table>, so browsers would otherwise size
     the leading columns independently and the sections wouldn't line up
     page-to-page. These are suggestions, not caps -- a long name still
     widens its column. */
  th:nth-child(1), td:nth-child(1) { width: 190px; }
  th:nth-child(2), td:nth-child(2) { width: 80px; }
  th:nth-child(3), td:nth-child(3) { width: 110px; }
  a { color: %(curious)s; }
""" % {
    "body": BODY_FONT, "title": TITLE_FONT, "subtitle": SUBTITLE_FONT,
    "navy": NAVY, "yellow": YELLOW, "curious": CURIOUS_BLUE, "gray": LIGHT_GRAY,
}


# The script's output is injected INTO a TouchPoint page that brings its own
# (Bootstrap-derived) stylesheet, so generic class names like .bar, .card,
# .status, .field and .hint are live collision risks -- TouchPoint's rules can
# silently restyle or hide parts of this page, which is exactly what happened
# to the header's eyebrow line on the first live run. Rather than renaming
# every class, each rule is scoped under a single wrapper id at render time:
# an id+class selector (1,1,0) outranks any plain class selector TouchPoint
# defines, and `body` rules are retargeted at the wrapper so this page stops
# trying to restyle TouchPoint's own <body>.
ROOT_ID = "rpcAttendanceRoster"


def scope_css(css, root="#" + ROOT_ID):
    """Prefix every selector in `css` with `root`; retarget `body` to it."""
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
    """Breadcrumb of the builder's three choose-steps, current one bolded."""
    labels = ["1. Ministry", "2. Division", "3. Involvement + options"]
    parts = []
    for i, label in enumerate(labels, start=1):
        cls = ' class="rr-on"' if i == current else ""
        parts.append("<span{0}>{1}</span>".format(cls, label))
    return '<span class="rr-sep">&rsaquo;</span>'.join(parts)


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


def valid_sort_by(value):
    return value if value in SORT_BY_KEYS else DEFAULT_SORT_BY


def valid_since_date(value):
    # Strict YYYY-MM-DD only (what an HTML5 date input submits) -- anything
    # else (blank, malformed, a paste gone wrong) falls back to "no filter"
    # rather than being trusted into SQL.
    value = str(value or "").strip()
    return value if re.match(r"^\d{4}-\d{2}-\d{2}$", value) else DEFAULT_SINCE_DATE


def field_value(key, p, sg_text=""):
    """Display string for configurable-column field `key` on roster row p.

    sg_text is the caller-computed, comma-joined sub-group label for this
    (person, involvement) pair -- sub-groups live in their own lookup dict
    rather than on the roster row itself, since one member can hold several.
    """
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
    if key == "subgroup":
        return sg_text or ""
    return ""  # "blank", or an unrecognized key -- render as an empty cell


def render_picker(step_title, heading, meta_text, select_name, options_html, hidden_fields=None, back_href=None, step_num=1):
    hidden_html = "".join(
        '<input type="hidden" name="{0}" value="{1}">'.format(k, v)
        for k, v in (hidden_fields or {}).items()
    )
    back_html = (
        '<p class="rr-back"><a href="{0}">&larr; Back</a></p>'.format(back_href)
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
<div class="rr-bar">
  <p class="rr-church">RockPointe Church</p>
  <h1>Attendance Roster</h1>
</div>
<div class="rr-wrap">
{back_html}
<p class="rr-steps">{steps}</p>
<div class="rr-card">
  <p class="rr-meta">{meta_text}</p>
  <form method="get">
    {hidden_html}
    <div class="rr-field">
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


def render_org_and_options_picker(org_rows, selected_program, selected_division, col1, col2,
                                  group_by, sort_by, since_date, exclude_zero, subgroup_counts):
    """Stage 3: check involvement(s), then choose how the roster prints.

    Sub-group availability is per-involvement, and this stage renders BEFORE
    anything is checked -- so every org's sub-group count is handed to the
    browser as a small JS map and the three sub-group choices below
    enable/disable live as boxes are ticked, with a status line saying why.
    Nothing is hidden: an unavailable choice stays visible but disabled and
    labelled, so the option never silently appears and disappears.

    This is a convenience layer only. valid_group_by()/valid_sort_by() plus
    the stage-4 no-sub-groups fallback still backstop it server-side, so a
    hand-edited URL or a browser with JS off produces a sane roster instead
    of an error.
    """
    # No pre-checking: this stage is only ever reached with zero validly-
    # selected orgs (any valid OrgIds jump straight to stage 4), so there's
    # never a prior selection worth restoring here.
    def org_checkbox(r):
        n = subgroup_counts.get(r.OrganizationId, 0)
        sg_note = (
            ' &middot; {0} sub-group{1}'.format(n, "" if n == 1 else "s") if n else ""
        )
        return (
            '<label class="rr-orgcb" data-name="{search_name}"><input type="checkbox" class="rr-orgcheck" value="{oid}" '
            'data-subgroups="{sg}"> {name} <span class="rr-cnt">({count} member{plural}{sg_note})</span></label>'
        ).format(
            oid=r.OrganizationId,
            sg=n,
            search_name=esc(str(r.OrganizationName or "").lower()).replace('"', "&quot;"),
            name=esc(r.OrganizationName),
            count=r.MemberCount,
            plural="" if r.MemberCount == 1 else "s",
            sg_note=sg_note,
        )

    checkbox_html = "".join(org_checkbox(r) for r in org_rows)

    def options_html(pairs, selected_key):
        return "".join(
            '<option value="{0}"{1}{2}>{3}</option>'.format(
                key,
                ' selected' if key == selected_key else '',
                ' data-needs-subgroups="1"' if key == "subgroup" else '',
                esc(label),
            )
            for key, label in pairs
        )

    # Map of OrganizationId -> sub-group count, for the live JS check.
    subgroup_map_js = "{" + ",".join(
        '"{0}":{1}'.format(r.OrganizationId, subgroup_counts.get(r.OrganizationId, 0))
        for r in org_rows
    ) + "}"

    print(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Choose Involvement(s) -- Roster Report</title>
<style>{css}</style>
</head>
<body>
<div id="{root_id}">
<div class="rr-bar">
  <p class="rr-church">RockPointe Church</p>
  <h1>Attendance Roster</h1>
</div>
<div class="rr-wrap">
<p class="rr-back"><a href="?ProgId={prog_id}">&larr; Back</a></p>
<p class="rr-steps">{steps}</p>
<div class="rr-card">
<p class="rr-meta">{count} active involvement(s) in {div_name}.</p>
<form method="get" id="pickerForm">
  <input type="hidden" name="ProgId" value="{prog_id}">
  <input type="hidden" name="DivId" value="{div_id}">
  <input type="hidden" name="OrgIds" id="OrgIdsField" value="">
  <fieldset class="rr-first">
    <legend>Involvements</legend>
    <div class="rr-searchrow">
      <input type="search" id="orgSearch" autocomplete="off"
             placeholder="Search involvements by name...">
      <button type="button" class="rr-clear" id="orgSearchClear" title="Clear search" hidden>&times;</button>
    </div>
    <div class="rr-orglist" id="orgList">{checkbox_html}<p class="rr-noresults" id="noResults" hidden>No involvements match that search.</p></div>
    <p class="rr-listmeta" id="listMeta"></p>
    <p class="rr-hint">Check one or more. Only combine involvements that share the same meeting schedule &mdash; the attendance grid uses one shared set of dates.</p>
    <p class="rr-status rr-off" id="sgStatus">Check an involvement above to see whether it has sub-groups.</p>
  </fieldset>
  <fieldset>
    <legend>Print options</legend>
    <div class="rr-field">
      <label for="Col1">Column 1 (after Total)</label>
      <select name="Col1" id="Col1">{col1_options}</select>
    </div>
    <div class="rr-field">
      <label for="Col2">Column 2 (after Total)</label>
      <select name="Col2" id="Col2">{col2_options}</select>
    </div>
    <div class="rr-field">
      <label for="GroupBy">Group roster by (starts a new printed page per section)</label>
      <select name="GroupBy" id="GroupBy">{group_options}</select>
    </div>
    <div class="rr-field">
      <label for="SortBy">Sort members by</label>
      <select name="SortBy" id="SortBy">{sort_options}</select>
    </div>
    <div class="rr-field">
      <label for="SinceDate">Attendance since (optional -- leave blank for full history)</label>
      <input type="date" name="SinceDate" id="SinceDate" value="{since_date}">
    </div>
    <div class="rr-field">
      <label class="rr-checklabel"><input type="checkbox" name="ExcludeZero" value="1"{exclude_zero_checked}> Exclude members with zero attendance (within the date range above, if set)</label>
    </div>
  </fieldset>
  <button type="submit">Build roster</button>
</form>
</div>
</div>
</div>
<script>var ORG_SUBGROUPS = {subgroup_map_js};</script>""".format(
            css=scope_css(BUILDER_CSS),
            root_id=ROOT_ID,
            steps=steps_html(3),
            prog_id=selected_program.Id,
            div_id=selected_division.Id,
            div_name=esc(selected_division.Name),
            count=len(org_rows),
            checkbox_html=checkbox_html,
            col1_options=options_html(FIELD_OPTIONS, col1),
            col2_options=options_html(FIELD_OPTIONS, col2),
            group_options=options_html(GROUP_BY_OPTIONS, group_by),
            sort_options=options_html(SORT_BY_OPTIONS, sort_by),
            since_date=esc(since_date),
            exclude_zero_checked=' checked' if exclude_zero else '',
            subgroup_map_js=subgroup_map_js,
        )
    )

    # Plain (unformatted) JS block -- kept out of the .format() above so its
    # braces don't have to be doubled and mis-escaped.
    print("""<script>
(function () {
  var form = document.getElementById('pickerForm');
  var status = document.getElementById('sgStatus');
  var selects = ['Col1', 'Col2', 'GroupBy', 'SortBy'].map(function (id) {
    return document.getElementById(id);
  });

  function subgroupOption(sel) {
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].getAttribute('data-needs-subgroups') === '1') { return sel.options[i]; }
    }
    return null;
  }

  // Remember each sub-group option's real label so it can be restored when
  // it becomes available again.
  selects.forEach(function (sel) {
    var opt = subgroupOption(sel);
    if (opt) { opt.setAttribute('data-label', opt.text); }
  });

  function refresh() {
    var boxes = document.querySelectorAll('.rr-orgcheck:checked');
    var total = 0;
    for (var i = 0; i < boxes.length; i++) {
      total += parseInt(boxes[i].getAttribute('data-subgroups'), 10) || 0;
    }
    var available = total > 0;
    var reverted = false;

    selects.forEach(function (sel) {
      var opt = subgroupOption(sel);
      if (!opt) { return; }
      opt.disabled = !available;
      opt.text = available ? opt.getAttribute('data-label')
                           : opt.getAttribute('data-label') + ' -- none in this selection';
      if (!available && sel.value === opt.value) {
        sel.selectedIndex = 0;
        reverted = true;
      }
    });

    if (boxes.length === 0) {
      status.className = 'rr-status rr-off';
      status.innerHTML = 'Check an involvement above to see whether it has sub-groups.';
    } else if (available) {
      status.className = 'rr-status';
      status.innerHTML = '<strong>' + total + ' sub-group' + (total === 1 ? '' : 's') +
        '</strong> found in your selection. You can now use Sub-Group as a column, ' +
        'a sort order, or a page break under Print options below.';
    } else {
      status.className = 'rr-status rr-off';
      status.innerHTML = 'The involvement(s) you checked have no sub-groups, so the ' +
        'Sub-Group options under Print options are turned off' +
        (reverted ? ' (your Sub-Group choice was reset).' : '.') +
        ' Sub-groups are set up on the involvement itself in TouchPoint.';
    }
  }

  // ---- Step 1 search: narrow a long involvement list ----------------
  var search = document.getElementById('orgSearch');
  var searchClear = document.getElementById('orgSearchClear');
  var noResults = document.getElementById('noResults');
  var listMeta = document.getElementById('listMeta');
  var labels = document.querySelectorAll('.rr-orgcb');

  function applySearch() {
    var term = (search.value || '').trim().toLowerCase();
    var shown = 0;
    for (var i = 0; i < labels.length; i++) {
      var match = !term || labels[i].getAttribute('data-name').indexOf(term) !== -1;
      if (match) { labels[i].classList.remove('rr-hide'); shown++; }
      else { labels[i].classList.add('rr-hide'); }
    }
    noResults.classList.toggle('rr-hide', shown !== 0);
    searchClear.hidden = !term;
    updateMeta(shown, term);
  }

  // A search only hides rows -- it never unchecks one. Anything already
  // checked stays selected (and still counts toward sub-group availability
  // and the roster), so the count below calls out hidden selections rather
  // than letting them silently disappear.
  function updateMeta(shown, term) {
    var checked = document.querySelectorAll('.rr-orgcheck:checked');
    var hiddenChecked = 0;
    for (var i = 0; i < checked.length; i++) {
      if (checked[i].parentNode.classList.contains('rr-hide')) { hiddenChecked++; }
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

  var all = document.querySelectorAll('.rr-orgcheck');
  for (var i = 0; i < all.length; i++) {
    all[i].addEventListener('change', function () {
      refresh();
      applySearch();
    });
  }
  refresh();
  applySearch();

  form.addEventListener('submit', function (e) {
    var checked = [];
    var boxes = document.querySelectorAll('.rr-orgcheck:checked');
    for (var i = 0; i < boxes.length; i++) { checked.push(boxes[i].value); }
    if (checked.length === 0) {
      alert('Pick at least one involvement.');
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
            step_num=2,
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
        sort_by = valid_sort_by(str(getattr(model.Data, "SortBy", "") or ""))
        since_date = valid_since_date(str(getattr(model.Data, "SinceDate", "") or ""))
        exclude_zero = str(getattr(model.Data, "ExcludeZero", "") or "") == "1"

        if not selected_org_ids:
            # How many sub-groups (dbo.MemberTags) each active org in this
            # division defines, so stage 3 can enable/disable the Sub-Group
            # choices live as boxes are ticked. Grouped by OrgId, so there's
            # no fan-out risk; orgs with none simply don't come back and
            # default to 0.
            sql_subgroup_counts = """
            SELECT mt.OrgId, COUNT(*) AS TagCount
            FROM dbo.MemberTags mt
            JOIN dbo.Organizations o ON o.OrganizationId = mt.OrgId
            WHERE o.OrganizationStatusId = {active_status_id}
              AND EXISTS (
                  SELECT 1 FROM dbo.DivOrg d3 WHERE d3.OrgId = mt.OrgId AND d3.DivId = {div_id}
              )
            GROUP BY mt.OrgId
            """.format(active_status_id=ACTIVE_STATUS_ID, div_id=selected_division.Id)

            subgroup_counts = dict(
                (r.OrgId, r.TagCount) for r in q.QuerySql(sql_subgroup_counts)
            )

            render_org_and_options_picker(
                org_rows, selected_program, selected_division, col1, col2,
                group_by, sort_by, since_date, exclude_zero, subgroup_counts,
            )

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
                OrganizationId = om.OrganizationId,
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

            # TouchPoint "SubGroups" for the selected involvement(s).
            # OrgMemMemTags' composite PK is (OrgId, PeopleId, MemberTagId),
            # so this returns exactly one row per member-per-sub-group with
            # no fan-out. Deliberately NOT the STUFF/FOR XML PATH string-
            # concat that roll-sheet-report/TPxi_RollSheet.py uses for the
            # same data: FOR XML PATH XML-escapes the tag name, so a
            # sub-group called "Men & Women" would come back as
            # "Men &amp; Women" and be double-escaped by esc() on render.
            # Joining the names in Python avoids that, and grouping needs
            # the individual names anyway.
            sql_subgroups = """
            SELECT
                ommt.PeopleId,
                ommt.OrgId,
                TagName = mt.Name
            FROM dbo.OrgMemMemTags ommt
            JOIN dbo.MemberTags mt ON mt.Id = ommt.MemberTagId
            JOIN dbo.Organizations o3 ON o3.OrganizationId = ommt.OrgId
            WHERE ommt.OrgId IN ({org_ids})
            ORDER BY o3.OrganizationName, mt.Name
            """.format(org_ids=org_ids_str)

            meeting_rows = list(q.QuerySql(sql_meetings))
            roster_rows = list(q.QuerySql(sql_roster))
            attend_rows = list(q.QuerySql(sql_attend))
            subgroup_rows = list(q.QuerySql(sql_subgroups))

            meeting_dates = [normalize_date(r.MeetingDate) for r in meeting_rows]

            attended_by_person = {}
            for r in attend_rows:
                attended_by_person.setdefault(r.PeopleId, set()).add(normalize_date(r.MeetingDate))

            # Keyed by (PeopleId, OrganizationId), not PeopleId alone:
            # sub-groups belong to a specific involvement, and someone in two
            # selected involvements has a separate roster row per involvement
            # (sql_roster reads from OrganizationMembers) with its own tags.
            subgroups_by_member = {}
            for r in subgroup_rows:
                subgroups_by_member.setdefault((r.PeopleId, r.OrgId), []).append(r.TagName)

            has_subgroups = bool(subgroup_rows)
            multi_org = len(selected_org_ids) > 1

            def subgroup_text(p):
                """Comma-joined sub-group label for one roster row."""
                return ", ".join(subgroups_by_member.get((p.PeopleId, p.OrganizationId), []))

            def subgroup_section_labels(p):
                """Every section this row belongs to when grouping by sub-group.

                A member in two sub-groups is printed under both, so a page
                handed to a sub-group's leader is complete. Sub-group names
                are only unique within an involvement (MemberTags.OrgId), so
                when several involvements are combined the section name is
                prefixed with the involvement to keep two identically-named
                sub-groups from merging into one page.
                """
                names = subgroups_by_member.get((p.PeopleId, p.OrganizationId), [])
                if not names:
                    return [NO_SUBGROUP_LABEL]
                if multi_org:
                    return ["{0}: {1}".format(p.Involvement, n) for n in names]
                return list(names)

            # A stale bookmark or a JS-less browser can still ask for a
            # sub-group column/sort/grouping on involvements that have none.
            # Fall back rather than printing an empty or confusing roster,
            # and say so in the meta line instead of failing silently.
            subgroup_unavailable = False
            if not has_subgroups:
                if group_by == "subgroup":
                    group_by = DEFAULT_GROUP_BY
                    subgroup_unavailable = True
                if sort_by == "subgroup":
                    sort_by = DEFAULT_SORT_BY
                    subgroup_unavailable = True
                if col1 == "subgroup" or col2 == "subgroup":
                    subgroup_unavailable = True

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
                        cells.append('<td class="rr-mark">{0}</td>'.format(mark))
                    total = len(dates_attended)
                    sg_text = subgroup_text(p)
                    col1_val = field_value(col1, p, sg_text)
                    col2_val = field_value(col2, p, sg_text)
                    rows.append(
                        "<tr><td>{name}</td><td>{gender}</td><td>{mtype}</td>{cells}"
                        '<td class="rr-total">{total}</td><td>{col1}</td><td>{col2}</td></tr>'.format(
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
                '<th class="rr-mark">{0}</th>'.format(esc(fmt_col_header(d))) for d in meeting_dates
            )
            col1_header = esc(FIELD_LABELS.get(col1, ""))
            col2_header = esc(FIELD_LABELS.get(col2, ""))

            def build_section_html(title, people, page_break):
                break_class = " rr-page-break" if page_break else ""
                heading_html = (
                    '<h2>{0} <span class="rr-count">({1})</span></h2>'.format(esc(title), len(people))
                    if title else ""
                )
                return """
<div class="rr-section{break_class}">
  {heading}
  <table>
    <thead>
      <tr>
        <th>Name</th><th>Gender</th><th>Member Type</th>{col_headers}<th class="rr-total">Total</th><th>{col1_header}</th><th>{col2_header}</th>
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

            # Sub-group sort: stable, so sql_roster's ORDER BY (involvement,
            # Leader-before-Member, name) survives as the tiebreak inside each
            # sub-group. Members with no sub-group sort to the end.
            if sort_by == "subgroup":
                roster_rows = sorted(
                    roster_rows,
                    key=lambda p: (0, subgroup_text(p).lower()) if subgroup_text(p) else (1, ""),
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
            elif group_by == "subgroup":
                # One section (and printed page) per sub-group, alphabetical,
                # with the no-sub-group catch-all always last. Members in
                # multiple sub-groups appear in each of theirs, so the section
                # counts can add up to more than the roster's total.
                groups = {}
                for p in roster_rows:
                    for label in subgroup_section_labels(p):
                        groups.setdefault(label, []).append(p)
                ordered = sorted(k for k in groups if k != NO_SUBGROUP_LABEL)
                sections_data = [(k, groups[k]) for k in ordered if groups[k]]
                if groups.get(NO_SUBGROUP_LABEL):
                    sections_data.append((NO_SUBGROUP_LABEL, groups[NO_SUBGROUP_LABEL]))
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
            back_href = "?ProgId={0}&amp;DivId={1}&amp;Col1={2}&amp;Col2={3}&amp;GroupBy={4}&amp;SortBy={5}&amp;SinceDate={6}&amp;ExcludeZero={7}".format(
                selected_program.Id, selected_division.Id, col1, col2, group_by, sort_by,
                since_date, "1" if exclude_zero else ""
            )

            since_date_meta = " since {0}".format(esc(since_date)) if since_date else ""
            exclude_zero_meta = " &middot; excluding zero-attendance members" if exclude_zero else ""
            if subgroup_unavailable:
                subgroup_meta = (
                    ' &middot; <strong>no sub-groups</strong> are set up on the selected '
                    'involvement(s), so the sub-group option was skipped'
                )
            elif group_by == "subgroup":
                subgroup_meta = (
                    " &middot; grouped by sub-group (anyone in more than one is listed under each)"
                )
            elif sort_by == "subgroup":
                subgroup_meta = " &middot; sorted by sub-group"
            else:
                subgroup_meta = ""

            print(
                """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{org_label} -- Roster</title>
<style>{css}</style>
</head>
<body>
<div id="{root_id}">
<p class="rr-no-print"><a href="{back_href}">&larr; Choose different involvement(s)</a></p>
<p class="rr-church">RockPointe Church</p>
<h1>{org_label}</h1>
<p class="rr-meta">{org_count} involvement(s) &middot; {meeting_count} meeting(s){since_date_meta} through {last_date} &middot; {total_count} total member(s){exclude_zero_meta}{subgroup_meta}</p>
{sections}
</div>
</body>
</html>""".format(
                    org_label=esc(org_label),
                    css=scope_css(ROSTER_CSS),
                    root_id=ROOT_ID,
                    back_href=back_href,
                    org_count=len(selected_org_ids),
                    meeting_count=len(meeting_dates),
                    since_date_meta=since_date_meta,
                    exclude_zero_meta=exclude_zero_meta,
                    subgroup_meta=subgroup_meta,
                    last_date=esc(fmt_col_header(meeting_dates[-1])) if meeting_dates else "n/a",
                    total_count=len(roster_rows),
                    sections=sections_html,
                )
            )
