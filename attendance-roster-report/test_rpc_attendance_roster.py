# -*- coding: utf-8 -*-
"""Offline test suite for RPC_AttendanceRoster.py.

Runs the real script end-to-end against a mocked TouchPoint `q`/`model`
with fabricated (non-PII) data, and captures the HTML it prints. No live
TouchPoint or database access -- run it from anywhere:

    python3 attendance-roster-report/test_rpc_attendance_roster.py

The headline section is BOOKMARK COMPATIBILITY. Staff "save" a roster
configuration by bookmarking its generated URL (see README), so every
query-string shape an existing bookmark could hold is replayed against
BOTH the pre-sub-group baseline (git commit BASELINE_REV) and the current
script, asserting the rendered roster rows and section headings come back
identical. Those bookmarks are replayed against involvements with and
without sub-groups, since an involvement may have had sub-groups added in
TouchPoint after the bookmark was made.

Fabricated fixture data only -- no real RPC member data lives here.
"""
import io, os, re, subprocess, sys, tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "RPC_AttendanceRoster.py")

# Last release before sub-group support -- the behavior bookmarked URLs
# were saved against ("RPC_AttendanceRoster: add optional attendance-since
# date filter and zero-attendance exclusion").
BASELINE_REV = "d15f4ae"
BASELINE_PATH = "attendance-roster-report/RPC_AttendanceRoster.py"


