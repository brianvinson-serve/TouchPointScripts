# RPC_StaffTaskDashboard.py - RockPointe church-wide staff task dashboard
#
# TouchPoint deployment:
#   Admin > Advanced > Special Content > Python Scripts > +New
#   Name: RPC_StaffTaskDashboard
#
# Purpose:
#   Church-wide view of outstanding TaskNote tasks (not just Student
#   Ministry), grouped by staff department/ministry, task type (native
#   Keyword taxonomy), and task age. Two lenses in one screen:
#     - Rollup view: department x age-bucket matrix, headline KPIs, owner
#       workload leaderboard, task-type breakdown. For leadership.
#     - Detail view: filterable row-by-row task list, worst-first. For
#       staff working their own queue or a lead triaging one department.
#
# Read-only. No task mutation actions (complete/reassign) in this version --
# every row links out to the native TouchPoint person profile for follow-up.
# See ../dashboard/README.md for why actions were deliberately left out of v1.
#
# Roster and Keyword-group data below are hardcoded and need manual upkeep.
# See DB_REFERENCE.md ("TaskNote Keywords", "MemberTags / OrgMemMemTags",
# and the OrgId-not-populated note) for how each design choice was reached:
#   - TaskNote.OrgId is 0% populated at RPC -- can't derive ministry context
#     from the task itself, only from who owns/is assigned to it.
#   - No native MemberTags-based staff/department roster exists at RPC --
#     hence a hardcoded roster here rather than a live TouchPoint join.
#   - The Keyword catalog mixes ministry tags, care/assimilation workflow
#     tags, and automated system/HR tags in one flat list -- KEYWORD_GROUPS
#     below untangles that for filtering purposes.

global model, q, Data

UNASSIGNED = "Unassigned"

# PeopleId -> (Name, Department). Sourced from the 64 people holding an open
# TaskNote task church-wide (2026-08-25 query) cross-referenced against
# https://www.rockpointechurch.org/staff/department/all-staff (2026-08-26).
# People not confirmed against that directory are bucketed Unassigned rather
# than guessed -- including Weston Watts (confirmed off staff, but kept
# visible/Unassigned rather than removed, so his open tasks don't silently
# disappear) and TP System (a non-human integration account, not a person).
# Update this dict as staff change; add new PeopleIds here as they pick up
# open tasks, or their tasks will show as Unassigned by default.
ROSTER = {
    18460: ("Abrie Champion", "Worship and Production"),
    29093: ("Aimee Whaley", "Special Needs Ministry"),
    1673: ("Alan Michael", "Executive/Admin"),
    6674: ("Amy Kraus", "Special Needs Ministry"),
    2879: ("Angela Cheshire", "Children's Ministry"),
    17314: ("Arianah Torres", "Men's Ministry"),
    21230: ("Ashley Reynolds", "Special Needs Ministry"),
    22732: ("Austin Powell", "Worship and Production"),
    23670: ("Brenda Bommarito", "Connections Team"),
    26216: ("Bridget Church", "Communications"),
    13982: ("Cam Champion", "Worship and Production"),
    3262: ("Christi Victor", "Children's Ministry"),
    19792: ("Colleen Dobbs", "Care Team"),
    284: ("Courtney Edmondson", "Student Ministry"),
    23538: ("Courtney Rehbehn", "Children's Ministry"),
    10430: ("Debbie Avinger", "Marriage Ministry"),
    23748: ("Greg Methvin", "Marriage Ministry"),
    46965: ("Isaac Jiles", "Student Ministry"),
    21285: ("Jason Trottie", "Ministry Leaders"),
    4666: ("Jen Armstrong", "Small Groups"),
    24371: ("Kelli Leird", "Marriage Ministry"),
    5285: ("Kellie Lampe", "Operations"),
    15580: ("Kimberley Cramer", "Small Groups"),
    9393: ("Kristin Baker", "Connections Team"),
    7039: ("Lauren Etter", "Women's Ministry"),
    28926: ("Leah McBain", "Children's Ministry"),
    11144: ("Linda Morrison", "NextGen Ministry"),
    28745: ("Maddy McCalley", "Young Adults"),
    37195: ("Makayla Tucker", "Student Ministry"),
    2990: ("Marcie Rumsey", "Operations"),
    35320: ("Margaret Bartlebaugh", "Mid-Gen/Senior Adults"),
    106: ("Margo Baisley", "Children's Ministry"),
    8962: ("Maria Jerke", "Missions & Church Planting"),
    7059: ("Marlene Godinez", "Operations"),
    23164: ("Max McCalley", "Student Ministry"),
    34921: ("Megan DeFilippo", "Care Team"),
    665: ("Melissa Pierce", "Operations"),
    35319: ("Ned Bartlebaugh", "Care Team"),
    25605: ("Sara Comer", "Special Needs Ministry"),
    34835: ("Steven Christopher", "Men's Ministry"),
    17100: ("Tino Smith", "Young Adults"),
    32745: ("Trace Summers", "Worship and Production"),
    300: ("Traci Erb", "Weekday Preschool"),
    29228: ("Treeka Andries", "Weekday Preschool"),
    2351: ("Virginia Smith", "Connections Team"),
    28000: ("Abbie Vinson", "Student Ministry"),

    # Not confirmed against the public staff directory as of 2026-08-26.
    44574: ("Alex Erkelens", UNASSIGNED),
    45948: ("Anthony Aguilar", UNASSIGNED),
    46101: ("Ayeli Padron", UNASSIGNED),
    45732: ("Brandi Protonentis", UNASSIGNED),
    27392: ("Chris Victor", UNASSIGNED),
    49649: ("David Johnston", UNASSIGNED),
    4353: ("Gary Tyner", UNASSIGNED),
    44564: ("Jillian Diveley", UNASSIGNED),
    3222: ("Matthew Webb", UNASSIGNED),
    45230: ("Nancy Tassy", UNASSIGNED),
    5673: ("Natalie Hite", UNASSIGNED),
    45265: ("Patricia Barela", UNASSIGNED),
    46456: ("Patti Flynn", UNASSIGNED),
    47918: ("Stacie Tran", UNASSIGNED),
    28183: ("Stephanie Hiester", UNASSIGNED),

    # Confirmed off staff -- kept Unassigned (not hidden) so any orphaned
    # open tasks stay visible instead of disappearing.
    19570: ("Weston Watts", UNASSIGNED),

    # Non-human integration account, not a staff member.
    33283: ("TP System", "System Account"),
}

