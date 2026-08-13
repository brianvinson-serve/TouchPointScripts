# RockPointe TouchPoint Focused Confirmation — 2026-08-13

Source: `rockpointe-touchpoint-focused-confirmation-2026-08-13.csv`

- Rows: 61
- Columns: 25
- Focused probes: 10
- Probe errors: 0
- SHA-256: `e6265e90ec106f459812d76c28ea64d779b89e319933a6150f0858887c34526b`

All queries were aggregate or lookup-only. No person names, contact information, task text, attendance detail, or arbitrary record samples were exported.

## TaskNote status behavior

`TaskNote.StatusId` uses live values 1–5:

| StatusId | TaskNote rows | IsNote |
|---:|---:|---:|
| 1 | 8,240 | 0 |
| 2 | 334 | 0 |
| 3 | 287 | 0 |
| 4 | 78 | 0 |
| 5 | 103,938 | 1 |

The existing project documentation maps 2 = Pending, 3 = Active/Accepted, and 4 = Declined. Existing task scripts treat 1 as completed and 5 as archived/note history.

Important: `lookup.TaskStatus` is not the lookup behind `TaskNote.StatusId` in this RPC schema. Its seven rows use IDs 10, 20, 30, 40, 50, 60, and 70, and all had zero `TaskNote` joins. All five live `TaskNote.StatusId` values are therefore structurally unmatched to `lookup.TaskStatus`.

The full aggregate showed no current `TaskNote.IsNote IS NULL` rows: task rows use `0`, and note/history rows use `1`. Existing filters may retain `(IsNote = 0 OR IsNote IS NULL)` defensively, but NULL is not the current observed storage behavior.

## TaskNote key

`TaskNote.TaskNoteId` is confirmed selectable and unique:

- Total rows: 112,877
- Non-null `TaskNoteId`: 112,877
- Distinct `TaskNoteId`: 112,877
- Minimum: 2
- Maximum: 115,599

## Organization statuses

| Id | Code | Description | Active | Organization count |
|---:|---|---|---|---:|
| 30 | A | Active | true | 821 |
| 40 | I | Inactive | false | 2,825 |

## Organization types

These are global lookup labels. RockPointe ministry-specific observed usage can be narrower and should be documented separately.

| Id | Code | Description | Organization count |
|---:|---|---|---:|
| 106 | MA | Mobile App | 24 |
| 200 | ASSIM | Assimilation | 86 |
| 201 | BIBLESTUDY | Bible Study/Class | 1,266 |
| 202 | MISSIONS | Community/Missions | 353 |
| 203 | EVENT | Event | 33 |
| 205 | ADMIN | Operations/Admin | 994 |
| 206 | GROUPS | Small Groups | 303 |
| 207 | VOLUNTEER | Volunteers | 476 |

All eight lookup rows have `Attendance = true` and `ShowInMobile = true`.

## Member types

| Id | Code | Description | Pending | Inactive | Organization-member rows |
|---:|---|---|---|---|---:|
| 103 | DR | Director | false | false | 41 |
| 104 | ED | Elder/Deacon Team | false | false | 2 |
| 130 | CH | Chairman | false | false | 0 |
| 136 | CC | Coach | false | false | 33 |
| 140 | L | Leader | false | false | 1,344 |
| 160 | T | Teacher | false | false | 2 |
| 161 | AT | Assistant Teacher | false | false | 0 |
| 162 | SC | Secretary | false | false | 4 |
| 170 | IR | In Reach Leader | false | false | 0 |
| 172 | OR | Outreach Leader | false | false | 0 |
| 220 | M | Member | false | false | 80,404 |
| 230 | IA | InActive | false | true | 454 |
| 300 | VM | Visiting Member | false | false | 0 |
| 310 | G | Guest | false | false | 0 |
| 311 | PR | Prospect | true | false | 108 |
| 415 | HB | Homebound | false | false | 0 |
| 500 | IM | In-Service Member | false | false | 0 |
| 700 | VI | VIP | false | false | 0 |
| 710 | VL | Volunteer | false | false | 36 |

This corrects the previous project note: 220 is Member, 140 is Leader, and 136 is Coach—not substitute.

## DivOrg fan-out

| Division links per organization | Organization count |
|---:|---:|
| 0 | 61 |
| 1 | 2,918 |
| 2 | 577 |
| 3 | 87 |
| 4 | 3 |

A direct `Organizations -> DivOrg` join duplicates organizations with multiple division links. Use `EXISTS`, `DISTINCT`, or deliberate grouping when the desired grain is one row per organization.

## OrgSchedule day values

| SchedDay | Schedule rows | Distinct organizations |
|---:|---:|---:|
| 0 | 255 | 229 |
| 1 | 16 | 16 |
| 2 | 33 | 33 |
| 3 | 54 | 54 |
| 4 | 35 | 35 |
| 5 | 7 | 7 |
| 6 | 25 | 24 |
| 10 | 6 | 6 |

Values 0–6 are used, plus special value 10. The existing RPC convention confirms 0 = Sunday. Do not assume 10 is a weekday; its meaning remains open.

`SchedTime` values carry a date component in the returned representation. Use only the time portion when comparing recurring schedule times.

## Meeting aggregate columns

All 78,126 current `Meetings` rows had non-null values for:

- `NumPresent`
- `NumVstMembers`
- `NumRepeatVst`
- `NumNewVisit`

Observed date range: 2013-03-12 through 2027-08-11. Future scheduled meetings therefore exist; do not interpret `MAX(MeetingDate)` as the latest completed meeting without a completion/date filter.
