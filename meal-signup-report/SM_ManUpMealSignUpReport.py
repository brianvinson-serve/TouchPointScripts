"""
SM_ManUpMealSignUpReport.py

TouchPoint Special Content (Python Script). Read-only.

Reports who signed up to bring/lead a meal for the "SM: Man Up Meal Sign Up"
registration (OrganizationId 4053), one row per night claimed (duplicate
nights for the same person are flagged, not silently merged), sorted by
calendar date. Also diffs claimed nights against the full list of nights
offered on the registration form's "choose a night" question and reports
which nights are still missing (no signup).

Deploy: Admin > Advanced > Special Content > Python Scripts > +New
Script name suggestion: SM_ManUpMealSignUpReport
Run directly in TouchPoint; renders an HTML report, no email sent.

Config values to update if this is reused for a different sign-up event:
    ORG_ID            -- Organizations.OrganizationId for the registration
    NIGHT_QUESTION_ID -- RegQuestion.RegQuestionId for the "choose a night"
                         question (find it with the SQL in
                         find_night_question.sql in this folder)
"""

import re
import json
from datetime import date

# ============================================================
# Config
# ============================================================
ORG_ID = 4053
NIGHT_QUESTION_ID = "fd1504b9-4cfd-4252-a0f3-f1a34c517c4d"

# Month >= this value is treated as the earlier calendar year (school-year
# sign-up spans two calendar years); months below it are the following year.
FALL_MONTH_CUTOFF = 8
FALL_YEAR = 2026
SPRING_YEAR = 2027

# ============================================================
# SQL: registrants + their raw answer value for the night question
# ============================================================
sql_registrants = """
SELECT
    p.PeopleId,
    p.Name,
    p.CellPhone,
    p.EmailAddress,
    r.CreatedDate AS RegisteredOn,
    ra.AnswerValue AS RawAnswer
FROM dbo.Registration r
JOIN dbo.RegPeople rp ON rp.RegistrationId = r.RegistrationId
JOIN dbo.RegAnswer ra ON ra.RegPeopleId = rp.RegPeopleId
                     AND ra.RegQuestionId = '{question_id}'
JOIN dbo.People p ON p.PeopleId = r.PeopleId
WHERE r.OrganizationId = {org_id}
ORDER BY p.Name
""".format(question_id=NIGHT_QUESTION_ID, org_id=ORG_ID)

# ============================================================
# SQL: the full list of nights actually offered on the form
# ============================================================
sql_options = """
SELECT Options
FROM dbo.RegQuestion
WHERE RegQuestionId = '{question_id}'
""".format(question_id=NIGHT_QUESTION_ID)


# ============================================================
# Parsing helpers
# ============================================================
DATE_LINE_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})\s+(.*\S)?\s*$")


def infer_year(month):
    return FALL_YEAR if month >= FALL_MONTH_CUTOFF else SPRING_YEAR


def parse_night_line(raw_line):
    """Parse a single 'M/D Meal description' line into (date, meal_text)."""
    m = DATE_LINE_RE.match(raw_line)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    meal_text = (m.group(3) or "").strip()
    try:
        d = date(infer_year(month), month, day)
    except ValueError:
        return None
    return d, meal_text


def split_answer_value(raw):
    """
    RegAnswer.AnswerValue for a multi-select question comes back as a
    JSON-style array of strings, e.g.:
        ["9/16 Nacho Bar","4/14 Hot Dogs"]
    Fall back to treating the whole value as one line if it isn't JSON
    (defensive -- some TouchPoint versions/questions store this as a
    plain delimited string instead).
    """
    if raw is None:
        return []
    raw = raw.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        return [str(parsed)]
    except (ValueError, TypeError):
        pass
    # Fallback: split on common delimiters TouchPoint sometimes uses
    parts = re.split(r"\r\n|\n|;", raw)
    return [p for p in parts if p.strip()]


def split_options_field(raw):
    """
    RegQuestion.Options holds the full picklist offered on the form as a
    JSON array of option objects, e.g.:
        [{"Name":null,"Value":"8/26","Text":"8/26 Hot Dogs ...","Limit":1,...}, ...]
    Confirmed live 2026-08-17 against RegQuestionId
    fd1504b9-4cfd-4252-a0f3-f1a34c517c4d. Each object's "Text" field is the
    same 'M/D Meal description' shape used in RegAnswer.AnswerValue, so it
    can be parsed with the same parse_night_line() used for answers.
    Falls back to a plain newline split if the value isn't valid JSON, in
    case a different TouchPoint version/question stores this differently.
    """
    if not raw:
        return []
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            lines = []
            for item in parsed:
                if isinstance(item, dict):
                    text = item.get("Text") or item.get("Value") or ""
                else:
                    text = str(item)
                if text:
                    lines.append(text)
            return lines
    except (ValueError, TypeError):
        pass
    parts = re.split(r"\r\n|\n", raw)
    return [p for p in parts if p.strip()]