# Departments that should sort to the bottom of rollups regardless of count,
# since they're not real ministry accountability buckets.
LOW_PRIORITY_DEPARTMENTS = [UNASSIGNED, "System Account"]

# Keyword Code -> (Description, Group). Source: live TaskNoteKeyword/Keyword
# query, 2026-08-25 (47 active keywords, 27,725 usage rows on ~113k TaskNote
# rows). Group is a judgment call classifying each keyword as a ministry
# context, a care/assimilation workflow stage, or an automated system/HR
# tag -- see DB_REFERENCE.md's "TaskNote Keywords" section for the reasoning.
# A task can carry more than one keyword/group. New keywords created after
# 2026-08-25 will show under "Other" until added here.
KEYWORD_GROUPS = {
    "SG": ("Small Groups", "Ministry"),
    "SM": ("Student Ministry", "Ministry"),
    "AD2": ("Mid-Gen/Senior Adult", "Ministry"),
    "CM": ("Children's Ministry", "Ministry"),
    "WM": ("Women's Ministry", "Ministry"),
    "MEN": ("Men's Ministry", "Ministry"),
    "MS": ("Missions", "Ministry"),
    "YA": ("Young Adult", "Ministry"),
    "AD": ("Adult Discipleship", "Ministry"),
    "MM": ("Marriage Ministry", "Ministry"),
    "WO": ("Worship Ministry", "Ministry"),
    "Fix-It": ("Fix It Ministry (Facilities)", "Ministry"),
    "OP": ("Operations", "Ministry"),
    "PM": ("Parenting", "Ministry"),
    "DX": ("Deacons", "Ministry"),
    "SN": ("Special Needs", "Ministry"),

    "CP": ("Care", "Care & Assimilation"),
    "CO": ("Connections", "Care & Assimilation"),
    "FTV": ("First Time Visitor", "Care & Assimilation"),
    "Pray": ("Prayer Request", "Care & Assimilation"),
    "PR5000": ("Mobile Prayer Request", "Care & Assimilation"),
    "PR5001": ("Prayer Request Unauthenticated", "Care & Assimilation"),
    "PR5002": ("Include in Prayer Feed", "Care & Assimilation"),
    "PR5003": ("Anonymous Prayer Request", "Care & Assimilation"),
    "Grief": ("Grief", "Care & Assimilation"),
    "Bap": ("Baptism", "Care & Assimilation"),
    "Beg w/God": ("Beginning a Relationship with God", "Care & Assimilation"),
    "Hosp.": ("Hospital", "Care & Assimilation"),
    "CA": ("Caution/Concern", "Care & Assimilation"),
    "DE": ("Deceased", "Care & Assimilation"),
    "SNed": ("See Ned", "Care & Assimilation"),
    "SA": ("See Alan", "Care & Assimilation"),
    "FOUP": ("Follow Up Marlene", "Care & Assimilation"),
    "Serve": ("Volunteering", "Care & Assimilation"),
    "Mmbshp": ("Membership", "Care & Assimilation"),
    "DWP": ("Dinner with the Pastor", "Care & Assimilation"),
    "SG1": ("Prospect", "Care & Assimilation"),
    "FTGN": ("FTG Note", "Care & Assimilation"),

    "Failed Gift": ("Failed Gift", "System"),
    "ERmvd": ("Staff email removed", "System"),
    "RRmvd": ("Staff System Roles Removed", "System"),
    "NLStaff": ("Note - no longer on staff", "System"),
    "RFI": ("Removed From Involvements", "System"),
    "RFAI": ("Removed From Additional Involvements", "System"),
    "RR": ("Remove Access Role", "System"),
    "TN0609": ("Account Deletion Requested", "System"),
    "Cmpltd": ("Completed", "System"),
}

