"""
TP_DuplicatePersonFinder.py

TouchPoint Special Content (Python Script). Read-only.

Fuzzy-match audit report for likely duplicate People records, aimed at the
"duplicates coming through registrations" problem raised at the 2026-08-26
TouchPoint summit roundtable: a person fills out an online registration form,
TouchPoint's own matching fails to find their existing record (nickname,
typo, missing field), and a brand new People row gets created instead of
attaching to the existing one.

This is NOT a replacement for TouchPoint's native duplicate tooling
(dbo.Duplicate / dbo.DuplicatesRun / dbo.MergeHistory, People.HasDuplicates)
-- it is a gap-filler. RPC's native finder found only ~21 candidate pairs as
of 2026-08-26 (per live schema inspection), and per Brian it does not catch
nickname variants (e.g. Jonathan / Johnny / Jon) -- it appears to key on
close/exact name matches. This script adds a nickname-aware + fuzzy-string
layer, deliberately EXCLUDES any pair already tracked in dbo.Duplicate (so it
only surfaces what the native tool is missing), and does not touch People,
Registration, Duplicate, or any other table -- it only ever reads.

This script never merges records. Merging is destructive (identity
collapse, FK cascade across dozens of tables) and TouchPoint's own Admin
merge tool already does that correctly -- every row here links to each
person's TouchPoint profile so staff can review and merge there themselves.

## How it works (full detail in duplicate-finder/README.md)

1. Pull the "recent" set: People created in the last LOOKBACK_DAYS (proxy
   for "came in through a recent registration" -- see ORIGIN_FILTER_IDS
   below for a tighter filter once confirmed live).
2. Find candidate matches via SQL-side "blocking": a UNION of single-key
   joins (not one big OR -- see the SQL performance note in the README)
   catches a SOUNDEX-equivalent last name, a matching email (full address
   or local-part only, so a domain typo still blocks in), a matching
   phone (cell/home/work), or a birth date that's exact or a documented
   near-miss (day/month transposed, year off by <=9, day off by one).
3. In Python, score each pair 0-100: nickname-aware + fuzzy first/last
   name matching (pure-Python Levenshtein -- no pip packages available in
   this sandbox), FUZZY email/phone/DOB scoring (a typo/transposition
   earns partial credit, not zero), and two household-aware adjustments:
   shared contact info between different people in an already-linked
   household is NOT scored as duplicate evidence, and a not-yet-linked
   household pair (e.g. siblings) is routed to its own report section
   instead of the duplicate tiers.
4. Exclude any pair already present in dbo.Duplicate (either column order).
5. Render an HTML report grouped by confidence tier (High/Medium/Low) plus
   the separate household-link section, each row linking to both people's
   TouchPoint profiles.

## Needs live TouchPoint confirmation before this is trusted as-is

- ORIGIN_FILTER_IDS is None (i.e. "any source") because People.OriginId's
  live value-to-label mapping (`SELECT Id, Description FROM lookup.Origin`)
  has not been confirmed at RPC yet. Once confirmed, set it to the
  Id(s) meaning "Web"/"Online Registration" to narrow the recent set to
  actual registration-created records instead of every new record.
- SOUNDEX blocking performance against RPC's live People table size is
  unverified -- MAX_RECENT_ROWS below is a defensive cap; lower it if the
  live run is slow.
- The nickname table is a general-purpose common-English list, not
  RPC-specific -- extend NICKNAME_CLUSTERS as real misses turn up.

Deploy: Admin > Advanced > Special Content > Python Scripts > +New
Script name suggestion: TP_DuplicatePersonFinder (named generically, not
RPC_-prefixed like this repo's other RockPointe-specific scripts, since
this one has no RPC-specific IDs/names and is portable to any TouchPoint
church as-is -- see duplicate-finder/README.md's Portability section).
Access via /PyScript/TP_DuplicatePersonFinder (or the Special Content
admin "run" preview -- this report takes no user input, so either works).
No email is sent; no data is written.
"""

import re

# ============================================================
# Config
# ============================================================

# How far back to look for "recently created" People records.
# Overridable per-run via ?Days=NN in the URL.
LOOKBACK_DAYS = 120

# Safety cap on how many recent records get fuzzy-matched in one run.
# If RPC's live People table makes this slow, lower this first.
MAX_RECENT_ROWS = 500

# Cap on how many candidate matches are shown per recent person, so one
# extremely common last name (e.g. "Smith") can't flood the report.
MAX_CANDIDATES_PER_PERSON = 5

# Once confirmed via `SELECT Id, Description FROM lookup.Origin`, set this
# to the OriginId(s) meaning "Web"/"Online Registration" to narrow the
# recent set to registration-created records specifically. None = any
# source (current default, since the mapping isn't confirmed yet).
ORIGIN_FILTER_IDS = None

# Composite score tiers (0-100 scale -- see score_pair()).
TIER_HIGH_MIN = 70
TIER_MEDIUM_MIN = 45

# Minimum fuzzy-similarity ratio (0-1, pure-Python Levenshtein ratio) for a
# near-miss email/phone to earn partial credit in scoring -- e.g. a single
# transposed digit or misspelled domain. Below this, two values are treated
# as unrelated rather than "close." A phone ratio of 0.8 on a 10-digit
# number allows roughly a 2-digit difference; an email ratio of 0.82 allows
# roughly a couple of character difference on a typical address length.
PHONE_FUZZY_MIN = 0.80
EMAIL_FUZZY_MIN = 0.82

# Minimum first-name score (see first_name_score()) for a SAME-HOUSEHOLD
# pair's shared email/phone to count as duplicate-identity evidence.
# Household members (spouses, siblings, a parent + a child with no email of
# their own) routinely and legitimately share one phone/email -- that's
# expected, not suspicious. Confirmed via live 2026-08-26 report output:
# unrelated first names (e.g. "Esther"/"Trinity", "Jett"/"Olivia") in the
# same family, sharing contact info, were scoring 75/100 High purely off
# last-name + shared household contact, with zero name evidence they're the
# same individual. Below this threshold, email/phone contribute nothing to
# the score for a same-family pair; at or above it (exact/nickname/fuzzy
# name match), the pair might genuinely be the same person who happens to
# share a household, so full credit still applies.
FAMILY_CONTACT_NAME_MIN = 0.5

