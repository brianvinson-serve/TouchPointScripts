# SM: Man Up Meal Sign-Up Report

Read-only TouchPoint report for the "SM: Man Up Meal Sign Up 2026-2027"
registration (`OrganizationId = 4053`). Shows who signed up to lead/bring a
meal, one row per night claimed (people who claimed more than one night are
shown as separate rows, flagged `duplicate row` so the count of nights
doesn't get confused with the count of people), sorted by calendar date. Also
lists any nights offered on the form that nobody has claimed yet.

## Background

- The registration URL `https://rockpointe.tpsdb.com/OnlineReg/4053` uses
  TouchPoint's standard `/OnlineReg/{OrganizationId}` pattern -- the number
  is the `OrganizationId`, not a `Registration.RegistrationId` (that field is
  a GUID in this schema, confirmed via `dbo.Registration.RegistrationId` =
  `uniqueidentifier`).
- This event tracks "bring food" as **which Wednesday night the person
  signed up to lead a meal**, via a multi-select registration question --
  not a free-text food field. All 15 claimed dates checked so far land on a
  Wednesday, consistent with SM Wednesdays (Division 42).
- `RegQuestion.Options` holds the full picklist of nights offered on the
  form. The report diffs claimed nights against that list to compute which
  Wednesdays are still missing a volunteer.

## Confirmed IDs (2026-08-17)

| Item | Value |
|---|---|
| OrganizationId | 4053 |
| OrganizationName | SM: Man Up Meal Sign Up 2026-2027 |
| RegistrationTypeId | 26 |
| RegistrationTitle | Man Up Meal Sign-Up 2026-2027 |
| "Enter your information" RegQuestionId | c2cd7305-669e-478f-a03e-990f4ccf7cfd (contact info, not used by this report) |
| "Please choose a night to lead a meal." RegQuestionId | fd1504b9-4cfd-4252-a0f3-f1a34c517c4d (used by this report) |

## Data shape gotcha

`RegAnswer.AnswerValue` for this multi-select question comes back as a
JSON-style array of strings, e.g.:

```
["9/16 Nacho Bar","4/14 Hot Dogs"]
```

The script parses this with `json.loads` first and falls back to a plain
newline/semicolon split if the value isn't valid JSON (defensive, in case a
different TouchPoint question type stores it differently).

## Year inference

The sign-up spans two calendar years. Any date with month >= 8 (Aug-Dec) is
treated as 2026; month < 8 (Jan-May) is treated as 2027. Update
`FALL_MONTH_CUTOFF`, `FALL_YEAR`, `SPRING_YEAR` in the script if this is
reused for a sign-up spanning different years.

## Files

- `SM_ManUpMealSignUpReport.py` -- the deployable TouchPoint Python Script.
- `sql_reference.sql` -- standalone SQL used to discover/confirm the org and
  question IDs above; not required at runtime (the Python script runs its
  own `q.QuerySql` calls), kept for re-verification or reuse on a different
  sign-up org.

## TouchPoint Deployment

- Type: Python Script
- TouchPoint path: `Admin > Advanced > Special Content > Python Scripts > +New`
- Script name: `SM_ManUpMealSignUpReport`
- Dependencies: none beyond stdlib (`re`, `json`, `datetime`)
- Config values to update if reused for a different event:
  - `ORG_ID` -- target registration's `OrganizationId`
  - `NIGHT_QUESTION_ID` -- the `RegQuestionId` for the night/date question
  - `FALL_MONTH_CUTOFF`, `FALL_YEAR`, `SPRING_YEAR` -- if the sign-up spans
    different calendar years than 2026/2027
- Test steps: paste the script into a new Python Script, save, and run it
  directly in TouchPoint. It renders an HTML report on screen -- no email is
  sent by this script.
- Rollback: n/a (read-only, no data mutation).

## Known limitation

If `RegQuestion.Options` isn't populated or doesn't parse (e.g. the picklist
is stored in a different format than one-option-per-line `M/D Meal text`),
the "Missing Nights" section will render an explicit note instead of a
(possibly wrong) empty list. The "Signed-Up Nights" table is unaffected by
that limitation -- it comes straight from actual registrant answers.