# ============================================================
# Run queries
# ============================================================
registrant_rows = list(q.QuerySql(sql_registrants))
option_rows = list(q.QuerySql(sql_options))

# ------------------------------------------------------------
# Build one row per claimed night (flagging duplicates per person)
# ------------------------------------------------------------
claimed = []
for r in registrant_rows:
    lines = split_answer_value(getattr(r, "RawAnswer", ""))
    for i, line in enumerate(lines):
        parsed = parse_night_line(line)
        if not parsed:
            continue
        night_date, meal_text = parsed
        claimed.append(
            {
                "date": night_date,
                "meal": meal_text,
                "name": getattr(r, "Name", ""),
                "phone": getattr(r, "CellPhone", "") or "",
                "email": getattr(r, "EmailAddress", "") or "",
                "registered_on": getattr(r, "RegisteredOn", None),
                "duplicate": i > 0,
            }
        )

claimed.sort(key=lambda row: row["date"])

claimed_dates = {row["date"] for row in claimed}

# ------------------------------------------------------------
# Build the full list of offered nights from RegQuestion.Options
# ------------------------------------------------------------
offered_dates = []
if option_rows:
    raw_options = getattr(option_rows[0], "Options", "") or ""
    for line in split_options_field(raw_options):
        parsed = parse_night_line(line)
        if parsed:
            offered_dates.append(parsed[0])
offered_dates = sorted(set(offered_dates))

missing_dates = [d for d in offered_dates if d not in claimed_dates]

# ============================================================
# Render HTML report (screen only -- no email sent)
# ============================================================
def fmt_date(d):
    # Avoid %-m/%-d (GNU/Unix-only strftime flags that raise or render
    # garbage under TouchPoint's Windows/IronPython runtime). Build the
    # no-leading-zero M/D/YYYY string manually instead.
    if not d:
        return ""
    return "{}/{}/{}".format(d.month, d.day, d.year)


def esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


rows_html = []
for row in claimed:
    dup_badge = (
        '<span style="color:#b00;font-weight:bold;">duplicate row</span>'
        if row["duplicate"]
        else ""
    )
    rows_html.append(
        "<tr>"
        "<td>{date}</td><td>{name}</td><td>{meal}</td>"
        "<td>{phone}</td><td>{email}</td><td>{dup}</td>"
        "</tr>".format(
            date=fmt_date(row["date"]),
            name=esc(row["name"]),
            meal=esc(row["meal"]),
            phone=esc(row["phone"]),
            email=esc(row["email"]),
            dup=dup_badge,
        )
    )

missing_html = "".join(
    "<li>{}</li>".format(fmt_date(d)) for d in missing_dates
) or "<li><em>None -- every offered night has at least one signup.</em></li>"

if not offered_dates:
    missing_note = (
        "<p><em>Could not read RegQuestion.Options for question {qid}. "
        "Missing-night comparison is unavailable; only the signed-up list "
        "below is reliable.</em></p>"
    ).format(qid=esc(NIGHT_QUESTION_ID))
else:
    missing_note = ""

print(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Man Up Meal Sign-Up Report</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 20px; color: #222; }}
  h1 {{ font-size: 20px; }}
  h2 {{ font-size: 16px; margin-top: 30px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 13px; text-align: left; }}
  th {{ background: #f2f2f2; }}
  ul {{ font-size: 14px; }}
</style>
</head>
<body>
<h1>SM: Man Up Meal Sign Up -- Signup Report</h1>
<p>Organization {org_id} &middot; {claimed_count} night(s) claimed by {people_count} unique person(people).</p>

<h2>Signed-Up Nights (sorted by date)</h2>
<table>
<tr><th>Date</th><th>Name</th><th>Meal</th><th>Phone</th><th>Email</th><th>Note</th></tr>
{rows}
</table>

<h2>Missing Nights (offered on the form, nobody signed up)</h2>
{missing_note}
<ul>
{missing}
</ul>

</body>
</html>""".format(
        org_id=ORG_ID,
        claimed_count=len(claimed),
        people_count=len(set(r["name"] for r in claimed)),
        rows="".join(rows_html),
        missing_note=missing_note,
        missing=missing_html,
    )
)