# Minimum last-name similarity, and minimum number of corroborating contact
# signals (email/phone/DOB, counting "match" or "similar" as one each), for
# a pair to be flagged as a probable HOUSEHOLD LINK GAP rather than either
# a duplicate or nothing -- see household_link_gap() below. Kept high/
# strict on purpose: this flag implies a data-maintenance action ("check
# whether these should be linked"), not just "no evidence of anything."
HOUSEHOLD_GAP_LAST_NAME_MIN = 0.85
HOUSEHOLD_GAP_MIN_SIGNALS = 2

# Common English nickname/full-name clusters. Not exhaustive -- extend as
# real misses come up. Matching is case-insensitive and set-based (any name
# in a person's {FirstName, NickName, PreferredName} is checked against any
# name in the other person's set).
NICKNAME_CLUSTERS = [
    {"jonathan", "jon", "johnny", "john", "jack"},
    {"michael", "mike", "mikey", "mick", "micky"},
    {"william", "will", "bill", "billy", "liam", "willy"},
    {"robert", "rob", "bob", "bobby", "robbie"},
    {"richard", "rich", "rick", "ricky", "dick"},
    {"james", "jim", "jimmy", "jamie"},
    {"thomas", "tom", "tommy"},
    {"daniel", "dan", "danny"},
    {"christopher", "chris", "topher", "kit"},
    {"matthew", "matt", "matty"},
    {"david", "dave", "davy", "davey"},
    {"steven", "stephen", "steve", "stevie"},
    {"andrew", "andy", "drew"},
    {"benjamin", "ben", "benny", "benji"},
    {"joseph", "joe", "joey", "jos"},
    {"anthony", "tony"},
    {"edward", "ed", "eddie", "ted", "teddy"},
    {"kenneth", "ken", "kenny"},
    {"lawrence", "larry"},
    {"francis", "frank", "frankie", "franklin"},
    {"gregory", "greg", "gregg"},
    {"patrick", "pat", "paddy"},
    {"nicholas", "nick", "nicky"},
    {"samuel", "sam", "sammy"},
    {"alexander", "alex", "xander", "al"},
    {"nathaniel", "nathan", "nate"},
    {"zachary", "zach", "zack"},
    {"tobias", "toby"},
    {"gabriel", "gabe"},
    {"manuel", "manny"},
    {"frederick", "fred", "freddy"},
    {"theodore", "ted", "teddy", "theo"},
    {"charles", "charlie", "chuck", "chas"},
    {"donald", "don", "donnie"},
    {"douglas", "doug"},
    {"harold", "harry", "hal"},
    {"henry", "hank", "harry"},
    {"raymond", "ray"},
    {"ronald", "ron", "ronnie"},
    {"russell", "russ"},
    {"timothy", "tim", "timmy"},
    {"walter", "walt", "wally"},
    {"jeffrey", "jeff", "geoff"},
    {"peter", "pete", "petey"},
    {"philip", "phillip", "phil"},
    {"vincent", "vince", "vinny"},
    {"albert", "al", "bert"},
    {"arthur", "art", "artie"},
    {"eugene", "gene"},
    {"leonard", "leo", "lenny"},
    {"martin", "marty"},
    {"norman", "norm"},
    {"stanley", "stan"},
    {"victor", "vic"},
    {"elizabeth", "liz", "beth", "betty", "betsy", "eliza", "libby", "ellie"},
    {"katherine", "catherine", "kate", "katie", "kathy", "cathy", "kat", "katy"},
    {"margaret", "maggie", "meg", "peggy", "peg", "margie", "marge"},
    {"susan", "sue", "suzy", "susie"},
    {"jennifer", "jen", "jenny"},
    {"patricia", "pat", "patty", "tricia", "trish"},
    {"deborah", "debra", "deb", "debbie"},
    {"barbara", "barb", "barbie"},
    {"cynthia", "cindy"},
    {"christina", "christine", "chris", "tina", "christy"},
    {"stephanie", "steph"},
    {"victoria", "vicky", "vicki", "tori"},
    {"rebecca", "becky", "becca"},
    {"amanda", "mandy"},
    {"jessica", "jess", "jessie"},
    {"samantha", "sam", "sammy"},
    {"alexandra", "alex", "sandra", "sandy", "lexi"},
    {"abigail", "abby", "gail"},
    {"virginia", "ginny", "ginger"},
    {"theresa", "teresa", "terri", "tessa"},
    {"kimberly", "kim", "kimmy"},
    {"melissa", "missy", "mel"},
    {"michelle", "shelly", "chelle"},
    {"nicole", "nikki"},
    {"pamela", "pam"},
    {"diane", "diana", "di"},
    {"julia", "julie", "jules"},
    {"caroline", "carol", "carrie", "carly"},
    {"anna", "annie", "ann", "anne"},
    {"emily", "em", "emmy"},
    {"gabrielle", "gabby"},
    {"isabelle", "isabella", "izzy", "bella"},
    {"olivia", "liv", "livvy"},
    {"sophia", "sophie"},
    {"natalie", "nat", "nattie"},
    {"veronica", "ronnie", "roni"},
]

NICKNAME_CLUSTER_INDEX = {}
for _cluster_id, _cluster in enumerate(NICKNAME_CLUSTERS):
    for _name in _cluster:
        NICKNAME_CLUSTER_INDEX[_name] = _cluster_id


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


def to_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def norm_str(value):
    return str(value or "").strip().lower()


def norm_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-10:] if len(digits) >= 10 else ""


def levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def string_ratio(a, b):
    a, b = norm_str(a), norm_str(b)
    if not a or not b:
        return 0.0
    dist = levenshtein(a, b)
    return 1.0 - (float(dist) / max(len(a), len(b)))


def name_variants(*names):
    return {norm_str(n) for n in names if norm_str(n)}


def first_name_score(names_a, names_b):
    if not names_a or not names_b:
        return 0.0
    best = 0.0
    for a in names_a:
        for b in names_b:
            if a == b:
                best = max(best, 1.0)
                continue
            cluster_a = NICKNAME_CLUSTER_INDEX.get(a)
            cluster_b = NICKNAME_CLUSTER_INDEX.get(b)
            if cluster_a is not None and cluster_a == cluster_b:
                best = max(best, 0.9)
                continue
            best = max(best, string_ratio(a, b) * 0.75)
    return best


def best_ratio(values_a, values_b):
    """Best pairwise Levenshtein ratio across two sets of non-empty strings.
    1.0 means some pair is an exact match; 0.0 means no data to compare."""
    best = 0.0
    for a in values_a:
        for b in values_b:
            if a == b:
                return 1.0
            best = max(best, string_ratio(a, b))
    return best


def dob_score(p1, p2):
    """0.0-1.0 date-of-birth closeness. Full birth date only (BirthYear /
    BirthMonth / BirthDay all present on both sides) -- returns 0.0 if
    either side is missing any part, since a partial DOB isn't strong
    enough evidence either way.

    Modeled on documented record-linkage practice: day/month transposition
    (e.g. 5/14 entered as 14/5) is a well-known common data-entry error
    worth matching explicitly rather than treating as a mismatch, and a
    single mis-typed digit in the birth year or day should earn partial
    credit rather than being scored identically to two unrelated dates.
    A clear, unexplainable mismatch stays at 0.0 (neutral) rather than
    penalizing the composite score -- this tool only adds corroborating
    evidence, it doesn't rule pairs out on a single field.
    """
    y1, m1, d1 = p1.BirthYear, p1.BirthMonth, p1.BirthDay
    y2, m2, d2 = p2.BirthYear, p2.BirthMonth, p2.BirthDay
    if not (y1 and y2 and m1 and m2 and d1 and d2):
        return 0.0
    if y1 == y2 and m1 == m2 and d1 == d2:
        return 1.0
    # Day/month transposed (14/5 vs 5/14) -- common manual-entry mistake.
    if y1 == y2 and m1 == d2 and d1 == m2 and m1 != d1:
        return 0.85
    # Month/day exact, birth year off by a small amount -- plausible
    # single fat-fingered digit in a 4-digit year (e.g. 1990 vs 1998).
    if m1 == m2 and d1 == d2 and y1 != y2 and abs(y1 - y2) <= 9:
        return 0.55
    # Year/month exact, day off by one -- plausible fat-finger/off-by-one.
    if y1 == y2 and m1 == m2 and d1 != d2 and abs(d1 - d2) == 1:
        return 0.6
    return 0.0


def score_pair(p1, p2):
    """Returns (score 0-100, signals dict) for a candidate pair."""
    last_score = 1.0 if norm_str(p1.LastName) == norm_str(p2.LastName) and norm_str(p1.LastName) else string_ratio(p1.LastName, p2.LastName)

    names_a = name_variants(p1.FirstName, p1.NickName, p1.PreferredName)
    names_b = name_variants(p2.FirstName, p2.NickName, p2.PreferredName)
    first_score = first_name_score(names_a, names_b)

    # Fuzzy, not just exact -- a fat-fingered digit/character still earns
    # partial credit instead of contributing nothing (PHONE_FUZZY_MIN /
    # EMAIL_FUZZY_MIN gate out unrelated values that happen to share a few
    # characters by chance).
    emails_a = {norm_str(p1.EmailAddress), norm_str(p1.EmailAddress2)} - {""}
    emails_b = {norm_str(p2.EmailAddress), norm_str(p2.EmailAddress2)} - {""}
    email_ratio = best_ratio(emails_a, emails_b)
    email_match = email_ratio >= 0.999
    email_similar = EMAIL_FUZZY_MIN <= email_ratio < 0.999

    phones_a = {norm_phone(p1.CellPhone), norm_phone(p1.HomePhone), norm_phone(p1.WorkPhone)} - {""}
    phones_b = {norm_phone(p2.CellPhone), norm_phone(p2.HomePhone), norm_phone(p2.WorkPhone)} - {""}
    phone_ratio = best_ratio(phones_a, phones_b)
    phone_match = phone_ratio >= 0.999
    phone_similar = PHONE_FUZZY_MIN <= phone_ratio < 0.999

    dob_ratio = dob_score(p1, p2)
    dob_match = dob_ratio >= 0.999
    dob_similar = 0 < dob_ratio < 0.999

    same_family = bool(p1.FamilyId and p2.FamilyId and p1.FamilyId == p2.FamilyId)

    # Household members routinely and legitimately share one phone/email --
    # a parent and a child with no email of their own, or siblings on a
    # family plan. That's expected, not evidence of duplicate identity.
    # Only let shared contact info count toward the score for a same-family
    # pair when the names ALSO look like they could be the same person
    # (exact/nickname/fuzzy) -- otherwise it's just "this household shares
    # a phone," which every correctly-modeled family does.
    family_dampened = same_family and first_score < FAMILY_CONTACT_NAME_MIN

    # Same shape, but NOT yet linked as a household in TouchPoint (no
    # shared FamilyId): near-identical last name, a first name that clearly
    # ISN'T the same person, and at least two independent corroborating
    # signals (email/phone/DOB). This is very likely two different family
    # members (e.g. siblings/twins) whose records simply haven't been
    # linked into the same household yet -- not a duplicate-identity case,
    # but a real, separate, human-actionable data-quality gap (confirm/fix
    # the family link). Flagged live 2026-08-27: "Seth O'Brien" / "Natalie
    # O'Brien" scored 92 High as a false "duplicate" under the pre-this-fix
    # logic purely because FamilyId happened to differ.
    signal_count = sum([
        email_match or email_similar,
        phone_match or phone_similar,
        dob_match or dob_similar,
    ])
    household_link_gap = (
        not same_family
        and last_score >= HOUSEHOLD_GAP_LAST_NAME_MIN
        and first_score < FAMILY_CONTACT_NAME_MIN
        and signal_count >= HOUSEHOLD_GAP_MIN_SIGNALS
    )

    dampened = family_dampened or household_link_gap
    scored_email_ratio = 0.0 if dampened else email_ratio
    scored_phone_ratio = 0.0 if dampened else phone_ratio

    score = (last_score * 30) + (first_score * 30)
    score += 25 * scored_email_ratio if scored_email_ratio >= EMAIL_FUZZY_MIN else 0
    score += 20 * scored_phone_ratio if scored_phone_ratio >= PHONE_FUZZY_MIN else 0
    score += 25 * dob_ratio
    # int(round(...)), not round(...) -- some Python runtimes (incl. the
    # one TouchPoint's Python Scripts run under) always return a float from
    # round(), so an un-cast score prints as "75.0" while a score that hits
    # the min(100, ...) cap happens to keep the plain int 100 literal --
    # same value, inconsistent display. Force plain int everywhere.
    score = min(100, int(round(score)))

    return score, {
        "last_score": last_score,
        "first_score": first_score,
        # These reflect what was actually FOUND (for badge display), even
        # when family_dampened kept them out of the score -- so a reviewer
        # can still see "yes, they share a phone" and understand why that
        # didn't count for anything.
        "email_match": email_match,
        "email_similar": email_similar,
        "phone_match": phone_match,
        "phone_similar": phone_similar,
        "dob_match": dob_match,
        "dob_similar": dob_similar,
        "same_family": same_family,
        "family_dampened": family_dampened,
        "household_link_gap": household_link_gap,
    }