KEYWORD_GROUP_CHOICES = ["Ministry", "Care & Assimilation", "System", "Other", "No Keyword"]

# (min_days, max_days_exclusive_or_None, label) -- ordered, checked in order.
AGE_BUCKETS = [
    (0, 7, "New"),
    (7, 14, "Getting Stale"),
    (14, 21, "Needs a Nudge"),
    (21, 30, "Falling Behind"),
    (30, 90, "Backlogged"),
    (90, None, "Forgotten"),
]
AGE_BUCKET_LABELS = [b[2] for b in AGE_BUCKETS]

DUE_BUCKET_CHOICES = ["Overdue", "Today", "This Week", "Later", "No Due Date"]

NEW_PERSON_DATA_ENTRY_PREFIX = "New Person Data Entry%"


def html_escape(value):
    if value is None:
        return ""
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def safe_markdown(value):
    if not value:
        return "<em>No task instructions entered.</em>"
    return model.Markdown(value)


def format_date(value):
    if not value:
        return "—"
    return html_escape(str(value)[:10])


def get_param(name, default_value):
    try:
        value = getattr(Data, name)
        if value is None or value == "":
            return default_value
        return str(value).strip()
    except Exception:
        return default_value


def person_name(first, last, fallback):
    name = ((first or "") + " " + (last or "")).strip()
    return name if name else fallback


def department_for(people_id):
    if not people_id:
        return UNASSIGNED
    entry = ROSTER.get(int(people_id))
    return entry[1] if entry else UNASSIGNED


def age_bucket_for(days_old):
    days_old = days_old or 0
    for lo, hi, label in AGE_BUCKETS:
        if hi is None:
            if days_old >= lo:
                return label
        elif lo <= days_old < hi:
            return label
    return AGE_BUCKET_LABELS[-1]


def due_bucket_for(is_overdue, due_date, days_until_due):
    if not due_date:
        return "No Due Date"
    if is_overdue:
        return "Overdue"
    if days_until_due is not None and days_until_due <= 0:
        return "Today"
    if days_until_due is not None and days_until_due <= 7:
        return "This Week"
    return "Later"


def department_sort_key(name):
    return (1 if name in LOW_PRIORITY_DEPARTMENTS else 0, name)


# ---------------------------------------------------------------------------
# Query params / filters
# ---------------------------------------------------------------------------

department_filter = get_param("dept", "all")
group_filter = get_param("type", "all")
keyword_filter = get_param("kw", "all")
age_filter = get_param("age", "all")
due_filter = get_param("due", "all")
person_filter = get_param("person", "all")
view_filter = get_param("view", "rollup")

all_departments = sorted(set(v[1] for v in ROSTER.values()), key=department_sort_key)

if department_filter not in all_departments:
    department_filter = "all"
if group_filter not in KEYWORD_GROUP_CHOICES:
    group_filter = "all"
if keyword_filter not in KEYWORD_GROUPS:
    keyword_filter = "all"
if age_filter not in AGE_BUCKET_LABELS:
    age_filter = "all"
if due_filter not in DUE_BUCKET_CHOICES:
    due_filter = "all"