def fetch_baseline():
    """Check the pre-sub-group script out of git, or None if unavailable."""
    try:
        blob = subprocess.check_output(
            ["git", "show", "%s:%s" % (BASELINE_REV, BASELINE_PATH)],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stderr=subprocess.PIPE,
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    fd, path = tempfile.mkstemp(suffix="_baseline.py")
    with os.fdopen(fd, "wb") as fh:
        fh.write(blob)
    return path


class Row(object):
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

class Data(object):
    def __init__(self, **kw):
        self._d = dict(kw)
    def __getattr__(self, name):
        return self._d.get(name, "")

class Model(object):
    def __init__(self, user_id, **data):
        self.UserPeopleId = user_id
        self.Data = Data(**data)
    def FmtPhone(self, v):
        return "(555) 555-%s" % str(v)[-4:] if v else ""

PROGRAMS = [Row(Id=1119, Name="Adult Discipleship (AD)")]
DIVISIONS = [Row(Id=126, Name="AD ReNew")]
ORGS = [
    Row(OrganizationId=3906, OrganizationName="ReNew Fall 2026", MemberCount=4),
    Row(OrganizationId=4133, OrganizationName="ReNew F26 Closed Groups", MemberCount=2),
]

# people: (PeopleId, Name, GenderId, MemberTypeId, OrgId)
PEOPLE = {
    101: ("Alice Adams", 2, 140, "Adams"),
    102: ("Bob Baker", 1, 220, "Baker"),
    103: ("Carol Chen", 2, 220, "Chen"),
    104: ("Dave Diaz", 1, 140, "Diaz"),
    105: ("Erin Ellis", 2, 220, "Ellis"),
    106: ("Frank Fox", 1, 220, "Fox"),
}
ORG_MEMBERS = {3906: [101, 102, 103, 104, 106], 4133: [102, 105]}
MEETINGS = {3906: ["2026-08-17", "2026-08-24"], 4133: ["2026-08-17", "2026-08-24"]}
ATTEND = {  # (PeopleId) -> dates attended
    101: ["2026-08-17", "2026-08-24"],
    102: ["2026-08-17"],
    103: [],                      # zero attendance
    104: ["2026-08-24"],
    105: ["2026-08-17", "2026-08-24"],
    106: ["2026-08-24"],
}

def build_q(subgroups):
    """subgroups: {(peopleId, orgId): [tagname, ...]}"""
    class Q(object):
        def QuerySql(self, sql):
            s = " ".join(sql.split())
            if "FROM dbo.Program p" in s:
                return list(PROGRAMS)
            if "FROM dbo.Division d " in s or s.rstrip().endswith("FROM dbo.Division d"):
                return list(DIVISIONS)
            if "FROM dbo.MemberTags mt JOIN dbo.Organizations o" in s and "COUNT(*)" in s:
                counts = {}
                for (pid, oid), tags in subgroups.items():
                    counts.setdefault(oid, set()).update(tags)
                return [Row(OrgId=o, TagCount=len(t)) for o, t in sorted(counts.items())]
            if "FROM dbo.Organizations o WHERE o.OrganizationStatusId" in s:
                return list(ORGS)
            if "FROM dbo.Meetings m WHERE" in s:
                oids = _ids(s)
                since = _since(s)
                dates = sorted(set(d for o in oids for d in MEETINGS.get(o, [])
                                   if not since or d >= since))
                return [Row(MeetingDate=d) for d in dates]
            if "FROM dbo.OrganizationMembers om JOIN dbo.People p" in s:
                oids = _ids(s)
                out = []
                for oid in oids:
                    oname = [o.OrganizationName for o in ORGS if o.OrganizationId == oid][0]
                    for pid in ORG_MEMBERS.get(oid, []):
                        nm, gid, mt, last = PEOPLE[pid]
                        out.append(Row(
                            PeopleId=pid, Name=nm, LastName=last, GenderId=gid,
                            Gender={1: "Male", 2: "Female"}.get(gid, "Unknown"),
                            MemberTypeId=mt, CellPhone="555000%04d" % pid,
                            Email="p%d@example.invalid" % pid, Age=30 + pid % 10,
                            Grade="", MaritalStatus="Married",
                            OrganizationId=oid, Involvement=oname))
                # mirror sql_roster's ORDER BY: org name, leader-first, lastname
                out.sort(key=lambda r: (r.Involvement,
                                        {140: 0, 220: 1}.get(r.MemberTypeId, 2),
                                        r.LastName, r.Name))
                return out
            if "FROM dbo.Attend a" in s:
                oids = _ids(s)
                since = _since(s)
                out = []
                for oid in oids:
                    for pid in ORG_MEMBERS.get(oid, []):
                        for d in ATTEND.get(pid, []):
                            if d in MEETINGS.get(oid, []) and (not since or d >= since):
                                out.append(Row(PeopleId=pid, MeetingDate=d))
                return out
            if "FROM dbo.OrgMemMemTags ommt" in s:
                oids = _ids(s)
                out = []
                for (pid, oid), tags in sorted(subgroups.items()):
                    if oid in oids:
                        for t in sorted(tags):
                            out.append(Row(PeopleId=pid, OrgId=oid, TagName=t))
                return out
            raise AssertionError("unmatched SQL:\n" + s[:300])
    return Q()

def _ids(s):
    m = re.search(r"IN \(([0-9,\s]+)\)", s)
    return [int(x) for x in m.group(1).split(",")] if m else []

def _since(s):
    m = re.search(r">= '(\d{4}-\d{2}-\d{2})'", s)
    return m.group(1) if m else None

def run(script_path, user_id=47110, subgroups=None, **data):
    src = io.open(script_path, encoding="utf-8").read()
    g = {"__name__": "__main__", "model": Model(user_id, **data), "q": build_q(subgroups or {})}
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        exec(compile(src, script_path, "exec"), g)
    finally:
        sys.stdout = old
    return buf.getvalue()

# Sub-group fixtures. Bob (102) is in TWO sub-groups; Carol (103) in none.
# Org 4133 deliberately reuses the name "Table 1" to test cross-org collision.
SG = {
    (101, 3906): ["Table 1"],
    (102, 3906): ["Table 1", "Table 2"],
    (104, 3906): ["Table 2"],
    (106, 3906): ["Table 1"],
    (102, 4133): ["Table 1"],
    (105, 4133): ["Table 3"],
}
NOSG = {}

NEW = SCRIPT
OLD = fetch_baseline()
if OLD is None:
    print("WARNING: baseline %s not reachable via git -- "
          "bookmark-compatibility comparisons will be skipped." % BASELINE_REV)

fails = []
def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (("\n         " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)

# Class names are deliberately prefixed (rr-*) so they can't collide with
# TouchPoint's own stylesheet, so a bookmark comparison against the older
# baseline must compare CONTENT, not styling hooks. Everything else about a
# row -- cell count, order, values, the attendance checkmarks -- still has to
# match exactly.
def tbody(html):
    return [re.sub(r'\s*class="[^"]*"', "", r)
            for r in re.findall(r"<tr><td>.*?</tr>", html, re.S)]

def headings(html):
    return [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h2>.*?</h2>", html, re.S)]

def names_in_order(html):
    return [re.match(r"<tr><td>([^<]*)</td>", r).group(1) for r in tbody(html)]

# =====================================================================
print("\n=== 1. BOOKMARK COMPATIBILITY: old URLs, old script vs new script ===")
# Every param combination a previously-bookmarked URL could contain.
BOOKMARKS = [
    ("bare legacy URL (no options at all)", dict(ProgId="1119", DivId="126", OrgIds="3906")),
    ("phone/email + gender", dict(ProgId="1119", DivId="126", OrgIds="3906", Col1="phone", Col2="email", GroupBy="gender")),
    ("group by involvement, 2 orgs", dict(ProgId="1119", DivId="126", OrgIds="3906,4133", Col1="involvement", Col2="age", GroupBy="involvement")),
    ("no grouping", dict(ProgId="1119", DivId="126", OrgIds="3906", GroupBy="none")),
    ("SinceDate filter", dict(ProgId="1119", DivId="126", OrgIds="3906", SinceDate="2026-08-24")),
    ("ExcludeZero", dict(ProgId="1119", DivId="126", OrgIds="3906", ExcludeZero="1")),
    ("age/lastname cols", dict(ProgId="1119", DivId="126", OrgIds="3906", Col1="age", Col2="lastname")),
    ("maritalstatus/grade cols", dict(ProgId="1119", DivId="126", OrgIds="3906", Col1="maritalstatus", Col2="grade")),
    ("SinceDate + ExcludeZero + involvement", dict(ProgId="1119", DivId="126", OrgIds="3906,4133", GroupBy="involvement", SinceDate="2026-08-17", ExcludeZero="1")),
    ("invalid stale GroupBy value", dict(ProgId="1119", DivId="126", OrgIds="3906", GroupBy="bogus")),
    ("stale OrgId no longer in division", dict(ProgId="1119", DivId="126", OrgIds="3906,99999")),
]
for label, params in (BOOKMARKS if OLD else []):
    # Bookmarks are replayed against BOTH sub-group states: the underlying
    # involvement may since have had sub-groups added in TouchPoint.
    for sgname, sg in (("no sub-groups", NOSG), ("sub-groups now exist", SG)):
        old_html = run(OLD, subgroups=NOSG, **params)   # old script never saw sub-groups
        new_html = run(NEW, subgroups=sg, **params)
        same_rows = tbody(old_html) == tbody(new_html)
        same_secs = headings(old_html) == headings(new_html)
        check("%s [%s] -- identical roster rows" % (label, sgname), same_rows,
              "old=%d rows new=%d rows" % (len(tbody(old_html)), len(tbody(new_html))))
        check("%s [%s] -- identical sections" % (label, sgname), same_secs,
              "old=%r new=%r" % (headings(old_html), headings(new_html)))

# =====================================================================
print("\n=== 2. NO SUB-GROUPS: new options degrade safely ===")
h = run(NEW, subgroups=NOSG, ProgId="1119", DivId="126", OrgIds="3906", GroupBy="subgroup")
check("GroupBy=subgroup falls back to gender sections",
      headings(h) == ["Men (3)", "Women (2)"], repr(headings(h)))
check("fallback is disclosed in the meta line", "no sub-groups</strong> are set up" in h)

h = run(NEW, subgroups=NOSG, ProgId="1119", DivId="126", OrgIds="3906", Col1="subgroup", Col2="email")
check("Col1=subgroup renders an empty column, no crash", "<td></td>" in h and len(tbody(h)) == 5)

h = run(NEW, subgroups=NOSG, ProgId="1119", DivId="126", OrgIds="3906", SortBy="subgroup")
base = run(NEW, subgroups=NOSG, ProgId="1119", DivId="126", OrgIds="3906")
check("SortBy=subgroup with no sub-groups leaves order unchanged",
      names_in_order(h) == names_in_order(base), repr(names_in_order(h)))

# =====================================================================
print("\n=== 3. WITH SUB-GROUPS: column / grouping / sorting ===")
h = run(NEW, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906", Col1="subgroup", Col2="email")
check("multi-sub-group member is comma-joined", "Table 1, Table 2" in h)
check("single-sub-group member shown", ">Table 1<" in h or "Table 1</td>" in h)
check("no-sub-group member's cell is blank", len(tbody(h)) == 5)

h = run(NEW, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906", GroupBy="subgroup")
hd = headings(h)
check("one section per sub-group, no-sub-group last",
      hd == ["Table 1 (3)", "Table 2 (2)", "(No sub-group) (1)"], repr(hd))
check("member in two sub-groups is printed under both",
      sum(1 for r in tbody(h) if "Bob Baker" in r) == 2)
check("grouping caveat disclosed in meta", "listed under each" in h)

# GroupBy=none so the sort can be read as one flat sequence (with gender
# grouping still on, the sort correctly applies *within* each section).
h = run(NEW, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906", SortBy="subgroup", Col1="subgroup", GroupBy="none")
order = names_in_order(h)
check("sorted by sub-group, no-sub-group member last",
      order == ["Alice Adams", "Frank Fox", "Bob Baker", "Dave Diaz", "Carol Chen"], repr(order))
check("sort keeps Leaders-first tiebreak inside one sub-group (Alice 140 before Frank 220)",
      order.index("Alice Adams") < order.index("Frank Fox"), repr(order))
h_gender = run(NEW, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906", SortBy="subgroup", GroupBy="gender")
check("sub-group sort applies within gender sections, sections intact",
      headings(h_gender) == ["Men (3)", "Women (2)"], repr(headings(h_gender)))
check("sort-by note appears in meta", "sorted by sub-group" in h)

# =====================================================================
print("\n=== 4. MULTI-INVOLVEMENT: identically-named sub-groups must not merge ===")
h = run(NEW, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906,4133", GroupBy="subgroup")
hd = headings(h)
check("sections are prefixed with the involvement",
      all(":" in x for x in hd if not x.startswith("(No")), repr(hd))
check("the two 'Table 1' sub-groups stay separate",
      len([x for x in hd if "Table 1" in x]) == 2, repr(hd))
check("single-involvement labels stay unprefixed",
      all(":" not in x for x in headings(run(NEW, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906", GroupBy="subgroup"))))

# =====================================================================
print("\n=== 5. BUILDER SCREENS render ===")
h1 = run(NEW, subgroups=SG)
check("stage 1 lists ministries", "Adult Discipleship" in h1 and "1. Ministry" in h1)
h2 = run(NEW, subgroups=SG, ProgId="1119")
check("stage 2 lists divisions", "AD ReNew" in h2 and "2. Division" in h2)
h3 = run(NEW, subgroups=SG, ProgId="1119", DivId="126")
check("stage 3 shows sub-group counts per involvement", "sub-group" in h3 and 'data-subgroups="2"' in h3)
check("stage 3 emits the JS availability map", "ORG_SUBGROUPS" in h3)
check("stage 3 offers a Sort dropdown", 'name="SortBy"' in h3)
h3n = run(NEW, subgroups=NOSG, ProgId="1119", DivId="126")
check("stage 3 with no sub-groups reports zero", 'data-subgroups="0"' in h3n)
check("brand navy present in builder CSS", "#0C2340" in h3 and "#FFD242" in h3)

print("\n=== 5b. STEP 1 SEARCH ===")
check("search input rendered", 'id="orgSearch"' in h3)
check("clear-search button rendered", 'id="orgSearchClear"' in h3)
check("no-results message rendered", 'id="noResults"' in h3)
check("selection/־count meta line rendered".replace("־",""), 'id="listMeta"' in h3)
check("every involvement carries a lowercased searchable name",
      h3.count('data-name="') == len(ORGS))
check("searchable name is lowercased for case-insensitive matching",
      'data-name="renew fall 2026"' in h3)
check("filtering uses a class, not the hidden attribute (.rr-orgcb sets display:block)",
      ".rr-hide { display: none !important; }" in h3 and "classList.add('rr-hide')" in h3)
check("a search never unchecks a hidden involvement",
      "still included" in h3 and "checked[i].parentNode.classList.contains('rr-hide')" in h3)

print("\n=== 5c. EMBEDDING IN TOUCHPOINT'S PAGE ===")
# The script's HTML is injected into a TouchPoint page carrying its own
# Bootstrap-derived stylesheet. Generic class names collided there on the
# first live run (a host `.church { display:none }` blanked the header's
# eyebrow, a host `.bar { padding:0 !important }` flattened the header bar),
# so every class is prefixed AND every rule is scoped under a wrapper id.
for label, page in (("stage 1", h1), ("stage 2", h2), ("stage 3", h3),
                    ("roster", run(NEW, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906"))):
    check("%s wraps its content in the scoping element" % label,
          'id="rpcAttendanceRoster"' in page)
    check("%s scopes every CSS rule under that id" % label,
          "#rpcAttendanceRoster" in page)
    check("%s styles the wrapper, never TouchPoint's own <body>" % label,
          not re.search(r"(?m)^\s*body\s*\{", page))
    check("%s uses only prefixed class names" % label,
          not re.search(r'class="(?!rr-)(bar|church|wrap|steps|meta|back|card|field|'
                        r'orglist|orgcb|cnt|hint|status|searchrow|listmeta|noresults|'
                        r'count|mark|total|section|no-print)\b', page))
check("@page survives scoping unprefixed (it takes no selector)",
      "@page { size: landscape" in run(NEW, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906"))
check("no stale 'Step 2' wording after the legend rename", "Step 2" not in h3)

# =====================================================================
print("\n=== 6. ROW-LEVEL SECURITY unchanged ===")
old_admin = run(OLD, user_id=7059, subgroups=NOSG, ProgId="1119", DivId="126", OrgIds="3906")
new_admin = run(NEW, user_id=7059, subgroups=SG, ProgId="1119", DivId="126", OrgIds="3906")
check("admin bypass still returns the same roster", tbody(old_admin) == tbody(new_admin))
nonadmin = run(NEW, user_id=99999, subgroups=SG)
check("non-admin still hits the RLS-filtered program query", "Choose a Ministry" in nonadmin)

print("\n" + "="*60)
print("FAILURES: %d" % len(fails))
for f in fails:
    print("  - " + f)
sys.exit(1 if fails else 0)