def tier_for(score):
    if score >= TIER_HIGH_MIN:
        return "High"
    if score >= TIER_MEDIUM_MIN:
        return "Medium"
    return "Low"


def display_name(p):
    return (
        (p.PreferredName or p.NickName or p.FirstName or "").strip()
        + " "
        + (p.LastName or "").strip()
    ).strip() or "(no name)"


def signal_badges(signals):
    # NOTE: email/phone are the only signals ever dampened (see score_pair)
    # -- DOB always reflects real scoring evidence, so it's shown the same
    # way regardless of family_dampened. An earlier version of this
    # function returned early on family_dampened and silently hid a real
    # DOB-match badge in that case -- fixed 2026-08-27.
    badges = []

    if signals["family_dampened"]:
        # Shared contact info here is fully explained by "this is a
        # household" -- the names don't suggest it's also the same person,
        # so email/phone did NOT count toward the score. Say so plainly
        # rather than showing "Email match"/"Phone match" as if they did.
        if signals["email_match"] or signals["email_similar"]:
            badges.append('<span class="badge badge-muted">Email shared (household, not scored)</span>')
        if signals["phone_match"] or signals["phone_similar"]:
            badges.append('<span class="badge badge-muted">Phone shared (household, not scored)</span>')
    else:
        if signals["email_match"]:
            badges.append('<span class="badge badge-email">Email match</span>')
        elif signals["email_similar"]:
            badges.append('<span class="badge badge-email-similar">Similar email</span>')
        if signals["phone_match"]:
            badges.append('<span class="badge badge-phone">Phone match</span>')
        elif signals["phone_similar"]:
            badges.append('<span class="badge badge-phone-similar">Similar phone</span>')

    if signals["dob_match"]:
        badges.append('<span class="badge badge-dob">DOB match</span>')
    elif signals["dob_similar"]:
        badges.append('<span class="badge badge-dob-similar">Similar DOB</span>')

    if signals["same_family"]:
        badges.append('<span class="badge badge-family">Same household</span>')

    return " ".join(badges)


def person_link(cms_host, p):
    return '<a href="{host}/Person2/{pid}#tab-touchpoints" target="_blank">{name}</a>'.format(
        host=cms_host, pid=p.PeopleId, name=esc(display_name(p))
    )


# ============================================================
# Query params
# ============================================================
lookback_days = to_int(getattr(model.Data, "Days", ""), LOOKBACK_DAYS)
if lookback_days <= 0:
    lookback_days = LOOKBACK_DAYS

origin_filter_sql = ""
if ORIGIN_FILTER_IDS:
    origin_filter_sql = "AND p.OriginId IN ({0})".format(
        ", ".join(str(i) for i in ORIGIN_FILTER_IDS)
    )

# ============================================================
# SQL: recent People (candidate "just registered" set)
# ============================================================
sql_recent = """
SELECT TOP {max_recent}
    p.PeopleId, p.FirstName, p.NickName, p.PreferredName, p.LastName,
    p.EmailAddress, p.EmailAddress2, p.CellPhone, p.HomePhone, p.WorkPhone,
    p.BirthYear, p.BirthMonth, p.BirthDay, p.FamilyId, p.CreatedDate
FROM dbo.People p
WHERE p.CreatedDate >= DATEADD(day, -{days}, GETDATE())
  AND ISNULL(p.ArchivedFlag, 0) = 0
  AND ISNULL(p.IsDeceased, 0) = 0
  AND ISNULL(p.IsBusiness, 0) = 0
  {origin_filter}
ORDER BY p.CreatedDate DESC
""".format(max_recent=MAX_RECENT_ROWS, days=lookback_days, origin_filter=origin_filter_sql)

recent_rows = list(q.QuerySql(sql_recent))
recent_ids_sql = ", ".join(str(r.PeopleId) for r in recent_rows) or "-1"