if view_filter not in ("rollup", "detail"):
    view_filter = "rollup"
if person_filter != "all":
    try:
        int(person_filter)
    except ValueError:
        person_filter = "all"

# ---------------------------------------------------------------------------
# Data pull -- one query, all filtering/bucketing done in Python since the
# dataset is small (a few hundred open tasks church-wide) and department is
# a code-side roster lookup, not something SQL can join to.
# ---------------------------------------------------------------------------

task_sql = """
SELECT
    tn.TaskNoteId,
    tn.OwnerId,
    COALESCE(ownerPerson.NickName, ownerPerson.FirstName) AS OwnerFirst,
    ownerPerson.LastName AS OwnerLast,
    tn.AssigneeId,
    COALESCE(assigneePerson.NickName, assigneePerson.FirstName) AS AssigneeFirst,
    assigneePerson.LastName AS AssigneeLast,
    tn.AboutPersonId,
    COALESCE(aboutPerson.NickName, aboutPerson.FirstName) AS AboutFirst,
    aboutPerson.LastName AS AboutLast,
    tn.StatusId,
    CASE tn.StatusId WHEN 2 THEN 'Pending' WHEN 3 THEN 'Active' ELSE CAST(tn.StatusId AS VARCHAR(20)) END AS StatusName,
    tn.CreatedDate,
    tn.DueDate,
    DATEDIFF(day, tn.CreatedDate, GETDATE()) AS DaysOld,
    CASE WHEN tn.DueDate IS NOT NULL AND CAST(tn.DueDate AS DATE) < CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END AS IsOverdue,
    DATEDIFF(day, CAST(GETDATE() AS DATE), CAST(tn.DueDate AS DATE)) AS DaysUntilDue,
    tn.Instructions,
    (
        SELECT STRING_AGG(k.Code, ',')
        FROM TaskNoteKeyword tnk
        JOIN Keyword k ON k.KeywordId = tnk.KeywordId
        WHERE tnk.TaskNoteId = tn.TaskNoteId
    ) AS KeywordCodes
FROM TaskNote tn
LEFT JOIN People ownerPerson ON ownerPerson.PeopleId = tn.OwnerId
LEFT JOIN People assigneePerson ON assigneePerson.PeopleId = tn.AssigneeId
LEFT JOIN People aboutPerson ON aboutPerson.PeopleId = tn.AboutPersonId
WHERE tn.StatusId IN (2, 3)
  AND (tn.IsArchived = 0 OR tn.IsArchived IS NULL)
  AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
  AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE '{new_person_prefix}')
""".format(new_person_prefix=NEW_PERSON_DATA_ENTRY_PREFIX)
# NOTE: STRING_AGG requires SQL Server 2017+. Needs live TouchPoint validation --
# if it errors, fall back to FOR XML PATH concatenation.

raw_tasks = list(q.QuerySql(task_sql))

tasks = []
for row in raw_tasks:
    owner_name = person_name(row.OwnerFirst, row.OwnerLast, "Unknown owner")
    assignee_name = person_name(row.AssigneeFirst, row.AssigneeLast, None) if row.AssigneeId else None
    about_name = person_name(row.AboutFirst, row.AboutLast, "—")

    accountable_id = row.AssigneeId or row.OwnerId
    accountable_name = assignee_name or owner_name
    department = department_for(accountable_id)

    keyword_codes = [c.strip() for c in (row.KeywordCodes or "").split(",") if c.strip()]
    keyword_labels = []
    keyword_groups = set()
    for code in keyword_codes:
        desc, group = KEYWORD_GROUPS.get(code, (code, "Other"))
        keyword_labels.append("{} ({})".format(desc, code))
        keyword_groups.add(group)
    if not keyword_codes:
        keyword_groups.add("No Keyword")

    days_old = row.DaysOld or 0

    tasks.append({
        "task_note_id": row.TaskNoteId,
        "owner_id": row.OwnerId,
        "owner_name": owner_name,
        "assignee_id": row.AssigneeId,
        "assignee_name": assignee_name,
        "about_id": row.AboutPersonId,
        "about_name": about_name,
        "status_name": row.StatusName,
        "created_date": row.CreatedDate,
        "due_date": row.DueDate,
        "days_old": days_old,
        "age_bucket": age_bucket_for(days_old),
        "is_overdue": bool(row.IsOverdue),
        "due_bucket": due_bucket_for(row.IsOverdue, row.DueDate, row.DaysUntilDue),
        "instructions": row.Instructions,
        "accountable_id": accountable_id,
        "accountable_name": accountable_name,
        "department": department,
        "keyword_codes": keyword_codes,
        "keyword_labels": keyword_labels,
        "keyword_groups": keyword_groups,
    })