# ============================================================
# SQL: bulk candidate-pair pre-filter ("blocking") against the recent set.
# This only decides who's WORTH fuzzy-scoring in Python -- it is
# deliberately looser than an exact match so a fat-fingered phone/email
# still gets pulled in (fine-grained near-miss scoring happens in
# score_pair()). Excludes pairs already tracked in dbo.Duplicate.
#
#   - SOUNDEX-equivalent last name (typos, spelling variants)
#   - exact-normalized email, checked BOTH full-address (domain included)
#     and local-part-only (so a domain typo like gmial.com vs gmail.com
#     still blocks in even though the full address won't match)
#   - exact-normalized phone (punctuation/spacing stripped) -- this was
#     missing from blocking entirely before 2026-08-26; phone-only matches
#     were silently invisible to this report until this fix
#   - identical full birth date
# ============================================================
def sql_norm_phone(col):
    # Strip common phone punctuation/spacing before comparing digits.
    return (
        "NULLIF(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
        "ISNULL({0}, ''), '(', ''), ')', ''), '-', ''), ' ', ''), '.', ''), '+', ''), '')"
    ).format(col)


def sql_email_norm(col):
    return "NULLIF(LOWER(LTRIM(RTRIM({0}))), '')".format(col)


def sql_email_local_part(col):
    # Local part (before '@'), lowercased -- the '+@' trick keeps CHARINDEX
    # well-defined even for a value with no '@' at all.
    trimmed = "LTRIM(RTRIM({0}))".format(col)
    return "NULLIF(LOWER(LEFT({0}, CHARINDEX('@', {0} + '@') - 1)), '')".format(trimmed)


def sql_soundex_guarded(col):
    # SOUNDEX('') / SOUNDEX of a blank string is not NULL in SQL Server
    # (e.g. '0000') -- guard so two people with no last name don't
    # spuriously "match" each other on that alone.
    return "CASE WHEN NULLIF(LTRIM(RTRIM({0})), '') IS NULL THEN NULL ELSE SOUNDEX({0}) END".format(col)


def person_norm_select(alias):
    # Precompute every normalized/fuzzy-blocking field ONCE per row here.
    # This is the fix for the query that used to hang: comparing these
    # expressions directly in a JOIN condition forces SQL Server to
    # recompute SOUNDEX/REPLACE/CHARINDEX for every (recent, candidate)
    # PAIR -- with hundreds of recent rows against a live People table of
    # tens of thousands, that's tens of millions of expensive non-sargable
    # function calls. Computing them here, once per row, turns the join
    # into a cheap equality/hash join over plain precomputed columns.
    return """
    SELECT
        {a}.PeopleId, {a}.FirstName, {a}.NickName, {a}.PreferredName, {a}.LastName,
        {a}.EmailAddress, {a}.EmailAddress2, {a}.CellPhone, {a}.HomePhone, {a}.WorkPhone,
        {a}.BirthYear, {a}.BirthMonth, {a}.BirthDay, {a}.FamilyId,
        {lnsoundex} AS LNSoundex,
        {email1} AS EmailNorm1, {email2} AS EmailNorm2,
        {emaillocal1} AS EmailLocal1, {emaillocal2} AS EmailLocal2,
        {phone1} AS PhoneNorm1, {phone2} AS PhoneNorm2, {phone3} AS PhoneNorm3
    FROM dbo.People {a}
    """.format(
        a=alias,
        lnsoundex=sql_soundex_guarded(alias + ".LastName"),
        email1=sql_email_norm(alias + ".EmailAddress"),
        email2=sql_email_norm(alias + ".EmailAddress2"),
        emaillocal1=sql_email_local_part(alias + ".EmailAddress"),
        emaillocal2=sql_email_local_part(alias + ".EmailAddress2"),
        phone1=sql_norm_phone(alias + ".CellPhone"),
        phone2=sql_norm_phone(alias + ".HomePhone"),
        phone3=sql_norm_phone(alias + ".WorkPhone"),
    )


# NOTE: the recent side is filtered down to the (small, capped) recent-ID
# list INSIDE its own CTE, before any join happens.
#
# A second, less obvious problem showed up after the first fix (a 2026-08-26
# live test still timed out): a JOIN condition that ORs together several
# UNRELATED column pairs (last name OR email OR phone OR DOB) generally
# can't be planned by SQL Server as a single efficient hash/index join, even
# when every column involved is precomputed -- there's no single shared key
# to build a hash table on, so the optimizer commonly falls back to a
# nested-loop scan of the whole candidate set per recent row and evaluates
# the big OR as a residual filter. That's still O(recent x candidates) even
# though each individual comparison got cheaper.
#
# Fix: decompose the OR into a UNION of separate joins, each on exactly ONE
# equality key (or, for the DOB near-miss rules, a two-column equality key
# with a cheap residual range check on an already-narrowed set). SQL Server
# can plan each branch as its own efficient hash/index join; UNION then
# dedupes any pair matched by more than one signal. Email and phone are
# first "flattened" (one row per non-null value, e.g. up to 2 email rows /
# 3 phone rows per person) so the multiple candidate fields become a single
# join key too, rather than an IN-list on both sides.
sql_pairs = """
;WITH RecentNorm AS (
    {recent_norm_select}
    WHERE {a}.PeopleId IN ({recent_ids})
),
CandidateNorm AS (
    {candidate_norm_select}
    WHERE ISNULL({a}.ArchivedFlag, 0) = 0
      AND ISNULL({a}.IsDeceased, 0) = 0
      AND ISNULL({a}.IsBusiness, 0) = 0
),
RecentEmails AS (
    SELECT PeopleId, EmailNorm1 AS V FROM RecentNorm WHERE EmailNorm1 IS NOT NULL
    UNION ALL
    SELECT PeopleId, EmailNorm2 FROM RecentNorm WHERE EmailNorm2 IS NOT NULL
),
CandidateEmails AS (
    SELECT PeopleId, EmailNorm1 AS V FROM CandidateNorm WHERE EmailNorm1 IS NOT NULL
    UNION ALL
    SELECT PeopleId, EmailNorm2 FROM CandidateNorm WHERE EmailNorm2 IS NOT NULL
),
RecentEmailLocals AS (
    SELECT PeopleId, EmailLocal1 AS V FROM RecentNorm WHERE EmailLocal1 IS NOT NULL
    UNION ALL
    SELECT PeopleId, EmailLocal2 FROM RecentNorm WHERE EmailLocal2 IS NOT NULL
),
CandidateEmailLocals AS (
    SELECT PeopleId, EmailLocal1 AS V FROM CandidateNorm WHERE EmailLocal1 IS NOT NULL
    UNION ALL
    SELECT PeopleId, EmailLocal2 FROM CandidateNorm WHERE EmailLocal2 IS NOT NULL
),
RecentPhones AS (
    SELECT PeopleId, PhoneNorm1 AS V FROM RecentNorm WHERE PhoneNorm1 IS NOT NULL
    UNION ALL
    SELECT PeopleId, PhoneNorm2 FROM RecentNorm WHERE PhoneNorm2 IS NOT NULL
    UNION ALL
    SELECT PeopleId, PhoneNorm3 FROM RecentNorm WHERE PhoneNorm3 IS NOT NULL
),
CandidatePhones AS (
    SELECT PeopleId, PhoneNorm1 AS V FROM CandidateNorm WHERE PhoneNorm1 IS NOT NULL
    UNION ALL
    SELECT PeopleId, PhoneNorm2 FROM CandidateNorm WHERE PhoneNorm2 IS NOT NULL
    UNION ALL
    SELECT PeopleId, PhoneNorm3 FROM CandidateNorm WHERE PhoneNorm3 IS NOT NULL
),
MatchPairs AS (
    -- Last name (SOUNDEX-equivalent)
    SELECT r.PeopleId AS RecentId, c.PeopleId AS CandidateId
    FROM RecentNorm r JOIN CandidateNorm c
      ON c.LNSoundex = r.LNSoundex AND c.PeopleId <> r.PeopleId
    WHERE r.LNSoundex IS NOT NULL

    UNION

    -- Email, full address
    SELECT r.PeopleId, c.PeopleId
    FROM RecentEmails r JOIN CandidateEmails c
      ON c.V = r.V AND c.PeopleId <> r.PeopleId

    UNION

    -- Email, local-part only (catches a domain typo)
    SELECT r.PeopleId, c.PeopleId
    FROM RecentEmailLocals r JOIN CandidateEmailLocals c
      ON c.V = r.V AND c.PeopleId <> r.PeopleId

    UNION

    -- Phone, any of cell/home/work on either side
    SELECT r.PeopleId, c.PeopleId
    FROM RecentPhones r JOIN CandidatePhones c
      ON c.V = r.V AND c.PeopleId <> r.PeopleId

    UNION

    -- DOB: month+day exact (equality key), year within 9 -- covers an
    -- exact match (year diff 0) and a plausible single mistyped year digit
    -- in one pass; dob_score() in Python determines which of those it is.
    SELECT r.PeopleId, c.PeopleId
    FROM RecentNorm r JOIN CandidateNorm c
      ON c.BirthMonth = r.BirthMonth AND c.BirthDay = r.BirthDay AND c.PeopleId <> r.PeopleId
    WHERE r.BirthMonth IS NOT NULL AND r.BirthDay IS NOT NULL
      AND r.BirthYear IS NOT NULL AND c.BirthYear IS NOT NULL
      AND ABS(c.BirthYear - r.BirthYear) <= 9

    UNION

    -- DOB: year+month exact (equality key), day off by exactly one
    SELECT r.PeopleId, c.PeopleId
    FROM RecentNorm r JOIN CandidateNorm c
      ON c.BirthYear = r.BirthYear AND c.BirthMonth = r.BirthMonth AND c.PeopleId <> r.PeopleId
    WHERE r.BirthDay IS NOT NULL AND c.BirthDay IS NOT NULL
      AND ABS(c.BirthDay - r.BirthDay) = 1

    UNION

    -- DOB: year exact (equality key), month/day transposed (14/5 vs 5/14)
    SELECT r.PeopleId, c.PeopleId
    FROM RecentNorm r JOIN CandidateNorm c
      ON c.BirthYear = r.BirthYear AND c.BirthMonth = r.BirthDay AND c.BirthDay = r.BirthMonth
     AND c.PeopleId <> r.PeopleId
    WHERE r.BirthMonth IS NOT NULL AND r.BirthDay IS NOT NULL AND r.BirthMonth <> r.BirthDay
)
SELECT
    mp.RecentId, mp.CandidateId, c.PeopleId,
    c.FirstName, c.NickName, c.PreferredName, c.LastName,
    c.EmailAddress, c.EmailAddress2, c.CellPhone, c.HomePhone, c.WorkPhone,
    c.BirthYear, c.BirthMonth, c.BirthDay, c.FamilyId
FROM MatchPairs mp
JOIN dbo.People c ON c.PeopleId = mp.CandidateId
WHERE NOT EXISTS (
      SELECT 1 FROM dbo.Duplicate d
      WHERE (d.id1 = mp.RecentId AND d.id2 = mp.CandidateId)
         OR (d.id1 = mp.CandidateId AND d.id2 = mp.RecentId)
  )
""".format(
    recent_norm_select=person_norm_select("p"),
    candidate_norm_select=person_norm_select("p"),
    a="p",
    recent_ids=recent_ids_sql,
)

candidate_rows = list(q.QuerySql(sql_pairs)) if recent_rows else []

# ============================================================
# Python: score every candidate pair, dedupe unordered pairs, tier + sort.
# ============================================================
recent_by_id = {r.PeopleId: r for r in recent_rows}