def matches_filters(task):
    if department_filter != "all" and task["department"] != department_filter:
        return False
    if group_filter != "all" and group_filter not in task["keyword_groups"]:
        return False
    if keyword_filter != "all" and keyword_filter not in task["keyword_codes"]:
        return False
    if age_filter != "all" and task["age_bucket"] != age_filter:
        return False
    if due_filter != "all" and task["due_bucket"] != due_filter:
        return False
    if person_filter != "all" and task["accountable_id"] != int(person_filter):
        return False
    return True


filtered = [t for t in tasks if matches_filters(t)]

# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

total_count = len(filtered)
overdue_count = sum(1 for t in filtered if t["is_overdue"])
forgotten_count = sum(1 for t in filtered if t["age_bucket"] == "Forgotten")
unassigned_count = sum(1 for t in filtered if t["department"] == UNASSIGNED)
distinct_people = len(set(t["accountable_id"] for t in filtered if t["accountable_id"]))
flagged_system_count = sum(1 for t in filtered if t["department"] == "System Account")

dept_matrix = {}
for t in filtered:
    dept = t["department"]
    row = dept_matrix.setdefault(dept, {"total": 0, "overdue": 0})
    for label in AGE_BUCKET_LABELS:
        row.setdefault(label, 0)
    row["total"] += 1
    row[t["age_bucket"]] += 1
    if t["is_overdue"]:
        row["overdue"] += 1

owner_workload = {}
for t in filtered:
    pid = t["accountable_id"] or 0
    entry = owner_workload.setdefault(pid, {
        "name": t["accountable_name"] or "Unassigned",
        "department": t["department"],
        "count": 0,
        "overdue": 0,
        "oldest_days": 0,
    })
    entry["count"] += 1
    if t["is_overdue"]:
        entry["overdue"] += 1
    entry["oldest_days"] = max(entry["oldest_days"], t["days_old"])

group_counts = {}
for t in filtered:
    for group in t["keyword_groups"]:
        group_counts[group] = group_counts.get(group, 0) + 1

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

print("""
<style>
.rpc-task-dashboard { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2933; }
.rpc-task-dashboard .hero { background: #12355b; color: white; border-radius: 12px; padding: 22px 26px; margin-bottom: 18px; }
.rpc-task-dashboard .hero h1 { margin: 0 0 6px 0; font-size: 28px; }
.rpc-task-dashboard .hero p { margin: 0; opacity: .9; }
.rpc-task-dashboard .cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 18px; }
.rpc-task-dashboard .card { flex: 1; min-width: 155px; background: #f7fafc; border: 1px solid #d9e2ec; border-radius: 10px; padding: 14px; }
.rpc-task-dashboard .card.warn { background: #fff5f5; border-color: #fca5a5; }
.rpc-task-dashboard .metric { font-size: 30px; font-weight: 800; line-height: 1; }
.rpc-task-dashboard .label { color: #52606d; font-size: 13px; margin-top: 5px; }
.rpc-task-dashboard .filters { background: #f0f4f8; border: 1px solid #d9e2ec; border-radius: 10px; padding: 14px; margin-bottom: 18px; }
.rpc-task-dashboard .filters form { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; margin: 0; }
.rpc-task-dashboard .field label { display: block; font-size: 12px; color: #52606d; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .04em; }
.rpc-task-dashboard select { padding: 7px 10px; border: 1px solid #bcccdc; border-radius: 6px; background: white; max-width: 220px; }
.rpc-task-dashboard button, .rpc-task-dashboard .button { background: #0b6bcb; color: white; border: 0; border-radius: 6px; padding: 8px 13px; text-decoration: none; cursor: pointer; display: inline-block; }
.rpc-task-dashboard .button.secondary { background: #627d98; }
.rpc-task-dashboard table { width: 100%; border-collapse: collapse; margin-bottom: 18px; }
.rpc-task-dashboard th { background: #243b53; color: white; text-align: left; padding: 10px; font-size: 13px; }
.rpc-task-dashboard td { border-bottom: 1px solid #d9e2ec; padding: 9px 10px; vertical-align: top; }
.rpc-task-dashboard tr.overdue td { background: #fff5f5; }
.rpc-task-dashboard tr.forgotten td { background: #fffbeb; }
.rpc-task-dashboard .pill { display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.rpc-task-dashboard .pill.red { background: #fde2e2; color: #b42318; }
.rpc-task-dashboard .pill.orange { background: #ffedd5; color: #9a3412; }
.rpc-task-dashboard .pill.yellow { background: #fff3bf; color: #7c5e10; }
.rpc-task-dashboard .pill.blue { background: #dbeafe; color: #1d4ed8; }
.rpc-task-dashboard .pill.gray { background: #e5e7eb; color: #374151; }
.rpc-task-dashboard .keyword-chip { display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 6px; padding: 2px 7px; font-size: 11px; margin: 1px 3px 1px 0; }
.rpc-task-dashboard .instructions { max-width: 460px; }
.rpc-task-dashboard .muted { color: #627d98; }
.rpc-task-dashboard .banner { background: #fffbeb; border: 1px solid #fbbf24; border-radius: 8px; padding: 10px 14px; margin-bottom: 18px; font-size: 14px; }
.rpc-task-dashboard .empty { text-align: center; padding: 32px; background: #f0fff4; border: 1px solid #c6f6d5; border-radius: 10px; color: #276749; font-weight: 700; }
.rpc-task-dashboard .tabs { display: flex; gap: 8px; margin-bottom: 18px; }
.rpc-task-dashboard .tabs a { padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 14px; color: #243b53; background: #e4e9f0; }
.rpc-task-dashboard .tabs a.active { background: #0b6bcb; color: white; }
.rpc-task-dashboard table.matrix td, .rpc-task-dashboard table.matrix th { text-align: center; }
.rpc-task-dashboard table.matrix td:first-child, .rpc-task-dashboard table.matrix th:first-child { text-align: left; }
</style>
<div class="rpc-task-dashboard">
  <div class="hero">
    <h1>RPC Staff Task Dashboard</h1>
    <p>Outstanding TouchPoint TaskNote tasks, church-wide, by department and task type.</p>
  </div>
""")