seen_pairs = set()
scored = []
household_gaps = []
for c in candidate_rows:
    pair_key = tuple(sorted((c.RecentId, c.CandidateId)))
    if pair_key in seen_pairs:
        continue
    seen_pairs.add(pair_key)

    recent_person = recent_by_id.get(c.RecentId)
    if recent_person is None:
        continue

    score, signals = score_pair(recent_person, c)
    row = {
        "recent": recent_person,
        "candidate": c,
        "score": score,
        "signals": signals,
    }

    # Household-link-gap pairs are routed out entirely, never into the
    # duplicate tiers -- they're a different KIND of finding (a probable
    # missing family link, not a possible duplicate identity) and get their
    # own section below. Checked before the TIER_MEDIUM_MIN cutoff because
    # dampening these pairs' email/phone contribution can legitimately push
    # their score under that threshold even though the gap itself is a
    # confident, separately-thresholded signal (see HOUSEHOLD_GAP_* above).
    if signals["household_link_gap"]:
        household_gaps.append(row)
        continue

    if score < TIER_MEDIUM_MIN:
        continue

    row["tier"] = tier_for(score)
    scored.append(row)

scored.sort(key=lambda x: x["score"], reverse=True)
household_gaps.sort(key=lambda x: x["score"], reverse=True)


def cap_per_recent_person(rows):
    # Cap candidates shown per recent person (highest score first --
    # caller must already have sorted `rows` descending by score).
    per_person_count = {}
    capped = []
    for row in rows:
        rid = row["recent"].PeopleId
        per_person_count[rid] = per_person_count.get(rid, 0) + 1
        if per_person_count[rid] <= MAX_CANDIDATES_PER_PERSON:
            capped.append(row)
    return capped


scored = cap_per_recent_person(scored)
household_gaps = cap_per_recent_person(household_gaps)

tiers = {"High": [], "Medium": [], "Low": []}
for row in scored:
    tiers[row["tier"]].append(row)

# ============================================================
# Render
# ============================================================
cms_host = model.CmsHost


def build_tier_html(tier_name, rows):
    if not rows:
        return ""
    body_rows = []
    for row in rows:
        recent_p = row["recent"]
        cand_p = row["candidate"]
        body_rows.append(
            "<tr><td>{recent_link}</td><td>{cand_link}</td>"
            "<td class=\"score\">{score}</td><td>{badges}</td></tr>".format(
                recent_link=person_link(cms_host, recent_p),
                cand_link=person_link(cms_host, cand_p),
                score=row["score"],
                badges=signal_badges(row["signals"]) or "&mdash;",
            )
        )
    return """
<div class="tier tier-{tier_class}">
  <h2>{tier_name} confidence <span class="count">({count})</span></h2>
  <table>
    <thead><tr><th>Recently created</th><th>Possible existing match</th><th>Score</th><th>Signals</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
""".format(
        tier_class=tier_name.lower(),
        tier_name=esc(tier_name),
        count=len(rows),
        rows="".join(body_rows),
    )


def build_household_gap_html(rows):
    if not rows:
        return ""
    body_rows = []
    for row in rows:
        recent_p = row["recent"]
        cand_p = row["candidate"]
        body_rows.append(
            "<tr><td>{recent_link}</td><td>{cand_link}</td>"
            "<td class=\"score\">{score}</td><td>{badges}</td></tr>".format(
                recent_link=person_link(cms_host, recent_p),
                cand_link=person_link(cms_host, cand_p),
                score=row["score"],
                badges=signal_badges(row["signals"]) or "&mdash;",
            )
        )
    return """
<div class="tier tier-household">
  <h2>Household link to verify <span class="count">({count})</span></h2>
  <p class="section-note">
    These pairs are NOT flagged as possible duplicates -- their first names clearly don't match.
    They share a last name plus at least two of email/phone/birth-date, but aren't currently linked
    as the same household (<code>FamilyId</code>) in TouchPoint. That's often siblings or a
    parent/child whose records just haven't been connected yet -- worth a quick check on whether
    the family link is missing, or whether it's simply a coincidence (e.g. a shared phone with an
    unrelated person).
  </p>
  <table>
    <thead><tr><th>Recently created</th><th>Possible household match</th><th>Score</th><th>Signals</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
""".format(count=len(rows), rows="".join(body_rows))


sections_html = (
    build_tier_html("High", tiers["High"])
    + build_tier_html("Medium", tiers["Medium"])
    + build_tier_html("Low", tiers["Low"])
)

if not scored:
    sections_html = '<p class="empty">No likely duplicates found among People created in the last {0} day(s), beyond what dbo.Duplicate already tracks.</p>'.format(lookback_days)

sections_html += build_household_gap_html(household_gaps)

legend_html = """
<details class="legend" open>
  <summary>How to read this report</summary>
  <div class="legend-tiers">
    <span class="badge tier-chip tier-chip-high">High confidence</span> score &ge; {tier_high} &mdash; strong overlap, worth a close look.
    <span class="badge tier-chip tier-chip-medium">Medium confidence</span> score &ge; {tier_medium} &mdash; some overlap, less certain.
    <span class="legend-plain">Below {tier_medium} isn't shown at all.</span>
    <span class="badge tier-chip tier-chip-household">Household link to verify</span> a separate, non-duplicate finding &mdash; see below.
  </div>
  <table class="legend-table">
    <tr><td><span class="badge badge-email">Email match</span></td><td>The two records share the exact same email address.</td></tr>
    <tr><td><span class="badge badge-email-similar">Similar email</span></td><td>Close but not identical (e.g. a misspelled domain) &mdash; still corroborating, weighted less.</td></tr>
    <tr><td><span class="badge badge-phone">Phone match</span></td><td>Same phone number (cell/home/work, either side).</td></tr>
    <tr><td><span class="badge badge-phone-similar">Similar phone</span></td><td>Close but not identical (e.g. a transposed digit).</td></tr>
    <tr><td><span class="badge badge-dob">DOB match</span></td><td>Exact same birth date.</td></tr>
    <tr><td><span class="badge badge-dob-similar">Similar DOB</span></td><td>Close (e.g. day/month swapped, or one mistyped digit) &mdash; a well-known data-entry pattern.</td></tr>
    <tr><td><span class="badge badge-family">Same household</span></td><td>TouchPoint already links these two people to the same family.</td></tr>
    <tr><td><span class="badge badge-muted">Email/Phone shared (household, not scored)</span></td><td>They share contact info, but since they're already the same household and the names don't match, that's expected &mdash; it did NOT count toward the score.</td></tr>
  </table>
  <p class="legend-note">This is a review aid, not a verdict &mdash; always confirm in TouchPoint before merging a person or changing a family link.</p>
</details>
""".format(tier_high=TIER_HIGH_MIN, tier_medium=TIER_MEDIUM_MIN)