if flagged_system_count:
    print(
        '<div class="banner">{} open task(s) are owned by the <strong>TP System</strong> integration '
        'account, not a person -- worth a look at what those actually are before treating them as '
        'real staff backlog.</div>'.format(flagged_system_count)
    )

print("""
  <div class="cards">
    <div class="card"><div class="metric">{total}</div><div class="label">Open tasks</div></div>
    <div class="card warn"><div class="metric">{overdue}</div><div class="label">Overdue</div></div>
    <div class="card warn"><div class="metric">{forgotten}</div><div class="label">Forgotten (90+ days)</div></div>
    <div class="card"><div class="metric">{people}</div><div class="label">Staff with open tasks</div></div>
    <div class="card"><div class="metric">{unassigned}</div><div class="label">Unassigned department</div></div>
  </div>
""".format(
    total=total_count,
    overdue=overdue_count,
    forgotten=forgotten_count,
    people=distinct_people,
    unassigned=unassigned_count,
))


def option_list(options, selected, all_label):
    html = ['<option value="all"{0}>{1}</option>'.format(" selected" if selected == "all" else "", all_label)]
    for value in options:
        sel = " selected" if value == selected else ""
        html.append('<option value="{0}"{1}>{0}</option>'.format(html_escape(value), sel))
    return "\n".join(html)


def keyword_options(selected):
    html = ['<option value="all"{0}>All keywords</option>'.format(" selected" if selected == "all" else "")]
    for group in ["Ministry", "Care & Assimilation", "System"]:
        codes = sorted(
            (c for c, (desc, g) in KEYWORD_GROUPS.items() if g == group),
            key=lambda c: KEYWORD_GROUPS[c][0],
        )
        if not codes:
            continue
        html.append('<optgroup label="{}">'.format(html_escape(group)))
        for code in codes:
            desc = KEYWORD_GROUPS[code][0]
            sel = " selected" if code == selected else ""
            html.append('<option value="{0}"{1}>{2} ({0})</option>'.format(html_escape(code), sel, html_escape(desc)))
        html.append('</optgroup>')
    return "\n".join(html)


def person_options(selected):
    html = ['<option value="all"{0}>All staff</option>'.format(" selected" if selected == "all" else "")]
    for pid, (name, dept) in sorted(ROSTER.items(), key=lambda kv: kv[1][0]):
        sel = " selected" if str(pid) == selected else ""
        html.append('<option value="{0}"{1}>{2} ({3})</option>'.format(pid, sel, html_escape(name), html_escape(dept)))
    return "\n".join(html)