print(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Possible Duplicate People -- Last {days} Days</title>
<style>
  :root {{
    --ink: #1c2530;
    --ink-muted: #5b6673;
    --border: #e1e5ea;
    --panel: #f8f9fb;
    --email: #0b5fa5;
    --email-bg: #e8f1fa;
    --phone: #a05a00;
    --phone-bg: #faf1e3;
    --dob: #8a3d68;
    --dob-bg: #f6e9f1;
    --family: #55606b;
    --family-bg: #eef0f2;
    --high: #0b3d78;
    --medium: #3f7cc9;
    --low: #7c8a9a;
    --household: #0f766e;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    margin: 24px; color: var(--ink); background: #fff; line-height: 1.45;
  }}
  h1 {{ font-size: 21px; margin: 0 0 4px; font-weight: 600; }}
  h2 {{ font-size: 15px; margin: 0 0 4px; font-weight: 600; color: var(--ink); }}
  .meta {{ color: var(--ink-muted); font-size: 13px; margin: 0 0 16px; max-width: 900px; }}
  .count {{ font-weight: 400; color: var(--ink-muted); font-size: 12px; }}
  .empty {{ color: var(--ink-muted); }}
  .section-note {{ color: var(--ink-muted); font-size: 12px; max-width: 900px; margin: 2px 0 0; }}

  .legend {{
    border: 1px solid var(--border); border-radius: 8px; background: var(--panel);
    padding: 10px 16px; margin-bottom: 20px; max-width: 900px;
  }}
  .legend summary {{ cursor: pointer; font-weight: 600; font-size: 13px; color: var(--ink); padding: 4px 0; }}
  .legend-tiers {{ font-size: 12px; color: var(--ink-muted); margin: 10px 0; line-height: 2.1; }}
  .legend-plain {{ color: var(--ink-muted); margin-right: 6px; }}
  .legend-table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
  .legend-table td {{ border: none; padding: 3px 8px 3px 0; font-size: 12px; color: var(--ink-muted); vertical-align: middle; }}
  .legend-table td:first-child {{ white-space: nowrap; width: 1%; }}
  .legend-note {{ font-size: 11.5px; color: var(--ink-muted); margin: 8px 0 0; font-style: italic; }}

  .tier {{
    border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px;
    margin-bottom: 16px; background: #fff;
  }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
  th, td {{ border-bottom: 1px solid var(--border); padding: 8px 10px; font-size: 13px; text-align: left; }}
  th {{ background: var(--panel); font-weight: 600; color: var(--ink-muted); font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.03em; }}
  tbody tr:nth-child(even) {{ background: #fbfcfd; }}
  td.score {{ text-align: center; font-weight: 700; width: 60px; }}

  .tier-high {{ border-left: 4px solid var(--high); }}
  .tier-high h2 {{ color: var(--high); }}
  .tier-high td.score {{ color: var(--high); }}
  .tier-medium {{ border-left: 4px solid var(--medium); }}
  .tier-medium h2 {{ color: var(--medium); }}
  .tier-medium td.score {{ color: var(--medium); }}
  .tier-low {{ border-left: 4px solid var(--low); }}
  .tier-low h2 {{ color: var(--low); }}
  .tier-low td.score {{ color: var(--low); }}
  .tier-household {{ border-left: 4px solid var(--household); background: #f4faf9; }}
  .tier-household h2 {{ color: var(--household); }}
  .tier-household td.score {{ color: var(--household); }}

  .tier-chip {{ color: #fff; font-weight: 600; }}
  .tier-chip-high {{ background: var(--high); }}
  .tier-chip-medium {{ background: var(--medium); }}
  .tier-chip-household {{ background: var(--household); }}

  .badge {{ display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-right: 5px; margin-bottom: 2px; white-space: nowrap; }}
  .badge-email {{ background: var(--email); color: #fff; }}
  .badge-email-similar {{ background: var(--email-bg); color: var(--email); border: 1px solid var(--email); }}
  .badge-phone {{ background: var(--phone); color: #fff; }}
  .badge-phone-similar {{ background: var(--phone-bg); color: var(--phone); border: 1px solid var(--phone); }}
  .badge-dob {{ background: var(--dob); color: #fff; }}
  .badge-dob-similar {{ background: var(--dob-bg); color: var(--dob); border: 1px solid var(--dob); }}
  .badge-family {{ background: var(--family); color: #fff; }}
  .badge-muted {{ background: var(--family-bg); color: var(--ink-muted); border: 1px dashed #b7bfc8; font-weight: 500; }}
</style>
</head>
<body>
<h1>Possible Duplicate People</h1>
<p class="meta">
  People created in the last <strong>{days}</strong> day(s) ({recent_count} found, capped at {max_recent}),
  fuzzy-matched against the People table. Pairs already tracked in TouchPoint's native
  Duplicates list are excluded. Up to {max_per_person} match(es) shown per person, highest score first.
  This is a read-only review aid &mdash; merge records using TouchPoint's own Admin merge tool, not here.
  Add <code>?Days=NN</code> to the URL to change the lookback window.
</p>
{legend}
{sections}
</body>
</html>""".format(
        legend=legend_html,
        days=lookback_days,
        recent_count=len(recent_rows),
        max_recent=MAX_RECENT_ROWS,
        max_per_person=MAX_CANDIDATES_PER_PERSON,
        sections=sections_html,
    )
)