print("""
  <div class="tabs">
    <a href="?view=rollup&dept={dept}&type={type}&kw={kw}&age={age}&due={due}&person={person}" class="{rollup_active}">Leadership Rollup</a>
    <a href="?view=detail&dept={dept}&type={type}&kw={kw}&age={age}&due={due}&person={person}" class="{detail_active}">Task Detail</a>
  </div>
""".format(
    dept=html_escape(department_filter),
    type=html_escape(group_filter),
    kw=html_escape(keyword_filter),
    age=html_escape(age_filter),
    due=html_escape(due_filter),
    person=html_escape(person_filter),
    rollup_active="active" if view_filter == "rollup" else "",
    detail_active="active" if view_filter == "detail" else "",
))

print("""
  <div class="filters">
    <form method="get">
      <input type="hidden" name="view" value="{view}">
      <div class="field">
        <label for="dept">Department</label>
        <select id="dept" name="dept">{dept_options}</select>
      </div>
      <div class="field">
        <label for="type">Task type (group)</label>
        <select id="type" name="type">{type_options}</select>
      </div>
      <div class="field">
        <label for="kw">Keyword</label>
        <select id="kw" name="kw">{kw_options}</select>
      </div>
      <div class="field">
        <label for="age">Age</label>
        <select id="age" name="age">{age_options}</select>
      </div>
      <div class="field">
        <label for="due">Due date</label>
        <select id="due" name="due">{due_options}</select>
      </div>
      <div class="field">
        <label for="person">Staff member</label>
        <select id="person" name="person">{person_options}</select>
      </div>
      <button type="submit">Apply</button>
      <a class="button secondary" href="?view={view}">Reset</a>
    </form>
  </div>
""".format(
    view=html_escape(view_filter),
    dept_options=option_list(all_departments, department_filter, "All departments"),
    type_options=option_list(KEYWORD_GROUP_CHOICES, group_filter, "All types"),
    kw_options=keyword_options(keyword_filter),
    age_options=option_list(AGE_BUCKET_LABELS, age_filter, "All ages"),
    due_options=option_list(DUE_BUCKET_CHOICES, due_filter, "All due dates"),
    person_options=person_options(person_filter),
))

if not filtered:
    print('<div class="empty">No open tasks match these filters.</div>')

elif view_filter == "rollup":
    # Department x age-bucket matrix
    print('<h3>By Department</h3>')
    print('<table class="matrix"><thead><tr><th>Department</th>')
    for label in AGE_BUCKET_LABELS:
        print('<th>{}</th>'.format(label))
    print('<th>Total</th><th>Overdue</th></tr></thead><tbody>')

    dept_order = sorted(dept_matrix.keys(), key=department_sort_key)
    totals_row = {label: 0 for label in AGE_BUCKET_LABELS}
    totals_row["total"] = 0
    totals_row["overdue"] = 0
    for dept in dept_order:
        row = dept_matrix[dept]
        print('<tr><td>{}</td>'.format(html_escape(dept)))
        for label in AGE_BUCKET_LABELS:
            count = row.get(label, 0)
            totals_row[label] += count
            cell = str(count) if count else '<span class="muted">0</span>'
            if label == "Forgotten" and count:
                cell = '<span class="pill yellow">{}</span>'.format(count)
            print('<td>{}</td>'.format(cell))
        totals_row["total"] += row["total"]
        totals_row["overdue"] += row["overdue"]
        overdue_cell = '<span class="pill red">{}</span>'.format(row["overdue"]) if row["overdue"] else "0"
        print('<td><strong>{}</strong></td><td>{}</td></tr>'.format(row["total"], overdue_cell))
    print('<tr><td><strong>All departments</strong></td>')
    for label in AGE_BUCKET_LABELS:
        print('<td><strong>{}</strong></td>'.format(totals_row[label]))
    print('<td><strong>{}</strong></td><td><strong>{}</strong></td></tr>'.format(totals_row["total"], totals_row["overdue"]))
    print('</tbody></table>')

    # Task-type breakdown
    print('<h3>By Task Type</h3>')
    print('<p class="muted">A task can carry more than one type, so these can add up to more than the total task count.</p>')
    print('<table><thead><tr><th>Type</th><th>Tasks</th></tr></thead><tbody>')
    for group in ["Ministry", "Care & Assimilation", "System", "Other", "No Keyword"]:
        count = group_counts.get(group, 0)
        if count:
            print('<tr><td>{}</td><td>{}</td></tr>'.format(html_escape(group), count))
    print('</tbody></table>')

    # Owner workload leaderboard
    print('<h3>By Staff Member</h3>')
    print('<table><thead><tr><th>Staff Member</th><th>Department</th><th>Open</th><th>Overdue</th><th>Oldest</th></tr></thead><tbody>')
    workload_order = sorted(owner_workload.items(), key=lambda kv: kv[1]["count"], reverse=True)
    for pid, entry in workload_order:
        oldest_cell = '<span class="pill yellow">{} days</span>'.format(entry["oldest_days"]) if entry["oldest_days"] >= 90 else "{} days".format(entry["oldest_days"])
        overdue_cell = '<span class="pill red">{}</span>'.format(entry["overdue"]) if entry["overdue"] else "0"
        name_cell = html_escape(entry["name"])
        if pid:
            name_cell = '<a href="{}/Person2/{}#tab-touchpoints">{}</a>'.format(model.CmsHost, pid, name_cell)
        print('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            name_cell, html_escape(entry["department"]), entry["count"], overdue_cell, oldest_cell
        ))
    print('</tbody></table>')

else:
    # Detail view -- worst first: overdue before not-overdue, oldest first within each.
    detail_tasks = sorted(filtered, key=lambda t: (0 if t["is_overdue"] else 1, -t["days_old"]))
    print("""
  <table>
    <thead>
      <tr>
        <th>Staff (Accountable)</th>
        <th>Department</th>
        <th>About</th>
        <th>Type</th>
        <th>Age</th>
        <th>Due</th>
        <th>Task</th>
      </tr>
    </thead>
    <tbody>
    """)
    for t in detail_tasks:
        row_class = ""
        if t["is_overdue"]:
            row_class = "overdue"
        elif t["age_bucket"] == "Forgotten":
            row_class = "forgotten"

        if t["age_bucket"] in ("Forgotten", "Backlogged"):
            age_pill_color = "red" if t["age_bucket"] == "Forgotten" else "yellow"
        elif t["age_bucket"] in ("Falling Behind", "Needs a Nudge"):
            age_pill_color = "orange"
        else:
            age_pill_color = "blue"
        age_badge = '<span class="pill {}">{} &middot; {}d</span>'.format(age_pill_color, t["age_bucket"], t["days_old"])

        due_colors = {"Overdue": "red", "Today": "orange", "This Week": "yellow", "Later": "blue", "No Due Date": "gray"}
        due_label = t["due_bucket"]
        if t["due_date"] and due_label != "No Due Date":
            due_label = "{} ({})".format(due_label, format_date(t["due_date"]))
        due_badge = '<span class="pill {}">{}</span>'.format(due_colors.get(t["due_bucket"], "gray"), due_label)

        about_link = "—"
        if t["about_id"]:
            about_link = '<a href="{}/Person2/{}#tab-touchpoints">{}</a>'.format(model.CmsHost, t["about_id"], html_escape(t["about_name"]))

        accountable_link = html_escape(t["accountable_name"] or "Unassigned")
        if t["accountable_id"]:
            accountable_link = '<a href="{}/Person2/{}#tab-touchpoints">{}</a>'.format(model.CmsHost, t["accountable_id"], accountable_link)

        keyword_html = "".join('<span class="keyword-chip">{}</span>'.format(html_escape(k)) for k in t["keyword_labels"]) or '<span class="muted">none</span>'

        print("""
      <tr class="{row_class}">
        <td>{accountable}</td>
        <td>{department}</td>
        <td>{about}</td>
        <td>{keywords}</td>
        <td>{age}</td>
        <td>{due}</td>
        <td class="instructions">{instructions}</td>
      </tr>
        """.format(
            row_class=row_class,
            accountable=accountable_link,
            department=html_escape(t["department"]),
            about=about_link,
            keywords=keyword_html,
            age=age_badge,
            due=due_badge,
            instructions=safe_markdown(t["instructions"]),
        ))
    print("""
    </tbody>
  </table>
    """)

print("""
  <p class="muted">
    Source: TaskNote. Open = Pending/Active, not archived, not a note, excluding New Person Data Entry
    housekeeping tasks. "Accountable" staff member is the assignee if set, otherwise the owner.
    Department comes from a hardcoded roster (see script header), not a live TouchPoint field --
    update it as staff change. This is a read-only view; use the linked TouchPoint profile to act
    on a task from the native task list.
  </p>
</div>
""")
